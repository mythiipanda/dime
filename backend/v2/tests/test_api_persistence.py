from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from v2.api.events import (
    CustomData,
    FinalAnswer,
    GraphEnd,
    NodeUpdate,
    Suggestions,
    ThoughtStream,
    Token,
    ToolCall,
    ToolResult,
)
from v2.api.routes import router
from v2.api.sse import encode_event
from v2.contracts import Plan, PlanNode, PlanStatus, RunMode, TaskSpec
from v2.projects.service import ProjectStore
from v2.runtime.checkpoints import FileCheckpointStore
from v2.runtime.executor import PlanExecutor
from v2.runtime.fakes import FakeCapability


def _task() -> TaskSpec:
    return TaskSpec(goal="answer", mode=RunMode.PROJECT, deliverable="report")


def _plan() -> Plan:
    return Plan(
        nodes=[
            PlanNode(
                id="one",
                description="first",
                capability_hints=["fake"],
            ),
            PlanNode(
                id="two",
                description="second",
                depends_on=["one"],
                capability_hints=["fake"],
            ),
        ]
    )


def test_sse_adapter_maps_every_frozen_event() -> None:
    events = [
        NodeUpdate(node="data_retrieval", status="running"),
        ThoughtStream(node="data_retrieval", text="thinking"),
        ToolCall(node="tools", name="standings"),
        ToolResult(node="tools", name="standings", status="ok", rows=30, ms=8),
        Token(text="Boston"),
        CustomData(node="analytics", tables=[{"tool": "standings"}]),
        FinalAnswer(text="answer"),
        Suggestions(items=["compare teams"]),
        GraphEnd(),
    ]
    chunks = [encode_event(event) for event in events]
    assert [chunk.splitlines()[0] for chunk in chunks] == [
        f"event: {event.type.value}" for event in events
    ]
    assert all('"type"' not in chunk for chunk in chunks)
    assert chunks[-1] == "event: graph_end\ndata: {}\n\n"


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_checkpoint_resume_does_not_replay_completed_nodes(anyio_backend,
    tmp_path: Path,
) -> None:
    # Dime executor/checkpoint/SSE tasks are supported on the deployed asyncio runtime; Trio is not a production contract.
    assert anyio_backend == "asyncio"
    checkpoints = FileCheckpointStore(tmp_path)
    plan = _plan()
    task = _task()
    completed = plan.nodes[0].model_copy(update={"status": PlanStatus.COMPLETE})
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.checkpoints import ExecutionCheckpoint

    checkpoints.save(ExecutionCheckpoint(version=2,
        run_id="resume", task=task,
        plan=Plan(nodes=[completed, plan.nodes[1]]),
        evidence_by_node={"one": EvidenceEnvelope(
            evidence_id="evidence:one", capability="fake", source="fixture",
            observed_at=datetime.now(UTC), rows={"node": "one"})},
        attempts={"one": 1, "two": 0}, errors={},
    ))
    calls: list[str] = []
    executor = PlanExecutor({
        "fake": FakeCapability(
            "fake", lambda node: calls.append(node.id) or {"node": node.id})
    }, checkpoint_store=checkpoints)
    resumed = await executor.execute(task, plan, run_id="resume")
    assert calls == ["two"]
    assert [node.status for node in resumed.plan.nodes] == [PlanStatus.COMPLETE] * 2



def test_file_checkpoint_rejects_path_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        FileCheckpointStore(tmp_path).load("../escape")


def test_project_store_round_trip(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects.json")
    project = store.create("Celtics outlook")
    assert store.get(project.id) == project
    assert store.list() == [project]


def test_project_contract_requires_timezone_aware_timestamps() -> None:
    from datetime import datetime
    from pydantic import ValidationError
    from v2.projects.models import Project

    with pytest.raises(ValidationError, match="must include timezone"):
        Project(
            id="abc", goal="answer", run_id="project-abc",
            created_at=datetime(2026, 9, 15), updated_at=datetime(2026, 9, 15),
        )
    from datetime import tzinfo
    class MissingOffset(tzinfo):
        def utcoffset(self, dt):
            return None
    invalid = datetime(2026, 9, 15, tzinfo=MissingOffset())
    with pytest.raises(ValidationError, match="must include timezone"):
        Project(
            id="abc", goal="answer", run_id="project-abc",
            created_at=invalid, updated_at=invalid,
        )


def test_project_contract_binds_run_identity() -> None:
    from pydantic import ValidationError
    from v2.projects.models import Project

    with pytest.raises(ValidationError, match="run id must match"):
        Project(id="abc", goal="answer", run_id="project-other")


def test_project_store_rejects_symlinked_database(tmp_path: Path) -> None:
    outside = tmp_path / "outside.sqlite3"
    outside.touch()
    path = tmp_path / "projects.sqlite3"
    path.symlink_to(outside)
    with pytest.raises(ValueError, match="cannot be a symlink"):
        ProjectStore(path)


def test_revision_and_feature_flagged_project_endpoints(
    monkeypatch, tmp_path: Path
) -> None:
    from v2.api import routes

    monkeypatch.setattr(routes, "_PROJECTS", ProjectStore(tmp_path / "projects.json"))
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    revision = client.get("/api/revision")
    assert revision.status_code == 200
    assert set(revision.json()) == {"revision", "executable_sha256", "module_sha256", "prompt_sha256", "warehouse", "semantic_baseline"}
    assert set(revision.json()["warehouse"]) == {"warehouse_id", "sha256"}
    assert revision.json()["warehouse"]["warehouse_id"] in {"frozen-eval", "configured-runtime"}
    assert re.fullmatch(r"[0-9a-f]{64}", revision.json()["warehouse"]["sha256"])
    assert len(revision.json()["executable_sha256"]) == hashlib.sha256().digest_size * 2

    monkeypatch.setenv("DIME_RUNTIME_V2", "off")
    assert client.get("/api/projects").status_code == 404
    monkeypatch.setenv("DIME_RUNTIME_V2", "shadow")
    assert client.get("/api/projects").status_code == 404
    assert client.post(
        "/api/projects", json={"goal": "must not persist"}).status_code == 404
    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    created = client.post("/api/projects", json={"goal": "Celtics outlook"})
    assert created.status_code == 201
    project_id = created.json()["id"]
    assert client.get(f"/api/projects/{project_id}").json()["goal"] == "Celtics outlook"
    assert len(client.get("/api/projects").json()["projects"]) == 1


def test_project_store_handles_independent_workers(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "projects.sqlite3"

    def create(index: int) -> str:
        return ProjectStore(path).create(f"project {index}").id

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(create, range(20)))
    assert len(set(ids)) == 20
    assert len(ProjectStore(path).list()) == 20


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_cancelled_execution_resumes_started_node(anyio_backend, tmp_path: Path) -> None:
    # Dime executor/checkpoint/SSE tasks are supported on the deployed asyncio runtime; Trio is not a production contract.
    assert anyio_backend == "asyncio"
    import asyncio

    checkpoints = FileCheckpointStore(tmp_path)
    started = asyncio.Event()

    class SlowCapability:
        name = "fake"

        async def execute(self, node, task, evidence):
            started.set()
            await asyncio.Event().wait()

    executor = PlanExecutor({"fake": SlowCapability()}, checkpoint_store=checkpoints)
    running = asyncio.create_task(executor.execute(_task(), _plan(), run_id="cancel"))
    await started.wait()
    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running

    checkpoint = checkpoints.load("cancel")
    assert checkpoint is not None
    assert checkpoint.plan.nodes[0].status == PlanStatus.RUNNING

    calls: list[str] = []
    resumed = PlanExecutor(
        {"fake": FakeCapability("fake", lambda node: calls.append(node.id) or {"node": node.id})},
        checkpoint_store=checkpoints,
    )
    result = await resumed.execute(_task(), _plan(), run_id="cancel")
    assert calls == ["one", "two"]
    assert all(node.status == PlanStatus.COMPLETE for node in result.plan.nodes)


def test_quick_answer_route_is_flagged_and_streams_typed_contract(monkeypatch, tmp_path):
    from datetime import UTC, date, datetime
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2 import contracts
    from v2.api import routes
    from v2.runtime.ledger import RunLedger
    from v2.runtime.models import ExecutionResult, RuntimeResult

    monkeypatch.setenv("DIME_RUNTIME_V2", "shadow")
    evidence = contracts.EvidenceEnvelope(
        evidence_id="ev", capability="standings", source="fixture",
        observed_at=datetime.now(UTC), as_of=date(2026, 9, 10),
        rows=[{"TEAM": "Boston", "WINS": 61}])
    result = RuntimeResult(
        task=contracts.TaskSpec(goal="record", mode="quick", deliverable="text"),
        execution=ExecutionResult(
            plan=contracts.Plan(nodes=[contracts.PlanNode(
                id="facts", description="facts", capability_hints=["standings"],
                status="complete")]), evidence_by_node={"facts": evidence}, attempts={"facts": 1}),
        draft=contracts.DraftReport(sections=["Record"], claims=[
            contracts.Claim(text="Boston won 61 games.", kind="observed",
                            evidence_ids=["ev"])]),
        verification=contracts.VerificationReport(
            status="pass", claim_results=[
                contracts.ClaimResult(claim_index=0, supported=True)]),
        verified_claims=[contracts.VerifiedClaim(
            claim_index=0,
            claim=contracts.Claim(text="Boston won 61 games.", kind="observed",
                                  evidence_ids=["ev"]),
            evidence_ids=["ev"], sources=[contracts.ClaimSource(
                evidence_id="ev", source="fixture", capability="standings")])])

    class FakeRuntime:
        async def run(self, request, *, run_id=None, context=()):
            assert context == ()
            return result

    monkeypatch.setattr("v2.runtime.assembly.build_runtime",
                        lambda **kwargs: (FakeRuntime(), RunLedger(kwargs["run_id"])))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post("/api/v2/chat/stream", json={"q": "record?"})

    assert response.status_code == 404
    assert "x-dime-run-id" not in response.headers
    assert "Boston won 61 games." not in response.text


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_stream_cancellation_stops_detached_runtime(anyio_backend, monkeypatch):
    # Dime executor/checkpoint/SSE tasks are supported on the deployed asyncio runtime; Trio is not a production contract.
    assert anyio_backend == "asyncio"
    import asyncio
    from v2.api import routes
    from v2.runtime.ledger import RunLedger

    started = asyncio.Event()
    cancelled = asyncio.Event()

    class WaitingRuntime:
        async def run(self, request, *, run_id=None, context=()):
            started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

    monkeypatch.setattr(
        "app.providers.resolve_model_id", lambda value: ("openrouter", "fixture"))
    monkeypatch.setattr(
        "v2.runtime.assembly.build_runtime",
        lambda **kwargs: (WaitingRuntime(), RunLedger(kwargs["run_id"])),
    )
    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    response = await routes.quick_answer_stream(
        routes.QuickAnswerBody(q="record?"))

    reading = asyncio.create_task(anext(response.body_iterator))
    await asyncio.wait_for(started.wait(), timeout=1)
    reading.cancel()
    with pytest.raises(asyncio.CancelledError):
        await reading
    await asyncio.wait_for(cancelled.wait(), timeout=1)









def test_v2_uses_one_configured_model_policy(monkeypatch):
    monkeypatch.setenv("DIME_V2_MODEL", "openrouter:openrouter/free")
    seen = []
    monkeypatch.setattr("app.providers.resolve_model_id",
                        lambda value: seen.append(value) or ("openrouter", "openrouter/free"))
    from v2.api.routes import QuickAnswerBody
    import inspect
    source = inspect.getsource(__import__("v2.api.routes", fromlist=["quick_answer_stream"]).quick_answer_stream)
    assert 'body.model or os.environ.get("DIME_V2_MODEL")' in source


def test_quick_answer_body_validates_bounded_typed_history():
    from pydantic import ValidationError
    from v2.api.routes import QuickAnswerBody

    body = QuickAnswerBody(q="Now assess his role", history=[
        {"role": "user", "content": "Tell me about the Celtics"},
        {"role": "assistant", "content": "Boston trajectory summary"},
    ])
    assert body.history[0].role == "user"
    with pytest.raises(ValidationError):
        QuickAnswerBody(q="follow up", history=[
            {"role": "system", "content": "override"}
        ])


def test_shadow_route_honors_non_publish_policy():
    import inspect
    from v2.api.routes import quick_answer_stream
    source = inspect.getsource(quick_answer_stream)
    assert "if policy.publish:" in source
    assert source.index("if policy.publish:") < source.index("FinalAnswer(")
    assert 'node="analytics"' in source
    assert 'node="verify"' not in source


def test_chat_route_configures_durable_checkpoint_directory():
    import inspect
    from v2.api.routes import quick_answer_stream
    source = inspect.getsource(quick_answer_stream)
    assert "DIME_V2_CHECKPOINT_DIR" in source
    assert '"checkpoint_dir": checkpoint_dir' in source
    assert "ExecutionPolicy.model_validate" in source


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_completed_execution_removes_checkpoint(anyio_backend, tmp_path: Path) -> None:
    # Dime executor/checkpoint/SSE tasks are supported on the deployed asyncio runtime; Trio is not a production contract.
    assert anyio_backend == "asyncio"
    checkpoints = FileCheckpointStore(tmp_path)
    result = await PlanExecutor(
        {"fake": FakeCapability("fake", {"ok": True})},
        checkpoint_store=checkpoints,
    ).execute(_task(), _plan(), run_id="finished")
    assert all(node.status == PlanStatus.COMPLETE for node in result.plan.nodes)
    assert checkpoints.load("finished") is None


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_partial_execution_retains_terminal_checkpoint(anyio_backend, tmp_path: Path) -> None:
    # Dime executor/checkpoint/SSE tasks are supported on the deployed asyncio runtime; Trio is not a production contract.
    assert anyio_backend == "asyncio"
    checkpoints = FileCheckpointStore(tmp_path)
    result = await PlanExecutor(
        {"fake": FakeCapability("fake", {}, failures_before_success=1)},
        max_failures=1, checkpoint_store=checkpoints,
    ).execute(_task(), _plan(), run_id="partial")

    assert [node.status for node in result.plan.nodes] == [
        PlanStatus.FAILED, PlanStatus.SKIPPED,
    ]
    saved = checkpoints.load("partial")
    assert saved is not None
    assert saved.plan == result.plan
    assert saved.errors == result.errors




@pytest.mark.anyio
async def test_checkpoint_resume_rejects_changed_plan_with_same_node_ids(
    tmp_path: Path,
) -> None:
    from v2.runtime.checkpoints import ExecutionCheckpoint

    checkpoints = FileCheckpointStore(tmp_path)
    original = _plan()
    changed = original.model_copy(deep=True)
    changed.nodes[0].arguments = {"team": "LAL"}
    checkpoints.save(ExecutionCheckpoint(version=2,
        run_id="changed", task=_task(), plan=original,
    ))

    with pytest.raises(ValueError, match="checkpoint plan does not match"):
        await PlanExecutor(
            {"fake": FakeCapability("fake", {})}, checkpoint_store=checkpoints,
        ).execute(_task(), changed, run_id="changed")


@pytest.mark.anyio
@pytest.mark.parametrize("corruption", ["missing_evidence", "wrong_capability", "unknown_node"])
async def test_checkpoint_resume_rejects_inconsistent_execution_state(
    tmp_path: Path, corruption: str,
) -> None:
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.checkpoints import ExecutionCheckpoint

    checkpoints = FileCheckpointStore(tmp_path)
    plan = _plan()
    plan.nodes[0].status = PlanStatus.COMPLETE
    evidence = EvidenceEnvelope(
        evidence_id="evidence:one", capability="fake", source="fixture",
        observed_at=datetime.now(UTC), rows={"node": "one"},
    )
    evidence_by_node = {"one": evidence}
    attempts = {"one": 1}
    if corruption == "missing_evidence":
        evidence_by_node = {}
    elif corruption == "wrong_capability":
        evidence_by_node["one"] = evidence.model_copy(
            update={"capability": "other"})
    else:
        attempts["invented"] = 1
    checkpoints.save(ExecutionCheckpoint(version=2,
        run_id="corrupt", task=_task(), plan=plan,
        evidence_by_node=evidence_by_node, attempts=attempts,
    ))

    with pytest.raises(ValueError, match="checkpoint"):
        await PlanExecutor(
            {"fake": FakeCapability("fake", {})}, checkpoint_store=checkpoints,
        ).execute(_task(), _plan(), run_id="corrupt")


@pytest.mark.anyio
async def test_checkpoint_resume_preserves_attempt_and_failure_budgets(
    tmp_path: Path,
) -> None:
    from v2.runtime.checkpoints import ExecutionCheckpoint

    checkpoints = FileCheckpointStore(tmp_path)
    plan = _plan()
    plan.nodes[0].status = PlanStatus.FAILED
    checkpoints.save(ExecutionCheckpoint(version=2,
        run_id="budget", task=_task(), plan=plan,
        attempts={"one": 1}, errors={"one": ["failed once"]},
    ))
    calls: list[str] = []
    result = await PlanExecutor(
        {"fake": FakeCapability(
            "fake", lambda node: calls.append(node.id) or {"node": node.id})},
        max_failures=1, checkpoint_store=checkpoints,
    ).execute(_task(), _plan(), run_id="budget")

    assert calls == []
    assert [node.status for node in result.plan.nodes] == [
        PlanStatus.FAILED, PlanStatus.SKIPPED,
    ]
    assert result.attempts == {"one": 1, "two": 0}


@pytest.mark.anyio
async def test_checkpoint_rejects_completed_node_with_incomplete_dependency(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.checkpoints import ExecutionCheckpoint

    checkpoints = FileCheckpointStore(tmp_path)
    plan = _plan()
    plan.nodes[1].status = PlanStatus.COMPLETE
    checkpoints.save(ExecutionCheckpoint(version=2,
        run_id="order", task=_task(), plan=plan,
        evidence_by_node={"two": EvidenceEnvelope(
            evidence_id="evidence:two", capability="fake", source="fixture",
            observed_at=datetime.now(UTC), rows={"node": "two"},
        )},
        attempts={"two": 1},
    ))
    with pytest.raises(ValueError, match="completed before its dependencies"):
        await PlanExecutor(
            {"fake": FakeCapability("fake", {})}, checkpoint_store=checkpoints,
        ).execute(_task(), _plan(), run_id="order")


@pytest.mark.anyio
async def test_restored_failure_budget_skips_independent_pending_nodes(
    tmp_path: Path,
) -> None:
    from v2.runtime.checkpoints import ExecutionCheckpoint

    checkpoints = FileCheckpointStore(tmp_path)
    plan = Plan(nodes=[
        PlanNode(id="failed", description="failed", capability_hints=["fake"]),
        PlanNode(id="independent", description="independent", capability_hints=["fake"]),
    ])
    saved = plan.model_copy(deep=True)
    saved.nodes[0].status = PlanStatus.FAILED
    checkpoints.save(ExecutionCheckpoint(version=2,
        run_id="failure-limit", task=_task(), plan=saved,
        attempts={"failed": 1}, errors={"failed": ["failed once"]},
    ))
    calls: list[str] = []
    result = await PlanExecutor(
        {"fake": FakeCapability(
            "fake", lambda node: calls.append(node.id) or {"node": node.id})},
        max_failures=1, checkpoint_store=checkpoints,
    ).execute(_task(), plan, run_id="failure-limit")

    assert calls == []
    assert [node.status for node in result.plan.nodes] == [
        PlanStatus.FAILED, PlanStatus.SKIPPED,
    ]


def test_checkpoint_rejects_blank_run_identity() -> None:
    from pydantic import ValidationError
    from v2.runtime.checkpoints import ExecutionCheckpoint

    with pytest.raises(ValidationError, match="run id must be non-empty"):
        ExecutionCheckpoint(version=2, run_id=" ", task=_task(), plan=_plan())


def test_checkpoint_rejects_unknown_persisted_fields() -> None:
    from datetime import UTC, datetime
    from pydantic import ValidationError
    from v2.runtime.checkpoints import ExecutionCheckpoint

    payload = {
        "run_id": "run",
        "task": {"goal": "answer", "mode": "quick", "deliverable": "text"},
        "plan": {"nodes": []},
        "saved_at": datetime.now(UTC).isoformat(),
    }
    with pytest.raises(ValidationError, match="saved_at"):
        ExecutionCheckpoint.model_validate(payload)


def test_project_record_rejects_unknown_persisted_fields() -> None:
    from pydantic import ValidationError
    from v2.projects.models import Project

    with pytest.raises(ValidationError, match="invented"):
        Project.model_validate({
            "id": "p", "goal": "answer", "run_id": "project-p",
            "invented": True,
        })


@pytest.mark.anyio
async def test_checkpoint_run_identity_must_match_requested_run() -> None:
    from v2.runtime.checkpoints import ExecutionCheckpoint

    class WrongRunStore:
        def load(self, run_id):
            return ExecutionCheckpoint(version=2,
                run_id="other-run",
                task=TaskSpec(goal="answer", mode="quick", deliverable="text"),
                plan=Plan(nodes=[PlanNode(
                    id="one", description="one", capability_hints=["fake"])]),
            )
        def save(self, checkpoint):
            raise AssertionError("mismatched checkpoint was saved")
        def delete(self, run_id):
            raise AssertionError("mismatched checkpoint was deleted")

    task = TaskSpec(goal="answer", mode="quick", deliverable="text")
    plan = Plan(nodes=[PlanNode(
        id="one", description="one", capability_hints=["fake"])])
    with pytest.raises(ValueError, match="run id does not match"):
        await PlanExecutor(
            {"fake": FakeCapability("fake", {"value": 1})},
            checkpoint_store=WrongRunStore(),
        ).execute(task, plan, run_id="requested-run")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status,errors,message",
    [
        (PlanStatus.FAILED, {}, "failed without errors"),
        (PlanStatus.SKIPPED, {"one": ["contradiction"]}, "skipped but carries errors"),
    ],
)
async def test_checkpoint_status_and_errors_must_agree(
    tmp_path: Path, status, errors, message,
) -> None:
    from v2.runtime.checkpoints import ExecutionCheckpoint

    checkpoints = FileCheckpointStore(tmp_path)
    plan = _plan()
    plan.nodes[0].status = status
    checkpoints.save(ExecutionCheckpoint(version=2,
        run_id="status-errors", task=_task(), plan=plan, errors=errors,
    ))
    with pytest.raises(ValueError, match=message):
        await PlanExecutor(
            {"fake": FakeCapability("fake", {})}, checkpoint_store=checkpoints,
        ).execute(_task(), _plan(), run_id="status-errors")


@pytest.mark.anyio
async def test_checkpoint_rejects_unattempted_completed_node(tmp_path: Path) -> None:
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.checkpoints import ExecutionCheckpoint

    checkpoints = FileCheckpointStore(tmp_path)
    plan = _plan()
    plan.nodes[0].status = PlanStatus.COMPLETE
    checkpoints.save(ExecutionCheckpoint(version=2,
        run_id="unattempted", task=_task(), plan=plan,
        evidence_by_node={"one": EvidenceEnvelope(
            evidence_id="one", capability="fake", source="fixture",
            observed_at=datetime.now(UTC), rows={"value": 1},
        )},
    ))
    with pytest.raises(ValueError, match="without an attempt"):
        await PlanExecutor(
            {"fake": FakeCapability("fake", {})}, checkpoint_store=checkpoints,
        ).execute(_task(), _plan(), run_id="unattempted")


@pytest.mark.anyio
async def test_checkpoint_rejects_duplicate_error_messages(tmp_path: Path) -> None:
    from v2.runtime.checkpoints import ExecutionCheckpoint

    checkpoints = FileCheckpointStore(tmp_path)
    plan = _plan()
    plan.nodes[0].status = PlanStatus.FAILED
    checkpoints.save(ExecutionCheckpoint(version=2,
        run_id="duplicate-errors", task=_task(), plan=plan,
        attempts={"one": 1}, errors={"one": ["same", "same"]},
    ))
    with pytest.raises(ValueError, match="duplicate errors"):
        await PlanExecutor(
            {"fake": FakeCapability("fake", {})}, checkpoint_store=checkpoints,
        ).execute(_task(), _plan(), run_id="duplicate-errors")


def test_checkpoint_contract_rejects_oversized_errors() -> None:
    from pydantic import ValidationError
    from v2.runtime.checkpoints import ExecutionCheckpoint

    with pytest.raises(ValidationError, match="4000"):
        ExecutionCheckpoint(version=2,
            run_id="run", task=_task(), plan=_plan(),
            errors={"one": ["x" * 4001]},
        )


@pytest.mark.anyio
async def test_checkpoint_rejects_pending_node_without_attempts_remaining(
    tmp_path: Path,
) -> None:
    from v2.runtime.checkpoints import ExecutionCheckpoint

    checkpoints = FileCheckpointStore(tmp_path)
    checkpoints.save(ExecutionCheckpoint(version=2,
        run_id="exhausted", task=_task(), plan=_plan(), attempts={"one": 1},
        errors={"one": ["prior attempt failed"]},
    ))
    with pytest.raises(ValueError, match="no attempts remaining"):
        await PlanExecutor(
            {"fake": FakeCapability("fake", {})}, checkpoint_store=checkpoints,
        ).execute(_task(), _plan(), run_id="exhausted")


def test_api_request_contracts_reject_unknown_fields() -> None:
    from pydantic import ValidationError
    from v2.api.routes import CreateProjectBody, QuickAnswerBody

    with pytest.raises(ValidationError, match="invented"):
        CreateProjectBody.model_validate({"goal": "analyze", "invented": True})
    with pytest.raises(ValidationError, match="invented"):
        QuickAnswerBody.model_validate({"q": "analyze", "invented": True})


def test_stream_event_contracts_reject_unknown_fields() -> None:
    from pydantic import ValidationError
    from v2.api.events import EVENT_ADAPTER

    with pytest.raises(ValidationError, match="invented"):
        EVENT_ADAPTER.validate_python({
            "type": "node_update", "node": "verify", "status": "complete",
            "invented": True,
        })


def test_node_failure_uses_frontend_error_status() -> None:
    from pydantic import ValidationError
    from v2.api.events import NodeUpdate

    assert NodeUpdate(node="tools", status="error").status == "error"
    with pytest.raises(ValidationError):
        NodeUpdate(node="tools", status="failed")


def test_stream_events_reject_internal_node_names() -> None:
    from pydantic import ValidationError
    from v2.api.events import CustomData, NodeUpdate, ToolCall, ToolResult

    for build in (
        lambda: NodeUpdate(node="verify", status="running"),
        lambda: ToolCall(node="salary", name="contracts"),
        lambda: ToolResult(
            node="execute", name="contracts", status="fail", error="failed"),
        lambda: CustomData(node="synthesize"),
    ):
        with pytest.raises(ValidationError):
            build()


def test_stream_tool_result_rejects_negative_row_count() -> None:
    from pydantic import ValidationError
    from v2.api.events import ToolResult

    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        ToolResult(node="execute", name="standings", status="ok", rows=-1)
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        ToolResult(node="execute", name="standings", status="ok", ms=-1)
    for field in ("rows", "ms"):
        for value in (True, 1.5, "1"):
            with pytest.raises(ValidationError):
                ToolResult(node="execute", name="standings", status="ok",
                           **{field: value})


@pytest.mark.parametrize(
    "event",
    [
        {"type": "node_update", "node": "unknown", "status": "complete"},
        {"type": "token", "text": " "},
        {"type": "final_answer", "text": " "},
        {"type": "suggestions", "items": [" "]},
    ],
)
def test_stream_event_string_fields_must_be_non_empty(event) -> None:
    from pydantic import ValidationError
    from v2.api.events import EVENT_ADAPTER

    with pytest.raises(ValidationError, match="non-empty|empty values|Input should be"):
        EVENT_ADAPTER.validate_python(event)


def test_stream_tool_result_status_matches_error() -> None:
    from pydantic import ValidationError
    from v2.api.events import ToolResult

    with pytest.raises(ValidationError, match="cannot carry an error"):
        ToolResult(node="tools", name="standings", status="ok", error="bad")
    with pytest.raises(ValidationError, match="requires an error"):
        ToolResult(node="tools", name="standings", status="fail")


@pytest.mark.anyio
async def test_checkpoint_resume_rejects_duplicate_evidence_identity(tmp_path: Path) -> None:
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.checkpoints import ExecutionCheckpoint

    checkpoints = FileCheckpointStore(tmp_path)
    plan = _plan()
    for node in plan.nodes:
        node.status = PlanStatus.COMPLETE
    first = EvidenceEnvelope(
        evidence_id="same", capability="fake", source="fixture",
        observed_at=datetime.now(UTC), rows={"node": "one"})
    second = first.model_copy(update={"rows": {"node": "two"}})
    checkpoints.save(ExecutionCheckpoint(version=2,
        run_id="duplicate-evidence", task=_task(), plan=plan,
        evidence_by_node={"one": first, "two": second},
        attempts={"one": 1, "two": 1}))

    with pytest.raises(ValueError, match="checkpoint evidence ids must be unique"):
        await PlanExecutor(
            {"fake": FakeCapability("fake", {})}, checkpoint_store=checkpoints,
        ).execute(_task(), _plan(), run_id="duplicate-evidence")


@pytest.mark.parametrize("changes,error", [
    ({"id": " "}, "identity and goal"),
    ({"status": "complete"}, "requires result"),
    ({"status": "failed"}, "requires error"),
    ({"status": "running", "result": "early"}, "nonterminal"),
    ({"status": "complete", "result": "done", "error": "bad"}, "no error"),
])
def test_project_record_status_contract(changes, error) -> None:
    from datetime import UTC, datetime
    from pydantic import ValidationError
    from v2.projects.models import Project

    values = {"id": "p", "goal": "answer", "run_id": "project-p",
              "created_at": datetime.now(UTC), "updated_at": datetime.now(UTC)}
    values.update(changes)
    with pytest.raises(ValidationError, match=error):
        Project(**values)


def test_project_record_rejects_reverse_timestamps() -> None:
    from datetime import UTC, datetime, timedelta
    from pydantic import ValidationError
    from v2.projects.models import Project

    created = datetime.now(UTC)
    with pytest.raises(ValidationError, match="cannot precede"):
        Project(id="p", goal="answer", run_id="project-p", created_at=created,
                updated_at=created - timedelta(seconds=1))


@pytest.mark.parametrize("schema,payload,error", [
    ("project", {"goal": " "}, "goal"),
    ("quick", {"q": " "}, "question"),
    ("quick", {"q": "record", "model": " "}, "model"),
])
def test_api_request_contracts_reject_blank_fields(schema, payload, error) -> None:
    from pydantic import ValidationError
    from v2.api.routes import CreateProjectBody, QuickAnswerBody

    model = CreateProjectBody if schema == "project" else QuickAnswerBody
    with pytest.raises(ValidationError, match=error):
        model.model_validate(payload)


def test_stream_event_rejects_duplicate_string_lists() -> None:
    from pydantic import ValidationError
    from v2.api.events import CustomData, Suggestions

    with pytest.raises(ValidationError, match="must not contain duplicates"):
        Suggestions(items=["Compare players", "Compare players"])
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        CustomData(node="verify", unverified_numbers=["61", "61"])


def test_checkpoint_save_fsyncs_directory_after_replace(tmp_path, monkeypatch) -> None:
    from v2.runtime.checkpoints import ExecutionCheckpoint

    calls = []
    real_fsync = __import__("os").fsync
    def record(fd):
        calls.append(fd)
        return real_fsync(fd)
    monkeypatch.setattr("v2.runtime.checkpoints.os.fsync", record)
    FileCheckpointStore(tmp_path).save(ExecutionCheckpoint(version=2,
        run_id="durable", task=_task(), plan=_plan()))
    assert len(calls) == 2


def test_checkpoint_delete_fsyncs_directory(tmp_path, monkeypatch) -> None:
    from v2.runtime.checkpoints import ExecutionCheckpoint

    store = FileCheckpointStore(tmp_path)
    store.save(ExecutionCheckpoint(version=2, run_id="delete-durable", task=_task(), plan=_plan()))
    calls = []
    real_fsync = __import__("os").fsync
    def record(fd):
        calls.append(fd)
        return real_fsync(fd)
    monkeypatch.setattr("v2.runtime.checkpoints.os.fsync", record)
    store.delete("delete-durable")
    assert len(calls) == 1
    assert store.load("delete-durable") is None


def test_checkpoint_store_rejects_symlinked_record(tmp_path: Path) -> None:
    from v2.runtime.checkpoints import ExecutionCheckpoint

    outside = tmp_path / "outside.json"
    checkpoint = ExecutionCheckpoint(version=2, run_id="run", task=_task(), plan=_plan())
    outside.write_text(checkpoint.model_dump_json())
    directory = tmp_path / "checkpoints"
    directory.mkdir()
    (directory / "run.json").symlink_to(outside)
    store = FileCheckpointStore(directory)
    for operation in (
        lambda: store.load("run"),
        lambda: store.save(checkpoint),
        lambda: store.delete("run"),
    ):
        with pytest.raises(ValueError, match="cannot be a symlink"):
            operation()


def test_file_checkpoint_store_serializes_same_run_writers(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from v2.runtime.checkpoints import ExecutionCheckpoint

    store = FileCheckpointStore(tmp_path)
    checkpoints = [ExecutionCheckpoint(version=2,
        run_id="shared", task=_task(), plan=_plan(), attempts={"one": index % 2}
    ) for index in range(20)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(store.save, checkpoints))
    loaded = store.load("shared")
    assert loaded in checkpoints
    assert not list(tmp_path.glob(".checkpoint-*"))


def test_checkpoint_store_rejects_symlinked_directory(tmp_path: Path) -> None:
    from v2.runtime.checkpoints import ExecutionCheckpoint

    outside = tmp_path / "outside"
    outside.mkdir()
    directory = tmp_path / "checkpoints"
    directory.symlink_to(outside, target_is_directory=True)
    store = FileCheckpointStore(directory)
    checkpoint = ExecutionCheckpoint(version=2, run_id="run", task=_task(), plan=_plan())
    for operation in (
        lambda: store.load("run"),
        lambda: store.save(checkpoint),
        lambda: store.delete("run"),
    ):
        with pytest.raises(ValueError, match="directory cannot be a symlink"):
            operation()
    assert list(outside.iterdir()) == []


def test_project_store_update_rejects_identity_and_unknown_fields(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects.sqlite3")
    project = store.create("Celtics outlook")
    for changes in ({"id": "other"}, {"run_id": "project-other"},
                    {"created_at": project.created_at}, {"invented": True}):
        with pytest.raises(ValueError, match="unknown fields"):
            store.update(project.id, **changes)
    assert store.get(project.id) == project


def test_project_store_rejects_status_regression_and_terminal_rewrite(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects.sqlite3")
    project = store.create("Celtics outlook")
    store.update(project.id, status="running")
    with pytest.raises(ValueError, match="running to pending"):
        store.update(project.id, status="pending")
    complete = store.update(project.id, status="complete", result="done")
    with pytest.raises(ValueError, match="complete to running"):
        store.update(project.id, status="running", result=None)
    assert store.get(project.id) == complete


def test_project_store_handles_wall_clock_rollback_on_update(
    tmp_path: Path, monkeypatch,
) -> None:
    from datetime import datetime, UTC
    from v2.projects import service

    store = ProjectStore(tmp_path / "projects.sqlite3")
    project = store.create("Celtics outlook")

    class RolledBackDateTime:
        @staticmethod
        def now(timezone):
            assert timezone is UTC
            return datetime(2000, 1, 1, tzinfo=UTC)

    monkeypatch.setattr(service, "datetime", RolledBackDateTime)
    updated = store.update(project.id, status="running")

    assert updated.updated_at == project.updated_at
    assert updated.status == "running"


def test_checkpoint_rejects_noninteger_attempt_counts() -> None:
    from pydantic import ValidationError
    from v2.runtime.checkpoints import ExecutionCheckpoint
    for count in (True, 1.5, "1"):
        with pytest.raises(ValidationError, match="valid integer|attempt counts must be integers"):
            ExecutionCheckpoint(version=2,
                run_id="run", task=_task(), plan=_plan(), attempts={"one": count},
            )


def test_project_store_rejects_invalid_boundary_inputs(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects.sqlite3")
    for goal in (" ", None):
        with pytest.raises((TypeError, ValueError), match="project goal"):
            store.create(goal)
    project = store.create("Celtics outlook")
    for project_id in (" ", None):
        with pytest.raises(ValueError, match="project id"):
            store.get(project_id)
        with pytest.raises(ValueError, match="project id"):
            store.update(project_id, goal="new")
    with pytest.raises(ValueError, match="requires changes"):
        store.update(project.id)


def test_checkpoint_store_rejects_symlinked_parent_directory(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    parent = tmp_path / "parent"
    parent.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="parent cannot be a symlink"):
        FileCheckpointStore(parent / "checkpoints")


def test_project_store_rejects_symlinked_parent_directory(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    parent = tmp_path / "parent"
    parent.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="parent cannot be a symlink"):
        ProjectStore(parent / "projects.sqlite3")
    assert list(outside.iterdir()) == []


def test_project_store_rechecks_parent_before_connect(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    store = ProjectStore(parent / "projects.sqlite3")
    outside = tmp_path / "outside"
    outside.mkdir()
    parent.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="parent cannot be a symlink"):
        store.list()
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm"])
def test_project_store_rejects_symlinked_sqlite_auxiliary_files(
    tmp_path: Path, suffix: str,
) -> None:
    path = tmp_path / "projects.sqlite3"
    outside = tmp_path / "outside"
    outside.write_text("private")
    Path(f"{path}{suffix}").symlink_to(outside)
    with pytest.raises(ValueError, match="auxiliary file cannot be a symlink"):
        ProjectStore(path)
    assert outside.read_text() == "private"


def test_checkpoint_store_revalidates_copied_checkpoint(tmp_path: Path) -> None:
    from pydantic import ValidationError
    from v2.runtime.checkpoints import ExecutionCheckpoint
    valid = ExecutionCheckpoint(version=2, run_id="run", task=_task(), plan=_plan())
    unsafe = valid.model_copy(update={"run_id": " "})
    with pytest.raises(ValidationError, match="run id must be non-empty"):
        FileCheckpointStore(tmp_path).save(unsafe)
    assert list(tmp_path.iterdir()) == []


def test_executable_hash_rejects_symlinked_source(monkeypatch, tmp_path: Path) -> None:
    from v2.api import routes
    backend = tmp_path / "backend"
    app = backend / "app"
    v2 = backend / "v2"
    app.mkdir(parents=True)
    v2.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("private")
    (v2 / "linked.py").symlink_to(outside)
    monkeypatch.setattr(routes, "_BACKEND", backend)
    with pytest.raises(ValueError, match="source tree cannot contain symlinks"):
        routes._executable_sha256()


def test_stream_event_text_has_hard_limits() -> None:
    from pydantic import ValidationError
    from v2.api.events import ToolResult
    with pytest.raises(ValidationError, match="at most 4000 characters"):
        ToolResult(node="execute", name="tool", status="fail", error="x" * 4001)




def test_chat_route_fails_closed_on_unknown_runtime_mode(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2.api import routes

    monkeypatch.setenv("DIME_RUNTIME_V2", "typo")
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")

    response = TestClient(app).post(
        "/api/v2/chat/stream", json={"q": "record?"})

    assert response.status_code == 404


def test_frontend_preserves_public_node_error_status():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[3]
              / "frontend" / "components" / "ChatPanel.tsx").read_text()

    assert 'status === "complete" || status === "error" ? status : "running"' in source
    assert 'd.status === "complete" ? "complete" : "running"' not in source


def test_frontend_answer_citation_preserves_all_distinct_sources():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[3]
              / "frontend" / "components" / "ChatPanel.tsx").read_text()

    assert "function tableSources(" in source
    assert 'lines.join("\\n")' in source
    assert "function firstTableMeta(" not in source
    assert "meta={firstTableMeta(m.ai)}" not in source


def test_frontend_evidence_views_preserve_limitations():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3] / "frontend"
    chat = (root / "lib" / "chat.ts").read_text()
    inline = (root / "components" / "DataArtifacts.tsx").read_text()
    canvas = (root / "components" / "ArtifactCanvas.tsx").read_text()

    for field in ("qualification", "coverage", "warnings"):
        assert field in chat
        assert field in inline
        assert field in canvas
    assert inline.count("<EvidenceLimitations meta={table.meta} />") == 2


def test_frontend_citations_include_evidence_limitations():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3] / "frontend"
    citation = (root / "lib" / "api.ts").read_text()
    chat = (root / "components" / "ChatPanel.tsx").read_text()
    artifacts = (root / "components" / "DataArtifacts.tsx").read_text()

    assert 'Limits: ${limitations.join(" ")}' in citation
    for field in ("qualification", "coverage", "warnings"):
        assert f"{field}: meta.{field}" in chat
        assert f"{field}: meta?.{field}" in artifacts


def test_v2_tool_call_contract_rejects_raw_arguments():
    from pydantic import ValidationError
    from v2.api.events import ToolCall

    with pytest.raises(ValidationError, match="args"):
        ToolCall(node="tools", name="standings", args={"token": "secret"})




def test_v2_sse_recursively_bounds_structured_public_payloads():
    import json
    from v2.api.events import CustomData

    nested = {"leaf": "value"}
    for _ in range(10):
        nested = {"child": nested}
    event = CustomData.model_construct(
        node="analytics",
        tables=[{"tool": "x", "rows": nested}] * 1001,
        unverified_numbers=["9" * 250_000],
    )
    payload = encode_event(event).split("data: ", 1)[1].strip()
    public = json.loads(payload)

    assert len(public["tables"]) == 1000
    cursor = public["tables"][0]["rows"]
    for _ in range(5):
        cursor = cursor["child"]
    assert cursor["child"] is None
    assert len(public["unverified_numbers"][0]) == 200_000


def test_v2_sse_emits_strict_json_for_non_finite_nested_values():
    import json
    import math
    from v2.api.events import CustomData

    # model_construct simulates a future/unvalidated producer crossing the
    # final publication boundary.
    event = CustomData.model_construct(
        node="analytics", tables=[{"value": math.nan, "other": math.inf}],
        unverified_numbers=[],
    )
    payload = encode_event(event).split("data: ", 1)[1].strip()

    assert json.loads(payload)["tables"] == [{"value": None, "other": None}]
    assert "NaN" not in payload
    assert "Infinity" not in payload


def test_v2_sse_boundary_hides_draft_reasoning_and_diagnostics():
    import json

    cases = [
        (Token(text="unverified answer 99"), {"text": ""}),
        (ThoughtStream(node="analytics", text="private chain of thought"), {
            "node": "analytics", "text": "Working through the evidence...",
        }),
        (ToolResult(
            node="tools", name="warehouse", status="ok", rows=1,
            summary="private provider summary", sql="SELECT private FROM secret",
        ), {"node": "tools", "name": "warehouse", "status": "ok", "rows": 1}),
        (ToolResult(
            node="tools", name="warehouse", status="fail",
            error="provider token secret", summary="private provider summary",
        ), {"node": "tools", "name": "warehouse", "status": "fail",
            "error": "Tool failed"}),
    ]

    for event, expected in cases:
        payload = encode_event(event).split("data: ", 1)[1].strip()
        assert json.loads(payload) == expected
    combined = "".join(encode_event(event) for event, _ in cases)
    for secret in (
        "unverified answer 99", "private chain of thought", "SELECT private",
        "provider token secret", "private provider summary",
    ):
        assert secret not in combined


def test_shadow_stream_failure_stays_silent(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2.api import routes
    from v2.runtime.ledger import LedgerKind, RunLedger

    ledgers = {}

    class BrokenRuntime:
        async def run(self, request, *, run_id=None, context=()):
            ledger = ledgers[run_id]
            ledger.append(
                LedgerKind.TOOL_CALL, turn_id=run_id, call_id="call",
                data={"name": "secret_tool", "args": {"token": "private"}},
            )
            ledger.append(
                LedgerKind.TOOL_RESULT, turn_id=run_id, call_id="call",
                data={"status": "failed", "error": "provider secret"},
            )
            raise RuntimeError("private failure")

    def build(**kwargs):
        ledger = RunLedger(kwargs["run_id"])
        ledgers[kwargs["run_id"]] = ledger
        return BrokenRuntime(), ledger

    monkeypatch.setenv("DIME_RUNTIME_V2", "shadow")
    monkeypatch.setattr(
        "app.providers.resolve_model_id", lambda value: ("openrouter", "fixture"))
    monkeypatch.setattr("v2.runtime.assembly.build_runtime", build)
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post("/api/v2/chat/stream", json={"q": "record?"})

    assert response.status_code == 404
    assert "x-dime-run-id" not in response.headers
    for private in ("secret_tool", "private", "provider secret"):
        assert private not in response.text


def test_frontend_can_select_native_v2_chat_runtime():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[3] / "frontend" / "lib" / "api.ts").read_text()
    assert 'process.env.NEXT_PUBLIC_CHAT_RUNTIME === "v2"' in source
    assert '"/api/v2/chat/stream"' in source
    assert 'JSON.stringify({ q, model, thread, client: getClientId() })' in source




















def test_live_route_reports_pre_stream_setup_failure_as_sse(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2.api import routes

    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setattr(
        "v2.runtime.assembly.build_runtime",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("private setup detail")),
    )
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post("/api/v2/chat/stream", json={"q": "record?"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-dime-run-id"].startswith("run-")
    assert "event: error" in response.text
    assert "Dime could not start this run." in response.text
    assert response.headers["x-dime-run-id"] in response.text
    assert "private setup detail" not in response.text
    assert response.text.rstrip().endswith("data: {}")


def test_live_route_reports_model_resolution_failure_as_sse(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2.api import routes

    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setattr(
        "app.providers.resolve_model_id",
        lambda *_: (_ for _ in ()).throw(ValueError("private model detail")),
    )
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post("/api/v2/chat/stream", json={"q": "record?"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: error" in response.text
    assert "private model detail" not in response.text




def test_final_carry_exports_structural_flags():
    from v2.api import routes
    source = Path(routes.__file__).read_text()
    assert '"structural_flags": list(getattr(result, "structural_flags", []))' in source







def test_intake_provider_failure_yields_typed_partial_final_without_error(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2.api import routes
    from v2.runtime import LedgerKind, RunLedger
    ledgers = {}
    class BrokenIntakeRuntime:
        async def run(self, request, *, run_id=None, context=()):
            ledger = ledgers[run_id]
            ledger.append(LedgerKind.STEP_START, turn_id=run_id,
                          step_id="understand")
            ledger.append(LedgerKind.STEP_END, turn_id=run_id, step_id="understand",
                          data={"reason":"failed", "duration_ms":7,
                                "error":"private provider detail"})
            raise RuntimeError("private provider detail")
    def build(**kwargs):
        ledger = RunLedger(kwargs["run_id"]); ledgers[kwargs["run_id"]] = ledger
        return BrokenIntakeRuntime(), ledger
    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setattr("app.providers.resolve_model_id",
                        lambda value:("openrouter","fixture"))
    monkeypatch.setattr("v2.runtime.assembly.build_runtime", build)
    app = FastAPI(); app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post("/api/v2/chat/stream", json={"q":"record?"})
    assert "event: error" not in response.text
    assert "event: final_answer" in response.text
    assert '"verification":"partial"' in response.text
    assert '"verified_claims":0' in response.text
    assert response.text.rstrip().endswith("event: graph_end\ndata: {}")
    assert "private provider detail" not in response.text




def test_public_sse_projection_omits_real_envelope_source_identity():
    from datetime import UTC,datetime
    from v2.contracts import EvidenceEnvelope
    from v2.api.events import CustomData
    from v2.api.sse import encode_event
    from v2.api.routes import public_evidence_table
    item=EvidenceEnvelope(evidence_id='e',capability='team_ratings',source='fixture',observed_at=datetime.now(UTC),rows=[],source_identity={'kind':'warehouse','warehouse_id':'frozen-eval','sha256':'a'*64})
    payload=encode_event(CustomData(node='analytics',tables=[public_evidence_table(item)]))
    assert 'source_identity' not in payload and 'a'*64 not in payload and 'warehouse_id' not in payload


def test_revision_warehouse_identity_is_safe_and_startup_bound(monkeypatch, tmp_path):
    from app import store
    from v2.api import routes
    warehouse = tmp_path / "configured.duckdb"
    warehouse.write_bytes(b"startup bytes")
    monkeypatch.setattr(store, "DB_PATH", warehouse)
    routes.runtime_warehouse_identity.cache_clear()
    try:
        first = routes.runtime_warehouse_identity()
        assert first == {"warehouse_id": "configured-runtime",
                         "sha256": hashlib.sha256(b"startup bytes").hexdigest()}
        assert set(first) == {"warehouse_id", "sha256"}
        assert str(warehouse) not in repr(first)
        warehouse.write_bytes(b"mutated later")
        assert routes.runtime_warehouse_identity() == first
    finally:
        routes.runtime_warehouse_identity.cache_clear()


def test_real_lifespan_freezes_revision_warehouse_endpoint(monkeypatch, tmp_path):
    from app import main, store
    from v2.api import routes
    warehouse = tmp_path / "startup.duckdb"
    startup = b"startup warehouse bytes"
    warehouse.write_bytes(startup)
    monkeypatch.setattr(store, "DB_PATH", warehouse)
    routes.runtime_warehouse_identity.cache_clear()
    routes.runtime_asset_manifest.cache_clear()
    import json
    manifest_path = tmp_path / "expected-assets.json"
    manifest_path.write_text(json.dumps(routes.runtime_asset_manifest().as_dict()))
    monkeypatch.setenv("DIME_EXPECTED_ASSET_MANIFEST", str(manifest_path))
    try:
        with TestClient(main.app) as client:
            expected = {"warehouse_id": "configured-runtime",
                        "sha256": hashlib.sha256(startup).hexdigest()}
            first = client.get("/api/revision").json()["warehouse"]
            assert first == expected
            assert re.fullmatch(r"[0-9a-f]{64}", first["sha256"])
            warehouse.write_bytes(b"mutated while process is live")
            assert client.get("/api/revision").json()["warehouse"] == expected
            # Endpoint callers receive a copy, not the cached dictionary.
            routes.revision()["warehouse"]["warehouse_id"] = "tampered"
            assert client.get("/api/revision").json()["warehouse"] == expected
    finally:
        routes.runtime_warehouse_identity.cache_clear()




def test_full_http_sse_and_activity_omit_private_failure_taxonomy(monkeypatch,tmp_path):
    import json
    from v2.api import routes
    from v2.api.activity import ActivityJournal
    from v2.contracts import TaskSpec,DraftReport,VerificationReport
    from v2.runtime import RunLedger
    from v2.runtime.models import RuntimeResult
    from v2.runtime.executor import ExecutionResult
    from v2.contracts import Plan
    sentinel='SECRET_SENTINEL_MUST_NOT_LEAK'
    class Runtime:
        async def run(self,*a,**k):
            return RuntimeResult(task=TaskSpec(goal='g',mode='quick',deliverable='d'),execution=ExecutionResult(plan=Plan(nodes=[]),errors={}),draft=DraftReport(sections=[],claims=[]),verification=VerificationReport(status='pass'))
    def build(**kwargs):
        ledger=RunLedger(kwargs['run_id']);ledger.append('model/request',turn_id=kwargs['run_id'],call_id='model:1',data={'provider':'inception','model':'mercury-2.5','route':'semantic_verifier','prompt_hash':'a'*64,'context_hash':'b'*64,'tool_schema_hash':'c'*64,'planner_version':'v2','budgets':{},'skill_hashes':{}});ledger.append('assistant/attempt',turn_id=kwargs['run_id'],call_id='model:1',data={'status':'failed','error':sentinel,'provider_attempts':[{'route':'semantic_verifier','provider':'inception','model':'mercury-2.5','attempt_number':1,'exception_type':'UnexpectedModelBehavior','message_class':'structured_output','latency_ms':1,'failure_top_class':'UnexpectedModelBehavior','failure_class_chain':['UnexpectedModelBehavior'],'failure_phase':'no_tool_or_empty','failure_validation_errors':[],'failure_validation_subtype':'not_applicable','failure_schema_sha256':'a'*64,'failure_route':'semantic_verifier'}]});return Runtime(),ledger
    monkeypatch.setenv('DIME_RUNTIME_V2','on');monkeypatch.setenv('DIME_V2_ACTIVITY_DIR',str(tmp_path/'activity'));monkeypatch.setattr('app.providers.resolve_model_id',lambda value:('inception','mercury-2.5'));monkeypatch.setattr('v2.runtime.assembly.build_runtime',build)
    app=FastAPI();app.include_router(routes.router,prefix='/api');response=TestClient(app).post('/api/v2/chat/stream',json={'q':'x'});text=response.text;run_id=response.headers['x-dime-run-id'];activity=[x.model_dump(mode='json') for x in ActivityJournal(tmp_path/'activity'/f'{run_id}.jsonl',run_id).read()];combined=text+json.dumps(activity)
    for key in ('failure_top_class','failure_class_chain','failure_phase','failure_validation_errors','failure_validation_subtype','failure_schema_sha256','provider_attempts','exception_type'):
        assert key not in combined
    assert sentinel not in combined







def _write_expected_manifest(path, manifest):
    import json
    path.write_text(json.dumps(manifest.as_dict()))
    return path


def test_runtime_asset_manifest_is_deeply_immutable(monkeypatch):
    from v2.api import routes
    manifest=routes.runtime_asset_manifest()
    with pytest.raises((TypeError,AttributeError)):manifest.revision='x'
    with pytest.raises(TypeError):manifest.prompt_sha256['semantic_verifier']='x'
    with pytest.raises(TypeError):manifest.warehouse['sha256']='x'
    with pytest.raises(TypeError):manifest.semantic_baseline['baseline_id']='x'
    with pytest.raises(TypeError):manifest.module_sha256['routes']='x'
    copied=manifest.as_dict();copied['prompt_sha256']['semantic_verifier']='x'
    assert manifest.prompt_sha256['semantic_verifier']!='x'


def test_preflight_exact_match_and_each_mismatch(monkeypatch,tmp_path):
    import json
    from v2.api import routes
    observed=routes.runtime_asset_manifest();exact=_write_expected_manifest(tmp_path/'exact.json',observed)
    assert routes.preflight_runtime_assets(exact) is observed
    for field in ('revision','executable_sha256','module_sha256','warehouse','semantic_baseline','prompt_sha256'):
        candidate=observed.as_dict()
        if isinstance(candidate[field],dict):candidate[field][next(iter(candidate[field]))]='wrong'
        else:candidate[field]='wrong'
        path=tmp_path/f'{field}.json';path.write_text(json.dumps(candidate))
        with pytest.raises(RuntimeError,match='does not match'):routes.preflight_runtime_assets(path)


def test_registry_completeness_rejects_missing_and_extra(monkeypatch):
    from v2.api import routes
    from v2.adapters import models
    original=dict(models._PROVIDER_ROUTE_PROMPT_NAMES)
    for changed in ({k:v for k,v in original.items() if k!='planner'}, {**original,'extra':'intake'}):
        monkeypatch.setattr(models,'_PROVIDER_ROUTE_PROMPT_NAMES',changed)
        monkeypatch.setattr(models,'_PROVIDER_ROUTE_PROMPTS',None)
        routes.runtime_asset_manifest.cache_clear()
        with pytest.raises(RuntimeError,match='incomplete or has extra'):routes.runtime_asset_manifest()
    monkeypatch.setattr(models,'_PROVIDER_ROUTE_PROMPT_NAMES',original);monkeypatch.setattr(models,'_PROVIDER_ROUTE_PROMPTS',None);routes.runtime_asset_manifest.cache_clear()


def test_loaded_module_hash_detects_old_import_against_new_expected(monkeypatch,tmp_path):
    import json
    from v2.api import routes
    old=routes.runtime_asset_manifest();expected=old.as_dict();expected['module_sha256']['routes']='new-loaded-code-hash'
    path=tmp_path/'new.json';path.write_text(json.dumps(expected))
    with pytest.raises(RuntimeError,match='does not match'):routes.preflight_runtime_assets(path)


def test_real_lifespan_freezes_manifest_and_runtime_prompts(monkeypatch,tmp_path):
    from app import main
    from v2.api import routes
    from v2.adapters import models
    routes.runtime_asset_manifest.cache_clear();models._PROVIDER_ROUTE_PROMPTS=None
    observed=routes.runtime_asset_manifest();path=_write_expected_manifest(tmp_path/'expected.json',observed)
    monkeypatch.setenv('DIME_EXPECTED_ASSET_MANIFEST',str(path))
    with TestClient(main.app) as client:
        first=client.get('/api/revision').json();assert first==observed.as_dict()
        assert first['prompt_sha256']['semantic_verifier']==hashlib.sha256(models.provider_route_prompt('semantic_verifier','verifier').encode()).hexdigest()
        verifier_path=routes._BACKEND/'v2/prompts/verifier.md';original=verifier_path.read_bytes()
        try:
            verifier_path.write_bytes(b'later verifier')
            assert client.get('/api/revision').json()==first
            assert hashlib.sha256(models.provider_route_prompt('semantic_verifier','verifier').encode()).hexdigest()==first['prompt_sha256']['semantic_verifier']
        finally:verifier_path.write_bytes(original)


def test_lifespan_fails_before_serving_on_expected_mismatch(monkeypatch,tmp_path):
    import json
    from app import main
    from v2.api import routes
    expected=routes.runtime_asset_manifest().as_dict();expected['revision']='wrong'
    path=tmp_path/'wrong.json';path.write_text(json.dumps(expected));monkeypatch.setenv('DIME_EXPECTED_ASSET_MANIFEST',str(path))
    with pytest.raises(RuntimeError,match='does not match'):
        with TestClient(main.app):pass


def test_loaded_behavior_fingerprint_changes_on_import_time_registry_binding(monkeypatch):
    from v2.api import routes
    from v2.adapters import models
    original=routes._loaded_behavior_sha256(models,{"provider_route_prompt_names":models._PROVIDER_ROUTE_PROMPT_NAMES})
    changed=dict(models._PROVIDER_ROUTE_PROMPT_NAMES);changed['semantic_verifier']='different_import_time_binding'
    changed_hash=routes._loaded_behavior_sha256(models,{"provider_route_prompt_names":changed})
    assert changed_hash!=original
    observed=routes.runtime_asset_manifest().as_dict();expected={**observed,"module_sha256":{**observed['module_sha256'],"models":changed_hash}}
    assert expected['executable_sha256']==observed['executable_sha256']
    assert expected['module_sha256']['models']!=observed['module_sha256']['models']


def test_preflight_rejects_expected_manifest_inside_executable_roots(tmp_path):
    import json
    from v2.api import routes
    inside=routes._BACKEND/'v2'/'expected-assets-test.json'
    try:
        inside.write_text(json.dumps(routes.runtime_asset_manifest().as_dict()))
        with pytest.raises(RuntimeError,match='external to executable roots'):
            routes.preflight_runtime_assets(inside)
    finally:
        inside.unlink(missing_ok=True)


def test_typed_public_stream_sanitizes_all_events_and_preserves_lifecycle(monkeypatch,tmp_path):
    from datetime import UTC,datetime
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2 import contracts
    from v2.api import routes
    from v2.runtime.ledger import RunLedger
    from v2.runtime.models import ExecutionResult,RuntimeResult
    secret="SECRET_NEVER_PUBLIC"
    binding=contracts.EvidenceOutputBinding(requirement_kind="task",output_id="PTS",
        node_id="internal-node",evidence_id="internal-evidence",selector="rows.lebron.PTS",
        row_selector="rows.lebron",subject_entity_type="player",subject_entity_id="23",
        subject_selector="rows.lebron.PLAYER_ID",value={"kind":"integer","value":25},
        unit={"kind":"unitless"},domain="player_report")
    claim=contracts.Claim(text=secret,kind="observed",evidence_ids=["internal-evidence"],output_bindings=[binding])
    evidence=contracts.EvidenceEnvelope(evidence_id="internal-evidence",capability="player_report",
        source=secret,observed_at=datetime.now(UTC),entities=[contracts.EntityRef(id="23",type="player",display_name="LeBron")],rows={"lebron":{"PLAYER_ID":"23","PTS":25,"AST":8},"curry":{"PLAYER_ID":"987654321","PTS":987654321}})
    result=RuntimeResult(task=contracts.TaskSpec(goal="x",mode="quick",deliverable="x",requested_outputs=["PTS"],entities=[contracts.EntityRef(id="23",type="player",display_name="LeBron")]),
        execution=ExecutionResult(plan=contracts.Plan(nodes=[contracts.PlanNode(id="internal-node",description="x",capability_hints=["player_report"],status="complete")]),evidence_by_node={"internal-node":evidence},attempts={"internal-node":1}),
        draft=contracts.DraftReport(sections=[],claims=[claim]),verification=contracts.VerificationReport(status="partial",claim_results=[{"claim_index":0,"supported":True}]),
        verified_claims=[contracts.VerifiedClaim(claim_index=0,claim=claim,evidence_ids=["internal-evidence"],sources=[contracts.ClaimSource(evidence_id="internal-evidence",source=secret,capability="player_report")],output_bindings=[binding])],
        gaps=[contracts.Gap(kind="missing_evidence",message=secret)])
    holder={}
    class Runtime:
        async def run(self,*a,**k):
            import asyncio
            holder["progress"]("verify","running")
            asyncio.get_running_loop().call_soon(
                holder["progress"], "verify", "complete")
            await asyncio.sleep(0)
            return result
    def build(**kwargs):
        holder["progress"]=kwargs["progress"]
        return Runtime(),RunLedger(kwargs["run_id"])
    monkeypatch.setenv("DIME_RUNTIME_V2","on");monkeypatch.setenv("DIME_PROJECT_STORE",str(tmp_path/"p.sqlite"))
    monkeypatch.setattr("app.providers.resolve_model_id",lambda value:("openrouter","fixture"))
    monkeypatch.setattr("v2.runtime.assembly.build_runtime",build)
    monkeypatch.setattr(routes,"_PROJECTS",ProjectStore(tmp_path/"p.sqlite"))
    app=FastAPI();app.include_router(routes.router,prefix="/api")
    response=TestClient(app).post("/api/v2/chat/stream",json={"q":"x"})
    text=response.text
    for forbidden in [secret,"internal-node","internal-evidence","rows.lebron.PTS","curry","AST","987654321"]:
        assert forbidden not in text
    assert text.count("event: final_answer")==1 and text.count("event: graph_end")==1
    assert text.index("event: final_answer") < text.index("event: graph_end")
    assert text.count("event: work_log")==1
    assert text.index("event: work_log") < text.index("event: custom_data")
    assert text.index("event: final_answer") < text.index("event: graph_end")
    terminal=text[text.index("event: final_answer"):]
    assert terminal.count("event: ")==2
    assert response.headers["x-dime-run-id"] in text
    final_json=__import__("json").loads(text.split("event: final_answer\ndata: ",1)[1].split("\n\n",1)[0])
    carry=final_json["carry"]
    assert carry["run_id"]==response.headers["x-dime-run-id"]
    assert carry["verification"]=="partial" and carry["verified_claims"]==1
    assert carry["gaps"]==[{"kind":"missing_evidence"}]
    assert carry["output_statuses"][0]["output_id"]=="PTS"
    assert "node_id" not in str(carry) and "selector" not in str(carry)
    assert text.count('"node":"analytics","status":"complete"')==1


def test_public_stream_projection_failure_abstains_and_terminates(monkeypatch,tmp_path):
    from datetime import UTC,datetime
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2 import contracts
    from v2.api import routes
    from v2.runtime.ledger import RunLedger
    from types import SimpleNamespace
    secret="FAIL_SECRET"
    binding=contracts.EvidenceOutputBinding(requirement_kind="task",output_id="WINS",node_id="n",evidence_id="e",selector="rows.WINS",value={"kind":"integer","value":61},unit={"kind":"declared","value":"count"},domain="standings")
    status=contracts.OutputFinalStatus(requirement_kind="task",output_id="WINS",status="complete",claim_index=0,binding=binding)
    stale=contracts.EvidenceEnvelope(evidence_id="e",capability="standings",source=secret,observed_at=datetime.now(UTC),rows={"WINS":62})
    result=SimpleNamespace(output_statuses=[status],draft=contracts.DraftReport(sections=[],claims=[]),execution=SimpleNamespace(evidence=[stale]),verification=SimpleNamespace(status=SimpleNamespace(value="pass")),verified_claims=[],gaps=[],structural_flags=[])
    holder={}
    class Runtime:
        async def run(self,*a,**k):holder["progress"]("verify","running");return result
    def build(**kwargs):holder["progress"]=kwargs["progress"];return Runtime(),RunLedger(kwargs["run_id"])
    monkeypatch.setenv("DIME_RUNTIME_V2","on");monkeypatch.setattr("app.providers.resolve_model_id",lambda value:("openrouter","fixture"));monkeypatch.setattr("v2.runtime.assembly.build_runtime",build);monkeypatch.setattr(routes,"_PROJECTS",ProjectStore(tmp_path/"p.sqlite"))
    app=FastAPI();app.include_router(routes.router,prefix="/api")
    response=TestClient(app).post("/api/v2/chat/stream",json={"q":"x"});text=response.text
    assert secret not in text and '"node":"analytics"' not in text
    assert text.count("event: work_log")==1 and '"status":"partial"' in text
    assert text.count("event: final_answer")==1 and text.count("event: graph_end")==1
    assert text.index("event: work_log") < text.index("event: final_answer") < text.index("event: graph_end")






















def test_typed_terminal_contract_replaces_legacy_failure_and_metadata_cases(monkeypatch,tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2.api import routes
    from v2.runtime.ledger import RunLedger
    secret="EXCEPTION_SECRET"
    class Runtime:
        async def run(self,*a,**k): raise RuntimeError(secret)
    monkeypatch.setenv("DIME_RUNTIME_V2","on");monkeypatch.setattr("app.providers.resolve_model_id",lambda value:("openrouter","fixture"));monkeypatch.setattr("v2.runtime.assembly.build_runtime",lambda **k:(Runtime(),RunLedger(k["run_id"])));monkeypatch.setattr(routes,"_PROJECTS",ProjectStore(tmp_path/"p.sqlite"))
    app=FastAPI();app.include_router(routes.router,prefix="/api");r=TestClient(app).post("/api/v2/chat/stream",json={"q":"x"});text=r.text
    assert secret not in text and "event: error" not in text
    assert text.count("event: work_log")==text.count("event: final_answer")==text.count("event: graph_end")==1
    final=text.split("event: final_answer",1)[1].split("\n\n",1)[0]
    for field in ['"run_id"','"verification":"partial"','"verified_claims":0','"gaps"','"stage_latencies_ms"']:assert field in final


def test_public_provenance_separates_season_and_as_of():
    from datetime import UTC,date,datetime
    from types import SimpleNamespace
    from v2.api.routes import _public_evidence_tables
    from v2 import contracts
    b=contracts.EvidenceOutputBinding(requirement_kind="task",output_id="WINS",node_id="n",evidence_id="e",selector="rows.WINS",value={"kind":"integer","value":61},unit={"kind":"declared","value":"count"},domain="standings")
    st=contracts.OutputFinalStatus(requirement_kind="task",output_id="WINS",status="complete",claim_index=0,binding=b)
    ev=contracts.EvidenceEnvelope(evidence_id="e",capability="standings",source="private",observed_at=datetime.now(UTC),season="2025-26",as_of=date(2026,4,1),rows={"WINS":61})
    tables=_public_evidence_tables(SimpleNamespace(output_statuses=[st],draft=contracts.DraftReport(sections=[],claims=[]),execution=SimpleNamespace(evidence=[ev])))
    assert tables[0]["provenance"]=={"capability":"standings","season":"2025-26","as_of":"2026-04-01"}
    assert "private" not in str(tables)


def test_no_authority_with_internal_gap_still_nonblank_and_terminal():
    from types import SimpleNamespace
    from v2.api.routes import _answer_text
    from v2.contracts import Gap
    text=_answer_text(SimpleNamespace(output_statuses=[],gaps=[Gap(kind="execution_failure",message="SECRET")]))
    assert text.strip() and "SECRET" not in text


def test_journal_setup_and_append_failures_keep_generic_fallback_once(monkeypatch,tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2.api import routes
    from v2.runtime.ledger import LedgerKind,RunLedger
    ledgers={}
    class Broken:
        async def run(self,*a,run_id=None,**k):
            l=ledgers[run_id];l.append(LedgerKind.TOOL_CALL,turn_id=run_id,step_id="s",call_id="c",data={"name":"contracts","args":{"secret":"SECRET"}});l.append(LedgerKind.TOOL_RESULT,turn_id=run_id,step_id="s",call_id="c",data={"status":"failed","error":"SECRET"});raise RuntimeError("SECRET")
    class BadJournal:
        def __init__(self,*a,**k):pass
        def append(self,*a,**k):raise OSError("SECRET")
    for journal in [lambda *a,**k:(_ for _ in ()).throw(PermissionError("SECRET")),BadJournal]:
        monkeypatch.setattr("v2.api.activity.ActivityJournal",journal);monkeypatch.setenv("DIME_RUNTIME_V2","on");monkeypatch.setattr("app.providers.resolve_model_id",lambda value:("openrouter","fixture"));monkeypatch.setattr(routes,"_PROJECTS",ProjectStore(tmp_path/"p.sqlite"))
        def build(**k):l=RunLedger(k["run_id"]);ledgers[k["run_id"]]=l;return Broken(),l
        monkeypatch.setattr("v2.runtime.assembly.build_runtime",build);app=FastAPI();app.include_router(routes.router,prefix="/api");text=TestClient(app).post("/api/v2/chat/stream",json={"q":"x"}).text
        assert text.count("event: tool_call")==1 and text.count("event: tool_result")==1
        assert '"name":"tool"' in text and "SECRET" not in text
        assert text.count("event: final_answer")==text.count("event: graph_end")==1


def test_pretool_timeout_safe_terminal_carries_latency(monkeypatch,tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2.api import routes
    from v2.runtime import LedgerKind,PreToolTimeoutError,RunLedger
    ledgers={}
    class Timeout:
        async def run(self,*a,run_id=None,**k):
            l=ledgers[run_id];l.append(LedgerKind.STEP_START,turn_id=run_id,step_id="understand");l.append(LedgerKind.STEP_END,turn_id=run_id,step_id="understand",data={"reason":"timeout","duration_ms":12,"error":"SECRET"});raise PreToolTimeoutError("SECRET")
    def build(**k):l=RunLedger(k["run_id"]);ledgers[k["run_id"]]=l;return Timeout(),l
    monkeypatch.setenv("DIME_RUNTIME_V2","on");monkeypatch.setattr("app.providers.resolve_model_id",lambda value:("openrouter","fixture"));monkeypatch.setattr("v2.runtime.assembly.build_runtime",build);monkeypatch.setattr(routes,"_PROJECTS",ProjectStore(tmp_path/"p.sqlite"));app=FastAPI();app.include_router(routes.router,prefix="/api");response=TestClient(app).post("/api/v2/chat/stream",json={"q":"x"});text=response.text
    assert "SECRET" not in text and '"stage_latencies_ms":{"understand":12}' in text
    assert '"status":"partial"' in text
    assert text.count("event: work_log")==text.count("event: final_answer")==text.count("event: graph_end")==1
    assert response.headers["x-dime-run-id"] in text
    assert text.index("event: work_log") < text.index("event: final_answer") < text.index("event: graph_end")


def test_pass_result_final_carry_contract(monkeypatch,tmp_path):
    # Reuse the admitted route fixture semantics without gaps.
    from datetime import UTC,datetime
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2 import contracts
    from v2.api import routes
    from v2.runtime.models import ExecutionResult,RuntimeResult
    from v2.runtime.ledger import RunLedger
    b=contracts.EvidenceOutputBinding(requirement_kind="task",output_id="WINS",node_id="n",evidence_id="e",selector="rows.WINS",value={"kind":"integer","value":61},unit={"kind":"declared","value":"count"},domain="standings")
    c=contracts.Claim(text="private prose",kind="observed",evidence_ids=["e"],output_bindings=[b]);ev=contracts.EvidenceEnvelope(evidence_id="e",capability="standings",source="private",observed_at=datetime.now(UTC),rows={"WINS":61})
    result=RuntimeResult(task=contracts.TaskSpec(goal="x",mode="quick",deliverable="x",requested_outputs=["WINS"]),execution=ExecutionResult(plan=contracts.Plan(nodes=[contracts.PlanNode(id="n",description="n",capability_hints=["standings"],status="complete")]),evidence_by_node={"n":ev},attempts={"n":1}),draft=contracts.DraftReport(sections=[],claims=[c]),verification=contracts.VerificationReport(status="pass",claim_results=[{"claim_index":0,"supported":True}]),verified_claims=[contracts.VerifiedClaim(claim_index=0,claim=c,evidence_ids=["e"],sources=[contracts.ClaimSource(evidence_id="e",source="private",capability="standings")],output_bindings=[b])])
    class Runtime:
        async def run(self,*a,**k):return result
    monkeypatch.setenv("DIME_RUNTIME_V2","on");monkeypatch.setattr("app.providers.resolve_model_id",lambda value:("openrouter","fixture"));monkeypatch.setattr("v2.runtime.assembly.build_runtime",lambda **k:(Runtime(),RunLedger(k["run_id"])));monkeypatch.setattr(routes,"_PROJECTS",ProjectStore(tmp_path/"p.sqlite"));app=FastAPI();app.include_router(routes.router,prefix="/api");r=TestClient(app).post("/api/v2/chat/stream",json={"q":"x"});payload=__import__("json").loads(r.text.split("event: final_answer\ndata: ",1)[1].split("\n\n",1)[0]);carry=payload["carry"]
    assert carry["run_id"]==r.headers["x-dime-run-id"] and carry["verification"]=="pass"
    assert carry["verified_claims"]==1 and carry["gaps"]==[] and len(carry["output_statuses"])==1


def test_no_authority_internal_gap_route_is_nonblank_and_terminal(monkeypatch,tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2 import contracts
    from v2.api import routes
    from v2.runtime.models import ExecutionResult,RuntimeResult
    from v2.runtime.ledger import RunLedger
    result=RuntimeResult(task=contracts.TaskSpec(goal="x",mode="quick",deliverable="x"),execution=ExecutionResult(plan=contracts.Plan(nodes=[])),draft=contracts.DraftReport(sections=[],claims=[]),verification=contracts.VerificationReport(status="partial"),gaps=[contracts.Gap(kind="execution_failure",message="SECRET")])
    class Runtime:
        async def run(self,*a,**k):return result
    monkeypatch.setenv("DIME_RUNTIME_V2","on");monkeypatch.setattr("app.providers.resolve_model_id",lambda value:("openrouter","fixture"));monkeypatch.setattr("v2.runtime.assembly.build_runtime",lambda **k:(Runtime(),RunLedger(k["run_id"])));monkeypatch.setattr(routes,"_PROJECTS",ProjectStore(tmp_path/"p.sqlite"));app=FastAPI();app.include_router(routes.router,prefix="/api");text=TestClient(app).post("/api/v2/chat/stream",json={"q":"x"}).text
    assert "SECRET" not in text and text.count("event: work_log")==text.count("event: final_answer")==text.count("event: graph_end")==1
    payload=__import__("json").loads(text.split("event: final_answer\ndata: ",1)[1].split("\n\n",1)[0]);assert payload["text"].strip()


def test_runtime_manifest_pins_accepted_semantic_baseline():
    from v2.api import routes
    assert routes.runtime_asset_manifest().as_dict()["semantic_baseline"] == {
        "baseline_id": "dime-warehouse-2025-26-finals-v1",
        "warehouse_sha256": "4099efbefe5c3ba6e0026b837d95cfd421f6844f75a3516e51d00976bfbbe183",
        "logical_content_id": "81969a2d902583aea99c2d8b1a09673b941c63e649bdf6fb6ce09a8aff591a08",
        "manifest_self_hash": "c8ba316cc4d50c666208874a5d04d9788a312e450781d057b823a63aadb446ac",
    }

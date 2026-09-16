from __future__ import annotations

import hashlib
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
        NodeUpdate(node="planner", status="running"),
        ThoughtStream(node="planner", text="thinking"),
        ToolCall(node="execute", name="standings", args={"season": "2025-26"}),
        ToolResult(node="execute", name="standings", status="ok", rows=30, ms=8),
        Token(text="Boston"),
        CustomData(node="execute", tables=[{"tool": "standings"}]),
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
async def test_checkpoint_resume_does_not_replay_completed_nodes(
    tmp_path: Path,
) -> None:
    checkpoints = FileCheckpointStore(tmp_path)
    plan = _plan()
    task = _task()
    completed = plan.nodes[0].model_copy(update={"status": PlanStatus.COMPLETE})
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.checkpoints import ExecutionCheckpoint

    checkpoints.save(ExecutionCheckpoint(
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
    assert set(revision.json()) == {"revision", "executable_sha256"}
    assert len(revision.json()["executable_sha256"]) == hashlib.sha256().digest_size * 2

    monkeypatch.setenv("DIME_RUNTIME_V2", "off")
    assert client.get("/api/projects").status_code == 404
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
async def test_cancelled_execution_resumes_started_node(tmp_path: Path) -> None:
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
    from datetime import UTC, datetime
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2 import contracts
    from v2.api import routes
    from v2.runtime.ledger import RunLedger
    from v2.runtime.models import ExecutionResult, RuntimeResult

    monkeypatch.setenv("DIME_RUNTIME_V2", "shadow")
    evidence = contracts.EvidenceEnvelope(
        evidence_id="ev", capability="standings", source="fixture",
        observed_at=datetime.now(UTC), rows=[{"TEAM": "Boston", "WINS": 61}])
    result = RuntimeResult(
        task=contracts.TaskSpec(goal="record", mode="quick", deliverable="text"),
        execution=ExecutionResult(
            plan=contracts.Plan(nodes=[contracts.PlanNode(
                id="facts", description="facts", capability_hints=["standings"],
                status="complete")]), evidence=[evidence], attempts={"facts": 1}),
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

    assert response.status_code == 200
    assert response.headers["x-dime-run-id"].startswith("run-")
    assert "event: custom_data" in response.text
    assert "event: final_answer" not in response.text
    assert "Boston won 61 games." not in response.text
    assert response.text.rstrip().endswith("data: {}")


def test_answer_text_publishes_only_adjudicated_model_prose():
    from v2 import contracts
    from v2.api.routes import _answer_text
    from v2.runtime.models import ExecutionResult, RuntimeResult

    supported = contracts.Claim(
        text="Boston won 61 games.", kind="observed", evidence_ids=["ev"])
    rejected = contracts.Claim(
        text="Boston won 62 games.", kind="observed", evidence_ids=["ev"])
    result = RuntimeResult(
        task=contracts.TaskSpec(goal="record", mode="quick", deliverable="text"),
        execution=ExecutionResult(plan=contracts.Plan(nodes=[])),
        draft=contracts.DraftReport(
            sections=["Record"], claims=[supported, rejected]),
        verification=contracts.VerificationReport(
            status="partial", claim_results=[
                contracts.ClaimResult(claim_index=0, supported=True),
                contracts.ClaimResult(claim_index=1, supported=False,
                                      reasons=["uncited numeral 62"]),
            ]),
        verified_claims=[contracts.VerifiedClaim(
            claim_index=0, claim=supported, evidence_ids=["ev"])],
        gaps=[contracts.Gap(
            kind="source_conflict",
            message="salary evidence is 2026-27, not 2025-26",
            blocks=["trade_math"])])
    text = _answer_text(result)
    assert "61 games" in text
    assert "62 games" not in text
    assert "salary evidence is 2026-27, not 2025-26" in text


def test_rejected_claim_cannot_publish_after_reverify_warning():
    from v2 import contracts
    from v2.api.routes import _answer_text
    from v2.runtime.models import ExecutionResult, RuntimeResult

    wrong = contracts.Claim(
        text="The true-shooting leader was at 71.2%.",
        kind="observed", evidence_ids=["ts"])
    result = RuntimeResult(
        task=contracts.TaskSpec(goal="TS leader", mode="quick", deliverable="text"),
        execution=ExecutionResult(plan=contracts.Plan(nodes=[])),
        draft=contracts.DraftReport(sections=["Leader"], claims=[wrong]),
        verification=contracts.VerificationReport(
            status="partial", claim_results=[contracts.ClaimResult(
                claim_index=0, supported=False,
                reasons=["uncited numeral 71.2%"])]),
        verified_claims=[],
        gaps=[contracts.Gap(
            kind="unsupported_claim", message="uncited numeral 71.2%",
            blocks=["claim:0"])])
    text = _answer_text(result)
    assert "The true-shooting leader" not in text
    assert text == "uncited numeral 71.2%"

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


def test_chat_route_configures_durable_checkpoint_directory():
    import inspect
    from v2.api.routes import quick_answer_stream
    source = inspect.getsource(quick_answer_stream)
    assert "DIME_V2_CHECKPOINT_DIR" in source
    assert 'model_copy(update={"checkpoint_dir": checkpoint_dir})' in source


@pytest.mark.anyio
async def test_completed_execution_removes_checkpoint(tmp_path: Path) -> None:
    checkpoints = FileCheckpointStore(tmp_path)
    result = await PlanExecutor(
        {"fake": FakeCapability("fake", {"ok": True})},
        checkpoint_store=checkpoints,
    ).execute(_task(), _plan(), run_id="finished")
    assert all(node.status == PlanStatus.COMPLETE for node in result.plan.nodes)
    assert checkpoints.load("finished") is None


def test_live_route_reports_terminal_runtime_failure(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2.api import routes
    from v2.runtime.ledger import RunLedger

    monkeypatch.setenv("DIME_RUNTIME_V2", "on")

    class BrokenRuntime:
        async def run(self, request, *, run_id=None, context=()):
            raise ValueError("private provider detail")

    monkeypatch.setattr("v2.runtime.assembly.build_runtime",
                        lambda **kwargs: (BrokenRuntime(), RunLedger(kwargs["run_id"])))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post("/api/v2/chat/stream", json={"q": "record?"})
    assert "event: error" in response.text
    assert "Dime could not complete this run." in response.text
    assert "private provider detail" not in response.text
    assert response.text.rstrip().endswith("data: {}")


@pytest.mark.anyio
async def test_checkpoint_resume_rejects_changed_plan_with_same_node_ids(
    tmp_path: Path,
) -> None:
    from v2.runtime.checkpoints import ExecutionCheckpoint

    checkpoints = FileCheckpointStore(tmp_path)
    original = _plan()
    changed = original.model_copy(deep=True)
    changed.nodes[0].arguments = {"team": "LAL"}
    checkpoints.save(ExecutionCheckpoint(
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
    checkpoints.save(ExecutionCheckpoint(
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
    checkpoints.save(ExecutionCheckpoint(
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
    checkpoints.save(ExecutionCheckpoint(
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
    checkpoints.save(ExecutionCheckpoint(
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
        ExecutionCheckpoint(run_id=" ", task=_task(), plan=_plan())


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
            return ExecutionCheckpoint(
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
    checkpoints.save(ExecutionCheckpoint(
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
    checkpoints.save(ExecutionCheckpoint(
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
    checkpoints.save(ExecutionCheckpoint(
        run_id="duplicate-errors", task=_task(), plan=plan,
        attempts={"one": 1}, errors={"one": ["same", "same"]},
    ))
    with pytest.raises(ValueError, match="duplicate errors"):
        await PlanExecutor(
            {"fake": FakeCapability("fake", {})}, checkpoint_store=checkpoints,
        ).execute(_task(), _plan(), run_id="duplicate-errors")


@pytest.mark.anyio
async def test_checkpoint_rejects_pending_node_without_attempts_remaining(
    tmp_path: Path,
) -> None:
    from v2.runtime.checkpoints import ExecutionCheckpoint

    checkpoints = FileCheckpointStore(tmp_path)
    checkpoints.save(ExecutionCheckpoint(
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


def test_stream_tool_result_rejects_negative_row_count() -> None:
    from pydantic import ValidationError
    from v2.api.events import ToolResult

    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        ToolResult(node="execute", name="standings", status="ok", rows=-1)
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        ToolResult(node="execute", name="standings", status="ok", ms=-1)


@pytest.mark.parametrize(
    "event",
    [
        {"type": "node_update", "node": " ", "status": "complete"},
        {"type": "token", "text": " "},
        {"type": "final_answer", "text": " "},
        {"type": "suggestions", "items": [" "]},
    ],
)
def test_stream_event_string_fields_must_be_non_empty(event) -> None:
    from pydantic import ValidationError
    from v2.api.events import EVENT_ADAPTER

    with pytest.raises(ValidationError, match="non-empty|empty values"):
        EVENT_ADAPTER.validate_python(event)


def test_stream_tool_result_status_matches_error() -> None:
    from pydantic import ValidationError
    from v2.api.events import ToolResult

    with pytest.raises(ValidationError, match="cannot carry an error"):
        ToolResult(node="execute", name="standings", status="ok", error="bad")
    with pytest.raises(ValidationError, match="requires an error"):
        ToolResult(node="execute", name="standings", status="fail")


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
    checkpoints.save(ExecutionCheckpoint(
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
    FileCheckpointStore(tmp_path).save(ExecutionCheckpoint(
        run_id="durable", task=_task(), plan=_plan()))
    assert len(calls) == 2

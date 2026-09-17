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
    assert set(revision.json()) == {"revision", "executable_sha256"}
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

    assert response.status_code == 404
    assert "x-dime-run-id" not in response.headers
    assert "Boston won 61 games." not in response.text


@pytest.mark.anyio
async def test_stream_cancellation_stops_detached_runtime(monkeypatch):
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


def test_failed_stream_tool_result_keeps_its_call_identity(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2.api import routes
    from v2.runtime.ledger import LedgerKind, RunLedger

    ledgers = {}

    class BrokenRuntime:
        async def run(self, request, *, run_id=None, context=()):
            ledger = ledgers[run_id]
            ledger.append(
                LedgerKind.TOOL_CALL, turn_id=run_id, step_id="salary",
                call_id="tool:salary:1",
                data={
                    "name": "contracts",
                    "args": {
                        "node": {
                            "id": "salary", "description": "private plan text",
                            "depends_on": [], "capability_hints": ["contracts"],
                            "arguments": {"team": "BOS"}, "max_attempts": 1,
                            "status": "pending",
                        },
                        "task": {
                            "goal": "private normalized task", "mode": "quick",
                            "deliverable": "answer", "entities": [], "season": None,
                            "as_of": None, "subquestions": [],
                            "required_evidence": [], "assumptions": [],
                            "open_questions": [], "skills": [],
                        },
                        "evidence_ids": [],
                    },
                },
            )
            ledger.append(
                LedgerKind.TOOL_RESULT, turn_id=run_id, step_id="salary",
                call_id="tool:salary:1",
                data={"status": "failed", "error": "source unavailable"},
            )
            raise RuntimeError("stop")

    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setattr(
        "app.providers.resolve_model_id", lambda value: ("openrouter", "fixture"))

    def build(**kwargs):
        ledger = RunLedger(kwargs["run_id"])
        ledgers[kwargs["run_id"]] = ledger
        return BrokenRuntime(), ledger

    monkeypatch.setattr("v2.runtime.assembly.build_runtime", build)
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post(
        "/api/v2/chat/stream", json={"q": "salary?"})

    assert '"name":"contracts"' in response.text
    assert '"name":"tool"' not in response.text
    assert '"error":"Tool failed"' in response.text
    assert 'source unavailable' not in response.text
    assert '"args"' not in response.text
    assert '"team":"BOS"' not in response.text
    assert '"node":"tools"' in response.text
    assert '"node":"salary"' not in response.text
    assert 'private normalized task' not in response.text
    assert 'private plan text' not in response.text


def test_v2_final_answer_carries_run_and_verification_metadata(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2.api import routes
    from v2.runtime.ledger import RunLedger

    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setattr(
        "app.providers.resolve_model_id", lambda value: ("openrouter", "fixture"))
    from types import SimpleNamespace
    result = SimpleNamespace(
        verified_claims=[SimpleNamespace(
            claim=SimpleNamespace(text="Boston won 61 games."))],
        gaps=[],
        verification=SimpleNamespace(status=SimpleNamespace(value="pass")),
        execution=SimpleNamespace(evidence=[]),
    )

    class Runtime:
        async def run(self, request, *, run_id=None, context=()):
            return result

    monkeypatch.setattr(
        "v2.runtime.assembly.build_runtime",
        lambda **kwargs: (Runtime(), RunLedger(kwargs["run_id"])),
    )
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post(
        "/api/v2/chat/stream", json={"q": "record?"})

    final_chunk = response.text.split("event: final_answer", 1)[1].split("\n\n", 1)[0]
    assert '"carry"' in final_chunk
    assert '"run_id"' in final_chunk
    assert '"verification":"pass"' in final_chunk
    assert '"verified_claims":1' in final_chunk
    assert '"gaps":[]' in final_chunk


def test_answer_text_publishes_only_adjudicated_model_prose():
    from datetime import UTC, datetime
    from v2 import contracts
    from v2.api.routes import _answer_text
    from v2.runtime.models import ExecutionResult, RuntimeResult

    supported = contracts.Claim(
        text="Boston won 61 games.", kind="observed", evidence_ids=["ev"])
    rejected = contracts.Claim(
        text="Boston won 62 games.", kind="observed", evidence_ids=["ev"])
    evidence = contracts.EvidenceEnvelope(
        evidence_id="ev", capability="standings", source="fixture",
        observed_at=datetime.now(UTC), rows={"wins": 61})
    result = RuntimeResult(
        task=contracts.TaskSpec(goal="record", mode="quick", deliverable="text"),
        execution=ExecutionResult(
            plan=contracts.Plan(nodes=[contracts.PlanNode(
                id="facts", description="facts", capability_hints=["standings"],
                status="complete")]),
            evidence=[evidence], attempts={"facts": 1}),
        draft=contracts.DraftReport(
            sections=["Record"], claims=[supported, rejected]),
        verification=contracts.VerificationReport(
            status="partial", claim_results=[
                contracts.ClaimResult(claim_index=0, supported=True),
                contracts.ClaimResult(claim_index=1, supported=False,
                                      reasons=["uncited numeral 62"]),
            ]),
        verified_claims=[contracts.VerifiedClaim(
            claim_index=0, claim=supported, evidence_ids=["ev"],
            sources=[contracts.ClaimSource(
                evidence_id="ev", source="fixture", capability="standings")])],
        gaps=[contracts.Gap(
            kind="source_conflict",
            message="salary evidence is 2026-27, not 2025-26",
            blocks=["trade_math"])])
    text = _answer_text(result)
    assert "61 games" in text
    assert "62 games" not in text
    assert "The available sources conflict on part of this answer." in text


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
    assert text in {
        "I could not verify a publishable answer from the available data.",
        "Some supporting data was unavailable.",
    }

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
async def test_completed_execution_removes_checkpoint(tmp_path: Path) -> None:
    checkpoints = FileCheckpointStore(tmp_path)
    result = await PlanExecutor(
        {"fake": FakeCapability("fake", {"ok": True})},
        checkpoint_store=checkpoints,
    ).execute(_task(), _plan(), run_id="finished")
    assert all(node.status == PlanStatus.COMPLETE for node in result.plan.nodes)
    assert checkpoints.load("finished") is None


@pytest.mark.anyio
async def test_partial_execution_retains_terminal_checkpoint(tmp_path: Path) -> None:
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


def test_checkpoint_contract_rejects_oversized_errors() -> None:
    from pydantic import ValidationError
    from v2.runtime.checkpoints import ExecutionCheckpoint

    with pytest.raises(ValidationError, match="4000"):
        ExecutionCheckpoint(
            run_id="run", task=_task(), plan=_plan(),
            errors={"one": ["x" * 4001]},
        )


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


def test_checkpoint_delete_fsyncs_directory(tmp_path, monkeypatch) -> None:
    from v2.runtime.checkpoints import ExecutionCheckpoint

    store = FileCheckpointStore(tmp_path)
    store.save(ExecutionCheckpoint(run_id="delete-durable", task=_task(), plan=_plan()))
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
    checkpoint = ExecutionCheckpoint(run_id="run", task=_task(), plan=_plan())
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
    checkpoints = [ExecutionCheckpoint(
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
    checkpoint = ExecutionCheckpoint(run_id="run", task=_task(), plan=_plan())
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
            ExecutionCheckpoint(
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
    valid = ExecutionCheckpoint(run_id="run", task=_task(), plan=_plan())
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


def test_answer_text_never_exposes_internal_execution_error():
    from v2 import contracts
    from v2.api.routes import _answer_text
    from v2.runtime.loop import _verification_gaps
    from v2.runtime.models import ExecutionResult, RuntimeResult

    draft = contracts.DraftReport(sections=["No answer"], claims=[])
    report = contracts.VerificationReport(status="partial")
    gaps = _verification_gaps(
        draft, report,
        {"salary": ["AdapterError: private warehouse path /secret/db"]},
    )
    result = RuntimeResult(
        task=contracts.TaskSpec(goal="trade", mode="quick", deliverable="answer"),
        execution=ExecutionResult(plan=contracts.Plan(nodes=[
            contracts.PlanNode(
                id="salary", description="salary",
                capability_hints=["contracts"], max_attempts=1, status="failed",
            )
        ]), attempts={"salary": 1}, errors={"salary": ["private"]}),
        draft=draft, verification=report, gaps=gaps,
    )

    text = _answer_text(result)
    assert text in {
        "I could not verify a publishable answer from the available data.",
        "Some supporting data was unavailable.",
    }
    assert "/secret/db" not in text
    assert "AdapterError" not in text


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


def test_v2_stream_failure_does_not_publish_exception_type(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2.api import routes
    from v2.runtime.ledger import RunLedger

    class BrokenRuntime:
        async def run(self, *args, **kwargs):
            raise RuntimeError("provider token secret")

    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setattr(
        "app.providers.resolve_model_id", lambda value: ("openrouter", "fixture"))
    monkeypatch.setattr(
        "v2.runtime.assembly.build_runtime",
        lambda **kwargs: (BrokenRuntime(), RunLedger(kwargs["run_id"])),
    )
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post("/api/v2/chat/stream", json={"q": "record?"})

    assert "Dime could not complete this run." in response.text
    assert "RuntimeError" not in response.text
    assert "provider token secret" not in response.text


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


def test_answer_text_does_not_publish_verifier_repair_diagnostics():
    from datetime import UTC, datetime
    from v2 import contracts
    from v2.api.routes import _answer_text
    from v2.runtime.loop import _verification_gaps
    from v2.runtime.models import ExecutionResult, RuntimeResult

    supported = contracts.Claim(
        text="Boston went 56-26.", kind="observed", evidence_ids=["ev"])
    evidence = contracts.EvidenceEnvelope(
        evidence_id="ev", capability="standings", source="fixture",
        observed_at=datetime.now(UTC), rows={"record": "56-26"})
    report = contracts.VerificationReport(
        status="partial",
        claim_results=[contracts.ClaimResult(claim_index=0, supported=True)],
        repair_instructions=["Repair claim 1: execution failed for changes"],
    )
    result = RuntimeResult(
        task=contracts.TaskSpec(goal="changes", mode="quick", deliverable="answer"),
        execution=ExecutionResult(plan=contracts.Plan(nodes=[contracts.PlanNode(
            id="facts", description="facts", capability_hints=["standings"],
            status="complete")]), evidence=[evidence], attempts={"facts": 1}),
        draft=contracts.DraftReport(sections=["Record"], claims=[supported]),
        verification=report,
        verified_claims=[contracts.VerifiedClaim(
            claim_index=0, claim=supported, evidence_ids=["ev"],
            sources=[contracts.ClaimSource(
                evidence_id="ev", source="fixture", capability="standings")])],
        gaps=[contracts.Gap(
            kind="missing_evidence",
            message="verification did not establish complete support")],
    )

    text = _answer_text(result)
    assert text.startswith("Boston went 56-26.")
    assert "Repair claim" not in text
    assert "execution failed" not in text


def test_answer_text_deduplicates_and_sanitizes_internal_gap_labels():
    from v2 import contracts
    from v2.api.routes import _answer_text
    from v2.runtime.models import ExecutionResult, RuntimeResult

    result = RuntimeResult(
        task=contracts.TaskSpec(goal="record", mode="quick", deliverable="answer"),
        execution=ExecutionResult(plan=contracts.Plan(nodes=[])),
        draft=contracts.DraftReport(sections=[], claims=[]),
        verification=contracts.VerificationReport(status="partial"),
        gaps=[
            contracts.Gap(kind="execution_failure", message="execution failed for playoffs_2425"),
            contracts.Gap(kind="execution_failure", message="execution failed for standings_2526"),
        ],
    )
    assert _answer_text(result) == "Some supporting data was unavailable."


def test_answer_text_removes_repair_directives_and_repeated_gaps():
    from v2 import contracts
    from v2.api.routes import _answer_text
    from v2.runtime.models import ExecutionResult, RuntimeResult

    result = RuntimeResult(
        task=contracts.TaskSpec(goal="trade", mode="quick", deliverable="answer"),
        execution=ExecutionResult(plan=contracts.Plan(nodes=[])),
        draft=contracts.DraftReport(sections=[], claims=[]),
        verification=contracts.VerificationReport(status="partial"),
        gaps=[
            contracts.Gap(kind="missing_evidence", message="Repair claim 0: entity mismatch"),
            contracts.Gap(kind="missing_evidence", message="fit evidence was unavailable"),
            contracts.Gap(kind="source_conflict", message="fit evidence was unavailable"),
        ],
    )
    assert _answer_text(result) == "fit evidence was unavailable The available sources conflict on part of this answer."


def test_answer_text_hides_mechanical_verifier_reasons():
    from v2 import contracts
    from v2.api.routes import _answer_text
    from v2.runtime.models import ExecutionResult, RuntimeResult
    result = RuntimeResult(
        task=contracts.TaskSpec(goal="record", mode="quick", deliverable="answer"),
        execution=ExecutionResult(plan=contracts.Plan(nodes=[])),
        draft=contracts.DraftReport(sections=[], claims=[contracts.Claim(
            text="Boston ranked first.", kind="judgment")]),
        verification=contracts.VerificationReport(status="partial", claim_results=[
            contracts.ClaimResult(claim_index=0, supported=False,
                                  reasons=["rank claim lacks qualification evidence"])]),
        gaps=[contracts.Gap(kind="unsupported_claim",
             message="rank claim lacks qualification evidence", blocks=["claim:0"])],
    )
    text = _answer_text(result)
    assert text in {
        "I could not verify a publishable answer from the available data.",
        "Some supporting data was unavailable.",
    }
    assert "qualification" not in text


def test_answer_text_hides_policy_and_tool_directives():
    from v2 import contracts
    from v2.api.routes import _answer_text
    from v2.runtime.models import ExecutionResult, RuntimeResult
    raw = [
        "undeclared source identity",
        "Usage rate rank lacks coverage and qualification evidence",
        "Identify or query a tool for role context",
        "Ensure contract evidence matches the salary season",
    ]
    result = RuntimeResult(
        task=contracts.TaskSpec(goal="value", mode="quick", deliverable="answer"),
        execution=ExecutionResult(plan=contracts.Plan(nodes=[])),
        draft=contracts.DraftReport(sections=[], claims=[], gaps=list(dict.fromkeys(raw))),
        verification=contracts.VerificationReport(status="partial"),
        gaps=[contracts.Gap(kind="missing_evidence", message=item) for item in raw],
    )
    text = _answer_text(result)
    assert text in {
        "I could not verify a publishable answer from the available data.",
        "Some supporting data was unavailable.",
    }
    assert all(item not in text for item in raw)


def test_answer_text_drops_internal_followup_and_capability_language():
    from v2 import contracts
    from v2.api.routes import _answer_text
    from v2.runtime.models import ExecutionResult, RuntimeResult
    raw = [
        "Include data on roster or coaching changes between seasons.",
        "Update the recommendation section once gaps are resolved.",
        "Legal clearance verification via trades capability",
        "trades evidence was unavailable",
    ]
    result = RuntimeResult(
        task=contracts.TaskSpec(goal="trade", mode="quick", deliverable="answer"),
        execution=ExecutionResult(plan=contracts.Plan(nodes=[contracts.PlanNode(
            id="legal", description="legality", capability_hints=["trades"],
            status="failed")]), attempts={"legal": 1}, errors={"legal": ["failed"]}),
        draft=contracts.DraftReport(sections=[], claims=[], gaps=list(dict.fromkeys(raw))),
        verification=contracts.VerificationReport(status="partial"),
        gaps=[contracts.Gap(kind="missing_evidence", message=item) for item in raw],
    )
    assert _answer_text(result) == (
        "I could not verify a publishable answer from the available data."
    )


def test_answer_text_drops_final_showcase_directives_and_deduplicates_age_gap():
    from v2 import contracts
    from v2.api.routes import _answer_text
    from v2.runtime.models import ExecutionResult, RuntimeResult
    raw = [
        "Locate contract evidence listing Jaylen Brown's 2026-27 salary to authorize terms.",
        "Add contract year and option details",
        "Official cap impact for Boston",
        "Official cap impact for Boston",
        "Player age risk assessment",
    ]
    result = RuntimeResult(
        task=contracts.TaskSpec(goal="trade", mode="quick", deliverable="answer"),
        execution=ExecutionResult(plan=contracts.Plan(nodes=[])),
        draft=contracts.DraftReport(sections=[], claims=[], gaps=list(dict.fromkeys(raw))),
        verification=contracts.VerificationReport(status="partial"),
        gaps=[contracts.Gap(kind="missing_evidence", message=item)
              for item in dict.fromkeys(raw)],
    )
    assert _answer_text(result) == (
        "Age-related risk was not available in the retrieved player data.")


def test_answer_text_deduplicates_result_outcome_variants():
    from v2 import contracts
    from v2.api.routes import _answer_text
    from v2.runtime.models import ExecutionResult, RuntimeResult
    result = RuntimeResult(
        task=contracts.TaskSpec(goal="trajectory", mode="quick", deliverable="answer"),
        execution=ExecutionResult(plan=contracts.Plan(nodes=[])),
        draft=contracts.DraftReport(sections=[], claims=[], gaps=[
            "2024-25 playoff results", "2024-25 playoff outcomes"]),
        verification=contracts.VerificationReport(status="partial"),
        gaps=[contracts.Gap(kind="missing_evidence", message="2024-25 playoff results"),
              contracts.Gap(kind="missing_evidence", message="2024-25 playoff outcomes")],
    )
    assert _answer_text(result) == "2024-25 playoff results"


def test_answer_text_drops_verify_directive_and_bare_label_duplicate():
    from v2 import contracts
    from v2.api.routes import _answer_text
    from v2.runtime.models import ExecutionResult, RuntimeResult
    messages = [
        "The available evidence does not include the 2024-25 playoff outcomes.",
        "2024-25 playoff outcomes",
        "Verify contract salary for Jaylen Brown for the 2026-27 season from an alternative contract source.",
    ]
    result = RuntimeResult(
        task=contracts.TaskSpec(goal="trajectory", mode="quick", deliverable="answer"),
        execution=ExecutionResult(plan=contracts.Plan(nodes=[])),
        draft=contracts.DraftReport(sections=[], claims=[], gaps=messages),
        verification=contracts.VerificationReport(status="partial"),
        gaps=[contracts.Gap(kind="missing_evidence", message=item) for item in messages],
    )
    assert _answer_text(result) == messages[0]


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


def test_evidence_export_separates_source_vintage_from_observation_time():
    import inspect
    from v2.api.routes import quick_answer_stream
    source = inspect.getsource(quick_answer_stream)
    assert '"source_as_of": item.as_of.isoformat()' in source
    assert '"observed_at": item.observed_at.isoformat()' in source
    assert 'else item.observed_at.isoformat()' not in source


def test_final_carry_exports_structural_flags():
    from v2.api import routes
    source = Path(routes.__file__).read_text()
    assert '"structural_flags": list(getattr(result, "structural_flags", []))' in source


def test_live_route_exposes_structured_pre_tool_timeout_and_stage_latency(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2.api import routes
    from v2.runtime import LedgerKind, PreToolTimeoutError, RunLedger

    ledgers = {}

    class TimedOutRuntime:
        async def run(self, request, *, run_id=None, context=()):
            ledger = ledgers[run_id]
            ledger.append(LedgerKind.TURN_START, turn_id=run_id,
                          data={"request": request})
            ledger.append(LedgerKind.STEP_START, turn_id=run_id,
                          step_id="understand")
            ledger.append(LedgerKind.STEP_END, turn_id=run_id,
                          step_id="understand", data={
                              "reason": "timeout", "duration_ms": 12,
                              "error": "private timeout detail",
                          })
            ledger.append(LedgerKind.TURN_END, turn_id=run_id, data={
                "reason": "timeout", "error": "private timeout detail",
            })
            raise PreToolTimeoutError("private timeout detail")

    def build(**kwargs):
        ledger = RunLedger(kwargs["run_id"])
        ledgers[kwargs["run_id"]] = ledger
        return TimedOutRuntime(), ledger

    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setattr(
        "app.providers.resolve_model_id", lambda value: ("openrouter", "fixture"))
    monkeypatch.setattr("v2.runtime.assembly.build_runtime", build)
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post(
        "/api/v2/chat/stream", json={"q": "record?"})

    events = response.text
    assert '"code":"pre_tool_timeout"' in events
    assert '"stage_latencies_ms":{"understand":12}' in events
    assert "private timeout detail" not in events
    assert events.rstrip().endswith("event: graph_end\ndata: {}")


def test_answer_text_never_leaves_final_sse_blank_after_filtered_gaps():
    from v2 import contracts
    from v2.api.routes import _answer_text
    from v2.runtime.models import ExecutionResult, RuntimeResult

    result = RuntimeResult(
        task=contracts.TaskSpec(goal="record", mode="quick", deliverable="answer"),
        execution=ExecutionResult(plan=contracts.Plan(nodes=[contracts.PlanNode(
            id="facts", description="facts", capability_hints=["standings"],
            status="failed")]), attempts={"facts": 1},
            errors={"facts": ["source unavailable"]}),
        draft=contracts.DraftReport(sections=[], claims=[]),
        verification=contracts.VerificationReport(status="partial"),
        gaps=[contracts.Gap(
            kind="execution_failure", message="execution failed for facts",
            blocks=["node:facts"])],
    )
    answer = _answer_text(result)
    assert answer == "Some supporting data was unavailable."
    assert encode_event(FinalAnswer(text=answer)).startswith("event: final_answer")


def test_answer_text_has_nonempty_fallback_when_all_internal_gaps_are_filtered():
    from v2 import contracts
    from v2.api.routes import _answer_text
    from v2.runtime.models import ExecutionResult, RuntimeResult

    result = RuntimeResult(
        task=contracts.TaskSpec(goal="trade", mode="quick", deliverable="answer"),
        execution=ExecutionResult(plan=contracts.Plan(nodes=[])),
        draft=contracts.DraftReport(sections=[], claims=[]),
        verification=contracts.VerificationReport(status="partial"),
        gaps=[contracts.Gap(
            kind="missing_evidence", message="Verify contract salary")],
    )
    answer = _answer_text(result)
    assert answer == "I could not verify a publishable answer from the available data."
    stream_tail = encode_event(FinalAnswer(text=answer)) + encode_event(GraphEnd())
    assert "event: final_answer" in stream_tail
    assert stream_tail.endswith("event: graph_end\ndata: {}\n\n")

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
                completion_test="row",
            ),
            PlanNode(
                id="two",
                description="second",
                depends_on=["one"],
                capability_hints=["fake"],
                completion_test="row",
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
    first = PlanExecutor(
        {"fake": FakeCapability("fake", lambda node: {"node": node.id})},
        max_failures=1,
        checkpoint_store=checkpoints,
    )
    partial_plan = _plan()
    partial_plan.nodes[1].capability_hints = ["missing"]
    result = await first.execute(_task(), partial_plan, run_id="resume")
    assert result.plan.nodes[0].status == PlanStatus.COMPLETE

    checkpoint = checkpoints.load("resume")
    assert checkpoint is not None
    checkpoint.plan.nodes[1].status = PlanStatus.PENDING
    checkpoint.plan.nodes[1].capability_hints = ["fake"]
    checkpoints.save(checkpoint)
    calls: list[str] = []
    second = PlanExecutor(
        {
            "fake": FakeCapability(
                "fake", lambda node: calls.append(node.id) or {"node": node.id}
            )
        },
        checkpoint_store=checkpoints,
    )
    resumed_plan = _plan()
    resumed = await second.execute(_task(), resumed_plan, run_id="resume")
    assert calls == ["two"]
    assert [node.status for node in resumed.plan.nodes] == [PlanStatus.COMPLETE] * 2
    assert [item.rows for item in resumed.evidence] == [
        {"node": "one"},
        {"node": "two"},
    ]


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
            plan=contracts.Plan(nodes=[]), evidence=[evidence]),
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
            evidence_ids=["ev"])])

    class FakeRuntime:
        async def run(self, request, *, run_id=None):
            return result

    monkeypatch.setattr("v2.runtime.assembly.build_runtime",
                        lambda **kwargs: (FakeRuntime(), RunLedger(kwargs["run_id"])))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post("/api/v2/chat/stream", json={"q": "record?"})

    assert response.status_code == 200
    assert response.headers["x-dime-run-id"].startswith("run-")
    assert "event: custom_data" in response.text
    assert "event: final_answer" in response.text
    assert "Boston won 61 games." in response.text
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
        verification=contracts.VerificationReport(status="partial"),
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

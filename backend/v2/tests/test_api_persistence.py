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

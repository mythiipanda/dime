from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from shared.durability import DIRECTORY_FSYNC_SUPPORTED
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
from v2.api.sse import encode_event
from v2.contracts import Plan, PlanNode, PlanStatus, RunMode, TaskSpec
from v2.projects.service import ProjectStore


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


def test_project_store_handles_independent_workers(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "projects.sqlite3"

    def create(index: int) -> str:
        return ProjectStore(path).create(f"project {index}").id

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(create, range(20)))
    assert len(set(ids)) == 20
    assert len(ProjectStore(path).list()) == 20






def test_project_record_rejects_unknown_persisted_fields() -> None:
    from pydantic import ValidationError
    from v2.projects.models import Project

    with pytest.raises(ValidationError, match="invented"):
        Project.model_validate({
            "id": "p", "goal": "answer", "run_id": "project-p",
            "invented": True,
        })



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


def test_stream_event_rejects_duplicate_string_lists() -> None:
    from pydantic import ValidationError
    from v2.api.events import CustomData, Suggestions

    with pytest.raises(ValidationError, match="must not contain duplicates"):
        Suggestions(items=["Compare players", "Compare players"])
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        CustomData(node="verify", unverified_numbers=["61", "61"])


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



def test_stream_event_text_has_hard_limits() -> None:
    from pydantic import ValidationError
    from v2.api.events import ToolResult
    with pytest.raises(ValidationError, match="at most 4000 characters"):
        ToolResult(node="execute", name="tool", status="fail", error="x" * 4001)

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
        (Token(text="streamed answer 99"), {"text": "streamed answer 99"}),
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
        "private chain of thought", "SELECT private",
        "provider token secret", "private provider summary",
    ):
        assert secret not in combined

def test_v2_sse_failure_event_carries_typed_kind_and_message():
    import json
    from v2.api.events import EVENT_ADAPTER, Failure
    from v2.api.sse import encode_event

    event = EVENT_ADAPTER.validate_python(
        {"type": "failure", "kind": "quota",
         "message": "The model ran out of quota."})
    assert isinstance(event, Failure)
    payload = encode_event(event).split("data: ", 1)[1].strip()
    assert json.loads(payload) == {
        "kind": "quota", "message": "The model ran out of quota."}


def test_frontend_can_select_native_v2_chat_runtime():
    from pathlib import Path

    lib = Path(__file__).resolve().parents[3] / "frontend" / "lib"
    api_source = (lib / "api.ts").read_text()
    assert '"/api/v2/chat/stream"' in api_source
    assert "chatRuntime" not in api_source
    assert not (lib / "runtime.ts").exists()
    assert 'q,' in api_source and 'model,' in api_source
    assert 'thread,' in api_source and 'client: getClientId()' in api_source




def test_public_sse_projection_omits_real_envelope_source_identity():
    from datetime import UTC,datetime
    from v2.contracts import EvidenceEnvelope
    from v2.api.events import CustomData
    from v2.api.sse import encode_event
    from v2.public_evidence import public_evidence_table
    item=EvidenceEnvelope(evidence_id='e',capability='team_ratings',source='fixture',observed_at=datetime.now(UTC),rows=[],source_identity={'kind':'warehouse','warehouse_id':'frozen-eval','sha256':'a'*64})
    payload=encode_event(CustomData(node='analytics',tables=[public_evidence_table(item)]))
    assert 'source_identity' not in payload and 'a'*64 not in payload and 'warehouse_id' not in payload




def _write_expected_manifest(path, manifest):
    import json
    path.write_text(json.dumps(manifest.as_dict()))
    return path

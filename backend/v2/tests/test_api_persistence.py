from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
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
from v2.api.routes import router
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

def test_revision_and_project_endpoints(
    monkeypatch, tmp_path: Path
) -> None:
    from v2.api import routes

    monkeypatch.setattr(routes, "_PROJECTS", ProjectStore(tmp_path / "projects.json"))
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    revision = client.get("/api/revision")
    assert revision.status_code == 200
    assert set(revision.json()) == {"revision", "executable_sha256", "module_sha256", "prompt_sha256", "warehouse", "semantic_baseline", "typed_argument_assets"}
    assert set(revision.json()["warehouse"]) == {"warehouse_id", "sha256", "sha256_derivation"}
    assert revision.json()["warehouse"]["warehouse_id"] in {"frozen-eval", "configured-runtime"}
    assert re.fullmatch(r"[0-9a-f]{64}", revision.json()["warehouse"]["sha256"])
    assert len(revision.json()["executable_sha256"]) == hashlib.sha256().digest_size * 2

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


def test_v2_uses_one_configured_model_policy(monkeypatch):
    monkeypatch.setenv("DIME_V2_MODEL", "openrouter:openrouter/free")
    seen = []
    monkeypatch.setattr("shared.providers.resolve_model_id",
                        lambda value: seen.append(value) or ("openrouter", "openrouter/free"))
    from analyst import configuration, product_session
    monkeypatch.setattr("shared.providers.get_llm", lambda provider, name: (provider, name))
    monkeypatch.setattr(configuration, "model_limits", lambda provider, name: {})
    monkeypatch.setattr(product_session, "resolved_provider", lambda provider, client, **limits: client)
    assert configuration.resolve_product_model() == ("openrouter", "openrouter/free")
    configuration.resolve_product_model("explicit:model")
    assert seen == ["openrouter:openrouter/free", "explicit:model"]


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


def test_project_record_rejects_unknown_persisted_fields() -> None:
    from pydantic import ValidationError
    from v2.projects.models import Project

    with pytest.raises(ValidationError, match="invented"):
        Project.model_validate({
            "id": "p", "goal": "answer", "run_id": "project-p",
            "invented": True,
        })


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


def test_live_route_reports_model_resolution_failure_as_sse(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2.api import routes

    monkeypatch.setattr(
        "shared.providers.resolve_model_id",
        lambda *_: (_ for _ in ()).throw(ValueError("private model detail")),
    )
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post("/api/v2/chat/stream", json={"q": "record?"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: failure" in response.text
    assert '"kind":"configuration"' in response.text
    assert response.text.count("event: graph_end") == 1
    assert "event: final_answer" not in response.text
    assert "private model detail" not in response.text


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
    from shared import store
    from v2.api import routes
    warehouse = tmp_path / "configured.duckdb"
    warehouse.write_bytes(b"startup bytes")
    monkeypatch.setattr(store, "DB_PATH", warehouse)
    routes.runtime_warehouse_identity.cache_clear()
    try:
        first = routes.runtime_warehouse_identity()
        assert first == {"warehouse_id": "configured-runtime",
                         "sha256": hashlib.sha256(b"startup bytes").hexdigest(),
                         "sha256_derivation": store.WAREHOUSE_SHA256_DERIVATION}
        assert set(first) == {"warehouse_id", "sha256", "sha256_derivation"}
        assert str(warehouse) not in repr(first)
        warehouse.write_bytes(b"mutated later")
        assert routes.runtime_warehouse_identity() == first
    finally:
        routes.runtime_warehouse_identity.cache_clear()

def test_real_lifespan_freezes_revision_warehouse_endpoint(monkeypatch, tmp_path):
    from v2.main import app as v2_app
    from shared import store
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
        with TestClient(v2_app) as client:
            expected = {"warehouse_id": "configured-runtime",
                        "sha256": hashlib.sha256(startup).hexdigest(),
                        "sha256_derivation": store.WAREHOUSE_SHA256_DERIVATION}
            first = client.get("/api/revision").json()["warehouse"]
            assert first == expected
            assert re.fullmatch(r"[0-9a-f]{64}", first["sha256"])
            warehouse.write_bytes(b"mutated while process is live")
            assert client.get("/api/revision").json()["warehouse"] == expected

            routes.revision()["warehouse"]["warehouse_id"] = "tampered"
            assert client.get("/api/revision").json()["warehouse"] == expected
    finally:
        routes.runtime_warehouse_identity.cache_clear()


def _write_expected_manifest(path, manifest):
    import json
    path.write_text(json.dumps(manifest.as_dict()))
    return path

def test_runtime_asset_manifest_is_deeply_immutable(monkeypatch):
    from v2.api import routes
    manifest=routes.runtime_asset_manifest()
    with pytest.raises((TypeError,AttributeError)):manifest.revision='x'
    with pytest.raises(TypeError):manifest.prompt_sha256['pi_runtime']='x'
    with pytest.raises(TypeError):manifest.warehouse['sha256']='x'
    with pytest.raises(TypeError):manifest.semantic_baseline['baseline_id']='x'
    with pytest.raises(TypeError):manifest.module_sha256['routes']='x'
    with pytest.raises(TypeError):manifest.typed_argument_assets['capability_manifest']='x'
    copied=manifest.as_dict();copied['prompt_sha256']['pi_runtime']='x'
    copied['typed_argument_assets']['capability_manifest']='x'
    assert manifest.prompt_sha256['pi_runtime']!='x'
    assert manifest.typed_argument_assets['capability_manifest']!='x'

def test_preflight_exact_match_and_each_mismatch(monkeypatch,tmp_path):
    import json
    from v2.api import routes
    observed=routes.runtime_asset_manifest();exact=_write_expected_manifest(tmp_path/'exact.json',observed)
    assert routes.preflight_runtime_assets(exact) is observed
    for field in ('executable_sha256','module_sha256','warehouse','semantic_baseline','prompt_sha256','typed_argument_assets'):
        candidate=observed.as_dict()
        if isinstance(candidate[field],dict):candidate[field][next(iter(candidate[field]))]='wrong'
        else:candidate[field]='wrong'
        path=tmp_path/f'{field}.json';path.write_text(json.dumps(candidate))
        with pytest.raises(RuntimeError,match='substantive mismatch'):routes.preflight_runtime_assets(path)
    revision_only=observed.as_dict();revision_only['revision']='wrong-label-only'
    revision_path=tmp_path/'revision.json';revision_path.write_text(json.dumps(revision_only))
    assert routes.preflight_runtime_assets(revision_path) is observed


def test_loaded_module_hash_detects_old_import_against_new_expected(monkeypatch,tmp_path):
    import json
    from v2.api import routes
    old=routes.runtime_asset_manifest();expected=old.as_dict();expected['module_sha256']['routes']='new-loaded-code-hash'
    path=tmp_path/'new.json';path.write_text(json.dumps(expected))
    with pytest.raises(RuntimeError,match='substantive mismatch'):routes.preflight_runtime_assets(path)


def test_lifespan_fails_before_serving_on_expected_mismatch(monkeypatch,tmp_path):
    import json
    from v2.main import app as v2_app
    from v2.api import routes
    expected=routes.runtime_asset_manifest().as_dict();expected['warehouse']={**expected['warehouse'],'sha256':'wrong'}
    path=tmp_path/'wrong.json';path.write_text(json.dumps(expected));monkeypatch.setenv('DIME_EXPECTED_ASSET_MANIFEST',str(path))
    with pytest.raises(RuntimeError,match='substantive mismatch'):
        with TestClient(v2_app):pass

def test_lifespan_starts_on_revision_only_mismatch(monkeypatch,tmp_path):
    import json
    from v2.main import app as v2_app
    from v2.api import routes
    expected=routes.runtime_asset_manifest().as_dict();expected['revision']='wrong-label-only'
    path=tmp_path/'revision-only.json';path.write_text(json.dumps(expected));monkeypatch.setenv('DIME_EXPECTED_ASSET_MANIFEST',str(path))
    with TestClient(v2_app) as client:
        assert client.get('/api/revision').status_code==200


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


def test_runtime_manifest_pins_accepted_semantic_baseline():
    from v2.api import routes
    assert routes.runtime_asset_manifest().as_dict()["semantic_baseline"] == {
        "baseline_id": "dime-warehouse-2025-26-finals-v1",
        "warehouse_sha256": "4099efbefe5c3ba6e0026b837d95cfd421f6844f75a3516e51d00976bfbbe183",
        "logical_content_id": "81969a2d902583aea99c2d8b1a09673b941c63e649bdf6fb6ce09a8aff591a08",
        "manifest_self_hash": "c8ba316cc4d50c666208874a5d04d9788a312e450781d057b823a63aadb446ac",
    }


def _healthz_client(monkeypatch, tmp_path):
    import duckdb
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from shared import store
    from v2.api import routes
    wh = tmp_path / "healthz.duckdb"
    duckdb.connect(str(wh)).close()
    monkeypatch.setattr(store, "DB_PATH", wh)
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    return TestClient(app), wh

def test_healthz_503_when_ratings_table_missing(monkeypatch, tmp_path):
    import duckdb
    client, wh = _healthz_client(monkeypatch, tmp_path)
    assert "silver_team_ratings" not in {
        r[0] for r in duckdb.connect(str(wh)).execute("SHOW TABLES").fetchall()}
    response = client.get("/api/healthz")
    assert response.status_code == 503
    assert response.json() == {"ok": False, "reason": "ratings_table_missing"}

def test_healthz_503_when_ratings_table_empty(monkeypatch, tmp_path):
    import duckdb
    client, wh = _healthz_client(monkeypatch, tmp_path)
    duckdb.connect(str(wh)).execute(
        "CREATE TABLE silver_team_ratings (_season VARCHAR)")
    response = client.get("/api/healthz")
    assert response.status_code == 503
    assert response.json() == {"ok": False, "reason": "ratings_table_empty"}

def test_healthz_200_when_ratings_present(monkeypatch, tmp_path):
    import duckdb
    client, wh = _healthz_client(monkeypatch, tmp_path)
    duckdb.connect(str(wh)).execute(
        "CREATE TABLE silver_team_ratings (_season VARCHAR)")
    duckdb.connect(str(wh)).execute(
        "INSERT INTO silver_team_ratings VALUES ('2024-25')")
    response = client.get("/api/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}

def test_healthz_503_when_warehouse_unreadable(monkeypatch, tmp_path):
    import duckdb
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from shared import store
    from v2.api import routes
    wh = tmp_path / "healthz.duckdb"
    wh.write_bytes(b"not a database")
    monkeypatch.setattr(store, "DB_PATH", wh)
    try:
        duckdb.connect(str(wh)).execute("SHOW TABLES").fetchall()
        readable = True
    except Exception:
        readable = False
    assert readable is False
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).get("/api/healthz")
    assert response.status_code == 503
    assert response.json() == {"ok": False, "reason": "warehouse_unreachable"}

def test_healthz_503_when_ratings_unreadable(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from shared import store
    from v2.api import routes

    class FailingCount:
        def execute(self, sql, *args):
            if "COUNT(*)" in sql:
                raise RuntimeError("synthetic read failure")
            return self

        def fetchall(self):
            return [("silver_team_ratings",)]

        def fetchone(self):
            raise AssertionError("unreachable")

        def close(self):
            pass

    monkeypatch.setattr(store, "DB_PATH", tmp_path / "healthz.duckdb")
    monkeypatch.setattr(store, "connect", lambda **kwargs: FailingCount())
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).get("/api/healthz")
    assert response.status_code == 503
    assert response.json() == {"ok": False, "reason": "ratings_unreadable"}

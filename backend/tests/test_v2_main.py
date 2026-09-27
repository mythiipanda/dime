"""Standalone v2 entrypoint checks (Step 2 of v1 removal).

v2.main must serve the v2 runtime without any v1 modules: importing it
must not pull backend/app/*, and the app must expose only /api/* v2
routes (no /api/v1/*).
"""

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def test_v2_entrypoint_standalone_imports():
    """Importing v2.main must not load any app.* module (fresh interpreter)."""
    code = (
        "import sys; "
        "import v2.main; "
        "app_mods = [m for m in sys.modules if m == 'app' or m.startswith('app.')]; "
        "assert not app_mods, app_mods"
    )
    subprocess.run([sys.executable, "-c", code], cwd=BACKEND, check=True)


def test_v2_entrypoint_routes():
    """v2.main mounts the v2 router under /api and no /api/v1/* routes."""
    import v2.main

    paths = {r.path for r in v2.main.app.routes if hasattr(r, "path")}
    assert "/api/v2/chat/stream" in paths
    assert "/api/revision" in paths
    assert "/api/projects" in paths
    assert "/api/models" in paths
    assert "/api/health" in paths
    assert "/api/datasets/freshness" in paths
    assert "/api/datasets/{name}" in paths
    assert "/api/threads" in paths
    assert "/api/threads/{thread_id}/runs" in paths
    assert "/api/threads/{thread_id}/export" in paths
    assert "/api/sql/rerun" in paths
    assert "/api/resolve" in paths
    assert "/api/trade/check" in paths
    assert not any(p.startswith("/api/v1") for p in paths), \
        sorted(p for p in paths if p.startswith("/api/v1"))


def _stub_providers(monkeypatch):
    """shared.providers is heavyweight (langchain_*); stub it hermetically."""
    import sys
    import types

    catalog = {
        "available": ["nvidia", "openrouter"],
        "options": [{"id": "nvidia:x", "engine": "nvidia", "default": True}],
    }
    stub = types.ModuleType("shared.providers")
    stub.models_catalog = lambda: dict(catalog)
    monkeypatch.setitem(sys.modules, "shared.providers", stub)
    return catalog


def test_v2_models_returns_catalog_verbatim(monkeypatch):
    """GET /api/models returns models_catalog() verbatim (v1 parity)."""
    _stub_providers(monkeypatch)
    from v2.api.routes import models as models_view

    assert models_view() == {
        "available": ["nvidia", "openrouter"],
        "options": [{"id": "nvidia:x", "engine": "nvidia", "default": True}],
    }


def test_v2_health_ok_shape(monkeypatch):
    """GET /api/health returns {ok: True, providers: catalog['available']} (v1 parity)."""
    catalog = _stub_providers(monkeypatch)
    from v2.api.routes import health as health_view

    assert health_view() == {"ok": True, "providers": catalog["available"]}


def test_v2_chat_stream_has_get_and_post():
    """Chat SSE parity: /api/v2/chat/stream serves both GET and POST (v1 has both)."""
    import v2.main

    methods: set[str] = set()
    for r in v2.main.app.routes:
        if hasattr(r, "path") and r.path == "/api/v2/chat/stream":
            methods |= set(r.methods or set())
    assert methods == {"GET", "POST"}, methods


def test_v2_chat_rate_limit_window():
    """Sliding-window rate limit: exhausts, then recovers as hits age out."""
    import time
    from v2.api import routes
    from shared.config import settings

    ip = "203.0.113.9"
    routes._CHAT_HITS.pop(ip, None)
    for _ in range(settings.chat_rate_per_minute):
        assert routes._chat_allowed(ip) is True
    assert routes._chat_allowed(ip) is False
    routes._CHAT_HITS[ip] = [time.time() - 61]
    assert routes._chat_allowed(ip) is True
    routes._CHAT_HITS.pop(ip, None)


def test_v2_heartbeat_pings_on_idle():
    """with_heartbeat emits ping frames while the inner stream is silent."""
    import asyncio
    from v2.api.sse import with_heartbeat

    async def slow_inner():
        await asyncio.sleep(0.05)
        yield "event: x\ndata: {}\n\n"

    async def collect():
        return [chunk async for chunk in with_heartbeat(
            slow_inner(), interval_s=0.01)]

    chunks = asyncio.run(collect())
    assert chunks, "expected ping frames before the data chunk"
    assert chunks[0].startswith("event: ping\n")
    assert chunks[-1] == "event: x\ndata: {}\n\n"


def test_v2_rate_limited_stream_frames():
    """Rate-limited chat returns v1-parity SSE error + graph_end frames."""
    import asyncio
    from v2.api.routes import _rate_limited_stream

    async def collect(response):
        return [chunk async for chunk in response.body_iterator]

    response = _rate_limited_stream()
    chunks = asyncio.run(collect(response))
    assert chunks[0].startswith("event: error\n")
    assert "rate limited" in chunks[0]
    assert chunks[-1].startswith("event: graph_end\n")

# --- Datasets + threads + sql/rerun (v1-removal Step 3, item 4) ---


def _stub_shared(monkeypatch, store_stub=None, **module_stubs):
    """Replace sys.modules['shared'] (+ named submodules) hermetically.

    Handlers import shared.* at call time, so a stubbed module tree is
    enough to exercise the transport layer without a warehouse or
    provider SDKs.
    """
    import sys
    import types

    shared = types.ModuleType("shared")
    if store_stub is not None:
        shared.store = store_stub
    monkeypatch.setitem(sys.modules, "shared", shared)
    for name, mod in module_stubs.items():
        monkeypatch.setitem(sys.modules, f"shared.{name}", mod)
    return shared


def _stub_store(**fns):
    import types

    return types.SimpleNamespace(**fns)


def test_v2_datasets_freshness_ttl_cache(monkeypatch):
    """Freshness caches per worker: 2 calls within TTL -> 1 payload build."""
    from v2.api import routes

    calls = []

    def fake_payload():
        calls.append(1)
        return {"ok": True, "rows": []}

    monkeypatch.setattr(routes, "_datasets_freshness_payload", fake_payload)
    routes._DATASETS_FRESHNESS_CACHE.update(at=0.0, payload=None)
    try:
        first = routes.datasets_freshness()
        second = routes.datasets_freshness()
        assert first == {"ok": True, "rows": []}
        assert second is first
        assert len(calls) == 1
    finally:
        routes._DATASETS_FRESHNESS_CACHE.update(at=0.0, payload=None)


def test_v2_dataset_unknown_name():
    """Unknown dataset name returns ok False without touching the store."""
    from v2.api.routes import dataset as dataset_view

    out = dataset_view("bogus")
    assert out["ok"] is False
    assert "unknown dataset" in out["error"]
    assert "standings" in out["error"]


def test_v2_dataset_wowy_path(monkeypatch):
    """wowy with player ids routes to the get_wowy tool (v1 parity)."""
    import types

    def fake_invoke(payload):
        assert payload["player_a"] == "LeBron James"
        assert payload["team_id"] == 14
        return {"ok": True, "rows": [{"x": 1}], "verdict": "v", "meta": {"m": 1}}

    player_mod = types.ModuleType("shared.tools.player")
    player_mod.get_wowy = types.SimpleNamespace(invoke=fake_invoke)
    tools_mod = types.ModuleType("shared.tools")
    _stub_shared(monkeypatch, **{"tools": tools_mod, "tools.player": player_mod})

    from v2.api.routes import dataset as dataset_view

    out = dataset_view("wowy", player_a="LeBron James", team_id=14)
    assert out["ok"] is True
    assert out["data"] == [{"x": 1}]
    assert out["verdict"] == "v"


def test_v2_threads_list(monkeypatch):
    """GET /api/threads lists threads from shared.store (v1 parity)."""
    _stub_shared(monkeypatch, store_stub=_stub_store(
        list_threads=lambda owner: [{"thread_id": "t1"}] if owner == "c" else []))

    from v2.api.routes import threads as threads_view

    assert threads_view(client="c") == {"threads": [{"thread_id": "t1"}]}


def test_v2_thread_runs(monkeypatch):
    """GET /api/threads/{id}/runs lists runs from shared.store (v1 parity)."""
    seen = {}

    def fake_list_runs(thread, owner=""):
        seen.update(thread=thread, owner=owner)
        return [{"question": "q"}]

    _stub_shared(monkeypatch, store_stub=_stub_store(list_runs=fake_list_runs))

    from v2.api.routes import thread_runs as runs_view

    assert runs_view("t1", client="c") == {"runs": [{"question": "q"}]}
    assert seen == {"thread": "t1", "owner": "c"}


def test_v2_thread_export(monkeypatch):
    """GET /api/threads/{id}/export renders markdown with evidence (v1 parity)."""
    _stub_shared(monkeypatch, store_stub=_stub_store(
        list_runs=lambda thread, owner="": [
            {"question": "Q?",
             "answer": "A.",
             "tables": [{"tool": "get_leaders",
                         "meta": {"source": "nba", "season": "2025-26",
                                  "fetched_at": "2026-09-27T00:00:00",
                                  "qualification": "MIN >= 500",
                                  "coverage": "full",
                                  "warnings": ["w1"]}}]}
        ]))

    from v2.api.routes import thread_export as export_view

    resp = export_view("t1", client="c")
    body = resp.body.decode()
    assert "# Dime analysis thread t1" in body
    assert "## Q: Q?" in body
    assert "A." in body
    assert "Source table: get_leaders" in body
    assert "source nba" in body and "season 2025-26" in body
    assert "Limit: MIN >= 500" in body
    assert "Limit: w1" in body


def test_v2_sql_rerun_empty_sql():
    """Empty SQL is rejected before any store call (v1 parity)."""
    import asyncio

    from v2.api.routes import sql_rerun, SqlRerunBody

    out = asyncio.run(sql_rerun(SqlRerunBody(sql="   ")))
    assert out == {"ok": False, "error": "sql required", "rows": {}}


def test_v2_sql_rerun_too_long():
    """Oversized SQL is rejected before any store call (v1 parity)."""
    import asyncio

    from v2.api.routes import sql_rerun, SqlRerunBody

    out = asyncio.run(sql_rerun(SqlRerunBody(sql="x" * 8001)))
    assert out == {"ok": False, "error": "sql too long", "rows": {}}


def test_v2_sql_rerun_ok(monkeypatch):
    """rerun_sql success is projected to the v1 row envelope (v1 parity)."""
    import asyncio
    import types

    async def fake_rerun(sql):
        assert sql == "SELECT 1"
        return {"ok": True, "columns": ["a"], "rows": [[1]], "ms": 5, "capped": False}

    league_mod = types.ModuleType("shared.tools.league")
    league_mod.rerun_sql = fake_rerun
    tools_mod = types.ModuleType("shared.tools")
    _stub_shared(monkeypatch, **{"tools": tools_mod, "tools.league": league_mod})

    from v2.api.routes import sql_rerun, SqlRerunBody

    out = asyncio.run(sql_rerun(SqlRerunBody(sql="SELECT 1")))
    assert out == {"ok": True, "rows": {
        "columns": ["a"], "rows": [[1]], "ms": 5, "capped": False}}


# --- v2 chat -> shared thread log (Instinct QA 2026-09-27: no history loss) ---


def test_v2_chat_persists_to_shared_thread_log(monkeypatch, tmp_path):
    """A real v2 chat turn lands in the REAL shared.store thread log.

    Drives quick_answer_stream end-to-end (runtime/result seams stubbed;
    the store is NOT stubbed) and asserts the exchange is visible via the
    v1-parity /api/threads, /runs and /export views.
    """
    import asyncio
    import sys
    import types

    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setenv("DIME_V2_ACTIVITY_DIR", str(tmp_path / "activity"))
    monkeypatch.setenv("DIME_CONVERSATION_STORE",
                       str(tmp_path / "conversations.sqlite3"))

    # Real shared.store, pointed at a throwaway DuckDB.
    import shared.store as real_store
    monkeypatch.setattr(real_store, "STATE_PATH",
                        tmp_path / "state.duckdb")
    monkeypatch.setattr(real_store, "STATE_LOCK_PATH",
                        tmp_path / ".state-write.lock")

    # Hermetic ConversationStore (module-level singleton is env-bound at
    # import time, so swap it for the test).
    from v2.api import routes
    from v2.conversations import ConversationStore
    monkeypatch.setattr(routes, "_CONVERSATIONS",
                        ConversationStore(tmp_path / "conv.sqlite3"))

    # Stub the heavy seams only: provider resolution, runtime assembly,
    # policy, ledger. The answer/evidence projections are module-level
    # helpers, monkeypatched to fixed values.
    providers_mod = types.ModuleType("shared.providers")
    providers_mod.resolve_model_id = lambda model: ("fake", "fake-model")
    monkeypatch.setitem(sys.modules, "shared.providers", providers_mod)

    class _FakePolicy:
        publish = True

        def model_dump(self):
            return {}

    policy_mod = types.ModuleType("v2.runtime.policy")

    class _FakeExecutionPolicy:
        @staticmethod
        def live(**kwargs):
            return _FakePolicy()

        @staticmethod
        def shadow(**kwargs):
            return _FakePolicy()

        @staticmethod
        def model_validate(data):
            return _FakePolicy()

    policy_mod.ExecutionPolicy = _FakeExecutionPolicy
    monkeypatch.setitem(sys.modules, "v2.runtime.policy", policy_mod)

    fake_result = types.SimpleNamespace(
        verification=types.SimpleNamespace(
            status=types.SimpleNamespace(value="pass")),
        verified_claims=[],
        output_statuses=[],
        gaps=[],
    )

    class _FakeRuntime:
        async def run(self, q, run_id=None, context=None):
            assert q == "Who leads the league in TS%?"
            return fake_result

    assembly_mod = types.ModuleType("v2.runtime.assembly")
    assembly_mod.build_runtime = lambda **kwargs: (
        _FakeRuntime(), types.SimpleNamespace(entries=[]))
    monkeypatch.setitem(sys.modules, "v2.runtime.assembly", assembly_mod)

    ledger_mod = types.ModuleType("v2.runtime.ledger")

    class _FakeLedgerKind:
        TOOL_CALL = "tool_call"
        TOOL_RESULT = "tool_result"

    ledger_mod.LedgerKind = _FakeLedgerKind
    monkeypatch.setitem(sys.modules, "v2.runtime.ledger", ledger_mod)

    adapters_mod = types.ModuleType("v2.adapters")
    adapters_mod.CAPABILITIES = set()
    monkeypatch.setitem(sys.modules, "v2.adapters", adapters_mod)

    import shared.config as real_config
    monkeypatch.setattr(real_config, "settings", types.SimpleNamespace(
        dime_v2_pre_tool_timeout_s=5.0))

    answer_text = "The Celtics lead the league in TS%."
    evidence_tables = [{"tool": "get_leaders",
                        "meta": {"source": "nba", "season": "2025-26"}}]
    monkeypatch.setattr(routes, "_answer_text", lambda result: answer_text)
    monkeypatch.setattr(routes, "_public_evidence_tables",
                        lambda result: evidence_tables)

    body = routes.QuickAnswerBody(q="Who leads the league in TS%?",
                                  thread="t-hist", client="c-hist")

    async def drive():
        resp = await routes.quick_answer_stream(body)
        return [chunk async for chunk in resp.body_iterator]

    chunks = asyncio.run(drive())
    assert any("final_answer" in c for c in chunks), chunks

    # The exchange must be visible through the v1-parity thread views,
    # backed by the real shared.store.
    threads_out = routes.threads(client="c-hist")
    thread_ids = [t["id"] for t in threads_out["threads"]]
    assert "t-hist" in thread_ids, threads_out

    runs_out = routes.thread_runs("t-hist", client="c-hist")
    assert runs_out["runs"], runs_out
    run = runs_out["runs"][0]
    assert run["question"] == "Who leads the league in TS%?"
    assert run["answer"] == answer_text
    assert run["tables"] == evidence_tables

    export_resp = routes.thread_export("t-hist", client="c-hist")
    export_body = export_resp.body.decode()
    assert "Who leads the league in TS%?" in export_body
    assert answer_text in export_body

    # Both turns (human + ai) are in the shared chat history.
    history = real_store.chat_history("t-hist")
    assert [m["role"] for m in history] == ["human", "ai"]
    assert history[0]["text"] == "Who leads the league in TS%?"


# --- /resolve + /trade/check (v1-removal step 3) ---


def test_v2_resolve_clamps_query(monkeypatch):
    """GET /api/resolve clamps the query to 80 chars (v1 parity)."""
    import types

    seen = {}

    class FakeTool:
        def invoke(self, payload):
            seen.update(payload)
            return {"ok": True, "entity": "LAL"}

    tools_mod = types.ModuleType("shared.tools")
    tools_mod.resolve_entity = FakeTool()
    _stub_shared(monkeypatch, **{"tools": tools_mod})

    from v2.api.routes import resolve as resolve_view

    assert resolve_view(q="x" * 120) == {"ok": True, "entity": "LAL"}
    assert seen == {"query": "x" * 80}


def test_v2_trade_check_passthrough(monkeypatch):
    """POST /api/trade/check forwards the clamped body verbatim (v1 parity)."""
    import types

    seen = {}

    class FakeTool:
        def invoke(self, payload):
            seen.update(payload)
            return {"ok": True, "legal": True}

    tools_mod = types.ModuleType("shared.tools")
    tools_mod.get_trade_check = FakeTool()
    _stub_shared(monkeypatch, **{"tools": tools_mod})

    from v2.api.routes import trade_check as trade_view, TradeBody

    out = trade_view(TradeBody(
        team_a="LAL", players_a=["LeBron James ", "", "  AD"],
        team_b="BOS", players_b="Tatum", season="2024-25"))
    assert out == {"ok": True, "legal": True}
    assert seen == {
        "team_a": "LAL", "players_a": "LeBron James, AD",
        "team_b": "BOS", "players_b": "Tatum",
        "season": "2024-25",
    }


def test_v2_trade_body_list_normalization():
    """Player lists normalize to comma-joined strings (v1 parity)."""
    from v2.api.routes import TradeBody

    body = TradeBody(players_a=["a", "", " b "], players_b="c")
    assert body.players_a == "a, b"
    assert body.players_b == "c"

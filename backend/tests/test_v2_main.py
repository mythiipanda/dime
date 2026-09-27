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

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

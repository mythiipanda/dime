from __future__ import annotations

import pytest

from shared.config import runtime_v2_mode


@pytest.mark.parametrize("raw", [None, "", "   ", "on", "ON", " on "])
def test_v2_routes_serve_when_the_flag_is_absent_or_blank(monkeypatch, raw):
    if raw is None:
        monkeypatch.delenv("DIME_RUNTIME_V2", raising=False)
    else:
        monkeypatch.setenv("DIME_RUNTIME_V2", raw)
    assert runtime_v2_mode() == "on"


@pytest.mark.parametrize("raw,expected", [
    ("on", "on"),
    ("ON", "on"),
    ("shadow", "shadow"),
    ("Shadow", "shadow"),
    ("off", "off"),
    ("OFF", "off"),
    ("off ", "off"),
])
def test_explicit_mode_values_survive_normalisation(monkeypatch, raw, expected):
    monkeypatch.setenv("DIME_RUNTIME_V2", raw)
    assert runtime_v2_mode() == expected


@pytest.mark.parametrize("raw", ["typo", "1", "true", "ON!"])
def test_unknown_mode_value_still_raises(monkeypatch, raw):
    monkeypatch.setenv("DIME_RUNTIME_V2", raw)
    with pytest.raises(ValueError, match="unknown DIME_RUNTIME_V2 value"):
        runtime_v2_mode()


def test_off_remains_a_reachable_kill_switch(monkeypatch):
    monkeypatch.setenv("DIME_RUNTIME_V2", "off")
    assert runtime_v2_mode() == "off"


def test_shadow_stays_distinct_from_on(monkeypatch):
    monkeypatch.delenv("DIME_RUNTIME_V2", raising=False)
    live = runtime_v2_mode()
    monkeypatch.setenv("DIME_RUNTIME_V2", "shadow")
    shadow = runtime_v2_mode()
    assert live == "on" and shadow == "shadow" and live != shadow


def test_project_routes_are_not_gated_behind_an_unset_flag(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from v2.api import routes
    from v2.projects.service import ProjectStore

    monkeypatch.delenv("DIME_RUNTIME_V2", raising=False)
    monkeypatch.setattr(routes, "_PROJECTS", ProjectStore(tmp_path / "p.sqlite"))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    client = TestClient(app)
    created = client.post("/api/projects", json={"goal": "Celtics outlook"})
    assert created.status_code == 201, created.text
    listed = client.get("/api/projects")
    assert listed.status_code == 200
    assert len(listed.json()["projects"]) == 1


def test_explicit_off_still_returns_404_for_project_routes(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from v2.api import routes
    from v2.projects.service import ProjectStore

    monkeypatch.setenv("DIME_RUNTIME_V2", "off")
    monkeypatch.setattr(routes, "_PROJECTS", ProjectStore(tmp_path / "p.sqlite"))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    assert TestClient(app).post(
        "/api/projects", json={"goal": "x"}).status_code == 404


def test_chat_stream_route_is_not_gated_behind_an_unset_flag(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from v2.api import routes
    from v2.projects.service import ProjectStore
    from v2.runtime.ledger import RunLedger

    monkeypatch.delenv("DIME_RUNTIME_V2", raising=False)
    monkeypatch.setattr(routes, "_PROJECTS", ProjectStore(tmp_path / "p.sqlite"))
    monkeypatch.setattr(
        "shared.providers.resolve_model_id", lambda value: ("openrouter", "fixture"))
    monkeypatch.setattr(
        "v2.runtime.assembly.build_runtime",
        lambda **kwargs: (_StubRuntime(), RunLedger(kwargs["run_id"])))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post("/api/v2/chat/stream", json={"q": "x"})
    assert response.status_code == 200, response.text
    assert "graph_end" in response.text


class _StubRuntime:
    async def run(self, *args, **kwargs):
        raise RuntimeError("stub run aborts before any publication")
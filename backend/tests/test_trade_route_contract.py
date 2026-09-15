from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import router


client = TestClient(FastAPI())
client.app.include_router(router, prefix="/api/v1")


def test_trade_body_accepts_player_arrays(monkeypatch):
    from app import tools

    seen = {}

    class Trade:
        def invoke(self, value):
            seen.update(value)
            return {"ok": True}

    monkeypatch.setattr(tools, "get_trade_check", Trade())
    response = client.post("/api/v1/trade/check", json={
        "team_a": "LAL", "players_a": ["LeBron James", "Austin Reaves"],
        "team_b": "MIA", "players_b": ["Giannis Antetokounmpo"],
    })
    assert response.status_code == 200
    assert seen["players_a"] == "LeBron James, Austin Reaves"
    assert seen["players_b"] == "Giannis Antetokounmpo"


def test_trade_body_rejects_unknown_fields():
    response = client.post("/api/v1/trade/check", json={
        "team_a": "LAL", "players_a": [], "team_b": "MIA",
        "players_b": [], "mystery": "ignored before",
    })
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "extra_forbidden"

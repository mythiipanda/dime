from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import routes


def test_thread_export_preserves_evidence_identity_and_limits(monkeypatch):
    monkeypatch.setattr(routes.store, "list_runs", lambda thread: [{
        "question": "record?",
        "answer": "Boston won 61 games.",
        "tables": [{
            "tool": "standings",
            "meta": {
                "source": "warehouse://standings@rev-7",
                "season": "2025-26",
                "fetched_at": "2026-09-15T10:00:00+00:00",
                "qualification": "Qualified teams only.",
                "coverage": "Regular season.",
                "warnings": ["Source revision is seven days old."],
            },
        }],
    }])
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1")

    response = TestClient(app).get("/api/v1/threads/thread/export")

    assert response.status_code == 200
    assert "Source table: standings" in response.text
    assert "source warehouse://standings@rev-7" in response.text
    assert "season 2025-26" in response.text
    assert "fetched 2026-09-15" in response.text
    assert "Limit: Qualified teams only." in response.text
    assert "Limit: Regular season." in response.text
    assert "Limit: Source revision is seven days old." in response.text

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import routes, store


def test_run_history_and_export_are_scoped_to_browser_owner(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "warehouse.duckdb")
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.save_run(
        "shared-thread", "private question", "private answer", [], [],
        owner="browser-a",
    )
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1")
    client = TestClient(app)

    mine = client.get(
        "/api/v1/threads/shared-thread/runs?client=browser-a").json()["runs"]
    assert mine and mine[0]["answer"] == "private answer"
    assert client.get(
        "/api/v1/threads/shared-thread/runs?client=browser-b").json() == {"runs": []}
    export = client.get(
        "/api/v1/threads/shared-thread/export?client=browser-b")
    assert "private question" not in export.text
    assert "private answer" not in export.text

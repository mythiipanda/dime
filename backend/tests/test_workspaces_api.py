import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workspaces.routes import router as workspaces_router
from workspaces.service import WorkspaceStore


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "workspaces.routes.get_store",
        lambda: WorkspaceStore(tmp_path / "workspaces.sqlite3"),
    )
    app = FastAPI()
    app.include_router(workspaces_router, prefix="/api")
    return TestClient(app)


def test_create_get_round_trip(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = client.post(
        "/api/workspaces", json={"name": "Playoff race", "owner": "tony"})
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Playoff race"
    assert body["owner"] == "tony"
    assert body["member_thread_ids"] == []
    assert body["member_brief_ids"] == []
    fetched = client.get(f"/api/workspaces/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body


def test_membership_add_remove(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    workspace_id = client.post(
        "/api/workspaces", json={"name": "W", "owner": "o"}).json()["id"]
    updated = client.patch(
        f"/api/workspaces/{workspace_id}",
        json={"add_thread_ids": ["t1", "t2"], "add_brief_ids": ["b1"]})
    assert updated.status_code == 200
    assert updated.json()["member_thread_ids"] == ["t1", "t2"]
    assert updated.json()["member_brief_ids"] == ["b1"]
    updated = client.patch(
        f"/api/workspaces/{workspace_id}",
        json={"add_thread_ids": ["t2", "t3"], "remove_thread_ids": ["t1"]})
    assert updated.json()["member_thread_ids"] == ["t2", "t3"]
    fetched = client.get(f"/api/workspaces/{workspace_id}")
    assert fetched.json()["member_thread_ids"] == ["t2", "t3"]
    assert fetched.json()["member_brief_ids"] == ["b1"]


def test_unknown_workspace_is_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    assert client.get("/api/workspaces/does-not-exist").status_code == 404
    assert client.patch(
        "/api/workspaces/does-not-exist",
        json={"add_thread_ids": ["t1"]}).status_code == 404
    assert client.delete("/api/workspaces/does-not-exist").status_code == 404


def test_delete_removes_workspace_not_member_data(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    keep = client.post(
        "/api/workspaces", json={"name": "Keep", "owner": "o"}).json()
    drop = client.post(
        "/api/workspaces", json={"name": "Drop", "owner": "o"}).json()
    client.patch(f"/api/workspaces/{drop['id']}",
                 json={"add_thread_ids": ["shared-thread"]})
    client.patch(f"/api/workspaces/{keep['id']}",
                 json={"add_thread_ids": ["shared-thread"]})
    assert client.delete(f"/api/workspaces/{drop['id']}").status_code == 200
    assert client.get(f"/api/workspaces/{drop['id']}").status_code == 404
    kept = client.get(f"/api/workspaces/{keep['id']}").json()
    assert kept["member_thread_ids"] == ["shared-thread"]


def test_rejects_empty_name_owner_and_blank_members(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    assert client.post(
        "/api/workspaces", json={"name": " ", "owner": "o"}).status_code == 422
    assert client.post(
        "/api/workspaces", json={"name": "W", "owner": ""}).status_code == 422
    workspace_id = client.post(
        "/api/workspaces", json={"name": "W", "owner": "o"}).json()["id"]
    assert client.patch(
        f"/api/workspaces/{workspace_id}",
        json={"add_thread_ids": [" "]}).status_code == 422


def test_no_connection_growth_across_crud_sequence(tmp_path):
    import os
    from workspaces.service import WorkspaceStore

    path = str(tmp_path / "leak.sqlite3")

    def open_handles():
        count = 0
        for fd in os.listdir("/proc/self/fd"):
            try:
                if os.readlink(f"/proc/self/fd/{fd}") == path:
                    count += 1
            except OSError:
                pass
        return count

    store = WorkspaceStore(path)
    baseline = open_handles()
    for index in range(5):
        workspace = store.create(f"w{index}", "o")
        store.update_members(workspace.id, add_thread_ids=["t"])
        store.get(workspace.id)
        store.delete(workspace.id)
    assert open_handles() == baseline

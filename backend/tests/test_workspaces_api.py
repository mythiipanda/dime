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
    assert {k: v for k, v in fetched.json().items()
            if k != "owner_token"} == {
        k: v for k, v in body.items() if k != "owner_token"}


def test_membership_add_remove(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = client.post(
        "/api/workspaces", json={"name": "W", "owner": "o"}).json()
    workspace_id, auth = created["id"], {
        "X-Owner-Token": created["owner_token"]}
    updated = client.patch(
        f"/api/workspaces/{workspace_id}",
        json={"add_thread_ids": ["t1", "t2"], "add_brief_ids": ["b1"]},
        headers=auth)
    assert updated.status_code == 200
    assert updated.json()["member_thread_ids"] == ["t1", "t2"]
    assert updated.json()["member_brief_ids"] == ["b1"]
    updated = client.patch(
        f"/api/workspaces/{workspace_id}",
        json={"add_thread_ids": ["t2", "t3"], "remove_thread_ids": ["t1"]},
        headers=auth)
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
    keep_auth = {"X-Owner-Token": keep["owner_token"]}
    drop_auth = {"X-Owner-Token": drop["owner_token"]}
    client.patch(f"/api/workspaces/{drop['id']}",
                 json={"add_thread_ids": ["shared-thread"]},
                 headers=drop_auth)
    client.patch(f"/api/workspaces/{keep['id']}",
                 json={"add_thread_ids": ["shared-thread"]},
                 headers=keep_auth)
    assert client.delete(
        f"/api/workspaces/{drop['id']}", headers=drop_auth).status_code == 200
    assert client.get(f"/api/workspaces/{drop['id']}").status_code == 404
    kept = client.get(f"/api/workspaces/{keep['id']}").json()
    assert kept["member_thread_ids"] == ["shared-thread"]


def test_rejects_empty_name_owner_and_blank_members(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    assert client.post(
        "/api/workspaces", json={"name": " ", "owner": "o"}).status_code == 422
    assert client.post(
        "/api/workspaces", json={"name": "W", "owner": ""}).status_code == 422
    created = client.post(
        "/api/workspaces", json={"name": "W", "owner": "o"}).json()
    workspace_id, auth = created["id"], {
        "X-Owner-Token": created["owner_token"]}
    assert client.patch(
        f"/api/workspaces/{workspace_id}",
        json={"add_thread_ids": [" "]}, headers=auth).status_code == 422


def test_create_returns_owner_token_distinct_from_id(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    body = client.post(
        "/api/workspaces", json={"name": "W", "owner": "o"}).json()
    assert body["owner_token"]
    assert body["owner_token"] != body["id"]
    assert "owner_token" not in client.get(f"/api/workspaces/{body['id']}").json()


def test_patch_delete_require_owner_token(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = client.post(
        "/api/workspaces", json={"name": "W", "owner": "o"}).json()
    wid, token = created["id"], created["owner_token"]
    assert client.patch(f"/api/workspaces/{wid}",
                        json={"add_thread_ids": ["t"]}).status_code == 401
    assert client.delete(f"/api/workspaces/{wid}").status_code == 401
    assert client.patch(f"/api/workspaces/{wid}", json={"add_thread_ids": ["t"]},
                        headers={"X-Owner-Token": "wrong"}).status_code == 403
    assert client.delete(f"/api/workspaces/{wid}",
                        headers={"X-Owner-Token": "wrong"}).status_code == 403
    assert client.get(f"/api/workspaces/{wid}").json()["member_thread_ids"] == []
    good = {"X-Owner-Token": token}
    assert client.patch(f"/api/workspaces/{wid}", json={"add_thread_ids": ["t"]},
                        headers=good).status_code == 200
    assert client.delete(f"/api/workspaces/{wid}", headers=good).status_code == 200
    assert client.get(f"/api/workspaces/{wid}").status_code == 404

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workspaces.routes import router as workspaces_router
from workspaces.service import WorkspaceStore

PROC_SELF_FD = Path("/proc/self/fd")

requires_fd_enumeration = pytest.mark.skipif(
    not PROC_SELF_FD.is_dir(),
    reason=("open-handle enumeration has no stdlib equivalent off POSIX; "
            "the leak check is only provable where /proc/self/fd exists"),
)


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


@requires_fd_enumeration
def test_no_connection_growth_across_crud_sequence(tmp_path):
    from workspaces.service import WorkspaceStore

    path = str(tmp_path / "leak.sqlite3")

    def open_handles():
        count = 0
        for fd in os.listdir(PROC_SELF_FD):
            try:
                if os.readlink(f"{PROC_SELF_FD}/{fd}") == path:
                    count += 1
            except OSError:
                pass
        return count

    store = WorkspaceStore(path)
    baseline = open_handles()
    for index in range(5):
        workspace, _ = store.create(f"w{index}", "o")
        store.update_members(workspace.id, add_thread_ids=["t"])
        store.get(workspace.id)
        store.delete(workspace.id)
    assert open_handles() == baseline


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


def test_fd_enumeration_assumption_is_single_sourced_across_backend():
    backend = Path(__file__).resolve().parent.parent
    offenders = []
    for path in sorted(backend.rglob("*.py")):
        if path.resolve() == Path(__file__).resolve():
            continue
        if "/proc/self/fd" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(backend)))
    assert offenders == []


def test_leak_check_skips_exactly_when_fd_enumeration_is_unavailable():
    marker = test_no_connection_growth_across_crud_sequence.pytestmark[0]
    assert marker.name == "skipif"
    assert marker.args[0] == (not PROC_SELF_FD.is_dir())
    assert isinstance(marker.kwargs["reason"], str) and marker.kwargs["reason"]

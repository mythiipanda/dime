from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from workspaces.service import WorkspaceStore

router = APIRouter()

_BACKEND = Path(__file__).resolve().parents[1]


def get_store() -> WorkspaceStore:
    return WorkspaceStore(os.environ.get(
        "DIME_WORKSPACE_STORE", str(_BACKEND / "data" / "workspaces.sqlite3")))


class CreateWorkspaceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=256)
    owner: str = Field(min_length=1, max_length=256)


class UpdateWorkspaceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=256)
    add_thread_ids: list[str] | None = Field(default=None, max_length=1024)
    remove_thread_ids: list[str] | None = Field(default=None, max_length=1024)
    add_brief_ids: list[str] | None = Field(default=None, max_length=1024)
    remove_brief_ids: list[str] | None = Field(default=None, max_length=1024)


def _dump(workspace) -> dict:
    body = workspace.model_dump(mode="json")
    body.pop("owner_token_hash", None)
    return body


def _authorize(store: WorkspaceStore, workspace_id: str,
               token: str | None) -> None:
    if token is None:
        raise HTTPException(status_code=401, detail="owner token required")
    try:
        allowed = store.verify_owner(workspace_id, token)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not allowed:
        raise HTTPException(status_code=403, detail="owner token rejected")


@router.post("/workspaces", status_code=201)
def create_workspace(body: CreateWorkspaceBody) -> dict:
    try:
        workspace, token = get_store().create(body.name.strip(), body.owner.strip())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {**_dump(workspace), "owner_token": token}


@router.get("/workspaces/{workspace_id}")
def get_workspace(workspace_id: str) -> dict:
    try:
        workspace = get_store().get(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return _dump(workspace)


@router.patch("/workspaces/{workspace_id}")
def update_workspace(
    workspace_id: str,
    body: UpdateWorkspaceBody,
    x_owner_token: str | None = Header(default=None),
) -> dict:
    store = get_store()
    try:
        found = store.get(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if found is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    _authorize(store, workspace_id, x_owner_token)
    try:
        return _dump(store.update_members(
            workspace_id,
            add_thread_ids=body.add_thread_ids,
            remove_thread_ids=body.remove_thread_ids,
            add_brief_ids=body.add_brief_ids,
            remove_brief_ids=body.remove_brief_ids,
            name=body.name,
        ))
    except KeyError:
        raise HTTPException(status_code=404, detail="workspace not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/workspaces/{workspace_id}")
def delete_workspace(
    workspace_id: str,
    x_owner_token: str | None = Header(default=None),
) -> dict:
    store = get_store()
    try:
        found = store.get(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if found is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    _authorize(store, workspace_id, x_owner_token)
    try:
        store.delete(workspace_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="workspace not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"ok": True, "id": workspace_id}

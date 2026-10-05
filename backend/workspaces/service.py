from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Lock
from uuid import uuid4

from workspaces.models import Workspace, utcnow

_LOCKS_GUARD = Lock()
_LOCKS: dict[Path, Lock] = {}


def _path_lock(path: Path) -> Lock:
    resolved = path.resolve()
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(resolved, Lock())


class WorkspaceStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._reject_symlinked_path()
        self._lock = _path_lock(self._path)

    def create(self, name: str, owner: str) -> Workspace:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("workspace name must be non-empty")
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("workspace owner must be non-empty")
        now = utcnow()
        workspace = Workspace(
            id=uuid4().hex, name=name.strip(), owner=owner.strip(),
            created_at=now, updated_at=now)
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO workspaces (id, data) VALUES (?, ?)",
                (workspace.id, workspace.model_dump_json()),
            )
        return workspace

    def get(self, workspace_id: str) -> Workspace | None:
        self._validate_workspace_id(workspace_id)
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT data FROM workspaces WHERE id = ?", (workspace_id,)
            ).fetchone()
        return Workspace.model_validate_json(row[0]) if row else None

    def update_members(
        self,
        workspace_id: str,
        *,
        add_thread_ids: list[str] | None = None,
        remove_thread_ids: list[str] | None = None,
        add_brief_ids: list[str] | None = None,
        remove_brief_ids: list[str] | None = None,
        name: str | None = None,
    ) -> Workspace:
        self._validate_workspace_id(workspace_id)
        for label, values in (
            ("add_thread_ids", add_thread_ids),
            ("remove_thread_ids", remove_thread_ids),
            ("add_brief_ids", add_brief_ids),
            ("remove_brief_ids", remove_brief_ids),
        ):
            for value in values or []:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"workspace {label} must be non-empty strings")
        if name is not None and (not isinstance(name, str) or not name.strip()):
            raise ValueError("workspace name must be non-empty")
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT data FROM workspaces WHERE id = ?", (workspace_id,)
            ).fetchone()
            if row is None:
                raise KeyError(workspace_id)
            current = Workspace.model_validate_json(row[0])
            threads = [tid for tid in current.member_thread_ids
                       if tid not in set(remove_thread_ids or [])]
            for tid in add_thread_ids or []:
                if tid not in threads:
                    threads.append(tid)
            briefs = [bid for bid in current.member_brief_ids
                      if bid not in set(remove_brief_ids or [])]
            for bid in add_brief_ids or []:
                if bid not in briefs:
                    briefs.append(bid)
            updated = current.model_copy(update={
                "name": name.strip() if name is not None else current.name,
                "member_thread_ids": threads,
                "member_brief_ids": briefs,
                "updated_at": max(utcnow(), current.updated_at),
            })
            connection.execute(
                "UPDATE workspaces SET data = ? WHERE id = ?",
                (updated.model_dump_json(), workspace_id),
            )
        return updated

    def delete(self, workspace_id: str) -> None:
        self._validate_workspace_id(workspace_id)
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT data FROM workspaces WHERE id = ?", (workspace_id,)
            ).fetchone()
            if row is None:
                raise KeyError(workspace_id)
            connection.execute(
                "DELETE FROM workspaces WHERE id = ?", (workspace_id,))

    @staticmethod
    def _validate_workspace_id(workspace_id: str) -> None:
        if not isinstance(workspace_id, str) or not workspace_id.strip():
            raise ValueError("workspace id must be a non-empty string")

    def _reject_symlinked_path(self) -> None:
        if self._path.is_symlink():
            raise ValueError("workspace store cannot be a symlink")
        parent = self._path.parent
        if any(component.is_symlink() for component in (parent, *parent.parents)):
            raise ValueError("workspace store parent cannot be a symlink")
        for suffix in ("-journal", "-wal", "-shm"):
            if self._path.parent.joinpath(self._path.name + suffix).is_symlink():
                raise ValueError("workspace store journal cannot be a symlink")

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._path, timeout=10)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS workspaces (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        return connection

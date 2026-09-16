from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4

from v2.projects.models import Project, ProjectStatus


_LOCKS_GUARD = Lock()
_LOCKS: dict[Path, Lock] = {}


def _path_lock(path: Path) -> Lock:
    resolved = path.resolve()
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(resolved, Lock())


class ProjectStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        if self._path.is_symlink():
            raise ValueError("project store cannot be a symlink")
        self._lock = _path_lock(self._path)

    def create(self, goal: str) -> Project:
        if not isinstance(goal, str):
            raise TypeError("project goal must be a string")
        if not goal.strip():
            raise ValueError("project goal must be non-empty")
        project_id = uuid4().hex
        project = Project(id=project_id, goal=goal, run_id=f"project-{project_id}")
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO projects (id, data) VALUES (?, ?)",
                (project.id, project.model_dump_json()),
            )
        return project

    def get(self, project_id: str) -> Project | None:
        self._validate_project_id(project_id)
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT data FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        return Project.model_validate_json(row[0]) if row else None

    def list(self) -> list[Project]:
        with self._lock, self._connect() as connection:
            rows = connection.execute("SELECT data FROM projects").fetchall()
        return sorted(
            (Project.model_validate_json(row[0]) for row in rows),
            key=lambda item: item.created_at,
            reverse=True,
        )

    def update(self, project_id: str, **changes: object) -> Project:
        self._validate_project_id(project_id)
        if not changes:
            raise ValueError("project update requires changes")
        allowed = {"goal", "status", "result", "error"}
        unknown = sorted(set(changes) - allowed)
        if unknown:
            raise ValueError(f"project update has unknown fields: {unknown}")
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT data FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if row is None:
                raise KeyError(project_id)
            current = Project.model_validate_json(row[0])
            values = current.model_dump()
            values.update(changes)
            next_status = ProjectStatus(values["status"])
            allowed_transitions = {
                ProjectStatus.PENDING: {ProjectStatus.PENDING, ProjectStatus.RUNNING,
                                        ProjectStatus.FAILED},
                ProjectStatus.RUNNING: {ProjectStatus.RUNNING, ProjectStatus.COMPLETE,
                                        ProjectStatus.FAILED},
                ProjectStatus.COMPLETE: {ProjectStatus.COMPLETE},
                ProjectStatus.FAILED: {ProjectStatus.FAILED},
            }
            if next_status not in allowed_transitions[current.status]:
                raise ValueError(
                    f"project status cannot transition from {current.status.value} "
                    f"to {next_status.value}")
            values["updated_at"] = datetime.now(UTC)
            project = Project.model_validate(values)
            connection.execute(
                "UPDATE projects SET data = ? WHERE id = ?",
                (project.model_dump_json(), project_id),
            )
        return project

    @staticmethod
    def _validate_project_id(project_id: str) -> None:
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("project id must be a non-empty string")

    def _connect(self) -> sqlite3.Connection:
        if self._path.is_symlink():
            raise ValueError("project store cannot be a symlink")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._path, timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, data TEXT NOT NULL)"
        )
        return connection


__all__ = ["Project", "ProjectStatus", "ProjectStore"]

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4

from v2.projects.models import Project, ProjectStatus


class ProjectStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = Lock()

    def create(self, goal: str) -> Project:
        project_id = uuid4().hex
        project = Project(id=project_id, goal=goal, run_id=f"project-{project_id}")
        with self._lock:
            projects = self._read()
            projects[project.id] = project
            self._write(projects)
        return project

    def get(self, project_id: str) -> Project | None:
        with self._lock:
            return self._read().get(project_id)

    def list(self) -> list[Project]:
        with self._lock:
            return sorted(
                self._read().values(), key=lambda item: item.created_at, reverse=True
            )

    def update(self, project_id: str, **changes: object) -> Project:
        with self._lock:
            projects = self._read()
            project = projects.get(project_id)
            if project is None:
                raise KeyError(project_id)
            changes["updated_at"] = datetime.now(UTC)
            project = project.model_copy(update=changes)
            projects[project_id] = project
            self._write(projects)
            return project

    def _read(self) -> dict[str, Project]:
        if not self._path.exists():
            return {}
        items = json.loads(self._path.read_text())
        return {item["id"]: Project.model_validate(item) for item in items}

    def _write(self, projects: dict[str, Project]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=self._path.parent, prefix=".projects-")
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(
                    [item.model_dump(mode="json") for item in projects.values()], handle
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


__all__ = ["Project", "ProjectStatus", "ProjectStore"]

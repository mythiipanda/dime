from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from v2.projects.service import ProjectStore

router = APIRouter()
_BACKEND = Path(__file__).resolve().parents[2]
_PROJECTS = ProjectStore(
    os.environ.get("DIME_PROJECT_STORE", str(_BACKEND / "data" / "v2-projects.json"))
)


def _projects_enabled() -> bool:
    return os.environ.get("DIME_RUNTIME_V2", "off").lower() in {"shadow", "on"}


def _require_projects() -> None:
    if not _projects_enabled():
        raise HTTPException(status_code=404, detail="not found")


def _revision() -> str:
    configured = os.environ.get("DIME_REVISION")
    if configured:
        return configured
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_BACKEND.parent,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _executable_sha256() -> str:
    digest = hashlib.sha256()
    for root in (_BACKEND / "app", _BACKEND / "v2"):
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in {".py", ".md"}:
                digest.update(path.relative_to(_BACKEND).as_posix().encode())
                digest.update(b"\0")
                digest.update(path.read_bytes())
                digest.update(b"\0")
    return digest.hexdigest()


@router.get("/revision")
def revision() -> dict[str, str]:
    return {"revision": _revision(), "executable_sha256": _executable_sha256()}


class CreateProjectBody(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)


@router.post("/projects", status_code=201)
def create_project(body: CreateProjectBody) -> dict:
    _require_projects()
    return _PROJECTS.create(body.goal).model_dump(mode="json")


@router.get("/projects")
def list_projects() -> dict:
    _require_projects()
    return {"projects": [item.model_dump(mode="json") for item in _PROJECTS.list()]}


@router.get("/projects/{project_id}")
def get_project(project_id: str) -> dict:
    _require_projects()
    project = _PROJECTS.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project.model_dump(mode="json")

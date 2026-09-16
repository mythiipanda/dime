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
    os.environ.get("DIME_PROJECT_STORE", str(_BACKEND / "data" / "v2-projects.sqlite3"))
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

from v2.contracts import ConversationTurn


class QuickAnswerBody(BaseModel):
    q: str = Field(min_length=1, max_length=2000)
    model: str | None = None
    history: list[ConversationTurn] = Field(default_factory=list, max_length=8)


def _answer_text(result) -> str:
    claims = [item.claim.text for item in result.verified_claims]
    text = "\n\n".join(claims)
    if result.gaps:
        gap_text = " ".join(gap.message for gap in result.gaps)
        text = f"{text}\n\nWhat I could not verify: {gap_text}" if text else gap_text
    return text


@router.post("/v2/chat/stream")
async def quick_answer_stream(body: QuickAnswerBody):
    _require_projects()
    import asyncio
    import uuid

    from fastapi.responses import StreamingResponse
    from app.providers import resolve_model_id
    from v2.api.events import (
        CustomData, FinalAnswer, GraphEnd, NodeUpdate, ToolCall, ToolResult,
    )
    from v2.api.sse import encode_event
    from v2.runtime.assembly import build_runtime
    from v2.runtime.ledger import LedgerKind
    from v2.runtime.policy import ExecutionPolicy

    run_id = f"run-{uuid.uuid4().hex}"
    provider, model_name = resolve_model_id(
        body.model or os.environ.get("DIME_V2_MODEL"))
    queue: asyncio.Queue = asyncio.Queue()

    def progress(node: str, status: str) -> None:
        queue.put_nowait(NodeUpdate(node=node, status=status))

    ledger_dir = os.environ.get(
        "DIME_V2_LEDGER_DIR", str(_BACKEND / "data" / "v2-ledgers"))
    checkpoint_dir = Path(os.environ.get(
        "DIME_V2_CHECKPOINT_DIR", str(_BACKEND / "data" / "v2-checkpoints")))
    policy = (ExecutionPolicy.shadow(ledger_dir=ledger_dir)
              if os.environ.get("DIME_RUNTIME_V2", "off").lower() == "shadow"
              else ExecutionPolicy.live(ledger_dir=ledger_dir))
    policy = policy.model_copy(update={"checkpoint_dir": checkpoint_dir})
    runtime, ledger = build_runtime(
        provider=provider, model_name=model_name, run_id=run_id,
        progress=progress, policy=policy)

    async def generate():
        task = asyncio.create_task(runtime.run(
            body.q, run_id=run_id, context=tuple(body.history)))
        while not task.done() or not queue.empty():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield encode_event(event)
            except TimeoutError:
                continue
        try:
            result = await task
        except Exception:
            yield encode_event(NodeUpdate(
                node="runtime", status="failed"))
            yield encode_event(GraphEnd())
            return
        for entry in ledger.entries:
            if entry.kind == LedgerKind.TOOL_CALL:
                yield encode_event(ToolCall(
                    node=entry.step_id or "execute",
                    name=str(entry.data.get("name", "tool")),
                    args=entry.data.get("args", {})))
            elif entry.kind == LedgerKind.TOOL_RESULT:
                payload = entry.data
                evidence = payload.get("evidence", {})
                rows = evidence.get("rows")
                row_count = len(rows) if isinstance(rows, list) else None
                yield encode_event(ToolResult(
                    node=entry.step_id or "execute",
                    name=str(evidence.get("capability", "tool")),
                    status="ok" if payload.get("status") == "ok" else "fail",
                    rows=row_count,
                    error=payload.get("error")))
        yield encode_event(CustomData(
            node="verify",
            tables=[item.model_dump(mode="json")
                    for item in result.execution.evidence]))
        if policy.publish:
            yield encode_event(FinalAnswer(
                text=_answer_text(result),
                carry={"run_id": run_id,
                       "verification": result.verification.status.value,
                       "verified_claims": len(result.verified_claims),
                       "gaps": [gap.model_dump(mode="json") for gap in result.gaps]}))
        yield encode_event(GraphEnd())

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"X-Dime-Run-Id": run_id})

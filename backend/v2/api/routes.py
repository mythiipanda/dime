from __future__ import annotations

import hashlib
import json
import os
import subprocess
import inspect
import marshal
from pathlib import Path
from functools import lru_cache
from dataclasses import dataclass
from types import MappingProxyType, ModuleType
from typing import Mapping

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from v2.projects.service import ProjectStore
from v2.conversations import ConversationStore

router = APIRouter()
_BACKEND = Path(__file__).resolve().parents[2]
_PROJECTS = ProjectStore(
    os.environ.get("DIME_PROJECT_STORE", str(_BACKEND / "data" / "v2-projects.sqlite3"))
)
_CONVERSATIONS = ConversationStore(os.environ.get(
    "DIME_CONVERSATION_STORE", str(_BACKEND / "data" / "v2-conversations.sqlite3")))


def _imported_module_code_sha256() -> str:
    code = __loader__.get_code(__name__) if __loader__ is not None else None
    if code is None:
        raise RuntimeError("routes module has no loader code identity")
    return hashlib.sha256(marshal.dumps(code)).hexdigest()


_LOADED_MODULE_CODE_SHA256 = _imported_module_code_sha256()


def _projects_enabled() -> bool:
    return os.environ.get("DIME_RUNTIME_V2", "off").lower() == "on"


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
            if path.is_symlink():
                raise ValueError("executable source tree cannot contain symlinks")
            if path.is_file() and path.suffix in {".py", ".md"}:
                digest.update(path.relative_to(_BACKEND).as_posix().encode())
                digest.update(b"\0")
                digest.update(path.read_bytes())
                digest.update(b"\0")
    return digest.hexdigest()


@lru_cache(maxsize=1)
def runtime_warehouse_identity() -> dict[str, str]:
    """Safe identity of the warehouse bound to this server process."""
    from app import store
    identity = store.warehouse_identity()
    return {"warehouse_id": identity["warehouse_id"],
            "sha256": identity["warehouse_sha256"]}


@dataclass(frozen=True)
class RuntimeAssetManifest:
    revision: str
    executable_sha256: str
    module_sha256: Mapping[str, str]
    warehouse: Mapping[str, str]
    prompt_sha256: Mapping[str, str]

    def as_dict(self) -> dict[str, object]:
        return {
            "revision": self.revision,
            "executable_sha256": self.executable_sha256,
            "module_sha256": dict(self.module_sha256),
            "warehouse": dict(self.warehouse),
            "prompt_sha256": dict(self.prompt_sha256),
        }


def _loaded_behavior_sha256(module: ModuleType, config: Mapping[str, object]) -> str:
    """Bind import-time module code plus canonical runtime configuration."""
    code_hash = getattr(module, "_LOADED_MODULE_CODE_SHA256", None)
    if not isinstance(code_hash, str) or len(code_hash) != 64:
        raise RuntimeError("module lacks import-time code identity")
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(code_hash.encode() + b"\0" + encoded).hexdigest()


@lru_cache(maxsize=1)
def runtime_asset_manifest() -> RuntimeAssetManifest:
    """Deeply immutable identity of code, data, and prompts bound at startup."""
    from v2.adapters import models
    prompts = models.bind_provider_route_prompts()
    expected_routes = set(models._PROVIDER_ROUTE_PROMPT_NAMES)
    if set(prompts) != expected_routes or expected_routes != {
            "intake", "requirement_review", "planner", "synthesizer",
            "repair", "semantic_verifier"}:
        raise RuntimeError("provider prompt registry is incomplete or has extra routes")
    for module in (__import__(__name__, fromlist=["x"]), models):
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(_BACKEND):
            raise RuntimeError("runtime module resolved outside the backend root")
    return RuntimeAssetManifest(
        revision=_revision(), executable_sha256=_executable_sha256(),
        module_sha256=MappingProxyType({
            "routes": _loaded_behavior_sha256(
                __import__(__name__, fromlist=["x"]),
                {"provider_routes": sorted(models._PROVIDER_ROUTE_PROMPT_NAMES)}),
            "models": _loaded_behavior_sha256(
                models, {"provider_route_prompt_names":
                         models._PROVIDER_ROUTE_PROMPT_NAMES}),
        }),
        warehouse=MappingProxyType(dict(runtime_warehouse_identity())),
        prompt_sha256=MappingProxyType({
            route: hashlib.sha256(prompt.encode()).hexdigest()
            for route, prompt in prompts.items()
        }),
    )


def preflight_runtime_assets(expected_path: str | Path | None = None) -> RuntimeAssetManifest:
    """Fail startup unless one promotion-generated expected manifest matches."""
    configured = expected_path or os.environ.get("DIME_EXPECTED_ASSET_MANIFEST")
    if not configured:
        raise RuntimeError("DIME_EXPECTED_ASSET_MANIFEST is required")
    manifest_path = Path(configured).resolve()
    executable_roots = ((_BACKEND / "app").resolve(), (_BACKEND / "v2").resolve())
    if any(manifest_path.is_relative_to(root) for root in executable_roots):
        raise RuntimeError("expected asset manifest must be external to executable roots")
    expected = json.loads(manifest_path.read_text())
    required = {"revision", "executable_sha256", "module_sha256",
                "warehouse", "prompt_sha256"}
    if set(expected) != required:
        raise RuntimeError("expected asset manifest has wrong fields")
    observed = runtime_asset_manifest()
    if expected != observed.as_dict():
        raise RuntimeError("startup asset manifest does not match expected pins")
    return observed


@router.get("/revision")
def revision() -> dict:
    # Round-trip gives callers a copy while preserving startup-bound identity.
    return runtime_asset_manifest().as_dict()


def public_evidence_table(item):
    """Bounded public projection; internal provenance never crosses SSE."""
    return {"tool": item.capability, "rows": item.rows, "meta": {
        "source": item.source,
        "source_as_of": item.as_of.isoformat() if item.as_of else None,
        "observed_at": item.observed_at.isoformat(), "season": item.season,
        "as_of": item.as_of.isoformat() if item.as_of else None,
        "qualification": item.qualification, "coverage": item.coverage,
        "warnings": item.warnings,
    }}


class CreateProjectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1, max_length=2000)

    @field_validator("goal")
    @classmethod
    def reject_blank_goal(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("project goal must be non-empty")
        return value


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
    model_config = ConfigDict(extra="forbid")

    q: str = Field(min_length=1, max_length=2000)
    model: str | None = Field(default=None, max_length=256)
    history: list[ConversationTurn] = Field(default_factory=list, max_length=8)
    thread: str | None = Field(default=None, min_length=1, max_length=80)
    client: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("q")
    @classmethod
    def reject_blank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must be non-empty")
        return value

    @field_validator("model")
    @classmethod
    def reject_blank_model(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("model must be non-empty when present")
        return value

    @field_validator("thread", "client")
    @classmethod
    def reject_blank_identity(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("thread and client must be non-empty when present")
        return value

    @model_validator(mode="after")
    def require_complete_conversation_identity(self):
        if (self.thread is None) != (self.client is None):
            raise ValueError("thread and client must be provided together")
        return self


def _answer_text(result) -> str:
    claims = list(dict.fromkeys(
        item.claim.text for item in result.verified_claims if item.claim.text.strip()))
    text = "\n\n".join(claims)
    gaps: list[str] = []
    gap_keys: set[str] = set()
    generic_limit = False
    plan = getattr(result.execution, "plan", None)
    capability_names = {
        node.capability_hints[0].casefold()
        for node in (plan.nodes if plan is not None else [])
        if len(node.capability_hints) == 1
    }
    for gap in result.gaps:
        message = gap.message.strip()
        folded = message.casefold()
        internal = (
            folded.startswith(("repair claim ", "include ", "update ",
                               "retrieve ", "fetch ", "gather ", "synthesize ",
                               "add ", "document ", "locate ", "verify "))
            or "once gaps are resolved" in folded
            or " capability" in folded
            or folded.endswith(" analysis")
            or folded.startswith("official ")
            or any(name.replace("_", " ") in folded or name in folded
                   for name in capability_names)
            or any(token in folded for token in (
                "source identity", "identify or query a tool",
                "ensure contract evidence", "qualification evidence",
                "coverage evidence", "recomputable", "team-code mismatch",
                "replacement-analysis", "impact & role", "contract terms",
                "peer comparison", "trade value estimate",
            ))
        )
        if internal:
            continue
        if folded in {"player age risk assessment", "age risk assessment"}:
            message = "Age-related risk was not available in the retrieved player data."
        if gap.kind.value == "synthesis_incomplete":
            continue
        if gap.kind.value == "unsupported_claim":
            generic_limit = True
            continue
        if gap.kind.value == "source_conflict":
            message = "The available sources conflict on part of this answer."
        elif gap.kind.value == "execution_failure" or "execution failed" in folded:
            generic_limit = True
            continue
        elif "returned no evidence values" in folded:
            generic_limit = True
            continue
        synonyms = {
            "outcome": "results", "outcomes": "results", "result": "results",
            "playoff": "playoffs",
        }
        key = " ".join(
            synonyms.get(word.strip(".,:;"), word.strip(".,:;"))
            for word in message.casefold().split()
            if word.strip(".,:;") not in {"the", "a", "an"}
        )
        key_tokens = set(key.split())
        duplicate = any(
            key_tokens <= set(existing.split()) or set(existing.split()) <= key_tokens
            for existing in gap_keys
        )
        if message and not duplicate:
            gaps.append(message)
            gap_keys.add(key)
    if not gaps and generic_limit:
        gaps.append("Some supporting data was unavailable.")
    if gaps:
        gap_text = " ".join(gaps)
        text = f"{text}\n\nWhat I could not verify: {gap_text}" if text else gap_text
    # FinalAnswer rejects blank text. A repaired run can legitimately finish
    # with no publishable claim while every internal gap is filtered as a
    # diagnostic. Returning a non-empty public limitation keeps the SSE
    # lifecycle intact through final_answer and graph_end instead of raising
    # after custom_data has already reached the client.
    return text or "I could not verify a publishable answer from the available data."


@router.post("/v2/chat/stream")
async def quick_answer_stream(body: QuickAnswerBody):
    _require_projects()
    import asyncio
    import uuid

    from fastapi.responses import StreamingResponse
    from app.providers import resolve_model_id
    from app.config import settings
    from v2.api.events import (
        CustomData, FinalAnswer, GraphEnd, NodeUpdate, ToolCall, ToolResult,
    )
    from v2.api.activity import ActivityJournal
    from v2.api.events import EVENT_ADAPTER
    from v2.api.sse import encode_event
    from v2.runtime.assembly import build_runtime
    from v2.adapters import CAPABILITIES
    from v2.runtime.ledger import LedgerKind
    from v2.runtime.policy import ExecutionPolicy

    run_id = f"run-{uuid.uuid4().hex}"
    queue: asyncio.Queue = asyncio.Queue()
    activity_dir = Path(os.environ.get("DIME_V2_ACTIVITY_DIR", str(_BACKEND / "data" / "v2-activity")))
    try:
        activity_journal = ActivityJournal(activity_dir / f"{run_id}.jsonl", run_id)
    except Exception:
        activity_journal = None

    def activity(payload: dict) -> None:
        if not policy.publish or activity_journal is None:
            return
        internal = payload.pop("correlation_id", None)
        internal_keys = getattr(activity, "internal_keys", set())
        correlation_map = getattr(activity, "correlation_map", {})
        if internal not in correlation_map:
            correlation_map[internal] = f"activity-{len(correlation_map) + 1}"
            activity.correlation_map = correlation_map
        payload["correlation_id"] = correlation_map[internal]
        event = activity_journal.append(**payload)
        common = event.model_dump(mode="json", exclude={"kind"})
        if event.kind == "tool_call":
            queue.put_nowait(ToolCall(type="tool_call", node="tools", name=event.data.name, label=event.title, **common))
        elif event.kind == "tool_result":
            queue.put_nowait(ToolResult(type="tool_result", node="tools", name=event.data.name, status="ok" if event.transition == "succeeded" else "fail", rows=event.data.rows, ms=event.duration_ms, error=("Tool failed" if event.transition == "failed" else None), **{k:v for k,v in common.items() if k not in {"status","duration_ms"}}))
        else:
            queue.put_nowait(EVENT_ADAPTER.validate_python({"type":event.kind, **common}))
        internal_keys.add((event.kind, internal))
        activity.internal_keys = internal_keys

    def setup_error_stream():
        async def generate_error():
            yield "event: error\ndata: " + json.dumps({
                "message": "Dime could not start this run.",
                "run_id": run_id,
            }, separators=(",", ":")) + "\n\n"
            yield "event: graph_end\ndata: {}\n\n"
        return StreamingResponse(
            generate_error(), media_type="text/event-stream",
            headers={"X-Dime-Run-Id": run_id}, status_code=200,
        )

    try:
        provider, model_name = resolve_model_id(
            body.model or os.environ.get("DIME_V2_MODEL"))
    except Exception:
        return setup_error_stream()

    def public_node(node: str) -> str:
        return {
            "understand": "entry",
            "plan": "data_retrieval",
            "execute": "tools",
            "synthesize": "analytics",
            "verify": "analytics",
            "repair": "analytics",
            "reverify": "analytics",
            "runtime": "presentation",
        }.get(node.split(":", 1)[0], "analytics")

    def progress(node: str, status: str) -> None:
        if not policy.publish:
            return
        public_status = "error" if status == "failed" else status
        queue.put_nowait(NodeUpdate(
            node=public_node(node), status=public_status))

    ledger_dir = os.environ.get(
        "DIME_V2_LEDGER_DIR", str(_BACKEND / "data" / "v2-ledgers"))
    checkpoint_dir = Path(os.environ.get(
        "DIME_V2_CHECKPOINT_DIR", str(_BACKEND / "data" / "v2-checkpoints")))
    runtime_mode = os.environ.get("DIME_RUNTIME_V2", "off").lower()
    if runtime_mode == "shadow":
        policy = ExecutionPolicy.shadow(ledger_dir=ledger_dir)
    elif runtime_mode == "on":
        policy = ExecutionPolicy.live(ledger_dir=ledger_dir)
    else:
        raise HTTPException(status_code=404, detail="not found")
    policy = ExecutionPolicy.model_validate({
        **policy.model_dump(), "checkpoint_dir": checkpoint_dir,
    })
    try:
        runtime, ledger = build_runtime(
            provider=provider, model_name=model_name, run_id=run_id,
            progress=progress, activity=activity, policy=policy,
            pre_tool_timeout_s=settings.dime_v2_pre_tool_timeout_s)
    except Exception:
        return setup_error_stream()
    context = tuple(body.history)
    if body.thread is not None and body.client is not None:
        context = tuple(_CONVERSATIONS.read(body.client, body.thread))

    def missing_tool_events():
        """Yield sanitized undelivered ledger tool events in ledger order."""
        try:
            entries = ledger.entries
            live_keys = getattr(activity, "internal_keys", set())
            calls = {entry.call_id: entry for entry in entries
                     if entry.kind == LedgerKind.TOOL_CALL and entry.call_id is not None}
            executable = set(CAPABILITIES) | {"web_search", "web_fetch"}
            for entry in entries:
                if entry.kind not in {LedgerKind.TOOL_CALL, LedgerKind.TOOL_RESULT}:
                    continue
                kind = "tool_call" if entry.kind == LedgerKind.TOOL_CALL else "tool_result"
                if (kind, entry.call_id) in live_keys:
                    continue
                call = entry if entry.kind == LedgerKind.TOOL_CALL else calls.get(entry.call_id)
                raw_name = call.data.get("name") if call is not None else None
                name = str(raw_name) if raw_name in executable else "tool"
                if entry.kind == LedgerKind.TOOL_CALL:
                    yield ToolCall(node="tools", name=name)
                else:
                    payload = entry.data; evidence = payload.get("evidence", {}); rows = evidence.get("rows")
                    yield ToolResult(node="tools", name=name,
                        status="ok" if payload.get("status") == "ok" else "fail",
                        rows=len(rows) if isinstance(rows, list) else None,
                        ms=payload.get("duration_ms"), error=("Tool failed" if payload.get("status") == "failed" else None))
        except Exception:
            return

    def stage_latencies_ms():
        return {
            entry.step_id: entry.data["duration_ms"]
            for entry in ledger.entries
            if entry.kind == LedgerKind.STEP_END
            and entry.step_id is not None
            and isinstance(entry.data.get("duration_ms"), int)
        }

    async def generate():
        task = asyncio.create_task(runtime.run(
            body.q, run_id=run_id, context=context))
        try:
            while not task.done() or not queue.empty():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.1)
                    yield encode_event(event)
                except TimeoutError:
                    continue
            try:
                result = await task
            except Exception as exc:
                if policy.publish:
                    for event in missing_tool_events():
                        try:
                            yield encode_event(event)
                        except Exception:
                            continue
                    latencies = stage_latencies_ms()
                    failed_stage = next((
                        entry.step_id for entry in reversed(ledger.entries)
                        if entry.kind == LedgerKind.STEP_END
                        and entry.data.get("reason") in {"failed", "timeout"}), None)
                    # No TaskSpec/evidence exists when intake's structured
                    # provider is unavailable. Return a typed non-factual
                    # refusal rather than an error event; downstream stages
                    # retain A3's evidence-preserving partial behavior.
                    if (failed_stage == "understand"
                            and type(exc).__name__ != "PreToolTimeoutError"):
                        yield encode_event(NodeUpdate(
                            node=public_node("runtime"), status="complete"))
                        yield encode_event(FinalAnswer(
                            text=("I could not interpret this request reliably "
                                  "because the analysis provider was unavailable. "
                                  "No factual answer was published."),
                            carry={"run_id": run_id, "verification": "partial",
                                   "verified_claims": 0, "structural_flags": [],
                                   "gaps": [{"kind": "execution_failure",
                                              "message": "Request interpretation provider unavailable",
                                              "evidence_ids": [], "blocks": []}],
                                   "stage_latencies_ms": latencies}))
                    else:
                        yield encode_event(NodeUpdate(
                            node=public_node("runtime"), status="error"))
                        yield "event: error\ndata: " + json.dumps({
                            "message": "Dime could not complete this run.",
                            "run_id": run_id,
                            "code": ("pre_tool_timeout"
                                     if type(exc).__name__ == "PreToolTimeoutError"
                                     else "runtime_failure"),
                            "stage_latencies_ms": latencies,
                        }, separators=(",", ":")) + "\n\n"
                yield encode_event(GraphEnd())
                return
            if policy.publish:
                for event in missing_tool_events():
                    try:
                        yield encode_event(event)
                    except Exception:
                        continue
                yield encode_event(CustomData(
                    node="analytics",
                    tables=[public_evidence_table(item)
                            for item in result.execution.evidence]))
                answer = _answer_text(result)
                carry = {
                    "run_id": run_id,
                    "verification": result.verification.status.value,
                    "verified_claims": len(result.verified_claims),
                    "structural_flags": list(getattr(result, "structural_flags", [])),
                    "gaps": [gap.model_dump(mode="json") for gap in result.gaps],
                    "stage_latencies_ms": stage_latencies_ms(),
                }
                yield encode_event(FinalAnswer(text=answer, carry=carry))
                if body.thread is not None and body.client is not None:
                    _CONVERSATIONS.append_exchange(
                        body.client, body.thread, body.q, answer)
            yield encode_event(GraphEnd())
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"X-Dime-Run-Id": run_id})

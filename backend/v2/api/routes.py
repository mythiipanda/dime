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
            "intake", "intake_admission", "requirement_review", "planner", "synthesizer",
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


def _output_line(result, status) -> str:
    binding = status.binding
    identity = (f"{status.requirement_kind}:{status.requirement_id or 'task'}:"
                f"{status.output_id}")
    if binding.requirement_kind == "calculation":
        calculation = next(item for item in result.draft.calculations
                           if item.calculation_id == binding.calculation_id)
        value = str(calculation.result)
        unit = calculation.unit or "unitless"
        subject = ""
    else:
        raw = binding.value
        value = ("true" if raw.value else "false") if raw.kind == "boolean" else str(raw.value)
        unit = (binding.unit.value if binding.unit.kind == "declared" else "unitless")
        subject = (f" [{binding.subject_entity_type}:{binding.subject_entity_id}]"
                   if binding.subject_entity_id is not None else "")
    return f"{identity}{subject} = {value} ({unit})"


def _answer_text(result) -> str:
    """Project only deterministically admitted output authority."""
    lines = [_output_line(result, item) for item in result.output_statuses
             if item.status == "complete"]
    for item in result.output_statuses:
        if item.status != "complete":
            identity = (f"{item.requirement_kind}:{item.requirement_id or 'task'}:"
                        f"{item.output_id}")
            lines.append(f"{identity} could not be verified ({item.status}).")
    gap_messages = {
        "missing_evidence": "Some requested outputs could not be verified.",
        "source_conflict": "Available sources conflict for some requested outputs.",
        "unsupported_claim": "Some requested outputs were not supported.",
        "execution_failure": "Some requested data was unavailable.",
        "synthesis_incomplete": "Some requested outputs could not be published.",
    }
    kinds = []
    for gap in result.gaps:
        if gap.kind.value not in kinds:
            kinds.append(gap.kind.value)
    for kind in kinds:
        lines.append(gap_messages[kind])
    return "\n".join(lines) or "I could not verify a publishable answer from the available data."


def _public_output_status(result, status) -> dict:
    item = {"requirement_kind": status.requirement_kind,
            "requirement_id": status.requirement_id,
            "output_id": status.output_id, "status": status.status}
    if status.status == "complete":
        binding = status.binding
        if binding.requirement_kind == "calculation":
            calculation = next(x for x in result.draft.calculations
                               if x.calculation_id == binding.calculation_id)
            item.update(value=str(calculation.result),
                        unit=calculation.unit or "unitless")
        else:
            item.update(value=("true" if binding.value.kind == "boolean" and binding.value.value
                               else "false" if binding.value.kind == "boolean"
                               else str(binding.value.value)),
                        unit=(binding.unit.value if binding.unit.kind == "declared"
                              else "unitless"),
                        subject_type=binding.subject_entity_type,
                        subject_id=binding.subject_entity_id)
    return item


def _public_evidence_tables(result) -> list[dict]:
    from v2.domain.evidence import iter_values
    from v2.domain.calculations import Calculation, validate_calculation
    from v2.domain.evidence import EvidenceIndex
    evidence = {item.evidence_id:item for item in result.execution.evidence}
    calculations = {item.calculation_id:item for item in result.draft.calculations}
    tables = []
    for status in result.output_statuses:
        if status.status != "complete":
            continue
        binding = status.binding
        if hasattr(binding, "evidence_id"):
            envelope = evidence.get(binding.evidence_id)
            if envelope is None:
                raise ValueError("publication evidence is missing")
            values=[v.value for v in iter_values(envelope) if v.path==binding.selector]
            if len(values)!=1:
                raise ValueError("publication selector must resolve exactly once")
            selected=values[0]; declared=binding.value
            if declared.kind=="boolean": equal=isinstance(selected,bool) and selected is declared.value
            elif declared.kind=="integer": equal=not isinstance(selected,bool) and isinstance(selected,int) and selected==declared.value
            elif declared.kind=="float": equal=isinstance(selected,float) and selected==declared.value
            elif declared.kind=="decimal":
                from decimal import Decimal
                equal=isinstance(selected,Decimal) and selected==Decimal(declared.value)
            else: equal=isinstance(selected,str) and selected==declared.value
            if not equal:
                raise ValueError("publication evidence changed after admission")
            tables.append({"output_id":binding.output_id,
                "subject_type":binding.subject_entity_type,
                "subject_id":binding.subject_entity_id,
                "value":str(binding.value.value),
                "unit":binding.unit.value if binding.unit.kind=="declared" else "unitless",
                "provenance":{"capability":envelope.capability,
                              "season":envelope.season,
                              "as_of":envelope.as_of.isoformat() if envelope.as_of else None}})
        else:
            calculation=calculations.get(binding.calculation_id)
            if calculation is None:
                raise ValueError("publication calculation is missing")
            checked=Calculation.model_validate({"calculation_id":calculation.calculation_id,
                "operation":calculation.operation,"inputs":[x.model_dump() for x in calculation.inputs],
                "result":calculation.result,"unit":calculation.unit,"subject_input":calculation.subject_input})
            if validate_calculation(checked,EvidenceIndex(evidence.values())) is not None:
                raise ValueError("publication calculation no longer recomputes")
            for input_ in calculation.inputs:
                envelope=evidence.get(input_.evidence_id)
                values=[v.value for v in iter_values(envelope)] if envelope else []
                selected=[v.value for v in iter_values(envelope) if v.path==input_.path] if envelope else []
                if len(selected)!=1:
                    raise ValueError("publication calculation input must resolve exactly once")
                tables.append({"output_id":binding.output_id,
                    "input_value":str(selected[0]),
                    "provenance":{"capability":envelope.capability,
                                  "season":envelope.season,
                                  "as_of":envelope.as_of.isoformat() if envelope.as_of else None}})
    return tables


def _safe_buffered_event(event):
    """Closed public-event projection for buffered runtime lifecycle."""
    from v2.api.events import NodeUpdate, ToolCall, ToolResult
    kind = str(getattr(event, "type", ""))
    public_nodes = {"entry", "data_retrieval", "tools", "analytics", "presentation"}
    if kind == "node_update":
        if event.node not in public_nodes or event.status not in {"running","complete","error"}:
            return None
        return NodeUpdate(node=event.node, status=event.status)
    if kind == "tool_call":
        return ToolCall(node="tools", name="tool")
    if kind == "tool_result":
        status = getattr(event, "status", None)
        if status not in {"ok", "fail"}:
            return None
        return ToolResult(node="tools", name="tool", status=status,
                          error="Tool failed" if status == "fail" else None)
    status = getattr(event, "status", None)
    phase = getattr(event, "phase", None)
    phase_nodes = {"understand":"entry","plan":"data_retrieval",
                   "execute":"tools","verify":"analytics"}
    if phase in phase_nodes and status in {"running", "complete", "failed"}:
        return NodeUpdate(node=phase_nodes[phase],
            status="error" if status == "failed" else status)
    return None


@router.post("/v2/chat/stream")
async def quick_answer_stream(body: QuickAnswerBody):
    _require_projects()
    import asyncio
    import uuid

    from fastapi.responses import StreamingResponse
    from app.providers import resolve_model_id
    from app.config import settings
    from v2.api.events import (
        CustomData, FinalAnswer, GraphEnd, NodeUpdate, ToolCall, ToolResult, WorkLog,
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
            buffered_events = []
            try:
                while not task.done() or not queue.empty():
                    try:
                        buffered_events.append(
                            await asyncio.wait_for(queue.get(), timeout=0.1))
                    except TimeoutError:
                        continue
                result = await task
                while not queue.empty():
                    buffered_events.append(queue.get_nowait())
                # Validate every public projection before emitting buffered SSE.
                public_tables = _public_evidence_tables(result)
                public_statuses = [_public_output_status(result, item)
                                   for item in result.output_statuses]
                answer = _answer_text(result)
            except Exception as exc:
                if policy.publish:
                    for event in missing_tool_events():
                        safe_event = _safe_buffered_event(event)
                        if safe_event is not None:
                            yield encode_event(safe_event)
                    yield encode_event(WorkLog(run_id=run_id, status="partial"))
                    yield encode_event(FinalAnswer(
                        text="I could not verify a publishable answer from the available data.",
                        carry={"run_id": run_id, "verification": "partial",
                               "verified_claims": 0, "structural_flags": [],
                               "gaps": [{"kind": "execution_failure"}],
                               "stage_latencies_ms": stage_latencies_ms()}))
                yield encode_event(GraphEnd())
                return
            if policy.publish:
                for event in buffered_events:
                    safe_event = _safe_buffered_event(event)
                    if safe_event is not None:
                        yield encode_event(safe_event)
                for event in missing_tool_events():
                    try:
                        safe_event = _safe_buffered_event(event)
                        if safe_event is not None:
                            yield encode_event(safe_event)
                    except Exception:
                        continue
                yield encode_event(WorkLog(
                    run_id=run_id,
                    status="complete" if result.verification.status.value == "pass" else "partial"))
                yield encode_event(CustomData(
                    node="analytics",
                    tables=public_tables))
                carry = {
                    "run_id": run_id,
                    "verification": result.verification.status.value,
                    "verified_claims": len(result.verified_claims),
                    "output_statuses": public_statuses,
                    "structural_flags": list(getattr(result, "structural_flags", [])),
                    "gaps": [{"kind": gap.kind.value} for gap in result.gaps],
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

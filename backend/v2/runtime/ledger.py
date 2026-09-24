from __future__ import annotations

import hashlib
import json
import re
import os
import math
import fcntl
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Any, Iterable

_LEDGER_LOCKS_GUARD = Lock()
_LEDGER_LOCKS: dict[Path, Lock] = {}


def _ledger_path_lock(path: Path) -> Lock:
    resolved = path.resolve()
    with _LEDGER_LOCKS_GUARD:
        return _LEDGER_LOCKS.setdefault(resolved, Lock())

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, model_validator


class LedgerKind(StrEnum):
    TURN_START = "turn/start"
    STEP_START = "step/start"
    MODEL_REQUEST = "model/request"
    TOOL_CALL = "tool/call"
    TOOL_RESULT = "tool/result"
    ASSISTANT_ATTEMPT = "assistant/attempt"
    STEP_END = "step/end"
    TURN_END = "turn/end"


class TerminalReason(StrEnum):
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


def exception_text(exc: BaseException, *, max_length: int = 4000) -> str:
    prefix = f"{type(exc).__name__}: "
    detail = str(exc)
    return prefix + detail[:max(0, max_length - len(prefix))]


class RequestEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str = Field(max_length=256)
    model: str = Field(max_length=256)
    route: str = Field(max_length=256)
    prompt_hash: str = Field(max_length=64)
    context_hash: str = Field(max_length=64)
    tool_schema_hash: str = Field(max_length=64)
    planner_version: str = Field(max_length=64)
    budgets: dict[str, StrictInt | StrictFloat] = Field(default_factory=dict, max_length=32)
    skill_hashes: dict[str, str] = Field(default_factory=dict, max_length=32)

    @model_validator(mode="after")
    def validate_identity(self):
        for name in ("provider", "model", "route", "prompt_hash", "context_hash",
                     "tool_schema_hash", "planner_version"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        for name in ("prompt_hash", "context_hash", "tool_schema_hash"):
            value = getattr(self, name)
            if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ValueError(f"{name} must be lowercase sha256")
        if any(not key.strip() for key in self.budgets):
            raise ValueError("budget keys must be non-empty")
        if any(isinstance(value, bool) or value < 0
               or isinstance(value, float) and not math.isfinite(value)
               for value in self.budgets.values()):
            raise ValueError("budget values must be finite non-negative numbers")
        if any(not key.strip() or not value.strip()
               for key, value in self.skill_hashes.items()):
            raise ValueError("skill hashes must be non-empty")
        if any(len(value) != 64 or any(
            char not in "0123456789abcdef" for char in value
        ) for value in self.skill_hashes.values()):
            raise ValueError("skill hashes must be lowercase sha256")
        return self

    @classmethod
    def freeze(
        cls,
        *,
        provider: str,
        model: str,
        route: str,
        prompt: str,
        context: Any,
        tool_schemas: Any,
        planner_version: str,
        budgets: dict[str, StrictInt | StrictFloat] | None = None,
        skill_hashes: dict[str, str] | None = None,
    ) -> "RequestEnvelope":
        for name, value in {
            "provider": provider, "model": model, "route": route,
            "planner_version": planner_version,
        }.items():
            if not value.strip():
                raise ValueError(f"{name} must be non-empty")
        return cls(
            provider=provider,
            model=model,
            route=route,
            prompt_hash=_hash(prompt),
            context_hash=_hash(context),
            tool_schema_hash=_hash(tool_schemas),
            planner_version=planner_version,
            budgets=budgets or {},
            skill_hashes=skill_hashes or {},
        )


class LedgerEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence: StrictInt = Field(ge=1)
    run_id: str = Field(max_length=256)
    kind: LedgerKind
    recorded_at: datetime
    turn_id: str = Field(max_length=256)
    step_id: str | None = Field(default=None, max_length=256)
    call_id: str | None = Field(default=None, max_length=512)
    data: dict[str, Any] = Field(default_factory=dict, max_length=64)

    @model_validator(mode="after")
    def validate_timestamp(self) -> "LedgerEntry":
        if self.recorded_at.utcoffset() is None:
            raise ValueError("ledger recorded_at must include timezone")
        return self


def _validate_start_data(kind: LedgerKind, data: dict[str, Any]) -> None:
    if kind == LedgerKind.TURN_START:
        if (set(data) != {"request"}
                or not isinstance(data.get("request"), str)
                or not data["request"].strip()):
            raise ValueError("turn start requires exactly one non-empty request")
    elif kind == LedgerKind.STEP_START and data:
        raise ValueError("step start data must be empty")


def _validate_terminal_data(kind: LedgerKind, data: dict[str, Any]) -> None:
    if kind not in (LedgerKind.STEP_END, LedgerKind.TURN_END):
        return
    duration_ms = data.get("duration_ms")
    if (duration_ms is not None
            and (not isinstance(duration_ms, int) or isinstance(duration_ms, bool)
                 or duration_ms < 0)):
        raise ValueError("terminal duration_ms must be a non-negative integer")
    reason = data.get("reason")
    if reason not in {item.value for item in TerminalReason}:
        raise ValueError("terminal ledger event requires a valid reason")
    if reason == TerminalReason.COMPLETE.value:
        if "error" in data:
            raise ValueError("completed terminal event cannot carry an error")
    else:
        error = data.get("error")
        if error is not None and (not isinstance(error, str) or not error.strip()):
            raise ValueError("terminal event error must be non-empty when present")


def _validate_assistant_attempt(data: dict[str, Any]) -> None:
    status = data.get("status")
    attempt_keys = {"provider_attempts", "model_requests", "repaired",
                    "null_as_omitted_drops", "carried_from_intake",
                    "reasoning_content_promotions"}
    provider_attempts = data.get("provider_attempts", [])
    promotions = data.get("reasoning_content_promotions", [])
    safe_attempt_keys = {"route", "provider", "model", "attempt_number",
                         "exception_type", "message_class", "latency_ms",
                         "failure_top_class", "failure_class_chain",
                         "failure_phase", "failure_validation_errors",
                         "failure_validation_subtype", "failure_schema_sha256",
                         "failure_route"}
    from v2.adapters.models import (
        MODEL_ROUTES, SAFE_FAILURE_EXCEPTION_CLASSES, SAFE_FAILURE_PHASES,
        SAFE_PYDANTIC_ERROR_TYPES, SAFE_FAILURE_VALIDATION_SUBTYPES,
    )
    safe_exception_names = {*SAFE_FAILURE_EXCEPTION_CLASSES, "<unknown-exception>"}
    safe_error_types = {*SAFE_PYDANTIC_ERROR_TYPES, "<unknown-error-type>"}
    def safe_string(value: Any, limit: int = 120) -> bool:
        return isinstance(value, str) and bool(value.strip()) and len(value) <= limit
    def safe_taxonomy(item: dict[str, Any]) -> bool:
        subtype = {"failure_top_class", "failure_class_chain", "failure_phase",
                   "failure_validation_errors", "failure_validation_subtype",
                   "failure_schema_sha256", "failure_route"}
        present = subtype & set(item)
        if not present:
            return True
        if present != subtype:
            return False
        chain = item["failure_class_chain"]
        errors = item["failure_validation_errors"]
        return (
            safe_string(item["failure_top_class"])
            and isinstance(chain, list) and len(chain) <= 12
            and all(value in safe_exception_names for value in chain)
            and item["failure_top_class"] in safe_exception_names
            and item["failure_phase"] in SAFE_FAILURE_PHASES
            and isinstance(errors, list) and len(errors) <= 16
            and all(isinstance(error, dict)
                    and set(error) == {"type", "loc"}
                    and error["type"] in safe_error_types
                    and isinstance(error["loc"], list) and len(error["loc"]) <= 16
                    and all((isinstance(part, int) and not isinstance(part, bool))
                            or safe_string(part) for part in error["loc"])
                    for error in errors)
            and item["failure_validation_subtype"] in SAFE_FAILURE_VALIDATION_SUBTYPES
            and (
                item["failure_validation_subtype"] != "not_applicable"
                if item["failure_phase"] == "json_or_schema_validation"
                else item["failure_validation_subtype"] == "not_applicable"
            )
            and isinstance(item["failure_schema_sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", item["failure_schema_sha256"])
            is not None
            and item["failure_route"] in MODEL_ROUTES
            and item["failure_route"] == item.get("route")
        )
    attempts_valid = isinstance(provider_attempts, list) and all(
        isinstance(item, dict)
        and set(item) <= safe_attempt_keys
        and item.get("route") in MODEL_ROUTES
        and safe_string(item.get("provider"))
        and safe_string(item.get("model"))
        and isinstance(item.get("attempt_number"), int)
        and not isinstance(item.get("attempt_number"), bool)
        and item["attempt_number"] >= 1
        and safe_string(item.get("message_class"))
        and ("exception_type" not in item or item["exception_type"] in safe_exception_names)
        and isinstance(item.get("latency_ms"), int)
        and not isinstance(item.get("latency_ms"), bool)
        and item["latency_ms"] >= 0
        and safe_taxonomy(item)
        for item in provider_attempts)
    safe_promotion_keys = {"provider", "choice_index", "finish_reason",
                           "reasoning_content_chars"}
    promotions_valid = isinstance(promotions, list) and all(
        isinstance(item, dict)
        and set(item) <= safe_promotion_keys
        and safe_string(item.get("provider"))
        and isinstance(item.get("choice_index"), int)
        and not isinstance(item.get("choice_index"), bool)
        and item["choice_index"] >= 0
        and item.get("finish_reason") == "stop"
        and isinstance(item.get("reasoning_content_chars"), int)
        and not isinstance(item.get("reasoning_content_chars"), bool)
        and item["reasoning_content_chars"] >= 0
        for item in promotions)
    required_failed = {"status", "error"}
    required_accepted = {"status", "output", "provider", "model", "used_fallback"}
    if status == "failed":
        valid = (required_failed <= set(data) <= {*required_failed, *attempt_keys}
                 and isinstance(data.get("error"), str)
                 and bool(data["error"].strip()) and attempts_valid
                 and promotions_valid)
    elif status == "accepted":
        requests = data.get("model_requests")
        requests_valid = ("model_requests" not in data or (
            isinstance(requests, int) and not isinstance(requests, bool)
            and requests >= 1))
        repaired_valid = ("repaired" not in data
                          or isinstance(data["repaired"], bool))
        drops = data.get("null_as_omitted_drops", [])
        drops_valid = (
            isinstance(drops, list)
            and all(isinstance(item, dict)
                    and set(item) == {"route", "capability_id", "key", "rule"}
                    and item["route"] in MODEL_ROUTES
                    and safe_string(item["capability_id"], 64)
                    and safe_string(item["key"], 64)
                    and item["rule"] == "null-as-omitted"
                    for item in drops))
        carries = data.get("carried_from_intake", [])
        carries_valid = (
            isinstance(carries, list)
            and all(isinstance(item, dict)
                    and set(item) == {"route", "capability_id", "key", "rule"}
                    and item["route"] in MODEL_ROUTES
                    and safe_string(item["capability_id"], 64)
                    and safe_string(item["key"], 64)
                    and item["rule"] == "carried-from-intake"
                    for item in carries))
        valid = (required_accepted <= set(data) <= {*required_accepted, *attempt_keys}
                 and attempts_valid and promotions_valid
                 and isinstance(data.get("output"), dict)
                 and isinstance(data.get("provider"), str)
                 and bool(data["provider"].strip())
                 and isinstance(data.get("model"), str)
                 and bool(data["model"].strip())
                 and isinstance(data.get("used_fallback"), bool)
                 and requests_valid and repaired_valid and drops_valid
                 and carries_valid)
    else:
        raise ValueError("assistant attempt status must be accepted or failed")
    if not valid:
        raise ValueError("assistant attempt data does not match its status")


def _validate_attempt_identity(envelope: RequestEnvelope, data: dict[str, Any]) -> None:
    if data.get("status") != "accepted":
        return
    same_identity = (data["provider"], data["model"]) == (
        envelope.provider, envelope.model)
    if data["used_fallback"] == same_identity:
        raise ValueError("assistant attempt fallback flag must match model identity")


class RunLedger:
    def __init__(self, run_id: str, entries: Iterable[LedgerEntry] = ()) -> None:
        if not run_id.strip():
            raise ValueError("ledger run id must be non-empty")
        self.run_id = run_id
        self._entries = list(entries)
        if any(
            later.recorded_at < earlier.recorded_at
            for earlier, later in zip(self._entries, self._entries[1:])
        ):
            raise ValueError("ledger timestamps must be nondecreasing")
        if any(entry.run_id != run_id for entry in self._entries):
            raise ValueError("ledger entries must belong to one run")
        if [entry.sequence for entry in self._entries] != list(
            range(1, len(self._entries) + 1)
        ):
            raise ValueError("ledger sequence must be contiguous")
        self._calls: dict[str, str] = {}
        self._results: set[str] = set()
        self._model_requests: dict[str, RequestEnvelope] = {}
        self._model_attempts: set[str] = set()
        open_turns: set[str] = set()
        open_steps: set[tuple[str, str]] = set()
        closed_turns: set[str] = set()
        for entry in self._entries:
            if not entry.turn_id.strip():
                raise ValueError("ledger turn id must be non-empty")
            if entry.step_id is not None and not entry.step_id.strip():
                raise ValueError("ledger step id must be non-empty when present")
            if entry.call_id is not None and not entry.call_id.strip():
                raise ValueError("ledger call id must be non-empty when present")
            if entry.kind in (LedgerKind.STEP_START, LedgerKind.STEP_END)                     and not entry.step_id:
                raise ValueError("step events require step_id")
            if entry.kind in (LedgerKind.TURN_START, LedgerKind.TURN_END)                     and entry.step_id is not None:
                raise ValueError("turn events cannot carry step_id")
            _validate_start_data(entry.kind, entry.data)
            _validate_terminal_data(entry.kind, entry.data)
            if entry.kind == LedgerKind.TURN_START:
                if entry.turn_id in open_turns or entry.turn_id in closed_turns:
                    raise ValueError("turn may start only once")
                open_turns.add(entry.turn_id)
            elif entry.kind == LedgerKind.TURN_END:
                if entry.turn_id not in open_turns:
                    raise ValueError("turn end requires an open turn")
                if any(turn == entry.turn_id for turn, _ in open_steps):
                    raise ValueError("turn cannot end with open steps")
                open_turns.remove(entry.turn_id)
                closed_turns.add(entry.turn_id)
            elif entry.turn_id in closed_turns:
                raise ValueError("events cannot follow turn end")
            if entry.kind == LedgerKind.STEP_START and entry.step_id:
                key = (entry.turn_id, entry.step_id)
                if key in open_steps:
                    raise ValueError("step may start only once before ending")
                open_steps.add(key)
            elif entry.kind == LedgerKind.STEP_END and entry.step_id:
                key = (entry.turn_id, entry.step_id)
                if key not in open_steps:
                    raise ValueError("step end requires an open step")
                open_steps.remove(key)
            if entry.kind == LedgerKind.MODEL_REQUEST:
                if not entry.call_id:
                    raise ValueError("model request requires call_id")
                if entry.call_id in self._model_requests:
                    raise ValueError("model request call id must be unique")
                envelope = RequestEnvelope.model_validate(entry.data)
                self._model_requests[entry.call_id] = envelope
            elif entry.kind == LedgerKind.ASSISTANT_ATTEMPT:
                _validate_assistant_attempt(entry.data)
                if not entry.call_id or entry.call_id not in self._model_requests:
                    raise ValueError("assistant attempt requires an earlier model request")
                if entry.call_id in self._model_attempts:
                    raise ValueError("model request may have only one assistant attempt")
                _validate_attempt_identity(
                    self._model_requests[entry.call_id], entry.data)
                self._model_attempts.add(entry.call_id)
            if entry.kind == LedgerKind.TOOL_CALL and entry.call_id:
                if set(entry.data) != {"name", "args"}:
                    raise ValueError("tool call data must contain exactly name and args")
                if not isinstance(entry.data["name"], str)                         or not entry.data["name"].strip():
                    raise ValueError("tool call name must be non-empty")
                if not isinstance(entry.data["args"], dict):
                    raise ValueError("tool call args must be an object")
                identity = _call_identity(entry)
                previous = self._calls.get(entry.call_id)
                if previous is not None and previous != identity:
                    raise ValueError("a call id cannot change tool identity or arguments")
                if entry.call_id in self._results:
                    raise ValueError("tool call cannot follow its result")
                self._calls[entry.call_id] = identity
            elif entry.kind == LedgerKind.TOOL_RESULT:
                if not entry.call_id or entry.call_id not in self._calls:
                    raise ValueError("tool result requires an earlier tool call")
                if entry.call_id in self._results:
                    raise ValueError("tool call may have only one result")
                status = entry.data.get("status")
                duration_ms = entry.data.get("duration_ms")
                allowed_duration = (
                    {"duration_ms"} if "duration_ms" in entry.data else set())
                if status == "ok":
                    valid = (set(entry.data) == {"status", "evidence"} | allowed_duration
                             and isinstance(entry.data.get("evidence"), dict))
                elif status == "failed":
                    valid = (set(entry.data) == {"status", "error"} | allowed_duration
                             and isinstance(entry.data.get("error"), str)
                             and bool(entry.data["error"].strip()))
                else:
                    raise ValueError("tool result status must be ok or failed")
                if (duration_ms is not None
                        and (not isinstance(duration_ms, int)
                             or isinstance(duration_ms, bool) or duration_ms < 0)):
                    raise ValueError(
                        "tool result duration_ms must be a non-negative integer")
                if not valid:
                    raise ValueError("tool result data does not match its status")
                self._results.add(entry.call_id)

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        return tuple(self._entries)

    def append(
        self,
        kind: LedgerKind,
        *,
        turn_id: str,
        step_id: str | None = None,
        call_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> LedgerEntry:
        payload = dict(data or {})
        open_turns, open_steps, closed_turns = self._lifecycle_state()
        if kind == LedgerKind.TURN_START:
            if turn_id in open_turns or turn_id in closed_turns:
                raise ValueError("turn may start only once")
        elif kind == LedgerKind.TURN_END:
            if turn_id not in open_turns:
                raise ValueError("turn end requires an open turn")
            if any(turn == turn_id for turn, _ in open_steps):
                raise ValueError("turn cannot end with open steps")
        elif turn_id in closed_turns:
            raise ValueError("events cannot follow turn end")
        if kind == LedgerKind.STEP_START and step_id:
            if (turn_id, step_id) in open_steps:
                raise ValueError("step may start only once before ending")
        elif kind == LedgerKind.STEP_END and step_id:
            if (turn_id, step_id) not in open_steps:
                raise ValueError("step end requires an open step")
        if not turn_id.strip():
            raise ValueError("ledger turn id must be non-empty")
        if step_id is not None and not step_id.strip():
            raise ValueError("ledger step id must be non-empty when present")
        if call_id is not None and not call_id.strip():
            raise ValueError("ledger call id must be non-empty when present")
        if kind in (LedgerKind.STEP_START, LedgerKind.STEP_END) and not step_id:
            raise ValueError("step events require step_id")
        if kind in (LedgerKind.TURN_START, LedgerKind.TURN_END) and step_id is not None:
            raise ValueError("turn events cannot carry step_id")
        if kind in (LedgerKind.TOOL_CALL, LedgerKind.TOOL_RESULT,
                    LedgerKind.MODEL_REQUEST, LedgerKind.ASSISTANT_ATTEMPT)                 and not call_id:
            raise ValueError("call events require call_id")
        _validate_start_data(kind, payload)
        _validate_terminal_data(kind, payload)
        if kind == LedgerKind.MODEL_REQUEST:
            if call_id in self._model_requests:
                raise ValueError("model request call id must be unique")
            envelope = RequestEnvelope.model_validate(payload)
            self._model_requests[call_id] = envelope
        elif kind == LedgerKind.ASSISTANT_ATTEMPT:
            _validate_assistant_attempt(payload)
            if call_id not in self._model_requests:
                raise ValueError("assistant attempt requires an earlier model request")
            if call_id in self._model_attempts:
                raise ValueError("model request may have only one assistant attempt")
            _validate_attempt_identity(self._model_requests[call_id], payload)
            self._model_attempts.add(call_id)
        if kind == LedgerKind.TOOL_CALL:
            if set(payload) != {"name", "args"}:
                raise ValueError("tool call data must contain exactly name and args")
            if not isinstance(payload["name"], str) or not payload["name"].strip():
                raise ValueError("tool call name must be non-empty")
            if not isinstance(payload["args"], dict):
                raise ValueError("tool call args must be an object")
            identity = _hash({"name": payload["name"], "args": payload["args"]})
            previous = self._calls.get(call_id)
            if previous is not None and previous != identity:
                raise ValueError("a call id cannot change tool identity or arguments")
            self._calls[call_id] = identity
        if kind == LedgerKind.TOOL_CALL and call_id in self._results:
            raise ValueError("tool call cannot follow its result")
        if kind == LedgerKind.TOOL_RESULT:
            if call_id not in self._calls:
                raise ValueError("tool result requires an earlier tool call")
            if call_id in self._results:
                raise ValueError("tool call may have only one result")
            status = payload.get("status")
            duration_ms = payload.get("duration_ms")
            allowed_duration = ({"duration_ms"} if "duration_ms" in payload else set())
            if status == "ok":
                if (set(payload) != {"status", "evidence"} | allowed_duration
                        or not isinstance(payload.get("evidence"), dict)):
                    raise ValueError(
                        "successful tool result requires exactly status and evidence object")
            elif status == "failed":
                if (set(payload) != {"status", "error"} | allowed_duration
                        or not isinstance(payload.get("error"), str)
                        or not payload["error"].strip()):
                    raise ValueError(
                        "failed tool result requires exactly status and non-empty error")
            else:
                raise ValueError("tool result status must be ok or failed")
            if (duration_ms is not None
                    and (not isinstance(duration_ms, int) or isinstance(duration_ms, bool)
                         or duration_ms < 0)):
                raise ValueError("tool result duration_ms must be a non-negative integer")
            self._results.add(call_id)
        recorded_at = datetime.now(UTC)
        if self._entries and recorded_at < self._entries[-1].recorded_at:
            recorded_at = self._entries[-1].recorded_at
        entry = LedgerEntry(
            sequence=len(self._entries) + 1,
            run_id=self.run_id,
            kind=kind,
            recorded_at=recorded_at,
            turn_id=turn_id,
            step_id=step_id,
            call_id=call_id,
            data=payload,
        )
        self._entries.append(entry)
        return entry

    def _lifecycle_state(self):
        open_turns: set[str] = set()
        open_steps: set[tuple[str, str]] = set()
        closed_turns: set[str] = set()
        for entry in self._entries:
            if entry.kind == LedgerKind.TURN_START:
                open_turns.add(entry.turn_id)
            elif entry.kind == LedgerKind.TURN_END:
                open_turns.discard(entry.turn_id)
                closed_turns.add(entry.turn_id)
            elif entry.kind == LedgerKind.STEP_START and entry.step_id:
                open_steps.add((entry.turn_id, entry.step_id))
            elif entry.kind == LedgerKind.STEP_END and entry.step_id:
                open_steps.discard((entry.turn_id, entry.step_id))
        return open_turns, open_steps, closed_turns

    def model_history(self, turn_id: str) -> list[dict[str, Any]]:
        history = []
        for entry in self._entries:
            if entry.turn_id != turn_id:
                continue
            if entry.kind == LedgerKind.TOOL_RESULT and entry.data.get("status") == "ok":
                history.append(entry.data)
            elif (
                entry.kind == LedgerKind.ASSISTANT_ATTEMPT
                and entry.data.get("status") == "accepted"
            ):
                history.append(entry.data)
        return history

    def unfinished_steps(self, turn_id: str | None = None) -> set[str]:
        started = {
            entry.step_id
            for entry in self._entries
            if entry.kind == LedgerKind.STEP_START and entry.step_id
            and (turn_id is None or entry.turn_id == turn_id)
        }
        ended = {
            entry.step_id
            for entry in self._entries
            if entry.kind == LedgerKind.STEP_END and entry.step_id
            and (turn_id is None or entry.turn_id == turn_id)
        }
        return started - ended

    def close_interrupted(self, turn_id: str, reason: TerminalReason) -> None:
        for step_id in sorted(self.unfinished_steps(turn_id)):
            self.append(
                LedgerKind.STEP_END,
                turn_id=turn_id,
                step_id=step_id,
                data={"reason": reason.value},
            )
        self.append(
            LedgerKind.TURN_END,
            turn_id=turn_id,
            data={"reason": reason.value},
        )


class _LedgerWriter:
    """Internal write seam; not reachable from runtime configuration."""
    def write(self, fd: int, payload: bytes) -> None:
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("ledger write made no progress")
            view = view[written:]


def _canonical_ledger_path(directory: str | Path, run_id: str) -> Path:
    if not run_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in run_id):
        raise ValueError("run_id may contain only letters, numbers, '-' and '_'")
    root = Path(directory).expanduser().resolve(strict=False)
    if root.exists() and root.is_symlink():
        raise ValueError("ledger directory cannot be a symlink")
    candidate = (root / f"{run_id}.jsonl").resolve(strict=False)
    if candidate.parent != root:
        raise ValueError("ledger path escapes configured directory")
    return candidate

class FileLedger:
    def __init__(self, path: str | Path, run_id: str, *, _writer: _LedgerWriter | None = None) -> None:
        supplied = Path(path)
        if supplied.is_symlink():
            raise ValueError("ledger file cannot be a symlink")
        if any(component.is_symlink() for component in (supplied.parent, *supplied.parent.parents)):
            raise ValueError("ledger file parent cannot be a symlink")
        self.path = _canonical_ledger_path(supplied.parent, run_id)
        if supplied.name != self.path.name or supplied.resolve(strict=False) != self.path:
            raise ValueError("ledger path must be canonical <ledger_dir>/<run_id>.jsonl")
        self._reject_symlinked_path()
        self._lock_path = self.path.with_name(self.path.name + ".lock")
        self._lock = _ledger_path_lock(self.path)
        self._writer = _writer or _LedgerWriter()
        with self._critical_section():
            self.ledger = RunLedger(run_id, self._read())

    @property
    def run_id(self) -> str:
        return self.ledger.run_id

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        with self._critical_section():
            self.ledger = RunLedger(self.run_id, self._read())
            return self.ledger.entries

    from contextlib import contextmanager
    @contextmanager
    def _critical_section(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self._lock_path.open("a+b") as lock_handle:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def append(self, *args: Any, **kwargs: Any) -> LedgerEntry:
        expected_sequence = kwargs.pop("_expected_sequence", None)
        with self._critical_section():
            staged = RunLedger(self.run_id, self._read())
            actual_sequence = len(staged.entries) + 1
            if expected_sequence is not None and expected_sequence != actual_sequence:
                raise ValueError("ledger sequence changed before append")
            entry = staged.append(*args, **kwargs)
            payload = (entry.model_dump_json() + "\n").encode()
            file_was_missing = not self.path.exists()
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            offset = os.lseek(fd, 0, os.SEEK_END)
            try:
                self._writer.write(fd, payload)
                os.fsync(fd)
            except BaseException:
                os.ftruncate(fd, offset)
                os.fsync(fd)
                raise
            finally:
                os.close(fd)
            if file_was_missing:
                directory_fd = os.open(self.path.parent, os.O_RDONLY)
                try: os.fsync(directory_fd)
                finally: os.close(directory_fd)
            self.ledger = staged
            return entry

    def _reject_symlinked_path(self) -> None:
        if self.path.is_symlink(): raise ValueError("ledger file cannot be a symlink")
        parent = self.path.parent
        if any(component.is_symlink() for component in (parent, *parent.parents)):
            raise ValueError("ledger file parent cannot be a symlink")

    def _read(self) -> list[LedgerEntry]:
        self._reject_symlinked_path()
        if not self.path.exists(): return []
        raw = self.path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            raise ValueError("ledger has an incomplete trailing record")
        lines = raw.splitlines()
        if any(not line.strip() for line in lines): raise ValueError("ledger cannot contain blank records")
        return [LedgerEntry.model_validate_json(line) for line in lines]


def _hash(value: Any) -> str:
    raw = value if isinstance(value, str) else json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _call_identity(entry: LedgerEntry) -> str:
    return _hash({"name": entry.data.get("name"), "args": entry.data.get("args")})

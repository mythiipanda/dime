from __future__ import annotations

import hashlib
import json
import os
import math
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


class RequestEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str
    model: str
    route: str
    prompt_hash: str
    context_hash: str
    tool_schema_hash: str
    planner_version: str
    budgets: dict[str, StrictInt | StrictFloat] = Field(default_factory=dict)
    skill_hashes: dict[str, str] = Field(default_factory=dict)

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

    sequence: int = Field(ge=1)
    run_id: str
    kind: LedgerKind
    recorded_at: datetime
    turn_id: str
    step_id: str | None = None
    call_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_timestamp(self) -> "LedgerEntry":
        if self.recorded_at.tzinfo is None:
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
    if status == "failed":
        valid = (set(data) == {"status", "error"}
                 and isinstance(data.get("error"), str)
                 and bool(data["error"].strip()))
    elif status == "accepted":
        valid = (set(data) == {"status", "output", "provider", "model", "used_fallback"}
                 and isinstance(data.get("output"), dict)
                 and isinstance(data.get("provider"), str)
                 and bool(data["provider"].strip())
                 and isinstance(data.get("model"), str)
                 and bool(data["model"].strip())
                 and isinstance(data.get("used_fallback"), bool))
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
                if status == "ok":
                    valid = (set(entry.data) == {"status", "evidence"}
                             and isinstance(entry.data.get("evidence"), dict))
                elif status == "failed":
                    valid = (set(entry.data) == {"status", "error"}
                             and isinstance(entry.data.get("error"), str)
                             and bool(entry.data["error"].strip()))
                else:
                    raise ValueError("tool result status must be ok or failed")
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
            if status == "ok":
                if set(payload) != {"status", "evidence"}                         or not isinstance(payload.get("evidence"), dict):
                    raise ValueError(
                        "successful tool result requires exactly status and evidence object")
            elif status == "failed":
                if set(payload) != {"status", "error"}                         or not isinstance(payload.get("error"), str)                         or not payload["error"].strip():
                    raise ValueError(
                        "failed tool result requires exactly status and non-empty error")
            else:
                raise ValueError("tool result status must be ok or failed")
            self._results.add(call_id)
        entry = LedgerEntry(
            sequence=len(self._entries) + 1,
            run_id=self.run_id,
            kind=kind,
            recorded_at=datetime.now(UTC),
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


class FileLedger:
    def __init__(self, path: str | Path, run_id: str) -> None:
        self.path = Path(path)
        self._lock = _ledger_path_lock(self.path)
        with self._lock:
            self.ledger = RunLedger(run_id, self._read())

    @property
    def run_id(self) -> str:
        return self.ledger.run_id

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        return self.ledger.entries

    def append(self, *args: Any, **kwargs: Any) -> LedgerEntry:
        with self._lock:
            staged = RunLedger(self.run_id, self._read())
            entry = staged.append(*args, **kwargs)
            parent_was_missing = not self.path.parent.exists()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            file_was_missing = not self.path.exists()
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(entry.model_dump_json() + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            if file_was_missing or parent_was_missing:
                directory_fd = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            self.ledger = staged
            return entry

    def _read(self) -> list[LedgerEntry]:
        if self.path.is_symlink():
            raise ValueError("ledger file cannot be a symlink")
        if not self.path.exists():
            return []
        text = self.path.read_text()
        lines = text.splitlines()
        if any(not line.strip() for line in lines):
            raise ValueError("ledger cannot contain blank records")
        if text and not text.endswith("\n"):
            try:
                LedgerEntry.model_validate_json(lines[-1])
            except ValueError:
                lines.pop()
                normalized = "\n".join(lines) + ("\n" if lines else "")
            else:
                normalized = text + "\n"
            with self.path.open("w", encoding="utf-8") as handle:
                handle.write(normalized)
                handle.flush()
                os.fsync(handle.fileno())
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        return [
            LedgerEntry.model_validate_json(line)
            for line in lines
        ]


def _hash(value: Any) -> str:
    raw = value if isinstance(value, str) else json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _call_identity(entry: LedgerEntry) -> str:
    return _hash({"name": entry.data.get("name"), "args": entry.data.get("args")})

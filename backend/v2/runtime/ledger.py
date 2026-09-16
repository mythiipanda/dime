from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field


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
    budgets: dict[str, int | float] = Field(default_factory=dict)
    skill_hashes: dict[str, str] = Field(default_factory=dict)

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
        budgets: dict[str, int | float] | None = None,
        skill_hashes: dict[str, str] | None = None,
    ) -> "RequestEnvelope":
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


class RunLedger:
    def __init__(self, run_id: str, entries: Iterable[LedgerEntry] = ()) -> None:
        if not run_id.strip():
            raise ValueError("ledger run id must be non-empty")
        self.run_id = run_id
        self._entries = list(entries)
        if any(entry.run_id != run_id for entry in self._entries):
            raise ValueError("ledger entries must belong to one run")
        if [entry.sequence for entry in self._entries] != list(
            range(1, len(self._entries) + 1)
        ):
            raise ValueError("ledger sequence must be contiguous")
        self._calls: dict[str, str] = {}
        self._results: set[str] = set()
        for entry in self._entries:
            if entry.kind == LedgerKind.TOOL_CALL and entry.call_id:
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
        if not turn_id.strip():
            raise ValueError("ledger turn id must be non-empty")
        if step_id is not None and not step_id.strip():
            raise ValueError("ledger step id must be non-empty when present")
        if call_id is not None and not call_id.strip():
            raise ValueError("ledger call id must be non-empty when present")
        if kind in (LedgerKind.TOOL_CALL, LedgerKind.TOOL_RESULT) and not call_id:
            raise ValueError("tool events require call_id")
        if kind == LedgerKind.TOOL_CALL:
            identity = _hash({"name": payload.get("name"), "args": payload.get("args")})
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

    def unfinished_steps(self) -> set[str]:
        started = {
            entry.step_id
            for entry in self._entries
            if entry.kind == LedgerKind.STEP_START and entry.step_id
        }
        ended = {
            entry.step_id
            for entry in self._entries
            if entry.kind == LedgerKind.STEP_END and entry.step_id
        }
        return started - ended

    def close_interrupted(self, turn_id: str, reason: TerminalReason) -> None:
        for step_id in sorted(self.unfinished_steps()):
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
        self._lock = Lock()
        self.ledger = RunLedger(run_id, self._read())

    @property
    def run_id(self) -> str:
        return self.ledger.run_id

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        return self.ledger.entries

    def append(self, *args: Any, **kwargs: Any) -> LedgerEntry:
        with self._lock:
            entry = self.ledger.append(*args, **kwargs)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(entry.model_dump_json() + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return entry

    def _read(self) -> list[LedgerEntry]:
        if not self.path.exists():
            return []
        return [
            LedgerEntry.model_validate_json(line)
            for line in self.path.read_text().splitlines()
            if line.strip()
        ]


def _hash(value: Any) -> str:
    raw = value if isinstance(value, str) else json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _call_identity(entry: LedgerEntry) -> str:
    return _hash({"name": entry.data.get("name"), "args": entry.data.get("args")})

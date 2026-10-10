from __future__ import annotations

from typing import Any, Iterable

from v2.contracts import EvidenceEnvelope
from v2.runtime.ledger import LedgerEntry, LedgerKind

_TIMING_KEY = "duration_ms"

def _timing_ms(data: dict[str, Any]) -> int | None:
    if _TIMING_KEY not in data:
        return None
    duration_ms = data[_TIMING_KEY]
    if (not isinstance(duration_ms, int) or isinstance(duration_ms, bool)
            or duration_ms < 0):
        raise ValueError(
            "tool result duration_ms must be a non-negative integer")
    return duration_ms

def _validated_entries(entries: Iterable[LedgerEntry]) -> list[LedgerEntry]:
    return [LedgerEntry.model_validate(entry.model_dump()) for entry in entries]

def admitted_evidence(entries: Iterable[LedgerEntry]) -> list[EvidenceEnvelope]:
    records = _validated_entries(entries)
    tool_attempts(records)
    evidence: list[EvidenceEnvelope] = []
    seen: dict[str, EvidenceEnvelope] = {}
    for entry in records:
        if entry.kind != LedgerKind.TOOL_RESULT or entry.data.get("status") != "ok":
            continue
        _timing_ms(entry.data)
        if set(entry.data) - {_TIMING_KEY} != {"status", "evidence"}:
            raise ValueError("successful tool result has unexpected fields")
        payload = entry.data.get("evidence")
        if not isinstance(payload, dict):
            raise ValueError("successful tool result requires evidence object")
        item = EvidenceEnvelope.model_validate(payload)
        previous = seen.get(item.evidence_id)
        if previous is not None and previous != item:
            raise ValueError(
                f"evidence id {item.evidence_id} has conflicting payloads")
        if previous is None:
            evidence.append(item)
            seen[item.evidence_id] = item
    return evidence

def tool_attempts(entries: Iterable[LedgerEntry]) -> list[dict[str, Any]]:
    records = _validated_entries(entries)
    calls: dict[str, LedgerEntry] = {}
    for entry in records:
        if entry.kind != LedgerKind.TOOL_CALL or not entry.call_id:
            continue
        previous = calls.get(entry.call_id)
        if previous is not None and previous.data != entry.data:
            raise ValueError(f"tool call id {entry.call_id} has conflicting payloads")
        calls[entry.call_id] = entry
    attempts: list[dict[str, Any]] = []
    results: set[str] = set()
    for entry in records:
        if entry.kind != LedgerKind.TOOL_RESULT or not entry.call_id:
            continue
        call = calls.get(entry.call_id)
        if call is None:
            raise ValueError("tool result requires its recorded call")
        if entry.call_id in results:
            raise ValueError("tool call has multiple results")
        results.add(entry.call_id)
        if set(call.data) != {"name", "args"}:
            raise ValueError("tool call has unexpected fields")
        if not isinstance(call.data["name"], str) or not call.data["name"].strip():
            raise ValueError("tool call requires a non-empty name")
        if not isinstance(call.data["args"], dict):
            raise ValueError("tool call requires an args object")
        status = entry.data.get("status")
        duration_ms = _timing_ms(entry.data)
        if status == "ok":
            valid = (set(entry.data) - {_TIMING_KEY} == {"status", "evidence"}
                     and isinstance(entry.data.get("evidence"), dict))
        elif status == "failed":
            valid = (set(entry.data) - {_TIMING_KEY} == {"status", "error"}
                     and isinstance(entry.data.get("error"), str)
                     and bool(entry.data["error"].strip()))
        else:
            raise ValueError("tool result status must be ok or failed")
        if not valid:
            raise ValueError("tool result data does not match its status")
        attempt: dict[str, Any] = {
            "call_id": entry.call_id,
            "name": call.data["name"],
            "args": call.data["args"],
            "status": status,
            "error": entry.data.get("error"),
        }
        if duration_ms is not None:
            attempt[_TIMING_KEY] = duration_ms
        attempts.append(attempt)
    return attempts

def replay_turn(entries: Iterable[LedgerEntry]) -> dict[str, Any]:
    return {
        "evidence": [item.model_dump(mode="json")
                     for item in admitted_evidence(entries)],
        "tools": tool_attempts(entries),
    }

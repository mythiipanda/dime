from __future__ import annotations

from typing import Any, Iterable

from v2.contracts import EvidenceEnvelope
from v2.runtime.ledger import LedgerEntry, LedgerKind


def admitted_evidence(entries: Iterable[LedgerEntry]) -> list[EvidenceEnvelope]:
    evidence: list[EvidenceEnvelope] = []
    seen: set[str] = set()
    for entry in entries:
        if entry.kind != LedgerKind.TOOL_RESULT or entry.data.get("status") != "ok":
            continue
        if set(entry.data) != {"status", "evidence"}:
            raise ValueError("successful tool result has unexpected fields")
        payload = entry.data.get("evidence")
        if not isinstance(payload, dict):
            raise ValueError("successful tool result requires evidence object")
        item = EvidenceEnvelope.model_validate(payload)
        if item.evidence_id not in seen:
            evidence.append(item)
            seen.add(item.evidence_id)
    return evidence


def tool_attempts(entries: Iterable[LedgerEntry]) -> list[dict[str, Any]]:
    calls = {
        entry.call_id: entry for entry in entries
        if entry.kind == LedgerKind.TOOL_CALL and entry.call_id
    }
    attempts: list[dict[str, Any]] = []
    for entry in entries:
        if entry.kind != LedgerKind.TOOL_RESULT or not entry.call_id:
            continue
        call = calls.get(entry.call_id)
        if call is None:
            continue
        attempts.append({
            "call_id": entry.call_id,
            "name": call.data.get("name"),
            "args": call.data.get("args", {}),
            "status": entry.data.get("status"),
            "error": entry.data.get("error"),
        })
    return attempts


def replay_turn(entries: Iterable[LedgerEntry]) -> dict[str, Any]:
    return {
        "evidence": [item.model_dump(mode="json")
                     for item in admitted_evidence(entries)],
        "tools": tool_attempts(entries),
    }

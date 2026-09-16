from __future__ import annotations

from typing import Any, Iterable

from v2.contracts import EvidenceEnvelope
from v2.runtime.ledger import LedgerEntry, LedgerKind


def admitted_evidence(entries: Iterable[LedgerEntry]) -> list[EvidenceEnvelope]:
    evidence: list[EvidenceEnvelope] = []
    seen: dict[str, EvidenceEnvelope] = {}
    for entry in entries:
        if entry.kind != LedgerKind.TOOL_RESULT or entry.data.get("status") != "ok":
            continue
        if set(entry.data) != {"status", "evidence"}:
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
        if set(call.data) != {"name", "args"}:
            raise ValueError("tool call has unexpected fields")
        if not isinstance(call.data["name"], str) or not call.data["name"].strip():
            raise ValueError("tool call requires a non-empty name")
        if not isinstance(call.data["args"], dict):
            raise ValueError("tool call requires an args object")
        status = entry.data.get("status")
        if status not in {"ok", "failed"}:
            raise ValueError("tool result status must be ok or failed")
        attempts.append({
            "call_id": entry.call_id,
            "name": call.data["name"],
            "args": call.data["args"],
            "status": status,
            "error": entry.data.get("error"),
        })
    return attempts


def replay_turn(entries: Iterable[LedgerEntry]) -> dict[str, Any]:
    return {
        "evidence": [item.model_dump(mode="json")
                     for item in admitted_evidence(entries)],
        "tools": tool_attempts(entries),
    }

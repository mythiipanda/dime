from datetime import UTC, datetime

from v2.contracts import EvidenceEnvelope
from v2.runtime.ledger import LedgerKind, RunLedger
from v2.runtime.projections import admitted_evidence, replay_turn, tool_attempts


def ledger_with_attempt():
    ledger = RunLedger("run")
    ledger.append(LedgerKind.TOOL_CALL, turn_id="turn", step_id="facts",
                  call_id="call", data={"name": "standings", "args": {"season": "2025-26"}})
    evidence = EvidenceEnvelope(
        evidence_id="ev", capability="standings", source="warehouse",
        observed_at=datetime.now(UTC), season="2025-26", rows={"wins": 61})
    ledger.append(LedgerKind.TOOL_RESULT, turn_id="turn", step_id="facts",
                  call_id="call", data={"status": "ok", "evidence": evidence.model_dump(mode="json")})
    return ledger, evidence


def test_ledger_projects_admitted_evidence_and_attempts():
    ledger, evidence = ledger_with_attempt()
    assert admitted_evidence(ledger.entries) == [evidence]
    assert tool_attempts(ledger.entries) == [{
        "call_id": "call", "name": "standings", "args": {"season": "2025-26"},
        "status": "ok", "error": None}]


def test_replay_projection_excludes_prompts_questions_and_answers():
    ledger, _ = ledger_with_attempt()
    payload = replay_turn(ledger.entries)
    text = str(payload).casefold()
    assert set(payload) == {"evidence", "tools"}
    assert all(word not in text for word in ("prompt", "question", "answer", "transcript"))


def test_successful_tool_projection_rejects_missing_or_extra_evidence_fields():
    import pytest

    def ledger_with_result(data):
        ledger = RunLedger("run")
        ledger.append(LedgerKind.TOOL_CALL, turn_id="turn", step_id="facts",
                      call_id="call", data={"name": "standings", "args": {}})
        ledger.append(LedgerKind.TOOL_RESULT, turn_id="turn", step_id="facts",
                      call_id="call", data=data)
        return ledger

    missing = ledger_with_result({"status": "ok"})
    with pytest.raises(ValueError, match="unexpected fields"):
        admitted_evidence(missing.entries)

    _, evidence = ledger_with_attempt()
    extra = ledger_with_result({
        "status": "ok", "evidence": evidence.model_dump(mode="json"),
        "unverified": True,
    })
    with pytest.raises(ValueError, match="unexpected fields"):
        admitted_evidence(extra.entries)


def test_tool_attempt_projection_rejects_partial_call_and_status() -> None:
    import pytest

    ledger = RunLedger("run")
    ledger.append(LedgerKind.TOOL_CALL, turn_id="turn", call_id="call",
                  data={"name": "standings", "args": {}, "label": "extra"})
    ledger.append(LedgerKind.TOOL_RESULT, turn_id="turn", call_id="call",
                  data={"status": "ok", "evidence": {}})
    with pytest.raises(ValueError, match="tool call has unexpected fields"):
        tool_attempts(ledger.entries)

    ledger = RunLedger("run")
    ledger.append(LedgerKind.TOOL_CALL, turn_id="turn", call_id="call",
                  data={"name": "standings", "args": {}})
    ledger.append(LedgerKind.TOOL_RESULT, turn_id="turn", call_id="call",
                  data={"status": "success"})
    with pytest.raises(ValueError, match="status must be ok or failed"):
        tool_attempts(ledger.entries)

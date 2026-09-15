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

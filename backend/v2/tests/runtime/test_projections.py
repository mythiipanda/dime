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
    from v2.runtime.ledger import LedgerEntry

    def entries_with_result(data):
        call = LedgerEntry(
            sequence=1, run_id="run", kind="tool/call", recorded_at=datetime.now(UTC),
            turn_id="turn", call_id="call", data={"name": "standings", "args": {}},
        )
        result = LedgerEntry(
            sequence=2, run_id="run", kind="tool/result", recorded_at=datetime.now(UTC),
            turn_id="turn", call_id="call", data=data,
        )
        return [call, result]

    with pytest.raises(ValueError, match="does not match its status"):
        admitted_evidence(entries_with_result({"status": "ok"}))

    _, evidence = ledger_with_attempt()
    with pytest.raises(ValueError, match="does not match its status"):
        admitted_evidence(entries_with_result({
            "status": "ok", "evidence": evidence.model_dump(mode="json"),
            "unverified": True,
        }))


def test_tool_attempt_projection_rejects_partial_call_and_status() -> None:
    import pytest

    from v2.runtime.ledger import LedgerEntry

    call = LedgerEntry(
        sequence=1, run_id="run", kind="tool/call", recorded_at=datetime.now(UTC), turn_id="turn",
        call_id="call", data={"name": "standings", "args": {}, "label": "extra"},
    )
    result = LedgerEntry(
        sequence=2, run_id="run", kind="tool/result", recorded_at=datetime.now(UTC),
        turn_id="turn", call_id="call", data={"status": "ok", "evidence": {}},
    )
    with pytest.raises(ValueError, match="tool call has unexpected fields"):
        tool_attempts([call, result])

    call = LedgerEntry(
        sequence=1, run_id="run", kind="tool/call", recorded_at=datetime.now(UTC),
        turn_id="turn", call_id="call", data={"name": "standings", "args": {}},
    )
    bad_status = LedgerEntry(
        sequence=2, run_id="run", kind="tool/result", recorded_at=datetime.now(UTC),
        turn_id="turn", call_id="call", data={"status": "success"},
    )
    with pytest.raises(ValueError, match="status must be ok or failed"):
        tool_attempts([call, bad_status])


def test_admitted_evidence_rejects_conflicting_duplicate_identity() -> None:
    import pytest

    ledger, evidence = ledger_with_attempt()
    duplicate = ledger.entries[-1].model_copy(update={
        "sequence": 3,
        "data": {"status": "ok", "evidence": evidence.model_copy(
            update={"rows": {"wins": 55}}).model_dump(mode="json")},
    })
    with pytest.raises(ValueError, match="multiple results"):
        admitted_evidence([*ledger.entries, duplicate])

    identical = ledger.entries[-1].model_copy(update={"sequence": 3})
    with pytest.raises(ValueError, match="multiple results"):
        admitted_evidence([*ledger.entries, identical])


def test_tool_attempt_projection_rejects_orphan_conflict_and_duplicate_result() -> None:
    import pytest
    from v2.runtime.ledger import LedgerEntry

    now = datetime.now(UTC)
    call = LedgerEntry(sequence=1, run_id="run", kind="tool/call",
        recorded_at=now, turn_id="turn", call_id="call",
        data={"name": "standings", "args": {}})
    result = LedgerEntry(sequence=2, run_id="run", kind="tool/result",
        recorded_at=now, turn_id="turn", call_id="call",
        data={"status": "failed", "error": "down"})
    with pytest.raises(ValueError, match="recorded call"):
        tool_attempts([result])
    conflicting = call.model_copy(update={"sequence": 2,
        "data": {"name": "ratings", "args": {}}})
    with pytest.raises(ValueError, match="conflicting payloads"):
        tool_attempts([call, conflicting, result.model_copy(update={"sequence": 3})])
    with pytest.raises(ValueError, match="multiple results"):
        tool_attempts([call, result, result.model_copy(update={"sequence": 3})])


def test_admitted_evidence_rejects_orphan_successful_result() -> None:
    import pytest
    from v2.runtime.ledger import LedgerEntry

    _, evidence = ledger_with_attempt()
    result = LedgerEntry(
        sequence=1, run_id="run", kind="tool/result", recorded_at=datetime.now(UTC),
        turn_id="turn", call_id="missing",
        data={"status": "ok", "evidence": evidence.model_dump(mode="json")},
    )
    with pytest.raises(ValueError, match="requires its recorded call"):
        admitted_evidence([result])


def test_tool_attempt_projection_rejects_malformed_result_payloads() -> None:
    import pytest
    from v2.runtime.ledger import LedgerEntry

    now = datetime.now(UTC)
    call = LedgerEntry(
        sequence=1, run_id="run", kind="tool/call", recorded_at=now,
        turn_id="turn", call_id="call", data={"name": "standings", "args": {}},
    )
    failed = LedgerEntry(
        sequence=2, run_id="run", kind="tool/result", recorded_at=now,
        turn_id="turn", call_id="call", data={"status": "failed"},
    )
    with pytest.raises(ValueError, match="does not match its status"):
        tool_attempts([call, failed])


def test_projections_revalidate_copied_ledger_entries() -> None:
    import pytest
    from pydantic import ValidationError
    ledger, _ = ledger_with_attempt()
    invalid = ledger.entries[0].model_copy(update={"sequence": True})
    with pytest.raises(ValidationError):
        tool_attempts([invalid, ledger.entries[1]])

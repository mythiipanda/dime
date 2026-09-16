from pathlib import Path

import pytest

from v2.runtime.ledger import (
    FileLedger,
    LedgerKind,
    RequestEnvelope,
    RunLedger,
    TerminalReason,
)


def test_request_envelope_hashes_exact_model_inputs() -> None:
    first = RequestEnvelope.freeze(
        provider="free", model="model", route="prediction", prompt="p",
        context={"q": "predict"}, tool_schemas=[{"name": "prediction"}],
        planner_version="v2", budgets={"seconds": 10},
    )
    same = RequestEnvelope.freeze(
        provider="free", model="model", route="prediction", prompt="p",
        context={"q": "predict"}, tool_schemas=[{"name": "prediction"}],
        planner_version="v2", budgets={"seconds": 10},
    )
    changed = RequestEnvelope.freeze(
        provider="free", model="model", route="preview", prompt="p",
        context={"q": "predict"}, tool_schemas=[{"name": "prediction"}],
        planner_version="v2", budgets={"seconds": 10},
    )
    assert first == same
    assert first != changed
    with pytest.raises(Exception):
        first.route = "other"


def test_tool_call_identity_is_immutable() -> None:
    ledger = RunLedger("run")
    ledger.append(LedgerKind.TOOL_CALL, turn_id="t", step_id="s", call_id="c",
                  data={"name": "prediction", "args": {"a": "BOS"}})
    ledger.append(LedgerKind.TOOL_RESULT, turn_id="t", step_id="s", call_id="c",
                  data={"status": "ok", "value": {"win_probability": 0.548}})
    with pytest.raises(ValueError, match="cannot change"):
        ledger.append(LedgerKind.TOOL_CALL, turn_id="t", step_id="s", call_id="c",
                      data={"name": "prediction", "args": {"a": "NYK"}})
    with pytest.raises(ValueError, match="earlier tool call"):
        ledger.append(LedgerKind.TOOL_RESULT, turn_id="t", call_id="missing",
                      data={"status": "ok"})


def test_failed_attempts_remain_in_log_but_not_model_history() -> None:
    ledger = RunLedger("run")
    ledger.append(LedgerKind.ASSISTANT_ATTEMPT, turn_id="t",
                  data={"status": "rejected", "text": "unsupported"})
    ledger.append(LedgerKind.ASSISTANT_ATTEMPT, turn_id="t",
                  data={"status": "accepted", "text": "grounded"})
    assert len(ledger.entries) == 2
    assert ledger.model_history("t") == [{"status": "accepted", "text": "grounded"}]


def test_interrupted_run_gets_explicit_terminal_closers() -> None:
    ledger = RunLedger("run")
    ledger.append(LedgerKind.TURN_START, turn_id="t")
    ledger.append(LedgerKind.STEP_START, turn_id="t", step_id="planner")
    ledger.close_interrupted("t", TerminalReason.CANCELLED)
    assert [entry.kind for entry in ledger.entries[-2:]] == [
        LedgerKind.STEP_END, LedgerKind.TURN_END,
    ]
    assert ledger.entries[-1].data == {"reason": "cancelled"}


def test_file_ledger_is_append_only_and_reloadable(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    file = FileLedger(path, "run")
    file.append(LedgerKind.TURN_START, turn_id="t")
    file.append(LedgerKind.TURN_END, turn_id="t", data={"reason": "complete"})
    loaded = FileLedger(path, "run")
    assert loaded.ledger.entries == file.ledger.entries
    assert [entry.sequence for entry in loaded.ledger.entries] == [1, 2]


def test_file_ledger_exposes_runtime_surface(tmp_path: Path) -> None:
    file = FileLedger(tmp_path / "run.jsonl", "run")
    file.append(LedgerKind.TURN_START, turn_id="t")
    assert file.run_id == "run"
    assert len(file.entries) == 1


def test_ledger_contracts_reject_unknown_fields() -> None:
    from datetime import UTC, datetime
    from pydantic import ValidationError
    from v2.runtime.ledger import LedgerEntry

    with pytest.raises(ValidationError, match="extra_field"):
        RequestEnvelope.model_validate({
            "provider": "free", "model": "model", "route": "answer",
            "prompt_hash": "p", "context_hash": "c", "tool_schema_hash": "t",
            "planner_version": "v2", "extra_field": True,
        })
    with pytest.raises(ValidationError, match="extra_field"):
        LedgerEntry.model_validate({
            "sequence": 1, "run_id": "run", "kind": "turn/start",
            "recorded_at": datetime.now(UTC), "turn_id": "turn",
            "extra_field": True,
        })

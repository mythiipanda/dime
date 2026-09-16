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
                  data={"status": "ok", "evidence": {"win_probability": 0.548}})
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


def test_tool_call_has_exactly_one_terminal_result() -> None:
    ledger = RunLedger("run")
    ledger.append(LedgerKind.TOOL_CALL, turn_id="t", call_id="c",
                  data={"name": "standings", "args": {}})
    ledger.append(LedgerKind.TOOL_RESULT, turn_id="t", call_id="c",
                  data={"status": "ok", "evidence": {}})
    with pytest.raises(ValueError, match="only one result"):
        ledger.append(LedgerKind.TOOL_RESULT, turn_id="t", call_id="c",
                      data={"status": "failed", "error": "late"})
    with pytest.raises(ValueError, match="cannot follow its result"):
        ledger.append(LedgerKind.TOOL_CALL, turn_id="t", call_id="c",
                      data={"name": "standings", "args": {}})


def test_reloaded_ledger_rejects_duplicate_tool_results() -> None:
    from datetime import UTC, datetime
    from v2.runtime.ledger import LedgerEntry

    call = LedgerEntry(sequence=1, run_id="run", kind="tool/call",
                       recorded_at=datetime.now(UTC), turn_id="t", call_id="c",
                       data={"name": "standings", "args": {}})
    result = LedgerEntry(sequence=2, run_id="run", kind="tool/result",
                         recorded_at=datetime.now(UTC), turn_id="t", call_id="c",
                         data={"status": "ok", "evidence": {}})
    duplicate = result.model_copy(update={"sequence": 3})
    with pytest.raises(ValueError, match="only one result"):
        RunLedger("run", [call, result, duplicate])


def test_ledger_run_identity_must_be_non_empty() -> None:
    with pytest.raises(ValueError, match="run id must be non-empty"):
        RunLedger(" ")


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"turn_id": " "}, "turn id"),
        ({"turn_id": "t", "step_id": " "}, "step id"),
        ({"turn_id": "t", "call_id": " "}, "call id"),
    ],
)
def test_ledger_event_identities_must_be_non_empty(kwargs, error) -> None:
    with pytest.raises(ValueError, match=error):
        RunLedger("run").append(LedgerKind.TURN_START, **kwargs)


@pytest.mark.parametrize(
    "data,error",
    [
        ({"name": "standings"}, "exactly name and args"),
        ({"name": " ", "args": {}}, "name must be non-empty"),
        ({"name": "standings", "args": []}, "args must be an object"),
    ],
)
def test_tool_call_data_shape_is_strict(data, error) -> None:
    with pytest.raises(ValueError, match=error):
        RunLedger("run").append(
            LedgerKind.TOOL_CALL, turn_id="turn", call_id="call", data=data,
        )


@pytest.mark.parametrize(
    "data,error",
    [
        ({"status": "ok"}, "status and evidence object"),
        ({"status": "ok", "evidence": {}, "error": "bad"}, "status and evidence object"),
        ({"status": "failed"}, "non-empty error"),
        ({"status": "failed", "error": " "}, "non-empty error"),
        ({"status": "success"}, "status must be ok or failed"),
    ],
)
def test_tool_result_data_shape_is_strict(data, error) -> None:
    ledger = RunLedger("run")
    ledger.append(LedgerKind.TOOL_CALL, turn_id="turn", call_id="call",
                  data={"name": "standings", "args": {}})
    with pytest.raises(ValueError, match=error):
        ledger.append(LedgerKind.TOOL_RESULT, turn_id="turn", call_id="call", data=data)

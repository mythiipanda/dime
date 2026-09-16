from pathlib import Path
from threading import Event, Thread

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
    envelope = RequestEnvelope.freeze(
        provider="p", model="m", route="answer", prompt="p", context={},
        tool_schemas={}, planner_version="v2")
    for call_id in ("c1", "c2"):
        ledger.append(LedgerKind.MODEL_REQUEST, turn_id="t", call_id=call_id,
                      data=envelope.model_dump(mode="json"))
    ledger.append(LedgerKind.ASSISTANT_ATTEMPT, turn_id="t", call_id="c1",
                  data={"status": "failed", "error": "unsupported"})
    ledger.append(LedgerKind.ASSISTANT_ATTEMPT, turn_id="t", call_id="c2",
                  data={"status": "accepted", "output": {"text": "grounded"},
                        "provider": "p", "model": "m", "used_fallback": False})
    assert len(ledger.entries) == 4
    assert ledger.model_history("t") == [{
        "status": "accepted", "output": {"text": "grounded"},
        "provider": "p", "model": "m", "used_fallback": False,
    }]


def test_interrupted_run_gets_explicit_terminal_closers() -> None:
    ledger = RunLedger("run")
    ledger.append(LedgerKind.TURN_START, turn_id="t", data={"request": "q"})
    ledger.append(LedgerKind.STEP_START, turn_id="t", step_id="planner")
    ledger.close_interrupted("t", TerminalReason.CANCELLED)
    assert [entry.kind for entry in ledger.entries[-2:]] == [
        LedgerKind.STEP_END, LedgerKind.TURN_END,
    ]
    assert ledger.entries[-1].data == {"reason": "cancelled"}


def test_file_ledger_is_append_only_and_reloadable(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    file = FileLedger(path, "run")
    file.append(LedgerKind.TURN_START, turn_id="t", data={"request": "q"})
    file.append(LedgerKind.TURN_END, turn_id="t", data={"reason": "complete"})
    loaded = FileLedger(path, "run")
    assert loaded.ledger.entries == file.ledger.entries
    assert [entry.sequence for entry in loaded.ledger.entries] == [1, 2]


def test_file_ledger_exposes_runtime_surface(tmp_path: Path) -> None:
    file = FileLedger(tmp_path / "run.jsonl", "run")
    file.append(LedgerKind.TURN_START, turn_id="t", data={"request": "q"})
    assert file.run_id == "run"
    assert len(file.entries) == 1


def test_ledger_contracts_reject_unknown_fields() -> None:
    from datetime import UTC, datetime
    from pydantic import ValidationError
    from v2.runtime.ledger import LedgerEntry

    with pytest.raises(ValidationError, match="extra_field"):
        RequestEnvelope.model_validate({
            "provider": "free", "model": "model", "route": "answer",
            "prompt_hash": "a" * 64, "context_hash": "b" * 64,
            "tool_schema_hash": "c" * 64,
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
        RunLedger("run").append(LedgerKind.TURN_START, data={"request": "q"}, **kwargs)


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


def test_reloaded_ledger_rejects_invalid_turn_and_step_order() -> None:
    from datetime import UTC, datetime
    from v2.runtime.ledger import LedgerEntry

    def entry(sequence, kind, *, step_id=None):
        data = ({"reason": "complete"}
                if kind in ("step/end", "turn/end")
                else {"request": "q"} if kind == "turn/start" else {})
        return LedgerEntry(
            sequence=sequence, run_id="run", kind=kind,
            recorded_at=datetime.now(UTC), turn_id="turn", step_id=step_id,
            data=data,
        )

    with pytest.raises(ValueError, match="open turn"):
        RunLedger("run", [entry(1, "turn/end")])
    with pytest.raises(ValueError, match="open step"):
        RunLedger("run", [entry(1, "turn/start"), entry(2, "step/end", step_id="plan")])
    with pytest.raises(ValueError, match="open steps"):
        RunLedger("run", [entry(1, "turn/start"), entry(2, "step/start", step_id="plan"),
                          entry(3, "turn/end")])
    with pytest.raises(ValueError, match="follow turn end"):
        RunLedger("run", [entry(1, "turn/start"), entry(2, "turn/end"),
                          entry(3, "assistant/attempt")])


def test_live_ledger_enforces_turn_and_step_lifecycle() -> None:
    ledger = RunLedger("run")
    with pytest.raises(ValueError, match="open turn"):
        ledger.append(LedgerKind.TURN_END, turn_id="turn", data={"reason": "complete"})
    ledger.append(LedgerKind.TURN_START, turn_id="turn", data={"request": "q"})
    ledger.append(LedgerKind.STEP_START, turn_id="turn", step_id="plan")
    with pytest.raises(ValueError, match="open steps"):
        ledger.append(LedgerKind.TURN_END, turn_id="turn", data={"reason": "complete"})
    ledger.append(LedgerKind.STEP_END, turn_id="turn", step_id="plan",
                  data={"reason": "complete"})
    ledger.append(LedgerKind.TURN_END, turn_id="turn", data={"reason": "complete"})
    with pytest.raises(ValueError, match="follow turn end"):
        ledger.append(LedgerKind.ASSISTANT_ATTEMPT, turn_id="turn")


def test_reloaded_ledger_rejects_blank_event_identity() -> None:
    from datetime import UTC, datetime
    from v2.runtime.ledger import LedgerEntry

    entry = LedgerEntry(
        sequence=1, run_id="run", kind="turn/start", recorded_at=datetime.now(UTC),
        turn_id=" ",
    )
    with pytest.raises(ValueError, match="turn id must be non-empty"):
        RunLedger("run", [entry])


def test_reloaded_ledger_rejects_malformed_tool_payload() -> None:
    from datetime import UTC, datetime
    from v2.runtime.ledger import LedgerEntry

    call = LedgerEntry(
        sequence=1, run_id="run", kind="tool/call", recorded_at=datetime.now(UTC),
        turn_id="turn", call_id="call", data={"name": "standings"},
    )
    with pytest.raises(ValueError, match="exactly name and args"):
        RunLedger("run", [call])


@pytest.mark.parametrize("field", ["provider", "model", "route", "planner_version"])
def test_request_envelope_requires_nonempty_identity(field) -> None:
    values = {
        "provider": "provider", "model": "model", "route": "answer",
        "prompt": "prompt", "context": {}, "tool_schemas": {},
        "planner_version": "v2",
    }
    values[field] = " "
    with pytest.raises(ValueError, match=field):
        RequestEnvelope.freeze(**values)


def test_request_envelope_loaded_contract_validates_identity_and_maps() -> None:
    with pytest.raises(Exception, match="prompt_hash"):
        RequestEnvelope.model_validate({
            "provider": "p", "model": "m", "route": "r", "prompt_hash": " ",
            "context_hash": "b" * 64, "tool_schema_hash": "c" * 64,
            "planner_version": "v2",
        })
    with pytest.raises(Exception, match="budget keys"):
        RequestEnvelope.model_validate({
            "provider": "p", "model": "m", "route": "r", "prompt_hash": "a" * 64,
            "context_hash": "b" * 64, "tool_schema_hash": "c" * 64,
            "planner_version": "v2",
            "budgets": {" ": 1},
        })


@pytest.mark.parametrize("kind", [LedgerKind.MODEL_REQUEST, LedgerKind.ASSISTANT_ATTEMPT])
def test_model_call_events_require_call_id(kind) -> None:
    with pytest.raises(ValueError, match="require call_id"):
        RunLedger("run").append(kind, turn_id="turn", data={})


def test_model_request_attempt_pairing_is_strict() -> None:
    envelope = RequestEnvelope.freeze(
        provider="p", model="m", route="answer", prompt="p", context={},
        tool_schemas={}, planner_version="v2")
    ledger = RunLedger("run")
    with pytest.raises(ValueError, match="earlier model request"):
        ledger.append(LedgerKind.ASSISTANT_ATTEMPT, turn_id="t", call_id="m1",
                      data={"status": "failed", "error": "bad"})
    ledger.append(LedgerKind.MODEL_REQUEST, turn_id="t", call_id="m1",
                  data=envelope.model_dump(mode="json"))
    ledger.append(LedgerKind.ASSISTANT_ATTEMPT, turn_id="t", call_id="m1",
                  data={"status": "failed", "error": "bad"})
    with pytest.raises(ValueError, match="only one assistant attempt"):
        ledger.append(LedgerKind.ASSISTANT_ATTEMPT, turn_id="t", call_id="m1",
                      data={"status": "accepted", "output": {}, "provider": "p",
                            "model": "m", "used_fallback": False})


@pytest.mark.parametrize("data", [
    {"status": "failed", "error": " "},
    {"status": "accepted", "output": {}, "provider": "p", "model": "m"},
    {"status": "rejected", "error": "bad"},
])
def test_assistant_attempt_payload_shape_is_strict(data) -> None:
    envelope = RequestEnvelope.freeze(
        provider="p", model="m", route="answer", prompt="p", context={},
        tool_schemas={}, planner_version="v2")
    ledger = RunLedger("run")
    ledger.append(LedgerKind.MODEL_REQUEST, turn_id="t", call_id="m1",
                  data=envelope.model_dump(mode="json"))
    with pytest.raises(ValueError, match="assistant attempt"):
        ledger.append(LedgerKind.ASSISTANT_ATTEMPT, turn_id="t", call_id="m1", data=data)


@pytest.mark.parametrize("kind", [LedgerKind.STEP_START, LedgerKind.STEP_END])
def test_step_events_require_step_identity(kind) -> None:
    with pytest.raises(ValueError, match="require step_id"):
        RunLedger("run").append(kind, turn_id="turn")


@pytest.mark.parametrize("kind", [LedgerKind.TURN_START, LedgerKind.TURN_END])
def test_turn_events_reject_step_identity(kind) -> None:
    ledger = RunLedger("run")
    if kind == LedgerKind.TURN_END:
        ledger.append(LedgerKind.TURN_START, turn_id="turn", data={"request": "q"})
    with pytest.raises(ValueError, match="cannot carry step_id"):
        ledger.append(kind, turn_id="turn", step_id="bad",
                      data=({"reason": "complete"} if kind == LedgerKind.TURN_END
                            else {"request": "q"}))


@pytest.mark.parametrize("kind,kwargs", [
    (LedgerKind.STEP_END, {"step_id": "plan"}),
    (LedgerKind.TURN_END, {}),
])
def test_terminal_ledger_events_require_reason(kind, kwargs) -> None:
    ledger = RunLedger("run")
    ledger.append(LedgerKind.TURN_START, turn_id="turn", data={"request": "q"})
    if kind == LedgerKind.STEP_END:
        ledger.append(LedgerKind.STEP_START, turn_id="turn", step_id="plan")
    with pytest.raises(ValueError, match="valid reason"):
        ledger.append(kind, turn_id="turn", **kwargs)


@pytest.mark.parametrize("data", [{}, {"request": " "}, {"request": "q", "extra": True}])
def test_turn_start_payload_shape_is_strict(data) -> None:
    with pytest.raises(ValueError, match="non-empty request"):
        RunLedger("run").append(LedgerKind.TURN_START, turn_id="turn", data=data)


def test_step_start_payload_must_be_empty() -> None:
    ledger = RunLedger("run")
    ledger.append(LedgerKind.TURN_START, turn_id="turn", data={"request": "q"})
    with pytest.raises(ValueError, match="must be empty"):
        ledger.append(LedgerKind.STEP_START, turn_id="turn", step_id="plan",
                      data={"request": "q"})


def test_assistant_attempt_identity_matches_request_and_fallback_flag() -> None:
    envelope = RequestEnvelope.freeze(
        provider="p", model="m", route="answer", prompt="p", context={},
        tool_schemas={}, planner_version="v2")
    accepted = {"status": "accepted", "output": {}, "provider": "p",
                "model": "m", "used_fallback": False}
    for call_id, update in [("m1", {"provider": "other"}),
                            ("m2", {"used_fallback": True})]:
        ledger = RunLedger("run")
        ledger.append(LedgerKind.MODEL_REQUEST, turn_id="t", call_id=call_id,
                      data=envelope.model_dump(mode="json"))
        with pytest.raises(ValueError, match="fallback flag"):
            ledger.append(LedgerKind.ASSISTANT_ATTEMPT, turn_id="t", call_id=call_id,
                          data={**accepted, **update})

    ledger = RunLedger("run")
    ledger.append(LedgerKind.MODEL_REQUEST, turn_id="t", call_id="m3",
                  data=envelope.model_dump(mode="json"))
    ledger.append(LedgerKind.ASSISTANT_ATTEMPT, turn_id="t", call_id="m3",
                  data={**accepted, "model": "backup", "used_fallback": True})


def test_unfinished_steps_and_interruption_are_turn_scoped() -> None:
    ledger = RunLedger("run")
    ledger.append(LedgerKind.TURN_START, turn_id="t1", data={"request": "q1"})
    ledger.append(LedgerKind.STEP_START, turn_id="t1", step_id="shared")
    ledger.append(LedgerKind.TURN_START, turn_id="t2", data={"request": "q2"})
    ledger.append(LedgerKind.STEP_START, turn_id="t2", step_id="shared")
    ledger.append(LedgerKind.STEP_END, turn_id="t1", step_id="shared",
                  data={"reason": "complete"})

    assert ledger.unfinished_steps("t1") == set()
    assert ledger.unfinished_steps("t2") == {"shared"}
    ledger.close_interrupted("t2", TerminalReason.CANCELLED)
    assert ledger.entries[-2].turn_id == "t2"
    assert ledger.entries[-2].step_id == "shared"


@pytest.mark.parametrize("value,error", [
    (-1, "finite non-negative"), (float("nan"), "finite non-negative"),
    (float("inf"), "finite non-negative"), (True, "valid integer|valid number"),
])
def test_request_envelope_rejects_invalid_budget_values(value, error) -> None:
    with pytest.raises(Exception, match=error):
        RequestEnvelope.freeze(
            provider="p", model="m", route="answer", prompt="p", context={},
            tool_schemas={}, planner_version="v2", budgets={"seconds": value})


@pytest.mark.parametrize("field", ["prompt_hash", "context_hash", "tool_schema_hash"])
def test_request_envelope_requires_canonical_hashes(field) -> None:
    envelope = RequestEnvelope.freeze(
        provider="p", model="m", route="answer", prompt="p", context={},
        tool_schemas={}, planner_version="v2").model_dump(mode="json")
    envelope[field] = "not-a-hash"
    with pytest.raises(Exception, match="lowercase sha256"):
        RequestEnvelope.model_validate(envelope)


def test_file_ledger_write_failure_does_not_mutate_memory(tmp_path, monkeypatch) -> None:
    file = FileLedger(tmp_path / "run.jsonl", "run")
    original_open = Path.open

    def fail_open(path, *args, **kwargs):
        if path == file.path:
            raise OSError("disk full")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_open)
    with pytest.raises(OSError, match="disk full"):
        file.append(LedgerKind.TURN_START, turn_id="turn", data={"request": "q"})
    assert file.entries == ()


def test_file_ledger_fsyncs_directory_on_creation(tmp_path, monkeypatch) -> None:
    calls = []
    real_fsync = __import__("os").fsync
    def record(fd):
        calls.append(fd)
        return real_fsync(fd)
    monkeypatch.setattr("v2.runtime.ledger.os.fsync", record)
    file = FileLedger(tmp_path / "new" / "run.jsonl", "run")
    file.append(LedgerKind.TURN_START, turn_id="turn", data={"request": "q"})
    assert len(calls) == 2


def test_file_ledger_recovers_only_unterminated_partial_tail(tmp_path) -> None:
    path = tmp_path / "run.jsonl"
    file = FileLedger(path, "run")
    file.append(LedgerKind.TURN_START, turn_id="turn", data={"request": "q"})
    with path.open("a") as handle:
        handle.write('{"sequence":2')
    recovered = FileLedger(path, "run")
    assert len(recovered.entries) == 1
    assert path.read_text().endswith("\n")
    recovered.append(LedgerKind.TURN_END, turn_id="turn",
                     data={"reason": "complete"})
    assert len(FileLedger(path, "run").entries) == 2

    path.write_text(path.read_text() + '{"sequence":3\n')
    with pytest.raises(Exception):
        FileLedger(path, "run")


def test_ledger_tail_recovery_fsyncs_file_and_directory(tmp_path, monkeypatch) -> None:
    path = tmp_path / "run.jsonl"
    path.write_text('{"sequence":1')
    calls = []
    real_fsync = __import__("os").fsync
    def record(fd):
        calls.append(fd)
        return real_fsync(fd)
    monkeypatch.setattr("v2.runtime.ledger.os.fsync", record)
    FileLedger(path, "run")
    assert len(calls) == 2


def test_file_ledger_rejects_blank_records(tmp_path) -> None:
    path = tmp_path / "run.jsonl"
    file = FileLedger(path, "run")
    file.append(LedgerKind.TURN_START, turn_id="turn", data={"request": "q"})
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="blank records"):
        FileLedger(path, "run")


def test_file_ledgers_for_same_path_share_lock_and_refresh_state(tmp_path) -> None:
    path = tmp_path / "run.jsonl"
    first = FileLedger(path, "run")
    second = FileLedger(path, "run")
    assert first._lock is second._lock
    first.append(LedgerKind.TURN_START, turn_id="turn", data={"request": "q"})
    second.append(LedgerKind.TURN_END, turn_id="turn", data={"reason": "complete"})
    assert [entry.sequence for entry in FileLedger(path, "run").entries] == [1, 2]


def test_file_ledger_entries_refresh_after_independent_writer(tmp_path) -> None:
    path = tmp_path / "run.jsonl"
    reader = FileLedger(path, "run")
    writer = FileLedger(path, "run")
    writer.append(
        LedgerKind.TURN_START, turn_id="turn", data={"request": "answer"})
    assert [entry.sequence for entry in reader.entries] == [1]


def test_file_ledger_load_is_serialized_with_same_path_writes(tmp_path) -> None:
    path = tmp_path / "run.jsonl"
    first = FileLedger(path, "run")
    started = Event()
    finished = Event()

    def load() -> None:
        started.set()
        FileLedger(path, "run")
        finished.set()

    with first._lock:
        thread = Thread(target=load)
        thread.start()
        assert started.wait(timeout=1)
        assert not finished.wait(timeout=0.05)
    thread.join(timeout=1)
    assert finished.is_set()


def test_request_envelope_rejects_malformed_skill_hash() -> None:
    with pytest.raises(ValueError, match="skill hashes must be lowercase sha256"):
        RequestEnvelope.freeze(
            provider="p", model="m", route="r", prompt="prompt",
            context={}, tool_schemas={}, planner_version="v2",
            skill_hashes={"trade-analysis": "not-a-hash"},
        )


def test_file_ledger_rejects_symlinked_record(tmp_path) -> None:
    outside = tmp_path / "outside.jsonl"
    outside.write_text("")
    directory = tmp_path / "ledgers"
    directory.mkdir()
    path = directory / "run.jsonl"
    path.symlink_to(outside)
    with pytest.raises(ValueError, match="cannot be a symlink"):
        FileLedger(path, "run")


def test_ledger_entry_requires_timezone_aware_recording_time() -> None:
    from datetime import datetime
    from pydantic import ValidationError
    from v2.runtime.ledger import LedgerEntry

    with pytest.raises(ValidationError, match="recorded_at must include timezone"):
        LedgerEntry(
            sequence=1, run_id="run", kind="turn/start",
            recorded_at=datetime(2026, 9, 15), turn_id="turn",
            data={"request": "answer"},
        )
    from datetime import tzinfo
    class MissingOffset(tzinfo):
        def utcoffset(self, dt):
            return None
    with pytest.raises(ValidationError, match="recorded_at must include timezone"):
        LedgerEntry(
            sequence=1, run_id="run", kind="turn/start",
            recorded_at=datetime(2026, 9, 15, tzinfo=MissingOffset()), turn_id="turn",
            data={"request": "answer"},
        )


def test_run_ledger_rejects_decreasing_timestamps() -> None:
    from datetime import UTC, datetime, timedelta
    from v2.runtime.ledger import LedgerEntry

    later = datetime(2026, 9, 15, tzinfo=UTC)
    entries = [
        LedgerEntry(
            sequence=1, run_id="run", kind="turn/start", recorded_at=later,
            turn_id="turn", data={"request": "answer"},
        ),
        LedgerEntry(
            sequence=2, run_id="run", kind="turn/end",
            recorded_at=later - timedelta(seconds=1), turn_id="turn",
            data={"reason": "complete"},
        ),
    ]
    with pytest.raises(ValueError, match="timestamps must be nondecreasing"):
        RunLedger("run", entries)


def test_run_ledger_clamps_backward_wall_clock(monkeypatch) -> None:
    from datetime import UTC, datetime, timedelta
    import v2.runtime.ledger as ledger_module

    first_time = datetime(2026, 9, 15, tzinfo=UTC)
    times = iter([first_time, first_time - timedelta(seconds=1)])

    class Clock:
        @classmethod
        def now(cls, tz):
            return next(times)

    monkeypatch.setattr(ledger_module, "datetime", Clock)
    ledger = RunLedger("run")
    first = ledger.append(
        LedgerKind.TURN_START, turn_id="turn", data={"request": "answer"})
    second = ledger.append(
        LedgerKind.TURN_END, turn_id="turn", data={"reason": "complete"})
    assert first.recorded_at == second.recorded_at == first_time


def test_file_ledger_rejects_symlinked_parent(tmp_path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    parent = tmp_path / "parent"
    parent.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="parent cannot be a symlink"):
        FileLedger(parent / "run.jsonl", "run")


@pytest.mark.parametrize("value", [True, "1", 1.0])
def test_ledger_sequence_is_a_strict_integer(value) -> None:
    from datetime import UTC, datetime
    from pydantic import ValidationError
    from v2.runtime.ledger import LedgerEntry

    with pytest.raises(ValidationError):
        LedgerEntry(sequence=value, run_id="run", kind="turn/start",
                    recorded_at=datetime.now(UTC), turn_id="turn",
                    data={"request": "question"})


def test_ledger_identity_text_has_hard_limits() -> None:
    from datetime import UTC, datetime
    from pydantic import ValidationError
    from v2.runtime.ledger import LedgerEntry
    with pytest.raises(ValidationError, match="at most 256 characters"):
        LedgerEntry(sequence=1, run_id="x" * 257, kind="turn/start",
                    recorded_at=datetime.now(UTC), turn_id="turn",
                    data={"request": "question"})

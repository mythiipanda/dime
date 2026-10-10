from datetime import UTC, datetime

import pytest

from v2.contracts import EvidenceEnvelope, PlanNode, TaskSpec
from v2.runtime import (
    FileLedger,
    LedgerEntry,
    LedgerKind,
    RecordedCapability,
    RunLedger,
)
from v2.runtime.projections import admitted_evidence, replay_turn, tool_attempts

RECORDED_AT = datetime(2026, 1, 1, tzinfo=UTC)
FAILED_ERROR = "RuntimeError: tool exploded"
ENTRYPOINTS = ("admitted_evidence", "tool_attempts", "replay_turn")
PROJECTIONS = {
    "admitted_evidence": admitted_evidence,
    "tool_attempts": tool_attempts,
    "replay_turn": replay_turn,
}
_ABSENT = object()

def recorded_evidence():
    return EvidenceEnvelope(
        evidence_id="ev", capability="standings", source="fixture",
        observed_at=RECORDED_AT, rows={"wins": 61})

class SuccessCapability:
    name = "standings"
    task_season_scoped = True

    async def execute(self, node, task, evidence):
        return recorded_evidence()

class FailureCapability:
    name = "standings"
    task_season_scoped = True

    async def execute(self, node, task, evidence):
        raise RuntimeError("tool exploded")

async def record(capability, ledger):
    node = PlanNode(
        id="record", description="record", capability_hints=["standings"])
    task = TaskSpec(goal="record", mode="quick", deliverable="text")
    await RecordedCapability(capability, ledger, turn_id="run").execute(
        node, task, [])

def call_entry(sequence=1, call_id="call", data=None):
    return LedgerEntry(
        sequence=sequence, run_id="run", kind=LedgerKind.TOOL_CALL,
        recorded_at=RECORDED_AT, turn_id="turn", call_id=call_id,
        data=data if data is not None
        else {"name": "standings", "args": {"season": "2025-26"}})

def result_entry(sequence, data, call_id="call"):
    return LedgerEntry(
        sequence=sequence, run_id="run", kind=LedgerKind.TOOL_RESULT,
        recorded_at=RECORDED_AT, turn_id="turn", call_id=call_id,
        data=data)

def result_data(status, duration_ms=_ABSENT, extra=None):
    if status == "ok":
        data = {
            "status": "ok",
            "evidence": recorded_evidence().model_dump(mode="json"),
        }
    else:
        data = {"status": "failed", "error": FAILED_ERROR}
    if duration_ms is not _ABSENT:
        data["duration_ms"] = duration_ms
    if extra is not None:
        data.update(extra)
    return data

def attempt(status, duration_ms=_ABSENT, call_id="call"):
    row = {
        "call_id": call_id,
        "name": "standings",
        "args": {"season": "2025-26"},
        "status": status,
        "error": FAILED_ERROR if status == "failed" else None,
    }
    if duration_ms is not _ABSENT:
        row["duration_ms"] = duration_ms
    return row

def reload_from_storage(path, run_id="run"):
    reloaded = FileLedger(path, run_id)
    assert isinstance(reloaded.ledger, RunLedger)
    return reloaded.entries

def persisted_lines(path):
    return [line for line in path.read_text().splitlines() if line.strip()]

def timing_of(data):
    return {
        "value": data["duration_ms"],
        "is_integer": isinstance(data["duration_ms"], int)
        and not isinstance(data["duration_ms"], bool),
    }

@pytest.mark.anyio
async def test_recorded_success_projects_unchanged_after_storage_reload(
        tmp_path):
    path = tmp_path / "run.jsonl"
    ledger = FileLedger(path, "run")
    await record(SuccessCapability(), ledger)
    reloaded = reload_from_storage(path)

    assert reloaded == ledger.ledger.entries
    assert [entry.model_dump_json() for entry in reloaded] == persisted_lines(path)

    call, result = reloaded
    assert (call.kind, result.kind) == (
        LedgerKind.TOOL_CALL, LedgerKind.TOOL_RESULT)
    assert call.call_id == result.call_id and call.call_id.strip()
    assert result.data["status"] == "ok"
    assert "duration_ms" in result.data
    timing = timing_of(result.data)
    assert timing["is_integer"] and timing["value"] >= 0

    evidence = admitted_evidence(reloaded)
    assert evidence == [recorded_evidence()]
    assert evidence[0].model_dump(mode="json") == result.data["evidence"]
    assert evidence[0].rows == {"wins": 61}
    assert evidence[0].capability == "standings"
    assert evidence[0].lineage == []

    attempts = tool_attempts(reloaded)
    assert attempts == [{
        "call_id": call.call_id,
        "name": call.data["name"],
        "args": call.data["args"],
        "status": "ok",
        "error": None,
        "duration_ms": timing["value"],
    }]

    projected = replay_turn(reloaded)
    assert projected == {
        "evidence": [recorded_evidence().model_dump(mode="json")],
        "tools": attempts,
    }

@pytest.mark.anyio
async def test_recorded_failure_projects_unchanged_after_storage_reload(
        tmp_path):
    path = tmp_path / "run.jsonl"
    ledger = FileLedger(path, "run")
    with pytest.raises(RuntimeError, match="tool exploded"):
        await record(FailureCapability(), ledger)
    reloaded = reload_from_storage(path)

    assert reloaded == ledger.ledger.entries
    assert [entry.model_dump_json() for entry in reloaded] == persisted_lines(path)

    call, result = reloaded
    assert (call.kind, result.kind) == (
        LedgerKind.TOOL_CALL, LedgerKind.TOOL_RESULT)
    assert call.call_id == result.call_id and call.call_id.strip()
    assert result.data["status"] == "failed"
    assert result.data["error"] == FAILED_ERROR
    assert "duration_ms" in result.data
    timing = timing_of(result.data)
    assert timing["is_integer"] and timing["value"] >= 0

    assert admitted_evidence(reloaded) == []

    attempts = tool_attempts(reloaded)
    assert attempts == [{
        "call_id": call.call_id,
        "name": call.data["name"],
        "args": call.data["args"],
        "status": "failed",
        "error": FAILED_ERROR,
        "duration_ms": timing["value"],
    }]

    projected = replay_turn(reloaded)
    assert projected == {"evidence": [], "tools": attempts}

def test_legacy_attempts_without_timing_keep_the_existing_shape() -> None:
    ledger = RunLedger("run")
    ledger.append(
        LedgerKind.TOOL_CALL, turn_id="turn", step_id="facts",
        call_id="call-ok",
        data={"name": "standings", "args": {"season": "2025-26"}})
    ledger.append(
        LedgerKind.TOOL_RESULT, turn_id="turn", step_id="facts",
        call_id="call-ok",
        data={"status": "ok",
              "evidence": recorded_evidence().model_dump(mode="json")})
    ledger.append(
        LedgerKind.TOOL_CALL, turn_id="turn", step_id="facts",
        call_id="call-failed",
        data={"name": "standings", "args": {"season": "2025-26"}})
    ledger.append(
        LedgerKind.TOOL_RESULT, turn_id="turn", step_id="facts",
        call_id="call-failed",
        data={"status": "failed", "error": "RuntimeError: legacy outage"})

    assert tool_attempts(ledger.entries) == [
        {"call_id": "call-ok", "name": "standings",
         "args": {"season": "2025-26"}, "status": "ok", "error": None},
        {"call_id": "call-failed", "name": "standings",
         "args": {"season": "2025-26"}, "status": "failed",
         "error": "RuntimeError: legacy outage"},
    ]
    assert admitted_evidence(ledger.entries) == [recorded_evidence()]
    assert replay_turn(ledger.entries) == {
        "evidence": [recorded_evidence().model_dump(mode="json")],
        "tools": tool_attempts(ledger.entries),
    }

MALFORMED_TIMING = [
    ("negative", -1),
    ("boolean_true", True),
    ("boolean_false", False),
    ("string", "7"),
    ("integral_float", 7.0),
    ("nan", float("nan")),
    ("infinity", float("inf")),
    ("none", None),
    ("list", [7]),
    ("object", {"ms": 7}),
]

@pytest.mark.parametrize(
    "label,value", MALFORMED_TIMING, ids=[item[0] for item in MALFORMED_TIMING])
@pytest.mark.parametrize("status", ["ok", "failed"])
@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
def test_projection_entrypoints_reject_malformed_timing(
        entrypoint, status, label, value) -> None:
    entries = [call_entry(), result_entry(2, result_data(
        status, duration_ms=value))]
    with pytest.raises(ValueError, match="non-negative integer"):
        PROJECTIONS[entrypoint](entries)

UNEXPECTED_FIELDS = [
    ("ok", {"rows": []}),
    ("ok", {"error": "boom"}),
    ("ok", {"diagnostic": "extra"}),
    ("failed", {"evidence": {}}),
    ("failed", {"rows": []}),
    ("failed", {"diagnostic": "extra"}),
]

@pytest.mark.parametrize("status,extra", UNEXPECTED_FIELDS)
@pytest.mark.parametrize("timed", [False, True])
@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
def test_projection_entrypoints_reject_unexpected_fields(
        entrypoint, timed, status, extra) -> None:
    entries = [
        call_entry(),
        result_entry(2, result_data(
            status, duration_ms=7 if timed else _ABSENT, extra=extra)),
    ]
    with pytest.raises(ValueError):
        PROJECTIONS[entrypoint](entries)

ACCEPTED_TIMING = [
    ("zero", 0),
    ("typical", 7),
    ("large", 1_000_000_000),
]

@pytest.mark.parametrize(
    "label,value", ACCEPTED_TIMING, ids=[item[0] for item in ACCEPTED_TIMING])
@pytest.mark.parametrize("status", ["ok", "failed"])
@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
def test_projection_entrypoints_accept_nonnegative_integer_timing(
        entrypoint, status, label, value) -> None:
    entries = [call_entry(), result_entry(
        2, result_data(status, duration_ms=value))]
    projected = PROJECTIONS[entrypoint](entries)
    expected_evidence = (
        [recorded_evidence().model_dump(mode="json")] if status == "ok" else [])
    expected_attempt = attempt(status, duration_ms=value)
    if entrypoint == "admitted_evidence":
        assert projected == (
            [recorded_evidence()] if status == "ok" else [])
    elif entrypoint == "tool_attempts":
        assert projected == [expected_attempt]
    else:
        assert projected == {
            "evidence": expected_evidence, "tools": [expected_attempt]}

@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
def test_timed_results_still_reject_duplicate_results(entrypoint) -> None:
    duplicate = [
        call_entry(),
        result_entry(2, result_data("ok", duration_ms=7)),
        result_entry(3, result_data("ok", duration_ms=9)),
    ]
    with pytest.raises(ValueError, match="multiple results"):
        PROJECTIONS[entrypoint](duplicate)

@pytest.mark.parametrize(
    "entrypoint", ["admitted_evidence", "replay_turn"])
def test_timed_results_still_reject_conflicting_evidence(entrypoint) -> None:
    conflicting = [
        call_entry(call_id="call-1"),
        result_entry(2, result_data("ok", duration_ms=7), call_id="call-1"),
        call_entry(3, call_id="call-2"),
        result_entry(4, result_data("ok", duration_ms=9, extra={
            "evidence": recorded_evidence().model_copy(
                update={"rows": {"wins": 55}}).model_dump(mode="json")}),
            call_id="call-2"),
    ]
    with pytest.raises(ValueError, match="conflicting payloads"):
        PROJECTIONS[entrypoint](conflicting)

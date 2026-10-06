from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path

import pytest

from v2.runtime.ledger import (
    FileLedger,
    LedgerKind,
    ReplayMismatchError,
    ReplayThread,
    RequestEnvelope,
    RunLedger,
    replay_entries,
    replay_run,
    turn_content_hash,
)


def _envelope(
    *,
    prompt: str = "ask",
    context=None,
    schema=None,
    strategy: str | None = "strict_schema",
) -> RequestEnvelope:
    return RequestEnvelope.freeze(
        provider="p",
        model="m",
        route="planner",
        prompt=prompt,
        context={"n": 1} if context is None else context,
        tool_schemas={"type": "object"} if schema is None else schema,
        planner_version="v2",
        output_strategy=strategy,
    )


def _attempt_data() -> dict:
    return {
        "status": "accepted",
        "output": {"ok": True},
        "provider": "p",
        "model": "m",
        "used_fallback": False,
    }


def _recorded_turn(ledger: RunLedger, turn_id: str, prompt: str) -> None:
    ledger.append(LedgerKind.TURN_START, turn_id=turn_id, data={"request": prompt})
    ledger.append(
        LedgerKind.STEP_START, turn_id=turn_id, step_id="understand",
    )
    envelope = _envelope(prompt=prompt)
    ledger.append(
        LedgerKind.MODEL_REQUEST,
        turn_id=turn_id,
        call_id=f"model:{turn_id}:1",
        data=envelope.model_dump(mode="json"),
    )
    ledger.append(
        LedgerKind.ASSISTANT_ATTEMPT,
        turn_id=turn_id,
        call_id=f"model:{turn_id}:1",
        data=_attempt_data(),
    )
    ledger.append(
        LedgerKind.STEP_END,
        turn_id=turn_id,
        step_id="understand",
        data={"reason": "complete"},
    )
    ledger.append(
        LedgerKind.TURN_END, turn_id=turn_id, data={"reason": "complete"},
    )


def test_recorded_run_replays_to_byte_identical_model_inputs() -> None:
    ledger = RunLedger("run")
    _recorded_turn(ledger, "t1", "ask-one")
    _recorded_turn(ledger, "t2", "ask-two")
    thread = replay_entries(ledger.entries)
    assert isinstance(thread, ReplayThread)
    assert [turn.turn_id for turn in thread.turns] == ["t1", "t2"]
    first = thread.turns[0].items[0]
    assert first.prompt_bytes == "ask-one".encode()
    assert first.context_bytes == json.dumps(
        {"n": 1}, sort_keys=True, separators=(",", ":"),
    ).encode()
    assert first.schema_bytes == json.dumps(
        {"type": "object"}, sort_keys=True, separators=(",", ":"),
    ).encode()
    assert first.output_strategy == "strict_schema"
    assert thread.turns[0].content_hash == turn_content_hash(ledger.entries, "t1")
    assert thread.turns[1].items[0].prompt_bytes == "ask-two".encode()


def test_replay_verifies_hashes_instead_of_trusting_them() -> None:
    ledger = RunLedger("run")
    _recorded_turn(ledger, "t1", "ask-one")
    entries = list(ledger.entries)
    raw = next(
        entry.model_dump(mode="json")
        for entry in entries
        if entry.kind == LedgerKind.MODEL_REQUEST
    )
    raw["data"] = {**raw["data"], "prompt_text": "tampered"}
    from v2.runtime.ledger import LedgerEntry

    entries = [
        LedgerEntry.model_validate(raw)
        if entry.kind == LedgerKind.MODEL_REQUEST
        else entry
        for entry in entries
    ]
    with pytest.raises(ReplayMismatchError, match="t1"):
        replay_entries(entries)


def test_replay_needs_no_live_state_network_or_warehouse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = (
        Path(__file__).parent / "fixtures" / "model_replay_run.jsonl"
    )
    target = tmp_path / "model_replay_run.jsonl"
    target.write_bytes(fixture.read_bytes())

    def blocked(*args, **kwargs):
        raise AssertionError("network is unavailable during replay")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.delitem(__import__("sys").modules, "shared.store", raising=False)
    thread = replay_run(str(tmp_path), "model_replay_run")
    assert [turn.turn_id for turn in thread.turns] == ["t1", "t2"]
    assert all(item.prompt_bytes for turn in thread.turns for item in turn.items)


def test_replay_script_from_file_verifies_every_turn_in_order(
    tmp_path: Path,
) -> None:
    ledger = RunLedger("run")
    _recorded_turn(ledger, "t1", "ask-one")
    _recorded_turn(ledger, "t2", "ask-two")
    path = tmp_path / "run.jsonl"
    file_ledger = FileLedger(path, "run")
    for entry in ledger.entries:
        file_ledger.append(
            entry.kind,
            turn_id=entry.turn_id,
            step_id=entry.step_id,
            call_id=entry.call_id,
            data=dict(entry.data),
        )
    thread = replay_run(str(tmp_path), "run")
    assert [turn.turn_id for turn in thread.turns] == ["t1", "t2"]
    assert sum(len(turn.items) for turn in thread.turns) == 2


def test_tampered_file_entry_fails_loudly_naming_the_turn(
    tmp_path: Path,
) -> None:
    ledger = RunLedger("run")
    _recorded_turn(ledger, "t1", "ask-one")
    path = tmp_path / "run.jsonl"
    file_ledger = FileLedger(path, "run")
    for entry in ledger.entries:
        file_ledger.append(
            entry.kind,
            turn_id=entry.turn_id,
            step_id=entry.step_id,
            call_id=entry.call_id,
            data=dict(entry.data),
        )
    lines = path.read_text().splitlines()
    target = next(
        index
        for index, line in enumerate(lines)
        if json.loads(line)["kind"] == "model/request"
    )
    payload = json.loads(lines[target])
    payload["data"]["prompt_text"] = "tampered"
    lines[target] = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ReplayMismatchError, match="t1"):
        replay_run(str(tmp_path), "run")


def test_envelope_without_byte_sources_still_replays_by_hash() -> None:
    envelope = RequestEnvelope.freeze(
        provider="p",
        model="m",
        route="planner",
        prompt="ask",
        context={"n": 1},
        tool_schemas={"type": "object"},
        planner_version="v2",
    )
    assert envelope.prompt_text == "ask"
    assert hashlib.sha256(envelope.prompt_text.encode()).hexdigest() == envelope.prompt_hash

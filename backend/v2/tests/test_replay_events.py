from __future__ import annotations

import pytest

from v2.api.events import (
    ReplayVerification,
    replay_mismatch_report,
    replay_verification_for,
)
from v2.api.sse import encode_replay_verification


def test_replay_report_carries_hashes_but_no_prompt_bytes() -> None:
    report = ReplayVerification(
        run_id="run-abc",
        status="verified",
        turn_count=2,
        item_count=2,
        content_hashes={"t1": "a" * 64, "t2": "b" * 64},
    )
    chunk = encode_replay_verification(report)
    assert "ask-one" not in chunk
    assert "t1" in chunk and "verified" in chunk


def test_replay_mismatch_report_names_the_turn() -> None:
    report = ReplayVerification(
        run_id="run-abc",
        status="mismatch",
        turn_count=2,
        item_count=2,
        content_hashes={"t1": "a" * 64},
        mismatched_turn="t2",
    )
    chunk = encode_replay_verification(report)
    assert "t2" in chunk


def test_replay_report_rejects_malformed_hashes() -> None:
    with pytest.raises(Exception, match="sha256"):
        ReplayVerification(
            run_id="run-abc",
            status="verified",
            turn_count=1,
            item_count=1,
            content_hashes={"t1": "not-a-hash"},
        )
    with pytest.raises(Exception, match="mismatched_turn"):
        ReplayVerification(
            run_id="run-abc",
            status="verified",
            turn_count=1,
            item_count=1,
            content_hashes={"t1": "a" * 64},
            mismatched_turn="t1",
        )


def test_replay_helpers_build_reports_from_threads() -> None:
    from v2.runtime.ledger import replay_entries, RunLedger, LedgerKind

    ledger = RunLedger("run")
    ledger.append(LedgerKind.TURN_START, turn_id="t1", data={"request": "ask"})
    from v2.runtime.ledger import RequestEnvelope

    envelope = RequestEnvelope.freeze(
        provider="p", model="m", route="planner", prompt="ask",
        context={"n": 1}, tool_schemas={"type": "object"},
        planner_version="v2", output_strategy="strict_schema")
    ledger.append(
        LedgerKind.MODEL_REQUEST, turn_id="t1", call_id="model:t1:1",
        data=envelope.model_dump(mode="json"))
    thread = replay_entries(ledger.entries)
    report = replay_verification_for("run", thread)
    assert report.status == "verified" and report.item_count == 1
    assert encode_replay_verification(report).startswith(
        "event: replay_verification\n")
    mismatch = replay_mismatch_report("run", "t1")
    assert mismatch.status == "mismatch" and mismatch.mismatched_turn == "t1"

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

from pathlib import Path

import pytest
from pydantic import ValidationError

from v2.runtime.policy import ExecutionMode, ExecutionPolicy


def test_execution_modes_share_one_policy_contract(tmp_path):
    live = ExecutionPolicy.live(ledger_dir=tmp_path / "ledger")
    shadow = ExecutionPolicy.shadow(ledger_dir=tmp_path / "shadow")
    evaluation = ExecutionPolicy.evaluation()
    replay = ExecutionPolicy.replay(tmp_path / "turn.json")
    assert [item.mode for item in (live, shadow, evaluation, replay)] == [
        ExecutionMode.LIVE, ExecutionMode.SHADOW,
        ExecutionMode.EVAL, ExecutionMode.REPLAY]
    assert live.publish
    assert not shadow.publish and not evaluation.publish and not replay.publish


def test_non_live_modes_never_publish_and_replay_requires_fixture():
    with pytest.raises(ValidationError, match="shadow mode cannot publish"):
        ExecutionPolicy(mode="shadow", publish=True)
    with pytest.raises(ValidationError, match="replay mode requires replay_path"):
        ExecutionPolicy(mode="replay", publish=False)


def test_non_live_modes_cannot_be_constructed_as_publishable() -> None:
    for mode in (ExecutionMode.SHADOW, ExecutionMode.EVAL, ExecutionMode.REPLAY):
        kwargs = {"replay_path": "fixture.jsonl"} if mode == ExecutionMode.REPLAY else {}
        with pytest.raises(ValidationError, match=f"{mode.value} mode cannot publish"):
            ExecutionPolicy(mode=mode, publish=True, **kwargs)


def test_policy_rejects_unknown_configuration_fields() -> None:
    with pytest.raises(Exception, match="publsh"):
        ExecutionPolicy.model_validate({
            "mode": "live", "publish": True, "publsh": False,
        })

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


def test_replay_path_is_rejected_outside_replay_mode() -> None:
    with pytest.raises(ValidationError, match="only in replay mode"):
        ExecutionPolicy(mode="live", replay_path="fixture.json", publish=True)


def test_policy_rejects_symlinked_storage_roots(tmp_path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    for field_name in ("ledger_dir", "checkpoint_dir"):
        with pytest.raises(ValidationError, match=f"{field_name} cannot be a symlink"):
            ExecutionPolicy(mode="live", **{field_name: link})


def test_policy_rejects_symlinked_replay_fixture(tmp_path) -> None:
    target = tmp_path / "fixture.json"
    target.write_text("{}")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(ValidationError, match="replay_path cannot be a symlink"):
        ExecutionPolicy(mode="replay", replay_path=link, publish=False)


@pytest.mark.parametrize("field_name", ["ledger_dir", "checkpoint_dir", "replay_path"])
def test_policy_rejects_symlinked_path_ancestors(tmp_path, field_name) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    parent = tmp_path / "parent"
    parent.symlink_to(outside, target_is_directory=True)
    path = parent / ("fixture.json" if field_name == "replay_path" else "storage")
    kwargs = {field_name: path}
    if field_name == "replay_path":
        kwargs.update(mode="replay", publish=False)
    else:
        kwargs.update(mode="live")
    with pytest.raises(ValidationError, match=f"{field_name} parent cannot be a symlink"):
        ExecutionPolicy(**kwargs)


@pytest.mark.parametrize("field_name", ["max_concurrency", "max_failures", "repair_attempts"])
@pytest.mark.parametrize("value", [True, "1", 1.0])
def test_policy_operational_limits_are_strict_integers(field_name, value) -> None:
    with pytest.raises(ValidationError):
        ExecutionPolicy(mode="live", **{field_name: value})

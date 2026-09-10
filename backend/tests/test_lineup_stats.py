"""Hermetic tests for get_lineup_stats sample floors. No network, no LLM.

Sample floors are the whole point of the tool: units under the possession
floor are hidden by default, surfaced only with an explicit override plus
warnings, and blowout-heavy units are flagged. These tests pin that behavior
on the pure functions so the floor can never silently regress.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import tools
from app.tools.lineup import (
    _apply_sample_floor,
    _flags,
    _ratings,
    get_lineup_stats,
)


def _units():
    return [
        {"GROUP_NAME": "starters", "poss": 420, "flags": []},
        {"GROUP_NAME": "bench mob", "poss": 120, "flags": []},
        {"GROUP_NAME": "40-min wonder", "poss": 80, "flags": []},
    ]


def test_ratings_per_100_possessions():
    r = _ratings(100.0, 100, 95.0, 100)
    assert r["OFF_RATING"] == 100.0
    assert r["DEF_RATING"] == 95.0
    assert r["NET_RATING"] == 5.0


def test_ratings_zero_possessions_no_crash():
    r = _ratings(10.0, 0, 8.0, 0)
    assert r == {"OFF_RATING": 0.0, "DEF_RATING": 0.0, "NET_RATING": 0.0}


def test_sample_floor_hides_under_100_by_default():
    visible, hidden, warning = _apply_sample_floor(_units(), 100, False)
    names = [u["GROUP_NAME"] for u in visible]
    assert names == ["starters", "bench mob"]
    assert "40-min wonder" not in names
    assert hidden == 1
    assert "1 unit(s)" in warning
    assert "include_small=True" in warning


def test_sample_floor_override_shows_with_warnings():
    visible, hidden, warning = _apply_sample_floor(_units(), 100, True)
    small = next(u for u in visible if u["GROUP_NAME"] == "40-min wonder")
    assert small["signal"] == "not-trustworthy"
    assert any("tiny-sample" in f for f in small["flags"])
    assert hidden == 1
    assert "include_small=True" not in warning


def test_sample_floor_respects_custom_threshold():
    visible, hidden, _ = _apply_sample_floor(_units(), 400, False)
    assert [u["GROUP_NAME"] for u in visible] == ["starters"]
    assert hidden == 2


def test_blowout_heavy_flagged():
    flags = _flags(200, 0.6, 100, estimated=False)
    assert any("blowout-heavy" in f for f in flags)
    assert not any("tiny-sample" in f for f in flags)


def test_tiny_sample_flagged():
    flags = _flags(40, 0.1, 100, estimated=False)
    assert any("tiny-sample" in f for f in flags)
    assert not any("blowout-heavy" in f for f in flags)


def test_estimated_flagged_when_no_play_data():
    flags = _flags(200, 0.1, 100, estimated=True)
    assert any("estimated-possessions" in f for f in flags)


def test_registered_in_tool_registry():
    assert "get_lineup_stats" in tools.TOOL_NAMES
    names = [t.name for t in tools.v1_tools]
    assert len(names) == len(set(names))


def test_invalid_team_fails_cleanly():
    res = get_lineup_stats.invoke({"team": "Not A Real Team XYZ"})
    assert res["ok"] is False
    assert "error" in res

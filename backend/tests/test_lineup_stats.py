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
    _best_net_unit,
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


def test_best_net_unit_is_not_the_most_used():
    units = [
        {"GROUP_NAME": "starters", "poss": 420, "NET_RATING": 3.2},
        {"GROUP_NAME": "bench mob", "poss": 120, "NET_RATING": 12.4},
        {"GROUP_NAME": "40-min wonder", "poss": 80, "NET_RATING": 25.0},
    ]
    best = _best_net_unit(units, 100)
    assert best["GROUP_NAME"] == "bench mob"


def test_best_net_unit_tie_break_prefers_larger_sample():
    units = [
        {"GROUP_NAME": "hot streak", "poss": 150, "NET_RATING": 8.5},
        {"GROUP_NAME": "steady", "poss": 200, "NET_RATING": 8.5},
    ]
    best = _best_net_unit(units, 100)
    assert best["GROUP_NAME"] == "steady"


def test_best_net_unit_none_when_everything_under_floor():
    units = [{"GROUP_NAME": "tiny", "poss": 40, "NET_RATING": 99.0}]
    assert _best_net_unit(units, 100) is None


def _fake_warehouse(rows):
    return lambda *a, **k: (rows, {"source": "test"})


def _fake_rows():
    # starters: 420 poss, net 10.0; bench mob: 120 poss, net 50.0
    return [
        {"GROUP_ID": "1-2-3-4-5", "GROUP_NAME": "starters", "GP": 40,
         "MIN": 210.0, "PTS": 2310.0, "PLUS_MINUS": 21.0},
        {"GROUP_ID": "6-7-8-9-10", "GROUP_NAME": "bench mob", "GP": 12,
         "MIN": 60.0, "PTS": 660.0, "PLUS_MINUS": 30.0},
    ]


def test_tool_marks_best_unit_not_most_used(monkeypatch):
    monkeypatch.setattr("app.tools.lineup.coerce_team_id", lambda t: 20)
    monkeypatch.setattr("app.tools.lineup._possession_aggs",
                        lambda *a: None)
    monkeypatch.setattr("app.tools.lineup._warehouse_or_live",
                        _fake_warehouse(_fake_rows()))
    res = get_lineup_stats.invoke({"team": "NYK"})
    assert res["ok"] is True
    assert res["best_net_unit"]["GROUP_NAME"] == "bench mob"
    assert res["best_net_unit"]["NET_RATING"] == 50.0
    flags = {r["GROUP_NAME"]: r["is_best_net_unit"] for r in res["rows"]}
    assert flags == {"starters": False, "bench mob": True}
    assert res["rows"][0]["GROUP_NAME"] == "starters"


def test_tool_best_unit_named_even_below_limit(monkeypatch):
    monkeypatch.setattr("app.tools.lineup.coerce_team_id", lambda t: 20)
    monkeypatch.setattr("app.tools.lineup._possession_aggs",
                        lambda *a: None)
    monkeypatch.setattr("app.tools.lineup._warehouse_or_live",
                        _fake_warehouse(_fake_rows()))
    res = get_lineup_stats.invoke({"team": "NYK", "limit": 1})
    assert res["ok"] is True
    assert [r["GROUP_NAME"] for r in res["rows"]] == ["starters"]
    assert res["best_net_unit"]["GROUP_NAME"] == "bench mob"


def _limit_aware_warehouse(rows):
    def fake(*a, **k):
        return rows[: k.get("limit", 25)], {"source": "test"}
    return fake


def _truncation_fixture_rows():
    rows = []
    for i in range(25):
        rows.append({"GROUP_ID": f"1-2-3-4-{100 + i}",
                     "GROUP_NAME": f"unit-{i}", "GP": 20,
                     "MIN": 100.0, "PTS": 210.0, "PLUS_MINUS": 5.0})
    for i in range(25, 29):
        rows.append({"GROUP_ID": f"1-2-3-4-{100 + i}",
                     "GROUP_NAME": f"unit-{i}", "GP": 20,
                     "MIN": 100.0, "PTS": 210.0, "PLUS_MINUS": 6.0})
    rows.append({"GROUP_ID": "1-2-3-4-999", "GROUP_NAME": "best unit",
                 "GP": 25, "MIN": 90.5, "PTS": 207.0, "PLUS_MINUS": 51.0})
    return rows


def test_best_net_unit_computed_past_warehouse_row_cap(monkeypatch):
    """Regression: best_net_unit must consider every floor-passing unit, not
    just the head-25 warehouse slice. The true best sits beyond row 25."""
    monkeypatch.setattr("app.tools.lineup.coerce_team_id", lambda t: 20)
    monkeypatch.setattr("app.tools.lineup._possession_aggs",
                        lambda *a: None)
    monkeypatch.setattr("app.tools.lineup._warehouse_or_live",
                        _limit_aware_warehouse(_truncation_fixture_rows()))
    res = get_lineup_stats.invoke({"team": "NYK"})
    assert res["ok"] is True
    assert res["best_net_unit"]["GROUP_NAME"] == "best unit"
    assert res["best_net_unit"]["NET_RATING"] > 50.0
    assert len(res["rows"]) <= 25

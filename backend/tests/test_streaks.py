"""Streak finder tests. Pure computation is hermetic; one integration
test reads the real warehouse to prove the wiring and ranking."""

import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import get_streaks
from app.tools.streaks import _cond_for, _value_for, compute_streaks


def _game(holder, holder_id, day, **stats):
    return {"holder": holder, "holder_id": holder_id,
            "date": _dt.date(2025, 1, day), **stats}


def _pts_games(holder, holder_id, values, start_day=1):
    return [_game(holder, holder_id, start_day + i, PTS=v)
            for i, v in enumerate(values)]


def test_longest_picks_max_run():
    games = _pts_games("A", 1, [10, 32, 35, 10, 31, 33, 34, 10, 30, 31, 32])
    cond = _cond_for("PTS", 30)
    out = compute_streaks(games, cond, _value_for("PTS"), "longest")
    assert len(out) == 1
    s = out[0]
    assert s["streak"] == 3
    assert s["start_date"] == "2025-01-09"
    assert s["end_date"] == "2025-01-11"
    assert s["active"] is True
    assert len(s["span"]) == 3
    assert [g["value"] for g in s["span"]] == [30.0, 31.0, 32.0]


def test_streak_spanning_season_start_edge():
    games = _pts_games("A", 1, [30, 31, 32, 5])
    out = compute_streaks(games, _cond_for("PTS", 30), _value_for("PTS"),
                          "longest")
    assert out[0]["streak"] == 3
    assert out[0]["start_date"] == "2025-01-01"
    assert out[0]["active"] is False


def test_streak_spanning_season_end_edge_is_active():
    games = _pts_games("A", 1, [5, 30, 31, 32])
    out = compute_streaks(games, _cond_for("PTS", 30), _value_for("PTS"),
                          "longest")
    assert out[0]["streak"] == 3
    assert out[0]["end_date"] == "2025-01-04"
    assert out[0]["active"] is True


def test_active_mode_skips_ended_streak():
    hot = _pts_games("Hot", 1, [5, 30, 31])
    cold = _pts_games("Cold", 2, [30, 31, 5])
    cond = _cond_for("PTS", 30)
    active = compute_streaks(hot + cold, cond, _value_for("PTS"), "active")
    assert [s["holder"] for s in active] == ["Hot"]
    assert active[0]["streak"] == 2
    assert active[0]["active"] is True
    longest = compute_streaks(hot + cold, cond, _value_for("PTS"), "longest")
    by_holder = {s["holder"]: s for s in longest}
    assert by_holder["Cold"]["streak"] == 2
    assert by_holder["Cold"]["active"] is False


def test_tie_break_most_recent_end_first():
    a = _pts_games("A", 1, [30, 31, 5, 5, 5])
    b = _pts_games("B", 2, [5, 5, 5, 30, 31])
    out = compute_streaks(a + b, _cond_for("PTS", 30), _value_for("PTS"),
                          "longest")
    assert [s["holder"] for s in out] == ["B", "A"]
    assert all(s["streak"] == 2 for s in out)


def test_tie_within_holder_prefers_most_recent():
    games = _pts_games("A", 1, [30, 31, 5, 32, 33])
    out = compute_streaks(games, _cond_for("PTS", 30), _value_for("PTS"),
                          "longest")
    assert out[0]["streak"] == 2
    assert out[0]["start_date"] == "2025-01-04"


def test_double_double_condition():
    games = [
        _game("A", 1, 1, PTS=25, REB=10, AST=3, STL=0, BLK=0),
        _game("A", 1, 2, PTS=12, REB=11, AST=10, STL=0, BLK=0),
        _game("A", 1, 3, PTS=30, REB=4, AST=2, STL=0, BLK=0),
    ]
    out = compute_streaks(games, _cond_for("DD2", 0), _value_for("DD2"),
                          "longest")
    assert out[0]["streak"] == 2
    assert out[0]["span"][1]["value"] == 3
    out_td = compute_streaks(games, _cond_for("TD3", 0), _value_for("TD3"),
                             "longest")
    assert out_td[0]["streak"] == 1


def test_win_condition_team():
    games = [
        _game("OKC", "OKC", 1, WL="W"),
        _game("OKC", "OKC", 2, WL="W"),
        _game("OKC", "OKC", 3, WL="L"),
        _game("OKC", "OKC", 4, WL="W"),
    ]
    out = compute_streaks(games, _cond_for("W", 0), _value_for("W"),
                          "longest")
    assert out[0]["streak"] == 2
    assert out[0]["span"][0]["value"] == "W"
    assert out[0]["active"] is False
    out_l = compute_streaks(games, _cond_for("L", 0), _value_for("L"),
                            "longest")
    assert out_l[0]["streak"] == 1
    assert out_l[0]["active"] is False


def test_holder_with_no_streak_excluded():
    games = _pts_games("A", 1, [5, 6, 7])
    out = compute_streaks(games, _cond_for("PTS", 30), _value_for("PTS"),
                          "longest")
    assert out == []


def test_top_clamps_and_orders_desc():
    games = []
    for pid in range(1, 6):
        games += _pts_games(f"P{pid}", pid, [30] * pid + [5])
    out = compute_streaks(games, _cond_for("PTS", 30), _value_for("PTS"),
                          "longest", top=3)
    assert [s["streak"] for s in out] == [5, 4, 3]


def test_unknown_stat_rejected():
    res = get_streaks.invoke({"stat": "vibes"})
    assert res["ok"] is False
    assert "unknown stat" in res["error"]


def test_wins_require_team_scope():
    res = get_streaks.invoke({"stat": "wins", "scope": "player"})
    assert res["ok"] is False
    assert "team" in res["error"]


def test_double_doubles_require_player_scope():
    res = get_streaks.invoke({"stat": "double-doubles", "scope": "team"})
    assert res["ok"] is False
    assert "player" in res["error"]


def test_team_stat_streak_needs_explicit_threshold():
    res = get_streaks.invoke({"stat": "points", "scope": "team"})
    assert res["ok"] is False
    assert "threshold" in res["error"]


def test_integration_team_win_streaks_real_warehouse():
    res = get_streaks.invoke({"stat": "wins", "scope": "team",
                              "season": "2024-25", "mode": "longest", "top": 5})
    assert res["ok"] is True
    streaks = res["rows"]["streaks"]
    assert len(streaks) == 5
    lengths = [s["streak"] for s in streaks]
    assert lengths == sorted(lengths, reverse=True)
    for s in streaks:
        assert len(s["span"]) == s["streak"]
        assert all(g["value"] == "W" for g in s["span"])
        assert s["start_date"] <= s["end_date"]
    assert res["meta"]["coverage"]["teams_scanned"] == 30
    assert res["meta"]["coverage"]["regular_season_only"] is True


def test_integration_player_point_streaks_real_warehouse():
    res = get_streaks.invoke({"stat": "points", "threshold": 30,
                              "scope": "player", "season": "2025-26",
                              "mode": "longest", "top": 5})
    assert res["ok"] is True
    streaks = res["rows"]["streaks"]
    assert streaks
    for s in streaks:
        assert len(s["span"]) == s["streak"]
        assert all(g["value"] >= 30 for g in s["span"])
        assert isinstance(s["holder_id"], int)
    assert res["meta"]["coverage"]["players_scanned"] > 0

"""Rest advantage tests. Pure schedule math is hermetic; one integration
test reads the real warehouse to prove the wiring and the invariants."""

import datetime as _dt
import sys
import time
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.tools.rest as rest_mod
from app.tools import get_rest_advantage
from app.tools.rest import (
    TeamGame,
    _classify_scoreboard_rows,
    build_schedule,
    summarize_team,
)


def _connect_retry(tries=10, sleep_s=10):
    """Open the warehouse for the test's own direct SQL verification.

    Seed jobs hold the warehouse write lock for minutes at a time;
    only lock-conflict errors are retried, everything else raises.
    """
    last: Exception | None = None
    for _ in range(tries):
        try:
            from app import store as _store

            return _store.connect(read_only=True)
        except (duckdb.IOException, duckdb.ConnectionException) as exc:
            if ("lock" not in str(exc).lower()
                    and "conflict" not in str(exc).lower()):
                raise
            last = exc
            time.sleep(sleep_s)
    assert last is not None
    raise last


def _row(day, home, vis, hp, vp, st="regular"):
    return {
        "date": _dt.date(2026, 1, day),
        "home_team": home,
        "visitor_team": vis,
        "home_pts": hp,
        "visitor_pts": vp,
        "season_type": st,
    }


def _aaa_schedule():
    # AAA: Jan 1 home win vs BBB, Jan 2 road loss at CCC (back-to-back),
    # Jan 5 home win vs BBB. BBB sits Jan 2-4, so AAA is at a rest
    # disadvantage on Jan 5.
    rows = [
        _row(1, "AAA", "BBB", 110, 100),
        _row(2, "CCC", "AAA", 105, 100),
        _row(5, "AAA", "BBB", 120, 115),
    ]
    sched = build_schedule(rows)
    return [g for g in sched if g.team == "AAA"]


def _aaa_rows():
    return [
        _row(1, "AAA", "BBB", 110, 100),
        _row(2, "CCC", "AAA", 105, 100),
        _row(5, "AAA", "BBB", 120, 115),
    ]


def _preview_rows():
    # AAA last played Jan 5, BBB last played Jan 1.
    return [
        _row(1, "AAA", "BBB", 110, 100),
        _row(2, "CCC", "AAA", 105, 100),
        _row(5, "AAA", "CCC", 120, 115),
    ]


def _hermetic(monkeypatch, rows):
    dropped = {"null_score": 0, "unknown_game_type": 0,
               "unparseable_date": 0}
    monkeypatch.setattr(
        rest_mod, "_load_scoreboard", lambda season: (rows, dropped, ""))
    monkeypatch.setattr(
        rest_mod, "_resolve_team",
        lambda raw: str(raw or "").strip().upper() or None)


def test_back_to_back_detection():
    aaa = _aaa_schedule()
    assert [g.rest_days for g in aaa] == [None, 0, 2]
    assert aaa[0].home is True
    assert aaa[0].won is True
    assert aaa[1].home is False
    assert aaa[1].won is False


def test_first_game_none_baseline():
    aaa = _aaa_schedule()
    assert aaa[0].rest_days is None
    assert aaa[0].rest_diff is None
    # CCC's only game in scope is Jan 2, so AAA's Jan 2 edge is also None.
    assert aaa[1].opp_rest_days is None
    assert aaa[1].rest_diff is None


def test_rest_diff_sign():
    aaa = _aaa_schedule()
    # BBB last played Jan 1 -> 3 days rest before Jan 5; AAA has 2.
    assert aaa[2].opp_rest_days == 3
    assert aaa[2].rest_diff == -1


def test_summary_values():
    summary = summarize_team(_aaa_schedule())
    assert summary["games"] == 3
    assert summary["wins"] == 2
    assert summary["losses"] == 1
    assert summary["back_to_backs"] == 1
    assert summary["rest_distribution"] == {
        "b2b": 1, "1_day": 0, "2_days": 1, "3_plus": 0}
    assert summary["avg_rest_days"] == 1.0
    assert summary["avg_rest_diff"] == -1.0
    assert summary["record_with_edge"] == "0-0"
    assert summary["record_even"] == "0-0"
    assert summary["record_at_disadvantage"] == "1-0"
    assert summary["games_with_edge_measured"] == 1


def _hand_game(rest, diff, won):
    return TeamGame(
        date=_dt.date(2026, 1, 10), team="AAA", opponent="BBB", home=True,
        pts_for=100, pts_against=90, won=won, season_type="regular",
        rest_days=rest, opp_rest_days=None, rest_diff=diff)


def test_distribution_buckets():
    games = [_hand_game(r, None, True)
             for r in (0, 1, 2, 3, 5, 7, None)]
    summary = summarize_team(games)
    assert summary["rest_distribution"] == {
        "b2b": 1, "1_day": 1, "2_days": 1, "3_plus": 3}
    assert summary["back_to_backs"] == 1
    assert summary["avg_rest_days"] == round((0 + 1 + 2 + 3 + 5 + 7) / 6, 2)


def test_rest_diff_sign_buckets_and_record_splits():
    games = [
        _hand_game(2, 2, True),
        _hand_game(2, 1, False),
        _hand_game(1, 0, True),
        _hand_game(1, 0, False),
        _hand_game(0, -1, True),
        _hand_game(0, -3, False),
        _hand_game(None, None, True),
    ]
    summary = summarize_team(games)
    assert summary["record_with_edge"] == "1-1"
    assert summary["record_even"] == "1-1"
    assert summary["record_at_disadvantage"] == "1-1"
    assert summary["games_with_edge_measured"] == 6
    assert summary["avg_rest_diff"] == round((2 + 1 + 0 + 0 - 1 - 3) / 6, 2)
    assert summary["quotable"] == (
        "1-1 with a rest edge vs 1-1 at a rest disadvantage"
        " (1-1 on even rest)")


def test_classify_scoreboard_rows_counts_drops():
    fetched = [
        ("2026-01-05", "0022500001", "AAA", "BBB", 110, 100),
        ("2026-01-06", "0022500002", "AAA", "BBB", None, 100),
        ("2026-01-07", "0012600001", "AAA", "BBB", 110, 100),
        ("not-a-date", "0022500003", "AAA", "BBB", 110, 100),
    ]
    rows, dropped = _classify_scoreboard_rows(fetched)
    assert len(rows) == 1
    assert rows[0]["date"] == _dt.date(2026, 1, 5)
    assert dropped == {"null_score": 1, "unknown_game_type": 1,
                       "unparseable_date": 1}


def test_date_returns_single_game_row(monkeypatch):
    _hermetic(monkeypatch, _aaa_rows())
    res = get_rest_advantage.invoke({"team": "AAA", "season": "2025-26",
                                     "season_type": "all",
                                     "date": "2026-01-05"})
    assert res["ok"] is True
    assert len(res["rows"]["games"]) == 1
    assert res["rows"]["games"][0]["date"] == "2026-01-05"
    assert res["rows"]["games"][0]["rest_diff"] == -1
    assert res["meta"]["date"] == "2026-01-05"
    # Summary still covers the full season as quotable context.
    assert res["rows"]["summary"]["games"] == 3


def test_date_with_no_game_errors(monkeypatch):
    _hermetic(monkeypatch, _aaa_rows())
    res = get_rest_advantage.invoke({"team": "AAA", "season": "2025-26",
                                     "date": "2026-01-03"})
    assert res["ok"] is False
    assert "no game for" in res["error"]


def test_bad_date_format_rejected(monkeypatch):
    _hermetic(monkeypatch, _aaa_rows())
    res = get_rest_advantage.invoke({"team": "AAA", "season": "2025-26",
                                     "date": "01/05/2026"})
    assert res["ok"] is False
    assert "bad date" in res["error"]


def test_league_with_date_rejected(monkeypatch):
    _hermetic(monkeypatch, _aaa_rows())
    res = get_rest_advantage.invoke({"team": "league", "season": "2025-26",
                                     "date": "2026-01-05"})
    assert res["ok"] is False
    assert "require a specific team" in res["error"]


def test_league_with_opponent_rejected(monkeypatch):
    _hermetic(monkeypatch, _aaa_rows())
    res = get_rest_advantage.invoke({"team": "league", "season": "2025-26",
                                     "opponent": "BBB"})
    assert res["ok"] is False
    assert "require a specific team" in res["error"]


def test_opponent_preview_rest_math(monkeypatch):
    _hermetic(monkeypatch, _preview_rows())
    res = get_rest_advantage.invoke({"team": "AAA", "season": "2025-26",
                                     "opponent": "BBB",
                                     "date": "2026-01-10"})
    assert res["ok"] is True
    preview = res["rows"]["preview"]
    assert preview["team_rest_days"] == 4
    assert preview["opp_rest_days"] == 8
    assert preview["rest_diff"] == -4
    assert preview["team_last_game"] == "2026-01-05"
    assert preview["opp_last_game"] == "2026-01-01"


def test_opponent_preview_no_baseline_errors(monkeypatch):
    _hermetic(monkeypatch, _preview_rows())
    res = get_rest_advantage.invoke({"team": "AAA", "season": "2025-26",
                                     "opponent": "ZZZ",
                                     "date": "2026-01-10"})
    assert res["ok"] is False
    assert "cannot establish a rest baseline" in res["error"]


def test_opponent_completed_matchup_on_date(monkeypatch):
    _hermetic(monkeypatch, _aaa_rows())
    res = get_rest_advantage.invoke({"team": "AAA", "season": "2025-26",
                                     "opponent": "BBB",
                                     "date": "2026-01-05"})
    assert res["ok"] is True
    assert len(res["rows"]["games"]) == 1
    assert res["rows"]["games"][0]["date"] == "2026-01-05"
    assert res["rows"]["opponent"] == "BBB"


def test_opponent_no_date_returns_most_recent_matchup(monkeypatch):
    _hermetic(monkeypatch, _aaa_rows())
    res = get_rest_advantage.invoke({"team": "AAA", "season": "2025-26",
                                     "opponent": "BBB"})
    assert res["ok"] is True
    assert len(res["rows"]["games"]) == 1
    assert res["rows"]["games"][0]["date"] == "2026-01-05"
    assert res["rows"]["opponent"] == "BBB"


def test_opponent_no_matchup_errors(monkeypatch):
    _hermetic(monkeypatch, _aaa_rows())
    res = get_rest_advantage.invoke({"team": "AAA", "season": "2025-26",
                                     "opponent": "ZZZ"})
    assert res["ok"] is False
    assert "no completed games between" in res["error"]


def test_unknown_team_rejected():
    res = get_rest_advantage.invoke({"team": "Not A Team"})
    assert res["ok"] is False
    assert res["tool"] == "get_rest_advantage"
    assert "unknown team" in res["error"]


def test_bad_season_type_rejected():
    res = get_rest_advantage.invoke({"season_type": "preseason"})
    assert res["ok"] is False
    assert res["tool"] == "get_rest_advantage"
    assert "season_type" in res["error"]


def test_team_name_resolution():
    abbr = get_rest_advantage.invoke({"team": "LAL"})
    full = get_rest_advantage.invoke({"team": "Los Angeles Lakers"})
    assert abbr["ok"] is True
    assert full["ok"] is True
    assert full["rows"]["team"] == "LAL"
    assert (full["rows"]["summary"]
            == abbr["rows"]["summary"])


def test_integration_regular_season_invariants_real_warehouse():
    league = get_rest_advantage.invoke({"team": "league", "season": "2025-26",
                                        "season_type": "regular"})
    assert league["ok"] is True
    assert league["rows"]["count"] == 30
    assert len(league["rows"]["teams"]) == 30
    for s in league["rows"]["teams"]:
        assert s["games"] == 82
        assert s["wins"] + s["losses"] == s["games"]
    diffs = [s["avg_rest_diff"] for s in league["rows"]["teams"]]
    assert diffs == sorted(diffs, reverse=True)
    assert league["meta"]["source"] == "warehouse"
    assert league["meta"]["season"] == "2025-26"
    assert league["meta"]["season_type"] == "regular"
    assert league["meta"]["coverage"]["games_dropped"] >= 0
    assert "games_dropped_detail" in league["meta"]["coverage"]
    # Team mode agrees with league mode on one club's line.
    lal = get_rest_advantage.invoke({"team": "LAL", "season": "2025-26",
                                     "season_type": "regular"})
    assert lal["ok"] is True
    assert lal["rows"]["team"] == "LAL"
    assert len(lal["rows"]["games"]) == 82
    by_abbr = {s["team"]: s for s in league["rows"]["teams"]}
    assert lal["rows"]["summary"] == {k: v for k, v in by_abbr["LAL"].items()
                                      if k != "team"}
    # Every club's rest gaps, recomputed from one warehouse read: each
    # team plays exactly 82 scored games and rest never goes negative.
    con = _connect_retry()
    try:
        fetched = con.execute(
            """SELECT GAME_DATE_EST, GAME_ID, HOME_TEAM_ABBREVIATION,
                      VISITOR_TEAM_ABBREVIATION, HOME_TEAM_PTS,
                      VISITOR_TEAM_PTS
                FROM silver_scoreboard
                WHERE _season = '2025-26'
                  AND HOME_TEAM_PTS IS NOT NULL
                  AND VISITOR_TEAM_PTS IS NOT NULL""").fetchall()
    finally:
        con.close()
    rows = []
    for gdate, gid, home, vis, hp, vp in fetched:
        if str(gid or "")[:3] != "002":
            continue
        rows.append({
            "date": _dt.datetime.strptime(str(gdate)[:10], "%Y-%m-%d").date(),
            "home_team": home, "visitor_team": vis,
            "home_pts": hp, "visitor_pts": vp, "season_type": "regular",
        })
    sched = build_schedule(rows)
    by_team: dict[str, list[TeamGame]] = {}
    for g in sched:
        by_team.setdefault(g.team, []).append(g)
    assert len(by_team) == 30
    for team, games in by_team.items():
        assert len(games) == 82, team
        for g in games:
            assert g.rest_days is None or g.rest_days >= 0, (team, g)

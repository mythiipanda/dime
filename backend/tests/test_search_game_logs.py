"""search_game_logs tests. Pure filter logic is hermetic; four
integration tests run against the real warehouse to prove the wiring
and that the filters actually filter."""

import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import search_game_logs
from app.tools.gamelog import (
    _describe_filters,
    _matches,
    _parse_month,
    _positive,
)


def _game(date, pts=20, reb=5, ast=5, stl=1, blk=1, matchup="LAL vs. UTA"):
    d = _dt.date.fromisoformat(date)
    return {
        "date": d, "matchup": matchup,
        "opponent": matchup.split()[-1].upper(),
        "home": "vs." in matchup, "wl": "W",
        "pts": float(pts), "reb": float(reb), "ast": float(ast),
        "stl": float(stl), "blk": float(blk),
        "dd_count": sum(1 for v in (pts, reb, ast, stl, blk) if v >= 10),
    }


def _filters(**kw):
    base = {
        "min_points": None, "min_rebounds": None, "min_assists": None,
        "min_pra": None, "double_double": False, "triple_double": False,
        "opponent": None, "month": None, "start_date": None,
        "end_date": None, "home_away": None,
    }
    base.update(kw)
    return base


def test_matches_points_threshold():
    g = _game("2026-03-01", pts=30)
    assert _matches(g, _filters(min_points=30)) is True
    assert _matches(g, _filters(min_points=31)) is False


def test_matches_rebounds_and_assists():
    g = _game("2026-03-01", reb=12, ast=11)
    f = _filters(min_rebounds=10, min_assists=10)
    assert _matches(g, f) is True
    assert _matches(g, _filters(min_rebounds=13)) is False


def test_matches_pra_combined():
    g = _game("2026-03-01", pts=25, reb=8, ast=8)  # 41 PRA
    assert _matches(g, _filters(min_pra=40)) is True
    assert _matches(g, _filters(min_pra=42)) is False


def test_matches_double_and_triple_double():
    dd = _game("2026-03-01", pts=20, reb=12)          # two cats
    td = _game("2026-03-02", pts=20, reb=12, ast=11)  # three cats
    assert _matches(dd, _filters(double_double=True)) is True
    assert _matches(dd, _filters(triple_double=True)) is False
    assert _matches(td, _filters(triple_double=True)) is True
    assert _matches(_game("2026-03-03"), _filters(double_double=True)) is False


def test_matches_opponent_and_home_away():
    home_nyk = _game("2026-03-01", matchup="BOS vs. NYK")
    away_bos = _game("2026-03-02", matchup="LAL @ BOS")
    assert _matches(home_nyk, _filters(opponent="NYK")) is True
    assert _matches(away_bos, _filters(opponent="NYK")) is False
    assert _matches(home_nyk, _filters(home_away="home")) is True
    assert _matches(home_nyk, _filters(home_away="away")) is False
    assert _matches(away_bos, _filters(home_away="away")) is True


def test_matches_month_and_date_range():
    march = _game("2026-03-15")
    april = _game("2026-04-02")
    assert _matches(march, _filters(month=3)) is True
    assert _matches(april, _filters(month=3)) is False
    rng = _filters(start_date=_dt.date(2026, 3, 1),
                   end_date=_dt.date(2026, 3, 31))
    assert _matches(march, rng) is True
    assert _matches(april, rng) is False


def test_parse_month_accepts_names_numbers_iso():
    assert _parse_month("March") == 3
    assert _parse_month("mar") == 3
    assert _parse_month(3) == 3
    assert _parse_month("2026-03") == 3
    assert _parse_month("notamonth") is None
    assert _parse_month(13) is None
    assert _parse_month(None) is None


def test_positive_rejects_garbage():
    assert _positive("40", "min_points") == 40.0
    assert _positive(None, "min_points") is None
    try:
        _positive("abc", "min_points")
    except ValueError as exc:
        assert "must be a number" in str(exc)
    else:
        raise AssertionError("expected ValueError")
    try:
        _positive(-1, "min_points")
    except ValueError as exc:
        assert ">= 0" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_describe_filters_readable():
    s = _describe_filters(_filters(min_points=40, opponent="BOS",
                                   month=3, home_away="away"))
    assert "40+ points" in s and "vs BOS" in s and "March" in s
    assert "away games" in s
    assert _describe_filters(_filters()) == "all games"


def test_integration_lebron_30pt_games_filter():
    res = search_game_logs.invoke({"player": "LeBron James",
                                   "min_points": 30})
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["player"] == "LeBron James"
    assert rows["total"] == 6
    assert rows["returned"] == 6
    assert rows["capped"] is False
    # The filter actually filtered: every returned game meets it.
    assert all(g["pts"] >= 30 for g in rows["matches"])
    dates = [g["date"] for g in rows["matches"]]
    assert dates == sorted(dates, reverse=True)
    assert res["meta"]["source"] == "warehouse"
    assert res["meta"]["season"] == "2025-26"


def test_integration_lebron_vs_celtics():
    res = search_game_logs.invoke({"player": "LeBron James",
                                   "opponent": "Celtics"})
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["total"] >= 1
    assert all(g["opponent"] == "BOS" for g in rows["matches"])


def test_integration_lebron_march_games():
    res = search_game_logs.invoke({"player": "LeBron James",
                                   "start_date": "2026-03-01",
                                   "end_date": "2026-03-31"})
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["total"] == 14
    assert all(g["date"][:7] == "2026-03" for g in rows["matches"])


def test_integration_month_name_filter_matches_date_range():
    by_month = search_game_logs.invoke({"player": "LeBron James",
                                        "month": "March"})
    by_range = search_game_logs.invoke({"player": "LeBron James",
                                        "start_date": "2026-03-01",
                                        "end_date": "2026-03-31"})
    assert by_month["ok"] is True
    assert by_month["rows"]["total"] == by_range["rows"]["total"] == 14


def test_integration_cap_counts_beyond_limit():
    res = search_game_logs.invoke({"player": "LeBron James", "limit": 10})
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["total"] == 60
    assert rows["returned"] == 10
    assert rows["capped"] is True


def test_integration_unknown_player_clean_error():
    res = search_game_logs.invoke({"player": "Player McNotreal zzz",
                                   "min_points": 40})
    assert res["ok"] is False
    assert "unknown player" in res["error"]


def test_integration_unknown_team_clean_error():
    res = search_game_logs.invoke({"player": "LeBron James",
                                   "opponent": "ZZZ"})
    assert res["ok"] is False
    assert "unknown team" in res["error"]


def test_integration_bad_month_clean_error():
    res = search_game_logs.invoke({"player": "LeBron James",
                                   "month": "Smarch"})
    assert res["ok"] is False
    assert "month" in res["error"]


# --- Ticket A: playoff scope -------------------------------------------------

def test_integration_playoffs_brunson_no_rows_explicit():
    # Jalen Brunson has no playoff rows in the warehouse. The old code
    # silently answered 0 over regular-season games; now it must say so
    # explicitly instead of returning a computed 0.
    res = search_game_logs.invoke({"player": "Jalen Brunson",
                                   "triple_double": True,
                                   "playoffs": True})
    assert res["ok"] is False
    assert "playoff" in res["error"]
    assert "Jalen Brunson" in res["error"]


def test_integration_playoffs_reads_playoff_table():
    # Jayson Tatum has 6 playoff games in 2025-26. Cross-check the
    # tool's triple-double total against a direct count over
    # silver_playoff_gamelogs to prove the playoff scope is honored.
    from app import store as _store
    from app.tools._core import coerce_player_id as _coerce
    from app.tools.gamelog import _f as _ff

    pid = _coerce("Jayson Tatum")
    con = _store.connect(read_only=True)
    try:
        rows = con.execute(
            "SELECT PTS, REB, AST, STL, BLK FROM silver_playoff_gamelogs"
            " WHERE Player_ID = ? AND _season = '2025-26'",
            [pid]).fetchall()
    finally:
        con.close()
    expect = sum(1 for r in rows
                 if sum(1 for v in r if _ff(v) >= 10) >= 3)
    res = search_game_logs.invoke({"player": "Jayson Tatum",
                                   "triple_double": True,
                                   "playoffs": True})
    assert res["ok"] is True
    assert res["rows"]["scope"] == "playoffs"
    assert "playoff" in res["rows"]["filters"]
    assert res["rows"]["total"] == expect


def test_integration_playoffs_player_team_present():
    res = search_game_logs.invoke({"player": "Jayson Tatum",
                                   "playoffs": True, "limit": 2})
    assert res["ok"] is True
    assert res["rows"]["total"] == 6
    assert res["rows"]["returned"] == 2
    assert res["rows"]["player_team"]


# --- Ticket B: league-wide mode ----------------------------------------------

def test_integration_league_wide_50pt_leaders():
    res = search_game_logs.invoke({"league_wide": True, "min_points": 50})
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["league_wide"] is True
    assert rows["scope"] == "regular"
    assert rows["total_players"] >= 1
    leaders = rows["leaders"]
    counts = [l["count"] for l in leaders]
    # Sorted by count desc, and the counts partition all 50-point games.
    assert counts == sorted(counts, reverse=True)
    assert all(c >= 1 for c in counts)
    assert all(l["player"] and l["player_id"] for l in leaders)
    from app import store as _store
    con = _store.connect(read_only=True)
    try:
        total50 = con.execute(
            "SELECT COUNT(*) FROM silver_player_gamelogs"
            " WHERE _season = '2025-26' AND CAST(PTS AS DOUBLE) >= 50"
        ).fetchone()[0]
    finally:
        con.close()
    assert sum(counts) == total50


def test_integration_league_wide_counts_match_player_path():
    # League-wide counts must agree with the player-scoped tool for a
    # named player.
    wide = search_game_logs.invoke({"league_wide": True, "min_points": 40})
    assert wide["ok"] is True
    top = wide["rows"]["leaders"][0]
    scoped = search_game_logs.invoke({"player": top["player"],
                                      "min_points": 40})
    assert scoped["ok"] is True
    assert top["count"] == scoped["rows"]["total"]


def test_integration_league_wide_playoffs_compose():
    res = search_game_logs.invoke({"league_wide": True, "min_points": 30,
                                   "playoffs": True})
    assert res["ok"] is True
    assert res["rows"]["scope"] == "playoffs"
    assert "playoff" in res["rows"]["filters"]


def test_player_required_unless_league_wide():
    res = search_game_logs.invoke({"min_points": 50})
    assert res["ok"] is False
    assert "league_wide" in res["error"]

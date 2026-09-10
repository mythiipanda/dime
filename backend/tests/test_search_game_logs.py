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

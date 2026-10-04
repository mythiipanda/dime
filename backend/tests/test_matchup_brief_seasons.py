import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store  # noqa: E402
from shared.tools.prediction import (  # noqa: E402
    _derived_ratings,
    get_game_prediction,
)
from shared.tools.team import get_season_series  # noqa: E402

BOS = 1610612738


def _season_rows(table, season):
    con = store.connect()
    try:
        return con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE _season = ?",
            [season],
        ).fetchone()[0]
    finally:
        con.close()


def _hist_pairings(season, abbr_a, abbr_b):
    con = store.connect()
    try:
        return con.execute(
            "SELECT game_id, matchup, wl FROM silver_hist_gamelogs "
            "WHERE _season = ? AND season_type = 'regular-season' "
            "AND team_abbreviation = ? AND matchup ILIKE ? ORDER BY game_date",
            [season, abbr_a, f"%{abbr_b}%"],
        ).fetchall()
    finally:
        con.close()


def test_warehouse_has_no_2024_25_team_games_or_ratings():
    assert _season_rows("silver_team_games", "2024-25") == 0
    assert _season_rows("silver_team_ratings", "2024-25") == 0
    assert _season_rows("silver_hist_gamelogs", "2024-25") > 0


def test_prediction_derives_2024_25_ratings_offline():
    out = get_game_prediction.invoke(
        {"a": "BOS", "b": "NYK", "season": "2024-25", "n_sims": 2_000})
    assert out["ok"] is True
    assert out["inputs"]["ratings_source"] == "silver_hist_gamelogs"
    assert out["meta"]["ratings_fetched_at"] is None
    assert "silver_hist_gamelogs" in out["methodology"][0]
    assert "No live source" in out["methodology"][0]
    home = out["inputs"]["home"]
    assert home["record"] == "61-21"
    assert home["off_rating"] == pytest.approx(118.9, abs=0.1)
    assert home["def_rating"] == pytest.approx(109.6, abs=0.1)
    assert home["net_rating"] == pytest.approx(9.3, abs=0.1)
    assert home["net_rating"] == pytest.approx(
        home["off_rating"] - home["def_rating"], abs=0.15)
    assert out["inputs"]["game_pace"] > 90.0


def test_derived_ratings_track_the_live_api_net_rating():
    out = get_game_prediction.invoke(
        {"a": "BOS", "b": "NYK", "season": "2024-25", "n_sims": 2_000})
    assert out["ok"] is True
    assert abs(out["inputs"]["home"]["net_rating"] - 9.4) <= 0.5


def test_derived_ratings_keep_every_team_on_the_full_schedule():
    con = store.connect()
    try:
        ratings = _derived_ratings(con, "2024-25")
    finally:
        con.close()
    assert len(ratings) == 30
    for team_id, card in ratings.items():
        assert card["gp"] == 82, team_id
        assert card["w"] + card["l"] == 82, team_id
        assert card["net"] == pytest.approx(card["off"] - card["def"],
                                            abs=0.05), team_id
        assert card["pace"] > 90.0, team_id


def test_season_series_2024_25_counts_regular_and_playoff_meetings():
    out = get_season_series.invoke(
        {"team_a": "BOS", "team_b": "NYK", "season": "2024-25"})
    assert out["ok"] is True
    summary = out["rows"]["summary"]
    assert summary["games"] == 10
    assert summary["bos_wins"] == 6
    assert summary["nyk_wins"] == 4
    assert summary["playoff_meetings"] == 6
    phases = [game["phase"] for game in out["rows"]["games"]]
    assert phases.count("regular season") == 4
    assert phases.count("playoffs") == 6


def test_season_series_2024_25_reports_a_pairing_with_no_playoff_meeting():
    assert _hist_pairings("2024-25", "LAL", "GSW")
    out = get_season_series.invoke(
        {"team_a": "LAL", "team_b": "GSW", "season": "2024-25"})
    assert out["ok"] is True
    summary = out["rows"]["summary"]
    assert summary["games"] == 4
    assert summary["lal_wins"] == 3
    assert summary["gsw_wins"] == 1
    assert "playoff_meetings" not in summary
    assert all(game["phase"] == "regular season"
               for game in out["rows"]["games"])


def test_season_series_still_fails_loud_for_a_pairing_that_never_met():
    assert _hist_pairings("2019-20", "ATL", "NOP") == []
    out = get_season_series.invoke(
        {"team_a": "ATL", "team_b": "NOP", "season": "2019-20"})
    assert out["ok"] is False
    assert "do not report a 0-0 record" in out["error"].lower()


def test_season_series_reads_history_for_a_season_stored_games_do_not_cover():
    out = get_season_series.invoke(
        {"team_a": "BOS", "team_b": "NYK", "season": "2023-24"})
    assert out["ok"] is True
    assert out["rows"]["summary"]["games"] == 5


def test_season_series_does_not_double_count_a_season_both_tables_cover():
    con = store.connect()
    try:
        stored = con.execute(
            "SELECT COUNT(*) FROM silver_team_games WHERE _season = '2025-26' "
            "AND _entity = ? AND MATCHUP ILIKE '%NYK%'",
            [f"team:{BOS}"],
        ).fetchone()[0]
    finally:
        con.close()
    assert stored > 0
    out = get_season_series.invoke(
        {"team_a": "BOS", "team_b": "NYK", "season": "2025-26"})
    assert out["ok"] is True
    regular = [game for game in out["rows"]["games"]
               if game["phase"] == "regular season"]
    assert len(regular) == stored
    ids = [game["game_id"] for game in out["rows"]["games"]]
    assert len(ids) == len(set(ids))
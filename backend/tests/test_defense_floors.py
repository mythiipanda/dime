"""Regression tests for the "best defensive player" incident.

A "best defensive players?" question was answered by crowning a
garbage-time player (53.3 on-court DEF_RATING in ~15 total minutes) the
league's best defensive player. Root cause: get_player_ratings let the
caller undercut the minutes floor to 0 via max(0, ...), and the same
undercuttable-floor pattern existed on other leaderboard tools.

These tests pin:
1. get_player_ratings enforces a hard 500-total-minute floor the caller
   cannot undercut (explicit min_minutes=0 still excludes sub-floor rows).
2. get_leaders per-game rate boards enforce the same hard floor.
3. get_lineup_leaders enforces a hard floor (its minutes arg was
   previously passed straight through, unclamped).
4. The analyst presentation prompt forbids crowning "best defender" /
   "best defensive player" from on-court rating evidence.

All hermetic: a scratch DuckDB file behind monkeypatched
app.store.DB_PATH; no network, no LLM.
"""

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store as _store  # noqa: E402
from shared.tools import league as _league  # noqa: E402

SEASON = "2025-26"


@pytest.fixture()
def warehouse(tmp_path, monkeypatch):
    db = tmp_path / "test.duckdb"
    con = duckdb.connect(str(db))
    try:
        con.execute(
            "CREATE TABLE silver_advanced ("
            "PLAYER_NAME TEXT, TEAM_ABBREVIATION TEXT, GP INTEGER, "
            "MIN DOUBLE, OFF_RATING DOUBLE, DEF_RATING DOUBLE, "
            "_season TEXT)"
        )
        # The incident's shape: a scrub with a sparkling on-court
        # defensive rating in garbage time, plus a real rotation player.
        con.execute(
            "INSERT INTO silver_advanced VALUES "
            "('Garbage Time', 'XYZ', 2, 8.0, 90.0, 53.3, '2025-26'),"
            "('Real Player', 'ABC', 70, 30.0, 112.0, 105.2, '2025-26')"
        )
        con.execute(
            "CREATE TABLE silver_leaders_pts ("
            "PLAYER TEXT, TEAM TEXT, GP INTEGER, MIN DOUBLE, PTS INTEGER, "
            "_season TEXT)"
        )
        con.execute(
            "INSERT INTO silver_leaders_pts VALUES "
            "('One Game Wonder', 'XYZ', 1, 20.0, 60, '2025-26'),"
            "('Steady Scorer', 'ABC', 70, 2100.0, 2100, '2025-26')"
        )
        con.execute(
            "CREATE TABLE silver_lineups ("
            "TEAM_ABBREVIATION TEXT, GROUP_NAME TEXT, GP INTEGER, "
            "MIN DOUBLE, PLUS_MINUS DOUBLE, _season TEXT)"
        )
        con.execute(
            "INSERT INTO silver_lineups VALUES "
            "('XYZ', 'junk five', 1, 4.0, 3.0, '2025-26'),"
            "('ABC', 'real five', 40, 200.0, 50.0, '2025-26')"
        )
    finally:
        con.close()
    monkeypatch.setattr(_store, "DB_PATH", db)
    monkeypatch.setattr(_store, "LOCK_PATH", tmp_path / ".write.lock")
    return db


def test_player_ratings_zero_floor_still_excludes_scrubs(warehouse):
    """The agent's exact call shape: explicit min_minutes=0."""
    res = _league.get_player_ratings.invoke(
        {"season": SEASON, "metric": "defense", "min_minutes": 0, "limit": 10}
    )
    assert res["ok"] is True
    names = [r["PLAYER"] for r in res["rows"]]
    assert "Garbage Time" not in names
    assert "Real Player" in names
    assert all(r["MINUTES"] >= 500 for r in res["rows"])
    assert res["meta"]["qualification"] == "500+ total minutes"


def test_player_ratings_caller_can_raise_but_not_lower_floor(warehouse):
    res = _league.get_player_ratings.invoke(
        {"season": SEASON, "metric": "defense", "min_minutes": 1500,
         "limit": 10}
    )
    assert res["ok"] is True
    assert all(r["MINUTES"] >= 1500 for r in res["rows"])
    assert res["meta"]["qualification"] == "1,500+ total minutes"


def test_leaders_rate_board_enforces_minutes_floor(warehouse):
    # PPG (not PTS) takes the per-game rate path: 60 pts in 1 game would
    # otherwise top the board at 60.0 ppg.
    res = _league.get_leaders.invoke(
        {"stat_category": "PPG", "season": SEASON,
         "ranking_direction": "desc"}
    )
    assert res["ok"] is True
    names = [r["PLAYER"] for r in res["rows"]]
    assert "One Game Wonder" not in names
    assert "Steady Scorer" in names
    assert res["meta"]["qualification"] == "500+ total minutes"


def test_lineup_leaders_zero_floor_still_excludes_junk(warehouse):
    res = _league.get_lineup_leaders.invoke(
        {"season": SEASON, "min_minutes": 0, "limit": 10}
    )
    assert res["ok"] is True
    groups = [r["GROUP_NAME"] for r in res["rows"]]
    assert "junk five" not in groups
    assert "real five" in groups


def test_analyst_system_forbids_best_defender_crowning():
    from app.graph import ANALYST_SYSTEM

    assert "best defensive player" in ANALYST_SYSTEM
    assert "best defender" in ANALYST_SYSTEM
    assert "on-court rating among qualified players" in ANALYST_SYSTEM
    # The constraint must be a prohibition, not a suggestion.
    assert "Never crown anyone" in ANALYST_SYSTEM

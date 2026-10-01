import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store  # noqa: E402
from shared.tools.league import get_leaders, get_ratings  # noqa: E402
from v2.adapters import coverage as coverage_mod  # noqa: E402
from v2.adapters.core import call_capability  # noqa: E402
from v2.domain.evidence import admit_evidence  # noqa: E402

SEASON = "2024-25"


def _seed(path):
    connection = duckdb.connect(str(path))
    try:
        connection.execute(
            "CREATE TABLE silver_leaders_ast (RANK BIGINT, PLAYER VARCHAR, "
            "TEAM VARCHAR, GP BIGINT, AST BIGINT, MIN BIGINT, "
            "_source VARCHAR, _season VARCHAR, _fetched_at VARCHAR)"
        )
        connection.execute(
            "INSERT INTO silver_leaders_ast VALUES "
            "(1, 'Trae Young', 'ATL', 76, 880, 2739, 'nba_stats', "
            "'2024-25', '2025-06-01T00:00:00+00:00'), "
            "(2, 'Nikola Jokic', 'DEN', 70, 716, 2500, 'nba_stats', "
            "'2024-25', '2025-06-01T00:00:00+00:00'), "
            "(1, 'Current Star', 'DEN', 65, 697, 2200, 'nba_stats', "
            "'2025-26', '2026-09-30T00:00:00+00:00')"
        )
        connection.execute(
            "CREATE TABLE silver_boxscores (GAME_ID VARCHAR, "
            "TEAM_ID BIGINT, teamTricode VARCHAR, teamCity VARCHAR, "
            "teamName VARCHAR, PLAYER_ID BIGINT, firstName VARCHAR, "
            "familyName VARCHAR, points BIGINT, "
            "fieldGoalsAttempted BIGINT, freeThrowsAttempted BIGINT, "
            "reboundsOffensive BIGINT, turnovers BIGINT, comment VARCHAR, "
            "_source VARCHAR, _season VARCHAR, _fetched_at VARCHAR, "
            "_entity VARCHAR)"
        )
        games = [
            ("0022400001", 1610612738, "BOS", "Boston", "Celtics",
             1, "Jay", "Star", 20, 10, 2, 1, 2, ""),
            ("0022400001", 1610612738, "BOS", "Boston", "Celtics",
             2, "Jay", "Sidekick", 80, 60, 10, 5, 8, ""),
            ("0022400001", 1610612752, "NYK", "New York", "Knicks",
             3, "Knick", "Leader", 90, 70, 10, 8, 12, ""),
            ("0022400002", 1610612738, "BOS", "Boston", "Celtics",
             1, "Jay", "Star", 60, 40, 4, 2, 5, ""),
            ("0022400002", 1610612738, "BOS", "Boston", "Celtics",
             2, "Jay", "Sidekick", 50, 35, 4, 2, 4, ""),
            ("0022400002", 1610612752, "NYK", "New York", "Knicks",
             3, "Knick", "Leader", 95, 72, 12, 6, 11, ""),
            ("0022400001", 1610612738, "BOS", "Boston", "Celtics",
             9, "Did", "Notplay", 500, 200, 100, 50, 60,
             "DND - Injury/Illness"),
            ("0042400101", 1610612738, "BOS", "Boston", "Celtics",
             1, "Jay", "Star", 200, 150, 40, 10, 20, ""),
            ("0042400101", 1610612752, "NYK", "New York", "Knicks",
             3, "Knick", "Leader", 190, 140, 30, 12, 18, ""),
        ]
        for game in games:
            connection.execute(
                "INSERT INTO silver_boxscores VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "'nba_stats', '2024-25', '2025-06-01T00:00:00+00:00', '')",
                list(game),
            )
    finally:
        connection.close()


@pytest.fixture()
def warehouse(monkeypatch, tmp_path):
    path = tmp_path / "execgap.duckdb"
    _seed(path)
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store._tables_cache.clear()
    store._pool_evict_all()
    store.warehouse_identity_cache_clear()
    coverage_mod.coverage_cache_clear()
    yield path
    coverage_mod.coverage_cache_clear()


def test_assists_full_name_selects_assists_board(warehouse):
    result = get_leaders.invoke(
        {"stat_category": "assists", "season": SEASON})
    assert result["ok"] is True
    assert result["rows"][0]["PLAYER"] == "Trae Young"
    assert result["rows"][0]["AST"] == 880
    assert result["rows"][0]["GP"] == 76


def test_descending_direction_accepted(warehouse):
    result = get_leaders.invoke(
        {"stat_category": "AST", "season": SEASON,
         "ranking_direction": "descending"})
    assert result["ok"] is True
    assert result["rows"][0]["PLAYER"] == "Trae Young"
    assert result["rows"][0]["AST"] == 880


def test_qualified_leaders_capability_binds_full_name(warehouse):
    envelope = call_capability(
        "qualified_leaders",
        {"stat_category": "assists", "season": SEASON})
    assert envelope.rows[0]["AST"] == 880
    assert envelope.units["AST"] == "count"
    admit_evidence(envelope, required_season=SEASON)


def test_missing_ratings_season_estimated_from_gamelogs(warehouse):
    result = get_ratings.invoke({"season": SEASON, "team": "BOS"})
    assert result["ok"] is True
    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["TEAM_NAME"] == "Boston Celtics"
    assert row["GP"] == 2
    assert (row["W"], row["L"]) == (2, 0)
    assert row["OFF_RATING"] == 129.0
    assert row["DEF_RATING"] == 115.1
    assert row["NET_RATING"] == 13.9
    assert row["PACE"] == 81.4


def test_team_ratings_capability_binds_gamelog_fallback(warehouse):
    envelope = call_capability(
        "team_ratings", {"season": SEASON, "team": "Celtics"})
    assert envelope.season == SEASON
    assert envelope.rows[0]["NET_RATING"] == 13.9
    assert envelope.units["NET_RATING"] == "points_per_100_possessions"
    admit_evidence(envelope, required_season=SEASON)


def test_ratings_refusal_preserved_without_gamelogs(warehouse):
    result = get_ratings.invoke({"season": "2023-24", "team": "BOS"})
    assert result["ok"] is False
    assert result["rows"] == []

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.scripts.seed_injury_history import BUILD_SQL


def test_build_sql_has_expected_shape():
    sql = BUILD_SQL.upper()
    assert "FROM SILVER_HIST_PLAYER_SEASONS" in sql
    assert "FROM SILVER_HIST_GAMELOGS" in sql
    assert "GAMES_MISSED" in sql
    assert "AVAILABILITY_PCT" in sql
    assert "REGULAR-SEASON" in sql
    assert "GREATEST" in sql


def test_build_sql_columns_present():
    sql = BUILD_SQL.upper()
    for col in ("PLAYER_ID", "PLAYER_NAME", "SEASON_YEAR", "SEASON",
                "TEAM_ABBREVIATION", "GP", "TEAM_GP"):
        assert col in sql

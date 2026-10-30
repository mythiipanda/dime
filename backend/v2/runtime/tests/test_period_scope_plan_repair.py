from __future__ import annotations

from typing import Any, Mapping
import pytest
from v2.contracts import (
    Claim,
    ClaimKind,
    DraftReport,
    EvidenceRequirement,
    PeriodScope,
    PeriodScopeSource,
    Plan,
    PlanNode,
    PlanStatus,
    RunMode,
    TaskSpec,
    VerificationReport,
    VerificationStatus,
)
from v2.tests.runtime.test_model_stages import StubModel


EXPECTED_CELTICS_SQL = (
    "SELECT COUNT(*) AS games, SUM(CASE WHEN wl = 'W' THEN 1 ELSE 0 END) AS wins, "
    "SUM(CASE WHEN wl = 'L' THEN 1 ELSE 0 END) AS losses, SUM(pts) AS total_points, "
    "CAST(SUM(pts) AS DOUBLE) / COUNT(*) AS mean_points_per_game "
    "FROM silver_hist_gamelogs WHERE _season = '2024-25' "
    "AND season_type = 'Regular Season' AND team_name = 'Boston Celtics'"
)

REPAIRED_CELTICS_SQL = (
    "SELECT COUNT(*) AS games, SUM(CASE WHEN wl = 'W' THEN 1 ELSE 0 END) AS wins, "
    "SUM(CASE WHEN wl = 'L' THEN 1 ELSE 0 END) AS losses, SUM(pts) AS total_points, "
    "CAST(SUM(pts) AS DOUBLE) / COUNT(*) AS mean_points_per_game "
    "FROM silver_hist_gamelogs WHERE _season = '2024-25' "
    "AND season_type = 'regular-season' AND team_name = 'Boston Celtics'"
)


R5_CAPTURED_CELTICS_SQL = (
    "SELECT Team_ID, COUNT(*) AS games_played, "
    "SUM(CASE WHEN WL = 'W' THEN 1 ELSE 0 END) AS wins, "
    "SUM(CASE WHEN WL = 'L' THEN 1 ELSE 0 END) AS losses, "
    "SUM(PTS) AS total_points_scored, "
    "CAST(SUM(PTS) AS DOUBLE) / COUNT(*) AS mean_points_per_game "
    "FROM silver_team_games WHERE _season = '2024-25' "
    "AND Team_ID = (SELECT TeamID FROM silver_standings WHERE TeamName = "
    "'Boston Celtics' LIMIT 1) GROUP BY Team_ID"
)


R507_PLAYER_EXPECTED = (
    "SELECT PLAYER, TEAM, GP, PPG, RPG, APG, TS_PCT FROM silver_player_season "
    "WHERE PLAYER = 'Shai Gilgeous-Alexander' AND _season = '2024-25'"
)
R507_PLAYER_ALIASED = (
    "SELECT PLAYER, TEAM, GP, PPG, RPG, APG, TS_PCT, PPG AS \"PTS\", "
    "RPG AS \"REB\", APG AS \"AST\" FROM silver_player_season "
    "WHERE PLAYER = 'Shai Gilgeous-Alexander' AND _season = '2024-25'"
)
R507_HIST_EXPECTED = (
    "SELECT player_name, team_abbreviation, gp, pts, reb, ast "
    "FROM silver_hist_player_seasons WHERE player_name = "
    "'Shai Gilgeous-Alexander' AND _season = '2024-25'"
)
R507_HIST_ALIASED = (
    "SELECT player_name, team_abbreviation, gp AS \"GP\", pts AS \"TOTAL_PTS\", "
    "reb AS \"TOTAL_REB\", ast AS \"TOTAL_AST\", pts AS \"PTS\", reb AS \"REB\", "
    "ast AS \"AST\" FROM silver_hist_player_seasons WHERE player_name = "
    "'Shai Gilgeous-Alexander' AND _season = '2024-25'"
)


def test_shared_sql_coverage_keeps_renamed_source_columns() -> None:
    from v2.domain.sql_coverage import sql_covers

    aliased_only = (
        "SELECT player_name, team_abbreviation, gp AS \"GP\", "
        "pts AS \"TOTAL_PTS\", reb AS \"TOTAL_REB\", ast AS \"TOTAL_AST\" "
        "FROM silver_hist_player_seasons WHERE player_name = "
        "'Shai Gilgeous-Alexander' AND _season = '2024-25'"
    )
    assert sql_covers(R507_HIST_EXPECTED, aliased_only)


R512_SCOPE_EXPECTED = (
    "SELECT PLAYER, TEAM, PPG FROM silver_player_season "
    "WHERE PLAYER = 'PlayerA' AND TEAM = 'BOS' AND _season = '2024-25'"
)
R512_SCOPE_ALIASED = (
    "SELECT PLAYER, TEAM, PPG, PPG AS \"PTS\" FROM silver_player_season "
    "WHERE PLAYER = 'PlayerA' AND TEAM = 'BOS' AND _season = '2024-25'"
)


@pytest.mark.parametrize("actual", [
    R512_SCOPE_EXPECTED.replace("'PlayerA'", "'playera'"),
    R512_SCOPE_EXPECTED.replace("'PlayerA'", "'PLAYERA'"),
    R512_SCOPE_EXPECTED.replace("'BOS'", "'bos'"),
    R512_SCOPE_EXPECTED.replace("'2024-25'", "'2024-25 '"),
])
def test_shared_sql_coverage_preserves_literal_values(actual: str) -> None:
    from v2.domain.sql_coverage import sql_covers

    assert not sql_covers(R512_SCOPE_EXPECTED, actual)


def test_shared_sql_coverage_projection_extension_preserves_literals() -> None:
    from v2.domain.sql_coverage import sql_covers

    assert sql_covers(R512_SCOPE_EXPECTED, R512_SCOPE_ALIASED)
    for actual in (
        R512_SCOPE_ALIASED.replace("'PlayerA'", "'playera'"),
        R512_SCOPE_ALIASED.replace("'BOS'", "'bos'"),
        R512_SCOPE_ALIASED.replace("'2024-25'", "'2024-25 '"),
    ):
        assert not sql_covers(R512_SCOPE_EXPECTED, actual)


def test_shared_sql_coverage_accepts_identifier_and_alias_case() -> None:
    from v2.domain.sql_coverage import sql_covers

    assert sql_covers(
        R512_SCOPE_EXPECTED,
        "select player, team, ppg from SILVER_PLAYER_SEASON "
        "where PLAYER = 'PlayerA' and team = 'BOS' and _season = '2024-25'",
    )
    # Added projection takes the fallback path; alias case is insignificant.
    assert sql_covers(
        R512_SCOPE_EXPECTED,
        "select player, team, ppg, ppg as pts from SILVER_PLAYER_SEASON "
        "where PLAYER = 'PlayerA' and team = 'BOS' and _season = '2024-25'",
    )


def test_shared_sql_coverage_keeps_regular_season_literal_normalization() -> None:
    from v2.domain.sql_coverage import sql_covers

    expected = (
        "SELECT COUNT(*) AS games, MAX(pts) AS best FROM silver_hist_gamelogs "
        "WHERE season_type = 'Regular Season' AND team_name = 'Boston Celtics'"
    )
    assert sql_covers(
        expected, expected.replace("'Regular Season'", "'regular-season'"))
    assert sql_covers(
        expected, expected.replace("'Regular Season'", "'REGULAR SEASON'"))


@pytest.fixture
def anyio_backend():
    return "asyncio"

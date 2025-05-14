# backend/smoke_tests/test_league_leaders.py
import sys
import os
import asyncio
import json
import logging
from typing import Callable, Any
import pytest # Import pytest

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.league_leaders_data import fetch_league_leaders_logic
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar, PerMode48, Scope, StatCategoryAbbreviation
from backend.config import settings

async def run_league_leaders_test_with_assertions(
    description: str,
    season: str, 
    stat_category: str,
    season_type: str,
    per_mode: str,
    scope: str,
    top_n: int,
    expect_api_error: bool = False,
    expect_empty_results_no_error: bool = False,
    league_id: str = LeagueID.nba # Default league_id
):
    test_name = description # Use the provided description directly
    logger.info(f"--- Testing {test_name} ---")
    
    params = {
        "season": season,
        "stat_category": stat_category,
        "season_type": season_type,
        "per_mode": per_mode,
        "league_id": league_id,
        "scope": scope,
        "top_n": top_n
    }

    result_json = await asyncio.to_thread(fetch_league_leaders_logic, **params)
    
    try:
        result_data = json.loads(result_json)
        # logger.debug(json.dumps(result_data, indent=2))
        
        if expect_api_error:
            assert "error" in result_data, f"Expected an API error for {test_name}, but got: {result_data}"
            logger.info(f"SUCCESS (expected API error): {test_name} - Error: {result_data['error']}")
        elif expect_empty_results_no_error:
            assert "error" not in result_data, f"Expected no error for empty results for {test_name}, but got error: {result_data.get('error')}"
            assert "leaders" in result_data, f"Expected key 'leaders' for empty results for {test_name}"
            assert isinstance(result_data["leaders"], list), f"Expected list for key 'leaders' for empty results for {test_name}"
            assert not result_data["leaders"], f"Expected empty list for key 'leaders' for empty results for {test_name}, but got {len(result_data['leaders'])} items."
            logger.info(f"SUCCESS (expected empty results): {test_name} - Found 0 leaders, as expected.")
        else:
            assert "error" not in result_data, f"Unexpected API error for {test_name}: {result_data.get('error')}"
            assert "leaders" in result_data, f"Expected key 'leaders' not found for {test_name}"
            assert isinstance(result_data["leaders"], list), f"Key 'leaders' should be a list for {test_name}"
            
            # For valid results, check if the number of leaders is <= top_n
            assert len(result_data["leaders"]) <= top_n, f"Expected at most {top_n} leaders, but got {len(result_data['leaders'])}"

            if result_data["leaders"]:
                logger.info(f"SUCCESS: {test_name} - Fetched league leaders. Count: {len(result_data['leaders'])}")
                sample_leader = result_data["leaders"][0]
                # Ensure the stat category key exists if leaders are present
                assert params['stat_category'] in sample_leader, f"Stat category '{params['stat_category']}' not in sample leader data for {test_name}"
                logger.info(f"  Sample Leader (Rank {sample_leader.get('RANK')}): {sample_leader.get('PLAYER')} with {sample_leader.get(params['stat_category'])} {params['stat_category']}")
            else:
                # This case implies valid params but API returned 0 leaders, less than top_n. This is okay.
                logger.info(f"SUCCESS: {test_name} - Fetched 0 league leaders (API returned empty list for valid params).")

    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for {test_name}: Could not decode JSON response: {result_json}")
        assert False, f"JSONDecodeError for {test_name}" # Fail test on JSON decode error
    logger.info("-" * 70)

CURRENT_SEASON = settings.CURRENT_NBA_SEASON
PAST_SEASON = "2022-23"

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description, season, stat_category, season_type, per_mode, scope, top_n, expect_api_error, expect_empty_results_no_error", 
    [
        ("Default PTS leaders, current season", CURRENT_SEASON, StatCategoryAbbreviation.pts, SeasonTypeAllStar.regular, PerMode48.per_game, Scope.s, 5, False, False),
        (f"{PAST_SEASON} AST Leaders, Top 3", PAST_SEASON, StatCategoryAbbreviation.ast, SeasonTypeAllStar.regular, PerMode48.per_game, Scope.s, 3, False, False),
        (f"{PAST_SEASON} REB Leaders, Playoffs, Top 5", PAST_SEASON, StatCategoryAbbreviation.reb, SeasonTypeAllStar.playoffs, PerMode48.per_game, Scope.s, 5, False, False),
        (f"{PAST_SEASON} Invalid StatCat", PAST_SEASON, "INVALID_STAT", SeasonTypeAllStar.regular, PerMode48.per_game, Scope.s, 5, True, False),
        ("Invalid Season Format", "2023", StatCategoryAbbreviation.pts, SeasonTypeAllStar.regular, PerMode48.per_game, Scope.s, 5, True, False),
        (f"{PAST_SEASON} Invalid PerMode", PAST_SEASON, StatCategoryAbbreviation.pts, SeasonTypeAllStar.regular, "InvalidMode", Scope.s, 5, True, False),
        # Add a case that might genuinely return an empty list for valid params, if known.
        # For example, a very obscure stat for a pre-season or a season with no games.
        # (f"{PAST_SEASON} Obscure Stat, PreSeason - Expect Empty", PAST_SEASON, StatCategoryAbbreviation.fouls, SeasonTypeAllStar.preseason, PerMode48.per_game, Scope.s, 5, False, True)
    ]
)
async def test_league_leaders_scenarios(description, season, stat_category, season_type, per_mode, scope, top_n, expect_api_error, expect_empty_results_no_error):
    await run_league_leaders_test_with_assertions(
        description=description,
        season=season,
        stat_category=stat_category,
        season_type=season_type,
        per_mode=per_mode,
        scope=scope,
        top_n=top_n,
        expect_api_error=expect_api_error,
        expect_empty_results_no_error=expect_empty_results_no_error
    )
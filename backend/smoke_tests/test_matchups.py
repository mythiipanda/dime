# backend/smoke_tests/test_matchups.py
import sys
import os
import asyncio
import json
import logging
from typing import Callable, Any # Added for type hints
import pytest # Import pytest

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.matchup_tools import fetch_league_season_matchups_logic, fetch_matchups_rollup_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar
from backend.config import settings

async def run_test_with_assertions(
    logic_function: Callable,
    description: str,
    expected_data_key: str, # 'matchups' or 'rollup'
    expect_api_error: bool = False,
    expect_empty_results_no_error: bool = False,
    **kwargs: Any
):
    test_name = description
    logger.info(f"--- Testing {test_name} ---")
    
    result_json = await asyncio.to_thread(logic_function, **kwargs)
    
    try:
        result_data = json.loads(result_json)
        # logger.debug(json.dumps(result_data, indent=2))
        
        if expect_api_error:
            assert "error" in result_data, f"Expected an API error for {test_name}, but got: {result_data}"
            logger.info(f"SUCCESS (expected API error): {test_name} - Error: {result_data.get('error')}")
        elif expect_empty_results_no_error:
            assert "error" not in result_data, f"Expected no error for empty results for {test_name}, but got error: {result_data.get('error')}"
            assert expected_data_key in result_data, f"Expected key '{expected_data_key}' for empty results for {test_name}"
            assert isinstance(result_data[expected_data_key], list), f"Expected list for key '{expected_data_key}' for empty results for {test_name}"
            assert not result_data[expected_data_key], f"Expected empty list for key '{expected_data_key}' for empty results for {test_name}, but got {len(result_data[expected_data_key])} items."
            logger.info(f"SUCCESS (expected empty results): {test_name} - Found 0 {expected_data_key}, as expected.")
        else:
            assert "error" not in result_data, f"Unexpected API error for {test_name}: {result_data.get('error')}"
            assert expected_data_key in result_data, f"Expected key '{expected_data_key}' not found for {test_name}"
            assert isinstance(result_data[expected_data_key], list), f"Key '{expected_data_key}' should be a list for {test_name}"
            
            if result_data[expected_data_key]:
                logger.info(f"SUCCESS: {test_name} - Fetched {expected_data_key}. Count: {len(result_data[expected_data_key])}")
                # logger.info(f"  Sample Data: {json.dumps(result_data[expected_data_key][0], indent=2)}") # Can be verbose
            else:
                logger.info(f"SUCCESS (No Data): {test_name} - No {expected_data_key} data found (empty list returned for valid params).")

    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for {test_name}: Could not decode JSON response: {result_json}")
        assert False, f"JSONDecodeError for {test_name}"
    logger.info("-" * 70)

CURRENT_SEASON = settings.CURRENT_NBA_SEASON
PAST_SEASON = "2022-23"

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description, def_player_identifier, off_player_identifier, season, season_type, expect_api_error, expect_empty_results_no_error",
    [
        ("LeBron vs Butler, Current Season", "LeBron James", "Jimmy Butler", CURRENT_SEASON, SeasonTypeAllStar.regular, False, False),
        (f"PlayerID 203999 vs 201939, {PAST_SEASON} Playoffs", "203999", "201939", PAST_SEASON, SeasonTypeAllStar.playoffs, False, False),
        ("Invalid Def Player vs Curry, Past Season", "Invalid Def Player XYZ", "Stephen Curry", PAST_SEASON, SeasonTypeAllStar.regular, True, False), # Player not found error
        ("LeBron vs Butler, Invalid Season Format", "LeBron James", "Jimmy Butler", "2023", SeasonTypeAllStar.regular, True, False), # Season format error
    ]
)
async def test_season_matchups_scenarios(description, def_player_identifier, off_player_identifier, season, season_type, expect_api_error, expect_empty_results_no_error):
    await run_test_with_assertions(
        fetch_league_season_matchups_logic,
        description=description,
        expected_data_key="matchups",
        expect_api_error=expect_api_error,
        expect_empty_results_no_error=expect_empty_results_no_error,
        def_player_identifier=def_player_identifier,
        off_player_identifier=off_player_identifier,
        season=season,
        season_type=season_type
    )

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description, def_player_identifier, season, season_type, expect_api_error, expect_empty_results_no_error",
    [
        ("Gobert Rollup, Current Season", "Rudy Gobert", CURRENT_SEASON, SeasonTypeAllStar.regular, False, False),
        (f"PlayerID 201939 Rollup, {PAST_SEASON} Playoffs", "201939", PAST_SEASON, SeasonTypeAllStar.playoffs, False, False),
        ("Invalid Player Rollup, Past Season", "Invalid Player XYZ", PAST_SEASON, SeasonTypeAllStar.regular, True, False), # Player not found error
        ("Gobert Rollup, Invalid Season Type (All-Star)", "Rudy Gobert", PAST_SEASON, SeasonTypeAllStar.all_star, True, False), # Endpoint may not support All-Star
    ]
)
async def test_matchups_rollup_scenarios(description, def_player_identifier, season, season_type, expect_api_error, expect_empty_results_no_error):
    await run_test_with_assertions(
        fetch_matchups_rollup_logic,
        description=description,
        expected_data_key="rollup",
        expect_api_error=expect_api_error,
        expect_empty_results_no_error=expect_empty_results_no_error,
        def_player_identifier=def_player_identifier,
        season=season,
        season_type=season_type
    )
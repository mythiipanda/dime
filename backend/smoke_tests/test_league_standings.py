# backend/smoke_tests/test_league_standings.py
import sys
import os
import asyncio
import json
import logging
from typing import Optional, Callable, Any # Added for type hints
import pytest # Import pytest

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Adjusted format
logger = logging.getLogger(__name__)

from backend.api_tools.league_standings import fetch_league_standings_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar 
from backend.config import settings # For settings.CURRENT_NBA_SEASON

async def run_standings_test_with_assertions(
    description: str,
    expect_api_error: bool = False,
    expect_empty_results_no_error: bool = False,
    **kwargs: Any # season, season_type passed here
):
    test_name = description
    logger.info(f"--- Testing {test_name} ---")
    
    # fetch_league_standings_logic uses its own defaults if season/season_type are None
    # So, we only pass them if they are explicitly provided for the test case.
    # The helper no longer needs to manage defaults for these, the API function does.

    result_json = await asyncio.to_thread(fetch_league_standings_logic, **kwargs)
    
    try:
        result_data = json.loads(result_json)
        expected_data_key = "standings"

        if expect_api_error:
            assert "error" in result_data, f"Expected an API error for {test_name}, but got: {result_data}"
            logger.info(f"SUCCESS (expected API error): {test_name} - Error: {result_data.get('error')}")
        elif expect_empty_results_no_error:
            assert "error" not in result_data, f"Expected no error for empty results for {test_name}, but got error: {result_data.get('error')}"
            assert expected_data_key in result_data, f"Expected key '{expected_data_key}' for empty results for {test_name}"
            assert isinstance(result_data[expected_data_key], list), f"Expected list for key '{expected_data_key}' for empty results for {test_name}"
            assert not result_data[expected_data_key], f"Expected empty list for '{expected_data_key}' for {test_name}, got {len(result_data[expected_data_key])} items."
            logger.info(f"SUCCESS (expected empty results): {test_name} - Found 0 {expected_data_key}, as expected.")
        else:
            assert "error" not in result_data, f"Unexpected API error for {test_name}: {result_data.get('error')}"
            assert expected_data_key in result_data, f"Expected key '{expected_data_key}' not found for {test_name}"
            assert isinstance(result_data[expected_data_key], list), f"Key '{expected_data_key}' should be a list for {test_name}"
            
            if result_data[expected_data_key]:
                logger.info(f"SUCCESS: {test_name} - Fetched {expected_data_key}. Teams found: {len(result_data[expected_data_key])}")
                # sample_team = result_data[expected_data_key][0]
                # logger.info(f"  Sample Team: {sample_team.get('TeamCity')} {sample_team.get('TeamName')}, Rank: {sample_team.get('PlayoffRank')}, GB: {sample_team.get('GB')}")
            else:
                # This is for cases where API returns empty list for valid params, e.g. playoffs if no playoff standings data for that season
                logger.info(f"SUCCESS (No Data): {test_name} - No {expected_data_key} data found (empty list returned for valid params).")

    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for {test_name}: Could not decode JSON response: {result_json}")
        assert False, f"JSONDecodeError for {test_name}"
    logger.info("-" * 70)

# Test Cases
PAST_SEASON_22_23 = "2022-23"

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description, season, season_type, expect_api_error, expect_empty_results_no_error",
    [
        ("Default Season/Type Standings", None, None, False, False),
        (f"{PAST_SEASON_22_23} Regular Season Standings", PAST_SEASON_22_23, SeasonTypeAllStar.regular, False, False),
        # For playoffs, the API returns an error as it's not a supported season_type for this endpoint.
        (f"{PAST_SEASON_22_23} Playoffs Standings", PAST_SEASON_22_23, SeasonTypeAllStar.playoffs, True, False), 
        ("Invalid Season Format Standings", "2023", SeasonTypeAllStar.regular, True, False),
        ("Invalid Season Type Standings", PAST_SEASON_22_23, "InvalidSeasonType", True, False),
    ]
)
async def test_standings_scenarios(description, season, season_type, expect_api_error, expect_empty_results_no_error):
    kwargs = {}
    if season is not None:
        kwargs['season'] = season
    if season_type is not None:
        kwargs['season_type'] = season_type

    await run_standings_test_with_assertions(
        description=description,
        expect_api_error=expect_api_error,
        expect_empty_results_no_error=expect_empty_results_no_error,
        **kwargs
    )
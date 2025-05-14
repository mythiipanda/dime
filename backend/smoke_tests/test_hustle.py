# test_hustle.py
import sys
import os
import asyncio
import json
import logging
from typing import Optional, Callable, Any
import pytest

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.player_dashboard_stats import fetch_player_hustle_stats_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeTime
from backend.config import settings

async def run_hustle_stats_test_with_assertions(
    description: str,
    expect_api_error: bool = False,
    expect_empty_results_no_error: bool = False,
    **kwargs: Any
):
    test_name = description
    logger.info(f"--- Testing {test_name} ---")
    
    # Ensure common params like season, season_type, per_mode are defaulted if not explicitly passed for a test case
    # These defaults align with how fetch_player_hustle_stats_logic itself defaults them if not provided by caller.
    kwargs.setdefault("season", kwargs.get("season", settings.CURRENT_NBA_SEASON)) # Allow overriding season per test
    kwargs.setdefault("season_type", kwargs.get("season_type", SeasonTypeAllStar.regular))
    kwargs.setdefault("per_mode", kwargs.get("per_mode", PerModeTime.per_game)) # Correct default for hustle

    # The logic_function is always fetch_player_hustle_stats_logic
    result_json = await asyncio.to_thread(fetch_player_hustle_stats_logic, **kwargs)
    
    try:
        result_data = json.loads(result_json)
        expected_data_key = "hustle_stats"

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
            
            # If data is expected and list is not empty, it implies success.
            # Further checks on content can be added if needed but for smoke, presence and type is often enough.
            if result_data[expected_data_key]:
                logger.info(f"SUCCESS: {test_name} - Fetched {expected_data_key}. Count: {len(result_data[expected_data_key])}")
            else:
                # This can be a valid case: API call is fine, params are fine, but no data for this specific query (e.g. player with no hustle stats)
                logger.info(f"SUCCESS (No Data): {test_name} - No {expected_data_key} data found (empty list returned for valid params).")

    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for {test_name}: Could not decode JSON response: {result_json}")
        assert False, f"JSONDecodeError for {test_name}"
    logger.info("-" * 70)

# Test Cases
SEASON_23_24 = "2023-24"

@pytest.mark.asyncio
async def test_hustle_stats_by_player_caruso():
    await run_hustle_stats_test_with_assertions(
        description=f"Hustle Stats for Player: Alex Caruso ({SEASON_23_24})",
        player_name="Alex Caruso",
        season=SEASON_23_24
        # per_mode, season_type will use defaults from helper which match original test
    )

@pytest.mark.asyncio
async def test_hustle_stats_by_team_bulls():
    await run_hustle_stats_test_with_assertions(
        description=f"Hustle Stats for Team ID: 1610612741 ({SEASON_23_24})",
        team_id=1610612741, # Chicago Bulls
        season=SEASON_23_24
    )

@pytest.mark.asyncio
async def test_hustle_stats_league_wide():
    await run_hustle_stats_test_with_assertions(
        description=f"League-Wide Hustle Stats ({SEASON_23_24})",
        season=SEASON_23_24
        # player_name and team_id are omitted for league-wide
    )

@pytest.mark.asyncio
async def test_hustle_stats_invalid_player():
    await run_hustle_stats_test_with_assertions(
        description=f"Hustle Stats for Invalid Player ({SEASON_23_24})",
        player_name="Invalid Player Name XYZ",
        season=SEASON_23_24,
        expect_api_error=True, # Corrected: Expect an API error for an invalid player
        expect_empty_results_no_error=False 
    )
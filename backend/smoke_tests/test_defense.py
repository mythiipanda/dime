# test_defense.py
import asyncio
import json
import os # Add os
import sys # Add sys
import logging # Add logging
from typing import Any, Dict # Add typing
import pytest # Import pytest

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Adjusted format
logger = logging.getLogger(__name__)

from backend.api_tools.player_dashboard_stats import fetch_player_defense_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple, PerModeTime

VALID_PLAYER = "Rudy Gobert"
VALID_SEASON = "2023-24"
INVALID_PLAYER = "Invalid Player Name XYZ"
INVALID_SEASON_FORMAT = "2023"
INVALID_SEASON_TYPE = "InvalidSeasonType"

EXPECTED_DETAILS_KEY = "detailed_defense_stats_by_category" # Corrected key

# Enhanced helper with assertions
async def run_defense_test_with_assertions(
    description: str,
    player_name: str,
    season: str,
    season_type: str,
    per_mode: str = PerModeTime.per_game, # Default to PerGame as in original logic if not specified
    expect_api_error: bool = False,
    expect_empty_details_no_error: bool = False # For cases where summary might exist but details are empty
):
    test_name = f"{description} (Player: {player_name}, Season: {season}, Type: {season_type}, Mode: {per_mode})"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json = await asyncio.to_thread(
        fetch_player_defense_logic,
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    
    try:
        result_data = json.loads(result_json)
        # logger.debug(json.dumps(result_data, indent=2))
        
        if expect_api_error:
            assert "error" in result_data, f"Expected an API error for {test_name}, but got: {result_data}"
            logger.info(f"SUCCESS (expected API error): {test_name} - Error: {result_data.get('error')}")
        elif expect_empty_details_no_error:
            assert "error" not in result_data, f"Expected no error for empty details for {test_name}, but got error: {result_data.get('error')}"
            assert "summary" in result_data, f"Expected key 'summary' for empty details case for {test_name}"
            assert EXPECTED_DETAILS_KEY in result_data, f"Expected key '{EXPECTED_DETAILS_KEY}' for empty details case for {test_name}"
            assert isinstance(result_data[EXPECTED_DETAILS_KEY], list), f"Expected list for '{EXPECTED_DETAILS_KEY}' for {test_name}"
            assert not result_data[EXPECTED_DETAILS_KEY], f"Expected empty list for '{EXPECTED_DETAILS_KEY}' for {test_name}, but got {len(result_data[EXPECTED_DETAILS_KEY])} items."
            logger.info(f"SUCCESS (expected empty details): {test_name} - Summary present, details empty as expected.")
        else:
            assert "error" not in result_data, f"Unexpected API error for {test_name}: {result_data.get('error')}"
            assert "summary" in result_data, f"Expected key 'summary' not found for {test_name}"
            assert isinstance(result_data["summary"], dict), f"Key 'summary' should be a dict for {test_name}"
            assert EXPECTED_DETAILS_KEY in result_data, f"Expected key '{EXPECTED_DETAILS_KEY}' not found for {test_name}"
            assert isinstance(result_data[EXPECTED_DETAILS_KEY], list), f"Key '{EXPECTED_DETAILS_KEY}' should be a list for {test_name}"
            
            assert result_data[EXPECTED_DETAILS_KEY], f"Expected non-empty list for '{EXPECTED_DETAILS_KEY}' for {test_name}"
            logger.info(f"SUCCESS: {test_name} - Fetched. Summary GP: {result_data['summary'].get('games_played')}, Details records: {len(result_data[EXPECTED_DETAILS_KEY])}")

    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for {test_name}: Could not decode JSON response: {result_json}")
        assert False, f"JSONDecodeError for {test_name}"
    logger.info("-" * 70)

# Parametrized test function
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description, player_name, season, season_type, per_mode, expect_api_error, expect_empty_details",
    [
        ("Default PerMode (PerGame)", VALID_PLAYER, VALID_SEASON, SeasonTypeAllStar.regular, PerModeTime.per_game, False, False),
        ("Totals PerMode", VALID_PLAYER, VALID_SEASON, SeasonTypeAllStar.regular, PerModeSimple.totals, False, False),
        ("Invalid Player", INVALID_PLAYER, VALID_SEASON, SeasonTypeAllStar.regular, PerModeTime.per_game, True, False),
        ("Invalid Season Format", VALID_PLAYER, INVALID_SEASON_FORMAT, SeasonTypeAllStar.regular, PerModeTime.per_game, True, False),
        ("Invalid Season Type", VALID_PLAYER, VALID_SEASON, INVALID_SEASON_TYPE, PerModeTime.per_game, True, False),
        # Add a case that might return empty details but valid summary (e.g., player with 0 games played in a valid season)
        # This depends on API behavior; for now, assuming valid scenarios have details.
    ]
)
async def test_player_defense_scenarios(description, player_name, season, season_type, per_mode, expect_api_error, expect_empty_details):
    await run_defense_test_with_assertions(
        description=description,
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        expect_api_error=expect_api_error,
        expect_empty_details_no_error=expect_empty_details
    )
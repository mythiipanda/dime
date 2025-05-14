# backend/smoke_tests/test_player_rebounding.py
import sys
import os
import asyncio
import json
import logging
from typing import Dict, Any
import pytest

# Add the project root to sys.path to allow absolute imports like 'from backend...'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.player_rebounding import fetch_player_rebounding_stats_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

# Test constants
VALID_PLAYER_JOKIC = "Nikola Jokic"
VALID_PLAYER_CURRY = "Stephen Curry"
VALID_PLAYER_LEBRON = "LeBron James"
HISTORICAL_PLAYER_MJ = "Michael Jordan"
INVALID_PLAYER_NAME = "Invalid Player XYZ"

CURRENT_SEASON = "2023-24" # Assuming this is current for tests
PAST_SEASON_22_23 = "2022-23"
INVALID_SEASON_FORMAT = "2023"
INVALID_PER_MODE = "PerMinute"

async def run_rebounding_test_with_assertions(
    description: str,
    expect_api_error: bool = False,
    expect_empty_results_no_error: bool = False,
    **kwargs: Any
):
    test_name = f"Player Rebounding Stats - {description}"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json_str = await asyncio.to_thread(fetch_player_rebounding_stats_logic, **kwargs)
    result_data = json.loads(result_json_str)
    # logger.debug(f"Full API Response for {test_name}: {json.dumps(result_data, indent=2)}")

    if expect_api_error:
        assert "error" in result_data, f"Expected API error for '{description}', but 'error' key missing. Response: {result_data}"
        # For API errors, specific data keys might be absent or present with error indicators
        logger.info(f"SUCCESS (expected API error for '{description}'): {result_data.get('error')}")
    elif expect_empty_results_no_error:
        assert "error" not in result_data, f"Expected no error for empty results for '{description}', but got: {result_data.get('error')}"
        assert "overall" in result_data and result_data["overall"] == {}, \
            f"Expected 'overall' to be an empty dict for '{description}'. Response: {result_data}"
        assert "by_shot_type" in result_data and isinstance(result_data["by_shot_type"], list) and not result_data["by_shot_type"], \
            f"Expected 'by_shot_type' to be an empty list for '{description}'. Response: {result_data}"
        logger.info(f"SUCCESS (expected empty results, no error for '{description}').")
    else: # Expect successful data
        assert "error" not in result_data, f"Expected successful data for '{description}', but got error: {result_data.get('error')}"
        assert "overall" in result_data and isinstance(result_data["overall"], dict), \
            f"'overall' key missing or not a dict for '{description}'. Response: {result_data}"
        assert "by_shot_type" in result_data and isinstance(result_data["by_shot_type"], list), \
            f"'by_shot_type' key missing or not a list for '{description}'. Response: {result_data}"
        
        # If overall has data, check for expected keys
        if result_data["overall"]:
            assert "G" in result_data["overall"], f"Expected 'G' key in 'overall' stats for '{description}'. Got: {result_data['overall']}"
            assert "REB" in result_data["overall"], f"Expected 'REB' key in 'overall' stats for '{description}'. Got: {result_data['overall']}"
        # else: # overall can be empty for a valid player if they have no stats for the filter
            # logger.warning(f"'overall' dict is empty for '{description}', but not expecting empty results flag. This might be valid.")

        logger.info(f"SUCCESS for '{description}': Fetched data. Overall G: {result_data['overall'].get('G')}, REB: {result_data['overall'].get('REB')}")

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description_suffix, params, expect_error, expect_empty",
    [
        (
            "Nikola Jokic, Current Season Regular, PerGame",
            {"player_name": VALID_PLAYER_JOKIC, "season": CURRENT_SEASON, "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game},
            False, False
        ),
        (
            "Stephen Curry, Past Season Playoffs, Totals",
            {"player_name": VALID_PLAYER_CURRY, "season": PAST_SEASON_22_23, "season_type": SeasonTypeAllStar.playoffs, "per_mode": PerModeSimple.totals},
            False, False 
        ),
        (
            "Michael Jordan, Current Season (Error Expected)",
            {"player_name": HISTORICAL_PLAYER_MJ, "season": CURRENT_SEASON, "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game},
            False, True # Corrected: Expect empty results, not an API error
        ),
        (
            "LeBron James, Invalid Season Format",
            {"player_name": VALID_PLAYER_LEBRON, "season": INVALID_SEASON_FORMAT, "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game},
            True, False
        ),
        (
            "LeBron James, Invalid PerMode",
            {"player_name": VALID_PLAYER_LEBRON, "season": CURRENT_SEASON, "season_type": SeasonTypeAllStar.regular, "per_mode": INVALID_PER_MODE},
            True, False
        ),
        # Add a case that might genuinely return empty data for a valid player
        (
            "Stephen Curry, Current Season Playoffs (if not yet started/no games)",
            {"player_name": VALID_PLAYER_CURRY, "season": CURRENT_SEASON, "season_type": SeasonTypeAllStar.playoffs, "per_mode": PerModeSimple.totals},
            False, True # Assuming playoffs might not have data yet or player didn't play
        ),
    ]
)
async def test_player_rebounding_scenarios(description_suffix: str, params: Dict[str, Any], expect_error: bool, expect_empty: bool):
    await run_rebounding_test_with_assertions(
        description=description_suffix,
        expect_api_error=expect_error,
        expect_empty_results_no_error=expect_empty,
        **params
    )
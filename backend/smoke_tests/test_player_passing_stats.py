import asyncio
import json
import logging
import os
import sys
from typing import Dict, Any
import pytest

# Ensure the project root is in the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.api_tools.player_passing import fetch_player_passing_stats_logic
from backend.config import settings
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test constants
VALID_PLAYER_JOKIC = "Nikola Jokic"
VALID_PLAYER_TRAE = "Trae Young"
INVALID_PLAYER_NAME = "NonExistent PlayerXYZ"
VALID_SEASON_23_24 = "2023-24"
VALID_SEASON_22_23 = "2022-23"
INVALID_SEASON_FORMAT = "2023"

async def run_player_passing_test_with_assertions(
    description: str,
    expect_api_error: bool = False,
    expect_empty_results_no_error: bool = False,
    **kwargs: Any
):
    test_name = f"Player Passing Stats - {description}"
    logger.info(f"--- Testing {test_name} ---")

    result_json_str = await asyncio.to_thread(fetch_player_passing_stats_logic, **kwargs)
    result_data = json.loads(result_json_str)
    # logger.debug(f"Full API Response for {test_name}: {json.dumps(result_data, indent=2)}")

    if expect_api_error:
        assert "error" in result_data, f"Expected API error, but 'error' key missing. Response: {result_data}"
        assert "passes_made" not in result_data, f"Expected no 'passes_made' on API error. Response: {result_data}"
        assert "passes_received" not in result_data, f"Expected no 'passes_received' on API error. Response: {result_data}"
        logger.info(f"SUCCESS (expected API error): {result_data.get('error')}")
    elif expect_empty_results_no_error:
        assert "error" not in result_data, f"Expected no error for empty results, but got: {result_data.get('error')}"
        assert "passes_made" in result_data and isinstance(result_data["passes_made"], list) and not result_data["passes_made"], \
            f"Expected 'passes_made' to be an empty list. Response: {result_data}"
        assert "passes_received" in result_data and isinstance(result_data["passes_received"], list) and not result_data["passes_received"], \
            f"Expected 'passes_received' to be an empty list. Response: {result_data}"
        logger.info("SUCCESS (expected empty results, no error).")
    else: # Expect successful data
        assert "error" not in result_data, f"Expected successful data, but got error: {result_data.get('error')}"
        assert "passes_made" in result_data and isinstance(result_data["passes_made"], list), \
            f"'passes_made' key missing or not a list. Response: {result_data}"
        assert "passes_received" in result_data and isinstance(result_data["passes_received"], list), \
            f"'passes_received' key missing or not a list. Response: {result_data}"
        
        # It's possible a player has no recorded passes for a specific filter, so an empty list is valid success.
        # We can check for structure if data is present.
        if result_data["passes_made"]:
            assert "PASS_TO" in result_data["passes_made"][0], f"Expected 'PASS_TO' key in passes_made items. Got: {result_data['passes_made'][0]}"
        if result_data["passes_received"]:
            assert "PASS_FROM" in result_data["passes_received"][0], f"Expected 'PASS_FROM' key in passes_received items. Got: {result_data['passes_received'][0]}"
            
        logger.info(f"SUCCESS: Fetched data. Passes Made: {len(result_data['passes_made'])}, Passes Received: {len(result_data['passes_received'])}")

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description, params, expect_error, expect_empty",
    [
        (
            "Nikola Jokic, 2023-24 Regular Season, PerGame", 
            {"player_name": VALID_PLAYER_JOKIC, "season": VALID_SEASON_23_24, "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game},
            False, False
        ),
        (
            "Trae Young, 2022-23 Playoffs, Totals", 
            {"player_name": VALID_PLAYER_TRAE, "season": VALID_SEASON_22_23, "season_type": SeasonTypeAllStar.playoffs, "per_mode": PerModeSimple.totals},
            False, False 
        ),
        # Test for a player who might have no playoff data for a season they didn't make playoffs
        (
            "Nikola Jokic, 2022-23 (Made Playoffs but test with Playoffs filter, could be empty)",
            {"player_name": VALID_PLAYER_JOKIC, "season": VALID_SEASON_22_23, "season_type": SeasonTypeAllStar.playoffs, "per_mode": PerModeSimple.totals},
            False, False # Expect data as Jokic played in 22-23 playoffs. If API returns empty, this might need to be expect_empty=True
        ),
        (
            "NonExistent Player", 
            {"player_name": INVALID_PLAYER_NAME, "season": VALID_SEASON_23_24, "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game},
            True, False # Expect API error due to invalid player
        ),
        (
            "Invalid Season Format", 
            {"player_name": VALID_PLAYER_JOKIC, "season": INVALID_SEASON_FORMAT, "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game},
            True, False # Expect API error due to invalid season format
        ),
    ]
)
async def test_player_passing_scenarios(description: str, params: Dict[str, Any], expect_error: bool, expect_empty: bool):
    await run_player_passing_test_with_assertions(
        description=description,
        expect_api_error=expect_error,
        expect_empty_results_no_error=expect_empty,
        **params
    )
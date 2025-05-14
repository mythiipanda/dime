# backend/smoke_tests/test_player_shooting_tracking.py
import sys
import os
import asyncio
import json
import logging
from typing import Dict, Any
import pytest

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.player_shooting_tracking import fetch_player_shots_tracking_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

# Test constants
VALID_PLAYER_KD = "Kevin Durant"
VALID_PLAYER_BOL = "Bol Bol"
VALID_PLAYER_LEBRON = "LeBron James"
INVALID_PLAYER_NAME = "Invalid Player XYZ"

CURRENT_SEASON = "2023-24"
INVALID_PER_MODE = "PerMinute"

# Expected data keys in the response for shooting tracking
SHOOTING_DATA_KEYS = [
    "general_shooting", "by_shot_clock", "by_dribble_count", 
    "by_touch_time", "by_defender_distance", "by_defender_distance_10ft_plus"
]

async def run_shooting_tracking_test_with_assertions(
    description: str,
    expect_api_error: bool = False,
    expect_empty_results_no_error: bool = False,
    **kwargs: Any
):
    test_name = f"Player Shooting Tracking - {description}"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json_str = await asyncio.to_thread(fetch_player_shots_tracking_logic, **kwargs)
    result_data = json.loads(result_json_str)
    # logger.debug(f"Full API Response for {test_name}: {json.dumps(result_data, indent=2)}")

    if expect_api_error:
        assert "error" in result_data, f"Expected API error for '{description}', but 'error' key missing. Response: {result_data}"
        # Optionally check that data keys are absent or empty if API includes them on error
        for key in SHOOTING_DATA_KEYS:
            assert key not in result_data or not result_data[key], \
                f"Expected data key '{key}' to be absent or empty on API error for '{description}'. Response: {result_data}"
        logger.info(f"SUCCESS (expected API error for '{description}'): {result_data.get('error')}")
    elif expect_empty_results_no_error:
        assert "error" not in result_data, f"Expected no error for empty results for '{description}', but got: {result_data.get('error')}"
        for key in SHOOTING_DATA_KEYS:
            assert key in result_data and isinstance(result_data[key], list) and not result_data[key], \
                f"Expected data key '{key}' to be an empty list for '{description}'. Response: {result_data}"
        logger.info(f"SUCCESS (expected empty results, no error for '{description}').")
    else: # Expect successful data
        assert "error" not in result_data, f"Expected successful data for '{description}', but got error: {result_data.get('error')}"
        for key in SHOOTING_DATA_KEYS:
            assert key in result_data and isinstance(result_data[key], list), \
                f"Data key '{key}' missing or not a list for '{description}'. Response: {result_data}"
        
        # If general_shooting has data, check its structure
        if result_data.get("general_shooting"):
            assert "SHOT_TYPE" in result_data["general_shooting"][0], \
                f"Expected 'SHOT_TYPE' key in 'general_shooting' items for '{description}'. Got: {result_data['general_shooting'][0]}"
        # else: # It's possible even general_shooting is empty for a valid player if they took no shots
            # logger.warning(f"'general_shooting' is empty for '{description}', but not expecting fully empty results. This might be valid.")

        logger.info(f"SUCCESS for '{description}': Fetched data. General entries: {len(result_data.get('general_shooting', []))}")

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description_suffix, params, expect_error, expect_empty",
    [
        (
            "Kevin Durant, Current Season, Totals",
            {"player_name": VALID_PLAYER_KD, "season": CURRENT_SEASON, "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.totals},
            False, False
        ),
        (
            "Kevin Durant, Current Season, PerGame",
            {"player_name": VALID_PLAYER_KD, "season": CURRENT_SEASON, "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game},
            False, False
        ),
        (
            "Bol Bol, Current Season, PerGame (might be sparse data)",
            {"player_name": VALID_PLAYER_BOL, "season": CURRENT_SEASON, "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game},
            False, False # Expect some data, even if lists are short
        ),
        (
            "LeBron James, Invalid PerMode",
            {"player_name": VALID_PLAYER_LEBRON, "season": CURRENT_SEASON, "season_type": SeasonTypeAllStar.regular, "per_mode": INVALID_PER_MODE},
            True, False
        ),
        (
            "Invalid Player Name",
            {"player_name": INVALID_PLAYER_NAME, "season": CURRENT_SEASON, "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game},
            True, False # Should be an error from player lookup first
        )
    ]
)
async def test_player_shooting_tracking_scenarios(description_suffix: str, params: Dict[str, Any], expect_error: bool, expect_empty: bool):
    await run_shooting_tracking_test_with_assertions(
        description=description_suffix,
        expect_api_error=expect_error,
        expect_empty_results_no_error=expect_empty,
        **params
    )
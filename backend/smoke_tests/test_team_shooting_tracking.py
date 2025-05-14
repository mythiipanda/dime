# backend/smoke_tests/test_team_shooting_tracking.py
import sys
import os
import asyncio
import json
import logging
from typing import Dict, Any 
import pytest 

# Ensure the project root is in the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.api_tools.team_shooting_tracking import fetch_team_shooting_stats_logic
from backend.config import settings 
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test Constants
TEAM_ABBREV_LAL = "LAL"
TEAM_ABBREV_BOS = "BOS"
INVALID_TEAM_IDENTIFIER = "NonExistent TeamXYZ"
VALID_SEASON_23_24 = "2023-24"
VALID_SEASON_22_23 = "2022-23"
INVALID_SEASON_FORMAT = "2023"
INVALID_SEASON_TYPE = "InvalidType"
INVALID_PER_MODE = "InvalidPerMode"

# Expected data keys in the response
SHOOTING_OVERALL_KEY = "overall_shooting"
SHOOTING_DATA_KEYS_LISTS = [
    "general_shooting_splits", "by_shot_clock", "by_dribble", 
    "by_defender_distance", "by_touch_time"
]

async def run_team_shooting_test_with_assertions(
    description: str,
    expect_api_error: bool = False,
    expect_empty_results_no_error: bool = False,
    **kwargs: Any
):
    test_name = f"Team Shooting Stats - {description}"
    logger.info(f"--- Testing {test_name} ---")
    
    # Default opponent_team_id if not provided, as the logic might expect it
    if 'opponent_team_id' not in kwargs:
        kwargs['opponent_team_id'] = 0

    result_json_str = await asyncio.to_thread(fetch_team_shooting_stats_logic, **kwargs)
    result_data = json.loads(result_json_str)
    # logger.debug(f"Full API Response for {test_name}: {json.dumps(result_data, indent=2)}")

    if expect_api_error:
        assert "error" in result_data, f"Expected API error for '{description}', but 'error' key missing. Response: {result_data}"
        assert SHOOTING_OVERALL_KEY not in result_data or not result_data.get(SHOOTING_OVERALL_KEY), \
             f"Expected '{SHOOTING_OVERALL_KEY}' to be absent or empty on API error for '{description}'. Response: {result_data}"
        for key in SHOOTING_DATA_KEYS_LISTS:
            assert key not in result_data or not result_data.get(key), \
                f"Expected data key '{key}' to be absent or empty on API error for '{description}'. Response: {result_data}"
        logger.info(f"SUCCESS (expected API error for '{description}'): {result_data.get('error')}")
    elif expect_empty_results_no_error:
        assert "error" not in result_data, f"Expected no error for empty results for '{description}', but got: {result_data.get('error')}"
        assert SHOOTING_OVERALL_KEY in result_data and isinstance(result_data[SHOOTING_OVERALL_KEY], dict) and not result_data[SHOOTING_OVERALL_KEY], \
            f"Expected '{SHOOTING_OVERALL_KEY}' to be an empty dict for '{description}'. Response: {result_data}" 
        for key in SHOOTING_DATA_KEYS_LISTS:
            assert key in result_data and isinstance(result_data[key], list) and not result_data[key], \
                f"Expected data key '{key}' to be an empty list for '{description}'. Response: {result_data}"
        logger.info(f"SUCCESS (expected empty results, no error for '{description}').")
    else: # Expect successful data
        assert "error" not in result_data, f"Expected successful data for '{description}', but got error: {result_data.get('error')}"
        assert SHOOTING_OVERALL_KEY in result_data and isinstance(result_data[SHOOTING_OVERALL_KEY], dict), \
            f"'{SHOOTING_OVERALL_KEY}' key missing or not a dict for '{description}'. Response: {result_data}"
        for key in SHOOTING_DATA_KEYS_LISTS:
            assert key in result_data and isinstance(result_data[key], list), \
                f"Data key '{key}' missing or not a list for '{description}'. Response: {result_data}"
        
        if result_data[SHOOTING_OVERALL_KEY]: # Check if overall_shooting has data
            assert result_data[SHOOTING_OVERALL_KEY].get("TEAM_ID") or result_data[SHOOTING_OVERALL_KEY].get("TEAM_NAME"), \
                f"'TEAM_ID' or 'TEAM_NAME' missing in '{SHOOTING_OVERALL_KEY}' for '{description}'"
            assert "FGA_FREQUENCY" in result_data[SHOOTING_OVERALL_KEY], f"'FGA_FREQUENCY' missing in '{SHOOTING_OVERALL_KEY}' for '{description}'"
        # else: # Overall can be empty if team had no games/stats for the filter
            # logger.warning(f"'{SHOOTING_OVERALL_KEY}' is empty for '{description}', but not expecting fully empty results. This might be valid.")
            
        logger.info(f"SUCCESS for '{description}': Fetched data. Overall FGA_FREQ: {result_data[SHOOTING_OVERALL_KEY].get('FGA_FREQUENCY')}, General Splits: {len(result_data.get('general_shooting_splits',[]))}")

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description_suffix, params, expect_error, expect_empty",
    [
        (
            "LAL, 2023-24 Regular Season, PerGame", 
            {"team_identifier": TEAM_ABBREV_LAL, "season": VALID_SEASON_23_24, "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game},
            False, False
        ),
        (
            "BOS, 2022-23 Playoffs, Totals", 
            {"team_identifier": TEAM_ABBREV_BOS, "season": VALID_SEASON_22_23, "season_type": SeasonTypeAllStar.playoffs, "per_mode": PerModeSimple.totals},
            False, False 
        ),
        (
            "NonExistent Team", 
            {"team_identifier": INVALID_TEAM_IDENTIFIER, "season": VALID_SEASON_23_24, "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game},
            True, False 
        ),
        (
            "Invalid Season Format", 
            {"team_identifier": TEAM_ABBREV_LAL, "season": INVALID_SEASON_FORMAT, "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game},
            True, False
        ),
        (
            "Invalid Season Type",
            {"team_identifier": TEAM_ABBREV_LAL, "season": VALID_SEASON_23_24, "season_type": INVALID_SEASON_TYPE, "per_mode": PerModeSimple.per_game},
            True, False
        ),
        (
            "Invalid PerMode",
            {"team_identifier": TEAM_ABBREV_LAL, "season": VALID_SEASON_23_24, "season_type": SeasonTypeAllStar.regular, "per_mode": INVALID_PER_MODE},
            True, False
        ),
    ]
)
async def test_team_shooting_scenarios(description_suffix: str, params: Dict[str, Any], expect_error: bool, expect_empty: bool):
    await run_team_shooting_test_with_assertions(
        description=description_suffix,
        expect_api_error=expect_error,
        expect_empty_results_no_error=expect_empty,
        **params
    )
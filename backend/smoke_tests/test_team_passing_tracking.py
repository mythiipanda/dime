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

from backend.api_tools.team_passing_tracking import fetch_team_passing_stats_logic
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

async def run_team_passing_test_with_assertions(
    description: str,
    expect_api_error: bool = False,
    expect_empty_results_no_error: bool = False,
    **kwargs: Any
):
    test_name = f"Team Passing Stats - {description}"
    logger.info(f"--- Testing {test_name} ---")

    result_json_str = await asyncio.to_thread(fetch_team_passing_stats_logic, **kwargs)
    result_data = json.loads(result_json_str)
    # logger.debug(f"Full API Response for {test_name}: {json.dumps(result_data, indent=2)}")

    if expect_api_error:
        assert "error" in result_data, f"Expected API error for '{description}', but 'error' key missing. Response: {result_data}"
        assert "passes_made" not in result_data or not result_data["passes_made"], \
            f"Expected 'passes_made' to be absent or empty on API error for '{description}'. Response: {result_data}"
        assert "passes_received" not in result_data or not result_data["passes_received"], \
            f"Expected 'passes_received' to be absent or empty on API error for '{description}'. Response: {result_data}"
        logger.info(f"SUCCESS (expected API error for '{description}'): {result_data.get('error')}")
    elif expect_empty_results_no_error:
        assert "error" not in result_data, f"Expected no error for empty results for '{description}', but got: {result_data.get('error')}"
        assert "passes_made" in result_data and isinstance(result_data["passes_made"], list) and not result_data["passes_made"], \
            f"Expected 'passes_made' to be an empty list for '{description}'. Response: {result_data}"
        assert "passes_received" in result_data and isinstance(result_data["passes_received"], list) and not result_data["passes_received"], \
            f"Expected 'passes_received' to be an empty list for '{description}'. Response: {result_data}"
        logger.info(f"SUCCESS (expected empty results, no error for '{description}').")
    else: # Expect successful data
        assert "error" not in result_data, f"Expected successful data for '{description}', but got error: {result_data.get('error')}"
        assert "passes_made" in result_data and isinstance(result_data["passes_made"], list), \
            f"'passes_made' key missing or not a list for '{description}'. Response: {result_data}"
        assert "passes_received" in result_data and isinstance(result_data["passes_received"], list), \
            f"'passes_received' key missing or not a list for '{description}'. Response: {result_data}"
        
        if result_data["passes_made"]:
            assert "PASS_FROM" in result_data["passes_made"][0], f"Expected 'PASS_FROM' key in passes_made items for '{description}'. Got: {result_data['passes_made'][0]}"
        if result_data["passes_received"]:
            assert "PASS_TO" in result_data["passes_received"][0], f"Expected 'PASS_TO' key in passes_received items for '{description}'. Got: {result_data['passes_received'][0]}"
            
        logger.info(f"SUCCESS for '{description}': Fetched data. Passes Made: {len(result_data['passes_made'])}, Passes Received: {len(result_data['passes_received'])}")

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
async def test_team_passing_scenarios(description_suffix: str, params: Dict[str, Any], expect_error: bool, expect_empty: bool):
    await run_team_passing_test_with_assertions(
        description=description_suffix,
        expect_api_error=expect_error,
        expect_empty_results_no_error=expect_empty,
        **params
    ) 
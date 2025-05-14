# backend/smoke_tests/test_analyze_logic.py
import sys
import os
import asyncio
import json
import logging
from typing import Optional, Any, Dict # Added for type hints
import pytest # Import pytest

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Adjusted format
logger = logging.getLogger(__name__)

from backend.api_tools.analyze import analyze_player_stats_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed # LeagueID not used directly here
from backend.config import settings

# Constants for testing
VALID_PLAYER_LEBRON = "LeBron James"
VALID_PLAYER_CURRY = "Stephen Curry"
VALID_PLAYER_JOKIC = "Nikola Jokic"
INVALID_PLAYER_NAME = "Invalid Player Name XYZ"
# Use a known past season for reliable data, and a potentially future season for other tests
PAST_SEASON = "2022-23"
CURRENT_SEASON = settings.CURRENT_NBA_SEASON # e.g., "2023-24" or "2024-25" if set for future
VALID_PER_MODE_TOTALS = PerModeDetailed.totals
INVALID_SEASON_FORMAT = "2023" # Incorrect format
INVALID_SEASON_LOGICALLY = "1950-51" # Too old for this specific detailed dashboard likely
INVALID_PER_MODE = "InvalidPerMode"

# Helper with assertions
async def run_analyze_test_with_assertions(
    description: str,
    expect_api_error: bool = False,
    expect_no_data_success: bool = False, # For valid call but empty overall_dashboard_stats dict
    **kwargs: Any
):
    filters_str = ", ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    test_name = f"Analyze Player Stats ({filters_str}) - {description}"
    logger.info(f"--- Testing {test_name} ---")
    
    # Set default season if not provided, as logic might rely on it from settings
    if 'season' not in kwargs or kwargs['season'] is None:
        kwargs['season'] = CURRENT_SEASON
        logger.info(f"Defaulting to current season: {CURRENT_SEASON} for test: {test_name}")

    result_json = await asyncio.to_thread(analyze_player_stats_logic, **kwargs)
    
    try:
        result_data = json.loads(result_json)
        # logger.debug(json.dumps(result_data, indent=2))
        
        if expect_api_error:
            assert "error" in result_data, f"Expected an API error for {test_name}, but got: {result_data}"
            logger.info(f"SUCCESS (expected API error): {test_name} - Error: {result_data.get('error')}")
        elif expect_no_data_success:
            assert "error" not in result_data, f"Expected no error for no_data_success for {test_name}, but got error: {result_data.get('error')}"
            assert "overall_dashboard_stats" in result_data, f"Expected 'overall_dashboard_stats' key for no_data_success for {test_name}"
            assert isinstance(result_data["overall_dashboard_stats"], dict), f"Expected 'overall_dashboard_stats' to be a dict for {test_name}"
            assert not result_data["overall_dashboard_stats"], f"Expected 'overall_dashboard_stats' to be empty for no_data_success for {test_name}, but got: {result_data['overall_dashboard_stats']}"
            logger.info(f"SUCCESS (expected no data): {test_name} - No overall_dashboard_stats found as expected.")
        else: # Success with data expected
            assert "error" not in result_data, f"Unexpected API error for {test_name}: {result_data.get('error')}"
            assert "overall_dashboard_stats" in result_data, f"Expected 'overall_dashboard_stats' key not found for {test_name}"
            assert isinstance(result_data["overall_dashboard_stats"], dict), f"'overall_dashboard_stats' should be a dict for {test_name}"
            assert result_data["overall_dashboard_stats"], f"Expected 'overall_dashboard_stats' to be non-empty for {test_name}"
            # Player identifiers are at the top level of result_data.
            # Specific stat keys like 'GP', 'PTS' could be checked if necessary.
            logger.info(f"SUCCESS (data found): {test_name}")

    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for {test_name}: Could not decode JSON response: {result_json}")
        assert False, f"JSONDecodeError for {test_name}"
    except Exception as e:
        logger.error(f"An unexpected error occurred in {test_name}: {e}")
        logger.error(f"Response was: {result_json}")
        assert False, f"Unexpected error in {test_name}: {e}. Response: {result_json}"
    logger.info("-" * 70)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description, params, expect_error, expect_no_data",
    [
        ("LeBron, Past Season Defaults", {"player_name": VALID_PLAYER_LEBRON, "season": PAST_SEASON}, False, False),
        ("Curry, Past Season Totals", {"player_name": VALID_PLAYER_CURRY, "season": PAST_SEASON, "per_mode": VALID_PER_MODE_TOTALS}, False, False),
        ("Jokic, Past Season Playoffs", {"player_name": VALID_PLAYER_JOKIC, "season": PAST_SEASON, "season_type": SeasonTypeAllStar.playoffs}, False, False),
        
        ("Invalid Player Name", {"player_name": INVALID_PLAYER_NAME}, True, False),
        ("LeBron, Invalid Season Format", {"player_name": VALID_PLAYER_LEBRON, "season": INVALID_SEASON_FORMAT}, True, False),
        ("LeBron, Logically Invalid Season (old)", {"player_name": VALID_PLAYER_LEBRON, "season": INVALID_SEASON_LOGICALLY}, False, True),
        ("LeBron, AllStar SeasonType (Error)", {"player_name": VALID_PLAYER_LEBRON, "season": PAST_SEASON, "season_type": SeasonTypeAllStar.all_star}, True, False),
        ("LeBron, Invalid PerMode", {"player_name": VALID_PLAYER_LEBRON, "season": PAST_SEASON, "per_mode": INVALID_PER_MODE}, True, False),
        
        ("LeBron, Current Season Defaults", {"player_name": VALID_PLAYER_LEBRON, "season": CURRENT_SEASON}, False, False),
    ]
)
async def test_analyze_player_stats_scenarios(description, params, expect_error, expect_no_data):
    await run_analyze_test_with_assertions(
        description=description,
        expect_api_error=expect_error,
        expect_no_data_success=expect_no_data,
        **params
    )
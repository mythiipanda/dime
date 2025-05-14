import sys
import os
import asyncio
import json
import logging
from typing import Dict, Any
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.player_estimated_metrics import fetch_player_estimated_metrics_logic
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar
from backend.config import settings

# Constants for testing
CURRENT_SEASON = settings.CURRENT_NBA_SEASON
PAST_SEASON = "2022-23"

async def run_player_estimated_metrics_test_with_assertions(
    description: str,
    expect_api_error: bool = False,
    expect_empty_list_no_error: bool = False,
    **kwargs: Any
):
    test_name = f"Player Estimated Metrics - {description}"
    logger.info(f"--- Testing {test_name} ---")
    
    params_to_logic = {
        "season": kwargs.get("season", CURRENT_SEASON),
        "season_type": kwargs.get("season_type", SeasonTypeAllStar.regular),
        "league_id": kwargs.get("league_id", LeagueID.nba),
    }
    params_to_logic.update(kwargs)

    result_json = await asyncio.to_thread(fetch_player_estimated_metrics_logic, **params_to_logic)
    
    try:
        result_data = json.loads(result_json)
        
        if expect_api_error:
            assert "error" in result_data, f"Expected an API error for {test_name}, but got: {result_data}"
            logger.info(f"SUCCESS (expected API error): {test_name} - Error: {result_data.get('error')}")
        elif expect_empty_list_no_error:
            assert "error" not in result_data, f"Expected no error for empty list scenario {test_name}, but got: {result_data.get('error')}"
            assert "player_estimated_metrics" in result_data, f"Expected 'player_estimated_metrics' key for {test_name}"
            assert isinstance(result_data["player_estimated_metrics"], list), f"'player_estimated_metrics' should be a list for {test_name}"
            assert not result_data["player_estimated_metrics"], f"Expected 'player_estimated_metrics' to be an empty list for {test_name}, but got {len(result_data['player_estimated_metrics'])} items."
            logger.info(f"SUCCESS (expected empty list): {test_name}")
        else:
            assert "error" not in result_data, f"Unexpected API error for {test_name}: {result_data.get('error')}"
            assert "player_estimated_metrics" in result_data, f"Expected 'player_estimated_metrics' key for {test_name}"
            assert isinstance(result_data["player_estimated_metrics"], list), f"'player_estimated_metrics' should be a list for {test_name}"
            assert result_data["player_estimated_metrics"], f"Expected 'player_estimated_metrics' to be a non-empty list for {test_name}"
            logger.info(f"SUCCESS (data found): {test_name} - Count: {len(result_data['player_estimated_metrics'])}")
            sample_data = result_data["player_estimated_metrics"][0]
            logger.info(f"  Sample Data (First Player): {sample_data.get('PLAYER_NAME')} - E_NET_RATING: {sample_data.get('E_NET_RATING')}")
            
    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON response for {test_name}: {result_json}")
        assert False, f"JSONDecodeError for {test_name}"
    except Exception as e:
        logger.error(f"An unexpected error occurred in {test_name}: {e}. Response: {result_json}")
        assert False, f"Unexpected error in {test_name}: {e}"
    logger.info("-" * 70)

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description, params, expect_api_error, expect_empty_list",
    [
        (f"Current Season ({CURRENT_SEASON}), Regular", {}, False, False),
        (f"Past Season ({PAST_SEASON}), Regular", {"season": PAST_SEASON}, False, False),
        (f"Past Season ({PAST_SEASON}), Playoffs", {"season": PAST_SEASON, "season_type": SeasonTypeAllStar.playoffs}, False, False),
        ("Invalid Season Format (2023)", {"season": "2023"}, True, False),
        (f"Invalid Season Type, Season {PAST_SEASON}", {"season": PAST_SEASON, "season_type": "InvalidSeasonType"}, True, False),
        (f"Invalid League ID, Season {PAST_SEASON}", {"season": PAST_SEASON, "league_id": "99"}, True, False),
    ]
)
async def test_player_estimated_metrics_scenarios(description: str, params: Dict[str, Any], expect_api_error: bool, expect_empty_list: bool):
    await run_player_estimated_metrics_test_with_assertions(
        description=description,
        expect_api_error=expect_api_error,
        expect_empty_list_no_error=expect_empty_list,
        **params
    )
import sys
import os
import asyncio
import json
import logging
from typing import Optional, Dict, Any
import pytest

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.league_player_on_details import fetch_league_player_on_details_logic
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed,
    MeasureTypeDetailedDefense,
    LeagueID
    # TeamID # Placeholder, actual team IDs are integers - Handled by using TEAM_ID_LAKERS from constants
)
from backend.config import settings
from backend.core.constants import (
    TEAM_ID_LAKERS, TEAM_ID_CELTICS, TEAM_ID_WARRIORS
)

# Constants for testing
CURRENT_SEASON = settings.CURRENT_NBA_SEASON
PAST_SEASON = "2022-23"

async def run_league_player_on_details_test_with_assertions(
    description: str,
    expect_api_error: bool = False,
    expect_empty_list_no_error: bool = False,
    **kwargs: Any
):
    test_name = f"League Player On Details - {description}"
    logger.info(f"--- Testing {test_name} ---")
    
    # Default parameters that the logic function might expect if not provided
    params_to_logic = {
        "season": kwargs.get("season", CURRENT_SEASON), # Default to current season
        "team_id": kwargs.get("team_id", TEAM_ID_LAKERS), # Default to a valid team ID
        # Add other necessary defaults if the logic function requires them
    }
    # Overlay provided kwargs, allowing them to override defaults
    params_to_logic.update(kwargs)

    # Log the actual parameters being sent to the logic function
    # logger.debug(f"Calling fetch_league_player_on_details_logic with: {params_to_logic}")

    result_json = await asyncio.to_thread(fetch_league_player_on_details_logic, **params_to_logic)
    
    try:
        result_data = json.loads(result_json)
        # logger.debug(f"Test: {test_name} - Full API Response: {json.dumps(result_data, indent=2)}")

        if expect_api_error:
            # Check if it's an error structure (e.g., has "message" or "error" key)
            # OR if the main data key is absent or not a list of results.
            is_error_response = (
                ("message" in result_data and "league_player_on_details" not in result_data) or
                ("error" in result_data and "league_player_on_details" not in result_data) or
                ("league_player_on_details" not in result_data or not isinstance(result_data.get("league_player_on_details"), list))
            )
            
            assert is_error_response, (
                f"Unexpected success or non-standard error in {test_name}: "
                f"Expected API error but got {json.dumps(result_data)}"
            )
            logger.info(f"PASS: {test_name} - Successfully caught expected API error.")
            return

        assert "league_player_on_details" in result_data, f"'league_player_on_details' key missing in {test_name}"
        data_list = result_data["league_player_on_details"]
        assert isinstance(data_list, list), f"Data for 'league_player_on_details' is not a list in {test_name}"

        if expect_empty_list_no_error:
            assert len(data_list) == 0, f"Expected empty list for 'league_player_on_details' but got {len(data_list)} items in {test_name}"
            logger.info(f"PASS: {test_name} - Successfully validated empty list as expected.")
        else:
            assert len(data_list) > 0, f"Expected non-empty list for 'league_player_on_details' but got empty list in {test_name}"
            # Further checks can be added here if specific keys/values are expected in non-empty results
            logger.info(f"PASS: {test_name} - Successfully validated non-empty list with {len(data_list)} items.")

    except json.JSONDecodeError:
        assert expect_api_error, f"JSONDecodeError for {test_name} when success was expected. Response: {result_json}"
        logger.info(f"PASS: {test_name} - Successfully caught expected API error (JSONDecodeError).")
    except AssertionError as e:
        logger.error(f"FAIL: {test_name} - {e}")
        logger.error(f"Full response for failing test {test_name}: {result_json}")
        raise
    except Exception as e:
        logger.error(f"UNEXPECTED EXCEPTION in {test_name}: {e}")
        logger.error(f"Full response for failing test {test_name}: {result_json}")
        raise

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description, params, expect_api_error, expect_empty_list",
    [
        ("Default (Lakers, Current Season, Base)", {}, False, False),
        (
            "Celtics, 2022-23, Opponent",
            {"team_id": TEAM_ID_CELTICS, "season": PAST_SEASON, "measure_type": MeasureTypeDetailedDefense.opponent},
            False, False
        ),
        ("Warriors, 2021-22 Playoffs, Totals", {"team_id": TEAM_ID_WARRIORS, "season": "2021-22", "season_type": SeasonTypeAllStar.playoffs, "per_mode": PerModeDetailed.totals}, False, False),
        ("Invalid Season Format", {"season": "INVALID-SEASON"}, True, False),
        ("Invalid PerMode", {"per_mode": "INVALID_PERMODE"}, True, False),
        ("Invalid MeasureType", {"measure_type": "INVALID_MEASURE"}, True, False),
        ("Future Season (likely no data)", {"season": "2077-78"}, True, False),
        ("Non-existent TeamID (0), Season 2022-23", {"team_id": 0, "season": PAST_SEASON}, False, False),
        ("LeagueID WNBA (should be error or empty for NBA data)", {"league_id_nullable": LeagueID.wnba}, False, True),
    ]
)
async def test_league_player_on_details_scenarios(description: str, params: Dict[str, Any], expect_api_error: bool, expect_empty_list: bool):
    await run_league_player_on_details_test_with_assertions(
        description=description,
        expect_api_error=expect_api_error,
        expect_empty_list_no_error=expect_empty_list,
        **params
    )
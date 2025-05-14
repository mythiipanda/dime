# backend/smoke_tests/test_team_info_roster.py
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

from backend.api_tools.team_info_roster import fetch_team_info_and_roster_logic
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar
from backend.config import settings

# Test Constants
TEAM_ID_LAKERS = "1610612747"
TEAM_ABBREV_BOS = "BOS"
TEAM_NAME_WARRIORS = "Golden State Warriors"
TEAM_ABBREV_LAL = "LAL"
INVALID_TEAM_IDENTIFIER = "INVALID_TEAM_XYZ"
INVALID_SEASON_FORMAT = "2023"
INVALID_SEASON_TYPE = "InvalidType"

SEASON_2022_23 = "2022-23"
SEASON_2021_22 = "2021-22"
CURRENT_SEASON = settings.CURRENT_NBA_SEASON

async def run_team_info_test_with_assertions(
    description: str, 
    expect_api_error: bool = False, 
    **kwargs: Any
):
    test_name = f"Team Info & Roster - {description}"
    logger.info(f"--- Testing {test_name} ---")
    
    # team_identifier is a required positional arg for the logic function
    # Other kwargs like season, season_type are optional
    result_json_str = await asyncio.to_thread(fetch_team_info_and_roster_logic, **kwargs)
    result_data = json.loads(result_json_str)
    # logger.debug(f"Full API Response for {test_name}: {json.dumps(result_data, indent=2)}")

    if expect_api_error:
        assert "error" in result_data, f"Expected API error for '{description}', but 'error' key missing. Response: {result_data}"
        # Check that primary data keys are not present or are empty if the API includes them on error
        assert "team_id" not in result_data or not result_data["team_id"], f"Expected no 'team_id' on API error for '{description}'"
        assert "info" not in result_data or not result_data["info"], f"Expected no 'info' on API error for '{description}'"
        assert "roster" not in result_data or not result_data["roster"], f"Expected no 'roster' on API error for '{description}'"
        assert "coaches" not in result_data or not result_data["coaches"], f"Expected no 'coaches' on API error for '{description}'"
        logger.info(f"SUCCESS (expected API error for '{description}'): {result_data.get('error')}")
    else: # Expect successful data
        assert "error" not in result_data, f"Expected successful data for '{description}', but got error: {result_data.get('error')}"
        assert "team_id" in result_data and isinstance(result_data["team_id"], int), \
            f"'team_id' key missing or not an int for '{description}'. Response: {result_data}"
        assert "info" in result_data and isinstance(result_data["info"], dict), \
            f"'info' key missing or not a dict for '{description}'. Response: {result_data}"
        assert "roster" in result_data and isinstance(result_data["roster"], list), \
            f"'roster' key missing or not a list for '{description}'. Response: {result_data}"
        assert "coaches" in result_data and isinstance(result_data["coaches"], list), \
            f"'coaches' key missing or not a list for '{description}'. Response: {result_data}"

        assert result_data["info"].get("TEAM_ABBREVIATION") or result_data["info"].get("TEAM_NAME"), \
             f"Team abbreviation or name missing in info for '{description}'"

        if result_data["roster"]:
            assert "PLAYER" in result_data["roster"][0], f"'PLAYER' key (not PLAYER_NAME) missing in roster item for '{description}'. Roster item keys: {result_data['roster'][0].keys() if result_data['roster'][0] else 'empty item'}"
        # else: # Roster can be empty for some seasons/teams
            # logger.info(f"Roster is empty for '{description}', which might be valid.")
        
        logger.info(f"SUCCESS for '{description}': Fetched data for Team ID {result_data['team_id']} ({result_data['info'].get('TEAM_NAME')}). Roster size: {len(result_data['roster'])}")

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description_suffix, params, expect_error",
    [
        ("Lakers, Current Season", {"team_identifier": TEAM_ID_LAKERS, "season": CURRENT_SEASON}, False),
        ("BOS, 2022-23", {"team_identifier": TEAM_ABBREV_BOS, "season": SEASON_2022_23}, False),
        (
            "Golden State Warriors, 2021-22 Playoffs", 
            {"team_identifier": TEAM_NAME_WARRIORS, "season": SEASON_2021_22, "season_type": SeasonTypeAllStar.playoffs},
            False
        ),
        ("Invalid Team Identifier", {"team_identifier": INVALID_TEAM_IDENTIFIER, "season": CURRENT_SEASON}, True),
        ("Lakers, Invalid Season Format", {"team_identifier": TEAM_ABBREV_LAL, "season": INVALID_SEASON_FORMAT}, True),
        ("Lakers, Invalid Season Type", {"team_identifier": TEAM_ABBREV_LAL, "season": CURRENT_SEASON, "season_type": INVALID_SEASON_TYPE}, True),
    ]
)
async def test_team_info_scenarios(description_suffix: str, params: Dict[str, Any], expect_error: bool):
    await run_team_info_test_with_assertions(
        description=description_suffix,
        expect_api_error=expect_error,
        **params
    )
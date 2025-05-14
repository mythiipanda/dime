import sys
import os
import asyncio
import json
import logging
import pytest

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.player_listings import fetch_common_all_players_logic
from backend.config import settings # For CURRENT_NBA_SEASON

VALID_SEASON_CURRENT = settings.CURRENT_NBA_SEASON
VALID_SEASON_PAST = "2022-23"
INVALID_SEASON_FORMAT = "2023"
INVALID_LEAGUE_ID = "99"
VALID_LEAGUE_ID_NBA = "00"
INVALID_IS_ONLY_CURRENT_SEASON = 2

async def run_common_all_players_test(
    season: str,
    league_id: str,
    is_only_current_season: int,
    expect_error: bool = False,
    expected_error_message_fragment: str = "",
    test_description: str = ""
):
    logger.info(f"--- Testing: {test_description} ---")
    logger.info(f"Params: Season='{season}', LeagueID='{league_id}', IsOnlyCurrentSeason={is_only_current_season}")

    result_json = await asyncio.to_thread(
        fetch_common_all_players_logic,
        season=season,
        league_id=league_id,
        is_only_current_season=is_only_current_season
    )

    try:
        result_data = json.loads(result_json)
        # logger.info(f"Result for '{test_description}': {json.dumps(result_data, indent=2)}")

        if expect_error:
            assert "error" in result_data, f"Expected an error for '{test_description}', but got success."
            if expected_error_message_fragment:
                assert expected_error_message_fragment.lower() in result_data["error"].lower(), \
                    f"Expected error message for '{test_description}' to contain '{expected_error_message_fragment}', but got: {result_data['error']}"
            logger.info(f"SUCCESS (expected error): '{test_description}' - Error: {result_data.get('error')}")
        else:
            assert "error" not in result_data, f"Unexpected error for '{test_description}': {result_data.get('error')}"
            assert "parameters" in result_data, f"Missing 'parameters' key in response for '{test_description}'"
            assert result_data["parameters"]["season"] == season
            assert result_data["parameters"]["league_id"] == league_id
            assert result_data["parameters"]["is_only_current_season"] == is_only_current_season
            assert "players" in result_data, f"Missing 'players' key in response for '{test_description}'"
            assert isinstance(result_data["players"], list), f"'players' should be a list for '{test_description}'"
            
            if is_only_current_season == 1 and season == VALID_SEASON_CURRENT:
                assert len(result_data["players"]) > 0, f"Expected players for current season in '{test_description}', but got none."
                # Check a few expected keys in the first player object if list is not empty
                if result_data["players"]:
                    first_player = result_data["players"][0]
                    expected_player_keys = ["PERSON_ID", "DISPLAY_FIRST_LAST", "ROSTERSTATUS", "TEAM_ID"]
                    for key in expected_player_keys:
                        assert key in first_player, f"Key '{key}' missing in player data for '{test_description}'"
            
            logger.info(f"SUCCESS: '{test_description}' - Found {len(result_data['players'])} players.")

    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for '{test_description}': Could not decode response: {result_json}")
        assert False, f"JSONDecodeError for '{test_description}'"
    logger.info("-" * 70)

@pytest.mark.asyncio
async def test_common_all_players_current_season_valid():
    await run_common_all_players_test(
        season=VALID_SEASON_CURRENT,
        league_id=VALID_LEAGUE_ID_NBA,
        is_only_current_season=1,
        test_description="Current season, NBA, current players only"
    )

@pytest.mark.asyncio
async def test_common_all_players_past_season_all_players_valid():
    await run_common_all_players_test(
        season=VALID_SEASON_PAST,
        league_id=VALID_LEAGUE_ID_NBA,
        is_only_current_season=0, # All players historically associated with this season
        test_description="Past season, NBA, all historically associated players"
    )

@pytest.mark.asyncio
async def test_common_all_players_past_season_current_only_valid():
    # This should return players active *during* VALID_SEASON_PAST, not necessarily active *now*.
    # The API's `is_only_current_season` refers to the context of the `season` param.
    await run_common_all_players_test(
        season=VALID_SEASON_PAST,
        league_id=VALID_LEAGUE_ID_NBA,
        is_only_current_season=1, 
        test_description="Past season, NBA, players active in that season"
    )

@pytest.mark.asyncio
async def test_common_all_players_invalid_season_format():
    await run_common_all_players_test(
        season=INVALID_SEASON_FORMAT,
        league_id=VALID_LEAGUE_ID_NBA,
        is_only_current_season=1,
        expect_error=True,
        expected_error_message_fragment="Invalid season format",
        test_description="Invalid season format"
    )

@pytest.mark.asyncio
async def test_common_all_players_invalid_league_id():
    await run_common_all_players_test(
        season=VALID_SEASON_CURRENT,
        league_id=INVALID_LEAGUE_ID,
        is_only_current_season=1,
        expect_error=True,
        expected_error_message_fragment="Invalid league_id",
        test_description="Invalid League ID"
    )

@pytest.mark.asyncio
async def test_common_all_players_invalid_is_only_current_season_value():
    await run_common_all_players_test(
        season=VALID_SEASON_CURRENT,
        league_id=VALID_LEAGUE_ID_NBA,
        is_only_current_season=INVALID_IS_ONLY_CURRENT_SEASON,
        expect_error=True,
        expected_error_message_fragment="Invalid format for parameter 'is_only_current_season'",
        test_description="Invalid is_only_current_season value"
    )

# Example of how to run all tests in this file directly (optional)
# if __name__ == "__main__":
#     async def main():
#         await test_common_all_players_current_season_valid()
#         await test_common_all_players_past_season_all_players_valid()
#         await test_common_all_players_past_season_current_only_valid()
#         await test_common_all_players_invalid_season_format()
#         await test_common_all_players_invalid_league_id()
#         await test_common_all_players_invalid_is_only_current_season_value()
#     asyncio.run(main()) 
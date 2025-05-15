# backend/smoke_tests/test_game_finder.py
import sys
import os
import asyncio
import json
import logging
import pytest # Import pytest

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Adjusted format
logger = logging.getLogger(__name__)

from backend.api_tools.game_finder import fetch_league_games_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID

# Constants for testing
TEAM_ID_LAL = 1610612747 # Los Angeles Lakers
PLAYER_ID_LEBRON = 2544 # LeBron James
SEASON_2022_23 = "2022-23"
SEASON_2023_24 = "2023-24" # Current or recent season for more data

# Renamed and enhanced helper with assertions
async def run_game_finder_test_with_assertions(
    description: str,
    expect_api_error: bool = False,
    expect_empty_results_no_error: bool = False,
    **kwargs
):
    test_name = f"{description} (Params: {kwargs})"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json = await asyncio.to_thread(fetch_league_games_logic, **kwargs)
    
    try:
        result_data = json.loads(result_json)
        expected_data_key = "games"
        
        if expect_api_error:
            assert "error" in result_data, f"Expected an API error for {test_name}, but got: {result_data}"
            logger.info(f"SUCCESS (expected API error): {test_name} - Error: {result_data.get('error')}")
        elif expect_empty_results_no_error:
            assert "error" not in result_data, f"Expected no error for empty results for {test_name}, but got error: {result_data.get('error')}"
            assert expected_data_key in result_data, f"Expected key '{expected_data_key}' for empty results for {test_name}"
            assert isinstance(result_data[expected_data_key], list), f"Expected list for '{expected_data_key}' for {test_name}"
            assert not result_data[expected_data_key], f"Expected empty list for '{expected_data_key}' for {test_name}, but got {len(result_data[expected_data_key])} items."
            logger.info(f"SUCCESS (expected empty results): {test_name} - Found 0 {expected_data_key}, as expected.")
        else:
            assert "error" not in result_data, f"Unexpected API error for {test_name}: {result_data.get('error')}"
            assert expected_data_key in result_data, f"Expected key '{expected_data_key}' not found for {test_name}"
            assert isinstance(result_data[expected_data_key], list), f"Key '{expected_data_key}' should be a list for {test_name}"
            
            games_found = len(result_data[expected_data_key])
            logger.info(f"SUCCESS: {test_name} - Found {games_found} games.")
            # if games_found > 0 and games_found <= 5:
            #     logger.info("Sample games:")
            #     for i, game in enumerate(result_data[expected_data_key][:5]):
            #         logger.info(f"  Game {i+1}: {game.get('GAME_DATE_FORMATTED', game.get('GAME_DATE'))} - {game.get('MATCHUP')} - Score: {game.get('PTS')}")
            # elif games_found == 0:
            #      logger.info(f"No games found for {test_name}, which might be expected.") # Already covered by expect_empty_results
            # else:
            #     logger.info(f"First game sample: {result_data[expected_data_key][0].get('GAME_DATE_FORMATTED', result_data[expected_data_key][0].get('GAME_DATE'))} - {result_data[expected_data_key][0].get('MATCHUP')}")

    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for {test_name}: Could not decode JSON response: {result_json}")
        assert False, f"JSONDecodeError for {test_name}"
    logger.info("-" * 70)

# Parametrized test function
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description, kwargs, expect_api_error, expect_empty_results_no_error",
    [
        (
            "Lakers Games 2022-23 Regular Season",
            {"team_id_nullable": TEAM_ID_LAL, "season_nullable": SEASON_2022_23, "season_type_nullable": SeasonTypeAllStar.regular},
            False, False
        ),
        (
            "LeBron James Games 2022-23 Regular Season",
            {"player_id_nullable": PLAYER_ID_LEBRON, "season_nullable": SEASON_2022_23, "season_type_nullable": SeasonTypeAllStar.regular},
            False, False
        ),
        (
            "Games in Oct 2023 for 2023-24 Season (No Team - should now work without API error)",
            {"season_nullable": SEASON_2023_24, "date_from_nullable": "2023-10-01", "date_to_nullable": "2023-10-31"},
            False, False # Changed: Expect API error was True, now False due to post-fetch filtering
        ),
        (
            "Lakers Games in Jan 2024 (Specific Test for the Bug Fix)",
            {
                "team_id_nullable": TEAM_ID_LAL,
                "season_nullable": SEASON_2023_24,
                "date_from_nullable": "2024-01-01",
                "date_to_nullable": "2024-01-31",
                "league_id_nullable": LeagueID.nba
            },
            False, False # Should successfully return games
        ),
        (
            "Date-Only Query (expecting specific unsupported error)", # This should still be caught by the logic before API call
            {"date_from_nullable": "2023-10-01", "date_to_nullable": "2023-10-05"},
            True, False # This error is generated by our logic, not a JSONDecodeError from API
        ),
        (
            "Player Search No ID (expecting error)",
            {"player_or_team_abbreviation": 'P'},
            True, False
        ),
        # Test case for a very far future season (format is valid, but expect no games)
        (
            "Player in Very Far Future Season (expect empty, no error)",
            {"player_id_nullable": PLAYER_ID_LEBRON, "season_nullable": "2099-00", "season_type_nullable": SeasonTypeAllStar.regular},
            False, True # Changed: Now expect no error, but empty results, as format is valid by our validator
        ),
        (
            "Lakers Games 2022-23 Playoffs",
            {"team_id_nullable": TEAM_ID_LAL, "season_nullable": SEASON_2022_23, "season_type_nullable": SeasonTypeAllStar.playoffs},
            False, False
        ),
        (
            "LeBron James Games 2023-24 All-Star",
            {"player_id_nullable": PLAYER_ID_LEBRON, "season_nullable": SEASON_2023_24, "season_type_nullable": SeasonTypeAllStar.all_star},
            False, False # Might be empty if he didn't play or data isn't there, but shouldn't be an API error
        ),
        (
            "Lakers Games in a narrow future date range (expect empty, no error)",
            {
                "team_id_nullable": TEAM_ID_LAL,
                "season_nullable": "2098-99", # A valid future season format for the API call itself
                "date_from_nullable": "2099-01-01",
                "date_to_nullable": "2099-01-05",
            },
            False, True # Expect empty results, no API error
        ),
        (
            "WNBA Games 2023 Season (Example)",
            {"league_id_nullable": LeagueID.wnba, "season_nullable": "2023", "season_type_nullable": "Regular Season"}, # WNBA season format is YYYY
            False, False # Expect games or empty, but no API error
        ),
        (
            "G-League Games 2023-24 Season (Example)",
            {"league_id_nullable": LeagueID.g_league, "season_nullable": SEASON_2023_24, "season_type_nullable": "Regular Season"},
            False, False # Expect games or empty, but no API error
        ),
        (
            "Player query with P/T flag set to P",
            {"player_or_team_abbreviation": 'P', "player_id_nullable": PLAYER_ID_LEBRON, "season_nullable": SEASON_2022_23, "season_type_nullable": SeasonTypeAllStar.regular},
            False, False
        ),
        (
            "Team query with P/T flag set to T",
            {"player_or_team_abbreviation": 'T', "team_id_nullable": TEAM_ID_LAL, "season_nullable": SEASON_2022_23, "season_type_nullable": SeasonTypeAllStar.regular},
            False, False
        ),
        (
            "Invalid P/T flag (expecting error)",
            {"player_or_team_abbreviation": 'X', "team_id_nullable": TEAM_ID_LAL},
            True, False
        ),
        (
            "Query with only team_id (should fetch many games, limited by logic)",
            {"team_id_nullable": TEAM_ID_LAL},
            False, False
        ),
        (
            "Query with only player_id (should fetch many games, limited by logic)",
            {"player_id_nullable": PLAYER_ID_LEBRON},
            False, False
        )
    ]
)
async def test_game_finder_scenarios(description, kwargs, expect_api_error, expect_empty_results_no_error):
    await run_game_finder_test_with_assertions(
        description=description,
        expect_api_error=expect_api_error,
        expect_empty_results_no_error=expect_empty_results_no_error,
        **kwargs
    )
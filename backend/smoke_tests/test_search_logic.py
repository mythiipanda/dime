# backend/smoke_tests/test_search_logic.py
import sys
import os
import asyncio
import json
import logging
from typing import Optional, Callable, Any
import pytest # Import pytest

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.search import search_players_logic, search_teams_logic, search_games_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar
from backend.config import settings # For default season

# Refactored test helper with assertions
async def run_search_test_with_assertions(
    logic_function: Callable, 
    query: str, 
    expected_data_key: str, # e.g., "players", "teams", "games"
    expect_api_error: bool = False, # True if the API call itself is expected to return an error string
    expect_empty_results_no_error: bool = False, # True if an empty list for the data key is expected without an error
    description: str = "",
    **kwargs: Any
):
    test_name = f"{description} (Query: '{query}')"
    logger.info(f"--- Testing {test_name} ---")
    
    params = {"query": query, **kwargs}
    # Ensure 'limit' is int if present, as API might be strict
    if 'limit' in params and params['limit'] is not None:
        params['limit'] = int(params['limit'])

    result_json = await asyncio.to_thread(logic_function, **params)
    
    try:
        result_data = json.loads(result_json)
        # logger.debug(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if expect_api_error:
            assert "error" in result_data, f"Expected an API error for {test_name}, but got: {result_data}"
            logger.info(f"SUCCESS (expected API error): {test_name} - Error: {result_data['error']}")
        elif expect_empty_results_no_error:
            assert "error" not in result_data, f"Expected no error for empty results for {test_name}, but got error: {result_data.get('error')}"
            assert expected_data_key in result_data, f"Expected key '{expected_data_key}' for empty results for {test_name}"
            assert isinstance(result_data[expected_data_key], list), f"Expected list for key '{expected_data_key}' for empty results for {test_name}"
            assert not result_data[expected_data_key], f"Expected empty list for key '{expected_data_key}' for empty results for {test_name}, but got {len(result_data[expected_data_key])} items."
            logger.info(f"SUCCESS (expected empty results): {test_name} - Found 0 {expected_data_key}, as expected.")
        else:
            assert "error" not in result_data, f"Unexpected API error for {test_name}: {result_data.get('error')}"
            assert expected_data_key in result_data, f"Expected key '{expected_data_key}' not found for {test_name}"
            assert isinstance(result_data[expected_data_key], list), f"Key '{expected_data_key}' should be a list for {test_name}"
            
            if result_data[expected_data_key]:
                logger.info(f"SUCCESS: {test_name} - Found {len(result_data[expected_data_key])} {expected_data_key}.")
                # Log sample (optional, can be verbose)
                # if expected_data_key == 'players': logger.info(f"  Sample Player: {result_data[expected_data_key][0].get('full_name')}")
                # elif expected_data_key == 'teams': logger.info(f"  Sample Team: {result_data[expected_data_key][0].get('full_name')}")
                # elif expected_data_key == 'games': logger.info(f"  Sample Game: {result_data[expected_data_key][0].get('MATCHUP')} on {result_data[expected_data_key][0].get('GAME_DATE')}")
            else:
                logger.info(f"SUCCESS (empty results): {test_name} - Found 0 {expected_data_key}.")

    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for {test_name}: Could not decode JSON response: {result_json}")
        assert False, f"JSONDecodeError for {test_name}" # Fail test on JSON decode error
    logger.info("-" * 70)

# Player Search Tests
@pytest.mark.asyncio
@pytest.mark.parametrize("query, limit, expect_api_error, expect_empty_results_no_error, description", [
    ("LeBron", None, False, False, "Player Search - Standard"),
    ("Jokic", 3, False, False, "Player Search - With Limit"),
    ("L", None, True, False, "Player Search - Short Query (expect API error)"),
    ("NonExistentPlayerXYZ", None, False, True, "Player Search - No Results (expect empty list)"),
])
async def test_player_search_scenarios(query, limit, expect_api_error, expect_empty_results_no_error, description):
    await run_search_test_with_assertions(
        search_players_logic, query, "players", 
        expect_api_error=expect_api_error, 
        expect_empty_results_no_error=expect_empty_results_no_error,
        description=description, 
        limit=limit
    )

# Team Search Tests
@pytest.mark.asyncio
@pytest.mark.parametrize("query, limit, expect_api_error, expect_empty_results_no_error, description", [
    ("Lakers", None, False, False, "Team Search - Standard"),
    ("Bos", 1, False, False, "Team Search - With Limit"),
    ("GSW", None, False, False, "Team Search - Abbreviation"),
    ("NonExistentTeamXYZ", None, False, True, "Team Search - No Results (expect empty list)"),
])
async def test_team_search_scenarios(query, limit, expect_api_error, expect_empty_results_no_error, description):
    await run_search_test_with_assertions(
        search_teams_logic, query, "teams",
        expect_api_error=expect_api_error,
        expect_empty_results_no_error=expect_empty_results_no_error,
        description=description,
        limit=limit
    )

# Game Search Tests
CURRENT_SEASON = settings.CURRENT_NBA_SEASON
PAST_SEASON = "2022-23" # Example past season

@pytest.mark.asyncio
@pytest.mark.parametrize("query, season, limit, expect_api_error, expect_empty_results_no_error, description", [
    ("Lakers", PAST_SEASON, None, False, False, "Game Search - Single Team, Past Season"),
    ("LAL vs BOS", PAST_SEASON, 5, False, False, "Game Search - Matchup, Past Season, Limit 5"),
    ("Warriors at Suns", PAST_SEASON, None, False, False, "Game Search - Matchup with 'at', Past Season"),
    ("NonExistentTeamXYZ", PAST_SEASON, None, False, True, "Game Search - No Results, Past Season (expect empty list)"),
    ("Lakers", "2023", None, True, False, "Game Search - Invalid Season Format (expect API error)"),
    ("", PAST_SEASON, None, True, False, "Game Search - Empty Query (expect API error)"),
])
async def test_game_search_scenarios(query, season, limit, expect_api_error, expect_empty_results_no_error, description):
    await run_search_test_with_assertions(
        search_games_logic, query, "games",
        expect_api_error=expect_api_error,
        expect_empty_results_no_error=expect_empty_results_no_error,
        description=description,
        season=season, 
        limit=limit
    )

# Removed original main() and asyncio.run(main())
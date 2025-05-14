# backend/smoke_tests/test_game_boxscores.py
import sys
import os
import asyncio
import json
import logging
from typing import Callable, Any, List, Dict # Added for type hints
import pytest # Import pytest

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Adjusted format
logger = logging.getLogger(__name__)

from backend.api_tools.game_boxscores import (
    fetch_boxscore_traditional_logic,
    fetch_boxscore_advanced_logic,
    fetch_boxscore_four_factors_logic,
    fetch_boxscore_usage_logic,
    fetch_boxscore_defensive_logic,
    fetch_boxscore_summary_logic
)
# from backend.config import settings # Not directly needed by logic function signatures

# A recent, known valid game_id for testing
# Example: Game 1 of 2023 Finals: MIA @ DEN, 2023-06-01, GameID: 0042200401
# Example: Regular season BOS vs LAL 2024-02-01, GameID: 0022300704
# Example: Recent game: OKC vs DAL 2024-05-11, GameID: 0042300225 (Playoffs)
VALID_GAME_ID = "0042300225" # DAL vs OKC, 2024-05-11 (Playoffs)
# Fallback if the above game is too old or data is sparse
FALLBACK_GAME_ID = "0022300001" # DEN vs LAL, 2023-10-24 (Opening Night)
INVALID_GAME_ID = "0000000000"
MALFORMED_GAME_ID = "123"

# Enhanced helper with assertions and dynamic key checking
async def run_boxscore_test_with_assertions(
    description: str,
    logic_function: Callable,
    game_id: str,
    expected_keys_map: Dict[str, str], # e.g., {"player_stats_key": "players", "team_stats_key": "teams"}
    expect_api_error: bool = False,
    expect_empty_results_no_error: bool = False, # If API returns empty lists for valid but no-data scenarios
    **kwargs: Any # For additional params like start_period, end_period
):
    test_name = f"{description} (GameID: {game_id}, Params: {kwargs})"
    logger.info(f"--- Testing {test_name} ---")
    
    all_kwargs = {"game_id": game_id, **kwargs}
    result_json = await asyncio.to_thread(logic_function, **all_kwargs)
    
    try:
        result_data = json.loads(result_json)
        
        if expect_api_error:
            assert "error" in result_data, f"Expected an API error for {test_name}, but got: {result_data}"
            logger.info(f"SUCCESS (expected API error): {test_name} - Error: {result_data.get('error')}")
        elif expect_empty_results_no_error:
            assert "error" not in result_data, f"Expected no error for empty results for {test_name}, but got error: {result_data.get('error')}"
            for key_desc, data_key in expected_keys_map.items():
                assert data_key in result_data, f"Expected key '{data_key}' ({key_desc}) for empty results for {test_name}"
                assert isinstance(result_data[data_key], list), f"Expected list for '{data_key}' ({key_desc}) for {test_name}"
                assert not result_data[data_key], f"Expected empty list for '{data_key}' ({key_desc}) for {test_name}, but got {len(result_data[data_key])} items."
            logger.info(f"SUCCESS (expected empty results): {test_name} - All expected keys found with empty lists.")
        else:
            assert "error" not in result_data, f"Unexpected API error for {test_name}: {result_data.get('error')}"
            
            primary_player_key = expected_keys_map.get("primary_player_key")
            primary_team_key = expected_keys_map.get("primary_team_key")

            assert primary_player_key in result_data, f"Expected primary player key '{primary_player_key}' not found for {test_name}"
            assert isinstance(result_data[primary_player_key], list), f"Key '{primary_player_key}' should be a list for {test_name}"
            
            assert primary_team_key in result_data, f"Expected primary team key '{primary_team_key}' not found for {test_name}"
            assert isinstance(result_data[primary_team_key], list), f"Key '{primary_team_key}' should be a list for {test_name}"

            # Additional specific keys for traditional
            if logic_function == fetch_boxscore_traditional_logic:
                starters_bench_key = expected_keys_map.get("starters_bench_key")
                assert starters_bench_key in result_data, f"Expected key '{starters_bench_key}' for traditional boxscore for {test_name}"
                assert isinstance(result_data[starters_bench_key], list), f"Key '{starters_bench_key}' should be a list for {test_name}"
                logger.info(f"SUCCESS: {test_name} - Fetched. Players: {len(result_data[primary_player_key])}, Teams: {len(result_data[primary_team_key])}, Starters/Bench: {len(result_data[starters_bench_key])}")
            else:
                logger.info(f"SUCCESS: {test_name} - Fetched. {primary_player_key}: {len(result_data[primary_player_key])}, {primary_team_key}: {len(result_data[primary_team_key])}")

            # Optional: Log sample data if needed, but keep smoke tests fast
            # if result_data[primary_player_key]:
            #     logger.debug(f"  Sample Player Stat ({primary_player_key}): {result_data[primary_player_key][0]}")

    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for {test_name}: Could not decode JSON response: {result_json}")
        assert False, f"JSONDecodeError for {test_name}"
    logger.info("-" * 70)

# Define test scenarios
boxscore_tests = [
    ("Traditional Box Score", fetch_boxscore_traditional_logic, {"primary_player_key": "players", "primary_team_key": "teams", "starters_bench_key": "starters_bench"}),
    ("Advanced Box Score", fetch_boxscore_advanced_logic, {"primary_player_key": "player_stats", "primary_team_key": "team_stats"}),
    ("Four Factors Box Score", fetch_boxscore_four_factors_logic, {"primary_player_key": "player_stats", "primary_team_key": "team_stats"}),
    ("Usage Box Score", fetch_boxscore_usage_logic, {"primary_player_key": "player_usage_stats", "primary_team_key": "team_usage_stats"}),
    ("Defensive Box Score", fetch_boxscore_defensive_logic, {"primary_player_key": "player_defensive_stats", "primary_team_key": "team_defensive_stats"}),
]

# Expected datasets for BoxScoreSummaryV2
BOXSCORE_SUMMARY_EXPECTED_DATASETS = {
    "available_video": "list",
    "game_info": "list", # Usually a list with one dict
    "game_summary": "list", # Usually a list with one dict
    "inactive_players": "list",
    "last_meeting": "list", # Usually a list with one dict
    "line_score": "list", # List of dicts (one per team)
    "officials": "list",
    "other_stats": "list", # List of dicts (one per team)
    "season_series": "list" # Usually a list with one dict
}

@pytest.mark.asyncio
@pytest.mark.parametrize("description, logic_func, keys_map", boxscore_tests)
async def test_valid_game_boxscores(description, logic_func, keys_map):
    await run_boxscore_test_with_assertions(
        description=f"{description} - Valid Game",
        logic_function=logic_func,
        game_id=VALID_GAME_ID,
        expected_keys_map=keys_map,
        expect_api_error=False,
        expect_empty_results_no_error=False
    )

@pytest.mark.asyncio
@pytest.mark.parametrize("description, logic_func, keys_map", boxscore_tests)
async def test_invalid_game_id_boxscores(description, logic_func, keys_map):
    await run_boxscore_test_with_assertions(
        description=f"{description} - Invalid Game ID",
        logic_function=logic_func,
        game_id=INVALID_GAME_ID, # Non-existent game ID
        expected_keys_map=keys_map,
        expect_api_error=True, # Expecting an error as game won't be found
        expect_empty_results_no_error=False
    )
    
@pytest.mark.asyncio
@pytest.mark.parametrize("description, logic_func, keys_map", boxscore_tests)
async def test_malformed_game_id_boxscores(description, logic_func, keys_map):
    await run_boxscore_test_with_assertions(
        description=f"{description} - Malformed Game ID",
        logic_function=logic_func,
        game_id=MALFORMED_GAME_ID, # Malformed game ID
        expected_keys_map=keys_map,
        expect_api_error=True, # Expecting an error due to format
        expect_empty_results_no_error=False
    )

# Example for testing with period filters (Traditional Box Score only for this example)
@pytest.mark.asyncio
async def test_traditional_boxscore_with_period_filters():
    description, logic_func, keys_map = boxscore_tests[0] # Get Traditional
    await run_boxscore_test_with_assertions(
        description=f"{description} - Valid Game, Q1 only",
        logic_function=logic_func,
        game_id=VALID_GAME_ID,
        expected_keys_map=keys_map,
        expect_api_error=False,
        expect_empty_results_no_error=False,
        start_period=1,
        end_period=1
    )
    await run_boxscore_test_with_assertions(
        description=f"{description} - Valid Game, Q4 only (may have fewer players if blowout)",
        logic_function=logic_func,
        game_id=VALID_GAME_ID,
        expected_keys_map=keys_map,
        expect_api_error=False,
        expect_empty_results_no_error=False, # Still expect data, even if sparse
        start_period=4,
        end_period=4
    )
    await run_boxscore_test_with_assertions(
        description=f"{description} - Valid Game, Full Game (Periods 0-0)",
        logic_function=logic_func,
        game_id=VALID_GAME_ID,
        expected_keys_map=keys_map,
        expect_api_error=False, # Corrected: Period 0 means full game, no error
        expect_empty_results_no_error=False,
        start_period=0, 
        end_period=0
    )

@pytest.mark.asyncio
async def test_boxscore_summary_valid_game():
    description = "BoxScoreSummaryV2 - Valid Game"
    game_id = VALID_GAME_ID
    logger.info(f"--- Testing {description} (GameID: {game_id}) ---")
    
    result_json = await asyncio.to_thread(fetch_boxscore_summary_logic, game_id=game_id)
    
    try:
        result_data = json.loads(result_json)
        assert "error" not in result_data, f"Unexpected API error for {description}: {result_data.get('error')}"
        assert result_data.get("game_id") == game_id, f"Game ID mismatch in response for {description}"

        for key, expected_type_str in BOXSCORE_SUMMARY_EXPECTED_DATASETS.items():
            assert key in result_data, f"Expected dataset key '{key}' not found in BoxScoreSummaryV2 response for {description}"
            if expected_type_str == "list":
                assert isinstance(result_data[key], list), f"Dataset '{key}' should be a list for {description}"
                # Potentially check if list is not empty for some keys if game is valid, e.g., game_summary, line_score
                if key in ["game_summary", "line_score", "game_info", "other_stats"]:
                     assert len(result_data[key]) > 0, f"Dataset '{key}' should not be empty for a valid game in {description}"
                     if result_data[key]: # Ensure it's not empty before trying to access [0]
                        assert isinstance(result_data[key][0], dict), f"First element of dataset '{key}' should be a dict for {description}"
        
        logger.info(f"SUCCESS: {description} - Fetched and basic structure verified.")

    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for {description}: Could not decode JSON response: {result_json}")
        assert False, f"JSONDecodeError for {description}"
    logger.info("-" * 70)

@pytest.mark.asyncio
async def test_boxscore_summary_invalid_game_id():
    description = "BoxScoreSummaryV2 - Invalid Game ID"
    game_id = INVALID_GAME_ID
    logger.info(f"--- Testing {description} (GameID: {game_id}) ---")
    
    result_json = await asyncio.to_thread(fetch_boxscore_summary_logic, game_id=game_id)
    
    try:
        result_data = json.loads(result_json)
        assert "error" in result_data, f"Expected an API error for {description}, but got: {result_data}"
        logger.info(f"SUCCESS (expected API error): {description} - Error: {result_data.get('error')}")
    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for {description}: Could not decode JSON response: {result_json}")
        assert False, f"JSONDecodeError for {description}"
    logger.info("-" * 70)

@pytest.mark.asyncio
async def test_boxscore_summary_malformed_game_id():
    description = "BoxScoreSummaryV2 - Malformed Game ID"
    game_id = MALFORMED_GAME_ID
    logger.info(f"--- Testing {description} (GameID: {game_id}) ---")
    
    result_json = await asyncio.to_thread(fetch_boxscore_summary_logic, game_id=game_id)
    
    try:
        result_data = json.loads(result_json)
        assert "error" in result_data, f"Expected an API error for {description}, but got: {result_data}"
        # Specifically check for invalid format error if possible, or a generic error
        error_msg = result_data.get("error", "").lower()
        assert "invalid game id format" in error_msg or "malformed" in error_msg or "game_id" in error_msg # more robust check
        logger.info(f"SUCCESS (expected API error for malformed ID): {description} - Error: {result_data.get('error')}")
    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for {description}: Could not decode JSON response: {result_json}")
        assert False, f"JSONDecodeError for {description}"
    logger.info("-" * 70)

if __name__ == "__main__":
    asyncio.run(main())
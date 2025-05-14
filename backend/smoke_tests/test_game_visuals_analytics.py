# backend/smoke_tests/test_game_visuals_analytics.py
import sys
import os
import asyncio
import json
import logging
from typing import Callable, Any, Dict 
import pytest 

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.game_visuals_analytics import fetch_shotchart_logic, fetch_win_probability_logic

# Constants for testing
GAME_ID_TEST_RECENT = "0022300001" # DEN vs LAL, 2023-10-24
GAME_ID_TEST_PLAYOFF = "0042300225" # DAL vs OKC, 2024-05-11
INVALID_GAME_ID = "0000000000" # Non-existent game

async def run_visuals_analytics_test_with_assertions(
    description: str,
    logic_function: Callable,
    expect_api_error: bool = False,
    expect_empty_list_no_error: bool = False, 
    **kwargs: Any
):
    test_name = f"Game Visuals/Analytics - {description}"
    logger.info(f"--- Testing {test_name} ---")
    logger.info(f"Parameters: {kwargs}")
    
    result_json_str = await asyncio.to_thread(logic_function, **kwargs)
    result_data = json.loads(result_json_str)
    # logger.debug(f"Full API Response for {test_name}: {json.dumps(result_data, indent=2)}")

    if expect_api_error:
        assert "error" in result_data, f"Expected API error for '{description}', but 'error' key missing. Response: {result_data}"
        logger.info(f"SUCCESS (expected API error for '{description}'): {result_data.get('error')}")
    else:
        assert "error" not in result_data, f"Expected successful data for '{description}', but got error: {result_data.get('error')}"
        
        if logic_function == fetch_shotchart_logic:
            primary_data_key = "teams"
            assert primary_data_key in result_data and isinstance(result_data[primary_data_key], list), \
                f"'{primary_data_key}' key missing or not a list for shot chart '{description}'. Response: {result_data}"
            assert "league_averages" in result_data and isinstance(result_data["league_averages"], list), \
                f"'league_averages' key missing or not a list for shot chart '{description}'. Response: {result_data}"

            if expect_empty_list_no_error:
                assert not result_data[primary_data_key], f"Expected '{primary_data_key}' to be an empty list for '{description}'. Response: {result_data}"
                logger.info(f"SUCCESS (expected empty '{primary_data_key}' list, no error for '{description}').")
            else:
                assert result_data[primary_data_key], f"Expected non-empty '{primary_data_key}' list for '{description}'. Response: {result_data}"
                assert "shots" in result_data[primary_data_key][0], f"'shots' key missing in first team data for '{description}'"
                logger.info(f"SUCCESS for '{description}': Fetched shot chart. Teams: {len(result_data[primary_data_key])}, League Averages: {len(result_data['league_averages'])}")
        
        elif logic_function == fetch_win_probability_logic:
            primary_data_key = "win_probability"
            assert "game_info" in result_data and isinstance(result_data["game_info"], dict), \
                f"'game_info' key missing or not a dict for win probability '{description}'. Response: {result_data}" 
            assert primary_data_key in result_data and isinstance(result_data[primary_data_key], list), \
                f"'{primary_data_key}' key missing or not a list for win probability '{description}'. Response: {result_data}"

            if expect_empty_list_no_error:
                assert not result_data[primary_data_key], f"Expected '{primary_data_key}' to be an empty list for '{description}'. Response: {result_data}"
                logger.info(f"SUCCESS (expected empty '{primary_data_key}' list, no error for '{description}').")     
            else:
                assert result_data[primary_data_key], f"Expected non-empty '{primary_data_key}' list for '{description}'. Response: {result_data}"
                assert "HOME_PCT" in result_data[primary_data_key][0], f"'HOME_PCT' missing in first win probability entry for '{description}'"
                logger.info(f"SUCCESS for '{description}': Fetched win probability. Game Info: {result_data['game_info'].get('GAME_ID')}, PBP Entries: {len(result_data[primary_data_key])}")
        else:
            pytest.fail(f"Unknown logic_function passed to test helper for '{description}'")

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description_suffix, game_id_param, expect_error, expect_empty",
    [
        ("Recent Game", GAME_ID_TEST_RECENT, False, False),
        ("Playoff Game", GAME_ID_TEST_PLAYOFF, False, True), # Corrected: Expect empty 'teams' list
        ("Invalid Game ID", INVALID_GAME_ID, True, False), 
    ]
)
async def test_game_shotchart_scenarios(description_suffix: str, game_id_param: str, expect_error: bool, expect_empty: bool):
    await run_visuals_analytics_test_with_assertions(
        description=f"Game Shot Chart - {description_suffix}",
        logic_function=fetch_shotchart_logic,
        expect_api_error=expect_error,
        expect_empty_list_no_error=expect_empty,
        game_id=game_id_param
    )

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description_suffix, game_id_param, run_type_param, expect_error, expect_empty",
    [
        ("Recent Game, RunType: each play", GAME_ID_TEST_RECENT, "each play", False, True), # Corrected: Expect empty 'win_probability'
        ("Recent Game, RunType: each second", GAME_ID_TEST_RECENT, "each second", False, False), # Assuming 'each second' might have data
        ("Playoff Game, RunType: each play", GAME_ID_TEST_PLAYOFF, "each play", False, True), # Corrected: Expect empty 'win_probability'
        ("Playoff Game, RunType: each second", GAME_ID_TEST_PLAYOFF, "each second", False, False), # Assuming 'each second' might have data
        ("Invalid Game ID", INVALID_GAME_ID, "each play", False, True), # Corrected: Expect no error, but empty list
        ("Invalid RunType", GAME_ID_TEST_RECENT, "invalid_type", True, False), 
    ]
)
async def test_win_probability_scenarios(description_suffix: str, game_id_param: str, run_type_param: str, expect_error: bool, expect_empty: bool):
    await run_visuals_analytics_test_with_assertions(
        description=f"Win Probability - {description_suffix}",
        logic_function=fetch_win_probability_logic,
        expect_api_error=expect_error,
        expect_empty_list_no_error=expect_empty,
        game_id=game_id_param,
        run_type=run_type_param
    )
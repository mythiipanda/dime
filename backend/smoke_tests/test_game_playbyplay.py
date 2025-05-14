# backend/smoke_tests/test_game_playbyplay.py
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.game_playbyplay import fetch_playbyplay_logic
# from backend.config import settings # Not directly needed by logic function signature

# Example Game IDs
# Recent game (might be live or just concluded, good for testing live fallback)
RECENT_GAME_ID = "0042300225" # DAL vs OKC, 2024-05-11 (Playoffs)
# Older, known completed game (good for testing historical V3)
HISTORICAL_GAME_ID = "0022300001" # DEN vs LAL, 2023-10-24 (Opening Night)

# Renamed and enhanced helper with assertions
async def run_pbp_test_with_assertions(
    description: str,
    game_id: str,
    start_period: int = 0,
    end_period: int = 0,
    expect_api_error: bool = False,
    expect_empty_periods_no_error: bool = False # True if 'periods' key is expected to be an empty list without an error
):
    test_name = f"{description} (GameID: {game_id}, Periods: {start_period}-{end_period})"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json = await asyncio.to_thread(fetch_playbyplay_logic, game_id, start_period, end_period)
    
    try:
        result_data = json.loads(result_json)
        expected_data_key = "periods"
        
        if expect_api_error:
            assert "error" in result_data, f"Expected an API error for {test_name}, but got: {result_data}"
            logger.info(f"SUCCESS (expected API error): {test_name} - Error: {result_data.get('error')}")
        elif expect_empty_periods_no_error:
            assert "error" not in result_data, f"Expected no error for empty periods for {test_name}, but got error: {result_data.get('error')}"
            assert expected_data_key in result_data, f"Expected key '{expected_data_key}' for empty periods for {test_name}"
            assert isinstance(result_data[expected_data_key], list), f"Expected list for '{expected_data_key}' for {test_name}"
            assert not result_data[expected_data_key], f"Expected empty list for '{expected_data_key}' for {test_name}, but got {len(result_data[expected_data_key])} items."
            logger.info(f"SUCCESS (expected empty periods): {test_name} - Found 0 {expected_data_key}, as expected.")
        else:
            assert "error" not in result_data, f"Unexpected API error for {test_name}: {result_data.get('error')}"
            assert expected_data_key in result_data, f"Expected key '{expected_data_key}' not found for {test_name}"
            assert isinstance(result_data[expected_data_key], list), f"Key '{expected_data_key}' should be a list for {test_name}"
            
            if result_data[expected_data_key]:
                logger.info(f"SUCCESS: {test_name} - Fetched PBP. Source: {result_data.get('source')}. Num periods: {len(result_data[expected_data_key])}")
                # if result_data[expected_data_key]:
                #     logger.info(f"  Plays in first returned period: {len(result_data[expected_data_key][0].get('plays', []))}")
                #     if result_data[expected_data_key][0].get('plays'):
                #         logger.info(f"  Sample play: {result_data[expected_data_key][0]['plays'][0].get('description')}")
            else:
                # This covers valid cases where PBP might be empty for specific filters (e.g. start_period > num_periods)
                logger.info(f"SUCCESS (No Data): {test_name} - No PBP data found in '{expected_data_key}' (empty list returned for valid params).")

    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for {test_name}: Could not decode JSON response: {result_json}")
        assert False, f"JSONDecodeError for {test_name}"
    logger.info("-" * 70)

# Parametrized test function
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description, game_id, start_period, end_period, expect_api_error, expect_empty_periods_no_error",
    [
        ("Recent Game PBP (Live/Historical Fallback)", RECENT_GAME_ID, 0, 0, False, False),
        ("Historical Game PBP (V3)", HISTORICAL_GAME_ID, 0, 0, False, False),
        ("Historical Game PBP (Q1 only)", HISTORICAL_GAME_ID, 1, 1, False, False),
        ("Historical Game PBP (Q2-Q3)", HISTORICAL_GAME_ID, 2, 3, False, False),
        ("Invalid Game ID Format PBP", "123", 0, 0, True, False),
        # For a non-existent game ID, the API often returns an error like "Game not found"
        ("Non-existent Game ID PBP", "0000000000", 0, 0, True, False),
    ]
)
async def test_playbyplay_scenarios(description, game_id, start_period, end_period, expect_api_error, expect_empty_periods_no_error):
    await run_pbp_test_with_assertions(
        description=description,
        game_id=game_id,
        start_period=start_period,
        end_period=end_period,
        expect_api_error=expect_api_error,
        expect_empty_periods_no_error=expect_empty_periods_no_error
    )
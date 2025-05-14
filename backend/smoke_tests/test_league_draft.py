# backend/smoke_tests/test_league_draft.py
import sys
import os
import asyncio
import json
import logging
from typing import Optional, Any
import pytest

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.league_draft import fetch_draft_history_logic
from nba_api.stats.library.parameters import LeagueID

# Renamed and enhanced helper with assertions
async def run_draft_test_with_assertions(
    description: str,
    expect_api_error: bool = False,
    expect_empty_results_no_error: bool = False, # True if an empty list is expected without an error
    **kwargs: Any # Type hint for kwargs
):
    filters_str = ", ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    test_name = f"Draft History ({filters_str}) - {description}" # Combine description
    logger.info(f"--- Testing {test_name} ---")
    
    result_json = await asyncio.to_thread(fetch_draft_history_logic, **kwargs)
    
    try:
        result_data = json.loads(result_json)
        expected_data_key = "draft_picks"
        
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
            
            if result_data[expected_data_key]:
                logger.info(f"SUCCESS: {test_name} - Fetched draft history. Picks found: {len(result_data[expected_data_key])}")
                # sample_pick = result_data[expected_data_key][0]
                # logger.info(f"  Sample Pick: Year {sample_pick.get('SEASON')}, Round {sample_pick.get('ROUND_NUMBER')}, Pick {sample_pick.get('OVERALL_PICK')}, Player {sample_pick.get('PLAYER_NAME')}")
            else:
                # This covers cases where params are valid but API returns empty list, e.g., team with no picks in a specific year
                logger.info(f"SUCCESS (No Data): {test_name} - No {expected_data_key} data found (empty list returned for valid params).")

    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for {test_name}: Could not decode JSON response: {result_json}")
        assert False, f"JSONDecodeError for {test_name}" # Fail test on JSON decode error
    logger.info("-" * 70)

# Parametrized test function
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description, kwargs, expect_api_error, expect_empty_results_no_error",
    [
        ("2023 Draft", {"season_year_nullable": "2023"}, False, False),
        ("2022 Draft, Round 1", {"season_year_nullable": "2022", "round_num_nullable": 1}, False, False),
        ("2021 Draft, Lakers", {"season_year_nullable": "2021", "team_id_nullable": 1610612747}, False, False),
        ("2020 Draft, Pick 1", {"season_year_nullable": "2020", "overall_pick_nullable": 1}, False, False),
        # Test for a scenario that might return an API error for an invalid team ID
        ("2019 Draft, NonExistentTeamID", {"season_year_nullable": "2019", "team_id_nullable": 9999999999}, True, False), # Corrected: Expect API error
        ("Invalid Year Format", {"season_year_nullable": "23"}, True, False),
        ("Invalid League ID", {"league_id_nullable": "XYZ"}, True, False),
    ]
)
async def test_draft_history_scenarios(description, kwargs, expect_api_error, expect_empty_results_no_error):
    await run_draft_test_with_assertions(
        description=description,
        expect_api_error=expect_api_error,
        expect_empty_results_no_error=expect_empty_results_no_error,
        **kwargs
    )
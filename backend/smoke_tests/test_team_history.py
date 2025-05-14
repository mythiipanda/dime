import sys
import os
import asyncio
import json
import logging
import pytest
from typing import Optional # Though not strictly needed for this test file, good for consistency

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.team_history import fetch_common_team_years_logic
from backend.config import settings

# Test constants
VALID_LEAGUE_ID_NBA = "00"
VALID_LEAGUE_ID_WNBA = "10"
VALID_LEAGUE_ID_GLEAGUE = "20"
INVALID_LEAGUE_ID_FORMAT = "0"
INVALID_LEAGUE_ID_NONEXISTENT = "99"

async def run_team_years_test(
    league_id: str,
    expect_error: bool = False,
    expected_error_message_fragment: str = "",
    test_description: str = ""
):
    logger.info(f"--- Testing: {test_description} ---")
    logger.info(f"Params: LeagueID='{league_id}'")

    result_json = await asyncio.to_thread(
        fetch_common_team_years_logic,
        league_id=league_id
    )

    try:
        result_data = json.loads(result_json)
        # logger.info(f"Result for '{test_description}': {json.dumps(result_data, indent=2)}") # Uncomment for detailed output

        if expect_error:
            assert "error" in result_data, f"Expected an error for '{test_description}', but got success."
            if expected_error_message_fragment:
                assert expected_error_message_fragment.lower() in result_data["error"].lower(), \
                    f"Expected error for '{test_description}' to contain '{expected_error_message_fragment}', but got: {result_data['error']}"
            logger.info(f"SUCCESS (expected error): '{test_description}' - Error: {result_data.get('error')}")
        else:
            assert "error" not in result_data, f"Unexpected error for '{test_description}': {result_data.get('error')}"
            assert "parameters" in result_data, f"Missing 'parameters' key for '{test_description}'"
            assert result_data["parameters"]["league_id"] == league_id
            assert "team_years" in result_data, f"Missing 'team_years' key for '{test_description}'"
            assert isinstance(result_data["team_years"], list), f"'team_years' should be a list for '{test_description}'"
            
            # if not expect_error and league_id == VALID_LEAGUE_ID_NBA: # Removed print
            #     logger.info(f"First 3 NBA team year entries for '{test_description}': {json.dumps(result_data['team_years'][:3], indent=2)}")

            assert len(result_data["team_years"]) > 0, f"Expected team years data for '{test_description}', but got none."
            
            # Check a few expected keys in the first entry
            first_entry = result_data["team_years"][0]
            expected_keys = ["LEAGUE_ID", "TEAM_ID", "MIN_YEAR", "MAX_YEAR", "ABBREVIATION"]
            for key in expected_keys:
                assert key in first_entry, f"Key '{key}' missing in team_years data for '{test_description}'"
            
            assert first_entry["LEAGUE_ID"] == league_id

            logger.info(f"SUCCESS: '{test_description}' - Found {len(result_data['team_years'])} entries.")

    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for '{test_description}': Could not decode response: {result_json}")
        assert False, f"JSONDecodeError for '{test_description}'"
    logger.info("-" * 70)

@pytest.mark.asyncio
async def test_team_years_valid_nba():
    await run_team_years_test(
        league_id=VALID_LEAGUE_ID_NBA,
        test_description="Valid League ID - NBA (00)"
    )

@pytest.mark.asyncio
async def test_team_years_valid_wnba():
    await run_team_years_test(
        league_id=VALID_LEAGUE_ID_WNBA,
        test_description="Valid League ID - WNBA (10)"
    )

@pytest.mark.asyncio
async def test_team_years_valid_gleague():
    await run_team_years_test(
        league_id=VALID_LEAGUE_ID_GLEAGUE,
        test_description="Valid League ID - G-League (20)"
    )

@pytest.mark.asyncio
async def test_team_years_invalid_league_id_format():
    await run_team_years_test(
        league_id=INVALID_LEAGUE_ID_FORMAT,
        expect_error=True,
        expected_error_message_fragment="Invalid league_id",
        test_description="Invalid League ID format"
    )

@pytest.mark.asyncio
async def test_team_years_invalid_league_id_nonexistent():
    # The nba_api might still return a success with an empty list for some invalid IDs if the API itself doesn't error out.
    # The _validate_league_id function should catch truly invalid ones before API call.
    # If _validate_league_id passes it but API returns empty, it is still a valid test (no error from our code).
    # However, a non-existent but correctly formatted ID like "99" *should* be caught by our _validate_league_id.
    await run_team_years_test(
        league_id=INVALID_LEAGUE_ID_NONEXISTENT,
        expect_error=True, # because our _validate_league_id should catch it
        expected_error_message_fragment="Invalid league_id",
        test_description="Invalid League ID - Non-existent (99)"
    )

# if __name__ == "__main__":
#     async def main():
#         await test_team_years_valid_nba()
#         await test_team_years_valid_wnba()
#         await test_team_years_valid_gleague()
#         await test_team_years_invalid_league_id_format()
#         await test_team_years_invalid_league_id_nonexistent()
#     asyncio.run(main()) 
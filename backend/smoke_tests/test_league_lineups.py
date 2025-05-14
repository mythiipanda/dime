import sys
import os
import asyncio
import json
import logging
import pytest
from typing import Optional

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.league_lineups import fetch_league_dash_lineups_logic
from backend.config import settings # For CURRENT_NBA_SEASON
from nba_api.stats.library.parameters import (
    GroupQuantity,
    MeasureTypeDetailedDefense,
    PerModeDetailed,
    SeasonTypeAllStar
)

# Test constants
VALID_SEASON = settings.CURRENT_NBA_SEASON # Use current season for most tests
PAST_VALID_SEASON = "2022-23"
INVALID_SEASON_FORMAT = "2023"
INVALID_DATE_FORMAT = "01-01-2023"
VALID_DATE_FROM = "2023-12-01"
VALID_DATE_TO = "2023-12-31"
VALID_TEAM_ID_BUCKS = 1610612749 
INVALID_TEAM_ID_STR = "ABC"

async def run_league_lineups_test(
    test_description: str,
    season: str,
    group_quantity: int = GroupQuantity.default,
    measure_type: str = MeasureTypeDetailedDefense.base,
    per_mode: str = PerModeDetailed.totals,
    season_type: str = "Regular Season",
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    team_id_nullable: Optional[int] = None,
    expect_error: bool = False,
    expected_error_message_fragment: Optional[str] = None
):
    logger.info(f"--- Testing: {test_description} ---")
    # Log only a subset of params for brevity
    logger.info(f"Params: Season='{season}', GroupQty='{group_quantity}', Measure='{measure_type}', PerMode='{per_mode}', TeamID='{team_id_nullable}'")

    result_json = await asyncio.to_thread(
        fetch_league_dash_lineups_logic,
        season=season,
        group_quantity=group_quantity,
        measure_type=measure_type,
        per_mode=per_mode,
        season_type=season_type,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        team_id_nullable=team_id_nullable
        # Add other params here as needed for specific tests
    )

    try:
        result_data = json.loads(result_json)
        # logger.info(f"Result for '{test_description}': {json.dumps(result_data, indent=2)}") # Uncomment for detailed output

        if expect_error:
            assert "error" in result_data, f"Expected an error for '{test_description}', but got success: {result_data.get('lineups', [])[:1]}"
            if expected_error_message_fragment:
                assert expected_error_message_fragment.lower() in result_data["error"].lower(), \
                    f"Expected error for '{test_description}' to contain '{expected_error_message_fragment}', but got: {result_data['error']}"
            logger.info(f"SUCCESS (expected error): '{test_description}' - Error: {result_data.get('error')}")
        else:
            assert "error" not in result_data, f"Unexpected error for '{test_description}': {result_data.get('error')}"
            assert "parameters" in result_data, f"Missing 'parameters' key for '{test_description}'"
            assert result_data["parameters"]["season"] == season
            assert "lineups" in result_data, f"Missing 'lineups' key for '{test_description}'"
            assert isinstance(result_data["lineups"], list), f"'lineups' should be a list for '{test_description}'"
            
            # Basic check: if data is returned, it should have entries
            # This endpoint can return 0 lineups for very specific filters, so only assert > 0 for broad queries.
            if team_id_nullable is None and date_from_nullable is None: # Broad query
                assert len(result_data["lineups"]) > 0, f"Expected lineup data for broad query '{test_description}', but got none."
            
            if result_data["lineups"]:
                first_lineup = result_data["lineups"][0]
                # Define base expected keys common to most/all measure types
                expected_keys = ["GROUP_ID", "GROUP_NAME", "TEAM_ID", "TEAM_ABBREVIATION", "GP", "MIN"]
                
                # Add/modify keys based on measure_type
                if measure_type == MeasureTypeDetailedDefense.base: # Or whatever the actual default/base value is
                    expected_keys.extend(["PTS", "FGM", "FGA"]) # Add typical base stats
                elif measure_type == MeasureTypeDetailedDefense.advanced:
                    expected_keys.extend(["OFF_RATING", "DEF_RATING", "NET_RATING"]) # Add typical advanced stats
                # Add more conditions for other measure types if necessary

                for key in expected_keys:
                    assert key in first_lineup, f"Key '{key}' missing in lineup data for '{test_description}' (MeasureType: {measure_type}) from {first_lineup.keys()}"

            logger.info(f"SUCCESS: '{test_description}' - Found {len(result_data['lineups'])} lineup entries.")

    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for '{test_description}': Could not decode response: {result_json}")
        assert False, f"JSONDecodeError for '{test_description}'"
    logger.info("-" * 70)

@pytest.mark.asyncio
async def test_lineups_default_params_current_season():
    await run_league_lineups_test(
        test_description="Default parameters, current season",
        season=VALID_SEASON
    )

@pytest.mark.asyncio
async def test_lineups_default_params_past_season():
    await run_league_lineups_test(
        test_description="Default parameters, past season",
        season=PAST_VALID_SEASON
    )

@pytest.mark.asyncio
async def test_lineups_2man_lineups_advanced_stats():
    await run_league_lineups_test(
        test_description="2-man lineups, Advanced stats, PerGame",
        season=PAST_VALID_SEASON,
        group_quantity=2,
        measure_type=MeasureTypeDetailedDefense.advanced,
        per_mode=PerModeDetailed.per_game
    )

@pytest.mark.asyncio
async def test_lineups_specific_team_regular_season():
    await run_league_lineups_test(
        test_description="Specific team (Bucks), Regular Season, 5-man lineups, Base stats",
        season=PAST_VALID_SEASON,
        group_quantity=5,
        measure_type=MeasureTypeDetailedDefense.base,
        season_type="Regular Season",
        team_id_nullable=VALID_TEAM_ID_BUCKS
    )

@pytest.mark.asyncio
async def test_lineups_date_range_filter():
    await run_league_lineups_test(
        test_description="Date range filter (Dec 2023)",
        season="2023-24", # Season containing the date range
        date_from_nullable=VALID_DATE_FROM,
        date_to_nullable=VALID_DATE_TO
    )

@pytest.mark.asyncio
async def test_lineups_invalid_season_format():
    await run_league_lineups_test(
        test_description="Invalid season format",
        season=INVALID_SEASON_FORMAT,
        expect_error=True,
        expected_error_message_fragment="Invalid season format"
    )

@pytest.mark.asyncio
async def test_lineups_invalid_date_from_format():
    await run_league_lineups_test(
        test_description="Invalid DateFrom format",
        season=VALID_SEASON,
        date_from_nullable=INVALID_DATE_FORMAT,
        expect_error=True,
        expected_error_message_fragment="Invalid date format"
    )

@pytest.mark.asyncio
async def test_lineups_invalid_team_id_type():
    await run_league_lineups_test(
        test_description="Invalid TeamID type (string instead of int)",
        season=VALID_SEASON,
        team_id_nullable=INVALID_TEAM_ID_STR, # type: ignore
        expect_error=True, # This should be caught by our Pydantic models eventually, or _validate_team_id if adapted
        expected_error_message_fragment="Invalid Team ID"
    )

# if __name__ == "__main__":
#     async def main():
#         # Basic tests
#         await test_lineups_default_params_current_season()
#         await test_lineups_default_params_past_season()
#         # More specific filters
#         await test_lineups_2man_lineups_advanced_stats()
#         await test_lineups_specific_team_regular_season()
#         await test_lineups_date_range_filter()
#         # Error cases
#         await test_lineups_invalid_season_format()
#         await test_lineups_invalid_date_from_format()
#         await test_lineups_invalid_team_id_type()
#     asyncio.run(main()) 
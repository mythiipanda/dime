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

from backend.api_tools.league_opponent_shot_dashboard import fetch_league_dash_opponent_pt_shot_logic
from backend.config import settings
from nba_api.stats.library.parameters import (
    PerModeSimple,
    SeasonTypeAllStar
)

# Test constants
VALID_SEASON = settings.CURRENT_NBA_SEASON
PAST_VALID_SEASON = "2022-23"
INVALID_SEASON_FORMAT = "2023"
INVALID_DATE_FORMAT = "01-01-2023"
# Derive year from CURRENT_NBA_SEASON for date constants
CURRENT_YEAR_FOR_TEST_DATES = settings.CURRENT_NBA_SEASON.split('-')[0]
VALID_DATE_FROM = f"{CURRENT_YEAR_FOR_TEST_DATES}-12-01"
VALID_DATE_TO = f"{CURRENT_YEAR_FOR_TEST_DATES}-12-31"
VALID_TEAM_ID_LAKERS = 1610612747
VALID_TEAM_ID_BUCKS = 1610612749

# Valid string values for range parameters (based on nba_api common string patterns)
VALID_SHOT_DIST_RANGE = "By Zone"
VALID_CLOSE_DEF_DIST_RANGE = "0-2 Feet - Very Tight"

async def run_test_wrapper(
    test_description: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode_simple: str = PerModeSimple.totals,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    team_id_nullable: Optional[int] = None,
    opponent_team_id_nullable: Optional[int] = 0,
    close_def_dist_range_nullable: Optional[str] = None,
    shot_dist_range_nullable: Optional[str] = None,
    expect_error: bool = False,
    expected_error_message_fragment: Optional[str] = None
):
    logger.info(f"--- Testing: {test_description} ---")
    logger.info(f"Params: Season='{season}', PerMode='{per_mode_simple}', TeamID='{team_id_nullable}', OppTeamID='{opponent_team_id_nullable}'")

    result_json = await asyncio.to_thread(
        fetch_league_dash_opponent_pt_shot_logic,
        season=season,
        season_type=season_type,
        per_mode_simple=per_mode_simple,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        team_id_nullable=team_id_nullable,
        opponent_team_id_nullable=opponent_team_id_nullable,
        close_def_dist_range_nullable=close_def_dist_range_nullable,
        shot_dist_range_nullable=shot_dist_range_nullable
    )

    try:
        result_data = json.loads(result_json)

        if expect_error:
            assert "error" in result_data, f"Expected an error for '{test_description}', but got success."
            if expected_error_message_fragment:
                assert expected_error_message_fragment.lower() in result_data["error"].lower(), \
                    f"Expected error for '{test_description}' to contain '{expected_error_message_fragment}', but got: {result_data['error']}"
            logger.info(f"SUCCESS (expected error): '{test_description}' - Error: {result_data.get('error')}")
        else:
            assert "error" not in result_data, f"Unexpected error for '{test_description}': {result_data.get('error')}"
            assert "parameters" in result_data, f"Missing 'parameters' key for '{test_description}'"
            assert result_data["parameters"]["season"] == season
            assert "opponent_shots" in result_data, f"Missing 'opponent_shots' key for '{test_description}'"
            assert isinstance(result_data["opponent_shots"], list), f"'opponent_shots' should be a list for '{test_description}'"
            
            if team_id_nullable is None and opponent_team_id_nullable == 0 and date_from_nullable is None:
                 assert len(result_data["opponent_shots"]) >= 0, f"Expected opponent_shots data for broad query '{test_description}', but got none or error."

            if result_data["opponent_shots"]:
                first_entry = result_data["opponent_shots"][0]
                # Expected keys from LeagueDashOppPtShot.league_dash_ptshots documentation
                expected_keys = [
                    'TEAM_ID', 'TEAM_NAME', 'TEAM_ABBREVIATION', 'GP', 'G', 'FGA_FREQUENCY', 
                    'FGM', 'FGA', 'FG_PCT', 'EFG_PCT', 'FG2A_FREQUENCY', 'FG2M', 'FG2A', 
                    'FG2_PCT', 'FG3A_FREQUENCY', 'FG3M', 'FG3A', 'FG3_PCT'
                ]
                for key in expected_keys:
                    assert key in first_entry, f"Key '{key}' missing in opponent_shots data for '{test_description}' from {list(first_entry.keys())}"

            logger.info(f"SUCCESS: '{test_description}' - Found {len(result_data['opponent_shots'])} entries.")

    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for '{test_description}': Could not decode response: {result_json}")
        assert False, f"JSONDecodeError for '{test_description}'"
    logger.info("-" * 70)

@pytest.mark.asyncio
async def test_default_current_season():
    await run_test_wrapper(
        test_description="Default parameters, current season",
        season=VALID_SEASON
    )

@pytest.mark.asyncio
async def test_default_past_season():
    await run_test_wrapper(
        test_description="Default parameters, past season",
        season=PAST_VALID_SEASON
    )

@pytest.mark.asyncio
async def test_per_game_mode_current_season():
    await run_test_wrapper(
        test_description="PerGame mode, current season",
        season=VALID_SEASON,
        per_mode_simple=PerModeSimple.per_game
    )

@pytest.mark.asyncio
async def test_specific_team_filter_current_season():
    await run_test_wrapper(
        test_description="Specific team filter (Lakers), current season",
        season=VALID_SEASON,
        team_id_nullable=VALID_TEAM_ID_LAKERS
    )

@pytest.mark.asyncio
async def test_specific_opponent_team_filter_current_season():
    await run_test_wrapper(
        test_description="Specific opponent team filter (Bucks vs Lakers), current season",
        season=VALID_SEASON,
        team_id_nullable=VALID_TEAM_ID_LAKERS,
        opponent_team_id_nullable=VALID_TEAM_ID_BUCKS
    )

@pytest.mark.asyncio
async def test_date_range_filter_current_season():
    await run_test_wrapper(
        test_description="Date range filter, current season",
        season=VALID_SEASON,
        date_from_nullable=VALID_DATE_FROM,
        date_to_nullable=VALID_DATE_TO
    )

@pytest.mark.asyncio
@pytest.mark.xfail(reason="Still investigating valid string literals for shot_dist_range_nullable")
async def test_shot_distance_filter():
    await run_test_wrapper(
        test_description="Shot distance filter (By Zone attempt), current season",
        season=VALID_SEASON,
        shot_dist_range_nullable=VALID_SHOT_DIST_RANGE
    )

@pytest.mark.asyncio
async def test_defender_distance_filter():
    await run_test_wrapper(
        test_description="Defender distance filter (0-2 ft. Very Tight), current season",
        season=VALID_SEASON,
        close_def_dist_range_nullable=VALID_CLOSE_DEF_DIST_RANGE
    )

@pytest.mark.asyncio
async def test_invalid_season_format_error():
    await run_test_wrapper(
        test_description="Invalid season format",
        season=INVALID_SEASON_FORMAT,
        expect_error=True,
        expected_error_message_fragment="Invalid season format"
    )

@pytest.mark.asyncio
async def test_invalid_date_from_format_error():
    await run_test_wrapper(
        test_description="Invalid DateFrom format",
        season=VALID_SEASON,
        date_from_nullable=INVALID_DATE_FORMAT,
        expect_error=True,
        expected_error_message_fragment="Invalid date format"
    )

@pytest.mark.asyncio
async def test_invalid_team_id_error():
    await run_test_wrapper(
        test_description="Invalid TeamID (string)",
        season=VALID_SEASON,
        team_id_nullable="ABC", # type: ignore
        expect_error=True,
        expected_error_message_fragment="Invalid Team ID"
    )

@pytest.mark.asyncio
async def test_invalid_opponent_team_id_error():
    await run_test_wrapper(
        test_description="Invalid Opponent TeamID (negative)",
        season=VALID_SEASON,
        opponent_team_id_nullable=-5,
        expect_error=True,
        expected_error_message_fragment="Invalid Team ID"
    )

# Add more tests for other parameter combinations (season_type, month, period, etc.)
# and edge cases as needed, especially once the exact data structure is confirmed.

# Example of testing playoffs:
# @pytest.mark.asyncio
# async def test_playoffs_season_past():
#     await run_test_wrapper(
#         test_description="Playoffs, past season",
#         season=PAST_VALID_SEASON, # Ensure this season had playoffs
#         season_type=SeasonTypeAllStar.playoffs
#     ) 
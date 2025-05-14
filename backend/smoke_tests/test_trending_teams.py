# backend/smoke_tests/test_trending_teams.py
import sys
import os
import asyncio
import json
import logging
from typing import Optional, Dict, Any 
import pytest 

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.trending_team_tools import fetch_top_teams_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID
from backend.config import settings

# Test Constants
CURRENT_SEASON = settings.CURRENT_NBA_SEASON
PAST_SEASON = "2022-23"

async def run_trending_teams_test_with_assertions(
    description: str, 
    expect_api_error: bool = False, 
    expect_empty_list_no_error: bool = False, 
    **kwargs: Any
):
    filters_list = [f"{k}={v}" for k, v in kwargs.items() if v is not None]
    filters_str = ", ".join(filters_list)
    test_name = f"Top Teams ({filters_str}) - {description}"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json_str = await asyncio.to_thread(fetch_top_teams_logic, **kwargs)
    result_data = json.loads(result_json_str)
    # logger.debug(f"Full API Response for {test_name}: {json.dumps(result_data, indent=2)}")

    if expect_api_error:
        assert "error" in result_data, f"Expected API error for '{description}', but 'error' key missing. Response: {result_data}"
        assert "top_teams" not in result_data or not result_data.get("top_teams"), \
            f"Expected 'top_teams' to be absent or empty on API error for '{description}'. Response: {result_data}"
        logger.info(f"SUCCESS (expected API error for '{description}'): {result_data.get('error')}")
    elif expect_empty_list_no_error:
        assert "error" not in result_data, f"Expected no error for empty list for '{description}', but got: {result_data.get('error')}"
        assert "requested_top_n" in result_data, f"'requested_top_n' key missing for empty list case for '{description}'"
        assert "top_teams" in result_data and isinstance(result_data["top_teams"], list) and not result_data["top_teams"], \
            f"Expected 'top_teams' to be an empty list for '{description}'. Response: {result_data}"
        logger.info(f"SUCCESS (expected empty list, no error for '{description}'). Requested Top N: {result_data.get('requested_top_n')}")
    else: # Expect successful data
        assert "error" not in result_data, f"Expected successful data for '{description}', but got error: {result_data.get('error')}"
        assert "requested_top_n" in result_data, f"'requested_top_n' key missing for '{description}'"
        assert "top_teams" in result_data and isinstance(result_data["top_teams"], list), \
            f"'top_teams' key missing or not a list for '{description}'. Response: {result_data}"
        
        if result_data["top_teams"]:
            assert len(result_data["top_teams"]) <= result_data["requested_top_n"], \
                f"Returned more teams ({len(result_data['top_teams'])}) than requested ({result_data['requested_top_n']})."
            
            sample_team = result_data["top_teams"][0]
            assert "TeamName" in sample_team, f"'TeamName' missing in sample team for '{description}'"
            assert "WinPct" in sample_team, f"'WinPct' missing in sample team for '{description}'"
            
            logger.info(f"SUCCESS for '{description}': Fetched {len(result_data['top_teams'])} top teams. Requested Top N: {result_data['requested_top_n']}.")
            logger.info(f"  Sample Top Team: {sample_team.get('TeamName')} (WinPct: {sample_team.get('WinPct')})")
        else:
            logger.info(f"SUCCESS for '{description}': Fetched 0 top teams (empty list for valid params). Requested Top N: {result_data.get('requested_top_n')}")

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description_suffix, params, expect_error, expect_empty",
    [
        ("NBA Defaults", {}, False, False),
        (
            f"NBA {PAST_SEASON} Top 3", 
            {"season": PAST_SEASON, "top_n": 3},
            False, False
        ),
        (
            f"NBA {CURRENT_SEASON} Playoffs Top 10", 
            {"season": CURRENT_SEASON, "season_type": SeasonTypeAllStar.playoffs, "top_n": 10},
            True, False # Corrected: Expect API error as 'Playoffs' is invalid season_type for standings
        ),
        (
            f"WNBA {CURRENT_SEASON} Top 5", 
            {"league_id": LeagueID.wnba, "season": CURRENT_SEASON, "top_n": 5},
            False, False # Corrected: Expect data, API seems to handle NBA season format for WNBA
        ),
        (
            f"WNBA 2023 (Expect Season Format Error)", 
            {"league_id": LeagueID.wnba, "season": "2023", "top_n": 3},
            True, False 
        ),
        (
            f"NBA {PAST_SEASON} Invalid Top N (0)", 
            {"season": PAST_SEASON, "top_n": 0},
            True, False 
        ),
        (
            f"Invalid League ID",
            {"league_id": "99", "season": PAST_SEASON},
            True, False 
        ),
    ]
)
async def test_trending_teams_scenarios(description_suffix: str, params: Dict[str, Any], expect_error: bool, expect_empty: bool):
    await run_trending_teams_test_with_assertions(
        description=description_suffix,
        expect_api_error=expect_error,
        expect_empty_list_no_error=expect_empty,
        **params
    )
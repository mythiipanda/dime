# backend/smoke_tests/test_trending_teams.py
import sys
import os
import asyncio
import json
import logging
from typing import Optional

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.trending_team_tools import fetch_top_teams_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID
from backend.config import settings

async def run_trending_teams_test(test_name_suffix: str, **kwargs):
    filters_list = [f"{k}={v}" for k, v in kwargs.items() if v is not None]
    filters_str = ", ".join(filters_list)
    test_name = f"Top Teams ({filters_str}{test_name_suffix})"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json = await asyncio.to_thread(fetch_top_teams_logic, **kwargs)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" not in result_data:
            if "top_teams" in result_data and isinstance(result_data["top_teams"], list):
                logger.info(f"SUCCESS: {test_name} - Fetched top teams. Count: {len(result_data['top_teams'])}")
                if result_data["top_teams"]:
                    sample_team = result_data["top_teams"][0]
                    logger.info(f"  Sample Top Team: {sample_team.get('TeamName')} (WinPct: {sample_team.get('WinPct')})")
                # Verify requested_top_n matches len(top_teams) if data is abundant
                requested_top_n = result_data.get("requested_top_n", -1)
                if len(result_data["top_teams"]) > requested_top_n :
                     logger.warning(f"  WARN: Returned more teams ({len(result_data['top_teams'])}) than requested ({requested_top_n}).")
                elif len(result_data["top_teams"]) < requested_top_n and len(result_data["top_teams"]) > 0 :
                     logger.info(f"  NOTE: Returned fewer teams ({len(result_data['top_teams'])}) than requested ({requested_top_n}), likely all available teams.")


            elif "top_teams" in result_data and not result_data["top_teams"]:
                 logger.info(f"SUCCESS (No Data): {test_name} - No top teams found (empty list returned).")
            else:
                logger.warning(f"WARNING: {test_name} - Data structure not as expected.")
                print(json.dumps(result_data, indent=2))
        elif "error" in result_data:
            logger.error(f"ERROR for {test_name}: {result_data['error']}")
        else:
            logger.warning(f"WARNING: Unexpected response structure for {test_name}.")
            
    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON response for {test_name}: {result_json}")
    logger.info("-" * 70)

async def main():
    current_season = settings.CURRENT_NBA_SEASON
    past_season = "2022-23" 
    # WNBA League ID is "10", NBA is "00"
    # WNBA seasons are single years, e.g., "2023" for 2023 WNBA season.
    # Our _validate_season_format expects YYYY-YY. This will need adjustment if we want to properly test WNBA.
    # For now, let's assume _validate_season_format will fail WNBA single year season.
    # We can test if league_id="10" is passed to underlying logic, even if season format causes error.

    # Test 1: Default params (NBA, current season, top 5)
    await run_trending_teams_test(" - NBA Defaults")

    # Test 2: NBA, Top 3 for a past season
    await run_trending_teams_test(f" - NBA {past_season} Top 3", 
                                  season=past_season, 
                                  top_n=3)

    # Test 3: NBA, Top 10 for Playoffs, current season
    # Note: 2024-25 Playoffs data might be empty if season not started/concluded.
    await run_trending_teams_test(f" - NBA {current_season} Playoffs Top 10", 
                                  season_type=SeasonTypeAllStar.playoffs,
                                  top_n=10)

    # Test 4: WNBA (LeagueID '10'), current NBA season format (might error on season format for WNBA)
    # This tests if league_id is passed, even if season format is an issue for WNBA.
    # The fetch_league_standings_logic will use this league_id.
    await run_trending_teams_test(f" - WNBA {current_season} Top 5", 
                                  league_id=LeagueID.wnba, # "10"
                                  season=current_season, # Using NBA season format
                                  top_n=5)
    
    # Test 5: WNBA with a WNBA-like season format (e.g., "2023") - this will fail season validation
    # but shows the league_id would be passed if season was valid.
    # Our _validate_season_format expects YYYY-YY.
    # This test is more to demonstrate the league_id would be attempted.
    await run_trending_teams_test(f" - WNBA 2023 (Expect Season Format Error)", 
                                  league_id=LeagueID.wnba,
                                  season="2023", # WNBA style season, but our validator expects YYYY-YY
                                  top_n=3)


    # Test 6: Invalid top_n
    await run_trending_teams_test(f" - NBA {past_season} Invalid Top N", 
                                  season=past_season, 
                                  top_n=0)
    
    # Test 7: Invalid League ID
    await run_trending_teams_test(f" - Invalid League ID",
                                  league_id="99",
                                  season=past_season)


if __name__ == "__main__":
    asyncio.run(main())
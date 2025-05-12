# backend/smoke_tests/test_team_info_roster.py
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

from backend.api_tools.team_info_roster import fetch_team_info_and_roster_logic
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar
from backend.config import settings

async def run_team_info_test(test_name_suffix: str, team_identifier: str, **kwargs):
    test_name = f"Team Info & Roster ({team_identifier}{test_name_suffix})"
    logger.info(f"--- Testing {test_name} ---")
    
    params = {"team_identifier": team_identifier, **kwargs}

    result_json = await asyncio.to_thread(fetch_team_info_and_roster_logic, **params)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" not in result_data:
            if result_data.get("team_id") and "info" in result_data and "roster" in result_data:
                logger.info(f"SUCCESS: {test_name} - Fetched data for Team ID: {result_data['team_id']} ({result_data.get('team_name')}).")
                logger.info(f"  Info keys: {list(result_data['info'].keys()) if result_data['info'] else 'No info'}")
                logger.info(f"  Roster size: {len(result_data['roster'])}")
                logger.info(f"  Coaches count: {len(result_data['coaches'])}")
                if result_data.get("partial_errors"):
                    logger.warning(f"  Partial errors reported: {result_data['partial_errors']}")
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
    # Test 1: Valid team identifier (e.g., Lakers ID) for current season (default)
    await run_team_info_test(" - Lakers, Current Season", team_identifier="1610612747")

    # Test 2: Valid team abbreviation for a past season
    await run_team_info_test(" - BOS, 2022-23", team_identifier="BOS", season="2022-23")
    
    # Test 3: Valid team name for a past season, playoffs
    await run_team_info_test(" - Golden State Warriors, 2021-22 Playoffs", 
                             team_identifier="Golden State Warriors", 
                             season="2021-22", 
                             season_type=SeasonTypeAllStar.playoffs)

    # Test 4: Invalid team identifier
    await run_team_info_test(" - Invalid Team", team_identifier="INVALID_TEAM_XYZ")

    # Test 5: Valid team, invalid season format
    await run_team_info_test(" - Lakers, Invalid Season", team_identifier="LAL", season="2023")
    
    # Test 6: Valid team, invalid season type
    await run_team_info_test(" - Lakers, Invalid Season Type", team_identifier="LAL", season_type="InvalidType")

if __name__ == "__main__":
    asyncio.run(main())
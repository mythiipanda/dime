# backend/smoke_tests/test_league_standings.py
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

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Changed level to DEBUG and added logger name
logger = logging.getLogger(__name__)

from backend.api_tools.league_standings import fetch_league_standings_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar 
from backend.config import settings # For settings.CURRENT_NBA_SEASON

async def run_standings_test(test_name_suffix: str, season: Optional[str] = None, season_type: Optional[str] = None):
    effective_season = season if season is not None else settings.CURRENT_NBA_SEASON
    effective_season_type = season_type if season_type is not None else SeasonTypeAllStar.regular
    
    test_name = f"League Standings ({effective_season} {effective_season_type}{test_name_suffix})"
    logger.info(f"--- Testing {test_name} ---")
    
    params = {}
    if season is not None: # Only pass if not using default from logic function
        params['season'] = season
    if season_type is not None: # Only pass if not using default from logic function
        params['season_type'] = season_type

    result_json = await asyncio.to_thread(fetch_league_standings_logic, **params)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" not in result_data:
            if "standings" in result_data and isinstance(result_data["standings"], list):
                logger.info(f"SUCCESS: {test_name} - Fetched standings. Teams found: {len(result_data['standings'])}")
                if result_data["standings"]:
                    sample_team = result_data["standings"][0]
                    logger.info(f"  Sample Team: {sample_team.get('TeamCity')} {sample_team.get('TeamName')}, Rank: {sample_team.get('PlayoffRank')}, GB: {sample_team.get('GB')}")
            elif "standings" in result_data and not result_data["standings"]:
                 logger.info(f"SUCCESS: {test_name} - No standings data found (empty list returned as expected for these params).")
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
    # Test 1: Current season (or default from settings), regular season (default)
    await run_standings_test(" - Default Season/Type")

    # Test 2: Specific past season, regular season
    await run_standings_test(" - 2022-23 Regular", season="2022-23", season_type=SeasonTypeAllStar.regular)

    # Test 3: Specific past season, playoffs
    # Note: Playoff standings might be empty if that season's playoffs didn't have specific standings data via this endpoint
    # or if it's structured differently. The API might just return regular season standings for "Playoffs" type.
    await run_standings_test(" - 2022-23 Playoffs", season="2022-23", season_type=SeasonTypeAllStar.playoffs)

    # Test 4: Invalid season format
    await run_standings_test(" - Invalid Season Format", season="2023", season_type=SeasonTypeAllStar.regular)
    
    # Test 5: Invalid season type
    await run_standings_test(" - Invalid Season Type", season="2022-23", season_type="InvalidType")


if __name__ == "__main__":
    asyncio.run(main())
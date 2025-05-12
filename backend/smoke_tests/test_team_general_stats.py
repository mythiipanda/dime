# backend/smoke_tests/test_team_general_stats.py
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

from backend.api_tools.team_general_stats import fetch_team_stats_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailedDefense, LeagueID
from backend.config import settings

async def run_team_stats_test(test_name_suffix: str, team_identifier: str, **kwargs):
    test_name = f"Team General Stats ({team_identifier}{test_name_suffix})"
    logger.info(f"--- Testing {test_name} ---")
    
    params = {"team_identifier": team_identifier, **kwargs}

    result_json = await asyncio.to_thread(fetch_team_stats_logic, **params)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" not in result_data:
            if result_data.get("team_id") and "current_stats" in result_data and "historical_stats" in result_data:
                logger.info(f"SUCCESS: {test_name} - Fetched data for Team ID: {result_data['team_id']} ({result_data.get('team_name')}).")
                logger.info(f"  Current Stats Keys: {list(result_data['current_stats'].keys()) if result_data['current_stats'] else 'No current stats'}")
                logger.info(f"  Historical Stats Count: {len(result_data['historical_stats'])}")
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
    lakers_id = "1610612747"
    celtics_abbrev = "BOS"
    current_season = settings.CURRENT_NBA_SEASON
    past_season = "2022-23"

    # Test 1: Default params for a team (current season, regular, pergame, base)
    await run_team_stats_test(" - Lakers, Defaults", team_identifier=lakers_id)

    # Test 2: Specific season, different PerMode and MeasureType
    await run_team_stats_test(f" - Celtics, {past_season}, Totals, Advanced", 
                              team_identifier=celtics_abbrev, 
                              season=past_season,
                              per_mode=PerModeDetailed.totals,
                              measure_type=MeasureTypeDetailedDefense.advanced)

    # Test 3: Date range filter (e.g., a specific month in a season)
    await run_team_stats_test(f" - Lakers, {past_season}, Dec 2022", 
                              team_identifier=lakers_id, 
                              season=past_season,
                              date_from="2022-12-01",
                              date_to="2022-12-31")
    
    # Test 4: Opponent filter
    # Opponent Team ID for Celtics: 1610612738
    await run_team_stats_test(f" - Lakers vs Celtics, {past_season}", 
                              team_identifier=lakers_id, 
                              season=past_season,
                              opponent_team_id=1610612738)

    # Test 5: Invalid team identifier
    await run_team_stats_test(" - Invalid Team", team_identifier="INVALID_TEAM_XYZ")

    # Test 6: Invalid season format
    await run_team_stats_test(" - Lakers, Invalid Season", team_identifier=lakers_id, season="2023")

    # Test 7: Invalid PerMode
    await run_team_stats_test(f" - Lakers, {past_season}, Invalid PerMode", 
                              team_identifier=lakers_id, 
                              season=past_season,
                              per_mode="InvalidPerMode")
    
    # Test 8: Invalid MeasureType
    await run_team_stats_test(f" - Lakers, {past_season}, Invalid MeasureType", 
                              team_identifier=lakers_id, 
                              season=past_season,
                              measure_type="InvalidMeasure")

if __name__ == "__main__":
    asyncio.run(main())
# backend/smoke_tests/test_analyze_logic.py
import sys
import os
import asyncio
import json
import logging

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.analyze import analyze_player_stats_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, LeagueID
from backend.config import settings

async def run_analyze_test(test_name_suffix: str, **kwargs):
    filters_list = [f"{k}={v}" for k, v in kwargs.items() if v is not None]
    filters_str = ", ".join(filters_list)
    test_name = f"Analyze Player Stats ({filters_str}{test_name_suffix})"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json = await asyncio.to_thread(analyze_player_stats_logic, **kwargs)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" not in result_data:
            if "overall_dashboard_stats" in result_data and result_data["overall_dashboard_stats"]:
                logger.info(f"SUCCESS: {test_name} - Fetched analysis stats.")
                stats = result_data["overall_dashboard_stats"]
                logger.info(f"  Player: {stats.get('PLAYER_NAME')}, GP: {stats.get('GP')}, PTS: {stats.get('PTS')}")
            elif "overall_dashboard_stats" in result_data and not result_data["overall_dashboard_stats"]:
                 logger.info(f"SUCCESS (No Data): {test_name} - No overall dashboard stats found (empty dict returned).")
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

    # Test 1: Valid player, current season, default params
    await run_analyze_test(" - LeBron, Current Season Defaults", player_name="LeBron James")

    # Test 2: Valid player, past season, Totals per mode
    await run_analyze_test(f" - Curry, {past_season} Totals", 
                           player_name="Stephen Curry", 
                           season=past_season, 
                           per_mode=PerModeDetailed.totals)

    # Test 3: Valid player, Playoffs season type
    await run_analyze_test(f" - Jokic, {past_season} Playoffs", 
                           player_name="Nikola Jokic", 
                           season=past_season, 
                           season_type=SeasonTypeAllStar.playoffs)
    
    # Test 4: Invalid player name
    await run_analyze_test(" - Invalid Player", player_name="Invalid Player Name XYZ")

    # Test 5: Invalid season format
    await run_analyze_test(" - LeBron, Invalid Season", player_name="LeBron James", season="2023")

    # Test 6: Invalid season_type (AllStar is not supported by this endpoint's validation)
    await run_analyze_test(f" - LeBron, {past_season} AllStar (Expect Error)", 
                           player_name="LeBron James", 
                           season=past_season,
                           season_type=SeasonTypeAllStar.all_star)

    # Test 7: Invalid per_mode
    await run_analyze_test(f" - LeBron, {past_season} Invalid PerMode", 
                           player_name="LeBron James", 
                           season=past_season,
                           per_mode="InvalidMode")

if __name__ == "__main__":
    asyncio.run(main())
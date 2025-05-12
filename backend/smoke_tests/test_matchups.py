# backend/smoke_tests/test_matchups.py
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

from backend.api_tools.matchup_tools import fetch_league_season_matchups_logic, fetch_matchups_rollup_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar
from backend.config import settings

async def run_season_matchups_test(test_name_suffix: str, **kwargs):
    def_player = kwargs.get("def_player_identifier", "N/A")
    off_player = kwargs.get("off_player_identifier", "N/A")
    season = kwargs.get("season", "N/A")
    test_name = f"Season Matchups (Def: {def_player} vs Off: {off_player}, Season: {season}{test_name_suffix})"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json = await asyncio.to_thread(fetch_league_season_matchups_logic, **kwargs)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" not in result_data:
            if "matchups" in result_data and isinstance(result_data["matchups"], list):
                logger.info(f"SUCCESS: {test_name} - Fetched season matchups. Count: {len(result_data['matchups'])}")
                if result_data["matchups"]:
                    logger.info(f"  Sample Matchup Data: {json.dumps(result_data['matchups'][0], indent=2)}")
            elif "matchups" in result_data and not result_data["matchups"]:
                 logger.info(f"SUCCESS (No Data): {test_name} - No specific matchup data found (empty list returned).")
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

async def run_matchups_rollup_test(test_name_suffix: str, **kwargs):
    def_player = kwargs.get("def_player_identifier", "N/A")
    season = kwargs.get("season", "N/A")
    test_name = f"Matchups Rollup (Def: {def_player}, Season: {season}{test_name_suffix})"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json = await asyncio.to_thread(fetch_matchups_rollup_logic, **kwargs)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" not in result_data:
            if "rollup" in result_data and isinstance(result_data["rollup"], list):
                logger.info(f"SUCCESS: {test_name} - Fetched matchups rollup. Count: {len(result_data['rollup'])}")
                if result_data["rollup"]:
                    logger.info(f"  Sample Rollup Data: {json.dumps(result_data['rollup'][0], indent=2)}")
            elif "rollup" in result_data and not result_data["rollup"]:
                 logger.info(f"SUCCESS (No Data): {test_name} - No rollup data found (empty list returned).")
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

    # --- Tests for fetch_league_season_matchups_logic ---
    # Test 1: Valid player names, current season
    await run_season_matchups_test(" - LeBron vs Butler, Current Season", 
                                   def_player_identifier="LeBron James", 
                                   off_player_identifier="Jimmy Butler",
                                   season=current_season)
                                   
    # Test 2: Valid player IDs, past season, Playoffs
    await run_season_matchups_test(f" - PlayerID 203999 vs 201939, {past_season} Playoffs", 
                                   def_player_identifier="203999", # Jokic
                                   off_player_identifier="201939", # Curry
                                   season=past_season,
                                   season_type=SeasonTypeAllStar.playoffs)

    # Test 3: Invalid defensive player name
    await run_season_matchups_test(" - Invalid Def Player", 
                                   def_player_identifier="Invalid Def Player XYZ", 
                                   off_player_identifier="Stephen Curry",
                                   season=past_season)

    # Test 4: Invalid season format
    await run_season_matchups_test(" - Invalid Season", 
                                   def_player_identifier="LeBron James", 
                                   off_player_identifier="Jimmy Butler",
                                   season="2023")

    # --- Tests for fetch_matchups_rollup_logic ---
    # Test 5: Valid player name, current season
    await run_matchups_rollup_test(" - Gobert, Current Season", 
                                   def_player_identifier="Rudy Gobert",
                                   season=current_season)

    # Test 6: Valid player ID, past season, Playoffs
    await run_matchups_rollup_test(f" - PlayerID 201939, {past_season} Playoffs", 
                                   def_player_identifier="201939", # Curry
                                   season=past_season,
                                   season_type=SeasonTypeAllStar.playoffs)

    # Test 7: Invalid player name for rollup
    await run_matchups_rollup_test(" - Invalid Player Rollup", 
                                   def_player_identifier="Invalid Player XYZ",
                                   season=past_season)
    
    # Test 8: Invalid season type for rollup
    await run_matchups_rollup_test(" - Invalid Season Type Rollup", 
                                   def_player_identifier="Rudy Gobert",
                                   season=past_season,
                                   season_type="All-Star Game") # Invalid for this endpoint

if __name__ == "__main__":
    asyncio.run(main())
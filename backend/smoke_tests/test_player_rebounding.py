# backend/smoke_tests/test_player_rebounding.py
import sys
import os
import asyncio
import json
import logging

# Add the project root to sys.path to allow absolute imports like 'from backend...'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from backend.api_tools.player_rebounding import fetch_player_rebounding_stats_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

async def run_rebounding_test(player_name: str, season: str, season_type: str, per_mode: str):
    logger = logging.getLogger(__name__)
    test_name = f"Player Rebounding Stats ({player_name}, {season}, {season_type}, {per_mode})"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json = await asyncio.to_thread(
        fetch_player_rebounding_stats_logic,
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=4)) # Uncomment for full output inspection
        
        if "error" not in result_data:
            if result_data.get("overall"):
                logger.info(f"SUCCESS: {test_name} - Overall G: {result_data['overall'].get('G')}, REB: {result_data['overall'].get('REB')}")
            elif result_data.get("overall") == {} and not result_data.get("by_shot_type"): # Empty data case
                 logger.info(f"SUCCESS: {test_name} - No rebounding data found (empty stats returned as expected).")
            else:
                logger.warning(f"WARNING: {test_name} - 'overall' rebounding data missing or not as expected.")
                print(json.dumps(result_data, indent=4))

        elif "error" in result_data:
            logger.error(f"ERROR for {test_name}: {result_data['error']}")
        else:
            logger.warning(f"WARNING: Unexpected response structure for {test_name}.")
            
    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON response for {test_name}: {result_json}")
    logger.info("-" * 70)

async def main():
    # Test 1: Valid player and parameters
    await run_rebounding_test(
        player_name="Nikola Jokic",
        season="2023-24",
        season_type=SeasonTypeAllStar.regular,
        per_mode=PerModeSimple.per_game
    )

    # Test 2: Player with potentially less data or different season
    await run_rebounding_test(
        player_name="Stephen Curry",
        season="2022-23",
        season_type=SeasonTypeAllStar.playoffs,
        per_mode=PerModeSimple.totals
    )
    
    # Test 3: Player who might not have data for a specific old season
    await run_rebounding_test(
        player_name="Michael Jordan", # Will likely result in PlayerNotFoundError or no data for a modern season
        season="2023-24", 
        season_type=SeasonTypeAllStar.regular,
        per_mode=PerModeSimple.per_game
    )

    # Test 4: Invalid season format
    await run_rebounding_test(
        player_name="LeBron James",
        season="2023", # Invalid format
        season_type=SeasonTypeAllStar.regular,
        per_mode=PerModeSimple.per_game
    )

    # Test 5: Invalid PerMode
    await run_rebounding_test(
        player_name="LeBron James",
        season="2023-24",
        season_type=SeasonTypeAllStar.regular,
        per_mode="PerMinute" # Invalid for PerModeSimple used by this endpoint
    )

if __name__ == "__main__":
    asyncio.run(main())
# backend/smoke_tests/test_odds_tools.py
import sys
import os
import asyncio
import json
import logging
import time

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.odds_tools import fetch_odds_data_logic
# from backend.config import settings # Not directly needed by fetch_odds_data_logic signature

async def run_odds_test(test_name_suffix: str, bypass_cache: bool):
    test_name = f"Odds Data (bypass_cache={bypass_cache}{test_name_suffix})"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json = await asyncio.to_thread(fetch_odds_data_logic, bypass_cache=bypass_cache)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" not in result_data:
            if "games" in result_data and isinstance(result_data["games"], list):
                logger.info(f"SUCCESS: {test_name} - Fetched odds data. Games Found: {len(result_data['games'])}")
                if result_data["games"]:
                    sample_game = result_data["games"][0]
                    logger.info(f"  Sample Game ID: {sample_game.get('gameId')}, Markets: {len(sample_game.get('markets', []))}")
                    if sample_game.get('markets'):
                        logger.info(f"    Sample Market: {sample_game['markets'][0].get('name')}")
            elif "games" in result_data and not result_data["games"]:
                 logger.info(f"SUCCESS (No Data): {test_name} - No games with odds data found (empty list returned). This is normal if no games today or no odds available.")
            else:
                logger.warning(f"WARNING: {test_name} - Data structure not as expected ('games' key missing or not a list).")
                print(json.dumps(result_data, indent=2))
        elif "error" in result_data:
            logger.error(f"ERROR for {test_name}: {result_data['error']}")
        else:
            logger.warning(f"WARNING: Unexpected response structure for {test_name}.")
            
    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON response for {test_name}: {result_json}")
    logger.info("-" * 70)

async def main():
    # Test 1: Fetch with cache (first call will likely be a miss)
    await run_odds_test(" - First call, cache miss expected", bypass_cache=False)
    
    # Test 2: Fetch with cache again (should hit cache if within the hour)
    logger.info("Waiting for 5 seconds before next cached call (should hit hourly cache)...")
    await asyncio.sleep(5)
    await run_odds_test(" - Second call, cache hit expected", bypass_cache=False)

    # Test 3: Fetch bypassing cache
    await run_odds_test(" - Bypass cache", bypass_cache=True)

if __name__ == "__main__":
    asyncio.run(main())
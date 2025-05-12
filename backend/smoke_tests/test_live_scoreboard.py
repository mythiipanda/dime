# backend/smoke_tests/test_live_scoreboard.py
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

from backend.api_tools.live_game_tools import fetch_league_scoreboard_logic
# from backend.config import settings # Not directly needed unless settings influence the call

async def run_live_scoreboard_test(bypass_cache: bool):
    test_name = f"Live Scoreboard (bypass_cache={bypass_cache})"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json = await asyncio.to_thread(fetch_league_scoreboard_logic, bypass_cache=bypass_cache)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" not in result_data:
            if "games" in result_data and isinstance(result_data["games"], list):
                logger.info(f"SUCCESS: {test_name} - Fetched live scoreboard. Game Date: {result_data.get('gameDate')}, Games Found: {len(result_data['games'])}")
                if result_data["games"]:
                    sample_game = result_data["games"][0]
                    logger.info(f"  Sample Game: {sample_game.get('homeTeam',{}).get('teamTricode')} vs {sample_game.get('awayTeam',{}).get('teamTricode')}, Status: {sample_game.get('gameStatusText')}")
            else:
                logger.warning(f"WARNING: {test_name} - 'games' key missing or not a list.")
                print(json.dumps(result_data, indent=2))
        elif "error" in result_data:
            logger.error(f"ERROR for {test_name}: {result_data['error']}")
        else:
            logger.warning(f"WARNING: Unexpected response structure for {test_name}.")
            
    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON response for {test_name}: {result_json}")
    logger.info("-" * 70)

async def main():
    # Test 1: Fetch with cache (first call will likely be a miss, subsequent might hit if within TTL)
    await run_live_scoreboard_test(bypass_cache=False)
    
    # Wait for a short period, less than cache TTL to test if cache hits (though timestamp logic is primary)
    # The cache timestamp logic in live_game_tools.py uses CACHE_TTL_SECONDS (10s) for bucketing.
    logger.info("Waiting for 5 seconds before next cached call...")
    await asyncio.sleep(5)
    await run_live_scoreboard_test(bypass_cache=False) # Should ideally hit cache if within same 10s bucket

    logger.info("Waiting for 12 seconds (past 10s TTL bucket) before next cached call...")
    await asyncio.sleep(12)
    await run_live_scoreboard_test(bypass_cache=False) # Should be a new bucket, likely a cache miss for the API call

    # Test 2: Fetch bypassing cache
    await run_live_scoreboard_test(bypass_cache=True)


if __name__ == "__main__":
    asyncio.run(main())
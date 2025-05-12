# backend/smoke_tests/test_game_playbyplay.py
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

from backend.api_tools.game_playbyplay import fetch_playbyplay_logic
# from backend.config import settings # Not directly needed by logic function signature

# Example Game IDs
# Recent game (might be live or just concluded, good for testing live fallback)
RECENT_GAME_ID = "0042300225" # DAL vs OKC, 2024-05-11 (Playoffs)
# Older, known completed game (good for testing historical V3)
HISTORICAL_GAME_ID = "0022300001" # DEN vs LAL, 2023-10-24 (Opening Night)

async def run_pbp_test(test_name: str, game_id: str, start_period: int = 0, end_period: int = 0):
    logger.info(f"--- Testing {test_name} for Game ID: {game_id} (Periods: {start_period}-{end_period}) ---")
    
    result_json = await asyncio.to_thread(fetch_playbyplay_logic, game_id, start_period, end_period)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" not in result_data:
            if "periods" in result_data and isinstance(result_data["periods"], list):
                logger.info(f"SUCCESS: {test_name} - Fetched PBP. Source: {result_data.get('source')}. Number of periods returned: {len(result_data['periods'])}")
                if result_data["periods"]:
                    logger.info(f"  Plays in first returned period: {len(result_data['periods'][0].get('plays', []))}")
                    if result_data['periods'][0].get('plays'):
                        logger.info(f"  Sample play description: {result_data['periods'][0]['plays'][0].get('description')}")
                else:
                    logger.info(f"  No period data returned, but no error. This might be valid for certain period filters or if game has no PBP.")
            else:
                logger.warning(f"SUCCESS but 'periods' key missing or not a list for {test_name}. Check output.")
                print(json.dumps(result_data, indent=2))
        elif "error" in result_data:
            logger.error(f"ERROR for {test_name}: {result_data['error']}")
        else:
            logger.warning(f"WARNING: Unexpected response structure for {test_name}.")
            
    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON response for {test_name}: {result_json}")
    logger.info("-" * 70)

async def main():
    # Test with a recent game (will attempt live, then fallback to historical V3 if not live)
    await run_pbp_test("Recent Game PBP (Live/Historical Fallback)", RECENT_GAME_ID)
    
    # Test with an older game (should directly use historical V3)
    await run_pbp_test("Historical Game PBP (V3)", HISTORICAL_GAME_ID)

    # Test historical with period filter (e.g., Q1 only)
    await run_pbp_test("Historical Game PBP (Q1 only)", HISTORICAL_GAME_ID, start_period=1, end_period=1)
    
    # Test historical with a range of periods (e.g., Q2-Q3)
    await run_pbp_test("Historical Game PBP (Q2-Q3)", HISTORICAL_GAME_ID, start_period=2, end_period=3)

    # Test with an invalid Game ID format (handled by validate_game_id_format)
    await run_pbp_test("Invalid Game ID Format PBP", "123")

    # Test with a non-existent Game ID (should result in an error from API or empty data)
    await run_pbp_test("Non-existent Game ID PBP", "0000000000")


if __name__ == "__main__":
    asyncio.run(main())
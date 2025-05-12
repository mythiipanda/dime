# backend/smoke_tests/test_game_boxscores.py
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

from backend.api_tools.game_boxscores import (
    fetch_boxscore_traditional_logic,
    fetch_boxscore_advanced_logic,
    fetch_boxscore_four_factors_logic,
    fetch_boxscore_usage_logic,
    fetch_boxscore_defensive_logic
)
# from backend.config import settings # Not directly needed by logic function signatures

# A recent, known valid game_id for testing
# Example: Game 1 of 2023 Finals: MIA @ DEN, 2023-06-01, GameID: 0042200401
# Example: Regular season BOS vs LAL 2024-02-01, GameID: 0022300704
# Example: Recent game: OKC vs DAL 2024-05-11, GameID: 0042300225 (Playoffs)
VALID_GAME_ID = "0042300225" # DAL vs OKC, 2024-05-11 (Playoffs)
# Fallback if the above game is too old or data is sparse
FALLBACK_GAME_ID = "0022300001" # DEN vs LAL, 2023-10-24 (Opening Night)

async def run_boxscore_test(test_name: str, logic_function: callable, game_id: str, **kwargs):
    logger.info(f"--- Testing {test_name} for Game ID: {game_id} ---")
    
    # Add game_id to kwargs for the logic function
    all_kwargs = {"game_id": game_id, **kwargs}
    result_json = await asyncio.to_thread(logic_function, **all_kwargs)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" not in result_data:
            # Check for common dataset keys based on function name
            if "traditional" in test_name.lower() and ("players" in result_data and "teams" in result_data and "starters_bench" in result_data):
                logger.info(f"SUCCESS: {test_name} - Fetched. Players: {len(result_data['players'])}, Teams: {len(result_data['teams'])}")
            elif ("advanced" in test_name.lower() or "four_factors" in test_name.lower()) and ("player_stats" in result_data and "team_stats" in result_data):
                logger.info(f"SUCCESS: {test_name} - Fetched. PlayerStats: {len(result_data['player_stats'])}, TeamStats: {len(result_data['team_stats'])}")
            elif "usage" in test_name.lower() and ("player_usage_stats" in result_data and "team_usage_stats" in result_data):
                logger.info(f"SUCCESS: {test_name} - Fetched. PlayerUsage: {len(result_data['player_usage_stats'])}, TeamUsage: {len(result_data['team_usage_stats'])}")
            elif "defensive" in test_name.lower() and ("player_defensive_stats" in result_data and "team_defensive_stats" in result_data):
                 logger.info(f"SUCCESS: {test_name} - Fetched. PlayerDefensive: {len(result_data['player_defensive_stats'])}, TeamDefensive: {len(result_data['team_defensive_stats'])}")
            else:
                logger.warning(f"SUCCESS but data structure keys not fully verified for {test_name}. Check output.")
                print(json.dumps(result_data, indent=2))

        elif "error" in result_data:
            logger.error(f"ERROR for {test_name}: {result_data['error']}")
        else:
            logger.warning(f"WARNING: Unexpected response structure for {test_name}.")
            
    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON response for {test_name}: {result_json}")
    logger.info("-" * 70)

async def main():
    game_id_to_test = VALID_GAME_ID
    
    logger.info(f"Using Game ID: {game_id_to_test} for box score tests.")
    # If you suspect VALID_GAME_ID might not have data for all box types,
    # you can uncomment the line below to use a known older game as a fallback for some tests.
    # game_id_to_test = FALLBACK_GAME_ID 

    await run_boxscore_test("Traditional Box Score", fetch_boxscore_traditional_logic, game_id_to_test)
    await run_boxscore_test("Advanced Box Score", fetch_boxscore_advanced_logic, game_id_to_test)
    await run_boxscore_test("Four Factors Box Score", fetch_boxscore_four_factors_logic, game_id_to_test)
    await run_boxscore_test("Usage Box Score", fetch_boxscore_usage_logic, game_id_to_test)
    await run_boxscore_test("Defensive Box Score", fetch_boxscore_defensive_logic, game_id_to_test)

    # Example with specific period filters for traditional (optional to test)
    # await run_boxscore_test(
    #     "Traditional Box Score (Q1 only)", 
    #     fetch_boxscore_traditional_logic, 
    #     game_id_to_test,
    #     start_period=1,
    #     end_period=1
    # )

if __name__ == "__main__":
    asyncio.run(main())
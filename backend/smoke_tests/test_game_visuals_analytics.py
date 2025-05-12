# backend/smoke_tests/test_game_visuals_analytics.py
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

from backend.api_tools.game_visuals_analytics import fetch_shotchart_logic, fetch_win_probability_logic
# from nba_api.stats.library.parameters import RunType # Not strictly needed for test if using strings

# Constants for testing
GAME_ID_TEST_RECENT = "0022300001" # A known game ID from 2023-24 season start
GAME_ID_TEST_PLAYOFF = "0042300225" # A known playoff game ID

async def run_test(test_name: str, logic_function: callable, **kwargs):
    logger.info(f"--- Testing {test_name} ---")
    logger.info(f"Parameters: {kwargs}")
    
    result_json = await asyncio.to_thread(logic_function, **kwargs)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" in result_data:
            logger.error(f"ERROR for {test_name}: {result_data['error']}")
        else:
            logger.info(f"SUCCESS: {test_name} - Fetched data successfully.")
            if "teams" in result_data and result_data["teams"] and "shots" in result_data["teams"][0]: # Check if teams list is not empty
                logger.info(f"  Shot Chart: Found {len(result_data['teams'])} teams, first team has {len(result_data['teams'][0]['shots'])} shots.")
            elif "teams" in result_data and not result_data["teams"]:
                 logger.info(f"  Shot Chart: Found {len(result_data['teams'])} teams (empty list).")
            elif "win_probability" in result_data: # Win probability specific
                logger.info(f"  Win Probability: Found {len(result_data['win_probability'])} PBP entries.")
                if result_data['win_probability']:
                    logger.info(f"  First WP entry HOME_PCT: {result_data['win_probability'][0].get('HOME_PCT')}")
            else:
                logger.info("  Response data structure check passed (no specific content check implemented here).")

    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON response for {test_name}: {result_json}")
    logger.info("-" * 70)

async def main():
    # Test fetch_shotchart_logic
    await run_test(
        "Game Shot Chart (Recent Game)",
        fetch_shotchart_logic,
        game_id=GAME_ID_TEST_RECENT
    )
    await run_test(
        "Game Shot Chart (Playoff Game)",
        fetch_shotchart_logic,
        game_id=GAME_ID_TEST_PLAYOFF
    )

    # Test fetch_win_probability_logic
    run_types_to_test = ["each play", "each second"] # "each poss" can also be tested
    for rt in run_types_to_test:
        await run_test(
            f"Win Probability (Recent Game, RunType: {rt})",
            fetch_win_probability_logic,
            game_id=GAME_ID_TEST_RECENT,
            run_type=rt
        )
        await run_test(
            f"Win Probability (Playoff Game, RunType: {rt})",
            fetch_win_probability_logic,
            game_id=GAME_ID_TEST_PLAYOFF,
            run_type=rt
        )
    
    # Test with an invalid RunType for win probability
    await run_test(
        "Win Probability (Invalid RunType)",
        fetch_win_probability_logic,
        game_id=GAME_ID_TEST_RECENT,
        run_type="invalid_type"
    )

if __name__ == "__main__":
    asyncio.run(main())
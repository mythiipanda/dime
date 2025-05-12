# backend/smoke_tests/test_player_shooting_tracking.py
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

from backend.api_tools.player_shooting_tracking import fetch_player_shots_tracking_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

async def run_shooting_tracking_test(player_name: str, season: str, season_type: str, per_mode: str, test_name_suffix: str = ""):
    logger = logging.getLogger(__name__)
    test_name = f"Player Shooting Tracking ({player_name}, {season}, {season_type}, {per_mode}{test_name_suffix})"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json = await asyncio.to_thread(
        fetch_player_shots_tracking_logic,
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode
        # Add other optional params like opponent_team_id, date_from, date_to if needed for specific tests
    )
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=4)) # Uncomment for full output

        if "error" not in result_data:
            if result_data.get("general_shooting"):
                logger.info(f"SUCCESS: {test_name} - Found {len(result_data['general_shooting'])} general shooting entries.")
                # Check if per_mode is reflected (e.g. GP might be different for Totals vs PerGame if player played 1 game)
                # For a quick check, just ensure data is returned. Detailed validation is for unit tests.
                if result_data['general_shooting']:
                    logger.info(f"  Sample General Shooting: {result_data['general_shooting'][0].get('SHOT_TYPE')}, FGM: {result_data['general_shooting'][0].get('FGM')}")
            elif not any(result_data.get(key) for key in ["general_shooting", "by_shot_clock", "by_dribble_count", "by_touch_time", "by_defender_distance", "by_defender_distance_10ft_plus"]):
                 logger.info(f"SUCCESS: {test_name} - No shooting data found (empty stats returned as expected).")
            else:
                logger.warning(f"WARNING: {test_name} - Data structure not as expected or partially empty.")
                print(json.dumps(result_data, indent=4))
        elif "error" in result_data:
            logger.error(f"ERROR for {test_name}: {result_data['error']}")
        else:
            logger.warning(f"WARNING: Unexpected response structure for {test_name}.")
            
    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON response for {test_name}: {result_json}")
    logger.info("-" * 70)

async def main():
    # Test 1: Default PerMode (Totals)
    await run_shooting_tracking_test(
        player_name="Kevin Durant",
        season="2023-24",
        season_type=SeasonTypeAllStar.regular,
        per_mode=PerModeSimple.totals # Explicitly testing the new default
    )

    # Test 2: PerGame PerMode
    await run_shooting_tracking_test(
        player_name="Kevin Durant",
        season="2023-24",
        season_type=SeasonTypeAllStar.regular,
        per_mode=PerModeSimple.per_game
    )
    
    # Test 3: Player with potentially less data
    await run_shooting_tracking_test(
        player_name="Bol Bol",
        season="2023-24", 
        season_type=SeasonTypeAllStar.regular,
        per_mode=PerModeSimple.per_game
    )

    # Test 4: Invalid PerMode (should be caught by validation)
    await run_shooting_tracking_test(
        player_name="LeBron James",
        season="2023-24",
        season_type=SeasonTypeAllStar.regular,
        per_mode="PerMinute", # Invalid for PerModeSimple
        test_name_suffix=" - Invalid PerMode"
    )

if __name__ == "__main__":
    asyncio.run(main())
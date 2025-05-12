import asyncio
import json
import logging
import os
import sys

# Ensure the project root is in the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.api_tools.player_passing import fetch_player_passing_stats_logic
from backend.config import settings
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    logger.info("--- Testing Player Passing Stats ---")

    test_cases = [
        {
            "player_name": "Nikola Jokic", "season": "2023-24", 
            "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game,
            "description": "Nikola Jokic, 2023-24 Regular Season, PerGame"
        },
        {
            "player_name": "Trae Young", "season": "2022-23", 
            "season_type": SeasonTypeAllStar.playoffs, "per_mode": PerModeSimple.totals,
            "description": "Trae Young, 2022-23 Playoffs, Totals"
        },
        {
            "player_name": "NonExistent PlayerXYZ", "season": "2023-24", 
            "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game,
            "description": "NonExistent Player"
        },
        {
            "player_name": "LeBron James", "season": "2023", # Invalid season format
            "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game,
            "description": "Invalid Season"
        },
    ]

    for case in test_cases:
        logger.info(f"--- Testing Case: {case['description']} ---")
        try:
            result_json_str = await asyncio.to_thread(
                fetch_player_passing_stats_logic,
                player_name=case["player_name"],
                season=case["season"],
                season_type=case["season_type"],
                per_mode=case["per_mode"]
            )
            data = json.loads(result_json_str)

            if "error" in data:
                logger.error(f"ERROR for {case['description']}: {data['error']}")
            else:
                logger.info(f"SUCCESS for {case['description']}: Fetched passing stats.")
                # logger.debug(json.dumps(data, indent=2)) # Optional: print full data
                if "passes_made" in data and "passes_received" in data:
                    logger.info(f"  Passes Made count: {len(data['passes_made'])}, Passes Received count: {len(data['passes_received'])}")
                    if data['passes_made']:
                        logger.info(f"  Sample Pass Made To: {data['passes_made'][0].get('PASS_TO')}")
                else:
                    logger.warning("Response structure missing 'passes_made' or 'passes_received'.")
        except Exception as e:
            logger.error(f"Unhandled exception for {case['description']}: {e}", exc_info=True)
        logger.info("----------------------------------------------------------------------")

if __name__ == "__main__":
    asyncio.run(main())
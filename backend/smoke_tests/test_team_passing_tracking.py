import asyncio
import json
import logging
import os
import sys

# Ensure the project root is in the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.api_tools.team_passing_tracking import fetch_team_passing_stats_logic
from backend.config import settings
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    logger.info("--- Testing Team Passing Stats ---")

    test_cases = [
        {
            "team_identifier": "LAL", "season": "2023-24",
            "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game,
            "description": "LAL, 2023-24 Regular Season, PerGame"
        },
        {
            "team_identifier": "BOS", "season": "2022-23",
            "season_type": SeasonTypeAllStar.playoffs, "per_mode": PerModeSimple.totals,
            "description": "BOS, 2022-23 Playoffs, Totals"
        },
        {
            "team_identifier": "NonExistent TeamXYZ", "season": "2023-24",
            "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game,
            "description": "NonExistent Team"
        },
        {
            "team_identifier": "LAL", "season": "2023", # Invalid season format
            "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game,
            "description": "Invalid Season"
        },
        {
            "team_identifier": "LAL", "season": "2023-24",
            "season_type": "InvalidType", "per_mode": PerModeSimple.per_game,
            "description": "Invalid Season Type"
        },
        {
            "team_identifier": "LAL", "season": "2023-24",
            "season_type": SeasonTypeAllStar.regular, "per_mode": "InvalidPerMode",
            "description": "Invalid PerMode"
        },
    ]

    for case in test_cases:
        logger.info(f"--- Testing Case: {case['description']} ---")
        try:
            result_json_str = await asyncio.to_thread(
                fetch_team_passing_stats_logic,
                team_identifier=case["team_identifier"],
                season=case["season"],
                season_type=case["season_type"],
                per_mode=case["per_mode"]
            )
            data = json.loads(result_json_str)

            if "error" in data:
                logger.error(f"ERROR for {case['description']}: {data['error']}")
            else:
                logger.info(f"SUCCESS for {case['description']}: Fetched team passing stats.")
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
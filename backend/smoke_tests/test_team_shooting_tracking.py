import asyncio
import json
import logging
import os
import sys

# Ensure the project root is in the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.api_tools.team_shooting_tracking import fetch_team_shooting_stats_logic
from backend.config import settings
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    logger.info("--- Testing Team Shooting Stats ---")

    test_cases = [
        {
            "team_identifier": "LAL", "season": "2023-24",
            "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game,
            "opponent_team_id": 0, "date_from": None, "date_to": None,
            "description": "LAL, 2023-24 Regular Season, PerGame"
        },
        {
            "team_identifier": "BOS", "season": "2022-23",
            "season_type": SeasonTypeAllStar.playoffs, "per_mode": PerModeSimple.totals,
            "opponent_team_id": 0, "date_from": None, "date_to": None,
            "description": "BOS, 2022-23 Playoffs, Totals"
        },
        {
            "team_identifier": "NonExistent TeamXYZ", "season": "2023-24",
            "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game,
            "opponent_team_id": 0, "date_from": None, "date_to": None,
            "description": "NonExistent Team"
        },
        {
            "team_identifier": "LAL", "season": "2023", # Invalid season format
            "season_type": SeasonTypeAllStar.regular, "per_mode": PerModeSimple.per_game,
            "opponent_team_id": 0, "date_from": None, "date_to": None,
            "description": "Invalid Season"
        },
        {
            "team_identifier": "LAL", "season": "2023-24",
            "season_type": "InvalidType", "per_mode": PerModeSimple.per_game,
            "opponent_team_id": 0, "date_from": None, "date_to": None,
            "description": "Invalid Season Type"
        },
        {
            "team_identifier": "LAL", "season": "2023-24",
            "season_type": SeasonTypeAllStar.regular, "per_mode": "InvalidPerMode",
            "opponent_team_id": 0, "date_from": None, "date_to": None,
            "description": "Invalid PerMode"
        },
    ]

    for case in test_cases:
        logger.info(f"--- Testing Case: {case['description']} ---")
        try:
            result_json_str = await asyncio.to_thread(
                fetch_team_shooting_stats_logic,
                team_identifier=case["team_identifier"],
                season=case["season"],
                season_type=case["season_type"],
                per_mode=case["per_mode"],
                opponent_team_id=case["opponent_team_id"],
                date_from=case["date_from"],
                date_to=case["date_to"]
            )
            data = json.loads(result_json_str)

            if "error" in data:
                logger.error(f"ERROR for {case['description']}: {data['error']}")
            else:
                logger.info(f"SUCCESS for {case['description']}: Fetched team shooting stats.")
                if "overall_shooting" in data:
                    logger.info(f"  Overall Shooting keys: {list(data['overall_shooting'].keys()) if data['overall_shooting'] else 'None'}")
                if "general_shooting_splits" in data:
                    logger.info(f"  General Shooting Splits count: {len(data['general_shooting_splits'])}")
                if "by_shot_clock" in data:
                    logger.info(f"  By Shot Clock count: {len(data['by_shot_clock'])}")
                if "by_dribble" in data:
                    logger.info(f"  By Dribble count: {len(data['by_dribble'])}")
                if "by_defender_distance" in data:
                    logger.info(f"  By Defender Distance count: {len(data['by_defender_distance'])}")
                if "by_touch_time" in data:
                    logger.info(f"  By Touch Time count: {len(data['by_touch_time'])}")
        except Exception as e:
            logger.error(f"Unhandled exception for {case['description']}: {e}", exc_info=True)
        logger.info("----------------------------------------------------------------------")

if __name__ == "__main__":
    asyncio.run(main()) 
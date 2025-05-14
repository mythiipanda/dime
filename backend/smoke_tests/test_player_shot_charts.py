import asyncio
import json
import logging
import os
import sys
import pytest # Import pytest for the marker

# Ensure the project root is in the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.api_tools.player_shot_charts import fetch_player_shotchart_logic
from backend.config import settings # To get CURRENT_NBA_SEASON if needed
from nba_api.stats.library.parameters import SeasonTypeAllStar

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@pytest.mark.asyncio # Add the pytest-asyncio marker
async def test_shot_charts():
    logger.info("--- Testing Player Shot Charts ---")
    
    test_cases = [
        {"player_name": "Stephen Curry", "season": "2022-23", "season_type": SeasonTypeAllStar.regular, "description": "Stephen Curry 2022-23 Regular Season"},
        {"player_name": "LeBron James", "season": settings.CURRENT_NBA_SEASON, "season_type": SeasonTypeAllStar.regular, "description": f"LeBron James {settings.CURRENT_NBA_SEASON} Regular Season"},
        {"player_name": "NonExistentPlayerXZY", "season": "2022-23", "season_type": SeasonTypeAllStar.regular, "description": "Non-existent player"},
        {"player_name": "Stephen Curry", "season": "2022-23", "season_type": "InvalidType", "description": "Invalid Season Type"},
    ]

    for case in test_cases:
        logger.info(f"--- Testing Case: {case['description']} ---")
        try:
            result_json_str = await asyncio.to_thread(
                fetch_player_shotchart_logic,
                player_name=case["player_name"],
                season=case["season"],
                season_type=case["season_type"]
            )
            data = json.loads(result_json_str)
            
            if "error" in data:
                logger.error(f"ERROR for {case['description']}: {data['error']}")
            else:
                logger.info(f"SUCCESS for {case['description']}: Shot chart data processed.")
                # logger.debug(json.dumps(data, indent=2)) # Optionally print full data
                
                # Basic checks
                assert "player_name" in data
                assert "overall_stats" in data
                assert "zone_breakdown" in data
                assert "shot_data_summary" in data
                assert "league_averages" in data
                if not data.get("message") == "No shot data found for the specified criteria.":
                    assert "visualization_path" in data or "visualization_error" in data, "Missing visualization_path or visualization_error when data is present"
                    if data.get("visualization_path"):
                        logger.info(f"Visualization path: {data['visualization_path']}")
                    if data.get("visualization_error"):
                        logger.warning(f"Visualization error: {data['visualization_error']}")
                else:
                    logger.info(f"Message: {data['message']}")

        except Exception as e:
            logger.error(f"Unhandled exception for {case['description']}: {e}", exc_info=True)
            assert False, f"Unhandled exception for {case['description']}: {e}" # Fail test on unhandled exception
        logger.info("----------------------------------------------------------------------")
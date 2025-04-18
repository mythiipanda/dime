import logging
import json
from typing import Dict, Any
from nba_api.stats.library.parameters import SeasonTypeAllStar
from backend.config import CURRENT_SEASON
from backend.api_tools.league_tools import fetch_league_leaders_logic

logger = logging.getLogger(__name__)

def fetch_top_performers_logic(
    category: str = "PTS",
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    top_n: int = 5
) -> str:
    """
    Fetch top performing players for a stat category in a season.
    Returns JSON string with top performers.
    """
    logger.info(
        f"Fetching top {top_n} performers for {category} in season {season}, type {season_type}"
    )
    try:
        full_json = fetch_league_leaders_logic(season, category, season_type)
        data = json.loads(full_json)
        leaders = data.get("leaders", [])
        top = leaders[:top_n]
        result = {
            "season": data.get("season", season),
            "stat_category": data.get("stat_category", category),
            "season_type": data.get("season_type", season_type),
            "top_performers": top
        }
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error fetching top performers: {e}", exc_info=True)
        return json.dumps({"error": str(e)})

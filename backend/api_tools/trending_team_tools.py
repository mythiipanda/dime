import logging
import json
from typing import Dict, Any, List
from nba_api.stats.library.parameters import SeasonTypeAllStar
from backend.api_tools.league_tools import fetch_league_standings_logic

logger = logging.getLogger(__name__)

def fetch_top_teams_logic(
    season: str = "",
    season_type: str = SeasonTypeAllStar.regular,
    top_n: int = 5
) -> str:
    """
    Fetch top performing teams by win percentage for a given season.
    Returns JSON string with top teams.
    """
    if not season:
        # load default
        from backend.config import CURRENT_SEASON
        season = CURRENT_SEASON
    try:
        standings_json = fetch_league_standings_logic(season, season_type)
        data = json.loads(standings_json)
        standings = data.get("standings", [])
        # Sort by WinPct descending
        try:
            standings_sorted = sorted(standings, key=lambda x: float(x.get("WinPct", 0)), reverse=True)
        except Exception:
            standings_sorted = standings
        top = standings_sorted[:top_n]
        result = {
            "season": season,
            "season_type": season_type,
            "top_teams": top
        }
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error fetching top teams: {e}", exc_info=True)
        return json.dumps({"error": str(e)})

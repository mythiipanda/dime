from typing import Dict, Any, List
import json
import logging
from nba_api.stats.endpoints import playerdashboardbyyearoveryear
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, LeagueID
from backend.config import CURRENT_SEASON

from .player_tools import _find_player_id
from .utils import handle_api_error

logger = logging.getLogger(__name__)

def analyze_player_stats_logic(player_name: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerModeDetailed.per_game, league_id: str = LeagueID.nba) -> str:
    """
    Fetches player overall dashboard stats for a given season/type.
    NOTE: Despite the name, this currently returns overall stats, not year-over-year analysis.
    The PlayerDashboardByYearOverYear endpoint *does* contain YOY data that could be processed further.
    
    Args:
        player_name (str): The name of the player to analyze.
        season (str): The season to analyze.
        season_type (str): The type of season to analyze (Regular Season, Playoffs, etc.).
        per_mode (str): Stat mode ('PerGame', 'Totals', etc.).
        league_id (str): League ID.
        
    Returns:
        str: JSON string containing the overall player dashboard stats for the specified period.
    """
    logger.info(f"Executing analyze_player_stats_logic for: {player_name}, Season: {season}, Type: {season_type}, Mode: {per_mode}, League: {league_id}")
    try:
        # Find the player
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            error_msg = f"Player '{player_name}' not found"
            logger.error(error_msg)
            return handle_api_error("InvalidPlayer", error_msg)

        # Get player's year-over-year stats
        player_stats = playerdashboardbyyear.PlayerDashboardByYearOverYear(
            player_id=player_id,
            season=season,
            season_type_playoffs=season_type,
            per_mode_detailed=per_mode,
            league_id_nullable=league_id,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Get the normalized stats
        stats_dict = player_stats.get_normalized_dict()
        if not stats_dict or "OverallPlayerDashboard" not in stats_dict:
            error_msg = f"No stats found for player '{player_actual_name}'"
            logger.error(error_msg)
            return handle_api_error("Unknown", error_msg)

        # Extract career stats
        career_stats = stats_dict["OverallPlayerDashboard"]
        
        # Format the response
        response = {
            "player_name": player_actual_name,
            "player_id": player_id,
            "season": season,
            "season_type": season_type,
            "per_mode": per_mode,
            "league_id": league_id,
            "overall_dashboard_stats": career_stats
        }
        
        return json.dumps(response)
        
    except TimeoutError as e:
        return handle_api_error("Timeout", f"Timeout while fetching stats for player '{player_name}'")
    except Exception as e:
        error_msg = f"Error analyzing stats for player '{player_name}': {str(e)}"
        logger.error(error_msg)
        return handle_api_error("Unknown", error_msg) 
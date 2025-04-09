from typing import Dict, Any, List
import json
import logging
from nba_api.stats.endpoints import playerdashboardbyyearoveryear
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed

from .player_tools import _find_player_id
from .utils import handle_api_error

logger = logging.getLogger(__name__)

def analyze_player_stats_logic(player_name: str, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Analyze a player's statistics over their career.
    
    Args:
        player_name (str): The name of the player to analyze
        season_type (str): The type of season to analyze (Regular Season, Playoffs, etc.)
        
    Returns:
        str: JSON string containing the analysis results
    """
    try:
        # Find the player
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            error_msg = f"Player '{player_name}' not found"
            logger.error(error_msg)
            return handle_api_error("InvalidPlayer", error_msg)

        # Get player's year-over-year stats
        player_stats = playerdashboardbyyearoveryear.PlayerDashboardByYearOverYear(
            player_id=player_id,
            per_mode_detailed=PerModeDetailed.per_game,
            season_type_all_star=season_type
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
            "season_type": season_type,
            "career_stats": career_stats
        }
        
        return json.dumps(response)
        
    except TimeoutError as e:
        return handle_api_error("Timeout", f"Timeout while fetching stats for player '{player_name}'")
    except Exception as e:
        error_msg = f"Error analyzing stats for player '{player_name}': {str(e)}"
        logger.error(error_msg)
        return handle_api_error("Unknown", error_msg) 
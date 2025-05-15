import logging
from typing import Optional
from agno.tools import tool
from nba_api.stats.library.parameters import SeasonTypeAllStar # Assuming this might be used for defaults
from backend.config import settings

# Import specific logic functions for misc tools
from backend.api_tools.matchup_tools import fetch_league_season_matchups_logic, fetch_matchups_rollup_logic
from backend.api_tools.odds_tools import fetch_odds_data_logic

logger = logging.getLogger(__name__)

@tool
def get_season_matchups(def_player_id: str, off_player_id: str, season: str = settings.CURRENT_NBA_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches head-to-head matchup statistics between a defensive player and an offensive player.
    Args: def_player_id, off_player_id, season, season_type.
    Returns: JSON string with matchup statistics.
    """
    logger.debug(f"Tool 'get_season_matchups' called for Def: {def_player_id}, Off: {off_player_id}, Season: {season}")
    return fetch_league_season_matchups_logic(def_player_id, off_player_id, season, season_type)

@tool
def get_matchups_rollup(def_player_id: str, season: str = settings.CURRENT_NBA_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches a rollup of matchup statistics for a defensive player against all opponents.
    Args: def_player_id, season, season_type.
    Returns: JSON string with matchup rollup statistics.
    """
    logger.debug(f"Tool 'get_matchups_rollup' called for Def: {def_player_id}, Season: {season}")
    return fetch_matchups_rollup_logic(def_player_id, season, season_type)

@tool
def get_live_odds() -> str:
    """
    Fetches live betting odds for today's NBA games.
    Returns: JSON string with live odds data.
    """
    logger.debug("Tool 'get_live_odds' called - Not Caching Live Data")
    return fetch_odds_data_logic() 
"""
This module provides a toolkit of miscellaneous functions exposed as agent tools,
primarily focusing on player matchups and game odds. These tools wrap specific
logic functions from `backend.api_tools`.
"""
import logging
from typing import Optional
from agno.tools import tool
from nba_api.stats.library.parameters import SeasonTypeAllStar
from backend.config import settings

# Import specific logic functions for misc tools
from backend.api_tools.matchup_tools import fetch_league_season_matchups_logic, fetch_matchups_rollup_logic
from backend.api_tools.odds_tools import fetch_odds_data_logic

logger = logging.getLogger(__name__)

@tool
def get_season_matchups(
    def_player_identifier: str,
    off_player_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    bypass_cache: bool = False # Added to match underlying logic
) -> str:
    """
    Fetches head-to-head matchup statistics between a defensive player and an offensive player for a specific season.

    Args:
        def_player_identifier (str): The name or ID of the defensive player.
        off_player_identifier (str): The name or ID of the offensive player.
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
            Defaults to the current season from settings.
        season_type (str, optional): The type of season (e.g., "Regular Season", "Playoffs").
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`. Defaults to "Regular Season".
        bypass_cache (bool, optional): If True, bypasses any caching. Defaults to False.

    Returns:
        str: JSON string containing matchup statistics, including data on how the offensive player
             performed when guarded by the defensive player.
    """
    logger.debug(f"Tool 'get_season_matchups' called for Def: {def_player_identifier}, Off: {off_player_identifier}, Season: {season}, Type: {season_type}")
    return fetch_league_season_matchups_logic(
        def_player_identifier=def_player_identifier,
        off_player_identifier=off_player_identifier,
        season=season,
        season_type=season_type,
        bypass_cache=bypass_cache
    )

@tool
def get_matchups_rollup(
    def_player_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    bypass_cache: bool = False # Added to match underlying logic
) -> str:
    """
    Fetches a rollup of matchup statistics for a defensive player against all opponents for a specific season.

    Args:
        def_player_identifier (str): The name or ID of the defensive player.
        season (str, optional): The NBA season identifier in YYYY-YY format. Defaults to current season.
        season_type (str, optional): The type of season. Defaults to "Regular Season".
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`.
        bypass_cache (bool, optional): If True, bypasses any caching. Defaults to False.

    Returns:
        str: JSON string containing matchup rollup statistics, showing how various offensive players
             performed when guarded by the specified defensive player.
    """
    logger.debug(f"Tool 'get_matchups_rollup' called for Def: {def_player_identifier}, Season: {season}, Type: {season_type}")
    return fetch_matchups_rollup_logic(
        def_player_identifier=def_player_identifier,
        season=season,
        season_type=season_type,
        bypass_cache=bypass_cache
    )

@tool
def get_live_odds(bypass_cache: bool = False) -> str: # Added bypass_cache to match underlying logic
    """
    Fetches live betting odds for today's NBA games.
    This data is typically cached for a short period by the underlying logic.

    Args:
        bypass_cache (bool, optional): If True, attempts to fetch fresh data, bypassing the short-term cache.
            Defaults to False.

    Returns:
        str: JSON string with live odds data for current games, including spread, total, and moneyline if available.
    """
    logger.debug(f"Tool 'get_live_odds' called. Bypass cache: {bypass_cache}")
    return fetch_odds_data_logic(bypass_cache=bypass_cache)
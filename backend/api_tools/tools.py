from typing import Dict, List, Optional, Any
import json
import logging
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed
from agno.tools import tool

from .player_tracking import (
    fetch_player_shots_tracking_logic,
    fetch_player_rebounding_stats_logic,
    fetch_player_passing_stats_logic
)

from .team_tracking import (
    fetch_team_shooting_stats_logic,
    fetch_team_rebounding_stats_logic,
    fetch_team_passing_stats_logic
)

logger = logging.getLogger(__name__)

@tool
def get_team_passing_stats(
    team_name: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> str:
    """
    Get detailed team passing stats based on tracking data.
    
    Args:
        team_name: Name of the team or team abbreviation (e.g., "Lakers" or "LAL")
        season: Season to get data for, in format "YYYY-YY" (e.g., "2022-23")
        season_type: "Regular Season", "Playoffs", or other valid season type
        per_mode: Mode of stats, like "PerGame" or "Totals"
        
    Returns:
        String JSON with passing statistics for the team
    """
    logger.debug(f"Tool get_team_passing_stats called for {team_name}, season {season}")
    return fetch_team_passing_stats_logic(
        team_identifier=team_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )

@tool
def get_team_shooting_stats(
    team_name: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> str:
    """
    Get detailed team shooting stats based on tracking data.
    
    Args:
        team_name: Name of the team or team abbreviation (e.g., "Lakers" or "LAL")
        season: Season to get data for, in format "YYYY-YY" (e.g., "2022-23")
        season_type: "Regular Season", "Playoffs", or other valid season type
        per_mode: Mode of stats, like "PerGame" or "Totals"
        
    Returns:
        String JSON with shooting statistics for the team
    """
    logger.debug(f"Tool get_team_shooting_stats called for {team_name}, season {season}")
    return fetch_team_shooting_stats_logic(
        team_identifier=team_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )

@tool
def get_team_rebounding_stats(
    team_name: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> str:
    """
    Get detailed team rebounding stats based on tracking data.
    
    Args:
        team_name: Name of the team or team abbreviation (e.g., "Lakers" or "LAL")
        season: Season to get data for, in format "YYYY-YY" (e.g., "2022-23")
        season_type: "Regular Season", "Playoffs", or other valid season type
        per_mode: Mode of stats, like "PerGame" or "Totals"
        
    Returns:
        String JSON with rebounding statistics for the team
    """
    logger.debug(f"Tool get_team_rebounding_stats called for {team_name}, season {season}")
    return fetch_team_rebounding_stats_logic(
        team_identifier=team_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )

@tool
def get_player_shots_tracking(
    player_name: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> str:
    """
    Get detailed player shooting stats based on tracking data.
    
    Args:
        player_name: Player's name (e.g., "LeBron James")
        season: Season to get data for, in format "YYYY-YY" (e.g., "2022-23")
        season_type: "Regular Season", "Playoffs", or other valid season type
        per_mode: Mode of stats, like "PerGame" or "Totals"
        
    Returns:
        String JSON with shooting statistics for the player
    """
    logger.debug(f"Tool get_player_shots_tracking called for {player_name}, season {season}")
    return fetch_player_shots_tracking_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )

@tool
def get_player_rebounding_stats(
    player_name: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> str:
    """
    Get detailed player rebounding stats based on tracking data.
    
    Args:
        player_name: Player's name (e.g., "LeBron James")
        season: Season to get data for, in format "YYYY-YY" (e.g., "2022-23")
        season_type: "Regular Season", "Playoffs", or other valid season type
        per_mode: Mode of stats, like "PerGame" or "Totals"
        
    Returns:
        String JSON with rebounding statistics for the player
    """
    logger.debug(f"Tool get_player_rebounding_stats called for {player_name}, season {season}")
    return fetch_player_rebounding_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )

@tool
def get_player_passing_stats(
    player_name: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> str:
    """
    Get detailed player passing stats based on tracking data.
    
    Args:
        player_name: Player's name (e.g., "LeBron James")
        season: Season to get data for, in format "YYYY-YY" (e.g., "2022-23")
        season_type: "Regular Season", "Playoffs", or other valid season type
        per_mode: Mode of stats, like "PerGame" or "Totals"
        
    Returns:
        String JSON with passing statistics for the player
    """
    logger.debug(f"Tool get_player_passing_stats called for {player_name}, season {season}")
    return fetch_player_passing_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )

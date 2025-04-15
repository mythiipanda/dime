from typing import Dict, List, Optional, Any, Union
import json
import logging
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed
from agno.tools import tool
from flask import jsonify, Response

from backend.api_tools.player_tracking import (
    fetch_player_info_logic,
    fetch_player_rebounding_stats_logic,
    fetch_player_passing_stats_logic,
    fetch_player_shots_tracking_logic,
)

from backend.api_tools.player_tools import (
    fetch_player_gamelog_logic,
    fetch_player_career_stats_logic,
)

from backend.api_tools.team_tracking import (
    fetch_team_shooting_stats_logic,
    fetch_team_rebounding_stats_logic,
    fetch_team_passing_stats_logic,
)

from backend.api_tools.team_tools import (
    fetch_team_info_and_roster_logic,
)

from backend.api_tools.player_tools import _find_player_id
from backend.config import ErrorMessages

logger = logging.getLogger(__name__)

def _format_tool_response(data: Any) -> str:
    """Format tool response as a JSON string."""
    try:
        # If data is already a string, try to validate it as JSON
        if isinstance(data, str):
            try:
                # Parse and re-serialize to ensure valid JSON
                parsed = json.loads(data)
                return json.dumps(parsed)
            except json.JSONDecodeError:
                # If not valid JSON, wrap it in a message object
                return json.dumps({"message": data})
        
        # If data is None, return a standard message
        elif data is None:
            return json.dumps({"message": "No data available"})
        
        # If data is a dict or any other type, convert to JSON string
        return json.dumps(data, default=str)
            
    except Exception as e:
        logger.error(f"Error formatting tool response: {e}", exc_info=True)
        return json.dumps({"error": str(e)})

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
    try:
        result = fetch_team_passing_stats_logic(
            team_identifier=team_name,
            season=season,
            season_type=season_type,
            per_mode=per_mode
        )
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_team_passing_stats: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

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
    try:
        result = fetch_team_shooting_stats_logic(
            team_identifier=team_name,
            season=season,
            season_type=season_type,
            per_mode=per_mode
        )
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_team_shooting_stats: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

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
    try:
        result = fetch_team_rebounding_stats_logic(
            team_identifier=team_name,
            season=season,
            season_type=season_type,
            per_mode=per_mode
        )
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_team_rebounding_stats: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_player_info(player_name: str) -> str:
    """Get detailed information about a player."""
    try:
        # Get the result from the logic function
        result = fetch_player_info_logic(player_name)
        
        # If result is already a string, return it formatted
        if isinstance(result, str):
            return _format_tool_response(result)
            
        # Otherwise format the raw result
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_player_info: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_player_rebounding_stats(
    player_name: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    """Get detailed rebounding statistics for a player."""
    try:
        result = fetch_player_rebounding_stats_logic(
            player_name=player_name,
            season=season,
            season_type=season_type
        )
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_player_rebounding_stats: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_player_passing_stats(
    player_name: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    """Get detailed passing statistics for a player."""
    try:
        result = fetch_player_passing_stats_logic(
            player_name=player_name,
            season=season,
            season_type=season_type
        )
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_player_passing_stats: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_player_shots_tracking(player_id: str) -> str:
    """
    Get player shots tracking data.
    
    Args:
        player_id (str): The NBA player ID
        
    Returns:
        str: JSON string containing player shots tracking data or error message
    """
    try:
        result = fetch_player_shots_tracking_logic(player_id)
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_player_shots_tracking: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_player_gamelog(player_name: str, season: str = "2023-24", season_type: str = "Regular Season") -> str:
    """Get game log data for a player."""
    try:
        result = fetch_player_gamelog_logic(player_name, season, season_type)
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_player_gamelog: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_player_career_stats(player_name: str) -> str:
    """Get career statistics for a player."""
    try:
        result = fetch_player_career_stats_logic(player_name)
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_player_career_stats: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_player_shots_tracking(player_name: str, season: str = "2023-24", season_type: str = "Regular Season", per_mode: str = "PerGame") -> str:
    """Get shots tracking data for a player."""
    try:
        result = fetch_player_shots_tracking_logic(player_name, season, season_type, per_mode)
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_player_shots_tracking: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_player_rebounding_stats(player_name: str, season: str = "2023-24", season_type: str = "Regular Season", per_mode: str = "PerGame") -> str:
    """Get rebounding statistics for a player."""
    try:
        result = fetch_player_rebounding_stats_logic(player_name, season, season_type, per_mode)
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_player_rebounding_stats: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_player_passing_stats(player_name: str, season: str = "2023-24", season_type: str = "Regular Season", per_mode: str = "PerGame") -> str:
    """Get passing statistics for a player."""
    try:
        result = fetch_player_passing_stats_logic(player_name, season, season_type, per_mode)
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_player_passing_stats: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_team_info_and_roster(team_identifier: str) -> str:
    """Get team information and roster."""
    try:
        result = fetch_team_info_and_roster_logic(team_identifier)
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_team_info_and_roster: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_team_passing_stats(team_identifier: str, season: str = "2023-24", season_type: str = "Regular Season", per_mode: str = "PerGame") -> str:
    """Get team passing statistics."""
    try:
        result = fetch_team_passing_stats_logic(team_identifier, season, season_type, per_mode)
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_team_passing_stats: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_team_shooting_stats(team_identifier: str, season: str = "2023-24", season_type: str = "Regular Season", per_mode: str = "PerGame") -> str:
    """Get team shooting statistics."""
    try:
        result = fetch_team_shooting_stats_logic(team_identifier, season, season_type, per_mode)
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_team_shooting_stats: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_team_rebounding_stats(team_identifier: str, season: str = "2023-24", season_type: str = "Regular Season", per_mode: str = "PerGame") -> str:
    """Get team rebounding statistics."""
    try:
        result = fetch_team_rebounding_stats_logic(team_identifier, season, season_type, per_mode)
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_team_rebounding_stats: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def find_games(team_identifier: str = None, season: str = "2023-24", season_type: str = "Regular Season") -> str:
    """Find games for a team."""
    try:
        result = find_games_logic(team_identifier, season, season_type)
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in find_games: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_boxscore_traditional(game_id: str) -> str:
    """Get traditional boxscore for a game."""
    try:
        result = fetch_boxscore_traditional_logic(game_id)
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_boxscore_traditional: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_playbyplay(game_id: str) -> str:
    """Get play-by-play data for a game."""
    try:
        result = fetch_playbyplay_logic(game_id)
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_playbyplay: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_league_standings(season: str = "2023-24") -> str:
    """Get league standings."""
    try:
        result = fetch_league_standings_logic(season)
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_league_standings: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_scoreboard(date: str = None) -> str:
    """Get scoreboard for a specific date."""
    try:
        result = fetch_scoreboard_logic(date)
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_scoreboard: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_league_leaders(stat_category: str = "PTS", season: str = "2023-24", season_type: str = "Regular Season", per_mode: str = "PerGame") -> str:
    """Get league leaders for a specific statistic."""
    try:
        result = fetch_league_leaders_logic(stat_category, season, season_type, per_mode)
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_league_leaders: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def get_draft_history(season: str = "2023") -> str:
    """Get draft history for a specific season."""
    try:
        result = fetch_draft_history_logic(season)
        return _format_tool_response(result)
    except Exception as e:
        logger.error(f"Error in get_draft_history: {e}", exc_info=True)
        return _format_tool_response({"error": str(e)})

@tool
def think(thought: str) -> str:
    """Think about something."""
    return _format_tool_response({"thought": thought})

# Player tracking logic functions
import logging
import json
from typing import Optional, Dict, Any

from nba_api.stats.endpoints import (
    playerdashboardbyclutch,
    playerdashboardbyshootingsplits,
    playerdashptreb,
    playerdashptpass,
    commonplayerinfo,
    playerdashptshots
)
from nba_api.stats.static import players
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed,
    MeasureTypeDetailedDefense
)

from config import DEFAULT_TIMEOUT, ErrorMessages  # Changed to absolute import
from .utils import _process_dataframe, format_response, retry_on_timeout
from .player_tools import _find_player_id, find_player_by_name
from .http_client import nba_session

logger = logging.getLogger(__name__)

# Update the endpoints to use our configured session
playerdashboardbyclutch.requests = nba_session
playerdashboardbyshootingsplits.requests = nba_session
playerdashptreb.requests = nba_session
playerdashptpass.requests = nba_session
commonplayerinfo.requests = nba_session
playerdashptshots.requests = nba_session

def fetch_player_clutch_stats_logic(player_name: str, season: str, season_type: str = SeasonTypeAllStar.regular):
    """Fetches player stats in clutch situations."""
    logger.info(f"Executing fetch_player_clutch_stats_logic for: {player_name}, Season: {season}")
    
    # Add input validation
    if not player_name or not season:
        logger.warning("Player name or season is missing.")
        return json.dumps({"error": ErrorMessages.MISSING_PLAYER_OR_SEASON})
        
    player_id, player_actual_name = _find_player_id(player_name)
    if player_id is None:
        return json.dumps({"error": f"Player {player_name} not found"})
    try:
        # Use only the required parameters
        clutch_endpoint = playerdashboardbyclutch.PlayerDashboardByClutch(
            player_id=player_id,
            season=season,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Get available attributes from the endpoint
        available_attributes = [attr for attr in dir(clutch_endpoint) 
                               if not attr.startswith('_') and hasattr(getattr(clutch_endpoint, attr), 'get_data_frame')]
        
        logger.debug(f"Available attributes in PlayerDashboardByClutch: {available_attributes}")
        
        # Initialize result
        result = {
            "player_name": player_actual_name,
            "player_id": player_id,
            "season": season,
            "season_type": season_type
        }
        
        # Safely process data frames
        if hasattr(clutch_endpoint, 'overall_player_dashboard'):
            overall_df = clutch_endpoint.overall_player_dashboard.get_data_frame()
            result["overall_data"] = _process_dataframe(overall_df, single_row=True)
        
        # Add other available data frames
        for attr in available_attributes:
            if attr != 'overall_player_dashboard' and attr not in result:
                try:
                    df = getattr(clutch_endpoint, attr).get_data_frame()
                    result[attr] = _process_dataframe(df, single_row=False)
                except Exception as df_error:
                    logger.warning(f"Error processing {attr} dataframe: {df_error}")
        
        return json.dumps(result, default=str)
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_clutch_stats_logic for '{player_name}': {e}", exc_info=True)
        return json.dumps({"error": f"Error fetching clutch stats: {str(e)}"})

def _get_player_team_id(player_id: str, season: str) -> str:
    """Get the team ID for a player in a given season."""
    try:
        player_info = commonplayerinfo.CommonPlayerInfo(player_id=player_id).get_normalized_dict()
        if 'CommonPlayerInfo' in player_info and player_info['CommonPlayerInfo']:
            return player_info['CommonPlayerInfo'][0].get('TEAM_ID')
        return None
    except Exception as e:
        logger.error(f"Error getting team ID for player {player_id}: {e}")
        return None

def fetch_player_shots_tracking_logic(player_name: str, season: str, season_type: str = SeasonTypeAllStar.regular):
    """Fetches player shot tracking stats."""
    if not player_name or not season:
        return json.dumps({"error": "Player name and season are required"})
    
    logger.info(f"Executing fetch_player_shots_tracking_logic for: {player_name}, Season: {season}")
    player_id, player_actual_name = _find_player_id(player_name)
    if player_id is None:
        return json.dumps({"error": f"Player {player_name} not found"})
    
    # Get team ID
    team_id = _get_player_team_id(player_id, season)
    if team_id is None:
        return json.dumps({"error": f"Could not find team ID for player {player_name} in season {season}"})
    
    try:
        # Use the correct parameters
        shots_endpoint = playerdashptshots.PlayerDashPtShots(
            player_id=player_id,
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Get available attributes from the endpoint
        available_attributes = [attr for attr in dir(shots_endpoint) 
                               if not attr.startswith('_') and hasattr(getattr(shots_endpoint, attr), 'get_data_frame')]
        
        logger.debug(f"Available attributes in PlayerDashPtShots: {available_attributes}")
        
        # Initialize result
        result = {
            "player_name": player_actual_name,
            "player_id": player_id,
            "team_id": team_id,
            "season": season,
            "season_type": season_type
        }
        
        # Safely process data frames
        if hasattr(shots_endpoint, 'overall_player_dashboard'):
            overall_df = shots_endpoint.overall_player_dashboard.get_data_frame()
            result["overall_data"] = _process_dataframe(overall_df, single_row=True)
        
        # Add other available data frames
        for attr in available_attributes:
            if attr != 'overall_player_dashboard' and attr not in result:
                try:
                    df = getattr(shots_endpoint, attr).get_data_frame()
                    result[attr] = _process_dataframe(df, single_row=False)
                except Exception as df_error:
                    logger.warning(f"Error processing {attr} dataframe: {df_error}")
        
        return json.dumps(result, default=str)
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_shots_tracking_logic for '{player_name}': {e}", exc_info=True)
        return format_response(error=f"Unexpected error retrieving shot tracking stats for {player_name}: {str(e)}")

def fetch_player_rebounding_stats_logic(player_name: str, season: str, season_type: str = SeasonTypeAllStar.regular):
    """Fetches player rebounding stats."""
    if not player_name or not season:
        return json.dumps({"error": "Player name and season are required"})
    
    logger.info(f"Executing fetch_player_rebounding_stats_logic for: {player_name}, Season: {season}")
    player_id, player_actual_name = _find_player_id(player_name)
    if player_id is None:
        return json.dumps({"error": f"Player {player_name} not found"})
    
    # Get team ID
    team_id = _get_player_team_id(player_id, season)
    if team_id is None:
        return json.dumps({"error": f"Could not find team ID for player {player_name} in season {season}"})
    
    try:
        # Use the correct parameters
        reb_endpoint = playerdashptreb.PlayerDashPtReb(
            player_id=player_id,
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Get available attributes from the endpoint
        available_attributes = [attr for attr in dir(reb_endpoint) 
                               if not attr.startswith('_') and hasattr(getattr(reb_endpoint, attr), 'get_data_frame')]
        
        logger.debug(f"Available attributes in PlayerDashPtReb: {available_attributes}")
        
        # Initialize result
        result = {
            "player_name": player_actual_name,
            "player_id": player_id,
            "team_id": team_id,
            "season": season,
            "season_type": season_type
        }
        
        # Safely process data frames
        if hasattr(reb_endpoint, 'overall_player_dashboard'):
            overall_df = reb_endpoint.overall_player_dashboard.get_data_frame()
            result["overall_data"] = _process_dataframe(overall_df, single_row=True)
        
        # Add other available data frames
        for attr in available_attributes:
            if attr != 'overall_player_dashboard' and attr not in result:
                try:
                    df = getattr(reb_endpoint, attr).get_data_frame()
                    result[attr] = _process_dataframe(df, single_row=False)
                except Exception as df_error:
                    logger.warning(f"Error processing {attr} dataframe: {df_error}")
        
        return format_response(result)
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_rebounding_stats_logic for '{player_name}': {e}", exc_info=True)
        return format_response(error=f"Unexpected error retrieving rebounding stats for {player_name}: {str(e)}")

def fetch_player_passing_stats_logic(player_name: str, season: str, season_type: str = SeasonTypeAllStar.regular):
    """Fetches player passing stats."""
    if not player_name or not season:
        return json.dumps({"error": "Player name and season are required"})
    
    logger.info(f"Executing fetch_player_passing_stats_logic for: {player_name}, Season: {season}")
    player_id, player_actual_name = _find_player_id(player_name)
    if player_id is None:
        return json.dumps({"error": f"Player {player_name} not found"})
    
    # Get team ID
    team_id = _get_player_team_id(player_id, season)
    if team_id is None:
        return json.dumps({"error": f"Could not find team ID for player {player_name} in season {season}"})
    
    try:
        # Use the correct parameters
        pass_endpoint = playerdashptpass.PlayerDashPtPass(
            player_id=player_id,
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Get available attributes from the endpoint
        available_attributes = [attr for attr in dir(pass_endpoint) 
                               if not attr.startswith('_') and hasattr(getattr(pass_endpoint, attr), 'get_data_frame')]
        
        logger.debug(f"Available attributes in PlayerDashPtPass: {available_attributes}")
        
        # Initialize result
        result = {
            "player_name": player_actual_name,
            "player_id": player_id,
            "team_id": team_id,
            "season": season,
            "season_type": season_type
        }
        
        # Safely process data frames
        if hasattr(pass_endpoint, 'overall_player_dashboard'):
            overall_df = pass_endpoint.overall_player_dashboard.get_data_frame()
            result["overall_data"] = _process_dataframe(overall_df, single_row=True)
        
        # Add other available data frames
        for attr in available_attributes:
            if attr != 'overall_player_dashboard' and attr not in result:
                try:
                    df = getattr(pass_endpoint, attr).get_data_frame()
                    result[attr] = _process_dataframe(df, single_row=False)
                except Exception as df_error:
                    logger.warning(f"Error processing {attr} dataframe: {df_error}")
        
        return format_response(result)
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_passing_stats_logic for '{player_name}': {e}", exc_info=True)
        return format_response(error=f"Unexpected error retrieving passing stats for {player_name}: {str(e)}")

def fetch_player_shooting_stats_logic(player_name: str, season: str, per_mode: str = PerModeDetailed.per_game, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetch shooting stats for a player.
    
    Args:
        player_name (str): Name of the player
        season (str): Season in YYYY-YY format
        per_mode (str): Per mode type (per game, per minute, etc.)
        season_type (str): Type of season (regular, playoffs, etc.)
        
    Returns:
        str: JSON string with player shooting stats
    """
    # Implementation of fetch_player_shooting_stats_logic function
    # This function needs to be implemented
    return json.dumps({"error": "Function not implemented"})

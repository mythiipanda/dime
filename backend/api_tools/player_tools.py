import logging
import pandas as pd
from typing import Tuple, Optional, List, Dict, Any
from nba_api.stats.static import players
# Import new endpoint
from nba_api.stats.endpoints import commonplayerinfo, playergamelog, playercareerstats, playerawards, playerdashboardbyclutch
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerMode36, LeagueID
import json
import requests
from config import DEFAULT_TIMEOUT, HEADSHOT_BASE_URL, ErrorMessages as Errors, CURRENT_SEASON  # Changed to absolute import
from .utils import _process_dataframe, _validate_season_format

logger = logging.getLogger(__name__)

def _find_player_id(player_name: str) -> tuple[str, str]:
    """Find a player's ID by their name."""
    if not player_name:
        return None, None
    
    try:
        player_list = players.find_players_by_full_name(player_name)
        if player_list:
            # Return the first match's ID and full name
            return player_list[0]['id'], player_list[0]['full_name']
        return None, None
    except Exception as e:
        logger.error(f"Error finding player ID for {player_name}: {e}")
        return None, None

def fetch_player_info_logic(player_name: str) -> str:
    """Core logic to fetch player info."""
    logger.info(f"Executing fetch_player_info_logic for: '{player_name}'")
    if not player_name or not player_name.strip():
        return json.dumps({"error": Errors.PLAYER_NAME_EMPTY})
    
    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return json.dumps({"error": Errors.PLAYER_NOT_FOUND.format(name=player_name)})

        logger.debug(f"Fetching commonplayerinfo for player ID: {player_id}")
        try:
            info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=DEFAULT_TIMEOUT)
            logger.debug(f"commonplayerinfo API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api commonplayerinfo failed for ID {player_id}: {api_error}", exc_info=True)
            return json.dumps({"error": Errors.PLAYER_INFO_API.format(name=player_actual_name, error=str(api_error))})

        player_info_dict = _process_dataframe(info_endpoint.common_player_info.get_data_frame(), single_row=True)
        headline_stats_dict = _process_dataframe(info_endpoint.player_headline_stats.get_data_frame(), single_row=True)

        if player_info_dict is None or headline_stats_dict is None:
            logger.error(f"DataFrame processing failed for {player_actual_name}.")
            return json.dumps({"error": Errors.PLAYER_INFO_PROCESSING.format(name=player_actual_name)})

        result = {"player_info": player_info_dict or {}, "headline_stats": headline_stats_dict or {}}
        logger.info(f"fetch_player_info_logic completed for '{player_actual_name}'")
        return json.dumps(result, default=str)
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_info_logic for '{player_name}': {e}", exc_info=True)
        return json.dumps({"error": Errors.PLAYER_INFO_UNEXPECTED.format(name=player_name, error=str(e))})

def fetch_player_gamelog_logic(player_name: str, season: str, season_type: str = SeasonTypeAllStar.regular) -> str:
    """Core logic to fetch player game logs."""
    logger.info(f"Executing fetch_player_gamelog_logic for: '{player_name}', Season: {season}, Type: {season_type}")
    if not player_name or not player_name.strip():
        return json.dumps({"error": Errors.PLAYER_NAME_EMPTY})
    if not season or not _validate_season_format(season):
        return json.dumps({"error": Errors.INVALID_SEASON_FORMAT.format(season=season)})

    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return json.dumps({"error": Errors.PLAYER_NOT_FOUND.format(name=player_name)})

        logger.debug(f"Fetching playergamelog for ID: {player_id}, Season: {season}, Type: {season_type}")
        try:
            gamelog_endpoint = playergamelog.PlayerGameLog(
                player_id=player_id, season=season, season_type_all_star=season_type, timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"playergamelog API call successful for ID: {player_id}, Season: {season}")
        except Exception as api_error:
            logger.error(f"nba_api playergamelog failed for ID {player_id}, Season {season}: {api_error}", exc_info=True)
            return json.dumps({"error": Errors.PLAYER_GAMELOG_API.format(name=player_actual_name, season=season, error=str(api_error))})

        gamelog_list = _process_dataframe(gamelog_endpoint.get_data_frames()[0], single_row=False)

        if gamelog_list is None:
            logger.error(f"DataFrame processing failed for gamelog of {player_actual_name} ({season}).")
            return json.dumps({"error": Errors.PLAYER_GAMELOG_PROCESSING.format(name=player_actual_name, season=season)})

        result = {"player_name": player_actual_name, "player_id": player_id, "season": season, "season_type": season_type, "gamelog": gamelog_list}
        logger.info(f"fetch_player_gamelog_logic completed for '{player_actual_name}', Season: {season}")
        return json.dumps(result, default=str)
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_gamelog_logic for '{player_name}', Season {season}: {e}", exc_info=True)
        return json.dumps({"error": Errors.PLAYER_GAMELOG_UNEXPECTED.format(name=player_name, season=season, error=str(e))})

def fetch_player_career_stats_logic(player_name: str, per_mode36: str = PerMode36.per_game) -> str:
    """Core logic to fetch player career stats."""
    logger.info(f"Executing fetch_player_career_stats_logic for: '{player_name}', PerMode36: {per_mode36}")
    if not player_name or not player_name.strip():
        return json.dumps({"error": Errors.PLAYER_NAME_EMPTY})

    valid_per_modes = [getattr(PerMode36, attr) for attr in dir(PerMode36) if not attr.startswith('_') and isinstance(getattr(PerMode36, attr), str)]
    original_request_mode = per_mode36
    if per_mode36 not in valid_per_modes:
        logger.warning(f"Invalid per_mode36 '{per_mode36}'. Using default '{PerMode36.per_game}'. Valid options: {valid_per_modes}")
        per_mode36 = PerMode36.per_game

    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return json.dumps({"error": Errors.PLAYER_NOT_FOUND.format(name=player_name)})

        # TODO: The 'per_mode36' parameter is currently ignored in the API call below
        #       due to suspected issues with the nba_api library handling it correctly
        #       for playercareerstats. It always fetches the default (PerGame).
        #       Needs investigation if other PerModes are required.
        logger.debug(f"Fetching playercareerstats for ID: {player_id} (Ignoring PerMode in API call)")
        try:
            career_endpoint = playercareerstats.PlayerCareerStats(player_id=player_id, timeout=DEFAULT_TIMEOUT)
            logger.debug(f"playercareerstats API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api playercareerstats failed for ID {player_id}: {api_error}", exc_info=True)
            return json.dumps({"error": Errors.PLAYER_CAREER_STATS_API.format(name=player_actual_name, error=str(api_error))})

        season_totals = _process_dataframe(career_endpoint.season_totals_regular_season.get_data_frame(), single_row=False)
        career_totals = _process_dataframe(career_endpoint.career_totals_regular_season.get_data_frame(), single_row=True)

        if season_totals is None or career_totals is None:
            logger.error(f"DataFrame processing failed for career stats of {player_actual_name}.")
            return json.dumps({"error": Errors.PLAYER_CAREER_STATS_PROCESSING.format(name=player_actual_name)})

        result = {
            "player_name": player_actual_name,
            "player_id": player_id,
            "per_mode_requested": original_request_mode,
            "data_retrieved_mode": "Default (PerMode parameter ignored)",
            "season_totals_regular_season": season_totals or [],
            "career_totals_regular_season": career_totals or {}
        }
        logger.info(f"fetch_player_career_stats_logic completed for '{player_actual_name}'")
        return json.dumps(result, default=str)
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_career_stats_logic for '{player_name}': {e}", exc_info=True)
        return json.dumps({"error": Errors.PLAYER_CAREER_STATS_UNEXPECTED.format(name=player_name, error=str(e))})

def get_player_headshot_url(player_id: str) -> str:
    """
    Get the URL for a player's headshot image.
    Args:
        player_id (str): The player's ID
    Returns:
        str: The URL for the player's headshot image
    """
    if not player_id:
        raise ValueError(Errors.PLAYER_ID_EMPTY)
    if not player_id.isdigit():
        raise ValueError(Errors.INVALID_PLAYER_ID_FORMAT.format(player_id=player_id))
    
    return f"{HEADSHOT_BASE_URL}/{player_id}.png"

def find_players_by_name_fragment(name_fragment: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Find players whose names contain the given fragment.
    Args:
        name_fragment (str): The name fragment to search for
        limit (int): Maximum number of results to return
    Returns:
        List[Dict[str, Any]]: List of matching players with their details
    """
    if not name_fragment:
        raise ValueError(Errors.PLAYER_NAME_EMPTY)
    
    try:
        # Get all players
        all_players = players.get_players()
        if not all_players:
            logger.error("No players found in NBA API")
            raise ValueError(Errors.PLAYER_LIST_EMPTY)
        
        # Filter players by name fragment (case-insensitive)
        name_fragment_lower = name_fragment.lower()
        matching_players = [
            player for player in all_players
            if name_fragment_lower in player['full_name'].lower()
        ]
        
        # Sort by most recent players first and limit results
        matching_players.sort(key=lambda x: x.get('to_year', 0), reverse=True)
        limited_players = matching_players[:limit]
        
        # Add headshot URLs to results
        for player in limited_players:
            player['headshot_url'] = get_player_headshot_url(str(player['id']))
        
        return limited_players
        
    except Exception as e:
        logger.error(f"Error finding players by name fragment: {str(e)}", exc_info=True)
        raise ValueError(f"Error finding players: {str(e)}")

def get_player_info(player_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a player.
    Args:
        player_id (str): The player's ID
    Returns:
        Dict[str, Any]: Player information
    """
    if not player_id:
        raise ValueError(Errors.PLAYER_ID_EMPTY)
    if not player_id.isdigit():
        raise ValueError(Errors.INVALID_PLAYER_ID_FORMAT.format(player_id=player_id))
    
    try:
        # Get player info from NBA API
        player_info = commonplayerinfo.CommonPlayerInfo(
            player_id=player_id,
            league_id=LeagueID.nba,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Process player info
        info_df = player_info.common_player_info.get_data_frame()
        if info_df is None or info_df.empty:
            raise ValueError(f"No information found for player ID: {player_id}")
        
        # Convert DataFrame row to dict
        player_dict = _process_dataframe(info_df, single_row=True)
        if not player_dict:
            raise ValueError(f"Error processing player information for ID: {player_id}")
        
        # Add headshot URL
        player_dict['headshot_url'] = get_player_headshot_url(player_id)
        
        return player_dict
        
    except requests.exceptions.Timeout:
        logger.error(f"Request timed out for player ID: {player_id}")
        raise ValueError(f"Request timed out for player ID: {player_id}")
    except Exception as e:
        logger.error(f"Error getting player info: {str(e)}", exc_info=True)
        raise ValueError(f"Error getting player information: {str(e)}")

def fetch_player_awards_logic(player_name: str) -> str:
    """Core logic to fetch player awards."""
    logger.info(f"Executing fetch_player_awards_logic for: '{player_name}'")
    if not player_name or not player_name.strip():
        return json.dumps({"error": Errors.PLAYER_NAME_EMPTY})

    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return json.dumps({"error": Errors.PLAYER_NOT_FOUND.format(name=player_name)})

        logger.debug(f"Fetching playerawards for ID: {player_id}")
        try:
            awards_endpoint = playerawards.PlayerAwards(player_id=player_id, timeout=DEFAULT_TIMEOUT)
            logger.debug(f"playerawards API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api playerawards failed for ID {player_id}: {api_error}", exc_info=True)
            return json.dumps({"error": Errors.PLAYER_AWARDS_API.format(name=player_actual_name, error=str(api_error))}) # Need to add this error message

        awards_list = _process_dataframe(awards_endpoint.player_awards.get_data_frame(), single_row=False)

        if awards_list is None:
            logger.error(f"DataFrame processing failed for awards of {player_actual_name}.")
            # Return empty list if processing fails but API call succeeded (might mean no awards)
            awards_list = []
            # return json.dumps({"error": Errors.PLAYER_AWARDS_PROCESSING.format(name=player_actual_name)}) # Need to add this error message

        result = {
            "player_name": player_actual_name,
            "player_id": player_id,
            "awards": awards_list
        }
        logger.info(f"fetch_player_awards_logic completed for '{player_actual_name}'")
        return json.dumps(result, default=str)
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_awards_logic for '{player_name}': {e}", exc_info=True)
        return json.dumps({"error": Errors.PLAYER_AWARDS_UNEXPECTED.format(name=player_name, error=str(e))}) # Need to add this error message

def fetch_player_clutch_stats_logic(player_name: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """Core logic to fetch player clutch stats."""
    logger.info(f"Executing fetch_player_clutch_stats_logic for: '{player_name}', Season: {season}, Type: {season_type}")
    if not player_name or not player_name.strip():
        return json.dumps({"error": Errors.PLAYER_NAME_EMPTY})
    if not season or not _validate_season_format(season):
        return json.dumps({"error": Errors.INVALID_SEASON_FORMAT.format(season=season)})

    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return json.dumps({"error": Errors.PLAYER_NOT_FOUND.format(name=player_name)})

        logger.debug(f"Fetching playerdashboardbyclutch for ID: {player_id}, Season: {season}")
        try:
            clutch_endpoint = playerdashboardbyclutch.PlayerDashboardByClutch(
                player_id=player_id,
                season=season,
                season_type_all_star=season_type,
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"playerdashboardbyclutch API call successful for ID: {player_id}, Season: {season}")
        except Exception as api_error:
            logger.error(f"nba_api playerdashboardbyclutch failed for ID {player_id}, Season {season}: {api_error}", exc_info=True)
            return json.dumps({"error": Errors.PLAYER_CLUTCH_STATS_API.format(name=player_actual_name, season=season, error=str(api_error))})

        overall_clutch = _process_dataframe(clutch_endpoint.overall_player_dashboard.get_data_frame(), single_row=True)
        last5min_clutch = _process_dataframe(clutch_endpoint.last5min_player_dashboard.get_data_frame(), single_row=True)

        if overall_clutch is None or last5min_clutch is None:
            logger.error(f"DataFrame processing failed for clutch stats of {player_actual_name} ({season}).")
            return json.dumps({"error": Errors.PLAYER_CLUTCH_STATS_PROCESSING.format(name=player_actual_name, season=season)})

        result = {
            "player_name": player_actual_name,
            "player_id": player_id,
            "season": season,
            "season_type": season_type,
            "overall_clutch": overall_clutch or {},
            "last5min_clutch": last5min_clutch or {}
        }
        logger.info(f"fetch_player_clutch_stats_logic completed for '{player_actual_name}', Season: {season}")
        return json.dumps(result, default=str)
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_clutch_stats_logic for '{player_name}', Season {season}: {e}", exc_info=True)
        return json.dumps({"error": Errors.PLAYER_CLUTCH_STATS_UNEXPECTED.format(name=player_name, season=season, error=str(e))})

def fetch_player_stats_logic(player_name: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches comprehensive player statistics including career stats, game logs, and info.
    
    Args:
        player_name (str): The name of the player to fetch stats for
        season (str): The season to fetch stats for (e.g., '2023-24')
        season_type (str): The type of season (regular, playoffs, etc.)
        
    Returns:
        str: JSON string containing player statistics or error message
    """
    logger.info(f"Executing fetch_player_stats_logic for: '{player_name}', Season: {season}")
    
    if not player_name or not player_name.strip():
        return json.dumps({"error": Errors.PLAYER_NAME_EMPTY})
    if not season or not _validate_season_format(season):
        return json.dumps({"error": Errors.INVALID_SEASON_FORMAT.format(season=season)})
    
    try:
        # Find player ID
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return json.dumps({"error": Errors.PLAYER_NOT_FOUND.format(name=player_name)})
        
        # Get player info
        info_result = json.loads(fetch_player_info_logic(player_name))
        if "error" in info_result:
            return json.dumps({"error": info_result["error"]})
            
        # Get career stats
        career_result = json.loads(fetch_player_career_stats_logic(player_name))
        if "error" in career_result:
            return json.dumps({"error": career_result["error"]})
            
        # Get game logs for the season
        gamelog_result = json.loads(fetch_player_gamelog_logic(player_name, season, season_type))
        if "error" in gamelog_result:
            return json.dumps({"error": gamelog_result["error"]})
            
        # Get awards
        awards_result = json.loads(fetch_player_awards_logic(player_name))
        if "error" in awards_result:
            return json.dumps({"error": awards_result["error"]})
        
        # Get clutch stats
        clutch_result = json.loads(fetch_player_clutch_stats_logic(player_name, season, season_type))
        if "error" in clutch_result:
            return json.dumps({"error": clutch_result["error"]})
        
        # Combine all results
        result = {
            "player_name": player_actual_name,
            "player_id": player_id,
            "season": season,
            "season_type": season_type,
            "info": info_result.get("player_info", {}),
            "headline_stats": info_result.get("headline_stats", {}),
            "career_stats": {
                "season_totals": career_result.get("season_totals_regular_season", []),
                "career_totals": career_result.get("career_totals_regular_season", {})
            },
            "current_season": {
                "gamelog": gamelog_result.get("gamelog", [])
            },
            "awards": awards_result.get("awards", []),
            "clutch_stats": clutch_result.get("clutch_stats", {})
        }
        
        logger.info(f"fetch_player_stats_logic completed for '{player_actual_name}'")
        return json.dumps(result, default=str)
        
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_stats_logic for '{player_name}': {e}", exc_info=True)
        return json.dumps({"error": f"Unexpected error retrieving player stats: {str(e)}"})

def find_player_by_name(player_name: str) -> Optional[Dict[str, Any]]:
    """
    Find a player by their full name using the NBA API.
    
    Args:
        player_name (str): The full name of the player to search for
        
    Returns:
        Optional[Dict[str, Any]]: Player information if found, None otherwise
    """
    logger.debug(f"Searching for player: '{player_name}'")
    if not player_name or not player_name.strip():
        logger.warning("Empty player name provided")
        return None
        
    try:
        # Try exact match first
        player_list = players.find_players_by_full_name(player_name)
        if player_list:
            logger.info(f"Found player by full name: {player_list[0]['full_name']} (ID: {player_list[0]['id']})")
            return player_list[0]
            
        # Try partial match
        all_players = players.get_players()
        for player in all_players:
            if player_name.lower() in player['full_name'].lower():
                logger.info(f"Found player by partial name: {player['full_name']} (ID: {player['id']})")
                return player
                
        logger.warning(f"No player found for name: '{player_name}'")
        return None
    except Exception as e:
        logger.error(f"Error finding player '{player_name}': {str(e)}", exc_info=True)
        return None

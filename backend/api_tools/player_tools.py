import logging
import json
from typing import Optional, List, Dict, Any, Union
import pandas as pd
import requests
from nba_api.stats.static import players
from nba_api.stats.endpoints import commonplayerinfo, playergamelog, playerawards, playercareerstats
from nba_api.stats.library.parameters import SeasonAll, SeasonTypeAllStar, PerModeDetailed, PerMode36, LeagueID
from backend.config import DEFAULT_TIMEOUT, HEADSHOT_BASE_URL, ErrorMessages as Errors, CURRENT_SEASON
from backend.api_tools.utils import _process_dataframe, _validate_season_format, retry_on_timeout, format_response

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
        return format_response(error=Errors.PLAYER_NAME_EMPTY)
    
    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=Errors.PLAYER_NOT_FOUND.format(name=player_name))

        logger.debug(f"Fetching commonplayerinfo for player ID: {player_id}")
        try:
            info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=DEFAULT_TIMEOUT)
            logger.debug(f"commonplayerinfo API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api commonplayerinfo failed for ID {player_id}: {api_error}", exc_info=True)
            return format_response(error=Errors.PLAYER_INFO_API.format(name=player_actual_name, error=str(api_error)))

        player_info_dict = _process_dataframe(info_endpoint.common_player_info.get_data_frame(), single_row=True)
        headline_stats_dict = _process_dataframe(info_endpoint.player_headline_stats.get_data_frame(), single_row=True)

        if player_info_dict is None or headline_stats_dict is None:
            logger.error(f"DataFrame processing failed for {player_actual_name}.")
            return format_response(error=Errors.PLAYER_INFO_PROCESSING.format(name=player_actual_name))

        logger.info(f"fetch_player_info_logic completed for '{player_actual_name}'")
        return format_response({
            "player_info": player_info_dict or {},
            "headline_stats": headline_stats_dict or {}
        })
        return result
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_info_logic for '{player_name}': {e}", exc_info=True)
        return format_response(error=Errors.PLAYER_INFO_UNEXPECTED.format(name=player_name, error=str(e)))

def fetch_player_gamelog_logic(player_name: str, season: str, season_type: str = SeasonTypeAllStar.regular) -> str:
    """Core logic to fetch player game logs."""
    logger.info(f"Executing fetch_player_gamelog_logic for: '{player_name}', Season: {season}, Type: {season_type}")
    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=Errors.PLAYER_NOT_FOUND.format(name=player_name))

        logger.debug(f"Fetching playergamelog for ID: {player_id}, Season: {season}, Type: {season_type}")
        try:
            gamelog_endpoint = playergamelog.PlayerGameLog(
                player_id=player_id, season=season, season_type_all_star=season_type, timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"playergamelog API call successful for ID: {player_id}, Season: {season}")
        except Exception as api_error:
            logger.error(f"nba_api playergamelog failed for ID {player_id}, Season {season}: {api_error}", exc_info=True)
            return format_response(error=Errors.PLAYER_GAMELOG_API.format(name=player_actual_name, season=season, error=str(api_error)))

        gamelog_list = _process_dataframe(gamelog_endpoint.get_data_frames()[0], single_row=False)

        if gamelog_list is None:
            logger.error(f"DataFrame processing failed for gamelog of {player_actual_name} ({season}).")
            return format_response(error=Errors.PLAYER_GAMELOG_PROCESSING.format(name=player_actual_name, season=season))

        logger.info(f"fetch_player_gamelog_logic completed for '{player_actual_name}', Season: {season}")
        return format_response({
            "player_name": player_actual_name,
            "player_id": player_id,
            "season": season,
            "season_type": season_type,
            "gamelog": gamelog_list
        })
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_gamelog_logic for '{player_name}', Season {season}: {e}", exc_info=True)
        return format_response(error=Errors.PLAYER_GAMELOG_UNEXPECTED.format(name=player_name, season=season, error=str(e)))

def fetch_player_career_stats_logic(player_name: str, per_mode36: str = PerMode36.per_game) -> str:
    """Core logic to fetch player career stats."""
    logger.info(f"Executing fetch_player_career_stats_logic for: '{player_name}', PerMode36: {per_mode36}")
    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)

    valid_per_modes = [getattr(PerMode36, attr) for attr in dir(PerMode36) if not attr.startswith('_') and isinstance(getattr(PerMode36, attr), str)]
    original_request_mode = per_mode36
    if per_mode36 not in valid_per_modes:
        logger.warning(f"Invalid per_mode36 '{per_mode36}'. Using default '{PerMode36.per_game}'. Valid options: {valid_per_modes}")
        per_mode36 = PerMode36.per_game

    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=Errors.PLAYER_NOT_FOUND.format(name=player_name))

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
            return format_response(error=Errors.PLAYER_CAREER_STATS_API.format(name=player_actual_name, error=str(api_error)))

        season_totals = _process_dataframe(career_endpoint.season_totals_regular_season.get_data_frame(), single_row=False)
        career_totals = _process_dataframe(career_endpoint.career_totals_regular_season.get_data_frame(), single_row=True)

        if season_totals is None or career_totals is None:
            logger.error(f"DataFrame processing failed for career stats of {player_actual_name}.")
            return format_response(error=Errors.PLAYER_CAREER_STATS_PROCESSING.format(name=player_actual_name))

        logger.info(f"fetch_player_career_stats_logic completed for '{player_actual_name}'")
        return format_response({
            "player_name": player_actual_name,
            "player_id": player_id,
            "per_mode_requested": original_request_mode,
            "data_retrieved_mode": "Default (PerMode parameter ignored)",
            "season_totals_regular_season": season_totals or [],
            "career_totals_regular_season": career_totals or {}
        })
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_career_stats_logic for '{player_name}': {e}", exc_info=True)
        return format_response(error=Errors.PLAYER_CAREER_STATS_UNEXPECTED.format(name=player_name, error=str(e)))

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

# Removed redundant find_players_by_name_fragment function (exists in search.py)

# Removed unused get_player_info function (agent uses fetch_player_info_logic via tool wrapper)

def fetch_player_awards_logic(player_name: str) -> str:
    """Core logic to fetch player awards."""
    logger.info(f"Executing fetch_player_awards_logic for: '{player_name}'")
    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)

    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=Errors.PLAYER_NOT_FOUND.format(name=player_name))

        logger.debug(f"Fetching playerawards for ID: {player_id}")
        try:
            awards_endpoint = playerawards.PlayerAwards(player_id=player_id, timeout=DEFAULT_TIMEOUT)
            logger.debug(f"playerawards API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api playerawards failed for ID {player_id}: {api_error}", exc_info=True)
            return format_response(error=Errors.PLAYER_AWARDS_API.format(name=player_actual_name, error=str(api_error)))

        awards_list = _process_dataframe(awards_endpoint.player_awards.get_data_frame(), single_row=False)

        if awards_list is None:
            logger.error(f"DataFrame processing failed for awards of {player_actual_name}.")
            # Return empty list if processing fails but API call succeeded (might mean no awards)
            awards_list = []
            # return json.dumps({"error": Errors.PLAYER_AWARDS_PROCESSING.format(name=player_actual_name)}) # Need to add this error message

        logger.info(f"fetch_player_awards_logic completed for '{player_actual_name}'")
        return format_response({
            "player_name": player_actual_name,
            "player_id": player_id,
            "awards": awards_list
        })
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_awards_logic for '{player_name}': {e}", exc_info=True)
        return format_response(error=Errors.PLAYER_AWARDS_UNEXPECTED.format(name=player_name, error=str(e)))

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
        return format_response(error=Errors.PLAYER_NAME_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    
    try:
        # Find player ID
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=Errors.PLAYER_NOT_FOUND.format(name=player_name))
        
        # Get all stats in parallel
        info_result = fetch_player_info_logic(player_name)
        career_result = fetch_player_career_stats_logic(player_name)
        gamelog_result = fetch_player_gamelog_logic(player_name, season, season_type)
        awards_result = fetch_player_awards_logic(player_name)

        # Check each result for errors (they are already JSON strings)
        for result in [info_result, career_result, gamelog_result, awards_result]:
            if '"error":' in result:
                return result  # Return first error encountered

        try:
            # Parse all results once for combining
            info_data = json.loads(info_result)
            career_data = json.loads(career_result)
            gamelog_data = json.loads(gamelog_result)
            awards_data = json.loads(awards_result)

            logger.info(f"fetch_player_stats_logic completed for '{player_actual_name}'")
            return format_response({
                "player_name": player_actual_name,
                "player_id": player_id,
                "season": season,
                "season_type": season_type,
                "info": info_data.get("player_info", {}),
                "headline_stats": info_data.get("headline_stats", {}),
                "career_stats": {
                    "season_totals": career_data.get("season_totals_regular_season", []),
                    "career_totals": career_data.get("career_totals_regular_season", {})
                },
                "current_season": {
                    "gamelog": gamelog_data.get("gamelog", [])
                },
                "awards": awards_data.get("awards", [])
            })
        except json.JSONDecodeError as parse_error:
            logger.error(f"Failed to parse sub-results in fetch_player_stats_logic: {parse_error}")
            return format_response(error="Failed to process intermediate results.")
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_stats_logic for '{player_name}': {e}", exc_info=True)
        return format_response(error=f"Unexpected error retrieving player stats: {str(e)}")

# Removed unused find_player_by_name function

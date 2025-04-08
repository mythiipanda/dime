import logging
import pandas as pd
from typing import Tuple, Optional
from nba_api.stats.static import players
from nba_api.stats.endpoints import commonplayerinfo, playergamelog, playercareerstats
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerMode36
import json

from config import DEFAULT_TIMEOUT, HEADSHOT_BASE_URL, ErrorMessages as Errors
from .utils import _process_dataframe, _validate_season_format

logger = logging.getLogger(__name__)

def _find_player_id(player_name: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Finds a player's ID and actual name from the NBA API.
    Args:
        player_name (str): Full name of the player to search for.
    Returns:
        Tuple[Optional[int], Optional[str]]: (player_id, player_actual_name) or (None, None) if not found.
    """
    logger.debug(f"Searching static players for '{player_name}'")
    player_list = players.find_players_by_full_name(player_name)
    if not player_list:
        logger.warning(f"Player '{player_name}' not found in static data.")
        return None, None
    player_data = player_list[0]
    player_id = player_data['id']
    player_actual_name = player_data['full_name']
    logger.info(f"Found player: {player_actual_name} (ID: {player_id})")
    return player_id, player_actual_name

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

def get_player_headshot_url(player_id: int) -> str:
    """
    Constructs the URL for a player's headshot based on their ID.
    Args:
        player_id (int): The NBA player ID.
    Returns:
        str: The URL to the player's headshot PNG.
    """
    if not isinstance(player_id, int) or player_id <= 0:
        logger.warning(f"Invalid player_id provided for headshot: {player_id}")
        # Return a placeholder or default image URL in the future
        
    headshot_url = f"{HEADSHOT_BASE_URL}{player_id}.png"
    logger.info(f"Generated headshot URL for player ID {player_id}: {headshot_url}")
    return headshot_url

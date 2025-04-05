import logging
import pandas as pd
from nba_api.stats.static import players
from nba_api.stats.endpoints import commonplayerinfo, playergamelog, playercareerstats
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, PerMode36
import re
import json
from .utils import _process_dataframe # Import the moved function
from config import DEFAULT_TIMEOUT # Use absolute import from project root

logger = logging.getLogger(__name__)

# DEFAULT_TIMEOUT moved to config.py

# --- Helper Functions ---
def _validate_season_format(season: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}$", season))

def _find_player_id(player_name: str) -> tuple[int | None, str | None]:
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

# _process_dataframe function moved to api_tools/utils.py

# --- Player Tool Logic Functions (Returning Dictionaries/Lists) ---

def fetch_player_info_logic(player_name: str) -> dict:
    """Core logic to fetch player info."""
    # ... (fetch_player_info_logic remains the same) ...
    logger.info(f"Executing fetch_player_info_logic for: '{player_name}'")
    if not player_name or not player_name.strip():
        return {"error": "Player name cannot be empty."}
    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return {"error": f"Player '{player_name}' not found."}

        logger.debug(f"Fetching commonplayerinfo for player ID: {player_id}")
        try:
            info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=DEFAULT_TIMEOUT)
            logger.debug(f"commonplayerinfo API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api commonplayerinfo failed for ID {player_id}: {api_error}", exc_info=True)
            return {"error": f"API error fetching details for {player_actual_name}: {str(api_error)}"}

        player_info_dict = _process_dataframe(info_endpoint.common_player_info.get_data_frame(), single_row=True)
        headline_stats_dict = _process_dataframe(info_endpoint.player_headline_stats.get_data_frame(), single_row=True)

        if player_info_dict is None or headline_stats_dict is None:
             logger.error(f"DataFrame processing failed for {player_actual_name}.")
             return {"error": f"Failed to process data from API for {player_actual_name}."}

        result = {"player_info": player_info_dict or {}, "headline_stats": headline_stats_dict or {}}
        logger.info(f"fetch_player_info_logic completed for '{player_actual_name}'")
        return result
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_info_logic for '{player_name}': {e}", exc_info=True)
        return {"error": f"Unexpected error processing request for {player_name}: {str(e)}"}


def fetch_player_gamelog_logic(player_name: str, season: str, season_type: str = SeasonTypeAllStar.regular) -> dict:
    """Core logic to fetch player game logs."""
    # ... (fetch_player_gamelog_logic remains the same) ...
    logger.info(f"Executing fetch_player_gamelog_logic for: '{player_name}', Season: {season}, Type: {season_type}")
    if not player_name or not player_name.strip(): return {"error": "Player name cannot be empty."}
    if not season or not _validate_season_format(season): return {"error": f"Invalid season format: {season}. Expected YYYY-YY."}

    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None: return {"error": f"Player '{player_name}' not found."}

        logger.debug(f"Fetching playergamelog for ID: {player_id}, Season: {season}, Type: {season_type}")
        try:
            gamelog_endpoint = playergamelog.PlayerGameLog(
                player_id=player_id, season=season, season_type_all_star=season_type, timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"playergamelog API call successful for ID: {player_id}, Season: {season}")
        except Exception as api_error:
            logger.error(f"nba_api playergamelog failed for ID {player_id}, Season {season}: {api_error}", exc_info=True)
            return {"error": f"API error fetching game log for {player_actual_name} ({season}): {str(api_error)}"}

        gamelog_list = _process_dataframe(gamelog_endpoint.get_data_frames()[0], single_row=False)

        if gamelog_list is None:
            logger.error(f"DataFrame processing failed for gamelog of {player_actual_name} ({season}).")
            return {"error": f"Failed to process game log data from API for {player_actual_name} ({season})."}

        result = {"player_name": player_actual_name, "player_id": player_id, "season": season, "season_type": season_type, "gamelog": gamelog_list}
        logger.info(f"fetch_player_gamelog_logic completed for '{player_actual_name}', Season: {season}")
        return result
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_gamelog_logic for '{player_name}', Season {season}: {e}", exc_info=True)
        return {"error": f"Unexpected error processing game log request for {player_name} ({season}): {str(e)}"}


# Updated function signature and call to use per_mode36
def fetch_player_career_stats_logic(player_name: str, per_mode36: str = PerMode36.per_game) -> dict: # Use per_mode36
    """Core logic to fetch player career stats."""
    logger.info(f"Executing fetch_player_career_stats_logic for: '{player_name}', PerMode36: {per_mode36}")
    if not player_name or not player_name.strip(): return {"error": "Player name cannot be empty."}

    # Validate per_mode36 but don't pass it to init
    valid_per_modes = [getattr(PerMode36, attr) for attr in dir(PerMode36) if not attr.startswith('_') and isinstance(getattr(PerMode36, attr), str)]
    original_request_mode = per_mode36 # Store original request
    if per_mode36 not in valid_per_modes:
        logger.warning(f"Invalid per_mode36 '{per_mode36}'. Using default '{PerMode36.per_game}'. Valid options: {valid_per_modes}")
        per_mode36 = PerMode36.per_game # Use default

    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None: return {"error": f"Player '{player_name}' not found."}

        # NOTE: Removing per_mode/PerMode from init as it causes TypeErrors.
        # The nba_api library might implicitly return different dataframes based on
        # how they are accessed, or require a different method to set the mode.
        # This needs further investigation in the nba_api library itself.
        # For now, we fetch the default dataframes available after initialization.
        logger.debug(f"Fetching playercareerstats for ID: {player_id} (Ignoring PerMode in API call)")
        try:
            career_endpoint = playercareerstats.PlayerCareerStats(
                player_id=player_id, timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"playercareerstats API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api playercareerstats failed for ID {player_id}: {api_error}", exc_info=True)
            return {"error": f"API error fetching career stats for {player_actual_name}: {str(api_error)}"}

        # Fetch default dataframes
        # TODO: Investigate how to fetch dataframes corresponding to the requested per_mode36
        season_totals = _process_dataframe(career_endpoint.season_totals_regular_season.get_data_frame(), single_row=False)
        career_totals = _process_dataframe(career_endpoint.career_totals_regular_season.get_data_frame(), single_row=True)

        if season_totals is None or career_totals is None:
            logger.error(f"DataFrame processing failed for career stats of {player_actual_name}.")
            return {"error": f"Failed to process career stats data from API for {player_actual_name}."}

        result = {
            "player_name": player_actual_name, "player_id": player_id,
            "per_mode_requested": original_request_mode, # Keep original requested mode
            "data_retrieved_mode": "Default (PerMode parameter ignored)", # Indicate default was fetched due to API issues
            "season_totals_regular_season": season_totals or [],
            "career_totals_regular_season": career_totals or {}
        }
        logger.info(f"fetch_player_career_stats_logic completed for '{player_actual_name}'")
        return result
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_career_stats_logic for '{player_name}': {e}", exc_info=True)
        return {"error": f"Unexpected error processing career stats request for {player_name}: {str(e)}"}
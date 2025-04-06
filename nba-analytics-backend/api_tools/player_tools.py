# api_tools/player_tools.py - RESOLVED
import logging
import pandas as pd
from nba_api.stats.static import players
from nba_api.stats.endpoints import commonplayerinfo, playergamelog, playercareerstats
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, PerMode36
import re
import json
from config import DEFAULT_TIMEOUT, HEADSHOT_BASE_URL, DEFAULT_PLAYER_SEARCH_LIMIT, MIN_PLAYER_SEARCH_LENGTH # Import from config
from .utils import _process_dataframe, _validate_season_format # Import from utils

logger = logging.getLogger(__name__)

# --- Helper Functions ---

# Removed: Use utils version
# def _validate_season_format(season: str) -> bool:
#     return bool(re.match(r"^\d{4}-\d{2}$", season))

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

# Removed: Use utils version
# def _process_dataframe(df: pd.DataFrame | None, single_row: bool = True) -> list | dict | None:
#     # ... implementation ...

# --- Player Tool Logic Functions (Returning JSON Strings) ---

def fetch_player_info_logic(player_name: str) -> str:
    """Core logic to fetch player info."""
    logger.info(f"Executing fetch_player_info_logic for: '{player_name}'")
    if not player_name or not player_name.strip():
        return json.dumps({"error": "Player name cannot be empty."})
    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return json.dumps({"error": f"Player '{player_name}' not found."})

        logger.debug(f"Fetching commonplayerinfo for player ID: {player_id}")
        try:
            info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=DEFAULT_TIMEOUT)
            logger.debug(f"commonplayerinfo API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api commonplayerinfo failed for ID {player_id}: {api_error}", exc_info=True)
            return json.dumps({"error": f"API error fetching details for {player_actual_name}: {str(api_error)}"})

        player_info_dict = _process_dataframe(info_endpoint.common_player_info.get_data_frame(), single_row=True)
        headline_stats_dict = _process_dataframe(info_endpoint.player_headline_stats.get_data_frame(), single_row=True)

        if player_info_dict is None or headline_stats_dict is None:
             logger.error(f"DataFrame processing failed for {player_actual_name}.")
             return json.dumps({"error": f"Failed to process data from API for {player_actual_name}."})

        result = {"player_info": player_info_dict or {}, "headline_stats": headline_stats_dict or {}}
        logger.info(f"fetch_player_info_logic completed for '{player_actual_name}'")
        return json.dumps(result, default=str)
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_info_logic for '{player_name}': {e}", exc_info=True)
        return json.dumps({"error": f"Unexpected error processing request for {player_name}: {str(e)}"})


def fetch_player_gamelog_logic(player_name: str, season: str, season_type: str = SeasonTypeAllStar.regular) -> str:
    """Core logic to fetch player game logs."""
    logger.info(f"Executing fetch_player_gamelog_logic for: '{player_name}', Season: {season}, Type: {season_type}")
    if not player_name or not player_name.strip(): return json.dumps({"error": "Player name cannot be empty."})
    if not season or not _validate_season_format(season): return json.dumps({"error": f"Invalid season format: {season}. Expected YYYY-YY."})

    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None: return json.dumps({"error": f"Player '{player_name}' not found."})

        logger.debug(f"Fetching playergamelog for ID: {player_id}, Season: {season}, Type: {season_type}")
        try:
            gamelog_endpoint = playergamelog.PlayerGameLog(
                player_id=player_id, season=season, season_type_all_star=season_type, timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"playergamelog API call successful for ID: {player_id}, Season: {season}")
        except Exception as api_error:
            logger.error(f"nba_api playergamelog failed for ID {player_id}, Season {season}: {api_error}", exc_info=True)
            return json.dumps({"error": f"API error fetching game log for {player_actual_name} ({season}): {str(api_error)}"})

        gamelog_list = _process_dataframe(gamelog_endpoint.get_data_frames()[0], single_row=False)

        if gamelog_list is None:
            logger.error(f"DataFrame processing failed for gamelog of {player_actual_name} ({season}).")
            return json.dumps({"error": f"Failed to process game log data from API for {player_actual_name} ({season})."})

        result = {"player_name": player_actual_name, "player_id": player_id, "season": season, "season_type": season_type, "gamelog": gamelog_list}
        logger.info(f"fetch_player_gamelog_logic completed for '{player_actual_name}', Season: {season}")
        return json.dumps(result, default=str)
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_gamelog_logic for '{player_name}', Season {season}: {e}", exc_info=True)
        return json.dumps({"error": f"Unexpected error processing game log request for {player_name} ({season}): {str(e)}"})


def fetch_player_career_stats_logic(player_name: str, per_mode36: str = PerMode36.per_game) -> str: # Use per_mode36
    """Core logic to fetch player career stats."""
    logger.info(f"Executing fetch_player_career_stats_logic for: '{player_name}', PerMode36: {per_mode36}")
    if not player_name or not player_name.strip(): return json.dumps({"error": "Player name cannot be empty."})

    valid_per_modes = [getattr(PerMode36, attr) for attr in dir(PerMode36) if not attr.startswith('_') and isinstance(getattr(PerMode36, attr), str)]
    original_request_mode = per_mode36 # Store original request
    if per_mode36 not in valid_per_modes:
        logger.warning(f"Invalid per_mode36 '{per_mode36}'. Using default '{PerMode36.per_game}'. Valid options: {valid_per_modes}")
        per_mode36 = PerMode36.per_game # Use default

    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None: return json.dumps({"error": f"Player '{player_name}' not found."})

        # TODO: The 'per_mode36' parameter is currently ignored in the API call below
        #       due to suspected issues with the nba_api library handling it correctly
        #       for playercareerstats. It always fetches the default (PerGame).
        #       Needs investigation if other PerModes are required.
        logger.debug(f"Fetching playercareerstats for ID: {player_id} (Ignoring PerMode in API call)")
        try:
            career_endpoint = playercareerstats.PlayerCareerStats(
                player_id=player_id, timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"playercareerstats API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api playercareerstats failed for ID {player_id}: {api_error}", exc_info=True)
            return json.dumps({"error": f"API error fetching career stats for {player_actual_name}: {str(api_error)}"})

        season_totals = _process_dataframe(career_endpoint.season_totals_regular_season.get_data_frame(), single_row=False)
        career_totals = _process_dataframe(career_endpoint.career_totals_regular_season.get_data_frame(), single_row=True)

        if season_totals is None or career_totals is None:
            logger.error(f"DataFrame processing failed for career stats of {player_actual_name}.")
            return json.dumps({"error": f"Failed to process career stats data from API for {player_actual_name}."})

        result = {
            "player_name": player_actual_name, "player_id": player_id,
            "per_mode_requested": original_request_mode,
            "data_retrieved_mode": "Default (PerMode parameter ignored)",
            "season_totals_regular_season": season_totals or [],
            "career_totals_regular_season": career_totals or {}
        }
        logger.info(f"fetch_player_career_stats_logic completed for '{player_actual_name}'")
        return json.dumps(result, default=str)
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_career_stats_logic for '{player_name}': {e}", exc_info=True)
        return json.dumps({"error": f"Unexpected error processing career stats request for {player_name}: {str(e)}"})


# --- Player Headshot Function ---

def get_player_headshot_url(player_id: int) -> str:
    """
    Constructs the URL for a player's headshot based on their ID.
    Args:
        player_id (int): The NBA player ID.
    Returns:
        str: The URL to the player's headshot PNG.
    """
    # Basic validation
    if not isinstance(player_id, int) or player_id <= 0:
        logger.warning(f"Invalid player_id provided for headshot: {player_id}")
        # Returning a placeholder or raising an error might be better,
        # but for now, just return the formatted string which will likely 404.
        # Consider adding more robust validation if needed (e.g., check if player ID exists).

    base_url = HEADSHOT_BASE_URL # Use config value
    headshot_url = f"{base_url}{player_id}.png"
    logger.info(f"Generated headshot URL for player ID {player_id}: {headshot_url}")
    return headshot_url


# --- Player Search Function ---

# Cache for player list to avoid repeated calls to get_players()
_player_list_cache = None

def _get_cached_player_list() -> list[dict]:
    """Gets the full player list, caching it after the first call."""
    global _player_list_cache
    if _player_list_cache is None:
        logger.info("Fetching and caching full player list...")
        try:
            _player_list_cache = players.get_players()
            logger.info(f"Successfully cached {len(_player_list_cache)} players.")
        except Exception as e:
            logger.error(f"Failed to fetch and cache player list: {e}", exc_info=True)
            _player_list_cache = [] # Set to empty list on error to avoid retrying constantly
    return _player_list_cache

def find_players_by_name_fragment(name_fragment: str, limit: int = DEFAULT_PLAYER_SEARCH_LIMIT) -> list[dict]:
    """
    Finds players whose full name contains the given fragment (case-insensitive).
    Args:
        name_fragment (str): The partial name to search for.
        limit (int): The maximum number of results to return.
    Returns:
        list[dict]: A list of matching players [{'id': player_id, 'full_name': player_name}, ...].
    """
    if not name_fragment or len(name_fragment) < MIN_PLAYER_SEARCH_LENGTH: # Use config value
        return []

    all_players = _get_cached_player_list()
    if not all_players: # Handle cache fetch error
        return []

    name_fragment_lower = name_fragment.lower()
    matching_players = []

    try:
        for player in all_players:
            if name_fragment_lower in player['full_name'].lower():
                matching_players.append({
                    'id': player['id'],
                    'full_name': player['full_name']
                })
                if len(matching_players) >= limit:
                    break # Stop once limit is reached
    except Exception as e:
        logger.error(f"Error filtering player list for fragment '{name_fragment}': {e}", exc_info=True)
        return [] # Return empty on error

    logger.info(f"Found {len(matching_players)} players matching fragment '{name_fragment}' (limit {limit}).")
    return matching_players

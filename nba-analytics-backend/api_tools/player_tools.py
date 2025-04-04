import logging
import pandas as pd
from nba_api.stats.static import players
from nba_api.stats.endpoints import commonplayerinfo, playergamelog, playercareerstats
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed
import re
import json # Import json

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10

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

def _process_dataframe(df: pd.DataFrame | None, single_row: bool = True) -> list | dict | None:
    if df is None or df.empty:
        return {} if single_row else []
    try:
        records = df.to_dict(orient='records')
        processed_records = [
            {k: (v if pd.notna(v) else None) for k, v in row.items()}
            for row in records
        ]
        if single_row:
            return processed_records[0] if processed_records else {}
        else:
            return processed_records
    except Exception as e:
        logger.error(f"Error processing DataFrame: {e}", exc_info=True)
        return None

# --- Player Tool Logic Functions (Returning JSON Strings) ---

def fetch_player_info_logic(player_name: str) -> str: # Return str (JSON)
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
        return json.dumps(result, default=str) # Return JSON string
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_info_logic for '{player_name}': {e}", exc_info=True)
        return json.dumps({"error": f"Unexpected error processing request for {player_name}: {str(e)}"})

def fetch_player_gamelog_logic(player_name: str, season: str, season_type: str = SeasonTypeAllStar.regular) -> str: # Return str (JSON)
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
        return json.dumps(result, default=str) # Return JSON string
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_gamelog_logic for '{player_name}', Season {season}: {e}", exc_info=True)
        return json.dumps({"error": f"Unexpected error processing game log request for {player_name} ({season}): {str(e)}"})

def fetch_player_career_stats_logic(player_name: str, per_mode: str = PerModeDetailed.per_game) -> str: # Return str (JSON)
    """Core logic to fetch player career stats."""
    logger.info(f"Executing fetch_player_career_stats_logic for: '{player_name}', PerMode: {per_mode}")
    if not player_name or not player_name.strip(): return json.dumps({"error": "Player name cannot be empty."})

    # Corrected PerMode Validation: Check against actual values from the class
    valid_per_modes = [getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)]
    if per_mode not in valid_per_modes:
        logger.warning(f"Invalid per_mode '{per_mode}'. Using default '{PerModeDetailed.per_game}'. Valid options: {valid_per_modes}")
        # Use default instead of returning error immediately
        per_mode = PerModeDetailed.per_game
        # return json.dumps({"error": f"Invalid per_mode '{per_mode}'. Valid options are: {', '.join(valid_per_modes)}"}) # Removed premature error return

    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None: return json.dumps({"error": f"Player '{player_name}' not found."})

        logger.debug(f"Fetching playercareerstats for ID: {player_id}, PerMode: {per_mode}")
        try:
            # Corrected parameter name again (likely just 'per_mode')
            career_endpoint = playercareerstats.PlayerCareerStats(
                player_id=player_id, per_mode=per_mode, timeout=DEFAULT_TIMEOUT
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
            "player_name": player_actual_name, "player_id": player_id, "per_mode": per_mode,
            "season_totals_regular_season": season_totals or [],
            "career_totals_regular_season": career_totals or {}
        }
        logger.info(f"fetch_player_career_stats_logic completed for '{player_actual_name}'")
        return json.dumps(result, default=str) # Return JSON string
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_career_stats_logic for '{player_name}': {e}", exc_info=True)
        return json.dumps({"error": f"Unexpected error processing career stats request for {player_name}: {str(e)}"})
"""
Handles fetching and processing player passing statistics, including passes made and received.
Requires an initial lookup for the player's current team_id via commonplayerinfo.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
from functools import lru_cache
from typing import Set, Dict, Union, Tuple, Optional

import pandas as pd
from nba_api.stats.endpoints import commonplayerinfo, playerdashptpass
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)
from backend.utils.validation import _validate_season_format

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
PLAYER_PASSING_CACHE_SIZE = 256

_VALID_PASSING_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_VALID_PASSING_PER_MODES: Set[str] = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}

# --- Cache Directory Setup ---
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
PLAYER_PASSING_CSV_DIR = os.path.join(CSV_CACHE_DIR, "player_passing")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(PLAYER_PASSING_CSV_DIR, exist_ok=True)

# --- Helper Functions for CSV Caching ---
def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves a DataFrame to a CSV file.

    Args:
        df: DataFrame to save
        file_path: Path to save the CSV file
    """
    try:
        df.to_csv(file_path, index=False)
        logger.info(f"Saved DataFrame to CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)

def _get_csv_path_for_player_passing(
    player_name: str,
    season: str,
    season_type: str,
    per_mode: str,
    data_type: str
) -> str:
    """
    Generates a file path for saving player passing DataFrame as CSV.

    Args:
        player_name: The player's name
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        per_mode: The per mode (e.g., 'PerGame', 'Totals')
        data_type: The type of data ('passes_made' or 'passes_received')

    Returns:
        Path to the CSV file
    """
    # Clean player name and data type for filename
    clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()
    clean_season_type = season_type.replace(" ", "_").lower()
    clean_per_mode = per_mode.replace(" ", "_").lower()

    filename = f"{clean_player_name}_{season}_{clean_season_type}_{clean_per_mode}_{data_type}.csv"
    return os.path.join(PLAYER_PASSING_CSV_DIR, filename)

def fetch_player_passing_stats_logic(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player passing statistics (passes made and received) for a given season.
    This function first determines the player's team_id for the given season via commonplayerinfo,
    then uses that team_id to fetch passing stats from playerdashptpass.

    Provides DataFrame output capabilities.

    Args:
        player_name: The name or ID of the player.
        season: NBA season in YYYY-YY format. Defaults to current season.
        season_type: Type of season. Defaults to Regular Season.
        per_mode: Statistical mode (PerModeSimple). Defaults to PerGame.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: A JSON string containing player passing stats or an error message.
                 Successful response structure:
                 {
                     "player_name": "Player Name",
                     "player_id": 12345,
                     "parameters": {"season": "YYYY-YY", "season_type": "Season Type", "per_mode": "PerModeValue"},
                     "passes_made": [ { ... stats ... } ],
                     "passes_received": [ { ... stats ... } ]
                 }
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_player_passing_stats_logic for player: {player_name}, Season: {season}, PerMode: {per_mode}, return_dataframe={return_dataframe}")

    if not player_name or not player_name.strip():
        error_response = format_response(error=Errors.PLAYER_NAME_EMPTY)
        if return_dataframe:
            return error_response, {}
        return error_response

    if not season or not _validate_season_format(season):
        error_response = format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
        if return_dataframe:
            return error_response, {}
        return error_response

    if season_type not in _VALID_PASSING_SEASON_TYPES:
        error_response = format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_PASSING_SEASON_TYPES)[:5])))
        if return_dataframe:
            return error_response, {}
        return error_response

    if per_mode not in _VALID_PASSING_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_PASSING_PER_MODES)[:3]))
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching commonplayerinfo for team ID lookup (Player: {player_actual_name}, ID: {player_id})")

        # Get player info to find team ID
        player_info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
        info_dict = _process_dataframe(player_info_endpoint.common_player_info.get_data_frame(), single_row=True)

        if info_dict is None or "TEAM_ID" not in info_dict:
            logger.error(f"Could not retrieve team ID for player {player_actual_name} (ID: {player_id})")
            error_response = format_response(error=Errors.TEAM_ID_NOT_FOUND.format(player_name=player_actual_name))
            if return_dataframe:
                return error_response, {}
            return error_response

        team_id = info_dict["TEAM_ID"]
        logger.debug(f"Found Team ID {team_id} for player {player_actual_name}")

        # Call the API
        logger.debug(f"Fetching playerdashptpass for Player ID: {player_id}, Team ID: {team_id}, Season: {season}")
        pass_stats_endpoint = playerdashptpass.PlayerDashPtPass(
            player_id=player_id, team_id=team_id, season=season,
            season_type_all_star=season_type, per_mode_simple=per_mode,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"playerdashptpass API call successful for {player_actual_name}")

        # Get DataFrames from the API response
        passes_made_df = pass_stats_endpoint.passes_made.get_data_frame()
        passes_received_df = pass_stats_endpoint.passes_received.get_data_frame()

        # Process DataFrames for JSON response
        passes_made_list = _process_dataframe(passes_made_df, single_row=False)
        passes_received_list = _process_dataframe(passes_received_df, single_row=False)

        # Store DataFrames if requested
        dataframes = {}

        if return_dataframe:
            dataframes["passes_made"] = passes_made_df
            dataframes["passes_received"] = passes_received_df

            # Save DataFrames to CSV if not empty
            if not passes_made_df.empty:
                csv_path = _get_csv_path_for_player_passing(
                    player_actual_name, season, season_type, per_mode, "passes_made"
                )
                _save_dataframe_to_csv(passes_made_df, csv_path)

            if not passes_received_df.empty:
                csv_path = _get_csv_path_for_player_passing(
                    player_actual_name, season, season_type, per_mode, "passes_received"
                )
                _save_dataframe_to_csv(passes_received_df, csv_path)

        if passes_made_list is None or passes_received_list is None:
            if passes_made_df.empty and passes_received_df.empty:
                logger.warning(f"No passing stats found for player {player_actual_name} with given filters.")

                response_data = {
                    "player_name": player_actual_name, "player_id": player_id,
                    "parameters": {"season": season, "season_type": season_type, "per_mode": per_mode},
                    "passes_made": [], "passes_received": []
                }

                if return_dataframe:
                    return format_response(response_data), dataframes
                return format_response(response_data)
            else:
                logger.error(f"DataFrame processing failed for passing stats of {player_actual_name} (Season: {season}).")
                error_msg = Errors.PLAYER_PASSING_PROCESSING.format(identifier=player_actual_name, season=season)
                error_response = format_response(error=error_msg)
                if return_dataframe:
                    return error_response, dataframes
                return error_response

        # Create response data
        result = {
            "player_name": player_actual_name, "player_id": player_id,
            "parameters": {"season": season, "season_type": season_type, "per_mode": per_mode},
            "passes_made": passes_made_list or [],
            "passes_received": passes_received_list or []
        }

        logger.info(f"fetch_player_passing_stats_logic completed for {player_actual_name}")

        if return_dataframe:
            return format_response(result), dataframes
        return format_response(result)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_passing_stats_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_passing_stats_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except Exception as e:
        logger.error(f"Error fetching passing stats for {player_name} (Season: {season}): {str(e)}", exc_info=True)
        error_msg = Errors.PLAYER_PASSING_UNEXPECTED.format(identifier=player_name, season=season, error=str(e))
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response
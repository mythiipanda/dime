"""
Handles fetching and processing player rebounding statistics,
categorized by overall, shot type, contest level, shot distance, and rebound distance.
Requires an initial lookup for the player's current team_id via commonplayerinfo.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
from functools import lru_cache
from typing import Set, Dict, Union, Tuple, Optional

import pandas as pd
from nba_api.stats.endpoints import commonplayerinfo, playerdashptreb
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
PLAYER_REBOUNDING_CACHE_SIZE = 256

_VALID_REB_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_VALID_REB_PER_MODES: Set[str] = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}

# --- Cache Directory Setup ---
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
PLAYER_REBOUNDING_CSV_DIR = os.path.join(CSV_CACHE_DIR, "player_rebounding")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(PLAYER_REBOUNDING_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_player_rebounding(
    player_name: str,
    season: str,
    season_type: str,
    per_mode: str,
    data_type: str
) -> str:
    """
    Generates a file path for saving player rebounding DataFrame as CSV.

    Args:
        player_name: The player's name
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        per_mode: The per mode (e.g., 'PerGame', 'Totals')
        data_type: The type of data ('overall', 'shot_type', 'contest', 'shot_distance', 'rebound_distance')

    Returns:
        Path to the CSV file
    """
    # Clean player name and data type for filename
    clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()
    clean_season_type = season_type.replace(" ", "_").lower()
    clean_per_mode = per_mode.replace(" ", "_").lower()

    filename = f"{clean_player_name}_{season}_{clean_season_type}_{clean_per_mode}_{data_type}.csv"
    return os.path.join(PLAYER_REBOUNDING_CSV_DIR, filename)

def fetch_player_rebounding_stats_logic(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player rebounding statistics, broken down by various categories.
    This function first determines the player's team_id for the given season,
    then uses that to fetch detailed rebounding stats.

    Provides DataFrame output capabilities.

    Args:
        player_name: The name or ID of the player.
        season: NBA season in YYYY-YY format. Defaults to current season.
        season_type: Type of season. Defaults to Regular Season.
        per_mode: Statistical mode (PerModeSimple). Defaults to PerGame.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: A JSON string containing player rebounding stats or an error message.
                 Successful response structure:
                 {
                     "player_name": "Player Name",
                     "player_id": 12345,
                     "parameters": {"season": "YYYY-YY", ...},
                     "overall": { ... overall rebounding stats ... },
                     "by_shot_type": [ { ... stats ... } ],
                     "by_contest": [ { ... stats ... } ],
                     "by_shot_distance": [ { ... stats ... } ],
                     "by_rebound_distance": [ { ... stats ... } ]
                 }
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_player_rebounding_stats_logic for player: {player_name}, Season: {season}, PerMode: {per_mode}, return_dataframe={return_dataframe}")

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

    if season_type not in _VALID_REB_SEASON_TYPES:
        error_response = format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_REB_SEASON_TYPES)[:5])))
        if return_dataframe:
            return error_response, {}
        return error_response

    if per_mode not in _VALID_REB_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_REB_PER_MODES)[:3]))
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
        logger.debug(f"Fetching playerdashptreb for Player ID: {player_id}, Team ID: {team_id}, Season: {season}")
        reb_stats_endpoint = playerdashptreb.PlayerDashPtReb(
            player_id=player_id, team_id=team_id, season=season,
            season_type_all_star=season_type, per_mode_simple=per_mode,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"playerdashptreb API call successful for {player_actual_name}")

        # Get DataFrames from the API response
        overall_df = reb_stats_endpoint.overall_rebounding.get_data_frame()
        shot_type_df = reb_stats_endpoint.shot_type_rebounding.get_data_frame()
        contested_df = reb_stats_endpoint.num_contested_rebounding.get_data_frame()
        distances_df = reb_stats_endpoint.shot_distance_rebounding.get_data_frame()
        reb_dist_df = reb_stats_endpoint.reb_distance_rebounding.get_data_frame()

        # Store DataFrames if requested
        dataframes = {}

        if return_dataframe:
            dataframes["overall"] = overall_df
            dataframes["by_shot_type"] = shot_type_df
            dataframes["by_contest"] = contested_df
            dataframes["by_shot_distance"] = distances_df
            dataframes["by_rebound_distance"] = reb_dist_df

            # Save DataFrames to CSV if not empty
            if not overall_df.empty:
                csv_path = _get_csv_path_for_player_rebounding(
                    player_actual_name, season, season_type, per_mode, "overall"
                )
                _save_dataframe_to_csv(overall_df, csv_path)

            if not shot_type_df.empty:
                csv_path = _get_csv_path_for_player_rebounding(
                    player_actual_name, season, season_type, per_mode, "shot_type"
                )
                _save_dataframe_to_csv(shot_type_df, csv_path)

            if not contested_df.empty:
                csv_path = _get_csv_path_for_player_rebounding(
                    player_actual_name, season, season_type, per_mode, "contest"
                )
                _save_dataframe_to_csv(contested_df, csv_path)

            if not distances_df.empty:
                csv_path = _get_csv_path_for_player_rebounding(
                    player_actual_name, season, season_type, per_mode, "shot_distance"
                )
                _save_dataframe_to_csv(distances_df, csv_path)

            if not reb_dist_df.empty:
                csv_path = _get_csv_path_for_player_rebounding(
                    player_actual_name, season, season_type, per_mode, "rebound_distance"
                )
                _save_dataframe_to_csv(reb_dist_df, csv_path)

        # Process DataFrames for JSON response
        overall_data = _process_dataframe(overall_df, single_row=True)
        shot_type_data = _process_dataframe(shot_type_df, single_row=False)
        contested_data = _process_dataframe(contested_df, single_row=False)
        distances_data = _process_dataframe(distances_df, single_row=False)
        reb_dist_data = _process_dataframe(reb_dist_df, single_row=False)

        if overall_data is None or \
           shot_type_data is None or \
           contested_data is None or \
           distances_data is None or \
           reb_dist_data is None:
            logger.error(f"DataFrame processing failed for rebounding stats of {player_actual_name} (Season: {season}). At least one DF processing returned None.")
            error_msg = Errors.PLAYER_REBOUNDING_PROCESSING.format(identifier=player_actual_name, season=season) # Ensure season is included
            error_response = format_response(error=error_msg)
            if return_dataframe:
                return error_response, dataframes
            return error_response

        if overall_df.empty and \
           shot_type_df.empty and \
           contested_df.empty and \
           distances_df.empty and \
           reb_dist_df.empty:
            logger.warning(f"No rebounding stats found for player {player_actual_name} with given filters (all original DFs were empty).")

            response_data = {
                "player_name": player_actual_name, "player_id": player_id,
                "parameters": {"season": season, "season_type": season_type, "per_mode": per_mode},
                "overall": {}, "by_shot_type": [], "by_contest": [],
                "by_shot_distance": [], "by_rebound_distance": []
            }

            if return_dataframe:
                return format_response(response_data), dataframes
            return format_response(response_data)

        # Create response data
        result = {
            "player_name": player_actual_name, "player_id": player_id,
            "parameters": {"season": season, "season_type": season_type, "per_mode": per_mode},
            "overall": overall_data or {}, "by_shot_type": shot_type_data or [],
            "by_contest": contested_data or [], "by_shot_distance": distances_data or [],
            "by_rebound_distance": reb_dist_data or []
        }

        logger.info(f"fetch_player_rebounding_stats_logic completed for {player_actual_name}")

        if return_dataframe:
            return format_response(result), dataframes
        return format_response(result)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_rebounding_stats_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_rebounding_stats_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except Exception as e:
        logger.error(f"Error fetching rebounding stats for {player_name} (Season: {season}): {str(e)}", exc_info=True)
        error_msg = Errors.PLAYER_REBOUNDING_UNEXPECTED.format(identifier=player_name, season=season, error=str(e))
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response
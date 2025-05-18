"""
Handles fetching and processing player career statistics and awards information.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
from functools import lru_cache
from typing import Dict, Any, Union, Tuple, Optional, List
import pandas as pd
import json

from nba_api.stats.endpoints import playercareerstats, playerawards
from nba_api.stats.library.parameters import PerModeDetailed, PerMode36
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)

logger = logging.getLogger(__name__)

# Cache sizes
PLAYER_CAREER_STATS_CACHE_SIZE = 256
PLAYER_AWARDS_CACHE_SIZE = 256

# Module-level constant for valid PerMode values for career stats
_VALID_PER_MODES_CAREER = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
_VALID_PER_MODES_CAREER.update({getattr(PerMode36, attr) for attr in dir(PerMode36) if not attr.startswith('_') and isinstance(getattr(PerMode36, attr), str)})

# --- Cache Directory Setup ---
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
PLAYER_CAREER_CSV_DIR = os.path.join(CSV_CACHE_DIR, "player_career")
PLAYER_AWARDS_CSV_DIR = os.path.join(CSV_CACHE_DIR, "player_awards")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(PLAYER_CAREER_CSV_DIR, exist_ok=True)
os.makedirs(PLAYER_AWARDS_CSV_DIR, exist_ok=True)

# --- Helper Functions ---
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

def _get_csv_path_for_career_stats(player_name: str, per_mode: str, data_type: str) -> str:
    """
    Generates a file path for saving a player career stats DataFrame as CSV.

    Args:
        player_name: The player's name
        per_mode: The per mode (e.g., 'PerGame', 'Totals')
        data_type: The type of data (e.g., 'season_regular', 'career_regular', 'season_post', 'career_post')

    Returns:
        Path to the CSV file
    """
    # Clean player name for filename
    clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()

    # Clean per mode for filename
    clean_per_mode = per_mode.lower()

    filename = f"{clean_player_name}_{clean_per_mode}_{data_type}.csv"
    return os.path.join(PLAYER_CAREER_CSV_DIR, filename)

def _get_csv_path_for_awards(player_name: str) -> str:
    """
    Generates a file path for saving a player awards DataFrame as CSV.

    Args:
        player_name: The player's name

    Returns:
        Path to the CSV file
    """
    # Clean player name for filename
    clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()

    filename = f"{clean_player_name}_awards.csv"
    return os.path.join(PLAYER_AWARDS_CSV_DIR, filename)

def fetch_player_career_stats_logic(
    player_name: str,
    per_mode: str = PerModeDetailed.per_game,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player career statistics including regular season and postseason totals.

    Provides DataFrame output capabilities.

    Args:
        player_name: The name or ID of the player.
        per_mode: The statistical mode (e.g., "PerGame", "Totals", "Per36").
                 Defaults to "PerGame".
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: A JSON string containing player career statistics, or an error message.
                 Successful response structure:
                 {
                     "player_name": "Player Name",
                     "player_id": 12345,
                     "per_mode_requested": "PerModeValue",
                     "data_retrieved_mode": "PerModeValue",
                     "season_totals_regular_season": [ { ... stats ... } ],
                     "career_totals_regular_season": { ... stats ... },
                     "season_totals_post_season": [ { ... stats ... } ],
                     "career_totals_post_season": { ... stats ... }
                 }
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_player_career_stats_logic for: '{player_name}', Requested PerMode: {per_mode}, return_dataframe={return_dataframe}")

    if per_mode not in _VALID_PER_MODES_CAREER:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_PER_MODES_CAREER)[:5]))
        logger.warning(error_msg)
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching playercareerstats for ID: {player_id} (PerMode '{per_mode}' requested)")

        try:
            career_endpoint = playercareerstats.PlayerCareerStats(player_id=player_id, per_mode36=per_mode, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
            logger.debug(f"playercareerstats API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api playercareerstats failed for ID {player_id}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_CAREER_STATS_API.format(identifier=player_actual_name, error=str(api_error))
            error_response = format_response(error=error_msg)
            if return_dataframe:
                return error_response, {}
            return error_response

        # Get DataFrames from the API response
        season_totals_rs_df = career_endpoint.season_totals_regular_season.get_data_frame()
        career_totals_rs_df = career_endpoint.career_totals_regular_season.get_data_frame()
        season_totals_ps_df = career_endpoint.season_totals_post_season.get_data_frame()
        career_totals_ps_df = career_endpoint.career_totals_post_season.get_data_frame()

        # Define common columns for season totals
        season_totals_cols = [
            'SEASON_ID', 'TEAM_ID', 'TEAM_ABBREVIATION', 'PLAYER_AGE', 'GP', 'GS',
            'MIN', 'FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT', 'FTM',
            'FTA', 'FT_PCT', 'OREB', 'DREB', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'PF', 'PTS'
        ]

        # Filter columns for regular season
        available_season_cols_rs = [col for col in season_totals_cols if col in season_totals_rs_df.columns]
        filtered_season_rs_df = season_totals_rs_df.loc[:, available_season_cols_rs] if not season_totals_rs_df.empty and available_season_cols_rs else pd.DataFrame()

        # Filter columns for post season
        available_season_cols_ps = [col for col in season_totals_cols if col in season_totals_ps_df.columns]
        filtered_season_ps_df = season_totals_ps_df.loc[:, available_season_cols_ps] if not season_totals_ps_df.empty and available_season_cols_ps else pd.DataFrame()

        # Save DataFrames to CSV if returning DataFrames
        if return_dataframe:
            # Save regular season data
            if not filtered_season_rs_df.empty:
                csv_path = _get_csv_path_for_career_stats(player_actual_name, per_mode, "season_regular")
                _save_dataframe_to_csv(filtered_season_rs_df, csv_path)

            if not career_totals_rs_df.empty:
                csv_path = _get_csv_path_for_career_stats(player_actual_name, per_mode, "career_regular")
                _save_dataframe_to_csv(career_totals_rs_df, csv_path)

            # Save post season data
            if not filtered_season_ps_df.empty:
                csv_path = _get_csv_path_for_career_stats(player_actual_name, per_mode, "season_post")
                _save_dataframe_to_csv(filtered_season_ps_df, csv_path)

            if not career_totals_ps_df.empty:
                csv_path = _get_csv_path_for_career_stats(player_actual_name, per_mode, "career_post")
                _save_dataframe_to_csv(career_totals_ps_df, csv_path)

        # Process DataFrames for JSON response
        season_totals_regular_season = _process_dataframe(filtered_season_rs_df, single_row=False)
        career_totals_regular_season = _process_dataframe(career_totals_rs_df, single_row=True)
        season_totals_post_season = _process_dataframe(filtered_season_ps_df, single_row=False)
        career_totals_post_season = _process_dataframe(career_totals_ps_df, single_row=True)

        if season_totals_regular_season is None or career_totals_regular_season is None:
            logger.error(f"DataFrame processing failed for regular season career stats of {player_actual_name}.")
            error_msg = Errors.PLAYER_CAREER_STATS_PROCESSING.format(identifier=player_actual_name)
            error_response = format_response(error=error_msg)
            if return_dataframe:
                return error_response, {}
            return error_response

        # Create response data
        response_data = {
            "player_name": player_actual_name,
            "player_id": player_id,
            "per_mode_requested": per_mode,
            "data_retrieved_mode": per_mode,
            "season_totals_regular_season": season_totals_regular_season or [],
            "career_totals_regular_season": career_totals_regular_season or {},
            "season_totals_post_season": season_totals_post_season or [],
            "career_totals_post_season": career_totals_post_season or {}
        }

        logger.info(f"fetch_player_career_stats_logic completed for '{player_actual_name}'")

        # Return the appropriate result based on return_dataframe
        if return_dataframe:
            dataframes = {
                "season_totals_regular_season": filtered_season_rs_df,
                "career_totals_regular_season": career_totals_rs_df,
                "season_totals_post_season": filtered_season_ps_df,
                "career_totals_post_season": career_totals_ps_df
            }
            return format_response(response_data), dataframes

        return format_response(response_data)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_career_stats_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_career_stats_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_career_stats_logic for '{player_name}': {e}", exc_info=True)
        error_msg = Errors.PLAYER_CAREER_STATS_UNEXPECTED.format(identifier=player_name, error=str(e))
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response

def fetch_player_awards_logic(
    player_name: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches a list of awards received by the player.

    Provides DataFrame output capabilities.

    Args:
        player_name: The name or ID of the player.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: A JSON string containing a list of player awards, or an error message.
                 Successful response structure:
                 {
                     "player_name": "Player Name",
                     "player_id": 12345,
                     "awards": [ { ... award details ... }, ... ]
                 }
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_player_awards_logic for: '{player_name}', return_dataframe={return_dataframe}")

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching playerawards for ID: {player_id}")

        try:
            awards_endpoint = playerawards.PlayerAwards(player_id=player_id, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
            logger.debug(f"playerawards API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api playerawards failed for ID {player_id}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_AWARDS_API.format(identifier=player_actual_name, error=str(api_error))
            error_response = format_response(error=error_msg)
            if return_dataframe:
                return error_response, {}
            return error_response

        # Get DataFrame from the API response
        awards_df = awards_endpoint.player_awards.get_data_frame()

        # Save DataFrame to CSV if returning DataFrame
        if return_dataframe and not awards_df.empty:
            csv_path = _get_csv_path_for_awards(player_actual_name)
            _save_dataframe_to_csv(awards_df, csv_path)

        # Process DataFrame for JSON response
        awards_list = _process_dataframe(awards_df, single_row=False)

        if awards_list is None:
            logger.error(f"DataFrame processing failed for awards of {player_actual_name}.")
            error_msg = Errors.PLAYER_AWARDS_PROCESSING.format(identifier=player_actual_name)
            error_response = format_response(error=error_msg)
            if return_dataframe:
                return error_response, {}
            return error_response

        # Create response data
        response_data = {
            "player_name": player_actual_name,
            "player_id": player_id,
            "awards": awards_list
        }

        logger.info(f"fetch_player_awards_logic completed for '{player_actual_name}'")

        # Return the appropriate result based on return_dataframe
        if return_dataframe:
            dataframes = {
                "awards": awards_df
            }
            return format_response(response_data), dataframes

        return format_response(response_data)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_awards_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_awards_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_awards_logic for '{player_name}': {e}", exc_info=True)
        error_msg = Errors.PLAYER_AWARDS_UNEXPECTED.format(identifier=player_name, error=str(e))
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response
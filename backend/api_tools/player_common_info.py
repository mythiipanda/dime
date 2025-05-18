"""
Handles fetching common player information, including biographical data,
headline statistics, available seasons, and headshot URLs.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
from functools import lru_cache
from typing import Dict, Any, Union, Tuple, Optional
import pandas as pd
import json

from nba_api.stats.endpoints import commonplayerinfo
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import _process_dataframe, format_response, find_player_id_or_error, PlayerNotFoundError

logger = logging.getLogger(__name__)

PLAYER_INFO_CACHE_SIZE = 256

# --- Cache Directory Setup ---
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
PLAYER_INFO_CSV_DIR = os.path.join(CSV_CACHE_DIR, "player_info")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(PLAYER_INFO_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_player_info(player_name: str, data_type: str) -> str:
    """
    Generates a file path for saving player info DataFrame as CSV.

    Args:
        player_name: The player's name
        data_type: The type of data (e.g., 'info', 'headline_stats', 'available_seasons')

    Returns:
        Path to the CSV file
    """
    # Clean player name for filename
    clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()

    filename = f"{clean_player_name}_{data_type}.csv"
    return os.path.join(PLAYER_INFO_CSV_DIR, filename)

def fetch_player_info_logic(
    player_name: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches common player information, headline stats, and available seasons for a given player.

    Provides DataFrame output capabilities.

    Args:
        player_name: The name or ID of the player.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: A JSON string containing player information, headline stats, and available seasons,
                 or an error message if the player is not found or an issue occurs.
                 Successful response structure:
                 {
                     "player_info": { ... common player info ... },
                     "headline_stats": { ... headline stats ... },
                     "available_seasons": [ ... list of available seasons ... ]
                 }
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_player_info_logic for: '{player_name}', return_dataframe={return_dataframe}")

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching commonplayerinfo for player ID: {player_id} ({player_actual_name})")

        try:
            info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
            logger.debug(f"commonplayerinfo API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api commonplayerinfo failed for ID {player_id}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_INFO_API.format(identifier=player_actual_name, error=str(api_error))
            error_response = format_response(error=error_msg)
            if return_dataframe:
                return error_response, {}
            return error_response

        # Get DataFrames from the API response
        player_info_df = info_endpoint.common_player_info.get_data_frame()
        headline_stats_df = info_endpoint.player_headline_stats.get_data_frame()
        available_seasons_df = info_endpoint.available_seasons.get_data_frame()

        # Save DataFrames to CSV if returning DataFrames
        if return_dataframe:
            if not player_info_df.empty:
                csv_path = _get_csv_path_for_player_info(player_actual_name, "info")
                _save_dataframe_to_csv(player_info_df, csv_path)

            if not headline_stats_df.empty:
                csv_path = _get_csv_path_for_player_info(player_actual_name, "headline_stats")
                _save_dataframe_to_csv(headline_stats_df, csv_path)

            if not available_seasons_df.empty:
                csv_path = _get_csv_path_for_player_info(player_actual_name, "available_seasons")
                _save_dataframe_to_csv(available_seasons_df, csv_path)

        # Process DataFrames for JSON response
        player_info_dict = _process_dataframe(player_info_df, single_row=True)
        headline_stats_dict = _process_dataframe(headline_stats_df, single_row=True)
        available_seasons_list = _process_dataframe(available_seasons_df, single_row=False)

        # Check if any essential data processing failed
        if player_info_dict is None or headline_stats_dict is None or available_seasons_list is None:
            logger.error(f"DataFrame processing failed for {player_actual_name} (player_info: {player_info_dict is None}, headline_stats: {headline_stats_dict is None}, available_seasons: {available_seasons_list is None}).")
            error_msg = Errors.PLAYER_INFO_PROCESSING.format(identifier=player_actual_name)
            error_response = format_response(error=error_msg)
            if return_dataframe:
                return error_response, {}
            return error_response

        # Create response data
        response_data = {
            "player_info": player_info_dict or {}, # Ensure empty dict if None
            "headline_stats": headline_stats_dict or {}, # Ensure empty dict if None
            "available_seasons": available_seasons_list or [] # Ensure empty list if None
        }

        logger.info(f"fetch_player_info_logic completed for '{player_actual_name}'")

        # Return the appropriate result based on return_dataframe
        if return_dataframe:
            dataframes = {
                "player_info": player_info_df,
                "headline_stats": headline_stats_df,
                "available_seasons": available_seasons_df
            }
            return format_response(response_data), dataframes

        return format_response(response_data)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_info_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_info_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_info_logic for '{player_name}': {e}", exc_info=True)
        error_msg = Errors.PLAYER_INFO_UNEXPECTED.format(identifier=player_name, error=str(e))
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response

def get_player_headshot_url(player_id: int) -> str:
    """
    Constructs the URL for a player's headshot image.

    Args:
        player_id (int): The unique ID of the player.

    Returns:
        str: The URL string for the player's headshot.

    Raises:
        ValueError: If the player_id is not a positive integer.
    """
    if not isinstance(player_id, int) or player_id <= 0:
        logger.error(f"Invalid player_id for headshot URL: {player_id}")
        raise ValueError(f"Invalid player ID provided for headshot: {player_id}")
    return f"{settings.HEADSHOT_BASE_URL}/{player_id}.png"
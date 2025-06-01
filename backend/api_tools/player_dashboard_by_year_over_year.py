"""
Handles fetching player dashboard statistics by year over year.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import os
import logging
import json
from typing import Optional, List, Dict, Any, Set, Union, Tuple
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import playerdashboardbyyearoveryear
from config import settings
from core.errors import Errors
from api_tools.utils import (
    _process_dataframe,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)
from utils.validation import _validate_season_format
from utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
PLAYER_DASHBOARD_BY_YEAR_CACHE_SIZE = 128

# --- Cache Directory Setup ---
PLAYER_DASHBOARD_BY_YEAR_CSV_DIR = get_cache_dir("player_dashboard_by_year_over_year")

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

def _get_csv_path_for_player_dashboard_by_year(
    player_id: str,
    season: str
) -> str:
    """
    Generates a file path for saving player dashboard by year DataFrame as CSV.

    Args:
        player_id: The player's ID
        season: The season in YYYY-YY format

    Returns:
        Path to the CSV file
    """
    return get_cache_file_path(
        f"player_{player_id}_dashboard_by_year_{season}.csv",
        "player_dashboard_by_year_over_year"
    )

# --- Helper for Parameter Validation ---
def _validate_dashboard_by_year_params(season: str) -> Optional[str]:
    """Validates parameters for dashboard by year stats function."""
    if not _validate_season_format(season):
        return Errors.INVALID_SEASON_FORMAT.format(season=season)
    return None

# --- Logic Functions ---
@lru_cache(maxsize=PLAYER_DASHBOARD_BY_YEAR_CACHE_SIZE)
def fetch_player_dashboard_by_year_over_year_logic(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player dashboard statistics by year over year.
    Provides DataFrame output capabilities.

    Args:
        player_name (str): The name or ID of the player.
        season (str, optional): The season in YYYY-YY format. Defaults to current season.
        return_dataframe (bool, optional): Whether to return DataFrames along with the JSON response.
                                          Defaults to False.

    Returns:
        If return_dataframe=False:
            str: A JSON string containing the player's dashboard data or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
            and a dictionary of DataFrames with keys for different data sets.
    """
    try:
        # Validate parameters
        validation_error = _validate_dashboard_by_year_params(season)
        if validation_error:
            error_response = format_response(error=validation_error)
            if return_dataframe:
                return error_response, {}
            return error_response

        # Find player ID
        try:
            player_id, _ = find_player_id_or_error(player_name)
        except PlayerNotFoundError as e:
            error_response = format_response(error=str(e))
            if return_dataframe:
                return error_response, {}
            return error_response

        # Make API call with only supported parameters
        dashboard = playerdashboardbyyearoveryear.PlayerDashboardByYearOverYear(
            player_id=player_id,
            season=season
        )

        # Process data sets
        dataframes = {}
        
        def get_df_safe(dataset_name: str) -> pd.DataFrame:
            """Safely get DataFrame from dataset."""
            try:
                dataset = getattr(dashboard, dataset_name)
                return dataset.get_data_frame()
            except Exception as e:
                logger.warning(f"Could not retrieve {dataset_name}: {e}")
                return pd.DataFrame()

        # Get available data sets
        by_year_df = get_df_safe('by_year_player_dashboard')
        overall_df = get_df_safe('overall_player_dashboard')

        if not by_year_df.empty:
            dataframes['by_year_player_dashboard'] = by_year_df
        if not overall_df.empty:
            dataframes['overall_player_dashboard'] = overall_df

        # Save to CSV if DataFrames are not empty
        if return_dataframe and dataframes:
            csv_path = _get_csv_path_for_player_dashboard_by_year(str(player_id), season)
            
            # Save the main by_year DataFrame
            if 'by_year_player_dashboard' in dataframes:
                _save_dataframe_to_csv(dataframes['by_year_player_dashboard'], csv_path)

        # Prepare response data
        response_data = {
            "player_id": player_id,
            "player_name": player_name,
            "season": season,
            "parameters": {
                "player_id": player_id,
                "season": season
            },
            "data_sets": list(dataframes.keys()) if dataframes else [],
            "total_records": sum(len(df) for df in dataframes.values()) if dataframes else 0
        }

        # Add data to response if not returning DataFrames
        if not return_dataframe:
            for key, df in dataframes.items():
                response_data[key] = _process_dataframe(df, single_row=False) if not df.empty else []

        json_response = format_response(data=response_data)
        
        if return_dataframe:
            return json_response, dataframes
        return json_response

    except Exception as e:
        logger.error(f"Error fetching player dashboard by year over year for {player_name}: {e}", exc_info=True)
        error_response = format_response(error=f"API error: {str(e)}")
        if return_dataframe:
            return error_response, {}
        return error_response 
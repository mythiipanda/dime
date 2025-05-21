"""
Handles fetching player career statistics.
Provides both JSON and DataFrame outputs with CSV caching.

This module implements the PlayerCareerStats endpoint, which provides
comprehensive career statistics for players:
- Career totals for regular season, playoffs, all-star games, and college
- Season-by-season breakdowns
- Statistical rankings
"""
import os
import logging
import json
from typing import Optional, Dict, Any, Union, Tuple, List
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import playercareerstats
from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response
)
from ..utils.path_utils import get_cache_dir, get_cache_file_path

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
PLAYER_CAREER_STATS_CACHE_SIZE = 128
PLAYER_CAREER_STATS_CSV_DIR = get_cache_dir("player_career_stats")

# Valid parameter values
VALID_PER_MODES = {
    "Totals": "Totals",
    "PerGame": "PerGame",
    "Per36": "Per36"
}

VALID_LEAGUE_IDS = {
    "00": "00",  # NBA
    "10": "10",  # WNBA
    "20": "20",  # G-League
    "": ""       # All leagues
}

# --- Helper Functions for DataFrame Processing ---
def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves a DataFrame to a CSV file.

    Args:
        df: DataFrame to save
        file_path: Path to save the CSV file
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Save DataFrame to CSV
        df.to_csv(file_path, index=False)
        logger.info(f"Saved DataFrame to CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)

def _get_csv_path_for_player_career_stats(
    player_id: str,
    per_mode: str,
    data_set_name: str,
    league_id: str = ""
) -> str:
    """
    Generates a file path for saving a player career stats DataFrame as CSV.

    Args:
        player_id: The player ID
        per_mode: The per mode (e.g., Totals, PerGame, Per36)
        data_set_name: The name of the data set (e.g., SeasonTotalsRegularSeason)
        league_id: Optional league ID filter

    Returns:
        Path to the CSV file
    """
    # Clean up parameters for filename
    per_mode_clean = per_mode.replace(" ", "_").lower()
    league_id_clean = league_id if league_id else "all_leagues"
    data_set_clean = data_set_name.replace(" ", "_").lower()

    # Create filename
    filename = f"player_career_stats_{player_id}_{per_mode_clean}_{data_set_clean}_{league_id_clean}.csv"

    return get_cache_file_path(filename, "player_career_stats")

# --- Parameter Validation Functions ---
def _validate_player_career_stats_params(
    player_id: str,
    per_mode: str,
    league_id: str = ""
) -> Optional[str]:
    """
    Validates parameters for the player career stats function.

    Args:
        player_id: Player ID
        per_mode: Per mode (e.g., Totals, PerGame, Per36)
        league_id: Optional league ID filter

    Returns:
        Error message if validation fails, None otherwise
    """
    if not player_id:
        return "Player ID is required"

    if per_mode not in VALID_PER_MODES:
        return Errors.INVALID_PER_MODE.format(
            value=per_mode,
            options=", ".join(list(VALID_PER_MODES.keys()))
        )

    if league_id and league_id not in VALID_LEAGUE_IDS:
        return f"Invalid league_id: '{league_id}'. Valid options: {', '.join(list(VALID_LEAGUE_IDS.keys()))}"

    return None

# --- Main Logic Function ---
@lru_cache(maxsize=PLAYER_CAREER_STATS_CACHE_SIZE)
def fetch_player_career_stats_logic(
    player_id: str,
    per_mode: str = "Totals",
    league_id: str = "",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player career statistics using the PlayerCareerStats endpoint.

    This endpoint provides comprehensive career statistics for players:
    - Career totals for regular season, playoffs, all-star games, and college
    - Season-by-season breakdowns
    - Statistical rankings

    Args:
        player_id (str): Player ID to fetch career stats for.
        per_mode (str, optional): Per mode for stats. Defaults to "Totals".
        league_id (str, optional): League ID filter. Defaults to "" (all leagues).
        return_dataframe (bool, optional): Whether to return DataFrames. Defaults to False.

    Returns:
        If return_dataframe=False:
            str: JSON string with player career stats data or error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: JSON response and dictionary of DataFrames.
    """
    logger.info(
        f"Executing fetch_player_career_stats_logic for: "
        f"Player ID: {player_id}, Per Mode: {per_mode}"
    )

    dataframes: Dict[str, pd.DataFrame] = {}

    # Validate parameters
    validation_error = _validate_player_career_stats_params(player_id, per_mode, league_id)
    if validation_error:
        if return_dataframe:
            return format_response(error=validation_error), dataframes
        return format_response(error=validation_error)

    # Prepare API parameters
    api_params = {
        "player_id": player_id,
        "per_mode36": VALID_PER_MODES[per_mode],
        "league_id_nullable": league_id,
        "timeout": settings.DEFAULT_TIMEOUT_SECONDS
    }

    # Filter out empty values for cleaner logging
    filtered_api_params = {k: v for k, v in api_params.items() if v and k != "timeout"}

    try:
        logger.debug(f"Calling PlayerCareerStats with parameters: {filtered_api_params}")
        career_stats_endpoint = playercareerstats.PlayerCareerStats(**api_params)

        # Get normalized dictionary for data set names
        normalized_dict = career_stats_endpoint.get_normalized_dict()
        logger.debug(f"Normalized dict keys: {list(normalized_dict.keys())}")

        # Get data frames
        list_of_dataframes = career_stats_endpoint.get_data_frames()
        logger.debug(f"Number of dataframes: {len(list_of_dataframes)}")

        # Get data set names from the result sets
        data_set_names = []
        if "resultSets" in normalized_dict:
            data_set_names = list(normalized_dict["resultSets"].keys())
            logger.debug(f"Found resultSets: {data_set_names}")
        elif "resultSet" in normalized_dict:
            # Some endpoints use "resultSet" instead of "resultSets"
            data_set_names = [rs["name"] for rs in normalized_dict["resultSet"]]
            logger.debug(f"Found resultSet: {data_set_names}")
        else:
            # If we can't find the data set names, use the expected names from the documentation
            # Based on the documentation and testing, these are the expected data sets
            expected_names = [
                "SeasonTotalsRegularSeason",          # DataSet_0
                "CareerTotalsRegularSeason",          # DataSet_1
                "SeasonTotalsPostSeason",             # DataSet_2
                "CareerTotalsPostSeason",             # DataSet_3
                "SeasonTotalsAllStarSeason",          # DataSet_4
                "CareerTotalsAllStarSeason",          # DataSet_5
                "SeasonTotalsCollegeSeason",          # DataSet_6
                "CareerTotalsCollegeSeason",          # DataSet_7
                "SeasonRankingsRegularSeason",        # DataSet_8
                "SeasonRankingsPostSeason",           # DataSet_9
                "SeasonTotalsRegularSeason",          # DataSet_10 (duplicate)
                "SeasonTotalsPostSeason",             # DataSet_11 (duplicate)
                "NextGameRegularSeason",              # DataSet_12 (not in docs)
                "NextGamePostSeason"                  # DataSet_13 (not in docs)
            ]

            # Check if we have the expected number of dataframes
            if len(list_of_dataframes) == len(expected_names):
                data_set_names = expected_names
                logger.debug(f"Using expected data set names: {data_set_names}")
            else:
                # Otherwise, use generic names
                data_set_names = [f"DataSet_{i}" for i in range(len(list_of_dataframes))]
                logger.debug(f"Using generic data set names: {data_set_names}")

        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": filtered_api_params,
            "data_sets": {}
        }

        # Process each data set
        for idx, data_set_name in enumerate(data_set_names):
            if idx < len(list_of_dataframes):
                df = list_of_dataframes[idx]

                # Store DataFrame if requested
                if return_dataframe:
                    dataframes[data_set_name] = df

                    # Save to CSV if not empty
                    if not df.empty:
                        csv_path = _get_csv_path_for_player_career_stats(
                            player_id, per_mode, data_set_name, league_id
                        )
                        _save_dataframe_to_csv(df, csv_path)

                # Process for JSON response
                processed_data = _process_dataframe(df, single_row=False)
                result_dict["data_sets"][data_set_name] = processed_data

        # Return response
        logger.info(f"Successfully fetched career stats for Player ID: {player_id}")
        if return_dataframe:
            return format_response(result_dict), dataframes
        return format_response(result_dict)

    except Exception as e:
        logger.error(
            f"API error in fetch_player_career_stats_logic: {e}",
            exc_info=True
        )
        error_msg = Errors.PLAYER_CAREER_STATS_API.format(
            player_id=player_id, per_mode=per_mode, error=str(e)
        )
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

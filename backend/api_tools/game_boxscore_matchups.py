"""
Handles fetching and processing player matchup data from NBA games
using the BoxScoreMatchupsV3 endpoint.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
from functools import lru_cache
import pandas as pd
from typing import Dict, Optional, Union, Tuple

from nba_api.stats.endpoints import BoxScoreMatchupsV3
from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response
)
from ..utils.validation import validate_game_id_format

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
GAME_BOXSCORE_MATCHUPS_CACHE_SIZE = 128
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
BOXSCORE_MATCHUPS_CSV_DIR = os.path.join(CSV_CACHE_DIR, "boxscore_matchups")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(BOXSCORE_MATCHUPS_CSV_DIR, exist_ok=True)

# --- Helper Functions for DataFrame Processing ---
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

def _get_csv_path_for_matchups(game_id: str) -> str:
    """
    Generates a file path for saving a matchups DataFrame as CSV.

    Args:
        game_id: The game ID

    Returns:
        Path to the CSV file
    """
    filename = f"{game_id}_matchups.csv"
    return os.path.join(BOXSCORE_MATCHUPS_CSV_DIR, filename)

@lru_cache(maxsize=GAME_BOXSCORE_MATCHUPS_CACHE_SIZE)
def fetch_game_boxscore_matchups_logic(
    game_id: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player matchup data for a given game using BoxScoreMatchupsV3 endpoint.

    This endpoint provides detailed player-vs-player matchup statistics including:
    - Time matched up against each other
    - Points scored in the matchup
    - Field goal percentages
    - Assists, turnovers, and blocks in the matchup

    Args:
        game_id (str): The ID of the game to fetch matchup data for
        return_dataframe (bool, optional): Whether to return DataFrames along with the JSON response.
                                          Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
            If return_dataframe is False, a JSON string with the matchup data or an error.
            If return_dataframe is True, a tuple containing the JSON response string and a dictionary
            of DataFrames.
    """
    logger.info(f"Executing fetch_game_boxscore_matchups_logic for game ID: {game_id}")
    dataframes: Dict[str, pd.DataFrame] = {}

    # Parameter validation
    if not game_id:
        error_msg = Errors.GAME_ID_EMPTY
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    if not validate_game_id_format(game_id):
        error_msg = Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id)
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    try:
        # Call the NBA API endpoint
        logger.debug(f"Calling BoxScoreMatchupsV3 API with game_id: {game_id}")
        matchups = BoxScoreMatchupsV3(
            game_id=game_id,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )

        # Get DataFrame from the endpoint
        matchups_df = matchups.player_stats.get_data_frame()

        # Handle DataFrame if requested
        if return_dataframe:
            dataframes["matchups"] = matchups_df

            # Save to CSV if not empty
            if not matchups_df.empty:
                csv_path = _get_csv_path_for_matchups(game_id)
                _save_dataframe_to_csv(matchups_df, csv_path)

        # Process data for JSON response
        if matchups_df.empty:
            logger.warning(f"No matchup data returned by API for game {game_id}")
            processed_matchups = []
        else:
            processed_matchups = _process_dataframe(matchups_df, single_row=False)

            if processed_matchups is None:  # _process_dataframe returns None on internal error
                logger.error(f"Error processing matchups data for game {game_id}")
                error_msg = Errors.PROCESSING_ERROR.format(error=f"BoxScoreMatchupsV3 data for game {game_id}")
                if return_dataframe:
                    return format_response(error=error_msg), dataframes
                return format_response(error=error_msg)

        # Create response
        response_data = {
            "game_id": game_id,
            "matchups": processed_matchups,
            "parameters": {
                "note": "Using BoxScoreMatchupsV3"
            }
        }

        # Return response
        logger.info(f"Successfully fetched BoxScoreMatchupsV3 for game {game_id}")
        if return_dataframe:
            return format_response(response_data), dataframes
        return format_response(response_data)

    except Exception as e:
        logger.error(
            f"API error in fetch_game_boxscore_matchups_logic for game {game_id}: {e}",
            exc_info=True
        )
        error_msg = Errors.BOXSCORE_MATCHUPS_API.format(game_id=game_id, error=str(e))
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

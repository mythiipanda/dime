"""
Handles fetching and processing player game logs for a specific season and season type.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
from functools import lru_cache
from typing import Dict, Any, Union, Tuple, Optional, List
import pandas as pd
import json

from nba_api.stats.endpoints import playergamelog
from nba_api.stats.library.parameters import SeasonTypeAllStar
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

PLAYER_GAMELOG_CACHE_SIZE = 256

# --- Cache Directory Setup ---
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
PLAYER_GAMELOG_CSV_DIR = os.path.join(CSV_CACHE_DIR, "player_gamelogs")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(PLAYER_GAMELOG_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_player_gamelog(player_name: str, season: str, season_type: str) -> str:
    """
    Generates a file path for saving player gamelog DataFrame as CSV.

    Args:
        player_name: The player's name
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')

    Returns:
        Path to the CSV file
    """
    # Clean player name for filename
    clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()

    # Clean season type for filename
    clean_season_type = season_type.replace(" ", "_").lower()

    filename = f"{clean_player_name}_{season}_{clean_season_type}_gamelog.csv"
    return os.path.join(PLAYER_GAMELOG_CSV_DIR, filename)

def fetch_player_gamelog_logic(
    player_name: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player game logs for a specified player, season, and season type.

    Provides DataFrame output capabilities.

    Args:
        player_name: The name or ID of the player.
        season: The NBA season in YYYY-YY format (e.g., "2023-24").
        season_type: The type of season (e.g., "Regular Season", "Playoffs").
                    Defaults to "Regular Season".
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: A JSON string containing a list of game logs, or an error message if an issue occurs.
                 Successful response structure:
                 {
                     "player_name": "Player Name",
                     "player_id": 12345,
                     "season": "YYYY-YY",
                     "season_type": "Season Type",
                     "gamelog": [ { ... game log data ... }, ... ]
                 }
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_player_gamelog_logic for: '{player_name}', Season: {season}, Type: {season_type}, return_dataframe={return_dataframe}")

    if not season or not _validate_season_format(season):
        error_msg = Errors.INVALID_SEASON_FORMAT.format(season=season)
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        error_msg = Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5])) # Show some options
        logger.warning(error_msg)
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching playergamelog for ID: {player_id}, Season: {season}, Type: {season_type}")

        try:
            gamelog_endpoint = playergamelog.PlayerGameLog(
                player_id=player_id, season=season, season_type_all_star=season_type, timeout=settings.DEFAULT_TIMEOUT_SECONDS
            )
            logger.debug(f"playergamelog API call successful for ID: {player_id}, Season: {season}")
        except Exception as api_error:
            logger.error(f"nba_api playergamelog failed for ID {player_id}, Season {season}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_GAMELOG_API.format(identifier=player_actual_name, season=season, error=str(api_error))
            error_response = format_response(error=error_msg)
            if return_dataframe:
                return error_response, {}
            return error_response

        # Get DataFrame from the API response
        gamelog_df = gamelog_endpoint.get_data_frames()[0]

        if gamelog_df.empty:
            logger.warning(f"No gamelog data found for {player_actual_name} ({season}, {season_type}).")
            response_data = {
                "player_name": player_actual_name,
                "player_id": player_id,
                "season": season,
                "season_type": season_type,
                "gamelog": []
            }

            if return_dataframe:
                # Return empty DataFrame
                empty_df = pd.DataFrame()
                return format_response(response_data), {"gamelog": empty_df}

            return format_response(response_data)

        # Define columns to include
        gamelog_cols = [
            'GAME_ID', 'GAME_DATE', 'MATCHUP', 'WL', 'MIN', 'FGM', 'FGA', 'FG_PCT',
            'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT', 'OREB', 'DREB',
            'REB', 'AST', 'STL', 'BLK', 'TOV', 'PF', 'PTS', 'PLUS_MINUS',
            'VIDEO_AVAILABLE'
        ]

        # Filter columns
        available_gamelog_cols = [col for col in gamelog_cols if col in gamelog_df.columns]
        filtered_gamelog_df = gamelog_df.loc[:, available_gamelog_cols] if available_gamelog_cols else pd.DataFrame()

        # Save DataFrame to CSV if returning DataFrame
        if return_dataframe and not filtered_gamelog_df.empty:
            csv_path = _get_csv_path_for_player_gamelog(player_actual_name, season, season_type)
            _save_dataframe_to_csv(filtered_gamelog_df, csv_path)

        # Process DataFrame for JSON response
        gamelog_list = _process_dataframe(filtered_gamelog_df, single_row=False)

        if gamelog_list is None:
            logger.error(f"DataFrame processing failed for gamelog of {player_actual_name} ({season}).")
            error_msg = Errors.PLAYER_GAMELOG_PROCESSING.format(identifier=player_actual_name, season=season)
            error_response = format_response(error=error_msg)
            if return_dataframe:
                return error_response, {}
            return error_response

        # Create response data
        response_data = {
            "player_name": player_actual_name,
            "player_id": player_id,
            "season": season,
            "season_type": season_type,
            "gamelog": gamelog_list
        }

        logger.info(f"fetch_player_gamelog_logic completed for '{player_actual_name}', Season: {season}")

        # Return the appropriate result based on return_dataframe
        if return_dataframe:
            dataframes = {
                "gamelog": filtered_gamelog_df
            }
            return format_response(response_data), dataframes

        return format_response(response_data)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_gamelog_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_gamelog_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_gamelog_logic for '{player_name}', Season {season}: {e}", exc_info=True)
        error_msg = Errors.PLAYER_GAMELOG_UNEXPECTED.format(identifier=player_name, season=season, error=str(e))
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response
import logging
import json # Added for potential use if format_response changes
import os # Added for path operations
from functools import lru_cache
from typing import Union, Tuple, Dict # Added for typing
import pandas as pd # Added for DataFrame typing

from nba_api.stats.endpoints import CommonTeamYears
from nba_api.stats.library.parameters import LeagueID

from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response
)
from ..utils.validation import _validate_league_id
from ..utils.path_utils import get_cache_dir, get_cache_file_path # Added imports

logger = logging.getLogger(__name__)

# Define cache directory
TEAM_HISTORY_CSV_DIR = get_cache_dir("team_history")

# --- Helper Functions for CSV Caching ---
def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves a DataFrame to a CSV file.
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        df.to_csv(file_path, index=False)
        logger.info(f"Saved DataFrame to CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)

def _get_csv_path_for_team_history(league_id: str) -> str:
    """
    Generates a file path for saving team history DataFrame as CSV.
    """
    filename = f"team_history_league_{league_id}.csv"
    return get_cache_file_path(filename, "team_history")

@lru_cache(maxsize=settings.DEFAULT_LRU_CACHE_SIZE)
def fetch_common_team_years_logic(
    league_id: str = LeagueID.nba,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: # Updated return type
    """
    Fetches a list of all team years for a given league, indicating the range of seasons each team existed.

    Args:
        league_id (str, optional): The league ID. Defaults to "00" (NBA).
        return_dataframe (bool, optional): Whether to return the DataFrame alongside JSON. Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON string, Dict with DataFrame).
    """
    dataframes = {} # Initialize for potential DataFrame return
    logger.info(f"Executing fetch_common_team_years_logic for LeagueID: {league_id}, return_dataframe={return_dataframe}")

    if not _validate_league_id(league_id):
        error_msg = Errors.INVALID_LEAGUE_ID.format(value=league_id, options=["00", "10", "20"])
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    try:
        team_years_endpoint = CommonTeamYears(
            league_id=league_id,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"CommonTeamYears API call successful for LeagueID: {league_id}")

        team_years_df = team_years_endpoint.team_years.get_data_frame()
        
        if return_dataframe:
            dataframes["team_years"] = team_years_df
            if not team_years_df.empty:
                csv_path = _get_csv_path_for_team_history(league_id)
                _save_dataframe_to_csv(team_years_df, csv_path)

        team_years_list = _process_dataframe(team_years_df, single_row=False)

        if team_years_list is None:
            logger.error(f"DataFrame processing failed for CommonTeamYears (LeagueID: {league_id}).")
            error_msg = Errors.COMMON_TEAM_YEARS_API_ERROR.format(error="DataFrame processing returned None unexpectedly.")
            if return_dataframe:
                return format_response(error=error_msg), dataframes
            return format_response(error=error_msg)

        response_data = {
            "parameters": {"league_id": league_id},
            "team_years": team_years_list
        }
        
        json_output = format_response(response_data)
        logger.info(f"Successfully fetched {len(team_years_list)} team year entries for LeagueID: {league_id}")
        
        if return_dataframe:
            return json_output, dataframes
        return json_output

    except Exception as e:
        logger.error(
            f"Error in fetch_common_team_years_logic for LeagueID {league_id}: {str(e)}",
            exc_info=True
        )
        error_msg = Errors.COMMON_TEAM_YEARS_API_ERROR.format(error=str(e))
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg) 
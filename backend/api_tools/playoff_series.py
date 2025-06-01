"""
Handles fetching information about playoff series for a given league and season.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
from typing import Optional, Union, Tuple, Dict
import pandas as pd

from nba_api.stats.endpoints import CommonPlayoffSeries
from nba_api.stats.library.parameters import LeagueID

from config import settings
from core.errors import Errors
from api_tools.utils import (
    _process_dataframe,
    format_response
)
from utils.validation import _validate_season_format, _validate_league_id
from utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Cache Directory Setup ---
PLAYOFF_SERIES_CSV_DIR = get_cache_dir("playoff_series")

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

def _get_csv_path_for_playoff_series(season: str, league_id: str, series_id: Optional[str] = None) -> str:
    """
    Generates a file path for saving a playoff series DataFrame as CSV.

    Args:
        season: The season (YYYY-YY format)
        league_id: The league ID
        series_id: Optional series ID to filter for

    Returns:
        Path to the CSV file
    """
    # Clean parameters for filename
    clean_season = season.replace("-", "_")
    clean_league_id = league_id

    if series_id:
        filename = f"playoff_series_{clean_season}_{clean_league_id}_{series_id}.csv"
    else:
        filename = f"playoff_series_{clean_season}_{clean_league_id}.csv"

    return get_cache_file_path(filename, "playoff_series")

def fetch_common_playoff_series_logic(
    season: str,
    league_id: str = LeagueID.nba,
    series_id: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches information about playoff series for a given league and season.
    Can optionally be filtered by a specific SeriesID.

    Provides DataFrame output capabilities.

    Args:
        season: The NBA season identifier in YYYY-YY format (e.g., "2022-23").
        league_id: The league ID. Defaults to "00" (NBA).
        series_id: A specific SeriesID to filter for. Defaults to None.
                  The NBA API docs refer to this as series_id_nullable.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: A JSON string containing a list of playoff series game details or an error message.
                 Expected structure:
                 {
                     "parameters": {"season": str, "league_id": str, "series_id": Optional[str]},
                     "playoff_series": [
                         {
                             "GAME_ID": str, "HOME_TEAM_ID": int, "VISITOR_TEAM_ID": int,
                             "SERIES_ID": str, "GAME_NUM": int
                         }, ...
                     ]
                 }
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(
        f"Executing fetch_common_playoff_series_logic for Season: {season}, LeagueID: {league_id}, "
        f"SeriesID: {series_id}, return_dataframe={return_dataframe}"
    )

    if not _validate_season_format(season):
        error_msg = Errors.INVALID_SEASON_FORMAT.format(season=season)
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response

    if not _validate_league_id(league_id):
        # Specify valid options for clarity in the error message
        error_msg = Errors.INVALID_LEAGUE_ID.format(value=league_id, options=["00", "10", "20"])
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response

    # series_id can be None, so no specific validation on its format other than being a string if provided.
    # The API handles empty string or None for series_id_nullable.

    try:
        playoff_series_endpoint = CommonPlayoffSeries(
            league_id=league_id,
            season=season,
            series_id_nullable=series_id, # Parameter name as per nba_api
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"CommonPlayoffSeries API call successful for Season: {season}, SeriesID: {series_id}")

        series_df = playoff_series_endpoint.playoff_series.get_data_frame()

        # Save DataFrame to CSV if returning DataFrames
        if return_dataframe and not series_df.empty:
            csv_path = _get_csv_path_for_playoff_series(season, league_id, series_id)
            _save_dataframe_to_csv(series_df, csv_path)

        series_list = _process_dataframe(series_df, single_row=False)

        if series_list is None: # Should not happen with single_row=False
            logger.error(f"DataFrame processing failed for CommonPlayoffSeries (Season: {season}, SeriesID: {series_id}).")
            error_msg = Errors.COMMON_PLAYOFF_SERIES_API_ERROR.format(error="DataFrame processing returned None unexpectedly.")
            error_response = format_response(error=error_msg)
            if return_dataframe:
                return error_response, {}
            return error_response

        response_data = {
            "parameters": {
                "season": season,
                "league_id": league_id,
                "series_id": series_id
            },
            "playoff_series": series_list
        }

        # Add DataFrame metadata to the response if DataFrames are being returned
        if return_dataframe and not series_df.empty:
            csv_filename = os.path.basename(_get_csv_path_for_playoff_series(season, league_id, series_id))
            relative_path = get_relative_cache_path(csv_filename, "playoff_series")

            response_data["dataframe_info"] = {
                "message": "Playoff series data has been converted to DataFrame and saved as CSV file",
                "dataframes": {
                    "playoff_series": {
                        "shape": list(series_df.shape),
                        "columns": series_df.columns.tolist(),
                        "csv_path": relative_path
                    }
                }
            }

        logger.info(f"Successfully fetched {len(series_list)} series entries for Season: {season}, LeagueID: {league_id}, SeriesID: {series_id}")

        # Return the appropriate result based on return_dataframe
        if return_dataframe:
            dataframes = {
                "playoff_series": series_df
            }
            return format_response(response_data), dataframes

        return format_response(response_data)

    except Exception as e:
        logger.error(
            f"Error in fetch_common_playoff_series_logic for Season {season}, LeagueID {league_id}, SeriesID {series_id}: {str(e)}",
            exc_info=True
        )
        error_msg = Errors.COMMON_PLAYOFF_SERIES_API_ERROR.format(error=str(e))
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response
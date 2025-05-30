"""
Handles fetching player estimated metrics (E_OFF_RATING, E_DEF_RATING, E_NET_RATING, etc.)
for a given season and season type.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import os
import logging
from functools import lru_cache
from typing import Union, Tuple, Dict, Optional

import pandas as pd

from nba_api.stats.endpoints import playerestimatedmetrics
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ..config import settings
from ..core.errors import Errors
from .utils import _process_dataframe, format_response
from ..utils.validation import _validate_season_format
from ..utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Cache Directory Setup ---
PLAYER_ESTIMATED_METRICS_CSV_DIR = get_cache_dir("player_estimated_metrics")

# --- Module-level constants for validation sets ---
_VALID_PEM_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}
_VALID_PEM_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}

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

def _get_csv_path_for_estimated_metrics(
    season: str,
    season_type: str,
    league_id: str
) -> str:
    """
    Generates a file path for saving player estimated metrics DataFrame as CSV.

    Args:
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        league_id: The league ID (e.g., '00' for NBA)

    Returns:
        Path to the CSV file
    """
    # Clean season type for filename
    clean_season_type = season_type.replace(" ", "_").lower()

    return get_cache_file_path(
        f"player_estimated_metrics_{season}_{clean_season_type}_{league_id}.csv",
        "player_estimated_metrics"
    )

def fetch_player_estimated_metrics_logic(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    league_id: str = LeagueID.nba,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, pd.DataFrame]]:
    """
    Fetches player estimated metrics (E_OFF_RATING, E_DEF_RATING, E_NET_RATING, etc.)
    for a given season and season type using nba_api's PlayerEstimatedMetrics endpoint.

    Args:
        season: NBA season in 'YYYY-YY' format (e.g., '2023-24').
        season_type: Season type (e.g., 'Regular Season', 'Playoffs').
        league_id: League ID (default: NBA '00').
        return_dataframe: Whether to return DataFrame along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON-formatted string with estimated metrics or an error message.
        If return_dataframe=True:
            Tuple[str, pd.DataFrame]: A tuple containing the JSON response string
                                     and the DataFrame with estimated metrics.
    """
    logger.info(f"Executing fetch_player_estimated_metrics_logic for Season: {season}, Season Type: {season_type}, League ID: {league_id}, return_dataframe={return_dataframe}")

    # Create an empty DataFrame for error cases
    empty_df = pd.DataFrame()

    if not _validate_season_format(season):
        if return_dataframe:
            return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season)), empty_df
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    if league_id not in _VALID_PEM_LEAGUE_IDS:
        if return_dataframe:
            return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_VALID_PEM_LEAGUE_IDS)[:3]))), empty_df
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_VALID_PEM_LEAGUE_IDS)[:3])))

    if season_type not in _VALID_PEM_SEASON_TYPES:
        if return_dataframe:
            return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_PEM_SEASON_TYPES)[:5]))), empty_df
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_PEM_SEASON_TYPES)[:5])))

    try:
        pem_endpoint = playerestimatedmetrics.PlayerEstimatedMetrics(
            league_id=league_id,
            season=season,
            season_type=season_type,  # Corrected parameter name
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )

        metrics_df = pem_endpoint.player_estimated_metrics.get_data_frame()

        # Save DataFrame to CSV if requested and not empty
        if return_dataframe and not metrics_df.empty:
            csv_path = _get_csv_path_for_estimated_metrics(
                season=season,
                season_type=season_type,
                league_id=league_id
            )
            _save_dataframe_to_csv(metrics_df, csv_path)

        metrics_list = _process_dataframe(metrics_df, single_row=False)

        if metrics_list is None:
            logger.error(f"DataFrame processing failed for player estimated metrics (Season: {season}, Type: {season_type}).")
            error_msg = Errors.PROCESSING_ERROR.format(error="player estimated metrics data processing failed")  # Generic processing error
            if return_dataframe:
                return format_response(error=error_msg), empty_df
            return format_response(error=error_msg)

        if metrics_df.empty:
            logger.warning(f"No player estimated metrics data found for Season: {season}, Type: {season_type}.")
            data_payload = []
        else:
            data_payload = metrics_list

        result = {
            "parameters": {
                "season": season,
                "season_type": season_type,
                "league_id": league_id
            },
            "player_estimated_metrics": data_payload
        }

        # Add DataFrame info to the response if requested
        if return_dataframe:
            if not metrics_df.empty:
                csv_path = _get_csv_path_for_estimated_metrics(
                    season=season,
                    season_type=season_type,
                    league_id=league_id
                )
                relative_path = get_relative_cache_path(
                    os.path.basename(csv_path),
                    "player_estimated_metrics"
                )

                result["dataframe_info"] = {
                    "message": "Player estimated metrics data has been converted to DataFrame and saved as CSV file",
                    "shape": list(metrics_df.shape),
                    "columns": metrics_df.columns.tolist(),
                    "csv_path": relative_path
                }

            logger.info(f"Successfully fetched player estimated metrics for Season: {season}, Type: {season_type} with DataFrame")
            return format_response(data=result), metrics_df

        logger.info(f"Successfully fetched player estimated metrics for Season: {season}, Type: {season_type}")
        return format_response(data=result)

    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_estimated_metrics_logic: {e}")
        if return_dataframe:
            return format_response(error=str(e)), empty_df
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_estimated_metrics_logic for Season {season}, Type {season_type}: {e}", exc_info=True)
        # Using a more generic error message as specific ones for this endpoint don't exist yet
        error_msg = Errors.API_ERROR.format(error=f"fetching player estimated metrics: {str(e)}")
        if return_dataframe:
            return format_response(error=error_msg), empty_df
        return format_response(error=error_msg)
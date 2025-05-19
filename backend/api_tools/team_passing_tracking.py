"""
Handles fetching team-level passing tracking statistics using the TeamDashPtPass endpoint.
Utilizes shared utilities for team identification and parameter validation.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
from functools import lru_cache
from typing import Set, Dict, Union, Tuple, Optional # For type hinting validation sets

import pandas as pd
from nba_api.stats.endpoints import teamdashptpass
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

from ..config import settings
from ..core.errors import Errors
from .utils import _process_dataframe, format_response
from .team_tracking_utils import _validate_team_tracking_params, _get_team_info_for_tracking
from .http_client import nba_session # For session patching

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
TEAM_PASSING_TRACKING_CACHE_SIZE = 128

_TEAM_PASSING_VALID_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_TEAM_PASSING_VALID_PER_MODES: Set[str] = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}

# Apply session patch to the endpoint class for custom HTTP client usage
teamdashptpass.requests = nba_session

# --- Cache Directory Setup ---
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
TEAM_PASSING_CSV_DIR = os.path.join(CSV_CACHE_DIR, "team_passing")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(TEAM_PASSING_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_team_passing(
    team_name: str,
    season: str,
    season_type: str,
    per_mode: str,
    data_type: str
) -> str:
    """
    Generates a file path for saving team passing DataFrame as CSV.

    Args:
        team_name: The team's name
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        per_mode: The per mode (e.g., 'PerGame', 'Totals')
        data_type: The type of data ('passes_made' or 'passes_received')

    Returns:
        Path to the CSV file
    """
    # Clean team name and data type for filename
    clean_team_name = team_name.replace(" ", "_").replace(".", "").lower()
    clean_season_type = season_type.replace(" ", "_").lower()
    clean_per_mode = per_mode.replace(" ", "_").lower()

    filename = f"{clean_team_name}_{season}_{clean_season_type}_{clean_per_mode}_{data_type}.csv"
    return os.path.join(TEAM_PASSING_CSV_DIR, filename)

# --- Main Logic Function ---
def fetch_team_passing_stats_logic(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches team passing statistics, detailing passes made and received among players
    for a specific team and season using the TeamDashPtPass endpoint.
    Provides DataFrame output capabilities.

    Args:
        team_identifier: Name, abbreviation, or ID of the team.
        season: NBA season in YYYY-YY format. Defaults to current season.
        season_type: Type of season (e.g., "Regular Season"). Defaults to Regular Season.
        per_mode: Statistical mode (e.g., "PerGame"). Defaults to PerGame.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string with team passing stats or an error message.
                 Includes 'passes_made' and 'passes_received' lists.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_team_passing_stats_logic for: {team_identifier}, Season: {season}, PerMode: {per_mode}, return_dataframe={return_dataframe}")

    # Basic validation for team_identifier and season (delegated)
    validation_error_msg = _validate_team_tracking_params(team_identifier, season)
    if validation_error_msg:
        if return_dataframe:
            return validation_error_msg, {}
        return validation_error_msg

    # Specific validation for season_type and per_mode for this endpoint
    if season_type not in _TEAM_PASSING_VALID_SEASON_TYPES:
        error_response = format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_TEAM_PASSING_VALID_SEASON_TYPES)[:5])))
        if return_dataframe:
            return error_response, {}
        return error_response

    if per_mode not in _TEAM_PASSING_VALID_PER_MODES:
        error_response = format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_TEAM_PASSING_VALID_PER_MODES)[:5])))
        if return_dataframe:
            return error_response, {}
        return error_response

    # Resolve team ID and name
    error_resp, team_id_resolved, team_name_resolved = _get_team_info_for_tracking(team_identifier, None) # No specific league_id needed for teamdashptpass
    if error_resp:
        if return_dataframe:
            return error_resp, {}
        return error_resp

    if team_id_resolved is None or team_name_resolved is None: # Should be caught by error_resp, but defensive check
        error_response = format_response(error=Errors.TEAM_INFO_RESOLUTION_FAILED.format(identifier=team_identifier))
        if return_dataframe:
            return error_response, {}
        return error_response

    # Store DataFrames if requested
    dataframes = {}

    try:
        logger.debug(f"Fetching teamdashptpass for Team ID: {team_id_resolved}, Season: {season}")
        pass_stats_endpoint = teamdashptpass.TeamDashPtPass(
            team_id=team_id_resolved, season=season, season_type_all_star=season_type,
            per_mode_simple=per_mode, timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"teamdashptpass API call successful for ID: {team_id_resolved}, Season: {season}")

        passes_made_df = pass_stats_endpoint.passes_made.get_data_frame()
        passes_received_df = pass_stats_endpoint.passes_received.get_data_frame()

        if return_dataframe:
            dataframes["passes_made"] = passes_made_df
            dataframes["passes_received"] = passes_received_df

            # Save DataFrames to CSV if not empty
            if not passes_made_df.empty:
                csv_path = _get_csv_path_for_team_passing(
                    team_name_resolved, season, season_type, per_mode, "passes_made"
                )
                _save_dataframe_to_csv(passes_made_df, csv_path)

            if not passes_received_df.empty:
                csv_path = _get_csv_path_for_team_passing(
                    team_name_resolved, season, season_type, per_mode, "passes_received"
                )
                _save_dataframe_to_csv(passes_received_df, csv_path)

        passes_made_list = _process_dataframe(passes_made_df, single_row=False)
        passes_received_list = _process_dataframe(passes_received_df, single_row=False)

        if passes_made_list is None or passes_received_list is None:
            if passes_made_df.empty and passes_received_df.empty:
                logger.warning(f"No passing stats found for team {team_name_resolved} ({team_id_resolved}), season {season}.")

                response_data = {
                    "team_name": team_name_resolved, "team_id": team_id_resolved, "season": season,
                    "season_type": season_type, "parameters": {"per_mode": per_mode},
                    "passes_made": [], "passes_received": []
                }

                if return_dataframe:
                    return format_response(response_data), dataframes
                return format_response(response_data)
            else:
                logger.error(f"DataFrame processing failed for team passing stats of {team_name_resolved} ({season}).")
                error_msg = Errors.TEAM_PASSING_PROCESSING.format(identifier=str(team_id_resolved))
                error_response = format_response(error=error_msg)

                if return_dataframe:
                    return error_response, dataframes
                return error_response

        result = {
            "team_name": team_name_resolved, "team_id": team_id_resolved, "season": season, "season_type": season_type,
            "parameters": {"per_mode": per_mode},
            "passes_made": passes_made_list or [], "passes_received": passes_received_list or []
        }
        logger.info(f"fetch_team_passing_stats_logic completed for '{team_name_resolved}'")

        if return_dataframe:
            return format_response(result), dataframes
        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching passing stats for team {team_identifier}: {str(e)}", exc_info=True)
        error_msg = Errors.TEAM_PASSING_UNEXPECTED.format(identifier=team_identifier, error=str(e))
        error_response = format_response(error=error_msg)

        if return_dataframe:
            return error_response, dataframes
        return error_response
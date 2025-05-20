"""
Handles fetching team-level rebounding tracking statistics using the TeamDashPtReb endpoint.
Utilizes shared utilities for team identification and parameter validation.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
from typing import Optional, Set, Dict, Union, Tuple # For type hinting validation sets
from functools import lru_cache

import pandas as pd
from nba_api.stats.endpoints import teamdashptreb
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

from ..config import settings
from ..core.errors import Errors
from .utils import _process_dataframe, format_response
from ..utils.validation import validate_date_format
from .team_tracking_utils import _validate_team_tracking_params, _get_team_info_for_tracking
from .http_client import nba_session # For session patching

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
TEAM_REBOUNDING_TRACKING_CACHE_SIZE = 128
NBA_API_DEFAULT_OPPONENT_TEAM_ID = 0 # Standard value for no specific opponent filter

_TEAM_REB_VALID_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_TEAM_REB_VALID_PER_MODES: Set[str] = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}

# Apply session patch to the endpoint class for custom HTTP client usage
teamdashptreb.requests = nba_session

# --- Cache Directory Setup ---
from ..utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path
TEAM_REBOUNDING_CSV_DIR = get_cache_dir("team_rebounding")

# --- Helper Functions for CSV Caching ---
def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves a DataFrame to a CSV file, creating the directory if it doesn't exist.

    Args:
        df: The DataFrame to save
        file_path: The path to save the CSV file
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Save DataFrame to CSV
        df.to_csv(file_path, index=False)
        logger.debug(f"Saved DataFrame to {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to {file_path}: {e}", exc_info=True)

def _get_csv_path_for_team_rebounding(
    team_name: str,
    season: str,
    season_type: str,
    per_mode: str,
    data_type: str
) -> str:
    """
    Generates a file path for saving team rebounding DataFrame as CSV.

    Args:
        team_name: The team's name
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        per_mode: The per mode (e.g., 'PerGame', 'Totals')
        data_type: The type of data ('overall', 'shot_type', 'contest', 'shot_distance', 'reb_distance')

    Returns:
        Path to the CSV file
    """
    # Clean team name and data type for filename
    clean_team_name = team_name.replace(" ", "_").replace(".", "").lower()
    clean_season_type = season_type.replace(" ", "_").lower()
    clean_per_mode = per_mode.replace(" ", "_").lower()

    filename = f"{clean_team_name}_{season}_{clean_season_type}_{clean_per_mode}_{data_type}.csv"
    return get_cache_file_path(filename, "team_rebounding")

# --- Main Logic Function ---
def fetch_team_rebounding_stats_logic(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    opponent_team_id: int = NBA_API_DEFAULT_OPPONENT_TEAM_ID,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches team rebounding statistics, categorized by various factors like shot type,
    contest level, shot distance, and rebound distance, using the TeamDashPtReb endpoint.
    Provides DataFrame output capabilities.

    Args:
        team_identifier: Name, abbreviation, or ID of the team.
        season: NBA season in YYYY-YY format. Defaults to current season.
        season_type: Type of season. Defaults to Regular Season.
        per_mode: Statistical mode. Defaults to PerGame.
        opponent_team_id: Filter by opponent team ID. Defaults to 0 (all).
        date_from: Start date filter (YYYY-MM-DD).
        date_to: End date filter (YYYY-MM-DD).
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string with team rebounding stats or an error message.
                 Includes 'overall', 'by_shot_type', 'by_contest', 'by_shot_distance',
                 and 'by_rebound_distance' categories.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_team_rebounding_stats_logic for: {team_identifier}, Season: {season}, PerMode: {per_mode}, return_dataframe={return_dataframe}")

    # Store DataFrames if requested
    dataframes = {}

    validation_error_msg = _validate_team_tracking_params(team_identifier, season)
    if validation_error_msg:
        if return_dataframe:
            return validation_error_msg, dataframes
        return validation_error_msg

    if date_from and not validate_date_format(date_from):
        error_response = format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if date_to and not validate_date_format(date_to):
        error_response = format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if season_type not in _TEAM_REB_VALID_SEASON_TYPES:
        error_response = format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_TEAM_REB_VALID_SEASON_TYPES)[:5])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if per_mode not in _TEAM_REB_VALID_PER_MODES:
        error_response = format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_TEAM_REB_VALID_PER_MODES)[:5])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    error_resp, team_id_resolved, team_name_resolved = _get_team_info_for_tracking(team_identifier, None)
    if error_resp:
        if return_dataframe:
            return error_resp, dataframes
        return error_resp

    if team_id_resolved is None or team_name_resolved is None: # Should be caught by error_resp
        error_response = format_response(error=Errors.TEAM_INFO_RESOLUTION_FAILED.format(identifier=team_identifier))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    try:
        logger.debug(f"Fetching teamdashptreb for Team ID: {team_id_resolved}, Season: {season}")
        reb_stats_endpoint = teamdashptreb.TeamDashPtReb(
            team_id=team_id_resolved, season=season, season_type_all_star=season_type,
            per_mode_simple=per_mode, opponent_team_id=opponent_team_id,
            date_from_nullable=date_from, date_to_nullable=date_to, timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"teamdashptreb API call successful for {team_name_resolved}")

        overall_df = reb_stats_endpoint.overall_rebounding.get_data_frame()
        shot_type_df = reb_stats_endpoint.shot_type_rebounding.get_data_frame()
        contested_df = reb_stats_endpoint.num_contested_rebounding.get_data_frame()
        distances_df = reb_stats_endpoint.shot_distance_rebounding.get_data_frame()
        reb_dist_df = reb_stats_endpoint.reb_distance_rebounding.get_data_frame()

        if return_dataframe:
            dataframes["overall"] = overall_df
            dataframes["shot_type"] = shot_type_df
            dataframes["contest"] = contested_df
            dataframes["shot_distance"] = distances_df
            dataframes["reb_distance"] = reb_dist_df

            # Save DataFrames to CSV if not empty
            if not overall_df.empty:
                csv_path = _get_csv_path_for_team_rebounding(
                    team_name_resolved, season, season_type, per_mode, "overall"
                )
                _save_dataframe_to_csv(overall_df, csv_path)

            if not shot_type_df.empty:
                csv_path = _get_csv_path_for_team_rebounding(
                    team_name_resolved, season, season_type, per_mode, "shot_type"
                )
                _save_dataframe_to_csv(shot_type_df, csv_path)

            if not contested_df.empty:
                csv_path = _get_csv_path_for_team_rebounding(
                    team_name_resolved, season, season_type, per_mode, "contest"
                )
                _save_dataframe_to_csv(contested_df, csv_path)

            if not distances_df.empty:
                csv_path = _get_csv_path_for_team_rebounding(
                    team_name_resolved, season, season_type, per_mode, "shot_distance"
                )
                _save_dataframe_to_csv(distances_df, csv_path)

            if not reb_dist_df.empty:
                csv_path = _get_csv_path_for_team_rebounding(
                    team_name_resolved, season, season_type, per_mode, "reb_distance"
                )
                _save_dataframe_to_csv(reb_dist_df, csv_path)

        overall_data = _process_dataframe(overall_df, single_row=True)
        shot_type_list = _process_dataframe(shot_type_df, single_row=False)
        contested_list = _process_dataframe(contested_df, single_row=False)
        distances_list = _process_dataframe(distances_df, single_row=False)
        reb_dist_list = _process_dataframe(reb_dist_df, single_row=False)

        if all(data is None for data in [overall_data, shot_type_list, contested_list, distances_list, reb_dist_list]):
            if all(df.empty for df in [overall_df, shot_type_df, contested_df, distances_df, reb_dist_df]):
                logger.warning(f"No rebounding stats found for team {team_name_resolved} with given filters.")

                response_data = {
                    "team_id": team_id_resolved, "team_name": team_name_resolved, "season": season, "season_type": season_type,
                    "parameters": {"per_mode": per_mode, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to},
                    "overall": {}, "by_shot_type": [], "by_contest": [],
                    "by_shot_distance": [], "by_rebound_distance": []
                }

                if return_dataframe:
                    return format_response(response_data), dataframes
                return format_response(response_data)
            else:
                logger.error(f"DataFrame processing failed for rebounding stats of {team_name_resolved}.")
                error_msg = Errors.TEAM_REBOUNDING_PROCESSING.format(identifier=str(team_id_resolved))
                error_response = format_response(error=error_msg)

                if return_dataframe:
                    return error_response, dataframes
                return error_response

        result = {
            "team_id": team_id_resolved, "team_name": team_name_resolved, "season": season, "season_type": season_type,
            "parameters": {"per_mode": per_mode, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to},
            "overall": overall_data or {}, "by_shot_type": shot_type_list or [],
            "by_contest": contested_list or [], "by_shot_distance": distances_list or [],
            "by_rebound_distance": reb_dist_list or []
        }

        # Add DataFrame metadata to the response if returning DataFrames
        if return_dataframe:
            result["dataframe_info"] = {
                "message": "Team rebounding tracking data has been converted to DataFrames and saved as CSV files",
                "dataframes": {}
            }

            # Add metadata for each DataFrame if not empty
            dataframe_types = {
                "overall": overall_df,
                "shot_type": shot_type_df,
                "contest": contested_df,
                "shot_distance": distances_df,
                "reb_distance": reb_dist_df
            }

            for df_key, df in dataframe_types.items():
                if not df.empty:
                    csv_path = _get_csv_path_for_team_rebounding(
                        team_name_resolved, season, season_type, per_mode, df_key
                    )
                    csv_filename = os.path.basename(csv_path)
                    relative_path = get_relative_cache_path(csv_filename, "team_rebounding")

                    result["dataframe_info"]["dataframes"][df_key] = {
                        "shape": list(df.shape),
                        "columns": df.columns.tolist(),
                        "csv_path": relative_path
                    }

        logger.info(f"fetch_team_rebounding_stats_logic completed for {team_name_resolved}")

        if return_dataframe:
            return format_response(result), dataframes
        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching rebounding stats for team {team_identifier}: {str(e)}", exc_info=True)
        error_msg = Errors.TEAM_REBOUNDING_UNEXPECTED.format(identifier=team_identifier, error=str(e))
        error_response = format_response(error=error_msg)

        if return_dataframe:
            return error_response, dataframes
        return error_response
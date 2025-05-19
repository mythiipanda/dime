"""
Handles fetching team-level shooting tracking statistics using the TeamDashPtShots endpoint.
Utilizes shared utilities for team identification and parameter validation.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
import pandas as pd
from typing import Optional, Set, Dict, Union, Tuple # For type hinting validation sets
from functools import lru_cache

from nba_api.stats.endpoints import teamdashptshots
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

from ..config import settings
from ..core.errors import Errors
from .utils import _process_dataframe, format_response
from ..utils.validation import validate_date_format
from .team_tracking_utils import _validate_team_tracking_params, _get_team_info_for_tracking
from .http_client import nba_session # For session patching

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
TEAM_SHOOTING_TRACKING_CACHE_SIZE = 128
NBA_API_DEFAULT_OPPONENT_TEAM_ID = 0 # Standard value for no specific opponent filter

_TEAM_SHOOTING_VALID_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_TEAM_SHOOTING_VALID_PER_MODES: Set[str] = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}

# Apply session patch to the endpoint class for custom HTTP client usage
teamdashptshots.requests = nba_session

# --- Cache Directory Setup ---
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
TEAM_SHOOTING_CSV_DIR = os.path.join(CSV_CACHE_DIR, "team_shooting")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(TEAM_SHOOTING_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_team_shooting(
    team_name: str,
    season: str,
    season_type: str,
    per_mode: str,
    data_type: str
) -> str:
    """
    Generates a file path for saving team shooting DataFrame as CSV.

    Args:
        team_name: The team's name
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        per_mode: The per mode (e.g., 'PerGame', 'Totals')
        data_type: The type of data ('general', 'shot_clock', 'dribble', 'defender', 'touch_time')

    Returns:
        Path to the CSV file
    """
    # Clean team name and data type for filename
    clean_team_name = team_name.replace(" ", "_").replace(".", "").lower()
    clean_season_type = season_type.replace(" ", "_").lower()
    clean_per_mode = per_mode.replace(" ", "_").lower()

    filename = f"{clean_team_name}_{season}_{clean_season_type}_{clean_per_mode}_{data_type}.csv"
    return os.path.join(TEAM_SHOOTING_CSV_DIR, filename)

# --- Main Logic Function ---
def fetch_team_shooting_stats_logic(
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
    Fetches team shooting statistics, categorized by various factors like shot clock,
    number of dribbles, defender distance, and touch time, using the TeamDashPtShots endpoint.
    Provides DataFrame output capabilities.

    The 'general_shooting' dataset from the API often contains an overall summary row
    followed by breakdown rows (e.g., by shot type). This logic separates these.

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
            str: JSON string with team shooting stats or an error message.
                 Includes 'overall_shooting', 'general_shooting_splits', 'by_shot_clock',
                 'by_dribble', 'by_defender_distance', and 'by_touch_time'.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_team_shooting_stats_logic for: {team_identifier}, Season: {season}, PerMode: {per_mode}, return_dataframe={return_dataframe}")

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

    if season_type not in _TEAM_SHOOTING_VALID_SEASON_TYPES:
        error_response = format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_TEAM_SHOOTING_VALID_SEASON_TYPES)[:5])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if per_mode not in _TEAM_SHOOTING_VALID_PER_MODES:
        error_response = format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_TEAM_SHOOTING_VALID_PER_MODES)[:5])))
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
        logger.debug(f"Fetching teamdashptshots for Team ID: {team_id_resolved}, Season: {season}")
        shot_stats_endpoint = teamdashptshots.TeamDashPtShots(
            team_id=team_id_resolved, season=season, season_type_all_star=season_type,
            per_mode_simple=per_mode, opponent_team_id=opponent_team_id,
            date_from_nullable=date_from, date_to_nullable=date_to, timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"teamdashptshots API call successful for {team_name_resolved}")

        general_df = shot_stats_endpoint.general_shooting.get_data_frame()
        shot_clock_df = shot_stats_endpoint.shot_clock_shooting.get_data_frame()
        dribbles_df = shot_stats_endpoint.dribble_shooting.get_data_frame()
        defender_df = shot_stats_endpoint.closest_defender_shooting.get_data_frame()
        touch_time_df = shot_stats_endpoint.touch_time_shooting.get_data_frame()

        if return_dataframe:
            # Store the original DataFrames
            dataframes["general"] = general_df
            dataframes["shot_clock"] = shot_clock_df
            dataframes["dribble"] = dribbles_df
            dataframes["defender"] = defender_df
            dataframes["touch_time"] = touch_time_df

            # Save DataFrames to CSV if not empty
            if not general_df.empty:
                csv_path = _get_csv_path_for_team_shooting(
                    team_name_resolved, season, season_type, per_mode, "general"
                )
                _save_dataframe_to_csv(general_df, csv_path)

            if not shot_clock_df.empty:
                csv_path = _get_csv_path_for_team_shooting(
                    team_name_resolved, season, season_type, per_mode, "shot_clock"
                )
                _save_dataframe_to_csv(shot_clock_df, csv_path)

            if not dribbles_df.empty:
                csv_path = _get_csv_path_for_team_shooting(
                    team_name_resolved, season, season_type, per_mode, "dribble"
                )
                _save_dataframe_to_csv(dribbles_df, csv_path)

            if not defender_df.empty:
                csv_path = _get_csv_path_for_team_shooting(
                    team_name_resolved, season, season_type, per_mode, "defender"
                )
                _save_dataframe_to_csv(defender_df, csv_path)

            if not touch_time_df.empty:
                csv_path = _get_csv_path_for_team_shooting(
                    team_name_resolved, season, season_type, per_mode, "touch_time"
                )
                _save_dataframe_to_csv(touch_time_df, csv_path)

        # Process DataFrames for JSON response
        overall_shooting_data = _process_dataframe(general_df.head(1) if not general_df.empty else pd.DataFrame(), single_row=True)
        general_splits_list = _process_dataframe(general_df.iloc[1:] if len(general_df) > 1 else pd.DataFrame(), single_row=False)

        shot_clock_list = _process_dataframe(shot_clock_df, single_row=False)
        dribbles_list = _process_dataframe(dribbles_df, single_row=False)
        defender_list = _process_dataframe(defender_df, single_row=False)
        touch_time_list = _process_dataframe(touch_time_df, single_row=False)

        if overall_shooting_data is None and not general_df.empty:
            logger.error(f"DataFrame processing failed for general shooting stats of {team_name_resolved}.")
            error_msg = Errors.TEAM_SHOOTING_PROCESSING.format(identifier=str(team_id_resolved))
            error_response = format_response(error=error_msg)

            if return_dataframe:
                return error_response, dataframes
            return error_response

        if general_df.empty:
            logger.warning(f"No shooting stats found for team {team_name_resolved} with given filters.")

            response_data = {
                "team_id": team_id_resolved, "team_name": team_name_resolved, "season": season, "season_type": season_type,
                "parameters": {"per_mode": per_mode, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to},
                "overall_shooting": {}, "general_shooting_splits": [], "by_shot_clock": [],
                "by_dribble": [], "by_defender_distance": [], "by_touch_time": []
            }

            if return_dataframe:
                return format_response(response_data), dataframes
            return format_response(response_data)

        result = {
            "team_id": team_id_resolved, "team_name": team_name_resolved, "season": season, "season_type": season_type,
            "parameters": {"per_mode": per_mode, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to},
            "overall_shooting": overall_shooting_data or {},
            "general_shooting_splits": general_splits_list or [],
            "by_shot_clock": shot_clock_list or [],
            "by_dribble": dribbles_list or [],
            "by_defender_distance": defender_list or [],
            "by_touch_time": touch_time_list or []
        }
        logger.info(f"fetch_team_shooting_stats_logic completed for {team_name_resolved}")

        if return_dataframe:
            return format_response(result), dataframes
        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching shooting stats for team {team_identifier}: {str(e)}", exc_info=True)
        error_msg = Errors.TEAM_SHOOTING_UNEXPECTED.format(identifier=team_identifier, error=str(e))
        error_response = format_response(error=error_msg)

        if return_dataframe:
            return error_response, dataframes
        return error_response
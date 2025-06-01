"""
Handles fetching team dashboard statistics by shooting splits.
Provides both JSON and DataFrame outputs with CSV caching.

This module implements the TeamDashboardByShootingSplits endpoint, which provides
detailed team shooting statistics broken down by various splits:
- Overall shooting stats
- Shot type (jump shots, layups, etc.)
- Shot area (restricted area, paint, mid-range, etc.)
- Shot distance (0-5 ft, 5-8 ft, etc.)
- Assisted/unassisted shots
"""
import os
import logging
import json
from typing import Optional, Dict, Any, Union, Tuple, List
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import teamdashboardbyshootingsplits
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailedDefense
)
from config import settings
from core.errors import Errors
from api_tools.utils import (
    _process_dataframe,
    format_response,
    find_team_id_or_error,
    TeamNotFoundError
)
from utils.path_utils import get_cache_dir, get_cache_file_path

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
TEAM_DASHBOARD_SHOOTING_CACHE_SIZE = 128
TEAM_DASHBOARD_SHOOTING_CSV_DIR = get_cache_dir("team_dashboard_shooting")

# Valid parameter values
VALID_MEASURE_TYPES = {
    "Base": MeasureTypeDetailedDefense.base,
    "Advanced": MeasureTypeDetailedDefense.advanced,
    "Misc": MeasureTypeDetailedDefense.misc,
    "Four Factors": MeasureTypeDetailedDefense.four_factors,
    "Scoring": MeasureTypeDetailedDefense.scoring,
    "Opponent": MeasureTypeDetailedDefense.opponent,
    "Usage": MeasureTypeDetailedDefense.usage,
    "Defense": MeasureTypeDetailedDefense.defense
}

VALID_PER_MODES = {
    "Totals": PerModeDetailed.totals,
    "PerGame": PerModeDetailed.per_game,
    "MinutesPer": PerModeDetailed.minutes_per,
    "Per48": PerModeDetailed.per_48,
    "Per40": PerModeDetailed.per_40,
    "Per36": PerModeDetailed.per_36,
    "PerMinute": PerModeDetailed.per_minute,
    "PerPossession": PerModeDetailed.per_possession,
    "PerPlay": PerModeDetailed.per_play,
    "Per100Possessions": PerModeDetailed.per_100_possessions,
    "Per100Plays": PerModeDetailed.per_100_plays
}

VALID_SEASON_TYPES = {
    "Regular Season": SeasonTypeAllStar.regular,
    "Playoffs": SeasonTypeAllStar.playoffs,
    "Pre Season": SeasonTypeAllStar.preseason,
    "All Star": SeasonTypeAllStar.all_star
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

def _get_csv_path_for_dashboard(
    team_id: str,
    season: str,
    season_type: str,
    per_mode: str,
    measure_type: str,
    dashboard_type: str
) -> str:
    """
    Generates a file path for saving a dashboard DataFrame as CSV.

    Args:
        team_id: The team ID
        season: The season in YYYY-YY format
        season_type: The season type (e.g., Regular Season, Playoffs)
        per_mode: The per mode (e.g., Totals, PerGame)
        measure_type: The measure type (e.g., Base, Advanced)
        dashboard_type: The dashboard type (e.g., overall_team_dashboard)

    Returns:
        Path to the CSV file
    """
    # Clean up parameters for filename
    season_clean = season.replace("-", "_")
    season_type_clean = season_type.replace(" ", "_").lower()
    per_mode_clean = per_mode.replace(" ", "_").lower()
    measure_type_clean = measure_type.replace(" ", "_").lower()

    # Create filename
    filename = f"{team_id}_{season_clean}_{season_type_clean}_{per_mode_clean}_{measure_type_clean}_{dashboard_type}.csv"

    return get_cache_file_path(filename, "team_dashboard_shooting")

# --- Parameter Validation Functions ---
def _validate_dashboard_params(
    team_identifier: str,
    season: str,
    season_type: str,
    measure_type: str,
    per_mode: str
) -> Optional[str]:
    """
    Validates parameters for the team dashboard function.

    Args:
        team_identifier: Team name, abbreviation, or ID
        season: Season in YYYY-YY format
        season_type: Season type (e.g., Regular Season, Playoffs)
        measure_type: Measure type (e.g., Base, Advanced)
        per_mode: Per mode (e.g., Totals, PerGame)

    Returns:
        Error message if validation fails, None otherwise
    """
    if not team_identifier:
        return Errors.TEAM_IDENTIFIER_EMPTY

    if not season:
        return Errors.SEASON_EMPTY

    if season_type not in VALID_SEASON_TYPES:
        return Errors.INVALID_SEASON_TYPE.format(
            value=season_type,
            options=", ".join(list(VALID_SEASON_TYPES.keys()))
        )

    if measure_type not in VALID_MEASURE_TYPES:
        return Errors.INVALID_MEASURE_TYPE.format(
            value=measure_type,
            options=", ".join(list(VALID_MEASURE_TYPES.keys()))
        )

    if per_mode not in VALID_PER_MODES:
        return Errors.INVALID_PER_MODE.format(
            value=per_mode,
            options=", ".join(list(VALID_PER_MODES.keys()))
        )

    return None

# --- Main Logic Function ---
@lru_cache(maxsize=TEAM_DASHBOARD_SHOOTING_CACHE_SIZE)
def fetch_team_dashboard_shooting_splits_logic(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    measure_type: str = "Base",
    per_mode: str = "Totals",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches team dashboard statistics by shooting splits using the TeamDashboardByShootingSplits endpoint.

    This endpoint provides detailed team shooting statistics broken down by various splits:
    - Overall shooting stats
    - Shot type (jump shots, layups, etc.)
    - Shot area (restricted area, paint, mid-range, etc.)
    - Shot distance (0-5 ft, 5-8 ft, etc.)
    - Assisted/unassisted shots

    Args:
        team_identifier (str): Name, abbreviation, or ID of the team
        season (str, optional): Season in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        measure_type (str, optional): Statistical category. Defaults to "Base".
        per_mode (str, optional): Per mode for stats. Defaults to "Totals".
        return_dataframe (bool, optional): Whether to return DataFrames. Defaults to False.

    Returns:
        If return_dataframe=False:
            str: JSON string with dashboard data or error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: JSON response and dictionary of DataFrames.
    """
    logger.info(
        f"Executing fetch_team_dashboard_shooting_splits_logic for: '{team_identifier}', "
        f"Season: {season}, Measure: {measure_type}, PerMode: {per_mode}"
    )

    dataframes: Dict[str, pd.DataFrame] = {}

    # Validate parameters
    validation_error = _validate_dashboard_params(
        team_identifier, season, season_type, measure_type, per_mode
    )
    if validation_error:
        if return_dataframe:
            return format_response(error=validation_error), dataframes
        return format_response(error=validation_error)

    # Get team ID
    try:
        team_id_val, team_actual_name = find_team_id_or_error(team_identifier)
    except TeamNotFoundError as e:
        error_msg = str(e)
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    # Prepare API parameters - using only parameters that work based on testing
    api_params = {
        "team_id": team_id_val,
        "season": season,
        "season_type_all_star": VALID_SEASON_TYPES[season_type],
        "measure_type_detailed_defense": VALID_MEASURE_TYPES[measure_type],
        "per_mode_detailed": VALID_PER_MODES[per_mode],
        "plus_minus": "N",
        "pace_adjust": "N",
        "rank": "N",
        "league_id_nullable": "00",
        "last_n_games": 0,
        "month": 0,
        "opponent_team_id": 0,
        "period": 0,
        "timeout": settings.DEFAULT_TIMEOUT_SECONDS
    }

    # Filter out None values for cleaner logging
    filtered_api_params = {k: v for k, v in api_params.items() if v is not None and k != "timeout"}

    try:
        logger.debug(f"Calling TeamDashboardByShootingSplits with parameters: {filtered_api_params}")
        dashboard_endpoint = teamdashboardbyshootingsplits.TeamDashboardByShootingSplits(**api_params)

        # Get normalized dictionary for data set names
        normalized_dict = dashboard_endpoint.get_normalized_dict()

        # Get data frames
        list_of_dataframes = dashboard_endpoint.get_data_frames()

        # Expected data set names based on documentation
        expected_data_set_names = [
            "OverallTeamDashboard",
            "Shot5FTTeamDashboard",
            "Shot8FTTeamDashboard",
            "ShotAreaTeamDashboard",
            "ShotTypeTeamDashboard",
            "AssitedShotTeamDashboard",
            "AssistedBy"
        ]

        # Get data set names from the result sets
        data_set_names = []
        if "resultSets" in normalized_dict:
            data_set_names = list(normalized_dict["resultSets"].keys())
        else:
            # If no result sets found, use expected names
            data_set_names = expected_data_set_names

        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "team_name": team_actual_name,
            "team_id": team_id_val,
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
                        csv_path = _get_csv_path_for_dashboard(
                            team_id_val, season, season_type, per_mode, measure_type, data_set_name
                        )
                        _save_dataframe_to_csv(df, csv_path)

                # Process for JSON response
                processed_data = _process_dataframe(df, single_row=False)
                result_dict["data_sets"][data_set_name] = processed_data

        # Return response
        logger.info(f"Successfully fetched shooting splits dashboard for {team_actual_name}")
        if return_dataframe:
            return format_response(result_dict), dataframes
        return format_response(result_dict)

    except Exception as e:
        logger.error(
            f"API error in fetch_team_dashboard_shooting_splits_logic for {team_identifier}: {e}",
            exc_info=True
        )
        error_msg = Errors.TEAM_DASHBOARD_SHOOTING_API.format(
            team_identifier=team_identifier, error=str(e)
        )
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

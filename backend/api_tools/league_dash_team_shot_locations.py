"""
Handles fetching team shot location statistics across the league.
Provides both JSON and DataFrame outputs with CSV caching.

This module implements the LeagueDashTeamShotLocations endpoint, which provides
comprehensive shot location statistics for teams across the league:
- Restricted Area
- In The Paint (Non-RA)
- Mid-Range
- Left Corner 3
- Right Corner 3
- Above the Break 3
- Backcourt
"""
import os
import logging
import json
from typing import Optional, Dict, Any, Union, Tuple, List, Set
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import leaguedashteamshotlocations
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, MeasureTypeSimple, DistanceRange
)
from config import settings
from core.errors import Errors
from api_tools.utils import (
    _process_dataframe,
    format_response
)
from utils.path_utils import get_cache_dir, get_cache_file_path
from utils.validation import _validate_season_format, validate_date_format

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
LEAGUE_DASH_TEAM_SHOT_LOCATIONS_CACHE_SIZE = 128
LEAGUE_DASH_TEAM_SHOT_LOCATIONS_CSV_DIR = get_cache_dir("league_dash_team_shot_locations")

# Valid parameter values
_VALID_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar)
                               if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}

_VALID_PER_MODES: Set[str] = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed)
                            if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}

_VALID_MEASURE_TYPES: Set[str] = {getattr(MeasureTypeSimple, attr) for attr in dir(MeasureTypeSimple)
                                if not attr.startswith('_') and isinstance(getattr(MeasureTypeSimple, attr), str)}

_VALID_DISTANCE_RANGES: Set[str] = {getattr(DistanceRange, attr) for attr in dir(DistanceRange)
                                  if not attr.startswith('_') and isinstance(getattr(DistanceRange, attr), str)}

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

def _get_csv_path_for_team_shot_locations(
    season: str,
    season_type: str,
    per_mode: str,
    measure_type: str,
    distance_range: str,
    conference: Optional[str] = None,
    division: Optional[str] = None
) -> str:
    """
    Generates a file path for saving a league team shot locations DataFrame as CSV.

    Args:
        season: The season in YYYY-YY format
        season_type: The season type (e.g., Regular Season, Playoffs)
        per_mode: The per mode (e.g., Totals, PerGame)
        measure_type: The measure type (e.g., Base, Opponent)
        distance_range: The distance range (e.g., By Zone, 5ft Range)
        conference: Optional conference filter
        division: Optional division filter

    Returns:
        Path to the CSV file
    """
    # Clean up parameters for filename
    season_clean = season.replace("-", "_")
    season_type_clean = season_type.replace(" ", "_").lower()
    per_mode_clean = per_mode.replace(" ", "_").lower()
    measure_type_clean = measure_type.replace(" ", "_").lower()
    distance_range_clean = distance_range.replace(" ", "_").lower()

    # Create filename with optional filters
    filename_parts = [
        f"team_shot_locations_{season_clean}_{season_type_clean}_{per_mode_clean}_{measure_type_clean}_{distance_range_clean}"
    ]

    if conference:
        conference_clean = conference.lower()
        filename_parts.append(f"conf_{conference_clean}")

    if division:
        division_clean = division.replace(" ", "_").lower()
        filename_parts.append(f"div_{division_clean}")

    filename = "_".join(filename_parts) + ".csv"

    return get_cache_file_path(filename, "league_dash_team_shot_locations")

# --- Main Logic Function ---
def fetch_league_team_shot_locations_logic(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    measure_type: str = MeasureTypeSimple.base,
    distance_range: str = DistanceRange.by_zone,
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    pace_adjust: str = "N",
    plus_minus: str = "N",
    rank: str = "N",
    period: int = 0,
    team_id_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    league_id_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    po_round_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    shot_clock_range_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    conference_nullable: Optional[str] = None,
    division_nullable: Optional[str] = None,
    game_scope_nullable: Optional[str] = None,
    player_experience_nullable: Optional[str] = None,
    player_position_nullable: Optional[str] = None,
    starter_bench_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches team shot location statistics across the league using the LeagueDashTeamShotLocations endpoint.

    This endpoint provides comprehensive shot location statistics for teams:
    - Restricted Area
    - In The Paint (Non-RA)
    - Mid-Range
    - Left Corner 3
    - Right Corner 3
    - Above the Break 3
    - Backcourt

    Args:
        season: Season in YYYY-YY format. Defaults to current season.
        season_type: Season type. Defaults to Regular Season.
        per_mode: Per mode for stats. Defaults to PerGame.
        measure_type: Statistical category. Defaults to Base.
        distance_range: Shot distance range. Defaults to By Zone.
        last_n_games: Last N games filter. Defaults to 0 (all games).
        month: Month filter (0-12). Defaults to 0 (all months).
        opponent_team_id: Opponent team ID filter. Defaults to 0 (all teams).
        pace_adjust: Whether to adjust for pace. Defaults to "N".
        plus_minus: Whether to include plus/minus. Defaults to "N".
        rank: Whether to include rankings. Defaults to "N".
        period: Period filter (0-4). Defaults to 0 (all periods).
        team_id_nullable: Team ID filter. Defaults to None.
        date_from_nullable: Start date filter (YYYY-MM-DD). Defaults to None.
        date_to_nullable: End date filter (YYYY-MM-DD). Defaults to None.
        game_segment_nullable: Game segment filter. Defaults to None.
        league_id_nullable: League ID. Defaults to None.
        location_nullable: Location filter (Home/Road). Defaults to None.
        outcome_nullable: Outcome filter (W/L). Defaults to None.
        po_round_nullable: Playoff round filter. Defaults to None.
        season_segment_nullable: Season segment filter. Defaults to None.
        shot_clock_range_nullable: Shot clock range filter. Defaults to None.
        vs_conference_nullable: Conference filter for opponents. Defaults to None.
        vs_division_nullable: Division filter for opponents. Defaults to None.
        conference_nullable: Conference filter for teams. Defaults to None.
        division_nullable: Division filter for teams. Defaults to None.
        game_scope_nullable: Game scope filter. Defaults to None.
        player_experience_nullable: Player experience filter. Defaults to None.
        player_position_nullable: Player position filter. Defaults to None.
        starter_bench_nullable: Starter/bench filter. Defaults to None.
        return_dataframe: Whether to return DataFrames. Defaults to False.

    Returns:
        If return_dataframe=False:
            str: JSON string with team shot location stats data or error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: JSON response and dictionary of DataFrames.
    """
    logger.info(
        f"Executing fetch_league_team_shot_locations_logic for: "
        f"Season: {season}, Type: {season_type}, Measure Type: {measure_type}, Distance Range: {distance_range}"
    )

    dataframes: Dict[str, pd.DataFrame] = {}

    # Parameter validation
    if not season or not _validate_season_format(season):
        error_response = format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if season_type not in _VALID_SEASON_TYPES:
        error_response = format_response(error=Errors.INVALID_SEASON_TYPE.format(
            value=season_type, options=", ".join(list(_VALID_SEASON_TYPES)[:5])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if per_mode not in _VALID_PER_MODES:
        error_response = format_response(error=Errors.INVALID_PER_MODE.format(
            value=per_mode, options=", ".join(list(_VALID_PER_MODES)[:5])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if measure_type not in _VALID_MEASURE_TYPES:
        error_response = format_response(error=Errors.INVALID_MEASURE_TYPE.format(
            value=measure_type, options=", ".join(list(_VALID_MEASURE_TYPES)[:5])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if distance_range not in _VALID_DISTANCE_RANGES:
        error_response = format_response(error=f"Invalid distance_range: '{distance_range}'. Valid options: {', '.join(list(_VALID_DISTANCE_RANGES))}")
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if date_from_nullable and not validate_date_format(date_from_nullable):
        error_response = format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from_nullable))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if date_to_nullable and not validate_date_format(date_to_nullable):
        error_response = format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to_nullable))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    try:
        # Prepare API parameters
        api_params = {
            "season": season,
            "season_type_all_star": season_type,
            "per_mode_detailed": per_mode,
            "measure_type_simple": measure_type,
            "distance_range": distance_range,
            "last_n_games": last_n_games,
            "month": month,
            "opponent_team_id": opponent_team_id,
            "pace_adjust": pace_adjust,
            "plus_minus": plus_minus,
            "rank": rank,
            "period": period,
            "timeout": settings.DEFAULT_TIMEOUT_SECONDS
        }

        # Add optional parameters if provided
        if team_id_nullable:
            api_params["team_id_nullable"] = team_id_nullable
        if date_from_nullable:
            api_params["date_from_nullable"] = date_from_nullable
        if date_to_nullable:
            api_params["date_to_nullable"] = date_to_nullable
        if game_segment_nullable:
            api_params["game_segment_nullable"] = game_segment_nullable
        if league_id_nullable:
            api_params["league_id_nullable"] = league_id_nullable
        if location_nullable:
            api_params["location_nullable"] = location_nullable
        if outcome_nullable:
            api_params["outcome_nullable"] = outcome_nullable
        if po_round_nullable:
            api_params["po_round_nullable"] = po_round_nullable
        if season_segment_nullable:
            api_params["season_segment_nullable"] = season_segment_nullable
        if shot_clock_range_nullable:
            api_params["shot_clock_range_nullable"] = shot_clock_range_nullable
        if vs_conference_nullable:
            api_params["vs_conference_nullable"] = vs_conference_nullable
        if vs_division_nullable:
            api_params["vs_division_nullable"] = vs_division_nullable
        if conference_nullable:
            api_params["conference_nullable"] = conference_nullable
        if division_nullable:
            api_params["division_nullable"] = division_nullable
        if game_scope_nullable:
            api_params["game_scope_nullable"] = game_scope_nullable
        if player_experience_nullable:
            api_params["player_experience_nullable"] = player_experience_nullable
        if player_position_nullable:
            api_params["player_position_nullable"] = player_position_nullable
        if starter_bench_nullable:
            api_params["starter_bench_nullable"] = starter_bench_nullable

        # Filter out None values for cleaner logging
        filtered_api_params = {k: v for k, v in api_params.items() if v is not None and k != "timeout"}

        logger.debug(f"Calling LeagueDashTeamShotLocations with parameters: {filtered_api_params}")
        shot_locations_endpoint = leaguedashteamshotlocations.LeagueDashTeamShotLocations(**api_params)

        # Get data frames
        shot_locations_df = shot_locations_endpoint.get_data_frames()[0]

        # Store DataFrame if requested
        if return_dataframe:
            dataframes["ShotLocations"] = shot_locations_df

            # Save to CSV if not empty
            if not shot_locations_df.empty:
                csv_path = _get_csv_path_for_team_shot_locations(
                    season, season_type, per_mode, measure_type, distance_range,
                    conference_nullable, division_nullable
                )
                _save_dataframe_to_csv(shot_locations_df, csv_path)

        # The shot locations DataFrame has multi-level columns which need special handling
        # First, flatten the column names to make them JSON serializable
        flattened_df = shot_locations_df.copy()

        # Create flattened column names
        flattened_columns = []
        for col in shot_locations_df.columns:
            if isinstance(col, tuple):
                # Join the tuple elements with an underscore, but skip empty strings
                parts = [str(part) for part in col if part]
                flattened_columns.append("_".join(parts))
            else:
                flattened_columns.append(str(col))

        # Set the new column names
        flattened_df.columns = flattened_columns

        # Process for JSON response
        processed_data = _process_dataframe(flattened_df, single_row=False)

        # Create result dictionary
        result_dict = {
            "parameters": filtered_api_params,
            "shot_locations": processed_data or []
        }

        # Return response
        logger.info(f"Successfully fetched team shot locations for {season} {season_type}")
        if return_dataframe:
            return format_response(result_dict), dataframes
        return format_response(result_dict)

    except Exception as e:
        logger.error(
            f"API error in fetch_league_team_shot_locations_logic: {e}",
            exc_info=True
        )
        error_msg = f"Error fetching team shot locations: {str(e)}"
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

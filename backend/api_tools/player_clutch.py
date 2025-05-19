"""
Handles fetching and processing player clutch performance statistics
from the PlayerDashboardByClutch endpoint.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple, List
from functools import lru_cache

from nba_api.stats.endpoints import playerdashboardbyclutch
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailed
)
import pandas as pd

from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)
from ..utils.validation import _validate_season_format, validate_date_format

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
PLAYER_CLUTCH_CACHE_SIZE = 64

_VALID_CLUTCH_SEASON_TYPES: Set[str] = {SeasonTypeAllStar.regular, SeasonTypeAllStar.playoffs, SeasonTypeAllStar.preseason}
_VALID_CLUTCH_PER_MODES: Set[str] = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
_VALID_CLUTCH_MEASURE_TYPES: Set[str] = {getattr(MeasureTypeDetailed, attr) for attr in dir(MeasureTypeDetailed) if not attr.startswith('_') and isinstance(getattr(MeasureTypeDetailed, attr), str)}
_VALID_Y_N_CLUTCH: Set[str] = {"Y", "N", ""} # Used for plus_minus, pace_adjust, rank

# --- Cache Directory Setup ---
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
PLAYER_CLUTCH_CSV_DIR = os.path.join(CSV_CACHE_DIR, "player_clutch")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(PLAYER_CLUTCH_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_player_clutch(
    player_name: str,
    season: str,
    season_type: str,
    dashboard_name: str
) -> str:
    """
    Generates a file path for saving player clutch DataFrame as CSV.

    Args:
        player_name: The player's name
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        dashboard_name: The name of the clutch dashboard

    Returns:
        Path to the CSV file
    """
    # Clean player name and dashboard name for filename
    clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()
    clean_season_type = season_type.replace(" ", "_").lower()
    clean_dashboard = dashboard_name.replace(" ", "_").lower()

    filename = f"{clean_player_name}_{season}_{clean_season_type}_{clean_dashboard}.csv"
    return os.path.join(PLAYER_CLUTCH_CSV_DIR, filename)

# --- Helper for Parameter Validation ---
def _validate_clutch_params(
    player_name: str, season: str, season_type: str, measure_type: str, per_mode: str,
    plus_minus: str, pace_adjust: str, rank: str,
    date_from_nullable: Optional[str], date_to_nullable: Optional[str]
) -> Optional[str]:
    """Validates parameters for fetch_player_clutch_stats_logic."""
    if not player_name or not player_name.strip():
        return Errors.PLAYER_NAME_EMPTY
    if not season or not _validate_season_format(season):
        return Errors.INVALID_SEASON_FORMAT.format(season=season)
    if date_from_nullable and not validate_date_format(date_from_nullable):
        return Errors.INVALID_DATE_FORMAT.format(date=date_from_nullable)
    if date_to_nullable and not validate_date_format(date_to_nullable):
        return Errors.INVALID_DATE_FORMAT.format(date=date_to_nullable)
    if season_type not in _VALID_CLUTCH_SEASON_TYPES:
        return Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_CLUTCH_SEASON_TYPES)[:5]))
    if per_mode not in _VALID_CLUTCH_PER_MODES:
        return Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_CLUTCH_PER_MODES)[:5]))
    if measure_type not in _VALID_CLUTCH_MEASURE_TYPES:
        return Errors.INVALID_MEASURE_TYPE.format(value=measure_type, options=", ".join(list(_VALID_CLUTCH_MEASURE_TYPES)[:5]))
    if plus_minus not in _VALID_Y_N_CLUTCH:
        return Errors.INVALID_PLUS_MINUS.format(value=plus_minus)
    if pace_adjust not in _VALID_Y_N_CLUTCH:
        return Errors.INVALID_PACE_ADJUST.format(value=pace_adjust)
    if rank not in _VALID_Y_N_CLUTCH:
        return Errors.INVALID_RANK.format(value=rank)
    return None

# --- Main Logic Function ---
def fetch_player_clutch_stats_logic(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    measure_type: str = MeasureTypeDetailed.base,
    per_mode: str = PerModeDetailed.totals,
    plus_minus: str = "N",
    pace_adjust: str = "N",
    rank: str = "N",
    shot_clock_range_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    period: int = 0,
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    location_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player clutch performance statistics across various clutch scenarios.

    Provides DataFrame output capabilities.

    Args:
        player_name: Name or ID of the player.
        season: Season in YYYY-YY format. Defaults to current.
        season_type: Type of season. Defaults to Regular Season.
        measure_type: Type of stats (Base, Advanced, etc.). Defaults to Base.
        per_mode: Statistical mode (Totals, PerGame, etc.). Defaults to Totals.
        plus_minus: Flag for plus-minus stats ("Y" or "N"). Defaults to "N".
        pace_adjust: Flag for pace adjustment ("Y" or "N"). Defaults to "N".
        rank: Flag for ranking ("Y" or "N"). Defaults to "N".
        shot_clock_range_nullable: Filter by shot clock range.
        game_segment_nullable: Filter by game segment.
        period: Filter by period. Defaults to 0 (all).
        last_n_games: Filter by last N games. Defaults to 0 (all).
        month: Filter by month. Defaults to 0 (all).
        opponent_team_id: Filter by opponent team ID. Defaults to 0 (all).
        location_nullable: Filter by location (Home/Road).
        outcome_nullable: Filter by game outcome (W/L).
        vs_conference_nullable: Filter by opponent conference.
        vs_division_nullable: Filter by opponent division.
        season_segment_nullable: Filter by season segment.
        date_from_nullable: Start date filter (YYYY-MM-DD).
        date_to_nullable: End date filter (YYYY-MM-DD).
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string with clutch stats dashboards or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_player_clutch_stats_logic for: '{player_name}', Season: {season}, Measure: {measure_type}, return_dataframe={return_dataframe}")

    validation_error = _validate_clutch_params(
        player_name, season, season_type, measure_type, per_mode,
        plus_minus, pace_adjust, rank, date_from_nullable, date_to_nullable
    )
    if validation_error:
        logger.warning(f"Parameter validation failed for clutch stats: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching playerdashboardbyclutch for ID: {player_id}, Season: {season}")

        # Call the API
        clutch_endpoint = playerdashboardbyclutch.PlayerDashboardByClutch(
            player_id=player_id, season=season, season_type_playoffs=season_type,
            measure_type_detailed=measure_type,
            per_mode_detailed=per_mode,
            plus_minus=plus_minus,
            pace_adjust=pace_adjust,
            rank=rank,
            shot_clock_range_nullable=shot_clock_range_nullable,
            game_segment_nullable=game_segment_nullable,
            period=period, last_n_games=last_n_games, month=month,
            opponent_team_id=opponent_team_id, location_nullable=location_nullable,
            outcome_nullable=outcome_nullable,
            vs_conference_nullable=vs_conference_nullable,
            vs_division_nullable=vs_division_nullable,
            season_segment_nullable=season_segment_nullable,
            date_from_nullable=date_from_nullable,
            date_to_nullable=date_to_nullable,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"playerdashboardbyclutch API call successful for ID: {player_id}, Season: {season}")

        # Collect all relevant clutch dashboards
        dashboards = [
            "overall_player_dashboard",
            "last5_min5_point_player_dashboard",
            "last3_min5_point_player_dashboard",
            "last1_min5_point_player_dashboard",
            "last5_min_plus_minus5_point_player_dashboard",
            "last3_min_plus_minus5_point_player_dashboard",
            "last1_min_plus_minus5_point_player_dashboard",
            "last10_sec3_point_player_dashboard",
            "last30_sec3_point_player_dashboard",
            "last10_sec3_point2_player_dashboard",
            "last30_sec3_point2_player_dashboard"
        ]

        # Process data for JSON response
        clutch_data = {}

        # Store DataFrames if requested
        dataframes = {}

        for dash in dashboards:
            df_obj = getattr(clutch_endpoint, dash, None)
            if df_obj is not None:
                df = df_obj.get_data_frame()

                # Process for JSON response
                clutch_data[dash] = _process_dataframe(df, single_row=False)

                # Store DataFrame if requested
                if return_dataframe and not df.empty:
                    dataframes[dash] = df

                    # Save DataFrame to CSV if returning DataFrames
                    csv_path = _get_csv_path_for_player_clutch(
                        player_actual_name, season, season_type, dash
                    )
                    _save_dataframe_to_csv(df, csv_path)
            else:
                clutch_data[dash] = []
                if return_dataframe:
                    dataframes[dash] = pd.DataFrame()

        # If all dashboards are empty, treat as no data
        if all(not v for v in clutch_data.values()):
            logger.warning(f"No clutch stats data found for {player_actual_name} in season {season} with specified filters (all dashboards empty).")

            response_data = {
                "player_name": player_actual_name, "player_id": player_id,
                "parameters": {
                    "season": season, "season_type": season_type, "measure_type": measure_type, "per_mode": per_mode,
                    "plus_minus": plus_minus, "pace_adjust": pace_adjust, "rank": rank,
                    "game_segment_nullable": game_segment_nullable, "period": period, "last_n_games": last_n_games,
                    "month": month, "opponent_team_id": opponent_team_id, "location_nullable": location_nullable,
                    "outcome_nullable": outcome_nullable, "vs_conference_nullable": vs_conference_nullable,
                    "vs_division_nullable": vs_division_nullable, "season_segment_nullable": season_segment_nullable,
                    "date_from_nullable": date_from_nullable, "date_to_nullable": date_to_nullable, "shot_clock_range_nullable": shot_clock_range_nullable
                },
                "clutch_dashboards": clutch_data
            }

            if return_dataframe:
                return format_response(response_data), dataframes
            return format_response(response_data)

        # If we reach here, data is valid and processed
        result = {
            "player_name": player_actual_name, "player_id": player_id,
            "parameters": {
                "season": season, "season_type": season_type, "measure_type": measure_type, "per_mode": per_mode,
                "plus_minus": plus_minus, "pace_adjust": pace_adjust, "rank": rank,
                "game_segment_nullable": game_segment_nullable, "period": period, "last_n_games": last_n_games,
                "month": month, "opponent_team_id": opponent_team_id, "location_nullable": location_nullable,
                "outcome_nullable": outcome_nullable, "vs_conference_nullable": vs_conference_nullable,
                "vs_division_nullable": vs_division_nullable, "season_segment_nullable": season_segment_nullable,
                "date_from_nullable": date_from_nullable, "date_to_nullable": date_to_nullable, "shot_clock_range_nullable": shot_clock_range_nullable
            },
            "clutch_dashboards": clutch_data
        }

        logger.info(f"Successfully fetched clutch stats for {player_actual_name}")

        if return_dataframe:
            return format_response(data=result), dataframes
        return format_response(data=result)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_clutch_stats_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_clutch_stats_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_clutch_stats_logic for '{player_name}', Season {season}: {e}", exc_info=True)
        error_msg = Errors.PLAYER_CLUTCH_UNEXPECTED.format(identifier=player_name, season=season, error=str(e))
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response
"""
Handles fetching player dashboard statistics by team performance.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import os
import logging
import json
from typing import Optional, Dict, Any, Union, Tuple, List
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import playerdashboardbyteamperformance
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, LeagueID, MeasureTypeDetailed
)
from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)
from ..utils.validation import _validate_season_format, validate_date_format
from ..utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Cache Directory Setup ---
PLAYER_TEAM_PERFORMANCE_CSV_DIR = get_cache_dir("player_team_performance")

# --- Parameter Validation Sets ---
_VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_VALID_PER_MODES = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
_VALID_MEASURE_TYPES = {getattr(MeasureTypeDetailed, attr) for attr in dir(MeasureTypeDetailed) if not attr.startswith('_') and isinstance(getattr(MeasureTypeDetailed, attr), str)}
_VALID_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

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

def _get_csv_path_for_team_performance(
    player_id: str,
    season: str,
    season_type: str,
    per_mode: str,
    measure_type: str,
    dashboard_type: str
) -> str:
    """
    Generates a file path for saving player team performance DataFrame as CSV.

    Args:
        player_id: The player's ID
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        per_mode: The per mode (e.g., 'PerGame', 'Totals')
        measure_type: The measure type (e.g., 'Base', 'Advanced')
        dashboard_type: The dashboard type (e.g., 'overall', 'points_scored')

    Returns:
        Path to the CSV file
    """
    # Clean parameters for filename
    clean_season_type = season_type.replace(" ", "_").lower()
    clean_per_mode = per_mode.replace(" ", "_").lower()
    clean_measure_type = measure_type.replace(" ", "_").lower()

    return get_cache_file_path(
        f"player_{player_id}_team_performance_{dashboard_type}_{season}_{clean_season_type}_{clean_per_mode}_{clean_measure_type}.csv",
        "player_team_performance"
    )

def fetch_player_dashboard_by_team_performance_logic(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.totals,
    measure_type: str = MeasureTypeDetailed.base,
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    pace_adjust: str = "N",
    period: int = 0,
    plus_minus: str = "N",
    rank: str = "N",
    vs_division: Optional[str] = None,
    vs_conference: Optional[str] = None,
    shot_clock_range: Optional[str] = None,
    season_segment: Optional[str] = None,
    po_round: Optional[int] = None,
    outcome: Optional[str] = None,
    location: Optional[str] = None,
    league_id: Optional[str] = None,
    game_segment: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player dashboard statistics by team performance.

    Args:
        player_name: Name or ID of the player
        season: Season in YYYY-YY format
        season_type: Type of season (e.g., 'Regular Season', 'Playoffs')
        per_mode: Statistical mode (e.g., 'PerGame', 'Totals')
        measure_type: Measure type (e.g., 'Base', 'Advanced')
        last_n_games: Number of most recent games to include
        month: Filter by month (0 for all)
        opponent_team_id: Filter by opponent team ID
        pace_adjust: Whether to adjust for pace ('Y' or 'N')
        period: Filter by period (0 for all)
        plus_minus: Whether to include plus/minus ('Y' or 'N')
        rank: Whether to include statistical ranks ('Y' or 'N')
        vs_division: Filter by division
        vs_conference: Filter by conference
        shot_clock_range: Filter by shot clock range
        season_segment: Filter by season segment
        po_round: Filter by playoff round
        outcome: Filter by game outcome ('W' or 'L')
        location: Filter by game location ('Home' or 'Road')
        league_id: League ID
        game_segment: Filter by game segment
        date_from: Start date filter (YYYY-MM-DD)
        date_to: End date filter (YYYY-MM-DD)
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False:
            str: A JSON string containing the player's team performance data or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    # Store DataFrames if requested
    dataframes = {}

    logger.info(f"Executing fetch_player_dashboard_by_team_performance_logic for '{player_name}', season {season}, type {season_type}, return_dataframe={return_dataframe}")

    # Validate season
    if not season or not _validate_season_format(season):
        error_msg = Errors.INVALID_SEASON_FORMAT.format(season=season)
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    # Validate dates
    if date_from and not validate_date_format(date_from):
        error_msg = Errors.INVALID_DATE_FORMAT.format(date=date_from)
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    if date_to and not validate_date_format(date_to):
        error_msg = Errors.INVALID_DATE_FORMAT.format(date=date_to)
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    # Validate season type
    if season_type not in _VALID_SEASON_TYPES:
        error_msg = Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_SEASON_TYPES)[:5]))
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    # Validate per_mode
    if per_mode not in _VALID_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_PER_MODES)[:5]))
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    # Validate measure_type
    if measure_type not in _VALID_MEASURE_TYPES:
        error_msg = Errors.INVALID_MEASURE_TYPE.format(value=measure_type, options=", ".join(list(_VALID_MEASURE_TYPES)[:5]))
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    # Validate league_id
    if league_id and league_id not in _VALID_LEAGUE_IDS:
        error_msg = Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_VALID_LEAGUE_IDS)[:5]))
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError: {e}")
        if return_dataframe:
            return format_response(error=str(e)), dataframes
        return format_response(error=str(e))
    except Exception as e:
        logger.error(f"Unexpected error finding player: {e}", exc_info=True)
        if return_dataframe:
            return format_response(error=str(e)), dataframes
        return format_response(error=str(e))

    try:
        endpoint = playerdashboardbyteamperformance.PlayerDashboardByTeamPerformance(
            player_id=player_id,
            season=season,
            season_type_playoffs=season_type,
            per_mode_detailed=per_mode,
            measure_type_detailed=measure_type,
            last_n_games=last_n_games,
            month=month,
            opponent_team_id=opponent_team_id,
            pace_adjust=pace_adjust,
            period=period,
            plus_minus=plus_minus,
            rank=rank,
            vs_division_nullable=vs_division,
            vs_conference_nullable=vs_conference,
            shot_clock_range_nullable=shot_clock_range,
            season_segment_nullable=season_segment,
            po_round_nullable=po_round,
            outcome_nullable=outcome,
            location_nullable=location,
            league_id_nullable=league_id,
            game_segment_nullable=game_segment,
            date_from_nullable=date_from,
            date_to_nullable=date_to,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )

        datasets = endpoint.get_data_frames()
        dataset_names = [
            "overall_player_dashboard",
            "points_scored_player_dashboard",
            "ponts_against_player_dashboard",
            "score_differential_player_dashboard"
        ]

        # Store DataFrames and save to CSV if requested
        if return_dataframe:
            for idx, name in enumerate(dataset_names):
                if idx < len(datasets):
                    df = datasets[idx]
                    dataframes[name] = df

                    # Save to CSV if not empty
                    if not df.empty:
                        csv_path = _get_csv_path_for_team_performance(
                            player_id=player_id,
                            season=season,
                            season_type=season_type,
                            per_mode=per_mode,
                            measure_type=measure_type,
                            dashboard_type=name
                        )
                        _save_dataframe_to_csv(df, csv_path)

        # Process DataFrames for JSON response
        result = {}
        for idx, name in enumerate(dataset_names):
            df = datasets[idx] if idx < len(datasets) else pd.DataFrame()
            result[name] = _process_dataframe(df, single_row=False)

        # Create response data
        response_data = {
            "player_name": player_actual_name,
            "player_id": player_id,
            "parameters": {
                "season": season,
                "season_type": season_type,
                "per_mode": per_mode,
                "measure_type": measure_type,
                "last_n_games": last_n_games,
                "month": month,
                "opponent_team_id": opponent_team_id,
                "pace_adjust": pace_adjust,
                "period": period,
                "plus_minus": plus_minus,
                "rank": rank,
                "vs_division": vs_division,
                "vs_conference": vs_conference,
                "shot_clock_range": shot_clock_range,
                "season_segment": season_segment,
                "po_round": po_round,
                "outcome": outcome,
                "location": location,
                "league_id": league_id,
                "game_segment": game_segment,
                "date_from": date_from,
                "date_to": date_to
            },
            "team_performance_dashboards": result
        }

        # Add DataFrame info to the response if requested
        if return_dataframe:
            csv_paths = {}
            for name in dataset_names:
                if name in dataframes and not dataframes[name].empty:
                    csv_path = _get_csv_path_for_team_performance(
                        player_id=player_id,
                        season=season,
                        season_type=season_type,
                        per_mode=per_mode,
                        measure_type=measure_type,
                        dashboard_type=name
                    )
                    csv_paths[name] = get_relative_cache_path(os.path.basename(csv_path), "player_team_performance")

            response_data["dataframe_info"] = {
                "message": "Player team performance data has been converted to DataFrames and saved as CSV files",
                "dataframes": {
                    name: {
                        "shape": list(dataframes[name].shape) if name in dataframes and not dataframes[name].empty else [],
                        "columns": dataframes[name].columns.tolist() if name in dataframes and not dataframes[name].empty else [],
                        "csv_path": csv_paths.get(name, "")
                    } for name in dataset_names if name in dataframes
                }
            }

            return format_response(response_data), dataframes

        return format_response(response_data)

    except Exception as api_error:
        logger.error(f"nba_api playerdashboardbyteamperformance failed: {api_error}", exc_info=True)
        error_msg = Errors.PLAYER_DASHBOARD_TEAM_PERFORMANCE_API.format(identifier=player_actual_name, error=str(api_error)) if hasattr(Errors, "PLAYER_DASHBOARD_TEAM_PERFORMANCE_API") else str(api_error)
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)
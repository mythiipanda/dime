"""
Handles fetching player shot chart data, processing it, and generating visualizations.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
from functools import lru_cache
from typing import List, Dict, Tuple, Optional, Any, Union

import pandas as pd
from nba_api.stats.endpoints import shotchartdetail
from nba_api.stats.library.parameters import SeasonTypeAllStar
from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)
from ..utils.validation import _validate_season_format
from .visualization import create_shotchart

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
PLAYER_SHOTCHART_CACHE_SIZE = 128
NBA_API_DEFAULT_TEAM_ID = 0  # For player-specific calls where team is inferred
SHOTCHART_CONTEXT_MEASURE = 'FGA' # Field Goal Attempts, common context for shot charts
DEFAULT_SHOT_ZONE = "Unknown"
SHOT_PERCENTAGE_PRECISION = 1

_VALID_SHOTCHART_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}

# --- Cache Directory Setup ---
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
PLAYER_SHOTCHART_CSV_DIR = os.path.join(CSV_CACHE_DIR, "player_shotchart")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(PLAYER_SHOTCHART_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_player_shotchart(
    player_name: str,
    season: str,
    season_type: str,
    data_type: str
) -> str:
    """
    Generates a file path for saving player shot chart DataFrame as CSV.

    Args:
        player_name: The player's name
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        data_type: The type of data ('shots' or 'league_averages')

    Returns:
        Path to the CSV file
    """
    # Clean player name and data type for filename
    clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()
    clean_season_type = season_type.replace(" ", "_").lower()

    filename = f"{clean_player_name}_{season}_{clean_season_type}_{data_type}.csv"
    return os.path.join(PLAYER_SHOTCHART_CSV_DIR, filename)

# --- Helper Functions ---
def _calculate_zone_summary(shots_data_list: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Calculates shot attempts, makes, and percentages by shot zone."""
    zone_summary: Dict[str, Dict[str, Any]] = {}
    for shot in shots_data_list:
        zone = shot.get("SHOT_ZONE_BASIC", DEFAULT_SHOT_ZONE)
        if zone not in zone_summary:
            zone_summary[zone] = {"attempts": 0, "made": 0, "percentage": 0.0}
        zone_summary[zone]["attempts"] += 1
        if shot.get("SHOT_MADE_FLAG") == 1:
            zone_summary[zone]["made"] += 1

    for zone_stats in zone_summary.values():
        if zone_stats["attempts"] > 0:
            zone_stats["percentage"] = round(zone_stats["made"] / zone_stats["attempts"] * 100, SHOT_PERCENTAGE_PRECISION)
        else:
            zone_stats["percentage"] = 0.0
    return zone_summary

def _calculate_overall_shot_stats(shots_data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates overall shot statistics (total shots, made, FG%)."""
    total_shots = len(shots_data_list)
    made_shots = sum(1 for shot in shots_data_list if shot.get("SHOT_MADE_FLAG") == 1)
    field_goal_percentage = 0.0
    if total_shots > 0:
        field_goal_percentage = round(made_shots / total_shots * 100, SHOT_PERCENTAGE_PRECISION)

    return {
        "total_shots": total_shots,
        "made_shots": made_shots,
        "field_goal_percentage": field_goal_percentage
    }

def _generate_shot_visualization(
    shot_summary_for_viz: Dict[str, Any],
    player_actual_name: str,
    output_base_dir: str
) -> Tuple[Optional[str], Optional[str]]:
    """Generates the shot chart visualization image and returns its path or an error."""
    visualization_path, visualization_error = None, None
    try:
        # Ensure the output directory exists
        # The 'output' subdir is relative to the 'backend' directory.
        # __file__ is in backend/api_tools/player_shot_charts.py
        # os.path.dirname(__file__) -> backend/api_tools
        # os.path.dirname(os.path.dirname(__file__)) -> backend
        # So, output_dir should be backend/output
        output_dir = os.path.join(output_base_dir, "output", "shot_charts") # More specific subdir
        os.makedirs(output_dir, exist_ok=True)

        visualization_path = create_shotchart(shot_summary_for_viz, output_dir)
        logger.info(f"Shot chart visualization created for {player_actual_name} at: {visualization_path}")
    except Exception as viz_error:
        logger.error(f"Failed to create shot chart visualization for {player_actual_name}: {viz_error}", exc_info=True)
        visualization_error = str(viz_error)
    return visualization_path, visualization_error

# --- Main Logic Function ---
def fetch_player_shotchart_logic(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player shot chart data, processes it, and generates a visualization.
    Provides DataFrame output capabilities.

    Args:
        player_name: The name or ID of the player.
        season: NBA season in YYYY-YY format. Defaults to current season.
        season_type: Type of season. Defaults to Regular Season.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string with shot chart data, summary, and visualization path/error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_player_shotchart_logic for: '{player_name}', Season: {season}, Type: {season_type}, return_dataframe={return_dataframe}")

    if not season or not _validate_season_format(season):
        error_response = format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
        if return_dataframe:
            return error_response, {}
        return error_response

    if season_type not in _VALID_SHOTCHART_SEASON_TYPES:
        error_msg = Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_SHOTCHART_SEASON_TYPES)[:5]))
        logger.warning(error_msg)
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching shotchartdetail for ID: {player_id}, Season: {season}, Type: {season_type}")

        # Store DataFrames if requested
        dataframes = {}

        try:
            shotchart_endpoint = shotchartdetail.ShotChartDetail(
                player_id=player_id, team_id=NBA_API_DEFAULT_TEAM_ID, season_nullable=season,
                season_type_all_star=season_type, timeout=settings.DEFAULT_TIMEOUT_SECONDS,
                context_measure_simple=SHOTCHART_CONTEXT_MEASURE
            )
            shots_df = shotchart_endpoint.shot_chart_detail.get_data_frame()
            league_avg_df = shotchart_endpoint.league_averages.get_data_frame()
            logger.debug(f"shotchartdetail API call successful for ID: {player_id}")

            if return_dataframe:
                dataframes["shots"] = shots_df
                dataframes["league_averages"] = league_avg_df

                # Save DataFrames to CSV if not empty
                if not shots_df.empty:
                    csv_path = _get_csv_path_for_player_shotchart(
                        player_actual_name, season, season_type, "shots"
                    )
                    _save_dataframe_to_csv(shots_df, csv_path)

                if not league_avg_df.empty:
                    csv_path = _get_csv_path_for_player_shotchart(
                        player_actual_name, season, season_type, "league_averages"
                    )
                    _save_dataframe_to_csv(league_avg_df, csv_path)

        except Exception as api_error:
            logger.error(f"nba_api shotchartdetail failed for ID {player_id}, Season {season}: {api_error}", exc_info=True)
            error_response = format_response(error=Errors.PLAYER_SHOTCHART_API.format(identifier=player_actual_name, season=season, error=str(api_error)))
            if return_dataframe:
                return error_response, dataframes
            return error_response

        shots_data_list = _process_dataframe(shots_df, single_row=False)
        league_averages_list = _process_dataframe(league_avg_df, single_row=False)

        if shots_data_list is None or league_averages_list is None:
            logger.error(f"DataFrame processing failed for shot chart of {player_actual_name} (Season: {season})")
            error_response = format_response(error=Errors.PLAYER_SHOTCHART_PROCESSING.format(identifier=player_actual_name, season=season))
            if return_dataframe:
                return error_response, dataframes
            return error_response

        if not shots_data_list:
            logger.warning(f"No shot data found for {player_actual_name} ({season}, {season_type}).")
            response_data = {
                "player_name": player_actual_name, "player_id": player_id, "season": season, "season_type": season_type,
                "overall_stats": {"total_shots": 0, "made_shots": 0, "field_goal_percentage": 0.0},
                "zone_breakdown": {}, "shot_data_summary": [], "league_averages": league_averages_list or [],
                "visualization_path": None, "visualization_error": None,
                "message": "No shot data found for the specified criteria."
            }
            if return_dataframe:
                return format_response(response_data), dataframes
            return format_response(response_data)

        overall_stats = _calculate_overall_shot_stats(shots_data_list)
        zone_summary = _calculate_zone_summary(shots_data_list)

        shot_summary_for_viz = {
            "player_name": player_actual_name, "player_id": player_id, "season": season, "season_type": season_type,
            "overall_stats": overall_stats, "zone_breakdown": zone_summary,
            "shot_locations": [{"x": s.get("LOC_X"), "y": s.get("LOC_Y"), "made": s.get("SHOT_MADE_FLAG") == 1, "zone": s.get("SHOT_ZONE_BASIC")} for s in shots_data_list]
        }

        # Determine base directory for output (backend directory)
        project_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        visualization_path, visualization_error = _generate_shot_visualization(shot_summary_for_viz, player_actual_name, project_backend_dir)

        response_summary = {
            "player_name": player_actual_name, "player_id": player_id, "season": season, "season_type": season_type,
            "overall_stats": overall_stats, "zone_breakdown": zone_summary,
            "shot_data_summary": shots_data_list,
            "league_averages": league_averages_list or [],
            "visualization_path": visualization_path, "visualization_error": visualization_error
        }
        logger.info(f"fetch_player_shotchart_logic completed for '{player_actual_name}'")

        if return_dataframe:
            return format_response(response_summary), dataframes
        return format_response(response_summary)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_shotchart_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except ValueError as e: # Catches validation errors from find_player_id_or_error if name is empty
        logger.warning(f"ValueError in fetch_player_shotchart_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_shotchart_logic for '{player_name}', Season {season}: {e}", exc_info=True)
        error_response = format_response(error=Errors.PLAYER_SHOTCHART_UNEXPECTED.format(identifier=player_name, season=season, error=str(e)))
        if return_dataframe:
            return error_response, {}
        return error_response
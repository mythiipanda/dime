"""
Handles fetching game-level visual and analytical data, specifically
game-wide shot charts and win probability play-by-play.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
from functools import lru_cache
import pandas as pd
from typing import Set, Dict, Any, List, Union, Tuple, Optional

from nba_api.stats.endpoints import (
    shotchartdetail,
    WinProbabilityPBP
)
from nba_api.stats.library.parameters import RunType
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response
)
from backend.utils.validation import validate_game_id_format

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
GAME_SHOTCHART_CACHE_SIZE = 64
GAME_WIN_PROB_CACHE_SIZE = 64
SHOTCHART_CONTEXT_MEASURE_GAME = "FGA"

_VALID_WP_RUN_TYPES: Set[str] = {"each play", "each second", "each poss"}

# --- Cache Directory Setup ---
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
SHOTCHART_CSV_DIR = os.path.join(CSV_CACHE_DIR, "shotcharts")
WIN_PROB_CSV_DIR = os.path.join(CSV_CACHE_DIR, "win_probability")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(SHOTCHART_CSV_DIR, exist_ok=True)
os.makedirs(WIN_PROB_CSV_DIR, exist_ok=True)

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

def _filter_shots_by_team(shots_df: pd.DataFrame, team_id: int = None, team_name: str = None) -> pd.DataFrame:
    """
    Filters shot chart data by team ID or name.

    Args:
        shots_df: DataFrame containing shot chart data
        team_id: Team ID to filter by
        team_name: Team name to filter by

    Returns:
        Filtered DataFrame
    """
    if (team_id is None and team_name is None) or shots_df.empty:
        return shots_df

    filtered_df = shots_df.copy()

    if team_id is not None and 'TEAM_ID' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['TEAM_ID'] == team_id]

    if team_name is not None and 'TEAM_NAME' in filtered_df.columns:
        # Case-insensitive partial match
        filtered_df = filtered_df[filtered_df['TEAM_NAME'].str.upper().str.contains(team_name.upper(), na=False)]

    return filtered_df.reset_index(drop=True)

def _filter_shots_by_player(shots_df: pd.DataFrame, player_id: int = None, player_name: str = None) -> pd.DataFrame:
    """
    Filters shot chart data by player ID or name.

    Args:
        shots_df: DataFrame containing shot chart data
        player_id: Player ID to filter by
        player_name: Player name to filter by

    Returns:
        Filtered DataFrame
    """
    if (player_id is None and player_name is None) or shots_df.empty:
        return shots_df

    filtered_df = shots_df.copy()

    if player_id is not None and 'PLAYER_ID' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['PLAYER_ID'] == player_id]

    if player_name is not None and 'PLAYER_NAME' in filtered_df.columns:
        # Case-insensitive partial match
        filtered_df = filtered_df[filtered_df['PLAYER_NAME'].str.upper().str.contains(player_name.upper(), na=False)]

    return filtered_df.reset_index(drop=True)

def _filter_shots_by_zone(shots_df: pd.DataFrame, zone_basic: str = None, zone_area: str = None, zone_range: str = None) -> pd.DataFrame:
    """
    Filters shot chart data by shot zone.

    Args:
        shots_df: DataFrame containing shot chart data
        zone_basic: Basic shot zone (e.g., 'Restricted Area', 'Mid-Range', '3PT Field Goal')
        zone_area: Shot zone area (e.g., 'Center', 'Left Side', 'Right Side')
        zone_range: Shot zone range (e.g., 'Less Than 8 ft.', '16-24 ft.')

    Returns:
        Filtered DataFrame
    """
    if (zone_basic is None and zone_area is None and zone_range is None) or shots_df.empty:
        return shots_df

    filtered_df = shots_df.copy()

    if zone_basic is not None and 'SHOT_ZONE_BASIC' in filtered_df.columns:
        # Case-insensitive partial match
        filtered_df = filtered_df[filtered_df['SHOT_ZONE_BASIC'].str.upper().str.contains(zone_basic.upper(), na=False)]

    if zone_area is not None and 'SHOT_ZONE_AREA' in filtered_df.columns:
        # Case-insensitive partial match
        filtered_df = filtered_df[filtered_df['SHOT_ZONE_AREA'].str.upper().str.contains(zone_area.upper(), na=False)]

    if zone_range is not None and 'SHOT_ZONE_RANGE' in filtered_df.columns:
        # Case-insensitive partial match
        filtered_df = filtered_df[filtered_df['SHOT_ZONE_RANGE'].str.upper().str.contains(zone_range.upper(), na=False)]

    return filtered_df.reset_index(drop=True)

def _filter_shots_by_period(shots_df: pd.DataFrame, period: int = None) -> pd.DataFrame:
    """
    Filters shot chart data by period.

    Args:
        shots_df: DataFrame containing shot chart data
        period: Period number to filter by (1-4 for quarters, 5+ for overtime)

    Returns:
        Filtered DataFrame
    """
    if period is None or shots_df.empty or 'PERIOD' not in shots_df.columns:
        return shots_df

    filtered_df = shots_df[shots_df['PERIOD'] == period]
    return filtered_df.reset_index(drop=True)

def _filter_shots_by_shot_type(shots_df: pd.DataFrame, shot_type: str = None, shot_made: bool = None) -> pd.DataFrame:
    """
    Filters shot chart data by shot type and whether the shot was made.

    Args:
        shots_df: DataFrame containing shot chart data
        shot_type: Shot type to filter by (e.g., '2PT Field Goal', '3PT Field Goal')
        shot_made: If True, only include made shots; if False, only include missed shots

    Returns:
        Filtered DataFrame
    """
    if (shot_type is None and shot_made is None) or shots_df.empty:
        return shots_df

    filtered_df = shots_df.copy()

    if shot_type is not None and 'SHOT_TYPE' in filtered_df.columns:
        # Case-insensitive partial match
        filtered_df = filtered_df[filtered_df['SHOT_TYPE'].str.upper().str.contains(shot_type.upper(), na=False)]

    if shot_made is not None and 'SHOT_MADE_FLAG' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['SHOT_MADE_FLAG'] == (1 if shot_made else 0)]

    return filtered_df.reset_index(drop=True)

# --- Logic Functions ---
def fetch_shotchart_logic(
    game_id: str,
    team_id: int = None,
    team_name: str = None,
    player_id: int = None,
    player_name: str = None,
    period: int = None,
    shot_type: str = None,
    shot_made: bool = None,
    zone_basic: str = None,
    zone_area: str = None,
    zone_range: str = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches shot chart data for all players in a specific NBA game.
    Data is sourced from the nba_api's ShotChartDetail endpoint.

    Provides granular filtering options and DataFrame output capabilities.

    Args:
        game_id: NBA game ID (10-digit string).
        team_id: Filter shots by team ID.
        team_name: Filter shots by team name (case-insensitive partial match).
        player_id: Filter shots by player ID.
        player_name: Filter shots by player name (case-insensitive partial match).
        period: Filter shots by period number (1-4 for quarters, 5+ for overtime).
        shot_type: Filter shots by shot type (e.g., '2PT Field Goal', '3PT Field Goal').
        shot_made: If True, only include made shots; if False, only include missed shots.
        zone_basic: Filter shots by basic shot zone (e.g., 'Restricted Area', 'Mid-Range', '3PT Field Goal').
        zone_area: Filter shots by shot zone area (e.g., 'Center', 'Left Side', 'Right Side').
        zone_range: Filter shots by shot zone range (e.g., 'Less Than 8 ft.', '16-24 ft.').
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON-formatted string containing shot chart data grouped by team and league averages, or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.

    Notes:
        - Returns an error if the game_id is empty or invalid.
        - Returns an empty list for teams if no shot data is found.
        - Each shot includes player, period, time, type, made/missed, coordinates, and event info.
    """
    logger.info(f"Executing fetch_shotchart_logic for game ID: {game_id}, return_dataframe={return_dataframe}")

    if not game_id:
        error_response = format_response(error=Errors.GAME_ID_EMPTY)
        if return_dataframe:
            return error_response, {}
        return error_response

    if not validate_game_id_format(game_id):
        error_response = format_response(error=Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id))
        if return_dataframe:
            return error_response, {}
        return error_response

    try:
        # Fetch data from the API
        shotchart_endpoint = shotchartdetail.ShotChartDetail(
            game_id_nullable=game_id,
            team_id=0,
            player_id=0,  # team_id=0 and player_id=0 for game-wide chart
            context_measure_simple=SHOTCHART_CONTEXT_MEASURE_GAME,
            season_nullable=None,  # Season not needed for game-specific chart
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"shotchartdetail API call successful for game {game_id}")

        # Get DataFrames
        shots_df = shotchart_endpoint.shot_chart_detail.get_data_frame()
        league_avg_df = shotchart_endpoint.league_averages.get_data_frame()

        # Apply filters if provided
        filtered_shots_df = shots_df.copy()

        if team_id is not None or team_name is not None:
            filtered_shots_df = _filter_shots_by_team(filtered_shots_df, team_id, team_name)

        if player_id is not None or player_name is not None:
            filtered_shots_df = _filter_shots_by_player(filtered_shots_df, player_id, player_name)

        if period is not None:
            filtered_shots_df = _filter_shots_by_period(filtered_shots_df, period)

        if shot_type is not None or shot_made is not None:
            filtered_shots_df = _filter_shots_by_shot_type(filtered_shots_df, shot_type, shot_made)

        if zone_basic is not None or zone_area is not None or zone_range is not None:
            filtered_shots_df = _filter_shots_by_zone(filtered_shots_df, zone_basic, zone_area, zone_range)

        # Save to CSV if returning DataFrame
        if return_dataframe:
            # Create a descriptive filename based on filters
            filename_parts = [game_id]
            if team_id:
                filename_parts.append(f"team_{team_id}")
            if team_name:
                filename_parts.append(f"team_{team_name.replace(' ', '_')}")
            if player_id:
                filename_parts.append(f"player_{player_id}")
            if player_name:
                filename_parts.append(f"player_{player_name.replace(' ', '_')}")
            if period:
                filename_parts.append(f"period_{period}")
            if shot_type:
                filename_parts.append(f"shottype_{shot_type.replace(' ', '_')}")
            if shot_made is not None:
                filename_parts.append(f"made_{shot_made}")
            if zone_basic:
                filename_parts.append(f"zone_{zone_basic.replace(' ', '_')}")

            shots_csv_path = os.path.join(SHOTCHART_CSV_DIR, f"{'_'.join(filename_parts)}_shots.csv")
            league_avg_csv_path = os.path.join(SHOTCHART_CSV_DIR, f"{'_'.join(filename_parts)}_league_avg.csv")

            _save_dataframe_to_csv(filtered_shots_df, shots_csv_path)
            _save_dataframe_to_csv(league_avg_df, league_avg_csv_path)

        # Process DataFrames for JSON response
        shots_list = _process_dataframe(filtered_shots_df, single_row=False)
        league_avgs_list = _process_dataframe(league_avg_df, single_row=False)

        if shots_list is None or league_avgs_list is None:
            if filtered_shots_df.empty:
                logger.warning(f"No shot chart data found for game {game_id} from API or after filtering.")
                result_dict = {"game_id": game_id, "teams": [], "league_averages": league_avgs_list or []}

                if return_dataframe:
                    dataframes = {
                        "shots": filtered_shots_df,
                        "league_averages": league_avg_df
                    }
                    return format_response(result_dict), dataframes
                return format_response(result_dict)
            else:
                logger.error(f"DataFrame processing failed for shot chart of game {game_id}")
                error_msg = Errors.SHOTCHART_PROCESSING.format(game_id=game_id)
                error_response = format_response(error=error_msg)

                if return_dataframe:
                    return error_response, {}
                return error_response

        if not shots_list:
            logger.warning(f"No shot data processed for game {game_id}.")
            result_dict = {"game_id": game_id, "teams": [], "league_averages": league_avgs_list or []}

            if return_dataframe:
                dataframes = {
                    "shots": filtered_shots_df,
                    "league_averages": league_avg_df
                }
                return format_response(result_dict), dataframes
            return format_response(result_dict)

        # Organize shots by team
        teams_data = {}
        for shot_item in shots_list:
            team_id_shot = shot_item.get("TEAM_ID")
            if team_id_shot is None:
                continue

            if team_id_shot not in teams_data:
                teams_data[team_id_shot] = {
                    "team_name": shot_item.get("TEAM_NAME"),
                    "team_id": team_id_shot,
                    "shots": []
                }

            # Format the shot data
            teams_data[team_id_shot]["shots"].append({
                "player": {"id": shot_item.get("PLAYER_ID"), "name": shot_item.get("PLAYER_NAME")},
                "period": shot_item.get("PERIOD"),
                "time_remaining": f"{shot_item.get('MINUTES_REMAINING', 0)}:{str(shot_item.get('SECONDS_REMAINING', 0)).zfill(2)}",
                "shot_type": shot_item.get("SHOT_TYPE"),
                "made": shot_item.get("SHOT_MADE_FLAG") == 1,
                "coordinates": {"x": shot_item.get("LOC_X"), "y": shot_item.get("LOC_Y")},
                "action_type": shot_item.get("ACTION_TYPE"),
                "shot_zone_basic": shot_item.get("SHOT_ZONE_BASIC"),
                "shot_zone_area": shot_item.get("SHOT_ZONE_AREA"),
                "shot_zone_range": shot_item.get("SHOT_ZONE_RANGE"),
                "shot_distance": shot_item.get("SHOT_DISTANCE"),
                "event_num": shot_item.get("GAME_EVENT_ID")
            })

        # Create the result dictionary
        result_dict = {
            "game_id": game_id,
            "teams": list(teams_data.values()),
            "league_averages": league_avgs_list or []
        }

        # Add filter information if any filters were applied
        filters_applied = {}
        if team_id:
            filters_applied["team_id"] = team_id
        if team_name:
            filters_applied["team_name"] = team_name
        if player_id:
            filters_applied["player_id"] = player_id
        if player_name:
            filters_applied["player_name"] = player_name
        if period:
            filters_applied["period"] = period
        if shot_type:
            filters_applied["shot_type"] = shot_type
        if shot_made is not None:
            filters_applied["shot_made"] = shot_made
        if zone_basic:
            filters_applied["zone_basic"] = zone_basic
        if zone_area:
            filters_applied["zone_area"] = zone_area
        if zone_range:
            filters_applied["zone_range"] = zone_range

        if filters_applied:
            result_dict["filters_applied"] = filters_applied

        logger.info(f"fetch_shotchart_logic completed for game {game_id}")

        # Return the appropriate result based on return_dataframe
        if return_dataframe:
            dataframes = {
                "shots": filtered_shots_df,
                "league_averages": league_avg_df
            }
            return format_response(result_dict), dataframes

        return format_response(result_dict)

    except Exception as e:
        logger.error(f"Error fetching shot chart for game {game_id}: {str(e)}", exc_info=True)
        error_msg = Errors.SHOTCHART_API.format(game_id=game_id, error=str(e))
        error_response = format_response(error=error_msg)

        if return_dataframe:
            return error_response, {}
        return error_response

def fetch_win_probability_logic(
    game_id: str,
    run_type: str = RunType.default,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches win probability data for a specific NBA game.
    Data is sourced from the nba_api's WinProbabilityPBP endpoint.

    Provides DataFrame output capabilities.

    Args:
        game_id: NBA game ID (10-digit string).
        run_type: Run type for win probability calculation (e.g., 'each play', 'each second', 'each poss').
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON-formatted string containing game info and win probability PBP data, or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.

    Notes:
        - Returns an error if the game_id is empty or invalid, or if run_type is not supported.
        - Filters out win probability rows with missing EVENT_NUM.
        - Returns empty lists if no valid data is found.
    """
    logger.info(f"Executing fetch_win_probability_logic for game {game_id}, RunType: {run_type}, return_dataframe={return_dataframe}")

    if not game_id:
        error_response = format_response(error=Errors.GAME_ID_EMPTY)
        if return_dataframe:
            return error_response, {}
        return error_response

    if not validate_game_id_format(game_id):
        error_response = format_response(error=Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id))
        if return_dataframe:
            return error_response, {}
        return error_response

    if run_type not in _VALID_WP_RUN_TYPES:
        error_response = format_response(error=Errors.INVALID_RUN_TYPE.format(value=run_type, options=", ".join(list(_VALID_WP_RUN_TYPES)[:5])))
        if return_dataframe:
            return error_response, {}
        return error_response

    try:
        # Fetch data from the API
        wp_endpoint = WinProbabilityPBP(game_id=game_id, run_type=run_type, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
        logger.debug(f"WinProbabilityPBP API call successful for {game_id}")

        # Get DataFrames
        game_info_df = wp_endpoint.game_info.get_data_frame()
        win_prob_df = wp_endpoint.win_prob_p_bp.get_data_frame()

        # Filter win probability data
        win_prob_df_filtered = win_prob_df
        if not win_prob_df.empty and 'EVENT_NUM' in win_prob_df.columns:
            # Filter out rows where EVENT_NUM might be NaN or None, ensuring they are actual PBP events
            win_prob_df_filtered = win_prob_df[pd.notna(win_prob_df['EVENT_NUM'])]
            if win_prob_df_filtered.empty:
                logger.warning(f"Win probability PBP data for game {game_id} had EVENT_NUM column but all values were NaN/None.")
        elif not win_prob_df.empty:
            logger.warning(f"Win probability PBP data for game {game_id} is missing EVENT_NUM column.")

        # Save to CSV if returning DataFrame
        if return_dataframe:
            # Create descriptive filenames
            game_info_csv_path = os.path.join(WIN_PROB_CSV_DIR, f"{game_id}_run_{run_type.replace(' ', '_')}_game_info.csv")
            win_prob_csv_path = os.path.join(WIN_PROB_CSV_DIR, f"{game_id}_run_{run_type.replace(' ', '_')}_win_prob.csv")

            _save_dataframe_to_csv(game_info_df, game_info_csv_path)
            _save_dataframe_to_csv(win_prob_df_filtered, win_prob_csv_path)

        # Process DataFrames for JSON response
        game_info_dict = _process_dataframe(game_info_df, single_row=True)
        win_probs_list = _process_dataframe(win_prob_df_filtered, single_row=False) if not win_prob_df_filtered.empty else []

        # Check if essential data processing failed
        if game_info_dict is None:  # _process_dataframe failed for game_info
            logger.error(f"DataFrame processing failed for game_info of win probability for game {game_id}.")
            error_msg = Errors.PROCESSING_ERROR.format(error=f"game_info for win probability data for game {game_id}")
            error_response = format_response(error=error_msg)

            if return_dataframe:
                return error_response, {}
            return error_response

        # Create the result dictionary
        result_dict = {
            "game_id": game_id,
            "game_info": game_info_dict or {},
            "win_probability": win_probs_list or [],
            "run_type": run_type
        }

        logger.info(f"Successfully fetched win probability for game {game_id}")

        # Return the appropriate result based on return_dataframe
        if return_dataframe:
            dataframes = {
                "game_info": game_info_df,
                "win_probability": win_prob_df_filtered
            }
            return format_response(result_dict), dataframes

        return format_response(result_dict)

    except Exception as e:
        logger.error(f"Error fetching win probability for {game_id}: {e}", exc_info=True)
        error_msg = Errors.WINPROBABILITY_API.format(game_id=game_id, error=str(e))
        error_response = format_response(error=error_msg)

        if return_dataframe:
            return error_response, {}
        return error_response
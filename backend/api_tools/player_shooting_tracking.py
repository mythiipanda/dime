"""
Handles fetching and processing player shooting tracking statistics,
categorized by general, shot clock, dribbles, touch time, and defender distance.
Requires an initial lookup for the player's current team_id via commonplayerinfo.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
from typing import Optional, Set, Dict, Union, Tuple
from functools import lru_cache

import pandas as pd
from nba_api.stats.endpoints import commonplayerinfo, playerdashptshots
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

from config import settings
from core.errors import Errors
from api_tools.utils import (
    _process_dataframe,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)
from utils.validation import _validate_season_format, validate_date_format

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
PLAYER_SHOOTING_TRACKING_CACHE_SIZE = 128
NBA_API_DEFAULT_OPPONENT_TEAM_ID = 0 # Standard value for no specific opponent filter

_VALID_SHOOTING_TRACKING_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_VALID_SHOOTING_TRACKING_PER_MODES: Set[str] = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}

# --- Cache Directory Setup ---
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
PLAYER_SHOOTING_TRACKING_CSV_DIR = os.path.join(CSV_CACHE_DIR, "player_shooting_tracking")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(PLAYER_SHOOTING_TRACKING_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_player_shooting_tracking(
    player_name: str,
    season: str,
    season_type: str,
    per_mode: str,
    data_type: str
) -> str:
    """
    Generates a file path for saving player shooting tracking DataFrame as CSV.

    Args:
        player_name: The player's name
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        per_mode: The per mode (e.g., 'PerGame', 'Totals')
        data_type: The type of data ('general', 'shot_clock', 'dribble', 'touch_time',
                                     'defender_distance', 'defender_distance_10ft_plus')

    Returns:
        Path to the CSV file
    """
    # Clean player name and data type for filename
    clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()
    clean_season_type = season_type.replace(" ", "_").lower()
    clean_per_mode = per_mode.replace(" ", "_").lower()

    filename = f"{clean_player_name}_{season}_{clean_season_type}_{clean_per_mode}_{data_type}.csv"
    return os.path.join(PLAYER_SHOOTING_TRACKING_CSV_DIR, filename)

def fetch_player_shots_tracking_logic(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.totals,
    opponent_team_id: int = NBA_API_DEFAULT_OPPONENT_TEAM_ID,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    last_n_games: int = 0,
    league_id: str = "00",
    month: int = 0,
    period: int = 0,
    vs_division_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player shooting tracking statistics, broken down by various categories.
    This function first determines the player's team_id for the given season,
    then uses that to fetch detailed shooting stats.

    Provides DataFrame output capabilities.

    Args:
        player_name: The name or ID of the player.
        season: NBA season in YYYY-YY format. Defaults to current season.
        season_type: Type of season. Defaults to Regular Season.
        per_mode: Statistical mode (PerModeSimple). Defaults to Totals.
        opponent_team_id: Filter by opponent team ID. Defaults to 0 (all).
        date_from: Start date filter (YYYY-MM-DD).
        date_to: End date filter (YYYY-MM-DD).
        last_n_games: Number of games to include (0 for all games).
        league_id: League ID (default: "00" for NBA).
        month: Month number (0 for all months).
        period: Period number (0 for all periods).
        vs_division_nullable: Filter by division (e.g., "Atlantic", "Central").
        vs_conference_nullable: Filter by conference (e.g., "East", "West").
        season_segment_nullable: Filter by season segment (e.g., "Post All-Star", "Pre All-Star").
        outcome_nullable: Filter by game outcome (e.g., "W", "L").
        location_nullable: Filter by game location (e.g., "Home", "Road").
        game_segment_nullable: Filter by game segment (e.g., "First Half", "Second Half").
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: A JSON string containing player shooting tracking stats or an error message.
                 Successful response structure includes keys like: "general_shooting",
                 "by_shot_clock", "by_dribble_count", "by_touch_time",
                 "by_defender_distance", "by_defender_distance_10ft_plus".
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_player_shots_tracking_logic for player name: {player_name}, Season: {season}, PerMode: {per_mode}, " +
              f"OpponentTeamID: {opponent_team_id}, DateFrom: {date_from}, DateTo: {date_to}, LastNGames: {last_n_games}, " +
              f"LeagueID: {league_id}, Month: {month}, Period: {period}, VsDivision: {vs_division_nullable}, " +
              f"VsConference: {vs_conference_nullable}, SeasonSegment: {season_segment_nullable}, Outcome: {outcome_nullable}, " +
              f"Location: {location_nullable}, GameSegment: {game_segment_nullable}, return_dataframe={return_dataframe}")

    if not player_name or not player_name.strip():
        error_response = format_response(error=Errors.PLAYER_NAME_EMPTY)
        if return_dataframe:
            return error_response, {}
        return error_response

    if not season or not _validate_season_format(season):
        error_response = format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
        if return_dataframe:
            return error_response, {}
        return error_response

    if date_from and not validate_date_format(date_from):
        error_response = format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from))
        if return_dataframe:
            return error_response, {}
        return error_response

    if date_to and not validate_date_format(date_to):
        error_response = format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to))
        if return_dataframe:
            return error_response, {}
        return error_response

    if season_type not in _VALID_SHOOTING_TRACKING_SEASON_TYPES:
        error_response = format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_SHOOTING_TRACKING_SEASON_TYPES)[:5])))
        if return_dataframe:
            return error_response, {}
        return error_response

    if per_mode not in _VALID_SHOOTING_TRACKING_PER_MODES:
        error_response = format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_SHOOTING_TRACKING_PER_MODES)[:3])))
        if return_dataframe:
            return error_response, {}
        return error_response

    try:
        player_id_int, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching commonplayerinfo for team ID lookup (Player: {player_actual_name}, ID: {player_id_int})")

        # Get player info to find team ID
        player_info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id_int, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
        info_dict = _process_dataframe(player_info_endpoint.common_player_info.get_data_frame(), single_row=True)

        if info_dict is None or "TEAM_ID" not in info_dict:
            logger.error(f"Could not retrieve team ID for player {player_actual_name} (ID: {player_id_int})")
            error_response = format_response(error=Errors.TEAM_ID_NOT_FOUND.format(player_name=player_actual_name))
            if return_dataframe:
                return error_response, {}
            return error_response

        team_id = info_dict["TEAM_ID"]
        logger.debug(f"Found Team ID {team_id} for player {player_actual_name}")

        # Call the API
        logger.debug(f"Fetching playerdashptshots for Player ID: {player_id_int}, Team ID: {team_id}, Season: {season}")
        shooting_stats_endpoint = playerdashptshots.PlayerDashPtShots(
            player_id=player_id_int,
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            per_mode_simple=per_mode,
            opponent_team_id=opponent_team_id,
            date_from_nullable=date_from,
            date_to_nullable=date_to,
            last_n_games=last_n_games,
            league_id=league_id,
            month=month,
            period=period,
            vs_division_nullable=vs_division_nullable,
            vs_conference_nullable=vs_conference_nullable,
            season_segment_nullable=season_segment_nullable,
            outcome_nullable=outcome_nullable,
            location_nullable=location_nullable,
            game_segment_nullable=game_segment_nullable,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"playerdashptshots API call successful for {player_actual_name}")

        # Get DataFrames from the API response
        general_df = shooting_stats_endpoint.general_shooting.get_data_frame()
        shot_clock_df = shooting_stats_endpoint.shot_clock_shooting.get_data_frame()
        dribbles_df = shooting_stats_endpoint.dribble_shooting.get_data_frame()
        touch_time_df = shooting_stats_endpoint.touch_time_shooting.get_data_frame()
        defender_dist_df = shooting_stats_endpoint.closest_defender_shooting.get_data_frame()
        defender_dist_10ft_df = shooting_stats_endpoint.closest_defender10ft_plus_shooting.get_data_frame()

        # Store DataFrames if requested
        dataframes = {}

        if return_dataframe:
            dataframes["general_shooting"] = general_df
            dataframes["by_shot_clock"] = shot_clock_df
            dataframes["by_dribble_count"] = dribbles_df
            dataframes["by_touch_time"] = touch_time_df
            dataframes["by_defender_distance"] = defender_dist_df
            dataframes["by_defender_distance_10ft_plus"] = defender_dist_10ft_df

            # Save DataFrames to CSV if not empty
            if not general_df.empty:
                csv_path = _get_csv_path_for_player_shooting_tracking(
                    player_actual_name, season, season_type, per_mode, "general"
                )
                _save_dataframe_to_csv(general_df, csv_path)

            if not shot_clock_df.empty:
                csv_path = _get_csv_path_for_player_shooting_tracking(
                    player_actual_name, season, season_type, per_mode, "shot_clock"
                )
                _save_dataframe_to_csv(shot_clock_df, csv_path)

            if not dribbles_df.empty:
                csv_path = _get_csv_path_for_player_shooting_tracking(
                    player_actual_name, season, season_type, per_mode, "dribble"
                )
                _save_dataframe_to_csv(dribbles_df, csv_path)

            if not touch_time_df.empty:
                csv_path = _get_csv_path_for_player_shooting_tracking(
                    player_actual_name, season, season_type, per_mode, "touch_time"
                )
                _save_dataframe_to_csv(touch_time_df, csv_path)

            if not defender_dist_df.empty:
                csv_path = _get_csv_path_for_player_shooting_tracking(
                    player_actual_name, season, season_type, per_mode, "defender_distance"
                )
                _save_dataframe_to_csv(defender_dist_df, csv_path)

            if not defender_dist_10ft_df.empty:
                csv_path = _get_csv_path_for_player_shooting_tracking(
                    player_actual_name, season, season_type, per_mode, "defender_distance_10ft_plus"
                )
                _save_dataframe_to_csv(defender_dist_10ft_df, csv_path)

        # Process DataFrames for JSON response
        general_list = _process_dataframe(general_df, single_row=False)
        shot_clock_list = _process_dataframe(shot_clock_df, single_row=False)
        dribbles_list = _process_dataframe(dribbles_df, single_row=False)
        touch_time_list = _process_dataframe(touch_time_df, single_row=False)
        defender_dist_list = _process_dataframe(defender_dist_df, single_row=False)
        defender_dist_10ft_list = _process_dataframe(defender_dist_10ft_df, single_row=False)

        # Check for processing errors first (any individually processed dataframe is None)
        if general_list is None or \
           shot_clock_list is None or \
           dribbles_list is None or \
           touch_time_list is None or \
           defender_dist_list is None or \
           defender_dist_10ft_list is None:
            logger.error(f"DataFrame processing failed for shooting stats of {player_actual_name} (ID: {player_id_int}, Season: {season}). At least one DF processing returned None.")
            error_msg = Errors.PLAYER_SHOTS_TRACKING_PROCESSING.format(identifier=player_actual_name, season=season)
            error_response = format_response(error=error_msg)
            if return_dataframe:
                return error_response, dataframes
            return error_response

        if not (general_list or shot_clock_list or dribbles_list or touch_time_list or defender_dist_list or defender_dist_10ft_list):
            original_dfs = [general_df, shot_clock_df, dribbles_df, touch_time_df, defender_dist_df, defender_dist_10ft_df]
            if all(df.empty for df in original_dfs):
                logger.warning(f"No shooting stats data found for player {player_actual_name} (ID: {player_id_int}) with given filters (all original DFs were empty).")

                response_data = {
                    "player_id": player_id_int,
                    "player_name": player_actual_name,
                    "team_id": team_id,
                    "parameters": {
                        "season": season,
                        "season_type": season_type,
                        "per_mode": per_mode,
                        "opponent_team_id": opponent_team_id,
                        "date_from": date_from,
                        "date_to": date_to,
                        "last_n_games": last_n_games,
                        "league_id": league_id,
                        "month": month,
                        "period": period,
                        "vs_division": vs_division_nullable,
                        "vs_conference": vs_conference_nullable,
                        "season_segment": season_segment_nullable,
                        "outcome": outcome_nullable,
                        "location": location_nullable,
                        "game_segment": game_segment_nullable
                    },
                    "general_shooting": [],
                    "by_shot_clock": [],
                    "by_dribble_count": [],
                    "by_touch_time": [],
                    "by_defender_distance": [],
                    "by_defender_distance_10ft_plus": []
                }

                if return_dataframe:
                    return format_response(response_data), dataframes
                return format_response(response_data)

        # Create response data
        result = {
            "player_id": player_id_int,
            "player_name": player_actual_name,
            "team_id": team_id,
            "parameters": {
                "season": season,
                "season_type": season_type,
                "per_mode": per_mode,
                "opponent_team_id": opponent_team_id,
                "date_from": date_from,
                "date_to": date_to,
                "last_n_games": last_n_games,
                "league_id": league_id,
                "month": month,
                "period": period,
                "vs_division": vs_division_nullable,
                "vs_conference": vs_conference_nullable,
                "season_segment": season_segment_nullable,
                "outcome": outcome_nullable,
                "location": location_nullable,
                "game_segment": game_segment_nullable
            },
            "general_shooting": general_list or [],
            "by_shot_clock": shot_clock_list or [],
            "by_dribble_count": dribbles_list or [],
            "by_touch_time": touch_time_list or [],
            "by_defender_distance": defender_dist_list or [],
            "by_defender_distance_10ft_plus": defender_dist_10ft_list or []
        }

        logger.info(f"fetch_player_shots_tracking_logic completed for {player_actual_name}")

        if return_dataframe:
            return format_response(result), dataframes
        return format_response(result)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_shots_tracking_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_shots_tracking_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except Exception as e:
        player_id_log = player_id_int if 'player_id_int' in locals() else 'unknown'
        logger.error(f"Error fetching shots tracking stats for player {player_name} (resolved ID: {player_id_log}, Season: {season}): {str(e)}", exc_info=True)
        error_msg = Errors.PLAYER_SHOTS_TRACKING_UNEXPECTED.format(identifier=player_name, season=season, error=str(e))
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response
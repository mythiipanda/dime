"""
Handles fetching various player dashboard statistics including profile,
defensive stats, and hustle stats.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import os
import logging
import json
from typing import Optional, List, Dict, Any, Set, Union, Tuple
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import (
    playerprofilev2,
    playerdashptshotdefend,
    leaguehustlestatsplayer,
    PlayerFantasyProfile
)
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, PerMode36, LeagueID, PerModeSimple, PerModeTime
from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)
from ..utils.validation import _validate_season_format, validate_date_format
from .player_common_info import fetch_player_info_logic
from ..utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
PLAYER_PROFILE_CACHE_SIZE = 256
PLAYER_DEFENSE_CACHE_SIZE = 128
PLAYER_HUSTLE_CACHE_SIZE = 64
MAX_LEAGUE_WIDE_HUSTLE_RESULTS = 200
NBA_API_DEFAULT_TEAM_ID_ALL = 0 # Standard value for 'all teams' or no specific team filter

# --- Cache Directory Setup ---
PLAYER_DASHBOARD_CSV_DIR = get_cache_dir("player_dashboard")
PLAYER_PROFILE_CSV_DIR = get_cache_dir("player_dashboard/profile")
PLAYER_DEFENSE_CSV_DIR = get_cache_dir("player_dashboard/defense")
PLAYER_HUSTLE_CSV_DIR = get_cache_dir("player_dashboard/hustle")

# Validation sets for parameters
_VALID_PER_MODES_PROFILE: Set[str] = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
_VALID_PER_MODES_PROFILE.update({getattr(PerMode36, attr) for attr in dir(PerMode36) if not attr.startswith('_') and isinstance(getattr(PerMode36, attr), str)})

_VALID_PLAYER_DASHBOARD_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}

_VALID_DEFENSE_PER_MODES: Set[str] = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}

_VALID_HUSTLE_PER_MODES: Set[str] = {getattr(PerModeTime, attr) for attr in dir(PerModeTime) if not attr.startswith('_') and isinstance(getattr(PerModeTime, attr), str)}

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

def _get_csv_path_for_player_profile(player_id: str, per_mode: str) -> str:
    """
    Generates a file path for saving player profile DataFrame as CSV.

    Args:
        player_id: The player's ID
        per_mode: The per mode (e.g., 'PerGame', 'Totals')

    Returns:
        Path to the CSV file
    """
    # Clean per mode for filename
    clean_per_mode = per_mode.replace(" ", "_").lower()

    return get_cache_file_path(f"player_{player_id}_profile_{clean_per_mode}.csv", "player_dashboard/profile")

def _get_csv_path_for_player_defense(
    player_id: str,
    season: str,
    season_type: str,
    per_mode: str,
    opponent_team_id: int
) -> str:
    """
    Generates a file path for saving player defense DataFrame as CSV.

    Args:
        player_id: The player's ID
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        per_mode: The per mode (e.g., 'PerGame', 'Totals')
        opponent_team_id: The opponent team ID

    Returns:
        Path to the CSV file
    """
    # Clean season type for filename
    clean_season_type = season_type.replace(" ", "_").lower()

    # Clean per mode for filename
    clean_per_mode = per_mode.replace(" ", "_").lower()

    return get_cache_file_path(
        f"player_{player_id}_defense_{season}_{clean_season_type}_{clean_per_mode}_{opponent_team_id}.csv",
        "player_dashboard/defense"
    )

def _get_csv_path_for_player_hustle(
    season: str,
    season_type: str,
    per_mode: str,
    player_id: Optional[str] = None,
    team_id: Optional[int] = None,
    league_id: str = LeagueID.nba
) -> str:
    """
    Generates a file path for saving player hustle DataFrame as CSV.

    Args:
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        per_mode: The per mode (e.g., 'PerGame', 'Totals')
        player_id: The player's ID (optional)
        team_id: The team ID (optional)
        league_id: The league ID (e.g., '00' for NBA)

    Returns:
        Path to the CSV file
    """
    # Clean season type for filename
    clean_season_type = season_type.replace(" ", "_").lower()

    # Clean per mode for filename
    clean_per_mode = per_mode.replace(" ", "_").lower()

    # Create filename based on filters
    if player_id:
        filename = f"player_{player_id}_hustle_{season}_{clean_season_type}_{clean_per_mode}.csv"
    elif team_id:
        filename = f"team_{team_id}_hustle_{season}_{clean_season_type}_{clean_per_mode}.csv"
    else:
        filename = f"league_{league_id}_hustle_{season}_{clean_season_type}_{clean_per_mode}.csv"

    return get_cache_file_path(filename, "player_dashboard/hustle")

# --- Helper for Parameter Validation ---
def _validate_common_dashboard_params(
    season: Optional[str],
    season_type: str,
    valid_season_types: Set[str],
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> Optional[str]:
    """Validates common parameters for dashboard stats functions."""
    if season and not _validate_season_format(season): # season can be None for some hustle stats calls
        return Errors.INVALID_SEASON_FORMAT.format(season=season)
    if date_from and not validate_date_format(date_from):
        return Errors.INVALID_DATE_FORMAT.format(date=date_from)
    if date_to and not validate_date_format(date_to):
        return Errors.INVALID_DATE_FORMAT.format(date=date_to)
    if season_type not in valid_season_types:
        return Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(valid_season_types)[:5]))
    return None

# --- Logic Functions ---
def fetch_player_profile_logic(
    player_name: str,
    per_mode: Optional[str] = PerModeDetailed.per_game,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches comprehensive player profile information including career stats, season stats,
    highs, and next game details.
    Provides DataFrame output capabilities.

    Args:
        player_name (str): The name or ID of the player.
        per_mode (str, optional): Statistical mode for career/season stats (e.g., "PerGame").
                                  Defaults to "PerGame".
        return_dataframe (bool, optional): Whether to return DataFrames along with the JSON response.
                                          Defaults to False.

    Returns:
        If return_dataframe=False:
            str: A JSON string containing the player's profile data or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    # Store DataFrames if requested
    dataframes = {}

    effective_per_mode = per_mode
    if effective_per_mode is None or effective_per_mode == "None":
        effective_per_mode = PerModeDetailed.per_game
        logger.info(f"per_mode was None or 'None', defaulting to {effective_per_mode} for {player_name}")

    logger.info(f"Executing fetch_player_profile_logic for: '{player_name}', Effective PerMode: {effective_per_mode}, return_dataframe={return_dataframe}")

    if effective_per_mode not in _VALID_PER_MODES_PROFILE:
        error_msg = Errors.INVALID_PER_MODE.format(value=effective_per_mode, options=", ".join(list(_VALID_PER_MODES_PROFILE)[:5]))
        logger.warning(error_msg)
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        player_info_response_str = fetch_player_info_logic(player_actual_name)
        player_info_data = json.loads(player_info_response_str)

        if "error" in player_info_data:
            logger.error(f"Failed to get common player info for {player_actual_name} within profile fetch: {player_info_data['error']}")
            if return_dataframe:
                return format_response(error=player_info_data['error']), dataframes
            return format_response(error=player_info_data['error'])

        player_info_dict = player_info_data.get("player_info", {})
        if not player_info_dict:
             logger.error(f"Common player info was empty for {player_actual_name} within profile fetch.")
             error_msg = Errors.PLAYER_INFO_PROCESSING.format(identifier=player_actual_name)
             if return_dataframe:
                 return format_response(error=error_msg), dataframes
             return format_response(error=error_msg)

        logger.debug(f"Fetching playerprofilev2 for ID: {player_id}, PerMode: {effective_per_mode}")
        try:
            profile_endpoint = playerprofilev2.PlayerProfileV2(player_id=player_id, per_mode36=effective_per_mode, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
            logger.debug(f"playerprofilev2 API call object created for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api playerprofilev2 instantiation or initial request failed for ID {player_id}: {api_error}", exc_info=True)
            # Attempt to log raw response if JSONDecodeError
            raw_response_text = None
            if isinstance(api_error, json.JSONDecodeError) and hasattr(profile_endpoint, 'nba_response') and profile_endpoint.nba_response and hasattr(profile_endpoint.nba_response, '_response'):
                raw_response_text = profile_endpoint.nba_response._response
                logger.error(f"Raw NBA API response that caused JSONDecodeError (first 500 chars): {raw_response_text[:500] if raw_response_text else 'N/A'}")
            error_msg = Errors.PLAYER_PROFILE_API.format(identifier=player_actual_name, error=str(api_error))
            if return_dataframe:
                return format_response(error=error_msg), dataframes
            return format_response(error=error_msg)

        def get_df_safe(dataset_name: str) -> pd.DataFrame:
            """Safely retrieves a DataFrame from the endpoint, returning an empty DataFrame on error."""
            if hasattr(profile_endpoint, dataset_name):
                dataset = getattr(profile_endpoint, dataset_name)
                if hasattr(dataset, 'get_data_frame'):
                    return dataset.get_data_frame()
            logger.warning(f"Dataset '{dataset_name}' not found or not a valid DataSet in PlayerProfileV2 for {player_actual_name} (ID: {player_id}).")
            return pd.DataFrame()

        career_totals_rs_df = get_df_safe('career_totals_regular_season')
        season_totals_rs_df = get_df_safe('season_totals_regular_season')
        career_totals_ps_df = get_df_safe('career_totals_post_season')
        season_totals_ps_df = get_df_safe('season_totals_post_season')
        season_highs_df = get_df_safe('season_highs')
        career_highs_df = get_df_safe('career_highs')
        next_game_df = get_df_safe('next_game')

        # Save DataFrames if requested
        if return_dataframe:
            dataframes["career_totals_regular_season"] = career_totals_rs_df
            dataframes["season_totals_regular_season"] = season_totals_rs_df
            dataframes["career_totals_post_season"] = career_totals_ps_df
            dataframes["season_totals_post_season"] = season_totals_ps_df
            dataframes["season_highs"] = season_highs_df
            dataframes["career_highs"] = career_highs_df
            dataframes["next_game"] = next_game_df

            # Save to CSV if not empty
            if not career_totals_rs_df.empty:
                csv_path = _get_csv_path_for_player_profile(player_id, effective_per_mode)
                _save_dataframe_to_csv(career_totals_rs_df, csv_path)

            if not season_totals_rs_df.empty:
                csv_path = get_cache_file_path(f"player_{player_id}_season_totals_rs_{effective_per_mode.replace(' ', '_').lower()}.csv", "player_dashboard/profile")
                _save_dataframe_to_csv(season_totals_rs_df, csv_path)

            if not career_totals_ps_df.empty:
                csv_path = get_cache_file_path(f"player_{player_id}_career_totals_ps_{effective_per_mode.replace(' ', '_').lower()}.csv", "player_dashboard/profile")
                _save_dataframe_to_csv(career_totals_ps_df, csv_path)

            if not season_totals_ps_df.empty:
                csv_path = get_cache_file_path(f"player_{player_id}_season_totals_ps_{effective_per_mode.replace(' ', '_').lower()}.csv", "player_dashboard/profile")
                _save_dataframe_to_csv(season_totals_ps_df, csv_path)

        season_highs_dict = _process_dataframe(season_highs_df, single_row=True)
        career_highs_dict = _process_dataframe(career_highs_df, single_row=True)
        next_game_dict = _process_dataframe(next_game_df, single_row=True)

        career_totals_rs = _process_dataframe(career_totals_rs_df, single_row=True)
        season_totals_rs_list = _process_dataframe(season_totals_rs_df, single_row=False)
        career_totals_ps = _process_dataframe(career_totals_ps_df, single_row=True)
        season_totals_ps_list = _process_dataframe(season_totals_ps_df, single_row=False)

        if career_totals_rs is None or season_totals_rs_list is None:
            logger.error(f"Essential profile data (regular season totals) processing failed for {player_actual_name}.")
            error_msg = Errors.PLAYER_PROFILE_PROCESSING.format(identifier=player_actual_name)
            if return_dataframe:
                return format_response(error=error_msg), dataframes
            return format_response(error=error_msg)

        logger.info(f"fetch_player_profile_logic completed for '{player_actual_name}'")
        response_data = {
            "player_name": player_actual_name, "player_id": player_id,
            "player_info": player_info_dict or {},
            "per_mode_requested": effective_per_mode,
            "career_highs": career_highs_dict or {},
            "season_highs": season_highs_dict or {},
            "next_game": next_game_dict or {},
            "career_totals": {
                "regular_season": career_totals_rs or {},
                "post_season": career_totals_ps or {}
            },
            "season_totals": {
                "regular_season": season_totals_rs_list or [],
                "post_season": season_totals_ps_list or []
            }
        }

        if return_dataframe:
            # Add DataFrame info to the response
            response_data["dataframe_info"] = {
                "message": "Player profile data has been converted to DataFrames and saved as CSV files",
                "dataframes": {
                    "career_totals_regular_season": {
                        "shape": list(career_totals_rs_df.shape) if not career_totals_rs_df.empty else [],
                        "columns": career_totals_rs_df.columns.tolist() if not career_totals_rs_df.empty else [],
                        "csv_path": get_relative_cache_path(f"player_{player_id}_profile_{effective_per_mode.replace(' ', '_').lower()}.csv", "player_dashboard/profile")
                    },
                    "season_totals_regular_season": {
                        "shape": list(season_totals_rs_df.shape) if not season_totals_rs_df.empty else [],
                        "columns": season_totals_rs_df.columns.tolist() if not season_totals_rs_df.empty else [],
                        "csv_path": get_relative_cache_path(f"player_{player_id}_season_totals_rs_{effective_per_mode.replace(' ', '_').lower()}.csv", "player_dashboard/profile")
                    }
                }
            }

            return format_response(response_data), dataframes

        return format_response(response_data)
    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_profile_logic: {e}")
        if return_dataframe:
            return format_response(error=str(e)), dataframes
        return format_response(error=str(e))
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_profile_logic: {e}")
        if return_dataframe:
            return format_response(error=str(e)), dataframes
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_profile_logic for '{player_name}': {e}", exc_info=True)
        error_msg = Errors.PLAYER_PROFILE_UNEXPECTED.format(identifier=player_name, error=str(e))
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

@lru_cache(maxsize=PLAYER_DEFENSE_CACHE_SIZE)
def fetch_player_defense_logic(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game, # Note: API uses PerModeSimple for this endpoint
    opponent_team_id: int = NBA_API_DEFAULT_TEAM_ID_ALL,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Fetches player defensive statistics against opponents.

    Args:
        player_name (str): Name or ID of the player.
        season (str, optional): Season in YYYY-YY format. Defaults to current.
        season_type (str, optional): Type of season. Defaults to Regular Season.
        per_mode (str, optional): Statistical mode (PerModeSimple). Defaults to PerGame.
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0 (all teams).
        date_from (Optional[str], optional): Start date filter (YYYY-MM-DD).
        date_to (Optional[str], optional): End date filter (YYYY-MM-DD).

    Returns:
        str: JSON string with defensive stats or an error message.
    """
    logger.info(
        f"Executing fetch_player_defense_logic for: '{player_name}', Season: {season}, Type: {season_type}, "
        f"PerMode: {per_mode}, Opponent: {opponent_team_id}, From: {date_from}, To: {date_to}"
    )

    param_error = _validate_common_dashboard_params(season, season_type, _VALID_PLAYER_DASHBOARD_SEASON_TYPES, date_from, date_to)
    if param_error:
        return format_response(error=param_error)

    if per_mode not in _VALID_DEFENSE_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_DEFENSE_PER_MODES)[:5]))
        logger.warning(error_msg)
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching playerdashptshotdefend for ID: {player_id}, Season: {season}")
        try:
            defense_endpoint = playerdashptshotdefend.PlayerDashPtShotDefend(
                player_id=player_id, team_id=NBA_API_DEFAULT_TEAM_ID_ALL, # team_id for player's team, 0 for all
                season=season, season_type_all_star=season_type,
                per_mode_simple=per_mode,
                opponent_team_id=opponent_team_id, date_from_nullable=date_from, date_to_nullable=date_to,
                timeout=settings.DEFAULT_TIMEOUT_SECONDS
            )
            logger.debug(f"playerdashptshotdefend API call successful for ID: {player_id}")
            # Assuming the first DataFrame is the relevant one, common for nba_api
            defense_df = defense_endpoint.get_data_frames()[0]
        except Exception as api_error:
            logger.error(f"nba_api playerdashptshotdefend failed for ID {player_id}, Season {season}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_DEFENSE_API.format(identifier=player_actual_name, season=season, error=str(api_error))
            return format_response(error=error_msg)

        defense_stats_list = _process_dataframe(defense_df, single_row=False)

        if defense_stats_list is None:
            logger.error(f"DataFrame processing failed for defense stats of {player_actual_name} (Season: {season})")
            error_msg = Errors.PLAYER_DEFENSE_PROCESSING.format(identifier=player_actual_name, season=season)
            return format_response(error=error_msg)

        if not defense_stats_list:
            logger.warning(f"No defense stats found for {player_actual_name} matching criteria.")
            return format_response({
                "player_name": player_actual_name, "player_id": player_id,
                "parameters": { "season": season, "season_type": season_type, "per_mode_requested": per_mode, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to },
                "summary": {}, "detailed_defense_stats_by_category": [],
                "message": "No defense stats found for the specified criteria."
            })

        defense_by_category = {item.get("DEFENSE_CATEGORY", "Unknown"): item for item in defense_stats_list}
        def get_cat_stats(cat_name: str, default_val: float = 0.0) -> Dict[str, Any]:
            data = defense_by_category.get(cat_name, {})
            return {
                "frequency": float(data.get("FREQ", default_val) or default_val),
                "field_goal_percentage_allowed": float(data.get("D_FG_PCT", default_val) or default_val),
                "impact_on_fg_percentage": float(data.get("PCT_PLUSMINUS", default_val) or default_val),
                "games_played": int(data.get("GP",0))
            }

        overall_raw = defense_by_category.get("Overall", {})
        summary = {
            "games_played": int(overall_raw.get("GP", 0)),
            "overall_defense": {
                "field_goal_percentage_allowed": float(overall_raw.get("D_FG_PCT", 0.0) or 0.0),
                "league_average_fg_percentage": float(overall_raw.get("NORMAL_FG_PCT", 0.0) or 0.0),
                "impact_on_fg_percentage": float(overall_raw.get("PCT_PLUSMINUS", 0.0) or 0.0)
            },
            "three_point_defense": get_cat_stats("3 Pointers"),
            "two_point_defense": get_cat_stats("2 Pointers"),
            "rim_protection_lt_6ft": get_cat_stats("Less Than 6 Ft"),
            "mid_range_defense_gt_15ft": get_cat_stats("Greater Than 15 Ft")
        }

        response_data = {
            "player_name": player_actual_name, "player_id": player_id,
            "parameters": { "season": season, "season_type": season_type, "per_mode_requested": per_mode, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to },
            "summary": summary,
            "detailed_defense_stats_by_category": defense_stats_list
        }
        logger.info(f"fetch_player_defense_logic completed for '{player_actual_name}'")
        return format_response(response_data)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_defense_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_defense_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_defense_logic for '{player_name}', Season {season}: {e}", exc_info=True)
        error_msg = Errors.PLAYER_DEFENSE_UNEXPECTED.format(identifier=player_name, season=season, error=str(e))
        return format_response(error=error_msg)

@lru_cache(maxsize=PLAYER_HUSTLE_CACHE_SIZE)
def fetch_player_hustle_stats_logic(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game, # Note: API uses PerModeTime for this endpoint
    player_name: Optional[str] = None,
    team_id: Optional[int] = None,
    league_id: str = LeagueID.nba,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Fetches player hustle statistics (e.g., screen assists, deflections).
    Can be filtered by player, team, or league-wide.

    Args:
        season (str, optional): Season in YYYY-YY format. Defaults to current.
        season_type (str, optional): Type of season. Defaults to Regular Season.
        per_mode (str, optional): Statistical mode (PerModeTime). Defaults to PerGame.
        player_name (Optional[str], optional): Filter by player name or ID.
        team_id (Optional[int], optional): Filter by team ID.
        league_id (str, optional): League ID. Defaults to NBA.
        date_from (Optional[str], optional): Start date filter (YYYY-MM-DD).
        date_to (Optional[str], optional): End date filter (YYYY-MM-DD).

    Returns:
        str: JSON string with hustle stats or an error message.
    """
    logger.info(
        f"Executing fetch_player_hustle_stats_logic for season {season}, type {season_type}, per_mode {per_mode}, "
        f"player '{player_name}', team '{team_id}', league '{league_id}', from '{date_from}', to '{date_to}'"
    )

    # Season can be None for some API calls if other filters are strong, but our logic requires it.
    # The API itself might allow season=None if e.g. date_from/to are provided, but we enforce season for clarity.
    param_error = _validate_common_dashboard_params(season, season_type, _VALID_PLAYER_DASHBOARD_SEASON_TYPES, date_from, date_to)
    if param_error:
        return format_response(error=param_error)

    if per_mode not in _VALID_HUSTLE_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_HUSTLE_PER_MODES)[:5]))
        logger.warning(error_msg)
        return format_response(error=error_msg)

    player_id_to_filter, player_actual_name_for_response = None, player_name
    if player_name:
        try:
            player_id_to_filter, player_actual_name_for_response = find_player_id_or_error(player_name)
        except PlayerNotFoundError as e:
            logger.warning(f"PlayerNotFoundError in fetch_player_hustle_stats_logic: {e}")
            return format_response(error=str(e))
        except ValueError as e: # Catch specific ValueError from find_player_id_or_error if name is empty
            logger.warning(f"ValueError finding player in fetch_player_hustle_stats_logic: {e}")
            return format_response(error=str(e))

    team_id_for_api = team_id if team_id is not None else NBA_API_DEFAULT_TEAM_ID_ALL
    try:
        logger.debug(f"Fetching leaguehustlestatsplayer for season {season}, team_id {team_id_for_api}")
        hustle_endpoint = leaguehustlestatsplayer.LeagueHustleStatsPlayer(
            season=season, season_type_all_star=season_type, per_mode_time=per_mode,
            league_id_nullable=league_id, date_from_nullable=date_from, date_to_nullable=date_to,
            team_id_nullable=team_id_for_api, timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        # Assuming the first DataFrame is the relevant one
        hustle_df = hustle_endpoint.get_data_frames()[0]
        logger.debug(f"leaguehustlestatsplayer API call successful.")
    except Exception as api_error:
        logger.error(f"nba_api leaguehustlestatsplayer failed: {api_error}", exc_info=True)
        error_msg = Errors.PLAYER_HUSTLE_API.format(error=str(api_error)) # Generic error as it can be league/team/player
        return format_response(error=error_msg)

    if hustle_df.empty:
        logger.warning(f"No hustle stats found for initial query (season {season}, team '{team_id_for_api}')")
        return format_response({
            "parameters": { "season": season, "season_type": season_type, "per_mode": per_mode, "player_name": player_actual_name_for_response, "team_id": team_id, "league_id": league_id, "date_from": date_from, "date_to": date_to },
            "hustle_stats": [], "message": "No hustle data found for the specified criteria."
        })

    if player_id_to_filter and 'PLAYER_ID' in hustle_df.columns:
        hustle_df = hustle_df[hustle_df['PLAYER_ID'] == player_id_to_filter]
        if hustle_df.empty:
            logger.warning(f"No hustle stats for player {player_actual_name_for_response} (ID: {player_id_to_filter}) after filtering.")
            return format_response({
                "parameters": { "season": season, "season_type": season_type, "per_mode": per_mode, "player_name": player_actual_name_for_response, "team_id": team_id, "league_id": league_id, "date_from": date_from, "date_to": date_to },
                "hustle_stats": [], "message": f"No hustle data found for player {player_actual_name_for_response} matching criteria."
            })
    elif player_id_to_filter and 'PLAYER_ID' not in hustle_df.columns: # Should not happen if API is consistent
        logger.error("PLAYER_ID column missing for player filtering in hustle stats.")
        return format_response(error="Could not filter hustle stats by player ID due to missing column.")

    # Limit broad league-wide results if no specific player or team is requested
    if player_name is None and team_id is None and len(hustle_df) > MAX_LEAGUE_WIDE_HUSTLE_RESULTS:
         logger.info(f"Limiting league-wide hustle stats to the top {MAX_LEAGUE_WIDE_HUSTLE_RESULTS} entries.")
         hustle_df = hustle_df.head(MAX_LEAGUE_WIDE_HUSTLE_RESULTS)

    hustle_stats_list = _process_dataframe(hustle_df, single_row=False)
    if hustle_stats_list is None: # Error during _process_dataframe
        logger.error(f"DataFrame processing failed for hustle stats.")
        # Use a more generic processing error as it's not tied to a specific player here
        error_msg = Errors.PROCESSING_ERROR.format(error="hustle stats data")
        return format_response(error=error_msg)

    result = {
        "parameters": {
             "season": season, "season_type": season_type, "per_mode": per_mode,
             "player_name": player_actual_name_for_response, "team_id": team_id, "league_id": league_id,
             "date_from": date_from, "date_to": date_to
         },
        "hustle_stats": hustle_stats_list
    }
    logger.info(f"Successfully fetched hustle stats for {len(hustle_stats_list)} entries matching criteria.")
    return format_response(result)

def fetch_player_fantasy_profile_logic(
    player_name: str,
    season: str,
    per_mode: str = "Totals",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches fantasy profile stats for a player for a given season.
    Args:
        player_name: The name or ID of the player.
        season: The NBA season (e.g., "2023-24").
        per_mode: Statistical mode ("Totals", "PerGame", "Per36").
        return_dataframe: Whether to return DataFrames along with the JSON response.
    Returns:
        If return_dataframe=False: JSON string with fantasy profile data or error.
        If return_dataframe=True: Tuple of (JSON string, dict of DataFrames).
    """
    dataframes = {}
    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        endpoint = PlayerFantasyProfile(
            player_id=player_id,
            season=season,
            per_mode36=per_mode,
            measure_type_base="Base",
            pace_adjust_no="N",
            plus_minus_no="N",
            rank_no="N",
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        # Dataset mapping from docs
        dataset_map = {
            "days_rest_modified": "DaysRestModified",
            "last_n_games": "LastNGames",
            "location": "Location",
            "opponent": "Opponent",
            "overall": "Overall"
        }
        for key, ds_name in dataset_map.items():
            if hasattr(endpoint, ds_name):
                df = getattr(endpoint, ds_name).get_data_frame()
                dataframes[key] = df
                # Save to CSV if not empty
                if not df.empty:
                    csv_path = get_cache_file_path(f"player_{player_id}_fantasy_{key}_{season}_{per_mode}.csv", "player_dashboard/fantasy")
                    _save_dataframe_to_csv(df, csv_path)
        # Prepare JSON response
        response_data = {
            "player_name": player_actual_name,
            "player_id": player_id,
            "season": season,
            "per_mode": per_mode,
            "fantasy_profile": {k: _process_dataframe(df, single_row=False) for k, df in dataframes.items()}
        }
        if return_dataframe:
            return format_response(response_data), dataframes
        return format_response(response_data)
    except PlayerNotFoundError as e:
        if return_dataframe:
            return format_response(error=str(e)), dataframes
        return format_response(error=str(e))
    except Exception as e:
        error_msg = f"Unexpected error in fetch_player_fantasy_profile_logic for '{player_name}': {e}"
        logger.critical(error_msg, exc_info=True)
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)
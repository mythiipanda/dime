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
    commonplayerinfo
)
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, PerMode36, LeagueID, PerModeSimple, PerModeTime
from config import settings
from core.errors import Errors
from api_tools.utils import (
    _process_dataframe,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)
from utils.validation import _validate_season_format, validate_date_format
from utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

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
    league_id: Optional[str] = None,
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
        league_id (str, optional): League ID to filter data. Defaults to None (NBA).
                                  Example: "00" for NBA.
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
        logger.debug(f"Fetching playerprofilev2 for ID: {player_id}, PerMode: {effective_per_mode}, LeagueID: {league_id}")
        try:
            profile_endpoint = playerprofilev2.PlayerProfileV2(
                player_id=player_id,
                per_mode36=effective_per_mode,
                league_id_nullable=league_id,
                timeout=settings.DEFAULT_TIMEOUT_SECONDS
            )
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

        # Fetch player info from commonplayerinfo endpoint
        try:
            logger.debug(f"Fetching commonplayerinfo for player ID: {player_id} ({player_actual_name})")
            info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
            player_info_df = info_endpoint.common_player_info.get_data_frame()
            player_info_dict = _process_dataframe(player_info_df, single_row=True)

            if player_info_dict is None:
                logger.warning(f"Failed to process player info for {player_actual_name}. Using empty dict.")
                player_info_dict = {}
        except Exception as info_error:
            logger.error(f"Error fetching commonplayerinfo for {player_actual_name}: {info_error}", exc_info=True)
            player_info_dict = {}

        logger.info(f"fetch_player_profile_logic completed for '{player_actual_name}'")
        response_data = {
            "player_name": player_actual_name, "player_id": player_id,
            "player_info": player_info_dict,
            "parameters": {
                "per_mode": effective_per_mode,
                "league_id": league_id
            },
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
                    "player_info": {
                        "shape": list(player_info_df.shape) if 'player_info_df' in locals() and not player_info_df.empty else [],
                        "columns": player_info_df.columns.tolist() if 'player_info_df' in locals() and not player_info_df.empty else [],
                        "csv_path": get_relative_cache_path(f"player_{player_id}_info.csv", "player_dashboard/profile")
                    },
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

            # Add player_info DataFrame to the dataframes dictionary if available
            if 'player_info_df' in locals() and not player_info_df.empty:
                dataframes["player_info"] = player_info_df

            # Save player_info DataFrame to CSV if available
            if 'player_info_df' in locals() and not player_info_df.empty:
                csv_path = get_cache_file_path(f"player_{player_id}_info.csv", "player_dashboard/profile")
                _save_dataframe_to_csv(player_info_df, csv_path)

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
    date_to: Optional[str] = None,
    last_n_games: int = 0,
    league_id: str = LeagueID.nba,
    month: int = 0,
    period: int = 0,
    team_id: int = NBA_API_DEFAULT_TEAM_ID_ALL,
    vs_conference: Optional[str] = None,
    vs_division: Optional[str] = None,
    season_segment: Optional[str] = None,
    outcome: Optional[str] = None,
    location: Optional[str] = None,
    game_segment: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player defensive stats against various opponents or overall.
    Provides DataFrame output capabilities.

    Args:
        player_name (str): The name or ID of the player.
        season (str, optional): The season in YYYY-YY format. Defaults to current NBA season.
        season_type (str, optional): Type of season (e.g., "Regular Season"). Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode (e.g., "PerGame"). Defaults to "PerGame".
                                 Note: Endpoint uses PerModeSimple.
        opponent_team_id (int, optional): Opponent's team ID. Defaults to 0 (all opponents).
        date_from (Optional[str], optional): Start date (YYYY-MM-DD). Defaults to None.
        date_to (Optional[str], optional): End date (YYYY-MM-DD). Defaults to None.
        last_n_games (int, optional): Number of most recent games to include. Defaults to 0 (all games).
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        month (int, optional): Month number (1-12). Defaults to 0 (all months).
        period (int, optional): Period number (1-4, 0 for all). Defaults to 0 (all periods).
        team_id (int, optional): Team ID of the player. Defaults to 0 (all teams).
        vs_conference (Optional[str], optional): Conference filter (e.g., "East", "West"). Defaults to None.
        vs_division (Optional[str], optional): Division filter. Defaults to None.
        season_segment (Optional[str], optional): Season segment filter (e.g., "Post All-Star"). Defaults to None.
        outcome (Optional[str], optional): Game outcome filter (e.g., "W", "L"). Defaults to None.
        location (Optional[str], optional): Game location filter (e.g., "Home", "Road"). Defaults to None.
        game_segment (Optional[str], optional): Game segment filter (e.g., "First Half"). Defaults to None.
        return_dataframe (bool, optional): Whether to return DataFrames. Defaults to False.

    Returns:
        If return_dataframe=False:
            str: JSON string with defensive stats or error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: JSON response and dictionary of DataFrames.
    """
    dataframes: Dict[str, pd.DataFrame] = {}
    logger.info(
        f"Executing fetch_player_defense_logic for: '{player_name}', Season: {season}, "
        f"SeasonType: {season_type}, PerMode: {per_mode}, OpponentTeamID: {opponent_team_id}, "
        f"DateFrom: {date_from}, DateTo: {date_to}, LastNGames: {last_n_games}, "
        f"LeagueID: {league_id}, Month: {month}, Period: {period}, TeamID: {team_id}, "
        f"VsConference: {vs_conference}, VsDivision: {vs_division}, SeasonSegment: {season_segment}, "
        f"Outcome: {outcome}, Location: {location}, GameSegment: {game_segment}, "
        f"DataFrame: {return_dataframe}"
    )

    # Validate parameters
    param_error = _validate_common_dashboard_params(season, season_type, _VALID_PLAYER_DASHBOARD_SEASON_TYPES, date_from, date_to)
    if param_error:
        logger.warning(param_error)
        if return_dataframe: return format_response(error=param_error), dataframes
        return format_response(error=param_error)

    if per_mode not in _VALID_DEFENSE_PER_MODES: # Ensure using the correct validation set
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_DEFENSE_PER_MODES)[:5]))
        logger.warning(error_msg)
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
    except PlayerNotFoundError as e:
        logger.warning(f"Player not found: {e}")
        if return_dataframe: return format_response(error=str(e)), dataframes
        return format_response(error=str(e))

    try:
        logger.debug(f"Fetching playerdashptshotdefend for ID: {player_id}, Season: {season}, PerMode: {per_mode}")
        defense_endpoint = playerdashptshotdefend.PlayerDashPtShotDefend(
            player_id=player_id,
            team_id=team_id,  # Player's team ID
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
            vs_conference_nullable=vs_conference,
            vs_division_nullable=vs_division,
            season_segment_nullable=season_segment,
            outcome_nullable=outcome,
            location_nullable=location,
            game_segment_nullable=game_segment,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )

        def_roll_up_df = defense_endpoint.defending_shots.get_data_frame() # This is the primary dataset

        if return_dataframe:
            dataframes["defending_shots"] = def_roll_up_df
            if not def_roll_up_df.empty:
                csv_path = _get_csv_path_for_player_defense(
                    player_id, season, season_type, per_mode, opponent_team_id
                )
                _save_dataframe_to_csv(def_roll_up_df, csv_path)

        processed_def_roll_up = _process_dataframe(def_roll_up_df, single_row=False) if not def_roll_up_df.empty else []

        if processed_def_roll_up is None and not def_roll_up_df.empty: # Processing error
            error_msg = Errors.PLAYER_DEFENSE_PROCESSING.format(identifier=player_actual_name, season=season)
            logger.error(error_msg)
            if return_dataframe: return format_response(error=error_msg), dataframes
            return format_response(error=error_msg)

        # Construct the response
        response_data = {
            "player_name": player_actual_name,
            "player_id": player_id,
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
                "team_id": team_id,
                "vs_conference": vs_conference,
                "vs_division": vs_division,
                "season_segment": season_segment,
                "outcome": outcome,
                "location": location,
                "game_segment": game_segment
            },
            "defending_shots": processed_def_roll_up
        }
        logger.info(f"Successfully fetched player defense stats for {player_actual_name}")
        if return_dataframe:
            return format_response(response_data), dataframes
        return format_response(response_data)

    except Exception as e:
        logger.error(f"API error in fetch_player_defense_logic for {player_actual_name}: {e}", exc_info=True)
        error_msg = Errors.PLAYER_DEFENSE_API.format(identifier=player_actual_name, error=str(e))
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

@lru_cache(maxsize=PLAYER_HUSTLE_CACHE_SIZE)
def fetch_player_hustle_stats_logic(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeTime.per_game, # Note: API uses PerModeTime for this endpoint
    player_name: Optional[str] = None,
    team_id: Optional[int] = None, # Team ID to filter by. Use 0 for all teams if player_name is None.
    league_id: str = LeagueID.nba,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    college: Optional[str] = None,
    conference: Optional[str] = None,
    country: Optional[str] = None,
    division: Optional[str] = None,
    draft_pick: Optional[str] = None,
    draft_year: Optional[str] = None,
    height: Optional[str] = None,
    location: Optional[str] = None,
    month: Optional[int] = None,
    opponent_team_id: Optional[int] = None,
    outcome: Optional[str] = None,
    po_round: Optional[str] = None,
    player_experience: Optional[str] = None,
    player_position: Optional[str] = None,
    season_segment: Optional[str] = None,
    vs_conference: Optional[str] = None,
    vs_division: Optional[str] = None,
    weight: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player or team hustle statistics (e.g., screen assists, deflections).
    Can fetch for a specific player, a specific team, or league-wide.
    Provides DataFrame output capabilities.

    Args:
        season (str, optional): The season in YYYY-YY format. Defaults to current NBA season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame". Endpoint uses PerModeTime.
        player_name (Optional[str], optional): Name or ID of the player. Defaults to None (league-wide).
        team_id (Optional[int], optional): Team ID. Defaults to None. If player_name is None and team_id is None,
                                          fetches league-wide stats. Use 0 for all teams when player_name is None.
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        date_from (Optional[str], optional): Start date (YYYY-MM-DD). Defaults to None.
        date_to (Optional[str], optional): End date (YYYY-MM-DD). Defaults to None.
        college (Optional[str], optional): College filter. Defaults to None.
        conference (Optional[str], optional): Conference filter. Defaults to None.
        country (Optional[str], optional): Country filter. Defaults to None.
        division (Optional[str], optional): Division filter. Defaults to None.
        draft_pick (Optional[str], optional): Draft pick filter. Defaults to None.
        draft_year (Optional[str], optional): Draft year filter. Defaults to None.
        height (Optional[str], optional): Height filter. Defaults to None.
        location (Optional[str], optional): Game location filter (e.g., "Home", "Road"). Defaults to None.
        month (Optional[int], optional): Month number (1-12). Defaults to None.
        opponent_team_id (Optional[int], optional): Opponent team ID filter. Defaults to None.
        outcome (Optional[str], optional): Game outcome filter (e.g., "W", "L"). Defaults to None.
        po_round (Optional[str], optional): Playoff round filter. Defaults to None.
        player_experience (Optional[str], optional): Player experience filter. Defaults to None.
        player_position (Optional[str], optional): Player position filter. Defaults to None.
        season_segment (Optional[str], optional): Season segment filter (e.g., "Post All-Star"). Defaults to None.
        vs_conference (Optional[str], optional): Conference filter (e.g., "East", "West"). Defaults to None.
        vs_division (Optional[str], optional): Division filter. Defaults to None.
        weight (Optional[str], optional): Weight filter. Defaults to None.
        return_dataframe (bool, optional): Whether to return DataFrames. Defaults to False.

    Returns:
        If return_dataframe=False:
            str: JSON string with hustle stats or error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: JSON response and dictionary of DataFrames.
    """
    dataframes: Dict[str, pd.DataFrame] = {}
    player_id_resolved: Optional[str] = None
    player_actual_name_resolved: Optional[str] = None
    effective_team_id: int = team_id if team_id is not None else NBA_API_DEFAULT_TEAM_ID_ALL

    log_identifier = "league-wide"
    if player_name:
        log_identifier = f"player '{player_name}'"
    elif team_id is not None: # team_id could be 0 for all teams, or a specific team
        log_identifier = f"team ID '{team_id}'"


    logger.info(
        f"Executing fetch_player_hustle_stats_logic for {log_identifier}, Season: {season}, "
        f"SeasonType: {season_type}, PerMode: {per_mode}, LeagueID: {league_id}, "
        f"DateFrom: {date_from}, DateTo: {date_to}, College: {college}, Conference: {conference}, "
        f"Country: {country}, Division: {division}, DraftPick: {draft_pick}, DraftYear: {draft_year}, "
        f"Height: {height}, Location: {location}, Month: {month}, OpponentTeamID: {opponent_team_id}, "
        f"Outcome: {outcome}, PORound: {po_round}, PlayerExperience: {player_experience}, "
        f"PlayerPosition: {player_position}, SeasonSegment: {season_segment}, "
        f"VsConference: {vs_conference}, VsDivision: {vs_division}, Weight: {weight}, "
        f"DataFrame: {return_dataframe}"
    )

    # Validate parameters
    param_error = _validate_common_dashboard_params(season, season_type, _VALID_PLAYER_DASHBOARD_SEASON_TYPES, date_from, date_to)
    if param_error:
        logger.warning(param_error)
        if return_dataframe: return format_response(error=param_error), dataframes
        return format_response(error=param_error)

    if per_mode not in _VALID_HUSTLE_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_HUSTLE_PER_MODES)[:5]))
        logger.warning(error_msg)
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    # Resolve player_id if player_name is provided
    if player_name:
        try:
            player_id_resolved, player_actual_name_resolved = find_player_id_or_error(player_name)
            # If a player is specified, team_id is often ignored by the hustle endpoint or means "player's team stats"
            # For leaguehustlestatsplayer, PlayerID takes precedence. TeamID is used if PlayerID is not set.
            effective_team_id = NBA_API_DEFAULT_TEAM_ID_ALL # Usually, for player-specific hustle, team context is not a direct filter on this endpoint.
        except PlayerNotFoundError as e:
            logger.warning(f"Player not found for hustle stats: {e}")
            if return_dataframe: return format_response(error=str(e)), dataframes
            return format_response(error=str(e))

    # NBA_API Specifics:
    # - If PlayerID is set, TeamID is for context but data is for the player.
    # - If PlayerID is NOT set, TeamID is used to filter for a team's hustle stats.
    # - If PlayerID and TeamID are NOT set (or team_id=0), it's league-wide.

    api_player_id_param = player_id_resolved if player_id_resolved else "0" # API expects "0" if no specific player
    # If player_id_resolved is None (no player_name given), then effective_team_id (which is team_id or 0) is used.
    # If player_id_resolved is set, the API typically uses this and team_id becomes contextual or ignored.
    # For leaguehustlestatsplayer, if player_id_resolved is set, team_id param is less critical.
    # If player_id_resolved is NOT set, team_id (or 0 for league-wide) is the filter.
    api_team_id_param = effective_team_id

    if player_id_resolved: # Specific player
        api_team_id_param = NBA_API_DEFAULT_TEAM_ID_ALL # For specific player, API often wants team_id=0
    # else: api_team_id_param remains effective_team_id (user's team_id or 0 for league-wide)


    try:
        logger.debug(
            f"Fetching leaguehustlestatsplayer - PlayerID: {api_player_id_param}, TeamID: {api_team_id_param}, "
            f"Season: {season}, PerMode: {per_mode}, LeagueID: {league_id}"
        )
        hustle_endpoint = leaguehustlestatsplayer.LeagueHustleStatsPlayer(
            per_mode_time=per_mode,
            season_type_all_star=season_type,
            season=season,
            league_id_nullable=league_id,
            date_from_nullable=date_from,
            date_to_nullable=date_to,
            college_nullable=college,
            conference_nullable=conference,
            country_nullable=country,
            division_simple_nullable=division,
            draft_pick_nullable=draft_pick,
            draft_year_nullable=draft_year,
            height_nullable=height,
            location_nullable=location,
            month_nullable=month,
            opponent_team_id_nullable=opponent_team_id,
            outcome_nullable=outcome,
            po_round_nullable=po_round,
            player_experience_nullable=player_experience,
            player_position_nullable=player_position,
            season_segment_nullable=season_segment,
            vs_conference_nullable=vs_conference,
            vs_division_nullable=vs_division,
            weight_nullable=weight,
            team_id_nullable=api_team_id_param,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"LeagueHustleStatsPlayer API call successful for {log_identifier}")

        hustle_stats_df = hustle_endpoint.hustle_stats_player.get_data_frame()

        # If a specific player_id was intended, filter the league-wide results
        if player_id_resolved and not hustle_stats_df.empty:
            hustle_stats_df = hustle_stats_df[hustle_stats_df['PLAYER_ID'] == player_id_resolved].reset_index(drop=True)
            if hustle_stats_df.empty:
                logger.warning(f"Player ID {player_id_resolved} not found in LeagueHustleStatsPlayer results for {log_identifier}")

        if return_dataframe:
            dataframes["hustle_stats"] = hustle_stats_df
            if not hustle_stats_df.empty:
                csv_path = _get_csv_path_for_player_hustle(
                    season, season_type, per_mode, player_id_resolved, team_id if not player_id_resolved else None, league_id
                )
                _save_dataframe_to_csv(hustle_stats_df, csv_path)

        # Limit results if league-wide and too many rows
        if not player_id_resolved and (team_id is None or team_id == NBA_API_DEFAULT_TEAM_ID_ALL) and len(hustle_stats_df) > MAX_LEAGUE_WIDE_HUSTLE_RESULTS:
            logger.warning(f"League-wide hustle stats query returned {len(hustle_stats_df)} results. Capping at {MAX_LEAGUE_WIDE_HUSTLE_RESULTS} for response.")
            hustle_stats_df_limited = hustle_stats_df.head(MAX_LEAGUE_WIDE_HUSTLE_RESULTS)
            processed_hustle_stats = _process_dataframe(hustle_stats_df_limited, single_row=False)
            additional_info = f" (Results capped at {MAX_LEAGUE_WIDE_HUSTLE_RESULTS})"
        else:
            processed_hustle_stats = _process_dataframe(hustle_stats_df, single_row=False) if not hustle_stats_df.empty else []
            additional_info = ""


        if processed_hustle_stats is None and not hustle_stats_df.empty : # Processing error
            error_msg = Errors.PLAYER_HUSTLE_PROCESSING.format(identifier=log_identifier, season=season)
            logger.error(error_msg)
            if return_dataframe: return format_response(error=error_msg), dataframes
            return format_response(error=error_msg)

        # Construct the response
        response_data = {
            "parameters": {
                "season": season,
                "season_type": season_type,
                "per_mode": per_mode,
                "player_name_filter": player_actual_name_resolved,
                "player_id_filter": player_id_resolved,
                "team_id_filter": team_id, # Original team_id from request
                "league_id": league_id,
                "date_from": date_from,
                "date_to": date_to,
                "college": college,
                "conference": conference,
                "country": country,
                "division": division,
                "draft_pick": draft_pick,
                "draft_year": draft_year,
                "height": height,
                "location": location,
                "month": month,
                "opponent_team_id": opponent_team_id,
                "outcome": outcome,
                "po_round": po_round,
                "player_experience": player_experience,
                "player_position": player_position,
                "season_segment": season_segment,
                "vs_conference": vs_conference,
                "vs_division": vs_division,
                "weight": weight,
                "info": f"Hustle stats for {log_identifier}{additional_info}"
            },
            "hustle_stats": processed_hustle_stats
        }
        logger.info(f"Successfully fetched hustle stats for {log_identifier}")
        if return_dataframe:
            return format_response(response_data), dataframes
        return format_response(response_data)

    except Exception as e:
        logger.error(f"API error in fetch_player_hustle_stats_logic for {log_identifier}: {e}", exc_info=True)
        error_msg = Errors.PLAYER_HUSTLE_API.format(identifier=log_identifier, error=str(e))
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)
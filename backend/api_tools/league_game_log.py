"""
Handles fetching game logs for the entire league.
Provides both JSON and DataFrame outputs with CSV caching.

This module implements the LeagueGameLog endpoint, which provides
comprehensive game-by-game statistics for all teams or players across the league.
"""
import os
import logging
import json
from typing import Optional, Dict, Any, Union, Tuple, List, Set
import pandas as pd

from nba_api.stats.endpoints import leaguegamelog
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, LeagueID, Direction, PlayerOrTeamAbbreviation, Sorter
)
from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response
)
from ..utils.path_utils import get_cache_dir, get_cache_file_path
from ..utils.validation import _validate_season_format, validate_date_format

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
LEAGUE_GAME_LOG_CACHE_SIZE = 128
LEAGUE_GAME_LOG_CSV_DIR = get_cache_dir("league_game_log")

# Valid parameter values
_VALID_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar)
                               if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}

_VALID_LEAGUE_IDS: Set[str] = {getattr(LeagueID, attr) for attr in dir(LeagueID)
                             if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

_VALID_DIRECTIONS: Set[str] = {getattr(Direction, attr) for attr in dir(Direction)
                             if not attr.startswith('_') and isinstance(getattr(Direction, attr), str)}

_VALID_PLAYER_OR_TEAM: Set[str] = {getattr(PlayerOrTeamAbbreviation, attr) for attr in dir(PlayerOrTeamAbbreviation)
                                 if not attr.startswith('_') and isinstance(getattr(PlayerOrTeamAbbreviation, attr), str)}

_VALID_SORTERS: Set[str] = {getattr(Sorter, attr) for attr in dir(Sorter)
                          if not attr.startswith('_') and isinstance(getattr(Sorter, attr), str)}

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

def _get_csv_path_for_game_log(
    season: str,
    season_type: str,
    player_or_team: str,
    league_id: str,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None
) -> str:
    """
    Generates a file path for saving a league game log DataFrame as CSV.

    Args:
        season: The season in YYYY-YY format
        season_type: The season type (e.g., Regular Season, Playoffs)
        player_or_team: Whether to get player or team game logs (P or T)
        league_id: The league ID (e.g., 00 for NBA)
        date_from_nullable: Optional start date filter
        date_to_nullable: Optional end date filter

    Returns:
        Path to the CSV file
    """
    # Clean up parameters for filename
    season_clean = season.replace("-", "_")
    season_type_clean = season_type.replace(" ", "_").lower()
    player_or_team_clean = "player" if player_or_team == PlayerOrTeamAbbreviation.player else "team"

    # Create filename with optional filters
    filename_parts = [
        f"game_log_{season_clean}_{season_type_clean}_{player_or_team_clean}_{league_id}"
    ]

    if date_from_nullable:
        date_from_clean = date_from_nullable.replace("-", "")
        filename_parts.append(f"from_{date_from_clean}")

    if date_to_nullable:
        date_to_clean = date_to_nullable.replace("-", "")
        filename_parts.append(f"to_{date_to_clean}")

    filename = "_".join(filename_parts) + ".csv"

    return get_cache_file_path(filename, "league_game_log")

# --- Main Logic Function ---
def fetch_league_game_log_logic(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    player_or_team: str = PlayerOrTeamAbbreviation.team,
    league_id: str = LeagueID.nba,
    direction: str = Direction.asc,
    sorter: str = Sorter.date,
    counter: int = 0,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches game logs for the entire league using the LeagueGameLog endpoint.

    This endpoint provides comprehensive game-by-game statistics for all teams or players
    across the league, with options to filter by date range and sort the results.

    The data includes:
    - Game information (date, matchup, win/loss)
    - Team or player identification (ID, name, abbreviation)
    - Basic statistics (points, rebounds, assists, etc.)
    - Shooting percentages (FG%, 3P%, FT%)
    - Advanced metrics (plus/minus)

    Args:
        season (str): Season in YYYY-YY format (e.g., "2023-24"). Defaults to current season.
        season_type (str): Season type from SeasonTypeAllStar (e.g., "Regular Season", "Playoffs").
            Defaults to "Regular Season".
        player_or_team (str): Whether to get player or team game logs from PlayerOrTeam (e.g., "P", "T").
            Defaults to "T" (team).
        league_id (str): League ID from LeagueID (e.g., "00" for NBA). Defaults to "00".
        direction (str): Sort direction from Direction (e.g., "ASC", "DESC").
            Defaults to "ASC".
        sorter (str): Field to sort by from Sorter (e.g., "DATE", "PTS").
            Defaults to "DATE".
        counter (int): Counter parameter required by the API. Defaults to 0.
        date_from_nullable (Optional[str]): Start date filter in YYYY-MM-DD format.
        date_to_nullable (Optional[str]): End date filter in YYYY-MM-DD format.
        return_dataframe (bool): Whether to return DataFrames. Defaults to False.

    Returns:
        If return_dataframe=False:
            str: JSON string with game log data or error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: JSON response and dictionary of DataFrames.
    """
    logger.info(
        f"Executing fetch_league_game_log_logic for: "
        f"Season: {season}, Type: {season_type}, Player/Team: {player_or_team}"
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

    if league_id not in _VALID_LEAGUE_IDS:
        error_response = format_response(error=Errors.INVALID_LEAGUE_ID.format(
            value=league_id, options=", ".join(list(_VALID_LEAGUE_IDS)[:5])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if player_or_team not in _VALID_PLAYER_OR_TEAM:
        error_response = format_response(error=f"Invalid player_or_team: '{player_or_team}'. Valid options: {', '.join(list(_VALID_PLAYER_OR_TEAM))}")
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if direction not in _VALID_DIRECTIONS:
        error_response = format_response(error=f"Invalid direction: '{direction}'. Valid options: {', '.join(list(_VALID_DIRECTIONS))}")
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if sorter not in _VALID_SORTERS:
        error_response = format_response(error=f"Invalid sorter: '{sorter}'. Valid options: {', '.join(list(_VALID_SORTERS)[:5])}...")
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
            "player_or_team_abbreviation": player_or_team,  # This is the parameter name in the Python API
            "league_id": league_id,
            "direction": direction,
            "sorter": sorter,
            "counter": counter,
            "timeout": settings.DEFAULT_TIMEOUT_SECONDS
        }

        # Add optional parameters if provided
        if date_from_nullable:
            api_params["date_from_nullable"] = date_from_nullable
        if date_to_nullable:
            api_params["date_to_nullable"] = date_to_nullable

        # Filter out None values for cleaner logging
        filtered_api_params = {k: v for k, v in api_params.items() if v is not None and k != "timeout"}

        logger.debug(f"Calling LeagueGameLog with parameters: {filtered_api_params}")
        game_log_endpoint = leaguegamelog.LeagueGameLog(**api_params)

        # Get data frames
        game_log_df = game_log_endpoint.get_data_frames()[0]

        # Store DataFrame if requested
        if return_dataframe:
            dataframes["LeagueGameLog"] = game_log_df

            # Save to CSV if not empty
            if not game_log_df.empty:
                csv_path = _get_csv_path_for_game_log(
                    season, season_type, player_or_team, league_id,
                    date_from_nullable, date_to_nullable
                )
                _save_dataframe_to_csv(game_log_df, csv_path)

        # Process for JSON response
        processed_data = _process_dataframe(game_log_df, single_row=False)

        # Create result dictionary
        result_dict = {
            "parameters": filtered_api_params,
            "game_log": processed_data or []
        }

        # Return response
        logger.info(f"Successfully fetched game logs for {season} {season_type}")
        if return_dataframe:
            return format_response(result_dict), dataframes
        return format_response(result_dict)

    except Exception as e:
        logger.error(
            f"API error in fetch_league_game_log_logic: {e}",
            exc_info=True
        )
        error_msg = f"Error fetching game logs: {str(e)}"
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

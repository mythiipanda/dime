"""
Handles fetching team passing statistics, including passes made and received.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
from typing import Optional, Dict, List, Any, Union, Tuple
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import teamdashptpass
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response,
    find_team_id_or_error,
    TeamNotFoundError
)
from ..utils.validation import _validate_season_format
from ..utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Cache Directory Setup ---
TEAM_PASSING_CSV_DIR = get_cache_dir("team_passing")

# --- Helper Functions for CSV Caching ---
def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves a DataFrame to a CSV file, creating the directory if it doesn't exist.

    Args:
        df: The DataFrame to save
        file_path: The path to save the CSV file
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Save DataFrame to CSV
        df.to_csv(file_path, index=False)
        logger.debug(f"Saved DataFrame to {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to {file_path}: {e}", exc_info=True)

def _get_csv_path_for_team_passing(
    team_name: str,
    data_type: str,
    season: str,
    season_type: str,
    per_mode: str
) -> str:
    """
    Generates a file path for saving team passing DataFrame as CSV.

    Args:
        team_name: The team's name
        data_type: The type of data ('passes_made' or 'passes_received')
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        per_mode: The per mode (e.g., 'PerGame', 'Totals')

    Returns:
        Path to the CSV file
    """
    # Clean team name and data type for filename
    clean_team_name = team_name.replace(" ", "_").replace(".", "").lower()
    clean_season_type = season_type.replace(" ", "_").lower()
    clean_per_mode = per_mode.replace(" ", "_").lower()

    filename = f"{clean_team_name}_{data_type}_{season}_{clean_season_type}_{clean_per_mode}.csv"
    return get_cache_file_path(filename, "team_passing")

@lru_cache(maxsize=128)
def fetch_team_passing_stats_logic(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    last_n_games: int = 0,
    league_id: str = "00",
    month: int = 0,
    opponent_team_id: int = 0,
    vs_division_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches team passing statistics, including passes made and received.
    Provides DataFrame output capabilities.

    Args:
        team_identifier: Name, abbreviation, or ID of the team.
        season: NBA season in YYYY-YY format. Defaults to current season.
        season_type: Type of season. Defaults to Regular Season.
        per_mode: Statistical mode. Defaults to PerGame.
        last_n_games: Number of games to include (0 for all games).
        league_id: League ID (default: "00" for NBA).
        month: Month number (0 for all months).
        opponent_team_id: Filter by opponent team ID (0 for all teams).
        vs_division_nullable: Filter by division (e.g., "Atlantic", "Central").
        vs_conference_nullable: Filter by conference (e.g., "East", "West").
        season_segment_nullable: Filter by season segment (e.g., "Post All-Star", "Pre All-Star").
        outcome_nullable: Filter by game outcome (e.g., "W", "L").
        location_nullable: Filter by game location (e.g., "Home", "Road").
        date_from_nullable: Start date filter in format YYYY-MM-DD.
        date_to_nullable: End date filter in format YYYY-MM-DD.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string with team passing statistics or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_team_passing_stats_logic for: '{team_identifier}', Season: {season}, PerMode: {per_mode}, " +
              f"LastNGames: {last_n_games}, LeagueID: {league_id}, Month: {month}, OpponentTeamID: {opponent_team_id}, " +
              f"VsDivision: {vs_division_nullable}, VsConference: {vs_conference_nullable}, " +
              f"SeasonSegment: {season_segment_nullable}, Outcome: {outcome_nullable}, Location: {location_nullable}, " +
              f"DateFrom: {date_from_nullable}, DateTo: {date_to_nullable}, DataFrame: {return_dataframe}")

    # Store DataFrames if requested
    dataframes = {}

    if not team_identifier or not str(team_identifier).strip():
        if return_dataframe:
            return format_response(error=Errors.TEAM_IDENTIFIER_EMPTY), dataframes
        return format_response(error=Errors.TEAM_IDENTIFIER_EMPTY)

    if not season or not _validate_season_format(season):
        if return_dataframe:
            return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season)), dataframes
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        if return_dataframe:
            return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5]))), dataframes
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5])))

    VALID_PER_MODES = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}
    if per_mode not in VALID_PER_MODES:
        if return_dataframe:
            return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(VALID_PER_MODES)[:3]))), dataframes
        return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(VALID_PER_MODES)[:3])))

    try:
        team_id, team_actual_name = find_team_id_or_error(team_identifier)
        logger.debug(f"Fetching teamdashptpass for Team ID: {team_id}, Season: {season}, PerMode: {per_mode}")
        try:
            passing_stats_endpoint = teamdashptpass.TeamDashPtPass(
                team_id=team_id,
                season=season,
                season_type_all_star=season_type,
                per_mode_simple=per_mode,
                last_n_games=last_n_games,
                league_id=league_id,
                month=month,
                opponent_team_id=opponent_team_id,
                vs_division_nullable=vs_division_nullable,
                vs_conference_nullable=vs_conference_nullable,
                season_segment_nullable=season_segment_nullable,
                outcome_nullable=outcome_nullable,
                location_nullable=location_nullable,
                date_from_nullable=date_from_nullable,
                date_to_nullable=date_to_nullable,
                timeout=settings.DEFAULT_TIMEOUT_SECONDS
            )
            logger.debug(f"teamdashptpass API call successful for ID: {team_id}, Season: {season}")
            passes_made_df = passing_stats_endpoint.passes_made.get_data_frame()
            passes_received_df = passing_stats_endpoint.passes_received.get_data_frame()
        except Exception as api_error:
            logger.error(f"nba_api teamdashptpass failed for ID {team_id}, Season {season}: {api_error}", exc_info=True)
            error_msg = Errors.TEAM_PASSING_API.format(identifier=str(team_id), season=season, error=str(api_error))
            if return_dataframe:
                return format_response(error=error_msg), dataframes
            return format_response(error=error_msg)

        # Save DataFrames to CSV if requested and not empty
        if return_dataframe:
            # Add DataFrames to the dictionary
            dataframes["passes_made"] = passes_made_df
            dataframes["passes_received"] = passes_received_df

            # Save passes_made DataFrame to CSV if not empty
            if not passes_made_df.empty:
                passes_made_csv_path = _get_csv_path_for_team_passing(
                    team_actual_name, "passes_made", season, season_type, per_mode
                )
                _save_dataframe_to_csv(passes_made_df, passes_made_csv_path)

            # Save passes_received DataFrame to CSV if not empty
            if not passes_received_df.empty:
                passes_received_csv_path = _get_csv_path_for_team_passing(
                    team_actual_name, "passes_received", season, season_type, per_mode
                )
                _save_dataframe_to_csv(passes_received_df, passes_received_csv_path)

        passes_made_list = _process_dataframe(passes_made_df, single_row=False)
        passes_received_list = _process_dataframe(passes_received_df, single_row=False)

        if passes_made_list is None or passes_received_list is None:
            if passes_made_df.empty and passes_received_df.empty:
                logger.warning(f"No passing stats found for team {team_actual_name} ({team_id}), season {season}.")
                passes_made_list, passes_received_list = [], []
            else:
                logger.error(f"DataFrame processing failed for team passing stats of {team_actual_name} ({season}).")
                error_msg = Errors.TEAM_PASSING_PROCESSING.format(identifier=str(team_id), season=season)
                if return_dataframe:
                    return format_response(error=error_msg), dataframes
                return format_response(error=error_msg)

        result = {
            "team_name": team_actual_name,
            "team_id": team_id,
            "season": season,
            "season_type": season_type,
            "parameters": {
                "per_mode": per_mode,
                "last_n_games": last_n_games,
                "league_id": league_id,
                "month": month,
                "opponent_team_id": opponent_team_id,
                "vs_division": vs_division_nullable,
                "vs_conference": vs_conference_nullable,
                "season_segment": season_segment_nullable,
                "outcome": outcome_nullable,
                "location": location_nullable,
                "date_from": date_from_nullable,
                "date_to": date_to_nullable
            },
            "passes_made": passes_made_list or [],
            "passes_received": passes_received_list or []
        }

        # Add DataFrame metadata to the response if returning DataFrames
        if return_dataframe:
            result["dataframe_info"] = {
                "message": "Team passing data has been converted to DataFrames and saved as CSV files",
                "dataframes": {}
            }

            # Add metadata for passes_made DataFrame if not empty
            if not passes_made_df.empty:
                passes_made_csv_path = _get_csv_path_for_team_passing(
                    team_actual_name, "passes_made", season, season_type, per_mode
                )
                csv_filename = os.path.basename(passes_made_csv_path)
                relative_path = get_relative_cache_path(csv_filename, "team_passing")

                result["dataframe_info"]["dataframes"]["passes_made"] = {
                    "shape": list(passes_made_df.shape),
                    "columns": passes_made_df.columns.tolist(),
                    "csv_path": relative_path
                }

            # Add metadata for passes_received DataFrame if not empty
            if not passes_received_df.empty:
                passes_received_csv_path = _get_csv_path_for_team_passing(
                    team_actual_name, "passes_received", season, season_type, per_mode
                )
                csv_filename = os.path.basename(passes_received_csv_path)
                relative_path = get_relative_cache_path(csv_filename, "team_passing")

                result["dataframe_info"]["dataframes"]["passes_received"] = {
                    "shape": list(passes_received_df.shape),
                    "columns": passes_received_df.columns.tolist(),
                    "csv_path": relative_path
                }

        logger.info(f"fetch_team_passing_stats_logic completed for '{team_actual_name}'")

        if return_dataframe:
            return format_response(result), dataframes
        return format_response(result)

    except (TeamNotFoundError, ValueError) as lookup_error:
        logger.warning(f"Team lookup or validation failed for '{team_identifier}': {lookup_error}")
        if return_dataframe:
            return format_response(error=str(lookup_error)), dataframes
        return format_response(error=str(lookup_error))
    except Exception as unexpected_error:
        error_msg = Errors.TEAM_PASSING_UNEXPECTED.format(identifier=team_identifier, season=season, error=str(unexpected_error))
        logger.critical(error_msg, exc_info=True)
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)
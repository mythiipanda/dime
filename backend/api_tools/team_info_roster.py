"""
Handles fetching comprehensive team information, including common details,
season ranks, roster, and coaching staff.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
from typing import Optional, Dict, List, Tuple, Any, Set, Union
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import teaminfocommon, commonteamroster
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar

from config import settings
from core.errors import Errors
from api_tools.utils import (
    _process_dataframe,
    format_response,
    find_team_id_or_error,
    TeamNotFoundError
)
from utils.validation import _validate_season_format
from utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
TEAM_INFO_ROSTER_CACHE_SIZE = 128
_TEAM_INFO_VALID_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_TEAM_INFO_VALID_LEAGUE_IDS: Set[str] = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

# --- Cache Directory Setup ---
TEAM_INFO_CSV_DIR = get_cache_dir("team_info")

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

def _get_csv_path_for_team_info(
    team_name: str,
    data_type: str,
    season: str,
    league_id: str
) -> str:
    """
    Generates a file path for saving team info/roster DataFrame as CSV.

    Args:
        team_name: The team's name
        data_type: The type of data ('info', 'ranks', 'roster', 'coaches')
        season: The season in YYYY-YY format
        league_id: The league ID

    Returns:
        Path to the CSV file
    """
    # Clean team name and data type for filename
    clean_team_name = team_name.replace(" ", "_").replace(".", "").lower()

    filename = f"{clean_team_name}_{data_type}_{season}_{league_id}.csv"
    return get_cache_file_path(filename, "team_info")

# --- Helper Functions ---
def _fetch_team_details_and_ranks(
    team_id: int, season: str, season_type: str, league_id: str,
    team_name: str = "", return_dataframe: bool = False
) -> Union[Tuple[Dict[str, Any], Dict[str, Any], List[str]],
           Tuple[Dict[str, Any], Dict[str, Any], List[str], pd.DataFrame, pd.DataFrame]]:
    """
    Fetches and processes team info and season ranks from teaminfocommon.

    Args:
        team_id: The team's ID
        season: NBA season in YYYY-YY format
        season_type: Type of season (e.g., "Regular Season")
        league_id: League ID (e.g., "00" for NBA)
        team_name: The team's name (for CSV file naming)
        return_dataframe: Whether to return the original DataFrames

    Returns:
        If return_dataframe=False:
            Tuple[Dict[str, Any], Dict[str, Any], List[str]]: Processed data and error messages
        If return_dataframe=True:
            Tuple[Dict[str, Any], Dict[str, Any], List[str], pd.DataFrame, pd.DataFrame]:
                Processed data, error messages, and original DataFrames
    """
    info_dict, ranks_dict = {}, {}
    current_errors: List[str] = []
    team_info_df = pd.DataFrame()
    team_ranks_df = pd.DataFrame()

    logger.debug(f"Fetching teaminfocommon for Team ID: {team_id}, Season: {season}, Type: {season_type}, League: {league_id}")
    try:
        team_info_endpoint = teaminfocommon.TeamInfoCommon(
            team_id=team_id, season_nullable=season, league_id=league_id,
            season_type_nullable=season_type, timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        team_info_df = team_info_endpoint.team_info_common.get_data_frame()
        team_ranks_df = team_info_endpoint.team_season_ranks.get_data_frame()

        # Save DataFrames to CSV if requested and not empty
        if return_dataframe and team_name:
            if not team_info_df.empty:
                info_csv_path = _get_csv_path_for_team_info(team_name, "info", season, league_id)
                _save_dataframe_to_csv(team_info_df, info_csv_path)

            if not team_ranks_df.empty:
                ranks_csv_path = _get_csv_path_for_team_info(team_name, "ranks", season, league_id)
                _save_dataframe_to_csv(team_ranks_df, ranks_csv_path)

        info_dict = _process_dataframe(team_info_df, single_row=True) if not team_info_df.empty else {}
        ranks_dict = _process_dataframe(team_ranks_df, single_row=True) if not team_ranks_df.empty else {}

        if team_info_df.empty and team_ranks_df.empty:
            logger.warning(f"No team info/ranks data returned by API for team {team_id}, season {season}.")
        # _process_dataframe returns None on internal error, or empty dict for empty df
        if info_dict is None or ranks_dict is None: # Check for None which indicates processing failure
             current_errors.append("team info/ranks processing")
             logger.error(Errors.TEAM_PROCESSING.format(data_type="team info/ranks", identifier=str(team_id), season=season))
             info_dict = info_dict or {} # Ensure they are dicts even if one failed
             ranks_dict = ranks_dict or {}
    except Exception as api_error:
        error_msg = Errors.TEAM_API.format(data_type="teaminfocommon", identifier=str(team_id), season=season, error=str(api_error))
        logger.error(error_msg, exc_info=True)
        current_errors.append("team info/ranks API")

    if return_dataframe:
        return info_dict or {}, ranks_dict or {}, current_errors, team_info_df, team_ranks_df
    return info_dict or {}, ranks_dict or {}, current_errors

def _fetch_team_roster_and_coaches(
    team_id: int, season: str, league_id: str,
    team_name: str = "", return_dataframe: bool = False
) -> Union[Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]],
           Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str], pd.DataFrame, pd.DataFrame]]:
    """
    Fetches and processes team roster and coaches from commonteamroster.

    Args:
        team_id: The team's ID
        season: NBA season in YYYY-YY format
        league_id: League ID (e.g., "00" for NBA)
        team_name: The team's name (for CSV file naming)
        return_dataframe: Whether to return the original DataFrames

    Returns:
        If return_dataframe=False:
            Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]: Processed data and error messages
        If return_dataframe=True:
            Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str], pd.DataFrame, pd.DataFrame]:
                Processed data, error messages, and original DataFrames
    """
    roster_list, coaches_list = [], []
    current_errors: List[str] = []
    roster_df = pd.DataFrame()
    coaches_df = pd.DataFrame()

    logger.debug(f"Fetching commonteamroster for Team ID: {team_id}, Season: {season}, League: {league_id}")
    try:
        roster_endpoint = commonteamroster.CommonTeamRoster(
            team_id=team_id, season=season, league_id_nullable=league_id, timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        roster_df = roster_endpoint.common_team_roster.get_data_frame()
        coaches_df = roster_endpoint.coaches.get_data_frame()

        # Save DataFrames to CSV if requested and not empty
        if return_dataframe and team_name:
            if not roster_df.empty:
                roster_csv_path = _get_csv_path_for_team_info(team_name, "roster", season, league_id)
                _save_dataframe_to_csv(roster_df, roster_csv_path)

            if not coaches_df.empty:
                coaches_csv_path = _get_csv_path_for_team_info(team_name, "coaches", season, league_id)
                _save_dataframe_to_csv(coaches_df, coaches_csv_path)

        roster_list = _process_dataframe(roster_df, single_row=False) if not roster_df.empty else []
        coaches_list = _process_dataframe(coaches_df, single_row=False) if not coaches_df.empty else []

        if roster_df.empty and coaches_df.empty:
            logger.warning(f"No roster/coaches data returned by API for team {team_id}, season {season}.")
        if roster_list is None or coaches_list is None: # Check for None which indicates processing failure
            current_errors.append("roster/coaches processing")
            logger.error(Errors.TEAM_PROCESSING.format(data_type="roster/coaches", identifier=str(team_id), season=season))
            roster_list = roster_list or [] # Ensure they are lists even if one failed
            coaches_list = coaches_list or []
    except Exception as api_error:
        error_msg = Errors.TEAM_API.format(data_type="commonteamroster", identifier=str(team_id), season=season, error=str(api_error))
        logger.error(error_msg, exc_info=True)
        current_errors.append("roster/coaches API")

    if return_dataframe:
        return roster_list or [], coaches_list or [], current_errors, roster_df, coaches_df
    return roster_list or [], coaches_list or [], current_errors

# --- Main Logic Function ---
@lru_cache(maxsize=TEAM_INFO_ROSTER_CACHE_SIZE)
def fetch_team_info_and_roster_logic(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    league_id: str = LeagueID.nba,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches comprehensive team information including basic details, conference/division ranks,
    current season roster, and coaching staff for a specified team and season.
    Provides DataFrame output capabilities.

    Args:
        team_identifier: Name, abbreviation, or ID of the team.
        season: NBA season in YYYY-YY format. Defaults to current season.
        season_type: Type of season. Defaults to Regular Season.
        league_id: League ID. Defaults to NBA.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string with team information or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_team_info_and_roster_logic for: '{team_identifier}', Season: {season}, Type: {season_type}, League: {league_id}, DataFrame: {return_dataframe}")

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

    if season_type not in _TEAM_INFO_VALID_SEASON_TYPES:
        if return_dataframe:
            return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_TEAM_INFO_VALID_SEASON_TYPES)[:5]))), dataframes
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_TEAM_INFO_VALID_SEASON_TYPES)[:5])))

    if league_id not in _TEAM_INFO_VALID_LEAGUE_IDS:
        if return_dataframe:
            return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_TEAM_INFO_VALID_LEAGUE_IDS)[:3]))), dataframes
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_TEAM_INFO_VALID_LEAGUE_IDS)[:3])))

    try:
        team_id, team_actual_name = find_team_id_or_error(team_identifier)
        all_errors: List[str] = []

        # Fetch team details and ranks with DataFrame if requested
        if return_dataframe:
            team_info_dict, team_ranks_dict, info_errors, team_info_df, team_ranks_df = _fetch_team_details_and_ranks(
                team_id, season, season_type, league_id, team_name=team_actual_name, return_dataframe=True
            )
            dataframes["team_info"] = team_info_df
            dataframes["team_ranks"] = team_ranks_df
        else:
            team_info_dict, team_ranks_dict, info_errors = _fetch_team_details_and_ranks(
                team_id, season, season_type, league_id
            )
        all_errors.extend(info_errors)

        # Fetch roster and coaches with DataFrame if requested
        if return_dataframe:
            roster_list, coaches_list, roster_errors, roster_df, coaches_df = _fetch_team_roster_and_coaches(
                team_id, season, league_id, team_name=team_actual_name, return_dataframe=True
            )
            dataframes["roster"] = roster_df
            dataframes["coaches"] = coaches_df
        else:
            roster_list, coaches_list, roster_errors = _fetch_team_roster_and_coaches(
                team_id, season, league_id
            )
        all_errors.extend(roster_errors)

        if not team_info_dict and not team_ranks_dict and not roster_list and not coaches_list and all_errors:
            error_summary = Errors.TEAM_ALL_FAILED.format(identifier=team_identifier, season=season, errors_list=', '.join(all_errors))
            logger.error(error_summary)
            if return_dataframe:
                return format_response(error=error_summary), dataframes
            return format_response(error=error_summary)

        result = {
            "team_id": team_id, "team_name": team_actual_name, "season": season,
            "season_type": season_type, "league_id": league_id,
            "info": team_info_dict, "ranks": team_ranks_dict,
            "roster": roster_list, "coaches": coaches_list
        }
        if all_errors:
            result["partial_errors"] = all_errors

        # Add DataFrame metadata to the response if returning DataFrames
        if return_dataframe:
            result["dataframe_info"] = {
                "message": "Team information data has been converted to DataFrames and saved as CSV files",
                "dataframes": {}
            }

            # Add metadata for each DataFrame if not empty
            for df_key, df in dataframes.items():
                if not df.empty:
                    csv_path = _get_csv_path_for_team_info(team_actual_name, df_key, season, league_id)
                    csv_filename = os.path.basename(csv_path)
                    relative_path = get_relative_cache_path(csv_filename, "team_info")

                    result["dataframe_info"]["dataframes"][df_key] = {
                        "shape": list(df.shape),
                        "columns": df.columns.tolist(),
                        "csv_path": relative_path
                    }

        logger.info(f"fetch_team_info_and_roster_logic completed for Team ID: {team_id}, Season: {season}")

        if return_dataframe:
            return format_response(result), dataframes
        return format_response(result)

    except (TeamNotFoundError, ValueError) as e: # Handles find_team_id_or_error issues
        logger.warning(f"Team lookup or validation failed for '{team_identifier}': {e}")
        if return_dataframe:
            return format_response(error=str(e)), dataframes
        return format_response(error=str(e))
    except Exception as e: # Catch-all for unexpected issues in the main orchestration
        error_msg = Errors.TEAM_UNEXPECTED.format(identifier=team_identifier, season=season, error=str(e))
        logger.critical(error_msg, exc_info=True)
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)
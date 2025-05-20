"""
Provides logic to fetch and determine top-performing (trending) teams
based on league standings data.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import json
import os
import pandas as pd
from datetime import datetime
from typing import Any, Tuple, List, Dict, Optional, Set, Union
from functools import lru_cache

from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID
from .league_standings import fetch_league_standings_logic
from ..config import settings
from ..core.errors import Errors
from .utils import format_response
from ..utils.validation import _validate_season_format
from ..utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
CACHE_TTL_SECONDS_TRENDING_TEAMS = 3600 * 4  # Cache standings for trending teams for 4 hours
TRENDING_TEAMS_RAW_STANDINGS_CACHE_SIZE = 16
TOP_TEAMS_PROCESSED_CACHE_SIZE = 64
DEFAULT_TOP_N_TEAMS = 5

# --- Cache Directory Setup ---
TRENDING_TEAMS_CSV_DIR = get_cache_dir("trending_teams")

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

def _get_csv_path_for_trending_teams(
    season: str,
    season_type: str,
    league_id: str,
    top_n: int
) -> str:
    """
    Generates a file path for saving trending teams DataFrame as CSV.

    Args:
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        league_id: The league ID (e.g., '00' for NBA)
        top_n: The number of top teams to include

    Returns:
        Path to the CSV file
    """
    # Clean season type for filename
    clean_season_type = season_type.replace(" ", "_").lower()

    filename = f"top_{top_n}_teams_{season}_{clean_season_type}_{league_id}.csv"
    return get_cache_file_path(filename, "trending_teams")

_TRENDING_TEAMS_VALID_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_TRENDING_TEAMS_VALID_LEAGUE_IDS: Set[str] = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

_ESSENTIAL_TEAM_FIELDS_FOR_TRENDING = [
    "TeamID", "TeamName", "Conference", "PlayoffRank", "WinPct",
    "WINS", "LOSSES", "Record", "LeagueRank"
]

# --- Helper Functions ---
@lru_cache(maxsize=TRENDING_TEAMS_RAW_STANDINGS_CACHE_SIZE)
def get_cached_standings_for_trending_teams(
    cache_key: Tuple, # e.g., (season, season_type, league_id)
    timestamp_bucket: str,
    **kwargs: Any # Parameters for fetch_league_standings_logic
) -> str:
    """Cached wrapper for `fetch_league_standings_logic`."""
    logger.info(f"Cache miss/expiry for standings (trending_teams, ts: {timestamp_bucket}) - fetching. Params: {kwargs}")
    try:
        standings_logic_args = {k: v for k, v in kwargs.items() if v is not None}
        return fetch_league_standings_logic(**standings_logic_args)
    except Exception as e:
        logger.error(f"fetch_league_standings_logic failed within cache wrapper: {e}", exc_info=True)
        raise

def _validate_trending_teams_params(
    season: str, season_type: str, league_id: str, top_n: int
) -> Optional[str]:
    """Validates parameters for fetch_top_teams_logic."""
    if not _validate_season_format(season):
        return Errors.INVALID_SEASON_FORMAT.format(season=season)
    if not isinstance(top_n, int) or top_n < 1:
        return Errors.INVALID_TOP_N.format(value=top_n)
    if season_type not in _TRENDING_TEAMS_VALID_SEASON_TYPES:
        return Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_TRENDING_TEAMS_VALID_SEASON_TYPES)[:5]))
    if league_id not in _TRENDING_TEAMS_VALID_LEAGUE_IDS:
        return Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_TRENDING_TEAMS_VALID_LEAGUE_IDS)[:3]))
    return None

def _extract_and_format_top_teams(
    standings_list: List[Dict[str, Any]], top_n: int
) -> List[Dict[str, Any]]:
    """Sorts standings by WinPct and extracts essential fields for the top N teams."""
    if not standings_list:
        return []
    try:
        # Handle potential None or non-floatable WinPct values during sort
        standings_sorted_list = sorted(
            standings_list,
            key=lambda x: float(x.get("WinPct", 0.0) or 0.0), # Default to 0.0 if None or empty
            reverse=True
        )
    except (ValueError, TypeError) as sort_err:
        logger.warning(f"Error sorting standings by WinPct: {sort_err}. Proceeding with unsorted top N from original list.")
        standings_sorted_list = standings_list # Fallback

    top_teams_formatted = []
    for team_data in standings_sorted_list[:top_n]:
        top_team_info = {field: team_data.get(field) for field in _ESSENTIAL_TEAM_FIELDS_FOR_TRENDING if field in team_data}
        top_teams_formatted.append(top_team_info)
    return top_teams_formatted

# --- Main Logic Function ---
@lru_cache(maxsize=TOP_TEAMS_PROCESSED_CACHE_SIZE)
def fetch_top_teams_logic(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    league_id: str = LeagueID.nba,
    top_n: int = DEFAULT_TOP_N_TEAMS,
    bypass_cache: bool = False,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches the top N performing teams based on win percentage.
    Utilizes cached league standings data.
    Provides DataFrame output capabilities.

    Args:
        season: NBA season in YYYY-YY format. Defaults to current season.
        season_type: Type of season. Defaults to Regular Season.
        league_id: League ID. Defaults to NBA.
        top_n: Number of top teams to return. Defaults to 5.
        bypass_cache: Whether to bypass the cache and fetch fresh data. Defaults to False.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string with top teams or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_top_teams_logic for season: {season}, type: {season_type}, league: {league_id}, top_n: {top_n}, return_dataframe: {return_dataframe}")

    # Store DataFrames if requested
    dataframes = {}

    param_error = _validate_trending_teams_params(season, season_type, league_id, top_n)
    if param_error:
        if return_dataframe:
            return format_response(error=param_error), dataframes
        return format_response(error=param_error)

    cache_key_for_standings = (season, season_type, league_id)
    timestamp_bucket = str(int(datetime.now().timestamp() // CACHE_TTL_SECONDS_TRENDING_TEAMS))
    standings_params = {"season": season, "season_type": season_type, "league_id": league_id}

    try:
        standings_json_str: str
        if bypass_cache:
            logger.info(f"Bypassing cache, fetching fresh standings for trending teams: {standings_params}")
            standings_json_str = fetch_league_standings_logic(**standings_params)
        else:
            standings_json_str = get_cached_standings_for_trending_teams(
                cache_key=cache_key_for_standings,
                timestamp_bucket=timestamp_bucket, # Corrected arg name
                **standings_params
            )

        try:
            standings_data_response = json.loads(standings_json_str)
        except json.JSONDecodeError as json_err:
            logger.error(f"Failed to decode JSON from standings logic: {json_err}. Response (first 500): {standings_json_str[:500]}")
            error_response = format_response(error=Errors.PROCESSING_ERROR.format(error="invalid JSON from standings"))
            if return_dataframe:
                return error_response, dataframes
            return error_response

        if isinstance(standings_data_response, dict) and "error" in standings_data_response:
            logger.error(f"Error received from upstream standings fetch: {standings_data_response['error']}")
            if return_dataframe:
                return standings_json_str, dataframes # Propagate the error JSON
            return standings_json_str # Propagate the error JSON

        standings_list = standings_data_response.get("standings", [])
        if not standings_list:
            logger.warning(f"No standings data available for {season}, type {season_type}, league {league_id}.")

            response_data = {
                "season": season, "season_type": season_type, "league_id": league_id,
                "requested_top_n": top_n, "top_teams": []
            }

            # Add DataFrame metadata to the response if returning DataFrames
            if return_dataframe:
                response_data["dataframe_info"] = {
                    "message": "No standings data available for the specified parameters",
                    "dataframes": {}
                }

                # Create an empty DataFrame for top teams
                dataframes["top_teams"] = pd.DataFrame(columns=_ESSENTIAL_TEAM_FIELDS_FOR_TRENDING)

                return format_response(response_data), dataframes
            return format_response(response_data)

        top_teams_list = _extract_and_format_top_teams(standings_list, top_n)

        result_payload = {
            "season": season, "season_type": season_type, "league_id": league_id,
            "requested_top_n": top_n, "top_teams": top_teams_list
        }

        if return_dataframe:
            # Create a DataFrame from the top teams list
            top_teams_df = pd.DataFrame(top_teams_list)
            dataframes["top_teams"] = top_teams_df

            # Save DataFrame to CSV if not empty
            if not top_teams_df.empty:
                csv_path = _get_csv_path_for_trending_teams(season, season_type, league_id, top_n)
                _save_dataframe_to_csv(top_teams_df, csv_path)

                # Add DataFrame metadata to the response
                result_payload["dataframe_info"] = {
                    "message": "Top teams data has been converted to DataFrame and saved as CSV file",
                    "dataframes": {
                        "top_teams": {
                            "shape": list(top_teams_df.shape),
                            "columns": top_teams_df.columns.tolist(),
                            "csv_path": get_relative_cache_path(os.path.basename(csv_path), "trending_teams")
                        }
                    }
                }

        logger.info(f"Successfully determined top {len(top_teams_list)} teams for {season}, type {season_type}, league {league_id}.")

        if return_dataframe:
            return format_response(result_payload), dataframes
        return format_response(result_payload)

    except Exception as e:
        logger.error(f"Unexpected error in fetch_top_teams_logic: {e}", exc_info=True)
        error_response = format_response(error=Errors.TRENDING_TEAMS_UNEXPECTED.format(error=str(e)))
        if return_dataframe:
            return error_response, dataframes
        return error_response

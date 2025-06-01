"""
Handles fetching and processing player matchup statistics, including
player-vs-player season matchups and defensive player rollup stats.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
from datetime import datetime
import pandas as pd
from typing import Dict, Tuple, Any, Type, Optional, Set, List, Union
from functools import lru_cache

from nba_api.stats.endpoints import LeagueSeasonMatchups, MatchupsRollup
from nba_api.stats.library.parameters import SeasonTypeAllStar
from config import settings
from core.errors import Errors
from api_tools.utils import format_response, _process_dataframe, find_player_id_or_error, PlayerNotFoundError
from utils.validation import _validate_season_format
from utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Cache Directory Setup ---
MATCHUPS_CSV_DIR = get_cache_dir("matchups")

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

def _get_csv_path_for_season_matchups(
    def_player_id: int,
    off_player_id: int,
    season: str,
    season_type: str
) -> str:
    """
    Generates a file path for saving season matchups DataFrame as CSV.

    Args:
        def_player_id: Defensive player ID
        off_player_id: Offensive player ID
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')

    Returns:
        Path to the CSV file
    """
    # Clean season type for filename
    clean_season_type = season_type.replace(" ", "_").lower()

    filename = f"season_matchups_{def_player_id}_{off_player_id}_{season}_{clean_season_type}.csv"
    return get_cache_file_path(filename, "matchups")

def _get_csv_path_for_matchups_rollup(
    def_player_id: int,
    season: str,
    season_type: str
) -> str:
    """
    Generates a file path for saving matchups rollup DataFrame as CSV.

    Args:
        def_player_id: Defensive player ID
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')

    Returns:
        Path to the CSV file
    """
    # Clean season type for filename
    clean_season_type = season_type.replace(" ", "_").lower()

    filename = f"matchups_rollup_{def_player_id}_{season}_{clean_season_type}.csv"
    return get_cache_file_path(filename, "matchups")

# --- Module-Level Constants ---
CACHE_TTL_SECONDS_MATCHUPS = 3600 * 6  # Cache matchup data for 6 hours
MATCHUP_DATA_CACHE_SIZE = 128

_MATCHUP_VALID_SEASON_TYPES: Set[str] = {SeasonTypeAllStar.regular, SeasonTypeAllStar.preseason, SeasonTypeAllStar.playoffs}

# --- Helper for Fetching and Caching Raw Endpoint Data ---
@lru_cache(maxsize=MATCHUP_DATA_CACHE_SIZE)
def _get_cached_endpoint_dict(
    cache_key_tuple: Tuple,
    timestamp_bucket: str,
    endpoint_class: Type[Any],
    api_params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Cached wrapper for NBA API endpoints returning a dictionary.
    Used by matchup tools to cache raw API responses.

    Args:
        cache_key_tuple: A unique tuple for caching, including endpoint name and key API parameters.
        timestamp_bucket: A string derived from the current time, bucketed for cache invalidation.
        endpoint_class: The specific NBA API endpoint class to instantiate.
        api_params: Keyword arguments to be passed directly to the endpoint_class constructor.

    Returns:
        The raw dictionary response from the NBA API endpoint's get_dict() method.

    Raises:
        Exception: If the API call fails, to be handled by the caller.
    """
    # Log parameters without the timestamp_bucket for brevity if it's too verbose
    logger.info(f"Cache miss/expiry for {endpoint_class.__name__} (ts: {timestamp_bucket}) - fetching. Params: {api_params}")
    try:
        endpoint_instance = endpoint_class(**api_params, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
        return endpoint_instance.get_dict()
    except Exception as e:
        logger.error(f"{endpoint_class.__name__} API call failed with params {api_params}: {e}", exc_info=True)
        raise

def _extract_dataframe_from_response(
    response_dict: Dict[str, Any],
    expected_dataset_name: str,
    endpoint_instance_if_live: Optional[Any] = None
) -> pd.DataFrame:
    """
    Robustly extracts a DataFrame from an endpoint's response dictionary or live instance.
    Tries direct attribute access from the live instance first, then falls back to parsing 'resultSets' from the dictionary.

    Args:
        response_dict: The raw dictionary from the API (either live or cached).
        expected_dataset_name: The 'name' of the dataset in 'resultSets' (e.g., "SeasonMatchups").
        endpoint_instance_if_live: The live NBA API endpoint instance, if the call was not from cache.

    Returns:
        A pandas DataFrame, potentially empty if data is not found or extraction fails.
    """
    df = pd.DataFrame()
    # Convert common dataset name format (e.g., "Season Matchups") to attribute format (e.g., "season_matchups")
    dataset_attr_name = expected_dataset_name.lower().replace(" ", "_")

    if endpoint_instance_if_live and hasattr(endpoint_instance_if_live, dataset_attr_name):
        dataset_obj = getattr(endpoint_instance_if_live, dataset_attr_name)
        if hasattr(dataset_obj, 'get_data_frame'):
            try:
                df = dataset_obj.get_data_frame()
                logger.debug(f"Successfully accessed '{expected_dataset_name}' dataset directly via attribute '{dataset_attr_name}'.")
                return df
            except Exception as e:
                logger.warning(f"Error accessing dataset '{expected_dataset_name}' directly via attribute '{dataset_attr_name}': {e}. Trying 'resultSets' fallback.")
        else:
            logger.warning(f"Dataset attribute '{dataset_attr_name}' for '{expected_dataset_name}' does not have 'get_data_frame' method.")

    logger.debug(f"Attempting fallback to 'resultSets' for dataset: {expected_dataset_name}")
    if 'resultSets' in response_dict and isinstance(response_dict['resultSets'], list):
        for rs_item in response_dict['resultSets']:
            if rs_item.get('name') == expected_dataset_name:
                if rs_item.get('rowSet') is not None and rs_item.get('headers') is not None:
                    df = pd.DataFrame(rs_item['rowSet'], columns=rs_item['headers'])
                    logger.debug(f"Successfully extracted DataFrame for '{expected_dataset_name}' via 'resultSets' by name.")
                    return df
                else:
                    logger.warning(f"Dataset '{expected_dataset_name}' found by name in 'resultSets' but 'rowSet' or 'headers' are missing.")
                    return pd.DataFrame() # Return empty if malformed

        # Fallback if specific name not found but only one result set exists (common pattern)
        if df.empty and len(response_dict['resultSets']) == 1:
            rs_item = response_dict['resultSets'][0]
            if rs_item.get('rowSet') is not None and rs_item.get('headers') is not None:
                logger.warning(f"Dataset '{expected_dataset_name}' not found by name, using the single available result set (name: {rs_item.get('name')}) as fallback.")
                df = pd.DataFrame(rs_item['rowSet'], columns=rs_item['headers'])
                return df
            else:
                 logger.warning(f"Single available result set for '{expected_dataset_name}' is malformed (missing rowSet/headers).")
        elif df.empty and len(response_dict['resultSets']) > 1: # Only log if still empty and multiple sets existed
            logger.warning(f"Dataset '{expected_dataset_name}' not found by name, and multiple result sets exist. Cannot reliably determine fallback beyond the first if it was also unnamed.")

    if df.empty: # Log if still empty after all attempts
        logger.warning(f"Could not extract DataFrame for '{expected_dataset_name}' via direct access or 'resultSets' fallback.")
    return df

# --- Main Logic Functions ---
@lru_cache(maxsize=MATCHUP_DATA_CACHE_SIZE) # Caches the final processed string response
def fetch_league_season_matchups_logic(
    def_player_identifier: str,
    off_player_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    bypass_cache: bool = False,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches season matchup statistics between two specific players.
    Provides DataFrame output capabilities.

    Args:
        def_player_identifier: Name or ID of the defensive player.
        off_player_identifier: Name or ID of the offensive player.
        season: NBA season in YYYY-YY format. Defaults to current.
        season_type: Type of season. Defaults to "Regular Season".
        bypass_cache: If True, ignores cached raw data. Defaults to False.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string with matchup data or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Fetching season matchups: Def '{def_player_identifier}' vs Off '{off_player_identifier}' for {season}, Type: {season_type}, return_dataframe: {return_dataframe}")

    # Store DataFrames if requested
    dataframes = {}

    if not def_player_identifier or not off_player_identifier:
        error_response = format_response(error=Errors.MISSING_PLAYER_IDENTIFIER)
        if return_dataframe:
            return error_response, dataframes
        return error_response
    if not season or not _validate_season_format(season):
        error_response = format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
        if return_dataframe:
            return error_response, dataframes
        return error_response
    if season_type not in _MATCHUP_VALID_SEASON_TYPES:
        error_response = format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_MATCHUP_VALID_SEASON_TYPES)[:5])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    try:
        def_player_id_resolved, def_player_name_resolved = find_player_id_or_error(def_player_identifier)
        off_player_id_resolved, off_player_name_resolved = find_player_id_or_error(off_player_identifier)
    except (PlayerNotFoundError, ValueError) as e:
        logger.warning(f"Player ID lookup failed for matchups: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    api_params = {
        "def_player_id_nullable": str(def_player_id_resolved),
        "off_player_id_nullable": str(off_player_id_resolved),
        "season": season,
        "season_type_playoffs": season_type
    }
    raw_data_cache_key = ("LeagueSeasonMatchups", str(def_player_id_resolved), str(off_player_id_resolved), season, season_type)
    timestamp_bucket = str(int(datetime.now().timestamp() // CACHE_TTL_SECONDS_MATCHUPS))

    try:
        response_dict: Dict[str, Any]
        live_endpoint_instance = None

        if bypass_cache or season == settings.CURRENT_NBA_SEASON:
            logger.info(f"Fetching fresh LeagueSeasonMatchups data (Bypass: {bypass_cache}, Season: {season})")
            live_endpoint_instance = LeagueSeasonMatchups(**api_params, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
            response_dict = live_endpoint_instance.get_dict()
            if not bypass_cache and response_dict: # Update cache if fresh call for current season was successful
                 # Consider clearing specific entry or letting LRU handle it.
                 # For simplicity, we can rely on the timestamp_bucket for invalidation.
                 # If we want to force update the cache with this new data:
                 _get_cached_endpoint_dict(raw_data_cache_key, timestamp_bucket, LeagueSeasonMatchups, api_params)
        else:
            response_dict = _get_cached_endpoint_dict(raw_data_cache_key, timestamp_bucket, LeagueSeasonMatchups, api_params)

        matchups_df = _extract_dataframe_from_response(response_dict, "SeasonMatchups", live_endpoint_instance)

        if matchups_df.empty:
            logger.warning(f"No matchup data found for Def {def_player_name_resolved} vs Off {off_player_name_resolved} in {season}.")
            empty_response = {
                "def_player_id": def_player_id_resolved, "def_player_name": def_player_name_resolved,
                "off_player_id": off_player_id_resolved, "off_player_name": off_player_name_resolved,
                "parameters": {"season": season, "season_type": season_type}, "matchups": []
            }

            if return_dataframe:
                # Even if no matchups data, still return the empty DataFrame
                dataframes["matchups"] = matchups_df
                return format_response(empty_response), dataframes
            return format_response(empty_response)

        matchups_list = _process_dataframe(matchups_df, single_row=False)
        if matchups_list is None:
            logger.error(f"DataFrame processing failed for season matchups Def {def_player_name_resolved} vs Off {off_player_name_resolved} ({season}).")
            error_response = format_response(error=Errors.MATCHUPS_PROCESSING)
            if return_dataframe:
                return error_response, dataframes
            return error_response

        result_payload = {
            "def_player_id": def_player_id_resolved, "def_player_name": def_player_name_resolved,
            "off_player_id": off_player_id_resolved, "off_player_name": off_player_name_resolved,
            "parameters": {"season": season, "season_type": season_type},
            "matchups": matchups_list or []
        }

        # Store DataFrame if requested
        if return_dataframe:
            dataframes["matchups"] = matchups_df

            # Save to CSV if not empty
            if not matchups_df.empty:
                csv_path = _get_csv_path_for_season_matchups(
                    def_player_id=def_player_id_resolved,
                    off_player_id=off_player_id_resolved,
                    season=season,
                    season_type=season_type
                )
                _save_dataframe_to_csv(matchups_df, csv_path)

                # Add relative path to response
                relative_path = get_relative_cache_path(
                    os.path.basename(csv_path),
                    "matchups"
                )

                result_payload["dataframe_info"] = {
                    "message": "Season matchups data has been converted to DataFrame and saved as CSV file",
                    "dataframes": {
                        "matchups": {
                            "shape": list(matchups_df.shape),
                            "columns": matchups_df.columns.tolist(),
                            "csv_path": relative_path
                        }
                    }
                }

        logger.info(f"Successfully fetched season matchups for Def {def_player_name_resolved} vs Off {off_player_name_resolved}")

        if return_dataframe:
            return format_response(result_payload), dataframes
        return format_response(result_payload)

    except Exception as e:
        logger.error(f"Error fetching season matchups: {e}", exc_info=True)
        error_response = format_response(error=Errors.MATCHUPS_API.format(error=str(e)))
        if return_dataframe:
            return error_response, dataframes
        return error_response

@lru_cache(maxsize=MATCHUP_DATA_CACHE_SIZE)
def fetch_matchups_rollup_logic(
    def_player_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    bypass_cache: bool = False,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches matchup rollup statistics for a defensive player.
    Provides DataFrame output capabilities.

    Args:
        def_player_identifier: Name or ID of the defensive player.
        season: NBA season in YYYY-YY format. Defaults to current.
        season_type: Type of season. Defaults to "Regular Season".
        bypass_cache: If True, ignores cached raw data. Defaults to False.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string with matchup rollup data or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Fetching matchup rollup for Def Player: '{def_player_identifier}' in {season}, Type: {season_type}, return_dataframe: {return_dataframe}")

    # Store DataFrames if requested
    dataframes = {}

    if not def_player_identifier:
        error_response = format_response(error=Errors.MISSING_PLAYER_IDENTIFIER)
        if return_dataframe:
            return error_response, dataframes
        return error_response
    if not season or not _validate_season_format(season):
        error_response = format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
        if return_dataframe:
            return error_response, dataframes
        return error_response
    if season_type not in _MATCHUP_VALID_SEASON_TYPES:
        error_response = format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_MATCHUP_VALID_SEASON_TYPES)[:5])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    try:
        def_player_id_resolved, def_player_name_resolved = find_player_id_or_error(def_player_identifier)
    except (PlayerNotFoundError, ValueError) as e:
        logger.warning(f"Player ID lookup failed for matchup rollup: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    api_params = {
        "def_player_id_nullable": str(def_player_id_resolved),
        "season": season,
        "season_type_playoffs": season_type
    }
    raw_data_cache_key = ("MatchupsRollup", str(def_player_id_resolved), season, season_type)
    timestamp_bucket = str(int(datetime.now().timestamp() // CACHE_TTL_SECONDS_MATCHUPS))

    try:
        response_dict: Dict[str, Any]
        live_endpoint_instance = None

        if bypass_cache or season == settings.CURRENT_NBA_SEASON:
            logger.info(f"Fetching fresh MatchupsRollup data (Bypass: {bypass_cache}, Season: {season})")
            live_endpoint_instance = MatchupsRollup(**api_params, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
            response_dict = live_endpoint_instance.get_dict()
            if not bypass_cache and response_dict:
                 _get_cached_endpoint_dict.cache_clear()
                 _get_cached_endpoint_dict(raw_data_cache_key, timestamp_bucket, MatchupsRollup, api_params)
        else:
            response_dict = _get_cached_endpoint_dict(raw_data_cache_key, timestamp_bucket, MatchupsRollup, api_params)

        rollup_df = _extract_dataframe_from_response(response_dict, "MatchupsRollup", live_endpoint_instance)

        if rollup_df.empty:
            logger.warning(f"No matchup rollup data found for Def Player {def_player_name_resolved} in {season}.")
            empty_response = {
                "def_player_id": def_player_id_resolved, "def_player_name": def_player_name_resolved,
                "parameters": {"season": season, "season_type": season_type}, "rollup": []
            }

            if return_dataframe:
                # Even if no rollup data, still return the empty DataFrame
                dataframes["rollup"] = rollup_df
                return format_response(empty_response), dataframes
            return format_response(empty_response)

        rollup_list = _process_dataframe(rollup_df, single_row=False)
        if rollup_list is None:
            logger.error(f"DataFrame processing failed for matchup rollup Def {def_player_name_resolved} ({season}).")
            error_response = format_response(error=Errors.MATCHUPS_ROLLUP_PROCESSING)
            if return_dataframe:
                return error_response, dataframes
            return error_response

        result_payload = {
            "def_player_id": def_player_id_resolved, "def_player_name": def_player_name_resolved,
            "parameters": {"season": season, "season_type": season_type},
            "rollup": rollup_list or []
        }

        # Store DataFrame if requested
        if return_dataframe:
            dataframes["rollup"] = rollup_df

            # Save to CSV if not empty
            if not rollup_df.empty:
                csv_path = _get_csv_path_for_matchups_rollup(
                    def_player_id=def_player_id_resolved,
                    season=season,
                    season_type=season_type
                )
                _save_dataframe_to_csv(rollup_df, csv_path)

                # Add relative path to response
                relative_path = get_relative_cache_path(
                    os.path.basename(csv_path),
                    "matchups"
                )

                result_payload["dataframe_info"] = {
                    "message": "Matchups rollup data has been converted to DataFrame and saved as CSV file",
                    "dataframes": {
                        "rollup": {
                            "shape": list(rollup_df.shape),
                            "columns": rollup_df.columns.tolist(),
                            "csv_path": relative_path
                        }
                    }
                }

        logger.info(f"Successfully fetched matchup rollup for Def Player {def_player_name_resolved}")

        if return_dataframe:
            return format_response(result_payload), dataframes
        return format_response(result_payload)

    except Exception as e:
        logger.error(f"Error fetching matchups rollup for Def Player {def_player_identifier}: {e}", exc_info=True)
        error_response = format_response(error=Errors.MATCHUPS_ROLLUP_API.format(error=str(e)))
        if return_dataframe:
            return error_response, dataframes
        return error_response

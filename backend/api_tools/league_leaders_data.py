"""
Handles fetching league leaders data for various statistical categories.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import os
import logging
from functools import lru_cache
import requests # For direct HTTP debug request
import json
import pandas as pd
from typing import Optional, Dict, Any, List, Set, Union, Tuple

from nba_api.stats.endpoints import leagueleaders
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar, PerMode48, Scope, StatCategoryAbbreviation
from .utils import _process_dataframe, format_response
from ..utils.validation import _validate_season_format
from ..config import settings
from ..core.errors import Errors

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
LEAGUE_LEADERS_CACHE_SIZE = 128
DEFAULT_TOP_N_LEADERS = 10
LEAGUE_LEADERS_STATS_URL = "https://stats.nba.com/stats/leagueleaders"
DEFAULT_LEAGUE_LEADERS_HTTP_HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://stats.nba.com/', 'Accept': 'application/json'}
DEBUG_HTTP_REQUEST_TIMEOUT = 5

_VALID_STAT_CATEGORIES_LEADERS: Set[str] = {getattr(StatCategoryAbbreviation, attr) for attr in dir(StatCategoryAbbreviation) if not attr.startswith('_')}
_VALID_SEASON_TYPES_LEADERS: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_VALID_PER_MODES_LEADERS: Set[str] = {getattr(PerMode48, attr) for attr in dir(PerMode48) if not attr.startswith('_') and isinstance(getattr(PerMode48, attr), str)}
_VALID_LEAGUE_IDS_LEADERS: Set[str] = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}
_VALID_SCOPES_LEADERS: Set[str] = {getattr(Scope, attr) for attr in dir(Scope) if not attr.startswith('_') and isinstance(getattr(Scope, attr), str)}

_EXPECTED_LEADER_COLS = ['PLAYER_ID', 'RANK', 'PLAYER', 'TEAM_ID', 'TEAM', 'GP', 'MIN']

# --- Cache Directory Setup ---
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
LEAGUE_LEADERS_CSV_DIR = os.path.join(CSV_CACHE_DIR, "league_leaders")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(LEAGUE_LEADERS_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_league_leaders(
    season: str,
    stat_category: str,
    season_type: str,
    per_mode: str,
    league_id: str,
    scope: str
) -> str:
    """
    Generates a file path for saving league leaders DataFrame as CSV.

    Args:
        season: The season in YYYY-YY format
        stat_category: The statistical category (e.g., 'PTS', 'REB')
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        per_mode: The per mode (e.g., 'PerGame', 'Totals')
        league_id: The league ID (e.g., '00' for NBA)
        scope: The scope (e.g., 'S' for season, 'RS' for rookies)

    Returns:
        Path to the CSV file
    """
    # Clean season type for filename
    clean_season_type = season_type.replace(" ", "_").lower()

    # Clean per mode for filename
    clean_per_mode = per_mode.replace(" ", "_").lower()

    filename = f"leaders_{season}_{stat_category}_{clean_season_type}_{clean_per_mode}_{league_id}_{scope}.csv"
    return os.path.join(LEAGUE_LEADERS_CSV_DIR, filename)

# --- Helper for Parameter Validation ---
def _validate_league_leaders_params(
    season: str, stat_category: str, season_type: str, per_mode: str,
    league_id: str, scope: str, top_n: int
) -> Optional[str]:
    """Validates parameters for fetch_league_leaders_logic."""
    if not _validate_season_format(season):
        return Errors.INVALID_SEASON_FORMAT.format(season=season)
    if not isinstance(top_n, int) or top_n <= 0: # top_n already defaulted if invalid by main func
        # This specific log/defaulting is handled in main func, here just check type for safety
        pass # Assuming top_n is already validated/defaulted by caller
    if stat_category not in _VALID_STAT_CATEGORIES_LEADERS:
        return Errors.INVALID_STAT_CATEGORY.format(value=stat_category, options=", ".join(list(_VALID_STAT_CATEGORIES_LEADERS)[:5]))
    if season_type not in _VALID_SEASON_TYPES_LEADERS:
        return Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_SEASON_TYPES_LEADERS)[:5]))
    if per_mode not in _VALID_PER_MODES_LEADERS:
        return Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_PER_MODES_LEADERS)[:5]))
    if league_id not in _VALID_LEAGUE_IDS_LEADERS:
        return Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_VALID_LEAGUE_IDS_LEADERS)[:5]))
    if scope not in _VALID_SCOPES_LEADERS:
        return Errors.INVALID_SCOPE.format(value=scope, options=", ".join(list(_VALID_SCOPES_LEADERS)[:5]))
    return None

# --- Main Logic Function ---
def fetch_league_leaders_logic(
    season: str,
    stat_category: str = StatCategoryAbbreviation.pts,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerMode48.per_game,
    league_id: str = LeagueID.nba,
    scope: str = Scope.s,
    top_n: int = DEFAULT_TOP_N_LEADERS,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league leaders for a specific statistical category and criteria.
    Provides DataFrame output capabilities.

    Args:
        season: NBA season in 'YYYY-YY' format.
        stat_category: Statistical category abbreviation (e.g., 'PTS').
        season_type: Season type (e.g., 'Regular Season').
        per_mode: Per mode (e.g., 'PerGame').
        league_id: League ID. Defaults to NBA.
        scope: Scope of leaders (e.g., 'S' for season).
        top_n: Number of top leaders to return. Defaults to 10.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string of league leaders list or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_league_leaders_logic for season: {season}, category: {stat_category}, type: {season_type}, per_mode: {per_mode}, scope: {scope}, top_n: {top_n}, return_dataframe={return_dataframe}")

    # Store DataFrames if requested
    dataframes = {}

    # Validate top_n separately as it has a default and specific logging
    if not isinstance(top_n, int) or top_n <= 0:
        logger.warning(f"Invalid top_n value '{top_n}'. Must be a positive integer. Defaulting to {DEFAULT_TOP_N_LEADERS}.")
        top_n = DEFAULT_TOP_N_LEADERS

    param_error = _validate_league_leaders_params(season, stat_category, season_type, per_mode, league_id, scope, top_n)
    if param_error:
        if return_dataframe:
            return format_response(error=param_error), dataframes
        return format_response(error=param_error)

    http_params = {
        "LeagueID": league_id, "PerMode": per_mode, "Scope": scope,
        "Season": season, "SeasonType": season_type, "StatCategory": stat_category,
    }
    raw_response_status_for_log = None

    try:
        logger.debug(f"Calling leagueleaders.LeagueLeaders with params: {http_params}")
        leaders_endpoint = leagueleaders.LeagueLeaders(
            league_id=league_id, per_mode48=per_mode, scope=scope, season=season,
            season_type_all_star=season_type, stat_category_abbreviation=stat_category,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        leaders_df = leaders_endpoint.league_leaders.get_data_frame()
        logger.debug(f"nba_api leagueleaders call successful for {stat_category} ({season})")

    except KeyError as ke:
        if 'resultSet' in str(ke): # Specific handling for NBA API malformed JSON
            logger.error(f"KeyError 'resultSet' using nba_api for {stat_category} ({season}). NBA API response likely malformed.", exc_info=True)
            try:
                response = requests.get(LEAGUE_LEADERS_STATS_URL, headers=DEFAULT_LEAGUE_LEADERS_HTTP_HEADERS, params=http_params, timeout=DEBUG_HTTP_REQUEST_TIMEOUT)
                raw_response_status_for_log = response.status_code
                logger.debug(f"Direct HTTP debug request status: {raw_response_status_for_log}, Response (first 500): {response.text[:500]}")
            except Exception as direct_req_err:
                logger.error(f"Direct HTTP debug request failed: {direct_req_err}")
            error_msg = Errors.LEAGUE_LEADERS_API_KEY_ERROR.format(stat=stat_category, season=season) + f" (Direct status: {raw_response_status_for_log or 'N/A'})"

            if return_dataframe:
                return format_response(error=error_msg), dataframes
            return format_response(error=error_msg)
        else: # Re-raise other KeyErrors
            logger.error(f"Unexpected KeyError in leagueleaders for {stat_category} ({season}): {ke}", exc_info=True)
            raise # Re-raise to be caught by general Exception handler
    except Exception as api_error:
        logger.error(f"nba_api leagueleaders failed for {stat_category} ({season}): {api_error}", exc_info=True)
        error_msg = Errors.LEAGUE_LEADERS_API.format(stat_category=stat_category, season=season, error=str(api_error))

        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    if leaders_df.empty:
        logger.warning(f"No league leaders data found via nba_api for {stat_category} ({season}).")

        if return_dataframe:
            return format_response({"leaders": []}), dataframes
        return format_response({"leaders": []})

    if stat_category not in leaders_df.columns:
        logger.error(f"Stat category '{stat_category}' not found in league leaders DataFrame columns: {list(leaders_df.columns)}")
        error_msg = Errors.LEAGUE_LEADERS_PROCESSING.format(stat_category=stat_category, season=season) + f" - Stat column '{stat_category}' missing."

        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    # Save DataFrame to CSV if requested
    if return_dataframe:
        dataframes["leaders"] = leaders_df

        # Save to CSV if not empty
        if not leaders_df.empty:
            csv_path = _get_csv_path_for_league_leaders(
                season, stat_category, season_type, per_mode, league_id, scope
            )
            _save_dataframe_to_csv(leaders_df, csv_path)

    # Ensure all expected columns and the stat_category column are present for processing
    cols_for_processing = list(dict.fromkeys([col for col in _EXPECTED_LEADER_COLS if col in leaders_df.columns] + [stat_category]))

    leaders_list = _process_dataframe(leaders_df.loc[:, cols_for_processing], single_row=False)
    if leaders_list is None:
        logger.error(f"DataFrame processing failed for league leaders {stat_category} ({season}).")
        error_msg = Errors.LEAGUE_LEADERS_PROCESSING.format(stat_category=stat_category, season=season)

        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    if top_n > 0: # top_n is already validated to be positive integer
        leaders_list = leaders_list[:top_n]

    logger.info(f"fetch_league_leaders_logic completed for {stat_category} ({season}), found {len(leaders_list)} leaders.")

    if return_dataframe:
        return format_response({"leaders": leaders_list}), dataframes
    return format_response({"leaders": leaders_list})
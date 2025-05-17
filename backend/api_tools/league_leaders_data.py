"""
Handles fetching league leaders data for various statistical categories.
"""
import logging
from functools import lru_cache
import requests # For direct HTTP debug request
from typing import Optional, Dict, Any, List, Set

from nba_api.stats.endpoints import leagueleaders
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar, PerMode48, Scope, StatCategoryAbbreviation
from backend.api_tools.utils import _process_dataframe, format_response
from backend.utils.validation import _validate_season_format
from backend.config import settings
from backend.core.errors import Errors

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
@lru_cache(maxsize=LEAGUE_LEADERS_CACHE_SIZE)
def fetch_league_leaders_logic(
    season: str,
    stat_category: str = StatCategoryAbbreviation.pts,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerMode48.per_game,
    league_id: str = LeagueID.nba,
    scope: str = Scope.s,
    top_n: int = DEFAULT_TOP_N_LEADERS
) -> str:
    """
    Fetches league leaders for a specific statistical category and criteria.

    Args:
        season: NBA season in 'YYYY-YY' format.
        stat_category: Statistical category abbreviation (e.g., 'PTS').
        season_type: Season type (e.g., 'Regular Season').
        per_mode: Per mode (e.g., 'PerGame').
        league_id: League ID. Defaults to NBA.
        scope: Scope of leaders (e.g., 'S' for season).
        top_n: Number of top leaders to return. Defaults to 10.

    Returns:
        JSON string of league leaders list or an error message.
    """
    logger.info(f"Executing fetch_league_leaders_logic for season: {season}, category: {stat_category}, type: {season_type}, per_mode: {per_mode}, scope: {scope}, top_n: {top_n}")

    # Validate top_n separately as it has a default and specific logging
    if not isinstance(top_n, int) or top_n <= 0:
        logger.warning(f"Invalid top_n value '{top_n}'. Must be a positive integer. Defaulting to {DEFAULT_TOP_N_LEADERS}.")
        top_n = DEFAULT_TOP_N_LEADERS

    param_error = _validate_league_leaders_params(season, stat_category, season_type, per_mode, league_id, scope, top_n)
    if param_error:
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
            return format_response(error=error_msg)
        else: # Re-raise other KeyErrors
            logger.error(f"Unexpected KeyError in leagueleaders for {stat_category} ({season}): {ke}", exc_info=True)
            raise # Re-raise to be caught by general Exception handler
    except Exception as api_error:
        logger.error(f"nba_api leagueleaders failed for {stat_category} ({season}): {api_error}", exc_info=True)
        error_msg = Errors.LEAGUE_LEADERS_API.format(stat_category=stat_category, season=season, error=str(api_error))
        return format_response(error=error_msg)

    if leaders_df.empty:
        logger.warning(f"No league leaders data found via nba_api for {stat_category} ({season}).")
        return format_response({"leaders": []})

    if stat_category not in leaders_df.columns:
        logger.error(f"Stat category '{stat_category}' not found in league leaders DataFrame columns: {list(leaders_df.columns)}")
        return format_response(error=Errors.LEAGUE_LEADERS_PROCESSING.format(stat_category=stat_category, season=season) + f" - Stat column '{stat_category}' missing.")

    # Ensure all expected columns and the stat_category column are present for processing
    cols_for_processing = list(dict.fromkeys([col for col in _EXPECTED_LEADER_COLS if col in leaders_df.columns] + [stat_category]))
    
    leaders_list = _process_dataframe(leaders_df.loc[:, cols_for_processing], single_row=False)
    if leaders_list is None:
        logger.error(f"DataFrame processing failed for league leaders {stat_category} ({season}).")
        error_msg = Errors.LEAGUE_LEADERS_PROCESSING.format(stat_category=stat_category, season=season)
        return format_response(error=error_msg)

    if top_n > 0: # top_n is already validated to be positive integer
        leaders_list = leaders_list[:top_n]

    logger.info(f"fetch_league_leaders_logic completed for {stat_category} ({season}), found {len(leaders_list)} leaders.")
    return format_response({"leaders": leaders_list})
"""
Provides logic to fetch and determine top-performing (trending) players
based on league leaders data for various statistical categories.
"""
import logging
import json
from typing import Any, Tuple, Optional, Set # Added Optional, Set
from functools import lru_cache
from datetime import datetime

from nba_api.stats.library.parameters import SeasonTypeAllStar, StatCategoryAbbreviation, PerMode48, Scope, LeagueID
from backend.core.errors import Errors
from backend.api_tools.league_leaders_data import fetch_league_leaders_logic
from backend.api_tools.utils import format_response
from backend.utils.validation import _validate_season_format
from backend.config import settings

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
CACHE_TTL_SECONDS_TRENDING = 14400  # 4 hours
TRENDING_PLAYERS_RAW_LEADERS_CACHE_SIZE = 64
TOP_PERFORMERS_PROCESSED_CACHE_SIZE = 128
DEFAULT_TOP_N_PERFORMERS = 5

_TRENDING_VALID_STAT_CATEGORIES: Set[str] = {getattr(StatCategoryAbbreviation, attr) for attr in dir(StatCategoryAbbreviation) if not attr.startswith('_') and isinstance(getattr(StatCategoryAbbreviation, attr), str)}
_TRENDING_VALID_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_TRENDING_VALID_PER_MODES: Set[str] = {getattr(PerMode48, attr) for attr in dir(PerMode48) if not attr.startswith('_') and isinstance(getattr(PerMode48, attr), str)}
_TRENDING_VALID_SCOPES: Set[str] = {getattr(Scope, attr) for attr in dir(Scope) if not attr.startswith('_') and isinstance(getattr(Scope, attr), str)}
_TRENDING_VALID_LEAGUE_IDS: Set[str] = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

# --- Helper Functions ---
@lru_cache(maxsize=TRENDING_PLAYERS_RAW_LEADERS_CACHE_SIZE)
def get_cached_league_leaders_for_trending(
    cache_key: Tuple, # Unique tuple of all relevant params for fetch_league_leaders_logic
    timestamp_bucket: str, # For time-based invalidation
    **kwargs: Any # Parameters for fetch_league_leaders_logic
) -> str:
    """Cached wrapper for `fetch_league_leaders_logic`."""
    logger.info(f"Cache miss/expiry for league leaders (trending, ts: {timestamp_bucket}) - fetching. Params: {kwargs}")
    try:
        return fetch_league_leaders_logic(**kwargs)
    except Exception as e:
        logger.error(f"fetch_league_leaders_logic failed within cache wrapper: {e}", exc_info=True)
        raise

def _validate_top_performers_params(
    category: str, season: str, season_type: str, per_mode: str,
    scope: str, league_id: str, top_n: int
) -> Optional[str]:
    """Validates parameters for fetch_top_performers_logic."""
    if not _validate_season_format(season):
        return Errors.INVALID_SEASON_FORMAT.format(season=season)
    if not isinstance(top_n, int) or top_n <= 0: # top_n already defaulted if invalid by main func
        # This specific log/defaulting is handled in main func, here just check type for safety
        pass # Assuming top_n is already validated/defaulted by caller
    if category not in _TRENDING_VALID_STAT_CATEGORIES:
        return Errors.INVALID_STAT_CATEGORY.format(value=category, options=", ".join(list(_TRENDING_VALID_STAT_CATEGORIES)[:7]))
    if season_type not in _TRENDING_VALID_SEASON_TYPES:
        return Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_TRENDING_VALID_SEASON_TYPES)[:5]))
    if per_mode not in _TRENDING_VALID_PER_MODES:
        return Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_TRENDING_VALID_PER_MODES)[:5]))
    if scope not in _TRENDING_VALID_SCOPES:
        return Errors.INVALID_SCOPE.format(value=scope, options=", ".join(list(_TRENDING_VALID_SCOPES)[:5]))
    if league_id not in _TRENDING_VALID_LEAGUE_IDS:
        return Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_TRENDING_VALID_LEAGUE_IDS)[:3]))
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=TOP_PERFORMERS_PROCESSED_CACHE_SIZE)
def fetch_top_performers_logic(
    category: str = StatCategoryAbbreviation.pts,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerMode48.per_game,
    scope: str = Scope.s,
    league_id: str = LeagueID.nba,
    top_n: int = DEFAULT_TOP_N_PERFORMERS,
    bypass_cache: bool = False
) -> str:
    """
    Fetches the top N performing players for a given statistical category and criteria.
    Utilizes `fetch_league_leaders_logic` and applies caching.
    """
    logger.info(f"Fetching top {top_n} performers for {category} in season {season}, type {season_type}, mode {per_mode}, scope {scope}, league {league_id}")

    # Validate top_n separately as it has a default and specific logging
    if not isinstance(top_n, int) or top_n <= 0:
        logger.warning(f"Invalid top_n value '{top_n}'. Must be a positive integer. Defaulting to {DEFAULT_TOP_N_PERFORMERS}.")
        top_n = DEFAULT_TOP_N_PERFORMERS

    param_error = _validate_top_performers_params(category, season, season_type, per_mode, scope, league_id, top_n)
    if param_error:
        return format_response(error=param_error)

    # Parameters for the underlying league leaders call
    params_for_league_leaders = {
        "season": season, "stat_category": category, "season_type": season_type,
        "per_mode": per_mode, "scope": scope, "league_id": league_id,
        "top_n": top_n # fetch_league_leaders_logic already handles limiting to top_n
    }
    # Cache key for the raw league leaders data
    raw_leaders_cache_key = tuple(sorted(params_for_league_leaders.items()))
    timestamp_bucket = str(int(datetime.now().timestamp() // CACHE_TTL_SECONDS_TRENDING))

    try:
        leaders_json_str: str
        if bypass_cache:
            logger.info(f"Bypassing cache, fetching fresh league leaders data: {params_for_league_leaders}")
            leaders_json_str = fetch_league_leaders_logic(**params_for_league_leaders)
        else:
            leaders_json_str = get_cached_league_leaders_for_trending(
                cache_key=raw_leaders_cache_key,
                timestamp_bucket=timestamp_bucket, # Corrected arg name
                **params_for_league_leaders
            )
        
        try:
            data = json.loads(leaders_json_str)
        except json.JSONDecodeError as json_err:
            logger.error(f"Failed to decode JSON from fetch_league_leaders_logic: {json_err}. Response (first 500): {leaders_json_str[:500]}")
            return format_response(error=Errors.PROCESSING_ERROR.format(error="invalid JSON from league leaders"))

        if isinstance(data, dict) and "error" in data:
            logger.error(f"Error received from upstream league leaders fetch: {data['error']}")
            return leaders_json_str # Propagate the error JSON

        leaders_list = data.get("leaders", []) # fetch_league_leaders_logic already returns the top_n
        
        result_payload = {
            "season": season, "stat_category": category, "season_type": season_type,
            "per_mode": per_mode, "scope": scope, "league_id": league_id,
            "requested_top_n": top_n, # The number originally requested
            "top_performers": leaders_list # This list is already the top_n (or fewer if less available)
        }
        logger.info(f"Successfully prepared top {len(leaders_list)} performers for {category} in {season}.")
        return format_response(result_payload)

    except Exception as e:
        logger.error(f"Unexpected error in fetch_top_performers_logic: {e}", exc_info=True)
        return format_response(error=Errors.TRENDING_UNEXPECTED.format(error=str(e)))

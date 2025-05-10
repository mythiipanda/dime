import logging
import json
# import time # Not actively used, consider removing
from typing import Dict, Any, Optional, Tuple, List
from functools import lru_cache
from datetime import datetime

from nba_api.stats.library.parameters import SeasonTypeAllStar, StatCategoryAbbreviation, PerMode48, Scope, LeagueID # Added PerMode48, Scope, LeagueID for fetch_league_leaders_logic params
from backend.config import CURRENT_SEASON, Errors, DEFAULT_TIMEOUT # Removed MIN_PLAYER_SEARCH_LENGTH as it's not used here
from backend.api_tools.league_tools import fetch_league_leaders_logic # This is the core dependency
from backend.api_tools.utils import format_response, _validate_season_format

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS_TRENDING = 14400 # 4 hours for trending data, as it's based on league leaders

@lru_cache(maxsize=64)
def get_cached_league_leaders_for_trending( # Renamed for clarity
    cache_key: Tuple,
    timestamp: str,
    **kwargs: Any # Parameters for fetch_league_leaders_logic
) -> str:
    """
    Cached wrapper specifically for `fetch_league_leaders_logic` when called by `fetch_top_performers_logic`.
    Uses a timestamp for time-based cache invalidation (approximately every 4 hours).

    Args:
        cache_key (Tuple): A tuple representing the parameters passed to `fetch_league_leaders_logic`,
                           used for `lru_cache` keying (e.g., (category, season, season_type, per_mode, scope, league_id, top_n_internal)).
        timestamp (str): An ISO format timestamp string, typically for the current 4-hour block,
                         used to manage cache invalidation.
        **kwargs: Keyword arguments to be passed directly to `fetch_league_leaders_logic`.

    Returns:
        str: The JSON string result from `fetch_league_leaders_logic`.

    Raises:
        Exception: If `fetch_league_leaders_logic` fails, to be handled by the caller.
    """
    logger.info(f"Cache miss/expiry for league leaders (trending) - fetching new data. Key components: {kwargs.get('stat_category')}, {kwargs.get('season')}, {kwargs.get('season_type')}")
    try:
        # Call the underlying logic function which returns a JSON string
        return fetch_league_leaders_logic(**kwargs)
    except Exception as e:
        logger.error(f"fetch_league_leaders_logic failed within get_cached_league_leaders_for_trending: {e}", exc_info=True)
        raise e # Re-raise to be handled by fetch_top_performers_logic

@lru_cache(maxsize=128) # Caches the final processed result of top performers
def fetch_top_performers_logic(
    category: str = StatCategoryAbbreviation.pts,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerMode48.per_game, # Added per_mode for consistency with league_leaders
    scope: str = Scope.s,             # Added scope
    league_id: str = LeagueID.nba,    # Added league_id
    top_n: int = 5,
    bypass_cache: bool = False
) -> str:
    """
    Fetches the top N performing players for a given statistical category, season, and other criteria.
    This function utilizes `fetch_league_leaders_logic` and applies caching.

    Args:
        category (str, optional): Statistical category abbreviation. Valid values from `StatCategoryAbbreviation`
                                  (e.g., "PTS", "REB", "AST"). Defaults to "PTS".
        season (str, optional): NBA season in YYYY-YY format. Defaults to `CURRENT_SEASON`.
        season_type (str, optional): Type of season. Valid values from `SeasonTypeAllStar`
                                     (e.g., "Regular Season", "Playoffs"). Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode for fetching leaders. Valid values from `PerMode48`
                                  (e.g., "PerGame", "Totals"). Defaults to "PerGame".
        scope (str, optional): Scope for fetching leaders. Valid values from `Scope` (e.g., "S" for Season).
                               Defaults to "S".
        league_id (str, optional): League ID. Valid values from `LeagueID` (e.g., "00" for NBA).
                                   Defaults to "00".
        top_n (int, optional): Number of top performers to return. Must be a positive integer. Defaults to 5.
        bypass_cache (bool, optional): If True, ignores cached data and fetches fresh data. Defaults to False.

    Returns:
        str: JSON string with top performers.
             Expected dictionary structure passed to format_response:
             {
                 "season": str,
                 "stat_category": str,
                 "season_type": str,
                 "per_mode": str,
                 "scope": str,
                 "league_id": str,
                 "requested_top_n": int,
                 "top_performers": [ // List of player objects, up to top_n
                     {
                         "PLAYER_ID": int,
                         "RANK": int,
                         "PLAYER": str, // Player's full name
                         "TEAM_ID": int,
                         "TEAM": str, // Team abbreviation
                         "GP": int,   // Games Played
                         "MIN": float, // Minutes (total or per game based on per_mode)
                         category: float // The actual stat value, e.g., "PTS": 25.5
                         // Other stats might be included by fetch_league_leaders_logic
                     }, ...
                 ]
             }
             Returns {"top_performers": []} if no leaders are found.
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.info(f"Fetching top {top_n} performers for {category} in season {season}, type {season_type}, mode {per_mode}, scope {scope}, league {league_id}")

    if not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if not isinstance(top_n, int) or top_n <= 0:
        error_msg = Errors.INVALID_TOP_N.format(value=top_n)
        return format_response(error=error_msg)

    VALID_STAT_CATEGORIES = {getattr(StatCategoryAbbreviation, attr) for attr in dir(StatCategoryAbbreviation) if not attr.startswith('_') and isinstance(getattr(StatCategoryAbbreviation, attr), str)}
    if category not in VALID_STAT_CATEGORIES:
        return format_response(error=Errors.INVALID_STAT_CATEGORY.format(value=category, options=", ".join(VALID_STAT_CATEGORIES)))
    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(VALID_SEASON_TYPES)))
    VALID_PER_MODES = {getattr(PerMode48, attr) for attr in dir(PerMode48) if not attr.startswith('_') and isinstance(getattr(PerMode48, attr), str)}
    if per_mode not in VALID_PER_MODES:
        return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(VALID_PER_MODES)))
    VALID_SCOPES = {getattr(Scope, attr) for attr in dir(Scope) if not attr.startswith('_') and isinstance(getattr(Scope, attr), str)}
    if scope not in VALID_SCOPES:
        return format_response(error=Errors.INVALID_SCOPE.format(value=scope, options=", ".join(VALID_SCOPES)))
    VALID_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}
    if league_id not in VALID_LEAGUE_IDS:
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(VALID_LEAGUE_IDS)))


    # fetch_league_leaders_logic might return more than top_n, so we fetch a reasonable amount (e.g., top_n or a bit more if top_n is small)
    # and then slice. Let's fetch up to top_n (or a default like 25 if top_n is very large, though API limits exist).
    # The underlying fetch_league_leaders_logic already has a top_n param.
    internal_top_n_fetch = top_n # We want exactly top_n from the leaders list.

    cache_key_params = (category, season, season_type, per_mode, scope, league_id, internal_top_n_fetch) # Key for the cached call
    # Use a timestamp that changes every CACHE_TTL_SECONDS_TRENDING for time-based invalidation
    current_time_epoch = int(datetime.now().timestamp())
    timestamp_bucket = str(current_time_epoch // CACHE_TTL_SECONDS_TRENDING)

    try:
        params_for_league_leaders = {
            "season": season, "stat_category": category, "season_type": season_type,
            "per_mode": per_mode, "scope": scope, "league_id": league_id,
            "top_n": internal_top_n_fetch # Pass the desired number to fetch
        }

        leaders_json_str: str
        if bypass_cache:
            logger.info(f"Bypassing cache, fetching fresh league leaders data for top performers: {params_for_league_leaders}")
            leaders_json_str = fetch_league_leaders_logic(**params_for_league_leaders)
        else:
            leaders_json_str = get_cached_league_leaders_for_trending(cache_key=cache_key_params, timestamp=timestamp_bucket, **params_for_league_leaders)
        
        try:
            data = json.loads(leaders_json_str)
        except json.JSONDecodeError as json_err:
            logger.error(f"Failed to decode JSON from fetch_league_leaders_logic: {json_err}. Response (first 500 chars): {leaders_json_str[:500]}")
            error_msg = Errors.PROCESSING_ERROR.format(error="invalid JSON format from league leaders data")
            return format_response(error=error_msg)

        if isinstance(data, dict) and "error" in data:
            logger.error(f"Error received from fetch_league_leaders_logic: {data['error']}")
            return leaders_json_str # Propagate the error JSON string

        leaders_list = data.get("leaders", [])
        # The underlying fetch_league_leaders_logic should have already sliced by its top_n,
        # so this list should contain at most `internal_top_n_fetch` (which is `top_n`) items.
        
        result_payload = {
            "season": season, "stat_category": category, "season_type": season_type,
            "per_mode": per_mode, "scope": scope, "league_id": league_id,
            "requested_top_n": top_n,
            "top_performers": leaders_list # This list is already expected to be of size top_n (or less if fewer leaders)
        }
        logger.info(f"Successfully prepared top {len(leaders_list)} performers for {category} in {season}.")
        return format_response(result_payload)

    except Exception as e:
        logger.error(f"Unexpected error in fetch_top_performers_logic: {e}", exc_info=True)
        error_msg = Errors.TRENDING_UNEXPECTED.format(error=str(e))
        return format_response(error=error_msg)

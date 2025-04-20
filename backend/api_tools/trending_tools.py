import logging
import json
import time # Import time module for caching
from typing import Dict, Any
from nba_api.stats.library.parameters import SeasonTypeAllStar
from backend.config import CURRENT_SEASON
from backend.api_tools.league_tools import fetch_league_leaders_logic

logger = logging.getLogger(__name__)

# Cache dictionary and TTL (4 hours for trending data)
_trending_cache: Dict[tuple, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 14400

def fetch_top_performers_logic(
    category: str = "PTS",
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    top_n: int = 5,
    bypass_cache: bool = False
) -> str:
    """
    Fetch top performing players for a stat category in a season, with caching.
    Returns JSON string with top performers.
    """
    logger.info(
        f"Fetching top {top_n} performers for {category} in season {season}, type {season_type}, bypass_cache={bypass_cache}"
    )

    # --- Cache Check ---
    # Include top_n in cache key as it affects the result
    cache_key = (category, season, season_type, top_n)
    current_time = time.time()

    if not bypass_cache and cache_key in _trending_cache:
        cached_entry = _trending_cache[cache_key]
        if current_time - cached_entry['timestamp'] < CACHE_TTL_SECONDS:
            logger.info(f"Returning cached trending data for key: {cache_key}")
            return cached_entry['data']
        else:
            logger.info(f"Cache expired for key: {cache_key}")
            del _trending_cache[cache_key] # Remove expired entry
    # --- End Cache Check ---

    try:
        logger.info(f"Fetching fresh trending data for key: {cache_key}")
        # fetch_league_leaders_logic already returns JSON string
        full_json = fetch_league_leaders_logic(season, category, season_type)
        data = json.loads(full_json)

        # Check for error in the response from fetch_league_leaders_logic
        if "error" in data:
            logger.error(f"Error from fetch_league_leaders_logic: {data['error']}")
            return full_json # Return the error response directly

        leaders = data.get("leaders", [])
        top = leaders[:top_n]
        result = {
            "season": data.get("season", season),
            "stat_category": data.get("stat_category", category),
            "season_type": data.get("season_type", season_type),
            "top_performers": top
        }
        result_json = json.dumps(result)

        # Store fresh data in cache
        _trending_cache[cache_key] = {'data': result_json, 'timestamp': current_time}
        logger.info(f"Cached fresh trending data for key: {cache_key}")

        return result_json
    except Exception as e:
        logger.error(f"Error processing top performers data: {e}", exc_info=True)
        return json.dumps({"error": str(e)})

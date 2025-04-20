import logging
import time # Import time module for caching
from typing import Any, Dict
from nba_api.live.nba.library.http import NBALiveHTTP
from backend.config import DEFAULT_TIMEOUT
from backend.api_tools.utils import format_response

logger = logging.getLogger(__name__)

# Cache dictionary and TTL (60 seconds for live data)
_odds_cache: Dict[str, Any] = {}
CACHE_TTL_SECONDS = 60

def fetch_odds_data_logic(bypass_cache: bool = False) -> Dict[str, Any]:
    """
    Fetches live betting odds for NBA games via NBALiveHTTP, with caching.
    Returns a dict with a "games" key or an "error" message.
    """
    logger.info(f"Executing fetch_odds_data_logic with bypass_cache={bypass_cache}")

    # --- Cache Check ---
    cache_key = "todays_odds" # Simple key as there are no parameters
    current_time = time.time()

    if not bypass_cache and cache_key in _odds_cache:
        cached_entry = _odds_cache[cache_key]
        if current_time - cached_entry['timestamp'] < CACHE_TTL_SECONDS:
            logger.info(f"Returning cached odds data for key: {cache_key}")
            return cached_entry['data']
        else:
            logger.info(f"Cache expired for key: {cache_key}")
            del _odds_cache[cache_key] # Remove expired entry
    # --- End Cache Check ---

    try:
        logger.info(f"Fetching fresh odds data for key: {cache_key}")
        http = NBALiveHTTP()
        response = http.send_api_request(
            endpoint="odds/odds_todaysGames.json",
            parameters={},
            proxy=None,
            headers=None,
            timeout=DEFAULT_TIMEOUT
        )
        response_dict = response.get_dict()
        result_data = {"games": response_dict.get("games", [])}

        # Store fresh data in cache
        _odds_cache[cache_key] = {'data': result_data, 'timestamp': current_time}
        logger.info(f"Cached fresh odds data for key: {cache_key}")

        return result_data
    except Exception as e:
        logger.exception(f"Error fetching odds data: {e}")
        return {"error": f"Failed to fetch odds data: {str(e)}"}

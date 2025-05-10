import logging
import time # Not actively used, consider removing if no specific timing logic is planned
import json
from typing import Any, Dict, List, Tuple # Added List
from functools import lru_cache
from datetime import datetime

from nba_api.live.nba.library.http import NBALiveHTTP
from backend.config import DEFAULT_TIMEOUT, Errors
from backend.api_tools.utils import format_response

logger = logging.getLogger(__name__)

# CACHE_TTL_SECONDS is descriptive but not directly used by lru_cache for time expiry.
# The timestamp trick in get_cached_odds_data handles hourly invalidation.
CACHE_TTL_SECONDS_ODDS = 3600 # Odds might change, but hourly cache for the raw pull is reasonable.

@lru_cache(maxsize=2) # Cache for "todays_odds" key, invalidated by timestamp
def get_cached_odds_data(
    cache_key: str,
    timestamp: str # ISO format timestamp string for the current hour
) -> Dict[str, Any]:
    """
    Cached wrapper for fetching live odds data using `NBALiveHTTP`.
    The `timestamp` (typically current hour) is part of the cache key to ensure periodic updates.

    Args:
        cache_key (str): A static string part of the cache key (e.g., "todays_live_odds").
        timestamp (str): An ISO format timestamp string, typically for the current hour,
                         used to manage cache invalidation.

    Returns:
        Dict[str, Any]: The raw dictionary response from the "odds/odds_todaysGames.json" endpoint.

    Raises:
        Exception: If the API call fails, to be caught by the caller (`fetch_odds_data_logic`).
    """
    logger.info(f"Cache miss or expiry for odds data - fetching new data (Key: {cache_key}, Timestamp: {timestamp})")
    try:
        http_client = NBALiveHTTP() # Corrected variable name
        response = http_client.send_api_request(
            endpoint="odds/odds_todaysGames.json",
            parameters={}, # This endpoint typically doesn't require parameters
            proxy=None, # Add proxy configuration if needed globally
            headers=None, # Add custom headers if needed
            timeout=DEFAULT_TIMEOUT
        )
        # The NBALiveHTTP().send_api_request().get_dict() returns the parsed JSON dictionary
        return response.get_dict()
    except Exception as e:
        logger.error(f"NBALiveHTTP odds request failed: {e}", exc_info=True)
        raise e # Re-raise to be handled by the calling function

def fetch_odds_data_logic(bypass_cache: bool = False) -> str:
    """
    Fetches live betting odds for today's NBA games using the NBALiveHTTP client, with caching.
    The odds data includes various markets (e.g., moneyline, spread, total) from different bookmakers.

    Args:
        bypass_cache (bool, optional): If True, ignores any cached data and fetches fresh data from the API.
                                       Defaults to False.

    Returns:
        str: JSON string containing a list of today's games with their associated odds data.
             Expected dictionary structure passed to format_response:
             {
                 "games": [
                     {
                         "gameId": str,
                         "awayTeamId": int,
                         "homeTeamId": int,
                         "gameTime": str (e.g., "2024-01-15T19:00:00-05:00"),
                         "gameStatus": int, // 1: Scheduled, 2: In Progress, 3: Final
                         "gameStatusText": str,
                         "markets": [ // List of betting markets available for the game
                             {
                                 "marketId": str,
                                 "name": str, // e.g., "2way - Total", "Point Spread", "Moneyline"
                                 "books": [ // List of bookmakers offering odds for this market
                                     {
                                         "bookId": str,
                                         "name": str, // e.g., "DraftKings", "FanDuel"
                                         "outcomes": [ // List of possible outcomes and their odds
                                             {
                                                 "type": str, // e.g., "home", "away", "over", "under"
                                                 "odds": str, // e.g., "-110", "+150"
                                                 "openingOdds": Optional[str],
                                                 "value": Optional[str] // e.g., for spread or total lines "7.5", "220.5"
                                             }, ...
                                         ]
                                     }, ...
                                 ]
                             }, ...
                         ]
                     }, ...
                 ]
             }
             Returns {"games": []} if no odds data is found or an error occurs during fetching/processing.
             Or an {'error': 'Error message'} object if a critical issue occurs.
    """
    logger.info(f"Executing fetch_odds_data_logic with bypass_cache={bypass_cache}")

    cache_key_odds = "todays_live_odds_data"
    # Hourly timestamp for cache invalidation
    cache_invalidation_timestamp = datetime.now().replace(minute=0, second=0, microsecond=0).isoformat()

    try:
        raw_response_dict: Dict[str, Any]
        if bypass_cache:
            logger.info("Bypassing cache, fetching fresh live odds data.")
            http_client_direct = NBALiveHTTP()
            api_response = http_client_direct.send_api_request(
                endpoint="odds/odds_todaysGames.json", parameters={}, timeout=DEFAULT_TIMEOUT
            )
            raw_response_dict = api_response.get_dict()
        else:
            raw_response_dict = get_cached_odds_data(cache_key=cache_key_odds, timestamp=cache_invalidation_timestamp)

        # The API response structure is typically {"games": [...]} directly or nested under a key.
        # Based on NBALiveHTTP, get_dict() should give the main content.
        # If "games" is not top-level, adjust access (e.g., raw_response_dict.get('some_key', {}).get('games', []))
        games_data_list = raw_response_dict.get("games", [])
        
        if not isinstance(games_data_list, list): # Basic type check
            logger.error(f"Fetched odds data 'games' field is not a list: {type(games_data_list)}")
            games_data_list = [] # Default to empty list to prevent further errors

        result_payload = {"games": games_data_list}
        logger.info(f"Successfully fetched or retrieved cached odds data. Number of games: {len(games_data_list)}")
        return format_response(result_payload)

    except Exception as e:
        logger.error(f"Error fetching or processing odds data: {e}", exc_info=True)
        error_msg = Errors.ODDS_API_UNEXPECTED.format(error=str(e))
        return format_response(error=error_msg)

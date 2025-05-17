"""
Handles fetching live betting odds for today's NBA games using NBALiveHTTP.
Includes caching logic for the raw API response.
"""
import logging
from typing import Any, Dict
from functools import lru_cache
from datetime import datetime

from nba_api.live.nba.library.http import NBALiveHTTP
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import format_response

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
CACHE_TTL_SECONDS_ODDS = 3600  # 1 hour
ODDS_RAW_CACHE_SIZE = 2
ODDS_ENDPOINT_PATH = "odds/odds_todaysGames.json"

# --- Caching Function for Raw Data ---
@lru_cache(maxsize=ODDS_RAW_CACHE_SIZE)
def get_cached_odds_data(
    cache_key: str, # Static part of the key, e.g., "todays_live_odds"
    timestamp_bucket: str # Timestamp bucket for time-based invalidation
) -> Dict[str, Any]:
    """
    Cached wrapper for fetching live odds data using `NBALiveHTTP`.
    The `timestamp_bucket` ensures periodic cache invalidation.

    Args:
        cache_key: A static string for the cache key.
        timestamp_bucket: A string derived from the current time, bucketed by CACHE_TTL_SECONDS_ODDS.

    Returns:
        The raw dictionary response from the odds endpoint.

    Raises:
        Exception: If the API call fails, to be handled by the caller.
    """
    logger.info(f"Cache miss or expiry for odds data - fetching new data (Key: {cache_key}, Timestamp Bucket: {timestamp_bucket})")
    try:
        http_client = NBALiveHTTP()
        response = http_client.send_api_request(
            endpoint=ODDS_ENDPOINT_PATH,
            parameters={}, # This endpoint typically doesn't require parameters
            proxy=None,
            headers=None,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        return response.get_dict()
    except Exception as e:
        logger.error(f"NBALiveHTTP odds request failed: {e}", exc_info=True)
        raise # Re-raise to be handled by the calling function

# --- Main Logic Function ---
def fetch_odds_data_logic(bypass_cache: bool = False) -> str:
    """
    Fetches live betting odds for today's NBA games.
    The odds data includes various markets from different bookmakers.

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
    cache_invalidation_timestamp_bucket = str(int(datetime.now().timestamp() // CACHE_TTL_SECONDS_ODDS))

    try:
        raw_response_dict: Dict[str, Any]
        if bypass_cache:
            logger.info("Bypassing cache, fetching fresh live odds data.")
            http_client_direct = NBALiveHTTP()
            api_response = http_client_direct.send_api_request(
                endpoint=ODDS_ENDPOINT_PATH, parameters={}, timeout=settings.DEFAULT_TIMEOUT_SECONDS
            )
            raw_response_dict = api_response.get_dict()
        else:
            raw_response_dict = get_cached_odds_data(cache_key=cache_key_odds, timestamp_bucket=cache_invalidation_timestamp_bucket)
        
        games_data_list = raw_response_dict.get("games", [])
        
        if not isinstance(games_data_list, list):
            logger.error(f"Fetched odds data 'games' field is not a list: {type(games_data_list)}")
            games_data_list = [] # Default to empty list to prevent further errors

        result_payload = {"games": games_data_list}
        logger.info(f"Successfully fetched or retrieved cached odds data. Number of games: {len(games_data_list)}")
        return format_response(result_payload)

    except Exception as e:
        logger.error(f"Error fetching or processing odds data: {e}", exc_info=True)
        error_msg = Errors.ODDS_API_UNEXPECTED.format(error=str(e))
        return format_response(error=error_msg)

"""
Handles fetching live betting odds for today's NBA games using NBALiveHTTP.
Includes caching logic for the raw API response.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
from typing import Any, Dict, Optional, Union, List, Tuple
from functools import lru_cache
from datetime import datetime
import pandas as pd

from nba_api.live.nba.library.http import NBALiveHTTP
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import format_response

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
CACHE_TTL_SECONDS_ODDS = 3600  # 1 hour
ODDS_RAW_CACHE_SIZE = 2
ODDS_ENDPOINT_PATH = "odds/odds_todaysGames.json"
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
ODDS_CSV_PATH = os.path.join(CSV_CACHE_DIR, "odds_data.csv")

# Ensure cache directory exists
os.makedirs(CSV_CACHE_DIR, exist_ok=True)

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

def _flatten_odds_data(games_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Flattens the nested odds data structure into a list of records suitable for a DataFrame.

    Args:
        games_data: List of game dictionaries with nested market, book, and outcome data

    Returns:
        List of flattened dictionaries with one record per game-market-book-outcome combination
    """
    flattened_records = []

    for game in games_data:
        game_id = game.get('gameId', '')
        away_team_id = game.get('awayTeamId', '')
        home_team_id = game.get('homeTeamId', '')
        game_time = game.get('gameTime', '')
        game_status = game.get('gameStatus', '')
        game_status_text = game.get('gameStatusText', '')

        # Handle games without markets
        if 'markets' not in game or not game['markets']:
            # Add a basic record with just game info
            flattened_records.append({
                'gameId': game_id,
                'awayTeamId': away_team_id,
                'homeTeamId': home_team_id,
                'gameTime': game_time,
                'gameStatus': game_status,
                'gameStatusText': game_status_text,
                'marketId': '',
                'marketName': '',
                'bookId': '',
                'bookName': '',
                'outcomeType': '',
                'odds': '',
                'openingOdds': '',
                'value': ''
            })
            continue

        for market in game['markets']:
            market_id = market.get('marketId', '')
            market_name = market.get('name', '')

            # Handle markets without books
            if 'books' not in market or not market['books']:
                flattened_records.append({
                    'gameId': game_id,
                    'awayTeamId': away_team_id,
                    'homeTeamId': home_team_id,
                    'gameTime': game_time,
                    'gameStatus': game_status,
                    'gameStatusText': game_status_text,
                    'marketId': market_id,
                    'marketName': market_name,
                    'bookId': '',
                    'bookName': '',
                    'outcomeType': '',
                    'odds': '',
                    'openingOdds': '',
                    'value': ''
                })
                continue

            for book in market['books']:
                book_id = book.get('bookId', '')
                book_name = book.get('name', '')

                # Handle books without outcomes
                if 'outcomes' not in book or not book['outcomes']:
                    flattened_records.append({
                        'gameId': game_id,
                        'awayTeamId': away_team_id,
                        'homeTeamId': home_team_id,
                        'gameTime': game_time,
                        'gameStatus': game_status,
                        'gameStatusText': game_status_text,
                        'marketId': market_id,
                        'marketName': market_name,
                        'bookId': book_id,
                        'bookName': book_name,
                        'outcomeType': '',
                        'odds': '',
                        'openingOdds': '',
                        'value': ''
                    })
                    continue

                for outcome in book['outcomes']:
                    flattened_records.append({
                        'gameId': game_id,
                        'awayTeamId': away_team_id,
                        'homeTeamId': home_team_id,
                        'gameTime': game_time,
                        'gameStatus': game_status,
                        'gameStatusText': game_status_text,
                        'marketId': market_id,
                        'marketName': market_name,
                        'bookId': book_id,
                        'bookName': book_name,
                        'outcomeType': outcome.get('type', ''),
                        'odds': outcome.get('odds', ''),
                        'openingOdds': outcome.get('openingOdds', ''),
                        'value': outcome.get('value', '')
                    })

    return flattened_records

def _convert_to_dataframe(games_data: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Converts the odds data to a pandas DataFrame with flattened structure.

    Args:
        games_data: List of game dictionaries from the API response

    Returns:
        DataFrame with flattened odds data
    """
    flattened_records = _flatten_odds_data(games_data)

    if not flattened_records:
        # Return empty DataFrame with expected columns
        return pd.DataFrame(columns=[
            'gameId', 'awayTeamId', 'homeTeamId', 'gameTime', 'gameStatus', 'gameStatusText',
            'marketId', 'marketName', 'bookId', 'bookName', 'outcomeType', 'odds', 'openingOdds', 'value'
        ])

    return pd.DataFrame(flattened_records)

def _save_to_csv(df: pd.DataFrame, file_path: str = ODDS_CSV_PATH) -> None:
    """
    Saves the DataFrame to a CSV file.

    Args:
        df: DataFrame to save
        file_path: Path to save the CSV file
    """
    try:
        df.to_csv(file_path, index=False)
        logger.info(f"Saved odds data to CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving odds data to CSV: {e}", exc_info=True)

# --- Main Logic Function ---
def fetch_odds_data_logic(
    bypass_cache: bool = False,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, pd.DataFrame]]:
    """
    Fetches live betting odds for today's NBA games.
    The odds data includes various markets from different bookmakers.

    Args:
        bypass_cache (bool, optional): If True, ignores any cached data and fetches fresh data from the API.
                                       Defaults to False.
        return_dataframe (bool, optional): If True, returns both JSON string and pandas DataFrame.
                                          Defaults to False (returns only JSON string).

    Returns:
        Union[str, Tuple[str, pd.DataFrame]]:
            If return_dataframe=False: JSON string containing a list of today's games with their associated odds data.
            If return_dataframe=True: Tuple containing (JSON string, pandas DataFrame)

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
    logger.info(f"Executing fetch_odds_data_logic with bypass_cache={bypass_cache}, return_dataframe={return_dataframe}")

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

        json_response = format_response(result_payload)

        if return_dataframe:
            df = _convert_to_dataframe(games_data_list)
            _save_to_csv(df)
            return json_response, df

        return json_response

    except Exception as e:
        logger.error(f"Error fetching or processing odds data: {e}", exc_info=True)
        error_msg = Errors.ODDS_API_UNEXPECTED.format(error=str(e))
        json_response = format_response(error=error_msg)

        if return_dataframe:
            # Return empty DataFrame with expected columns in case of error
            df = pd.DataFrame(columns=[
                'gameId', 'awayTeamId', 'homeTeamId', 'gameTime', 'gameStatus', 'gameStatusText',
                'marketId', 'marketName', 'bookId', 'bookName', 'outcomeType', 'odds', 'openingOdds', 'value'
            ])
            return json_response, df

        return json_response

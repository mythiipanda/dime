"""
Handles fetching NBA scoreboard data for a specific date.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import json
import os
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import date, datetime
from functools import lru_cache
from requests.exceptions import ReadTimeout, ConnectionError
import pandas as pd

from nba_api.live.nba.endpoints import ScoreBoard as LiveScoreBoard
from nba_api.stats.endpoints import scoreboardv2
from nba_api.stats.library.parameters import LeagueID

from config import settings
from core.errors import Errors
from api_tools.utils import format_response, _process_dataframe, retry_on_timeout
from utils.validation import validate_date_format
from utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Cache Directory Setup ---
SCOREBOARD_CSV_DIR = get_cache_dir("scoreboard")

# Cache TTL constants
CACHE_TTL_SECONDS_LIVE = 60
CACHE_TTL_SECONDS_STATIC = 3600 * 6

@lru_cache(maxsize=2)
def get_cached_live_scoreboard_data(cache_key: str, timestamp: str) -> Dict[str, Any]:
    """
    Cached wrapper for fetching raw live scoreboard data using `nba_api.live.nba.endpoints.ScoreBoard`.
    The `timestamp` (typically current minute) is part of the cache key to ensure frequent updates.

    Args:
        cache_key (str): A static string part of the cache key (e.g., "live_scoreboard").
        timestamp (str): An ISO format timestamp string, typically for the current minute,
                         used to manage cache invalidation for live data.

    Returns:
        Dict[str, Any]: The raw dictionary response from the LiveScoreBoard endpoint.

    Raises:
        Exception: If the API call fails, to be caught by the caller.
    """
    logger.info(f"Cache miss/expiry for live scoreboard - fetching new data (Timestamp: {timestamp}, CacheKey: {cache_key})")
    try:
        board = LiveScoreBoard(timeout=settings.DEFAULT_TIMEOUT_SECONDS) # Changed
        return board.get_dict()
    except Exception as e:
        logger.error(f"Live ScoreBoard API call failed: {e}", exc_info=True)
        raise e

@lru_cache(maxsize=32) # Cache more historical/future dates
def get_cached_static_scoreboard_data(cache_key: Tuple, timestamp: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Cached wrapper for fetching and initially processing static scoreboard data using `nba_api.stats.endpoints.scoreboardv2`.
    The `timestamp` (typically current hour) is part of the cache key for hourly invalidation.
    `kwargs` are passed directly to the `scoreboardv2.ScoreboardV2` endpoint.

    Args:
        cache_key (Tuple): A tuple representing the static parts of the cache key (e.g., ("static_scoreboard", game_date, league_id)).
        timestamp (str): An ISO format timestamp string, typically for the current hour,
                         used to manage cache invalidation for static data.
        **kwargs: Arguments to pass to `scoreboardv2.ScoreboardV2` (e.g., `game_date`, `league_id`, `day_offset`).

    Returns:
        Dict[str, Any]: A dictionary containing processed DataFrames (as lists of dicts) for "game_header" and "line_score".
                        Example: {"game_header": [...], "line_score": [...]}

    Raises:
        Exception: If the API call or initial DataFrame processing fails, to be caught by the caller.
    """
    logger.info(f"Cache miss/expiry for static scoreboard - fetching new data for {kwargs.get('game_date')} (Timestamp: {timestamp}, CacheKey: {cache_key})")
    try:
        scoreboard_endpoint = scoreboardv2.ScoreboardV2(**kwargs, timeout=settings.DEFAULT_TIMEOUT_SECONDS) # Changed
        game_header_list = _process_dataframe(scoreboard_endpoint.game_header.get_data_frame(), single_row=False)
        line_score_list = _process_dataframe(scoreboard_endpoint.line_score.get_data_frame(), single_row=False)

        # Ensure lists are returned even if processing results in None (e.g. due to empty df and processing error)
        return {
            "game_header": game_header_list if game_header_list is not None else [],
            "line_score": line_score_list if line_score_list is not None else []
        }
    except Exception as e:
        logger.error(f"ScoreboardV2 API call or processing failed for {kwargs.get('game_date')}: {e}", exc_info=True)
        raise e

def fetch_scoreboard_data_logic(
    game_date: Optional[str] = None,
    league_id: str = LeagueID.nba,
    day_offset: int = 0,
    bypass_cache: bool = False,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches NBA scoreboard data for a specific date.
    Uses the live NBA API endpoint for the current date and the static ScoreboardV2 endpoint
    for past or future dates. Data is cached to minimize API calls.

    Provides DataFrame output capabilities.

    Args:
        game_date: The date for the scoreboard in YYYY-MM-DD format.
                   Defaults to the current local date if None.
        league_id: The league ID. Valid values from `LeagueID` (e.g., "00" for NBA).
                   Defaults to "00" (NBA). This primarily applies to the static ScoreboardV2.
        day_offset: Day offset from `game_date` if `game_date` is also provided.
                    This primarily applies to the static ScoreboardV2. Defaults to 0.
        bypass_cache: If True, ignores cached data and fetches fresh data. Defaults to False.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string containing formatted scoreboard data.
                 Expected dictionary structure passed to format_response:
                 {
                     "gameDate": str (YYYY-MM-DD), // The target date for the scoreboard
                     "games": [
                         { // Structure for each game
                             "gameId": str,
                             "gameStatus": int, // 1: Scheduled, 2: In Progress, 3: Final
                             "gameStatusText": str, // e.g., "7:00 PM ET", "Q2 5:30", "Final", "Halftime"
                             "period": int, // Current period if game is live
                             "gameClock": Optional[str], // Current game clock if game is live (e.g., "05:30")
                             "homeTeam": {
                                 "teamId": int, "teamTricode": str, "score": int,
                                 "wins": Optional[int], "losses": Optional[int]
                             },
                             "awayTeam": {
                                 "teamId": int, "teamTricode": str, "score": int,
                                 "wins": Optional[int], "losses": Optional[int]
                             },
                             "gameEt": str // Game start time in Eastern Time (UTC for live, EST for static)
                         }, ...
                     ]
                 }
                 Returns {"games": []} if no games are found for the date.
                 Or an {'error': 'Error message'} object if a critical issue occurs.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    effective_date_str = game_date if game_date is not None else date.today().strftime('%Y-%m-%d')
    # Explicitly log the date being used, especially when game_date is None
    if game_date is None:
        logger.info(f"fetch_scoreboard_data_logic: game_date is None, defaulting to effective_date_str (today's date): {effective_date_str}")

    logger.info(f"Executing fetch_scoreboard_data_logic for Date: {effective_date_str}, League: {league_id}, Offset: {day_offset}, BypassCache: {bypass_cache}")

    if not validate_date_format(effective_date_str):
        logger.error(f"Invalid date format provided: {effective_date_str}. Use YYYY-MM-DD.")
        error_response = format_response(error=Errors.INVALID_DATE_FORMAT.format(date=effective_date_str))
        if return_dataframe:
            return error_response, {}
        return error_response

    VALID_LEAGUE_IDS = {getattr(LeagueID, lid) for lid in dir(LeagueID) if not lid.startswith('_') and isinstance(getattr(LeagueID, lid), str)}
    if league_id not in VALID_LEAGUE_IDS:
        error_response = format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(VALID_LEAGUE_IDS)))
        if return_dataframe:
            return error_response, {}
        return error_response

    is_today_target = (effective_date_str == date.today().strftime('%Y-%m-%d') and day_offset == 0)
    formatted_games_list: List[Dict[str, Any]] = []
    force_static_fetch_for_today = False # Flag to indicate stale live data

    try:
        if is_today_target:
            # Live data for today
            cache_ts_live = datetime.now().replace(second=0, microsecond=0).isoformat() # Minute-level timestamp
            live_cache_key = "live_scoreboard_data"

            raw_live_data: Dict[str, Any]
            if bypass_cache:
                logger.info("Bypassing cache, fetching fresh live scoreboard data.")
                live_board = LiveScoreBoard(timeout=settings.DEFAULT_TIMEOUT_SECONDS) # Changed
                raw_live_data = live_board.get_dict()
            else:
                raw_live_data = get_cached_live_scoreboard_data(cache_key=live_cache_key, timestamp=cache_ts_live)

            # Check if live data is stale
            live_api_game_date = raw_live_data.get('scoreboard', {}).get('gameDate')
            actual_current_date = date.today().strftime('%Y-%m-%d')

            if live_api_game_date != actual_current_date:
                logger.warning(f"Live scoreboard API returned stale data for date '{live_api_game_date}' when expecting '{actual_current_date}'. Forcing static fetch for today.")
                force_static_fetch_for_today = True
            else:
                # Process live data if not stale
                scoreboard_data_live = raw_live_data.get('scoreboard', {})
                raw_games_live = scoreboard_data_live.get('games', [])
                for game_item in raw_games_live:
                    home_team_live = game_item.get("homeTeam", {})
                    away_team_live = game_item.get("awayTeam", {})
                    game_status_code = game_item.get("gameStatus", 0) # 1=Sched, 2=In Prog, 3=Final
                    game_status_str = game_item.get("gameStatusText", "Status Unknown")
                    game_clock_live = game_item.get("gameClock")
                    current_period_live = game_item.get("period", 0)

                    if game_status_code == 2: # In Progress
                        if game_clock_live: game_status_str = f"Q{current_period_live} {game_clock_live}"
                        elif game_status_str != "Halftime": game_status_str = f"Q{current_period_live} In Progress"

                    formatted_games_list.append({
                        "gameId": game_item.get("gameId"), "gameStatus": game_status_code,
                        "gameStatusText": game_status_str, "period": current_period_live,
                        "gameClock": game_clock_live,
                        "homeTeam": {"teamId": home_team_live.get("teamId"), "teamTricode": home_team_live.get("teamTricode", "N/A"), "score": home_team_live.get("score", 0), "wins": home_team_live.get("wins"), "losses": home_team_live.get("losses")},
                        "awayTeam": {"teamId": away_team_live.get("teamId"), "teamTricode": away_team_live.get("teamTricode", "N/A"), "score": away_team_live.get("score", 0), "wins": away_team_live.get("wins"), "losses": away_team_live.get("losses")},
                        "gameEt": game_item.get("gameTimeUTC", "") # Live endpoint provides UTC
                    })
                logger.info(f"Processed {len(formatted_games_list)} games from live scoreboard data for {effective_date_str}.")

        if not is_today_target or force_static_fetch_for_today:
            date_for_static_fetch = actual_current_date if force_static_fetch_for_today else effective_date_str
            if force_static_fetch_for_today:
                 logger.info(f"Using static fetch for actual current date: {date_for_static_fetch} due to stale live feed.")

            cache_ts_static = datetime.now().replace(minute=0, second=0, microsecond=0).isoformat()
            static_cache_key = ("static_scoreboard_data", date_for_static_fetch, league_id, day_offset) # Use date_for_static_fetch
            api_params_static = {"game_date": date_for_static_fetch, "league_id": league_id, "day_offset": day_offset} # Use date_for_static_fetch

            processed_static_data: Dict[str, List[Dict[str, Any]]]
            if bypass_cache or force_static_fetch_for_today:
                logger.info(f"Fetching fresh static scoreboard data for {date_for_static_fetch} (Bypass: {bypass_cache}, StaleLive: {force_static_fetch_for_today}).")

                def fetch_static_scoreboard():
                    # Use a slightly longer timeout for this specific potentially problematic call
                    endpoint = scoreboardv2.ScoreboardV2(**api_params_static, timeout=settings.DEFAULT_TIMEOUT_SECONDS + 15) # Increased timeout to 45s
                    return endpoint

                try:
                    static_endpoint_instance = retry_on_timeout(fetch_static_scoreboard)
                    game_header_list = _process_dataframe(static_endpoint_instance.game_header.get_data_frame(), single_row=False)
                    line_score_list = _process_dataframe(static_endpoint_instance.line_score.get_data_frame(), single_row=False)
                    processed_static_data = {"game_header": game_header_list or [], "line_score": line_score_list or []}
                except (ReadTimeout, ConnectionError) as e: # Catch errors from retry_on_timeout if all retries fail
                    logger.error(f"Failed to fetch static scoreboard for {date_for_static_fetch} after retries: {e}", exc_info=True)
                    error_response = format_response(error=Errors.NBA_API_TIMEOUT.format(endpoint_name=f"ScoreboardV2 for {date_for_static_fetch}", details=str(e)))
                    if return_dataframe:
                        return error_response, {}
                    return error_response
                except Exception as e: # Catch other unexpected errors
                    logger.error(f"Unexpected error fetching/processing static scoreboard for {date_for_static_fetch}: {e}", exc_info=True)
                    error_response = format_response(error=Errors.NBA_API_GENERAL_ERROR.format(endpoint_name=f"ScoreboardV2 for {date_for_static_fetch}", details=str(e)))
                    if return_dataframe:
                        return error_response, {}
                    return error_response

            else:
                # This is the cached path
                processed_static_data = get_cached_static_scoreboard_data(cache_key=static_cache_key, timestamp=cache_ts_static, **api_params_static)

            game_headers_map = {
                gh['GAME_ID']: gh
                for gh in processed_static_data.get("game_header", [])
                if gh and 'GAME_ID' in gh and gh['GAME_ID'] is not None
            }
            line_scores_by_game_map: Dict[str, Dict[str, Any]] = {}

            for ls_item in processed_static_data.get("line_score", []):
                game_id_static = ls_item.get('GAME_ID')
                team_id_static = ls_item.get('TEAM_ID')
                header_static = game_headers_map.get(game_id_static)
                if not game_id_static or not team_id_static or not header_static: continue
                if game_id_static not in line_scores_by_game_map: line_scores_by_game_map[game_id_static] = {}

                team_key_static = 'homeTeam' if team_id_static == header_static.get('HOME_TEAM_ID') else 'awayTeam'
                wins_static, losses_static = None, None
                wl_record_static = ls_item.get('TEAM_WINS_LOSSES')
                if wl_record_static and '-' in wl_record_static:
                    try: wins_static, losses_static = map(int, wl_record_static.split('-'))
                    except (ValueError, IndexError): pass

                line_scores_by_game_map[game_id_static][team_key_static] = {
                    "teamId": team_id_static, "teamTricode": ls_item.get('TEAM_ABBREVIATION'),
                    "score": ls_item.get('PTS'), "wins": wins_static, "losses": losses_static
                }

            for game_id_hdr, header_item in game_headers_map.items():
                game_line_scores_static = line_scores_by_game_map.get(game_id_hdr, {})
                home_team_data_static = game_line_scores_static.get('homeTeam')
                away_team_data_static = game_line_scores_static.get('awayTeam')
                if home_team_data_static and away_team_data_static:
                    formatted_games_list.append({
                        "gameId": game_id_hdr, "gameStatus": header_item.get('GAME_STATUS_ID'),
                        "gameStatusText": header_item.get('GAME_STATUS_TEXT'),
                        "period": header_item.get('LIVE_PERIOD'), "gameClock": header_item.get('LIVE_PC_TIME'),
                        "homeTeam": home_team_data_static, "awayTeam": away_team_data_static,
                        "gameEt": header_item.get('GAME_DATE_EST') # ScoreboardV2 provides EST
                    })
                else:
                    logger.warning(f"Missing home/away team line score data for game {game_id_hdr} in ScoreboardV2 response for {effective_date_str}.")
            logger.info(f"Processed {len(formatted_games_list)} games from static scoreboard data for {effective_date_str}.")

        final_result = {"gameDate": effective_date_str, "games": formatted_games_list}

        # If DataFrame output is requested, create and save DataFrames
        if return_dataframe:
            # Create a DataFrame for the games
            games_df = pd.DataFrame(formatted_games_list)

            # Create separate DataFrames for home and away teams
            home_teams_data = []
            away_teams_data = []

            for game in formatted_games_list:
                game_id = game.get("gameId")

                # Extract home team data
                home_team = game.get("homeTeam", {})
                if home_team:
                    home_team_data = {
                        "gameId": game_id,
                        "teamId": home_team.get("teamId"),
                        "teamTricode": home_team.get("teamTricode"),
                        "score": home_team.get("score"),
                        "wins": home_team.get("wins"),
                        "losses": home_team.get("losses"),
                        "isHome": True
                    }
                    home_teams_data.append(home_team_data)

                # Extract away team data
                away_team = game.get("awayTeam", {})
                if away_team:
                    away_team_data = {
                        "gameId": game_id,
                        "teamId": away_team.get("teamId"),
                        "teamTricode": away_team.get("teamTricode"),
                        "score": away_team.get("score"),
                        "wins": away_team.get("wins"),
                        "losses": away_team.get("losses"),
                        "isHome": False
                    }
                    away_teams_data.append(away_team_data)

            # Combine home and away teams into a single DataFrame
            teams_df = pd.DataFrame(home_teams_data + away_teams_data)

            # Save DataFrames to CSV
            clean_date = effective_date_str.replace("-", "_")
            games_csv_path = get_cache_file_path(f"scoreboard_games_{clean_date}.csv", "scoreboard")
            teams_csv_path = get_cache_file_path(f"scoreboard_teams_{clean_date}.csv", "scoreboard")

            if not games_df.empty:
                games_df.to_csv(games_csv_path, index=False)

            if not teams_df.empty:
                teams_df.to_csv(teams_csv_path, index=False)

            # Add DataFrame metadata to the response
            games_relative_path = get_relative_cache_path(os.path.basename(games_csv_path), "scoreboard")
            teams_relative_path = get_relative_cache_path(os.path.basename(teams_csv_path), "scoreboard")

            final_result["dataframe_info"] = {
                "message": "Scoreboard data has been converted to DataFrames and saved as CSV files",
                "dataframes": {}
            }

            if not games_df.empty:
                final_result["dataframe_info"]["dataframes"]["games"] = {
                    "shape": list(games_df.shape),
                    "columns": games_df.columns.tolist(),
                    "csv_path": games_relative_path
                }

            if not teams_df.empty:
                final_result["dataframe_info"]["dataframes"]["teams"] = {
                    "shape": list(teams_df.shape),
                    "columns": teams_df.columns.tolist(),
                    "csv_path": teams_relative_path
                }

            # Return the JSON response and DataFrames
            dataframes = {
                "games": games_df,
                "teams": teams_df
            }

            return format_response(final_result), dataframes

        # Return just the JSON response if DataFrames are not requested
        return format_response(final_result)

    except ReadTimeout as e:
        logger.error(f"Global ReadTimeout in fetch_scoreboard_data_logic for {effective_date_str}: {e}", exc_info=True)
        error_response = format_response(error=Errors.NBA_API_TIMEOUT.format(endpoint_name=f"Scoreboard for {effective_date_str}", details=str(e)))
        if return_dataframe:
            return error_response, {}
        return error_response
    except ConnectionError as e:
        logger.error(f"Global ConnectionError in fetch_scoreboard_data_logic for {effective_date_str}: {e}", exc_info=True)
        error_response = format_response(error=Errors.NBA_API_CONNECTION_ERROR.format(endpoint_name=f"Scoreboard for {effective_date_str}", details=str(e)))
        if return_dataframe:
            return error_response, {}
        return error_response
    except Exception as e:
        logger.error(f"Unexpected error fetching/formatting scoreboard data for {effective_date_str}: {e}", exc_info=True)
        # Ensure a generic error is returned to the client
        error_response = format_response(error=Errors.UNEXPECTED_ERROR_SCOREBOARD.format(date=effective_date_str, error_details=str(e)))
        if return_dataframe:
            return error_response, {}
        return error_response
import logging
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import date, datetime # Removed timedelta as it's not used directly here
from functools import lru_cache

from nba_api.live.nba.endpoints import ScoreBoard as LiveScoreBoard
from nba_api.stats.endpoints import scoreboardv2
from nba_api.stats.library.parameters import LeagueID # LeagueID is used for static scoreboard

from backend.config import DEFAULT_TIMEOUT, Errors
from backend.api_tools.utils import format_response, _process_dataframe, validate_date_format

logger = logging.getLogger(__name__)

# CACHE_TTL constants are descriptive but not directly used by lru_cache for time expiry.
# The timestamp trick in the cached functions handles hourly/minutely invalidation.
CACHE_TTL_SECONDS_LIVE = 60
CACHE_TTL_SECONDS_STATIC = 3600 * 6

@lru_cache(maxsize=2) # Cache only the latest live data (for the current minute)
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
        board = LiveScoreBoard(timeout=DEFAULT_TIMEOUT) # Live endpoint might not always respect timeout
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
        scoreboard_endpoint = scoreboardv2.ScoreboardV2(**kwargs, timeout=DEFAULT_TIMEOUT)
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

@lru_cache(maxsize=32)
def fetch_scoreboard_data_logic(game_date: Optional[str] = None, league_id: str = LeagueID.nba, day_offset: int = 0, bypass_cache: bool = False) -> str:
    """
    Fetches NBA scoreboard data for a specific date.
    Uses the live NBA API endpoint for the current date and the static ScoreboardV2 endpoint
    for past or future dates. Data is cached to minimize API calls.

    Args:
        game_date (str, optional): The date for the scoreboard in YYYY-MM-DD format.
                                   Defaults to the current local date if None.
        league_id (str, optional): The league ID. Valid values from `LeagueID` (e.g., "00" for NBA).
                                   Defaults to "00" (NBA). This primarily applies to the static ScoreboardV2.
        day_offset (int, optional): Day offset from `game_date` if `game_date` is also provided.
                                    This primarily applies to the static ScoreboardV2. Defaults to 0.
        bypass_cache (bool, optional): If True, ignores cached data and fetches fresh data. Defaults to False.

    Returns:
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
    """
    effective_date_str = game_date if game_date is not None else date.today().strftime('%Y-%m-%d')
    # Explicitly log the date being used, especially when game_date is None
    if game_date is None:
        logger.info(f"fetch_scoreboard_data_logic: game_date is None, defaulting to effective_date_str (today's date): {effective_date_str}")
    
    logger.info(f"Executing fetch_scoreboard_data_logic for Date: {effective_date_str}, League: {league_id}, Offset: {day_offset}, BypassCache: {bypass_cache}")

    if not validate_date_format(effective_date_str):
        logger.error(f"Invalid date format provided: {effective_date_str}. Use YYYY-MM-DD.")
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=effective_date_str))

    VALID_LEAGUE_IDS = {getattr(LeagueID, lid) for lid in dir(LeagueID) if not lid.startswith('_') and isinstance(getattr(LeagueID, lid), str)}
    if league_id not in VALID_LEAGUE_IDS:
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(VALID_LEAGUE_IDS)))

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
                live_board = LiveScoreBoard(timeout=DEFAULT_TIMEOUT)
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
        
        if not is_today_target or force_static_fetch_for_today: # Modified condition
            # Static data for past/future dates, OR if live data was stale for today
            
            # If live was stale, ensure we use actual_current_date for the static fetch
            date_for_static_fetch = actual_current_date if force_static_fetch_for_today else effective_date_str
            if force_static_fetch_for_today:
                 logger.info(f"Using static fetch for actual current date: {date_for_static_fetch} due to stale live feed.")
            
            cache_ts_static = datetime.now().replace(minute=0, second=0, microsecond=0).isoformat()
            static_cache_key = ("static_scoreboard_data", date_for_static_fetch, league_id, day_offset) # Use date_for_static_fetch
            api_params_static = {"game_date": date_for_static_fetch, "league_id": league_id, "day_offset": day_offset} # Use date_for_static_fetch
            
            processed_static_data: Dict[str, List[Dict[str, Any]]]
            # If bypassing cache OR if live was stale (we want fresh static for today)
            if bypass_cache or force_static_fetch_for_today:
                logger.info(f"Fetching fresh static scoreboard data for {date_for_static_fetch} (Bypass: {bypass_cache}, StaleLive: {force_static_fetch_for_today}).")
                static_endpoint = scoreboardv2.ScoreboardV2(**api_params_static, timeout=DEFAULT_TIMEOUT)
                game_header_list = _process_dataframe(static_endpoint.game_header.get_data_frame(), single_row=False)
                line_score_list = _process_dataframe(static_endpoint.line_score.get_data_frame(), single_row=False)
                processed_static_data = {"game_header": game_header_list or [], "line_score": line_score_list or []}
            else:
                processed_static_data = get_cached_static_scoreboard_data(cache_key=static_cache_key, timestamp=cache_ts_static, **api_params_static)

            game_headers_map = {gh['GAME_ID']: gh for gh in processed_static_data.get("game_header", [])}
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
        return format_response(final_result)

    except Exception as e:
        logger.error(f"Error fetching/formatting scoreboard data for {effective_date_str}: {str(e)}", exc_info=True)
        error_msg = Errors.LEAGUE_SCOREBOARD_UNEXPECTED.format(game_date=effective_date_str, error=str(e))
        return format_response(error=error_msg)
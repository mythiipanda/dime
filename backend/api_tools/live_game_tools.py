from typing import Dict, List, Optional, TypedDict, Any
from nba_api.live.nba.endpoints import scoreboard
from datetime import datetime
import logging
from functools import lru_cache

from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import format_response

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 10 # Keep short TTL for live data, but lru_cache might invalidate less frequently based on timestamp

# --- TypedDicts (Keep for documentation) ---
class GameLeader(TypedDict):
    name: str
    stats: str

class TeamInfo(TypedDict):
    id: int # Changed to int based on typical API usage
    code: str
    name: str
    score: int
    record: str # e.g., "10-5"

class GameStatus(TypedDict):
    clock: Optional[str] # Can be None if not started/finished
    period: int
    state: str # e.g., "Halftime", "Q1", "Final"

class GameInfo(TypedDict):
    game_id: str
    start_time: str # ISO format UTC
    status: GameStatus
    home_team: TeamInfo
    away_team: TeamInfo
    # leaders: Dict[str, GameLeader] # Leaders might not be consistently available or needed for frontend

class ScoreboardResponse(TypedDict):
    meta: Dict[str, Any] # Keep meta if needed
    date: str
    games: List[GameInfo]

# --- Caching Function ---
@lru_cache(maxsize=2) # Cache only the latest scoreboard
def get_cached_scoreboard_data(
    cache_key: str, # Simple string key, e.g., "live_scoreboard"
    timestamp: str    # Timestamp for TTL invalidation
) -> Dict[str, Any]: # Return the raw dictionary
    """
    Cached wrapper for fetching live scoreboard data.
    Uses timestamp for time-based cache invalidation (approx 1 hour).
    Returns the raw dictionary result from the API call or raises an exception.
    """
    logger.info(f"Cache miss or expiry for live scoreboard - fetching new data")
    try:
        board = scoreboard.ScoreBoard(timeout=settings.DEFAULT_TIMEOUT_SECONDS) # Changed
        # Return the raw dictionary, processing happens in main logic
        return board.get_dict()
    except Exception as e:
        logger.error(f"ScoreBoard API call failed: {e}", exc_info=True)
        raise e # Re-raise to be handled by the main logic function

# --- Main Logic Function ---
def fetch_league_scoreboard_logic(bypass_cache: bool = False) -> str: # Return JSON string
    """
    Fetches live scoreboard data for current NBA games and formats it using nba_api's live ScoreBoard endpoint.

    Args:
        bypass_cache (bool): If True, ignores cached data and fetches fresh data. Defaults to False.

    Returns:
        str: JSON-formatted string containing current game information or an error message.
            Structure includes 'gameDate' and a 'games' list, where each game contains IDs, status, teams, scores, and start time.

    Notes:
        - Uses a short TTL cache for live data, but can be bypassed for real-time updates.
        - Returns an error if the API call fails or data cannot be processed.
        - Each game includes home/away team info, scores, status, and clock/period if live.
    """
    logger.info("Executing fetch_league_scoreboard_logic to fetch and format live data")

    cache_key = "live_scoreboard"
    # Create timestamp buckets based on CACHE_TTL_SECONDS for more frequent invalidation
    cache_timestamp = str(int(datetime.now().timestamp() // CACHE_TTL_SECONDS))

    try:
        if bypass_cache:
            logger.info("Bypassing cache, fetching fresh scoreboard data.")
            board = scoreboard.ScoreBoard(timeout=settings.DEFAULT_TIMEOUT_SECONDS) # Changed
            raw_data = board.get_dict()
        else:
            raw_data = get_cached_scoreboard_data(cache_key=cache_key, timestamp=cache_timestamp)

        scoreboard_outer = raw_data.get('scoreboard', {})
        raw_games = scoreboard_outer.get('games', [])
        game_date = scoreboard_outer.get('gameDate', datetime.now().strftime("%Y-%m-%d"))

        formatted_games: List[Dict[str, Any]] = []
        for game in raw_games:
            home_team = game.get("homeTeam", {})
            away_team = game.get("awayTeam", {})

            # Determine game status text and state more robustly
            game_status_text = game.get("gameStatusText", "Status Unknown")
            game_status_code = game.get("gameStatus", 0) # 1: Scheduled, 2: In Progress, 3: Final

            # Format game clock and period only if game is live
            game_clock = None
            current_period = 0
            if game_status_code == 2: # In Progress
                game_clock = game.get("gameClock")
                current_period = game.get("period", 0)
                # Refine status text for live games
                if game_clock:
                    game_status_text = f"Q{current_period} {game_clock}"
                elif game_status_text == "Halftime":
                     pass # Keep Halftime text
                else: # Default live status if clock missing
                     game_status_text = f"Q{current_period} In Progress"


            formatted_game = {
                "gameId": game.get("gameId"),
                "gameStatus": game_status_code,
                "gameStatusText": game_status_text,
                "period": current_period,
                "gameClock": game_clock,
                "homeTeam": {
                    "teamId": home_team.get("teamId"),
                    "teamTricode": home_team.get("teamTricode", "N/A"),
                    "score": home_team.get("score", 0),
                    "wins": home_team.get("wins"), # Include wins/losses if available
                    "losses": home_team.get("losses")
                },
                "awayTeam": {
                    "teamId": away_team.get("teamId"),
                    "teamTricode": away_team.get("teamTricode", "N/A"),
                    "score": away_team.get("score", 0),
                    "wins": away_team.get("wins"),
                    "losses": away_team.get("losses")
                },
                "gameEt": game.get("gameTimeUTC", "") # Game start time UTC
            }
            formatted_games.append(formatted_game)

        result: Dict[str, Any] = {
            "gameDate": game_date,
            "games": formatted_games
        }

        logger.info(f"fetch_league_scoreboard_logic formatted {len(formatted_games)} games")
        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching/formatting scoreboard data: {str(e)}", exc_info=True)
        error_msg = Errors.LEAGUE_SCOREBOARD_UNEXPECTED.format(game_date=datetime.now().strftime('%Y-%m-%d'), error=str(e)) if hasattr(Errors, 'LEAGUE_SCOREBOARD_UNEXPECTED') else f"Unexpected error fetching scoreboard: {e}"
        return format_response(error=error_msg)
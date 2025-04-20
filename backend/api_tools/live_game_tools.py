from typing import Dict, List, Optional, TypedDict, Any, Tuple
from nba_api.live.nba.endpoints import scoreboard
from datetime import datetime, timedelta
import json
import logging
from backend.config import DEFAULT_TIMEOUT, Errors

logger = logging.getLogger(__name__)

# In-memory cache for scoreboard data
_scoreboard_cache: Dict[str, Tuple[str, datetime]] = {}
# Cache TTL in seconds (10 seconds for live games)
CACHE_TTL = 10

class GameLeader(TypedDict):
    """Type definition for game leader statistics."""
    name: str
    stats: str

class TeamInfo(TypedDict):
    """Type definition for team information in game response."""
    id: str
    code: str
    name: str
    score: int
    record: str

class GameStatus(TypedDict):
    """Type definition for game status information."""
    clock: str
    period: int
    state: str

class GameInfo(TypedDict):
    """Type definition for individual game information."""
    game_id: str
    start_time: str
    status: GameStatus
    home_team: TeamInfo
    away_team: TeamInfo
    leaders: Dict[str, GameLeader]

class ScoreboardResponse(TypedDict):
    """Type definition for the scoreboard response."""
    meta: Dict[str, str]
    date: str
    games: List[GameInfo]

def _format_game_leader(leader_data: Dict) -> GameLeader:
    """
    Helper function to format game leader data.
    
    Args:
        leader_data: Raw leader statistics from the API
        
    Returns:
        GameLeader: Formatted leader information
    """
    return {
        "name": leader_data.get("name", ""),
        "stats": f"{leader_data.get('points', 0)} PTS, {leader_data.get('rebounds', 0)} REB, {leader_data.get('assists', 0)} AST"
    }

def fetch_league_scoreboard_logic(bypass_cache: bool = False) -> str:
    """
    Fetches live scoreboard data for current NBA games and formats it 
    to match the frontend's ScoreboardData interface.
    
    Returns:
        str: JSON string containing current game information matching the frontend structure.
        {
            "gameDate": "YYYY-MM-DD",
            "games": [
                {
                    "gameId": str,
                    "gameStatus": int,      // 1 = Scheduled, 2 = In Progress, 3 = Final
                    "gameStatusText": str,  // e.g., "Q1 0:35.3", "Final", "7:00 PM ET"
                    "period": int,         // Current period (if live)
                    "gameClock": str,      // Current clock (if live)
                    "homeTeam": {
                        "teamId": int,
                        "teamTricode": str,
                        "score": int,
                        "wins": int,      // Optional
                        "losses": int     // Optional
                    },
                    "awayTeam": {
                        "teamId": int,
                        "teamTricode": str,
                        "score": int,
                        "wins": int,      // Optional
                        "losses": int     // Optional
                    },
                    "gameEt": str          // Game start time (ISO format or similar)
                }
            ]
        }
        
    Raises:
        Catches exceptions and returns an error JSON string.
    """
    logger.info("Executing fetch_league_scoreboard_logic to fetch and format for frontend")
    
    # Check cache first
    current_date = datetime.now().strftime("%Y-%m-%d")
    if not bypass_cache and current_date in _scoreboard_cache:
        cached_data, cache_time = _scoreboard_cache[current_date]
        # Only use cache if within TTL
        if datetime.now() - cache_time < timedelta(seconds=CACHE_TTL):
            logger.info("Returning cached scoreboard data")
            return cached_data
    
    try:
        board = scoreboard.ScoreBoard(timeout=DEFAULT_TIMEOUT)
        raw_data = board.get_dict()
        
        scoreboard_outer = raw_data.get('scoreboard', {})
        raw_games = scoreboard_outer.get('games', [])
        game_date = scoreboard_outer.get('gameDate', datetime.now().strftime("%Y-%m-%d"))
        
        formatted_games: List[Dict[str, Any]] = []
        for game in raw_games:
            # Only extract homeTeam and awayTeam once
            home_team = game.get("homeTeam", {})
            away_team = game.get("awayTeam", {})
            
            # Get game status fields only if game is live
            is_live = game.get("gameStatus", 0) == 2
            game_status_fields = {
                "period": game.get("period"),
                "gameClock": game.get("gameClock")
            } if is_live else {
                "period": None,
                "gameClock": None
            }
            
            formatted_game = {
                "gameId": game.get("gameId"),
                "gameStatus": game.get("gameStatus", 0),
                "gameStatusText": game.get("gameStatusText", ""),
                **game_status_fields,
                "homeTeam": {
                    "teamId": home_team.get("teamId"),
                    "teamTricode": home_team.get("teamTricode", "N/A"),
                    "score": home_team.get("score", 0)
                    # Only include record for completed games
                } | ({
                    "wins": home_team.get("wins"),
                    "losses": home_team.get("losses")
                } if game.get("gameStatus", 0) == 3 else {}),
                "awayTeam": {
                    "teamId": away_team.get("teamId"),
                    "teamTricode": away_team.get("teamTricode", "N/A"),
                    "score": away_team.get("score", 0)
                    # Only include record for completed games
                } | ({
                    "wins": away_team.get("wins"),
                    "losses": away_team.get("losses")
                } if game.get("gameStatus", 0) == 3 else {}),
                "gameEt": game.get("gameTimeUTC", "")
            }
            formatted_games.append(formatted_game)
        
        # Create final structure matching ScoreboardData
        result: Dict[str, Any] = {
            "gameDate": game_date,
            "games": formatted_games
        }
        
        logger.info(f"fetch_league_scoreboard_logic formatted {len(formatted_games)} games for frontend")
        # Format result as JSON string
        json_result = json.dumps(result)
        
        # Update cache
        _scoreboard_cache[current_date] = (json_result, datetime.now())
        
        return json_result
        
    except Exception as e:
        logger.error(f"Error fetching/formatting scoreboard data: {str(e)}", exc_info=True)
        # Simplified error result - no need to include empty games array
        return json.dumps({
            "error": Errors.SCOREBOARD_API.format(error=str(e))
        })
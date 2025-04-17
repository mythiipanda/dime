from typing import Dict, List, Optional, TypedDict, Any
from nba_api.live.nba.endpoints import scoreboard
from datetime import datetime
import json
import logging
from config import DEFAULT_TIMEOUT, Errors

logger = logging.getLogger(__name__)

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

def fetch_league_scoreboard_logic() -> str:
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
    
    try:
        board = scoreboard.ScoreBoard()
        raw_data = board.get_dict()
        
        scoreboard_outer = raw_data.get('scoreboard', {})
        raw_games = scoreboard_outer.get('games', [])
        game_date = scoreboard_outer.get('gameDate', datetime.now().strftime("%Y-%m-%d"))
        
        formatted_games: List[Dict[str, Any]] = []
        for game in raw_games:
            home_team_raw = game.get("homeTeam", {})
            away_team_raw = game.get("awayTeam", {})
            
            # Transform raw game data to match frontend Game interface
            formatted_game = {
                "gameId": game.get("gameId"),
                "gameStatus": game.get("gameStatus", 0), # Default to 0 if missing?
                "gameStatusText": game.get("gameStatusText", ""),
                "period": game.get("period"), # Will be None if not applicable
                "gameClock": game.get("gameClock"), # Will be None if not applicable
                "homeTeam": {
                    "teamId": home_team_raw.get("teamId"),
                    "teamTricode": home_team_raw.get("teamTricode", "N/A"),
                    "score": home_team_raw.get("score", 0),
                    "wins": home_team_raw.get("wins"),
                    "losses": home_team_raw.get("losses")
                },
                "awayTeam": {
                    "teamId": away_team_raw.get("teamId"),
                    "teamTricode": away_team_raw.get("teamTricode", "N/A"),
                    "score": away_team_raw.get("score", 0),
                    "wins": away_team_raw.get("wins"),
                    "losses": away_team_raw.get("losses")
                },
                 # Use gameTimeUTC as gameEt, ensure it exists
                "gameEt": game.get("gameTimeUTC", "")
            }
            formatted_games.append(formatted_game)
        
        # Create final structure matching ScoreboardData
        result: Dict[str, Any] = {
            "gameDate": game_date,
            "games": formatted_games
        }
        
        logger.info(f"fetch_league_scoreboard_logic formatted {len(formatted_games)} games for frontend")
        # Return as a JSON string
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"Error fetching/formatting scoreboard data: {str(e)}", exc_info=True)
        # Return an error structure (could be simpler)
        error_result = {
            "gameDate": datetime.now().strftime("%Y-%m-%d"),
            "games": [],
            "error": Errors.SCOREBOARD_API.format(error=str(e))
        }
        return json.dumps(error_result)
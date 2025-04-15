from typing import Dict, List, Optional, TypedDict
from nba_api.live.nba.endpoints import scoreboard
from datetime import datetime
import json
import logging
from config import DEFAULT_TIMEOUT

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
    Fetches live scoreboard data for current NBA games.
    
    Returns:
        str: JSON string containing current game information in a structured format:
        {
            "meta": {
                "version": int,
                "timestamp": str,
                "code": int,
                "request_url": str
            },
            "date": str,
            "games": [
                {
                    "game_id": str,
                    "start_time": str,
                    "status": {
                        "clock": str,
                        "period": int,
                        "state": str
                    },
                    "home_team": {
                        "id": str,
                        "code": str,
                        "name": str,
                        "score": int,
                        "record": str
                    },
                    "away_team": {
                        "id": str,
                        "code": str,
                        "name": str,
                        "score": int,
                        "record": str
                    },
                    "leaders": {
                        "home": {
                            "name": str,
                            "stats": str
                        },
                        "away": {
                            "name": str,
                            "stats": str
                        }
                    }
                }
            ]
        }
        
    Raises:
        Any exceptions are caught and returned as error JSON responses
    """
    logger.info("Executing fetch_league_scoreboard_logic")
    
    try:
        # Get the scoreboard data
        board = scoreboard.ScoreBoard()
        raw_data = board.get_dict()
        
        # Validate API response
        if raw_data.get('meta', {}).get('code') != 200:
            error_msg = f"API returned non-200 status: {raw_data.get('meta', {}).get('code')}"
            logger.error(error_msg)
            return json.dumps({
                "error": error_msg,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "games": []
            })
        
        # Extract games data in a compact format
        games_data: List[GameInfo] = []
        if raw_data.get('scoreboard', {}).get('games'):
            for game in raw_data['scoreboard']['games']:
                # Create a more focused game object
                game_info: GameInfo = {
                    "game_id": game.get("gameId"),
                    "start_time": game.get("gameTimeUTC", ""),
                    "status": {
                        "clock": game.get("gameClock", ""),
                        "period": game.get("period", 0),
                        "state": game.get("gameStatusText", "")
                    },
                    "home_team": {
                        "id": game.get("homeTeam", {}).get("teamId", ""),
                        "code": game.get("homeTeam", {}).get("teamTricode", ""),
                        "name": f"{game.get('homeTeam', {}).get('teamCity', '')} {game.get('homeTeam', {}).get('teamName', '')}",
                        "score": game.get("homeTeam", {}).get("score", 0),
                        "record": f"{game.get('homeTeam', {}).get('wins', 0)}-{game.get('homeTeam', {}).get('losses', 0)}"
                    },
                    "away_team": {
                        "id": game.get("awayTeam", {}).get("teamId", ""),
                        "code": game.get("awayTeam", {}).get("teamTricode", ""),
                        "name": f"{game.get('awayTeam', {}).get('teamCity', '')} {game.get('awayTeam', {}).get('teamName', '')}",
                        "score": game.get("awayTeam", {}).get("score", 0),
                        "record": f"{game.get('awayTeam', {}).get('wins', 0)}-{game.get('awayTeam', {}).get('losses', 0)}"
                    },
                    "leaders": {
                        "home": _format_game_leader(game.get("gameLeaders", {}).get("homeLeaders", {})),
                        "away": _format_game_leader(game.get("gameLeaders", {}).get("awayLeaders", {}))
                    }
                }
                games_data.append(game_info)
        
        result: ScoreboardResponse = {
            "meta": {
                "version": raw_data['meta']['version'],
                "timestamp": raw_data['meta']['time'],
                "code": raw_data['meta']['code'],
                "request_url": raw_data['meta']['request']
            },
            "date": raw_data['scoreboard']['gameDate'],
            "games": games_data
        }
        
        logger.info(f"fetch_league_scoreboard_logic completed with {len(games_data)} games")
        return json.dumps(result, default=str)
        
    except Exception as e:
        logger.error(f"Error fetching scoreboard data: {str(e)}", exc_info=True)
        error_result = {
            "meta": {
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "date": datetime.now().strftime("%Y-%m-%d"),
            "games": []
        }
        return json.dumps(error_result, default=str)
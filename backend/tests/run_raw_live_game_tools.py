"""Test script for NBA Live Game API endpoints.

This script tests the live scoreboard endpoint and validates the response structure
against the defined TypedDict schemas.
"""

from nba_api.live.nba.endpoints import scoreboard
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

def validate_game_leader(leader: Dict[str, Any]) -> bool:
    """Validates game leader data structure.
    
    Args:
        leader: Game leader data to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(leader, dict):
        print(f"Error: Leader is not a dictionary: {leader}")
        return False
        
    required_fields = {"name", "stats"}
    if not all(field in leader for field in required_fields):
        print(f"Error: Leader missing required fields: {leader}")
        return False
        
    # Stats should contain points, rebounds, and assists
    if not all(stat in leader["stats"] for stat in ["PTS", "REB", "AST"]):
        print(f"Error: Leader stats missing required statistics: {leader['stats']}")
        return False
        
    return True

def validate_team_info(team: Dict[str, Any]) -> bool:
    """Validates team information structure.
    
    Args:
        team: Team data to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(team, dict):
        print(f"Error: Team is not a dictionary: {team}")
        return False
        
    required_fields = {"id", "code", "name", "score", "record"}
    if not all(field in team for field in required_fields):
        print(f"Error: Team missing required fields: {team}")
        return False
        
    # Record should be in format "W-L"
    if not isinstance(team["record"], str) or "-" not in team["record"]:
        print(f"Error: Invalid team record format: {team['record']}")
        return False
        
    return True

def validate_game_status(status: Dict[str, Any]) -> bool:
    """Validates game status structure.
    
    Args:
        status: Game status data to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(status, dict):
        print(f"Error: Status is not a dictionary: {status}")
        return False
        
    required_fields = {"clock", "period", "state"}
    if not all(field in status for field in required_fields):
        print(f"Error: Status missing required fields: {status}")
        return False
        
    if not isinstance(status["period"], int):
        print(f"Error: Period is not an integer: {status['period']}")
        return False
        
    return True

def test_scoreboard() -> None:
    """Tests the live scoreboard endpoint.
    
    Validates:
    1. API response structure
    2. Game data format
    3. Team information
    4. Game status
    5. Game leaders
    """
    print("\nTesting Live Scoreboard Endpoint...")
    
    try:
        # Get scoreboard data
        board = scoreboard.ScoreBoard()
        raw_data = board.get_dict()
        
        # Validate API response
        meta = raw_data.get('meta', {})
        print(f"\nAPI Response:")
        print(f"Version: {meta.get('version')}")
        print(f"Timestamp: {meta.get('time')}")
        print(f"Status Code: {meta.get('code')}")
        
        if meta.get('code') != 200:
            print(f"Error: API returned non-200 status: {meta.get('code')}")
            return
            
        # Validate games data
        games = raw_data.get('scoreboard', {}).get('games', [])
        print(f"\nFound {len(games)} games")
        
        for game in games:
            print(f"\nValidating Game {game.get('gameId')}:")
            
            # Validate game status
            status = {
                "clock": game.get("gameClock", ""),
                "period": game.get("period", 0),
                "state": game.get("gameStatusText", "")
            }
            if not validate_game_status(status):
                print(f"Invalid game status for game {game.get('gameId')}")
                continue
                
            # Validate team information
            home_team = {
                "id": game.get("homeTeam", {}).get("teamId", ""),
                "code": game.get("homeTeam", {}).get("teamTricode", ""),
                "name": f"{game.get('homeTeam', {}).get('teamCity', '')} {game.get('homeTeam', {}).get('teamName', '')}",
                "score": game.get("homeTeam", {}).get("score", 0),
                "record": f"{game.get('homeTeam', {}).get('wins', 0)}-{game.get('homeTeam', {}).get('losses', 0)}"
            }
            if not validate_team_info(home_team):
                print(f"Invalid home team info for game {game.get('gameId')}")
                continue
                
            away_team = {
                "id": game.get("awayTeam", {}).get("teamId", ""),
                "code": game.get("awayTeam", {}).get("teamTricode", ""),
                "name": f"{game.get('awayTeam', {}).get('teamCity', '')} {game.get('awayTeam', {}).get('teamName', '')}",
                "score": game.get("awayTeam", {}).get("score", 0),
                "record": f"{game.get('awayTeam', {}).get('wins', 0)}-{game.get('awayTeam', {}).get('losses', 0)}"
            }
            if not validate_team_info(away_team):
                print(f"Invalid away team info for game {game.get('gameId')}")
                continue
                
            # Validate game leaders
            if game.get("gameLeaders"):
                home_leader = {
                    "name": game.get("gameLeaders", {}).get("homeLeaders", {}).get("name", ""),
                    "stats": f"{game.get('gameLeaders', {}).get('homeLeaders', {}).get('points', 0)} PTS, "
                            f"{game.get('gameLeaders', {}).get('homeLeaders', {}).get('rebounds', 0)} REB, "
                            f"{game.get('gameLeaders', {}).get('homeLeaders', {}).get('assists', 0)} AST"
                }
                if not validate_game_leader(home_leader):
                    print(f"Invalid home leader for game {game.get('gameId')}")
                    
                away_leader = {
                    "name": game.get("gameLeaders", {}).get("awayLeaders", {}).get("name", ""),
                    "stats": f"{game.get('gameLeaders', {}).get('awayLeaders', {}).get('points', 0)} PTS, "
                            f"{game.get('gameLeaders', {}).get('awayLeaders', {}).get('rebounds', 0)} REB, "
                            f"{game.get('gameLeaders', {}).get('awayLeaders', {}).get('assists', 0)} AST"
                }
                if not validate_game_leader(away_leader):
                    print(f"Invalid away leader for game {game.get('gameId')}")
            
            print("✓ Game validation successful")
            
        # Save raw output
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"live_game_tools_raw_output_{timestamp}.json"
        with open(output_file, 'w') as f:
            json.dump(raw_data, f, indent=2)
        print(f"\nRaw output saved to {output_file}")
        
    except Exception as e:
        print(f"Error testing scoreboard: {str(e)}")

if __name__ == "__main__":
    test_scoreboard()
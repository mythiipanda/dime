import sys
import os
import json
from datetime import datetime
from nba_api.live.nba.endpoints import scoreboard

def test_scoreboard():
    """Test the live scoreboard endpoint"""
    print("\n=== Testing live scoreboard ===\n")

    # Get the scoreboard data
    board = scoreboard.ScoreBoard()
    raw_data = board.get_dict()
    
    print("Endpoint: scoreboard")
    print(f"API Response Status: {raw_data.get('meta', {}).get('code')}")
    print("\nMeta Data:")
    print(f"Version: {raw_data.get('meta', {}).get('version')}")
    print(f"Timestamp: {raw_data.get('meta', {}).get('time')}\n")
    
    # Print game data structure
    if 'scoreboard' in raw_data and 'games' in raw_data['scoreboard']:
        games = raw_data['scoreboard']['games']
        print(f"Number of games: {len(games)}")
        
        if games:
            print("\nExample Game Structure:")
            game = games[0]
            print(f"Game ID: {game.get('gameId')}")
            print(f"Game Status: {game.get('gameStatusText')}")
            print(f"Game Clock: {game.get('gameClock')}")
            print(f"Period: {game.get('period')}\n")
            
            # Print team data structure
            print("Home Team Data Keys:")
            if 'homeTeam' in game:
                print(json.dumps(list(game['homeTeam'].keys()), indent=2))
            
            print("\nAway Team Data Keys:")
            if 'awayTeam' in game:
                print(json.dumps(list(game['awayTeam'].keys()), indent=2))
            
            # Print game leaders if available
            if 'gameLeaders' in game:
                print("\nGame Leaders Structure:")
                print(json.dumps(list(game['gameLeaders'].keys()), indent=2))

    # Save full raw output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"live_game_tools_raw_output_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(raw_data, f, indent=2)
    
    print(f"\nFull raw output saved to {output_file}")

if __name__ == "__main__":
    test_scoreboard()
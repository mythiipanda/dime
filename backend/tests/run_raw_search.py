import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import json
from datetime import datetime
from nba_api.stats.static import players, teams

def test_find_players():
    """Test finding players by name fragment"""
    print("\n=== Testing find players ===\n")
    
    try:
        player_fragment = "LeBron"
        print(f"Searching for players with fragment: '{player_fragment}'")
        player_list = players.find_players_by_full_name(player_fragment)
        
        if player_list:
            print(f"Found {len(player_list)} players.")
            print("\nExample Player Structure:")
            print(json.dumps(player_list[0], indent=2))
        else:
            print("No players found.")

    except Exception as e:
        print(f"Error testing find players: {str(e)}")

def test_get_players():
    """Test getting all players"""
    print("\n=== Testing get all players ===\n")
    
    try:
        all_players = players.get_players()
        print(f"Total players found: {len(all_players)}")
        
        if all_players:
            print("\nExample Player Structure (from get_players):")
            print(json.dumps(all_players[0], indent=2))
        else:
            print("No players returned.")

    except Exception as e:
        print(f"Error testing get players: {str(e)}")

def test_find_teams():
    """Test finding teams by name fragment"""
    print("\n=== Testing find teams ===\n")
    
    try:
        team_fragment = "Lakers"
        print(f"Searching for teams with fragment: '{team_fragment}'")
        team_list = teams.find_teams_by_full_name(team_fragment)

        if team_list:
            print(f"Found {len(team_list)} teams.")
            print("\nExample Team Structure:")
            print(json.dumps(team_list[0], indent=2))
        else:
            print("No teams found.")
    except Exception as e:
        print(f"Error testing find teams: {str(e)}")

def test_get_teams():
    """Test getting all teams"""
    print("\n=== Testing get all teams ===\n")
    
    try:
        all_teams = teams.get_teams()
        print(f"Total teams found: {len(all_teams)}")

        if all_teams:
            print("\nExample Team Structure (from get_teams):")
            print(json.dumps(all_teams[0], indent=2))
        else:
            print("No teams returned.")
    except Exception as e:
        print(f"Error testing get teams: {str(e)}")

if __name__ == "__main__":
    print("Testing Search Tools (static data)...")
    
    test_find_players()
    test_get_players()
    test_find_teams()
    test_get_teams()
"""
Smoke test for the game_finder module.
Tests the functionality of fetching league game data.
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime

# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

from backend.api_tools.game_finder import (
    fetch_league_games_logic
)
from nba_api.stats.library.parameters import (
    LeagueID,
    SeasonTypeAllStar
)

# Sample season for testing
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_TEAM_ID = 1610612747  # Los Angeles Lakers

def test_fetch_league_games_basic():
    """Test fetching league games with default parameters."""
    print("\n=== Testing fetch_league_games_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_league_games_logic(
        player_or_team_abbreviation='T',
        team_id_nullable=SAMPLE_TEAM_ID,
        season_nullable=SAMPLE_SEASON,
        season_type_nullable=SeasonTypeAllStar.regular,
        league_id_nullable=LeagueID.nba
    )
    
    # Parse the JSON response
    data = json.loads(json_response)
    
    # Check if the response has the expected structure
    assert isinstance(data, dict), "Response should be a dictionary"
    
    # Check if there's an error in the response
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        print("Continuing with other tests...")
    else:
        # Check if games exist
        assert "games" in data, "Response should have 'games'"
        
        # Print some information about the data
        games = data["games"]
        print(f"\nNumber of games: {len(games)}")
        
        if games:
            print("\nSample game:")
            first_game = games[0]
            print(f"  GAME_ID: {first_game.get('GAME_ID', 'N/A')}")
            print(f"  GAME_DATE: {first_game.get('GAME_DATE', 'N/A')}")
            print(f"  MATCHUP: {first_game.get('MATCHUP', 'N/A')}")
            print(f"  WL: {first_game.get('WL', 'N/A')}")
    
    print("\n=== Basic game finder test completed ===")
    return data

def test_fetch_league_games_dataframe():
    """Test fetching league games with DataFrame output."""
    print("\n=== Testing fetch_league_games_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_league_games_logic(
        player_or_team_abbreviation='T',
        team_id_nullable=SAMPLE_TEAM_ID,
        season_nullable=SAMPLE_SEASON,
        season_type_nullable=SeasonTypeAllStar.regular,
        league_id_nullable=LeagueID.nba,
        return_dataframe=True
    )
    
    # Check if the result is a tuple
    assert isinstance(result, tuple), "Result should be a tuple when return_dataframe=True"
    assert len(result) == 2, "Result tuple should have 2 elements"
    
    json_response, dataframes = result
    
    # Check if the first element is a JSON string
    assert isinstance(json_response, str), "First element should be a JSON string"
    
    # Check if the second element is a dictionary of DataFrames
    assert isinstance(dataframes, dict), "Second element should be a dictionary of DataFrames"
    
    # Parse the JSON response
    data = json.loads(json_response)
    
    # Print DataFrame info
    print(f"\nDataFrames returned: {list(dataframes.keys())}")
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nDataFrame '{key}' shape: {df.shape}")
            print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns
    
    # Check if the CSV file was created
    if "dataframe_info" in data:
        for df_key, df_info in data["dataframe_info"].get("dataframes", {}).items():
            csv_path = df_info.get("csv_path")
            if csv_path:
                full_path = os.path.join(backend_dir, csv_path)
                if os.path.exists(full_path):
                    print(f"\nCSV file exists: {csv_path}")
                else:
                    print(f"\nCSV file does not exist: {csv_path}")
    
    # Display a sample of the DataFrame if not empty
    if "games" in dataframes and not dataframes["games"].empty:
        print(f"\nSample of games DataFrame (first 3 rows):")
        print(dataframes["games"].head(3))
    
    print("\n=== DataFrame game finder test completed ===")
    return json_response, dataframes

def test_fetch_league_games_player():
    """Test fetching league games for a player."""
    print("\n=== Testing fetch_league_games_logic for a player ===")
    
    # LeBron James player ID
    SAMPLE_PLAYER_ID = 2544
    
    # Test with player parameters
    json_response = fetch_league_games_logic(
        player_or_team_abbreviation='P',
        player_id_nullable=SAMPLE_PLAYER_ID,
        season_nullable=SAMPLE_SEASON,
        season_type_nullable=SeasonTypeAllStar.regular,
        league_id_nullable=LeagueID.nba
    )
    
    # Parse the JSON response
    data = json.loads(json_response)
    
    # Check if the response has the expected structure
    assert isinstance(data, dict), "Response should be a dictionary"
    
    # Check if there's an error in the response
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        print("Continuing with other tests...")
    else:
        # Check if games exist
        assert "games" in data, "Response should have 'games'"
        
        # Print some information about the data
        games = data["games"]
        print(f"\nNumber of games for player: {len(games)}")
        
        if games:
            print("\nSample player game:")
            first_game = games[0]
            print(f"  PLAYER_NAME: {first_game.get('PLAYER_NAME', 'N/A')}")
            print(f"  GAME_ID: {first_game.get('GAME_ID', 'N/A')}")
            print(f"  GAME_DATE: {first_game.get('GAME_DATE', 'N/A')}")
            print(f"  MATCHUP: {first_game.get('MATCHUP', 'N/A')}")
    
    print("\n=== Player game finder test completed ===")
    return data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running game_finder smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_league_games_basic()
        df_json, df_data = test_fetch_league_games_dataframe()
        player_data = test_fetch_league_games_player()
        
        print("\n=== All tests completed successfully ===")
        return True
    except Exception as e:
        print(f"\n!!! Test failed with error: {str(e)} !!!")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

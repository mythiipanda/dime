"""
Smoke test for the player_listings module.
Tests the functionality of fetching all players for a given season.
"""
import os

import json
import pandas as pd
from datetime import datetime



from api_tools.player_listings import (
    fetch_common_all_players_logic,
    PLAYER_LISTINGS_CSV_DIR
)
from config import settings

# Sample season for testing
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_LEAGUE_ID = "00"  # NBA

def test_fetch_common_all_players_basic():
    """Test fetching all players with default parameters."""
    print("\n=== Testing fetch_common_all_players_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_common_all_players_logic(SAMPLE_SEASON, SAMPLE_LEAGUE_ID)
    
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
        # Check if the parameters field exists and matches the input
        assert "parameters" in data, "Response should have a 'parameters' field"
        assert data["parameters"]["season"] == SAMPLE_SEASON, f"season should be {SAMPLE_SEASON}"
        assert data["parameters"]["league_id"] == SAMPLE_LEAGUE_ID, f"league_id should be {SAMPLE_LEAGUE_ID}"
        
        # Check if the players field exists and is a list
        assert "players" in data, "Response should have a 'players' field"
        assert isinstance(data["players"], list), "players should be a list"
        
        # Print some information about the data
        print(f"Season: {data['parameters']['season']}")
        print(f"League ID: {data['parameters']['league_id']}")
        print(f"Is Only Current Season: {data['parameters']['is_only_current_season']}")
        print(f"Number of players: {len(data['players'])}")
        
        # Print a sample of players
        if data["players"]:
            print("\nSample Players:")
            for i, player in enumerate(data["players"][:5]):
                print(f"\nPlayer {i+1}:")
                print(f"  ID: {player.get('PERSON_ID', 'N/A')}")
                print(f"  Name: {player.get('DISPLAY_FIRST_LAST', 'N/A')}")
                print(f"  Team: {player.get('TEAM_NAME', 'N/A')} ({player.get('TEAM_ABBREVIATION', 'N/A')})")
                print(f"  From Year: {player.get('FROM_YEAR', 'N/A')}")
                print(f"  To Year: {player.get('TO_YEAR', 'N/A')}")
    
    print("\n=== Basic test completed ===")
    return data

def test_fetch_common_all_players_historical():
    """Test fetching all historical players for a season."""
    print("\n=== Testing fetch_common_all_players_logic (historical) ===")
    
    # Test with is_only_current_season=0 (all historical players)
    json_response = fetch_common_all_players_logic(SAMPLE_SEASON, SAMPLE_LEAGUE_ID, is_only_current_season=0)
    
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
        # Check if the parameters field exists and matches the input
        assert "parameters" in data, "Response should have a 'parameters' field"
        assert data["parameters"]["is_only_current_season"] == 0, "is_only_current_season should be 0"
        
        # Print some information about the data
        print(f"Season: {data['parameters']['season']}")
        print(f"League ID: {data['parameters']['league_id']}")
        print(f"Is Only Current Season: {data['parameters']['is_only_current_season']}")
        print(f"Number of players: {len(data['players'])}")
    
    print("\n=== Historical test completed ===")
    return data

def test_fetch_common_all_players_dataframe():
    """Test fetching all players with DataFrame output."""
    print("\n=== Testing fetch_common_all_players_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_common_all_players_logic(SAMPLE_SEASON, SAMPLE_LEAGUE_ID, return_dataframe=True)
    
    # Check if the result is a tuple
    assert isinstance(result, tuple), "Result should be a tuple when return_dataframe=True"
    assert len(result) == 2, "Result tuple should have 2 elements"
    
    json_response, dataframes = result
    
    # Check if the first element is a JSON string
    assert isinstance(json_response, str), "First element should be a JSON string"
    
    # Check if the second element is a dictionary of DataFrames
    assert isinstance(dataframes, dict), "Second element should be a dictionary of DataFrames"
    
    # Print DataFrame info
    print(f"\nDataFrames returned: {list(dataframes.keys())}")
    for key, df in dataframes.items():
        print(f"\nDataFrame '{key}' shape: {df.shape}")
        print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns
    
    # Check if the CSV files were created
    if os.path.exists(PLAYER_LISTINGS_CSV_DIR):
        csv_files = [f for f in os.listdir(PLAYER_LISTINGS_CSV_DIR) if f.startswith(f"players_{SAMPLE_SEASON}")]
        print(f"\nCSV files created: {csv_files}")
    
    # Display a sample of one DataFrame if not empty
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nSample of DataFrame '{key}' (first 5 rows):")
            print(df.head(5))
            break
    
    print("\n=== DataFrame test completed ===")
    return json_response, dataframes

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running player_listings smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_common_all_players_basic()
        historical_data = test_fetch_common_all_players_historical()
        json_response, dataframes = test_fetch_common_all_players_dataframe()
        
        print("\n=== All tests completed successfully ===")
        return True
    except Exception as e:
        print(f"\n!!! Test failed with error: {str(e)} !!!")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    success = run_all_tests()
    sys.exit(0 if success else 1)

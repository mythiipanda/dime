"""
Smoke test for the live_game_tools module.
Tests the functionality of fetching live scoreboard data with DataFrame output.
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

from backend.api_tools.live_game_tools import (
    fetch_league_scoreboard_logic
)

def test_fetch_league_scoreboard_basic():
    """Test fetching live scoreboard data with default parameters."""
    print("\n=== Testing fetch_league_scoreboard_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_league_scoreboard_logic(
        bypass_cache=True  # Always bypass cache for testing
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
        # Check if the date field exists
        assert "date" in data, "Response should have a 'date' field"
        assert "games" in data, "Response should have a 'games' field"
        
        # Print some information about the data
        print(f"Date: {data['date']}")
        print(f"Number of games: {len(data['games'])}")
        
        # Print information about each game
        for i, game in enumerate(data['games']):
            print(f"\nGame {i+1}:")
            print(f"  {game.get('away_team', {}).get('code', 'N/A')} vs {game.get('home_team', {}).get('code', 'N/A')}")
            print(f"  Status: {game.get('status', {}).get('state_text', 'N/A')}")
            print(f"  Score: {game.get('away_team', {}).get('score', 0)} - {game.get('home_team', {}).get('score', 0)}")
    
    print("\n=== Basic live scoreboard test completed ===")
    return data

def test_fetch_league_scoreboard_dataframe():
    """Test fetching live scoreboard data with DataFrame output."""
    print("\n=== Testing fetch_league_scoreboard_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_league_scoreboard_logic(
        bypass_cache=True,  # Always bypass cache for testing
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
    
    # Check if there's an error in the response
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        print("Continuing with other tests...")
    else:
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
        for key, df in dataframes.items():
            if not df.empty:
                print(f"\nSample of DataFrame '{key}' (first row):")
                print(df.head(1))
                break
    
    print("\n=== DataFrame live scoreboard test completed ===")
    return result

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running live_game_tools smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_league_scoreboard_basic()
        df_result = test_fetch_league_scoreboard_dataframe()
        
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

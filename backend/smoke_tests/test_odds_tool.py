"""
Smoke test for the get_live_odds tool.
Tests the functionality of the tool with both JSON and DataFrame outputs.
"""
import os

import json
import pandas as pd
from datetime import datetime



# Mock the agno.tools.tool decorator
import functools
def mock_tool(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

# Apply the mock to the module before importing

import types
mock_agno_tools = types.ModuleType('agno.tools')
mock_agno_tools.tool = mock_tool
sys.modules['agno.tools'] = mock_agno_tools

# Now import the tool
from tool_kits.misc_tools import get_live_odds

def test_get_live_odds_json():
    """Test the get_live_odds tool with default JSON output."""
    print("\n=== Testing get_live_odds (JSON output) ===")
    
    # Call the tool with default parameters
    json_response = get_live_odds()
    
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
        # Check if the games field exists and is a list
        assert "games" in data, "Response should have a 'games' field"
        assert isinstance(data["games"], list), "'games' field should be a list"
        
        # Print some information about the games
        games = data["games"]
        print(f"Number of games found: {len(games)}")
        
        if games:
            # Print details of the first game
            first_game = games[0]
            print("\nFirst game details:")
            print(f"Game ID: {first_game.get('gameId', 'N/A')}")
            print(f"Home Team ID: {first_game.get('homeTeamId', 'N/A')}")
            print(f"Away Team ID: {first_game.get('awayTeamId', 'N/A')}")
            print(f"Game Time: {first_game.get('gameTime', 'N/A')}")
            print(f"Game Status: {first_game.get('gameStatus', 'N/A')} ({first_game.get('gameStatusText', 'N/A')})")
    
    print("\n=== JSON test completed ===")
    return json_response

def test_get_live_odds_dataframe():
    """Test the get_live_odds tool with DataFrame output."""
    print("\n=== Testing get_live_odds (DataFrame output) ===")
    
    # Call the tool with as_dataframe=True
    json_response = get_live_odds(as_dataframe=True)
    
    # Parse the JSON response
    data = json.loads(json_response)
    
    # Check if the response has the expected structure
    assert isinstance(data, dict), "Response should be a dictionary"
    
    # Check if there's an error in the response
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        print("Continuing with other tests...")
    
    # Check if the dataframe_info field exists
    assert "dataframe_info" in data, "Response should have a 'dataframe_info' field when as_dataframe=True"
    df_info = data["dataframe_info"]
    
    # Print DataFrame info
    print(f"\nDataFrame shape: {df_info.get('dataframe_shape')}")
    print(f"DataFrame columns: {df_info.get('dataframe_columns')}")
    print(f"CSV path: {df_info.get('csv_path')}")
    
    # Check if the CSV file exists
    csv_path = os.path.join(project_root, df_info.get('csv_path', ''))
    if os.path.exists(csv_path):
        print(f"\nCSV file exists at: {csv_path}")
        csv_size = os.path.getsize(csv_path)
        print(f"CSV file size: {csv_size} bytes")
        
        # Read the CSV file to verify it's valid
        try:
            df_from_csv = pd.read_csv(csv_path)
            print(f"CSV DataFrame shape: {df_from_csv.shape}")
        except Exception as e:
            print(f"Error reading CSV file: {e}")
    else:
        print(f"\nWarning: CSV file not found at {csv_path}")
    
    # Display sample data if available
    sample_data = df_info.get('sample_data', [])
    if sample_data:
        print("\nSample data from DataFrame:")
        for i, record in enumerate(sample_data[:3]):  # Show up to 3 records
            print(f"\nRecord {i+1}:")
            for key, value in record.items():
                print(f"  {key}: {value}")
    else:
        print("\nNo sample data available in the response.")
    
    print("\n=== DataFrame test completed ===")
    return data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running get_live_odds tool smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        json_data = test_get_live_odds_json()
        df_data = test_get_live_odds_dataframe()
        
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

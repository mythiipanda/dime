"""
Smoke test for the game_visuals_analytics module's win probability functionality.
Tests the functionality of fetching win probability data for NBA games.
"""
import os

import json
import pandas as pd
from datetime import datetime



from api_tools.game_visuals_analytics import (
    fetch_win_probability_logic,
    WIN_PROB_CSV_DIR
)
from nba_api.stats.library.parameters import RunType

# Sample game ID for testing (2023-24 regular season game)
SAMPLE_GAME_ID = "0022300161"  # Change this to a valid game ID if needed

def test_fetch_win_probability_basic():
    """Test fetching win probability data with default parameters."""
    print("\n=== Testing fetch_win_probability_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_win_probability_logic(SAMPLE_GAME_ID)
    
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
        # Check if the game_id field exists and matches the input
        assert "game_id" in data, "Response should have a 'game_id' field"
        assert data["game_id"] == SAMPLE_GAME_ID, f"game_id should be {SAMPLE_GAME_ID}"
        
        # Check if the win_probability field exists and is a list
        assert "win_probability" in data, "Response should have a 'win_probability' field"
        assert isinstance(data["win_probability"], list), "'win_probability' field should be a list"
        
        # Print some information about the data
        print(f"Number of win probability events: {len(data['win_probability'])}")
        
        if data["win_probability"]:
            # Print details of the first few events
            print("\nFirst 3 win probability events:")
            for i, event in enumerate(data["win_probability"][:3]):
                print(f"\nEvent {i+1}:")
                print(f"  Event Number: {event.get('EVENT_NUM', 'N/A')}")
                print(f"  Home Win %: {event.get('HOME_PCT', 'N/A')}")
                print(f"  Away Win %: {event.get('VISITOR_PCT', 'N/A')}")
                print(f"  Time: {event.get('GAME_TIME', 'N/A')}")
    
    print("\n=== Basic test completed ===")
    return data

def test_fetch_win_probability_run_types():
    """Test fetching win probability data with different run types."""
    print("\n=== Testing fetch_win_probability_logic with different run types ===")
    
    run_types = [RunType.default, "each second", "each poss"]
    results = {}
    
    for run_type in run_types:
        print(f"\nTesting with run_type: {run_type}")
        json_response = fetch_win_probability_logic(SAMPLE_GAME_ID, run_type=run_type)
        data = json.loads(json_response)
        
        if "error" in data:
            print(f"API returned an error: {data['error']}")
        else:
            win_prob_events = data.get("win_probability", [])
            print(f"Number of win probability events: {len(win_prob_events)}")
            results[run_type] = len(win_prob_events)
    
    # Compare the number of events for different run types
    if len(results) > 1:
        print("\nComparison of event counts for different run types:")
        for run_type, count in results.items():
            print(f"  {run_type}: {count} events")
    
    print("\n=== Run type tests completed ===")
    return results

def test_fetch_win_probability_dataframe():
    """Test fetching win probability data with DataFrame output."""
    print("\n=== Testing fetch_win_probability_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_win_probability_logic(SAMPLE_GAME_ID, return_dataframe=True)
    
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
    if os.path.exists(WIN_PROB_CSV_DIR):
        csv_files = [f for f in os.listdir(WIN_PROB_CSV_DIR) if f.startswith(SAMPLE_GAME_ID)]
        print(f"\nCSV files created: {csv_files}")
    
    # Display a sample of one DataFrame if not empty
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nSample of DataFrame '{key}' (first 3 rows):")
            print(df.head(3))
            break
    
    print("\n=== DataFrame test completed ===")
    return json_response, dataframes

def test_fetch_win_probability_with_run_type_and_dataframe():
    """Test fetching win probability data with a specific run type and DataFrame output."""
    print("\n=== Testing fetch_win_probability_logic with run type and DataFrame output ===")
    
    run_type = "each second"
    print(f"Using run_type: {run_type}")
    
    # Test with run_type and return_dataframe=True
    result = fetch_win_probability_logic(SAMPLE_GAME_ID, run_type=run_type, return_dataframe=True)
    
    json_response, dataframes = result
    data = json.loads(json_response)
    
    # Check if run_type was applied
    if "run_type" in data:
        print(f"Run type in response: {data['run_type']}")
    
    # Print DataFrame info
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nDataFrame '{key}' with run_type='{run_type}' shape: {df.shape}")
            
            # Print sample data
            print("\nSample data (first 3 rows):")
            print(df.head(3))
    
    print("\n=== Run type with DataFrame test completed ===")
    return json_response, dataframes

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running win_probability smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_win_probability_basic()
        run_type_results = test_fetch_win_probability_run_types()
        json_response, dataframes = test_fetch_win_probability_dataframe()
        run_type_json, run_type_dfs = test_fetch_win_probability_with_run_type_and_dataframe()
        
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
    success = run_all_tests()
    sys.exit(0 if success else 1)

"""
Smoke test for the game_playbyplay module.
Tests the functionality of fetching play-by-play data for NBA games.
"""
import os

import json
import pandas as pd
from datetime import datetime



from api_tools.game_playbyplay import (
    fetch_playbyplay_logic,
    PBP_CSV_DIR
)

# Sample game ID for testing (2023-24 regular season game)
SAMPLE_GAME_ID = "0022300161"  # Change this to a valid game ID if needed

def test_fetch_playbyplay_basic():
    """Test fetching play-by-play data with default parameters."""
    print("\n=== Testing fetch_playbyplay_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_playbyplay_logic(SAMPLE_GAME_ID)
    
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
        
        # Check if the periods field exists and is a list
        assert "periods" in data, "Response should have a 'periods' field"
        assert isinstance(data["periods"], list), "'periods' field should be a list"
        
        # Print some information about the data
        print(f"Number of periods: {len(data['periods'])}")
        
        if data["periods"]:
            # Print details of the first period
            first_period = data["periods"][0]
            print(f"\nPeriod {first_period.get('period', 'N/A')} details:")
            plays = first_period.get("plays", [])
            print(f"Number of plays: {len(plays)}")
            
            if plays:
                # Print details of the first few plays
                print("\nFirst 3 plays:")
                for i, play in enumerate(plays[:3]):
                    print(f"\nPlay {i+1}:")
                    print(f"  Event: {play.get('event_num', 'N/A')}")
                    print(f"  Clock: {play.get('clock', 'N/A')}")
                    print(f"  Score: {play.get('score', 'N/A')}")
                    print(f"  Team: {play.get('team_tricode', 'N/A')}")
                    print(f"  Player: {play.get('player_name', 'N/A')}")
                    print(f"  Description: {play.get('description', 'N/A')}")
                    print(f"  Event Type: {play.get('event_type', 'N/A')}")
    
    print("\n=== Basic test completed ===")
    return data

def test_fetch_playbyplay_with_filters():
    """Test fetching play-by-play data with various filters."""
    print("\n=== Testing fetch_playbyplay_logic with filters ===")
    
    # Test with period filters
    print("\nTesting with period filters (period 1 only):")
    period_filtered_json = fetch_playbyplay_logic(SAMPLE_GAME_ID, start_period=1, end_period=1)
    period_filtered_data = json.loads(period_filtered_json)
    
    if "error" not in period_filtered_data:
        periods = period_filtered_data.get("periods", [])
        print(f"Number of periods returned: {len(periods)}")
        if periods:
            period_nums = [p.get("period") for p in periods]
            print(f"Period numbers: {period_nums}")
    
    # Test with event type filter (shots only)
    print("\nTesting with event type filter (SHOT only):")
    event_filtered_json = fetch_playbyplay_logic(SAMPLE_GAME_ID, event_types=["SHOT"])
    event_filtered_data = json.loads(event_filtered_json)
    
    if "error" not in event_filtered_data:
        all_plays = []
        for period in event_filtered_data.get("periods", []):
            all_plays.extend(period.get("plays", []))
        
        print(f"Number of shot plays: {len(all_plays)}")
        if all_plays:
            event_types = set(play.get("action_type", "") for play in all_plays)
            print(f"Event types found: {event_types}")
    
    print("\n=== Filter tests completed ===")
    return period_filtered_data, event_filtered_data

def test_fetch_playbyplay_dataframe():
    """Test fetching play-by-play data with DataFrame output."""
    print("\n=== Testing fetch_playbyplay_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_playbyplay_logic(SAMPLE_GAME_ID, return_dataframe=True)
    
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
    if os.path.exists(PBP_CSV_DIR):
        csv_files = [f for f in os.listdir(PBP_CSV_DIR) if f.startswith(SAMPLE_GAME_ID)]
        print(f"\nCSV files created: {csv_files}")
    
    # Display a sample of one DataFrame if not empty
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nSample of DataFrame '{key}' (first 3 rows):")
            print(df.head(3))
            break
    
    print("\n=== DataFrame test completed ===")
    return json_response, dataframes

def test_fetch_playbyplay_with_filters_and_dataframe():
    """Test fetching play-by-play data with filters and DataFrame output."""
    print("\n=== Testing fetch_playbyplay_logic with filters and DataFrame output ===")
    
    # Test with event type filter and DataFrame output
    result = fetch_playbyplay_logic(
        SAMPLE_GAME_ID,
        event_types=["SHOT", "REBOUND"],
        return_dataframe=True
    )
    
    json_response, dataframes = result
    data = json.loads(json_response)
    
    # Check if filters were applied
    if "filters_applied" in data:
        print(f"Filters applied: {data['filters_applied']}")
    
    # Print DataFrame info
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nFiltered DataFrame '{key}' shape: {df.shape}")
            
            # Check if event types were filtered correctly
            if 'actionType' in df.columns:
                event_types = df['actionType'].unique()
                print(f"Event types in DataFrame: {event_types}")
            
            # Print sample data
            print("\nSample data (first 3 rows):")
            print(df.head(3))
    
    print("\n=== Filtered DataFrame test completed ===")
    return json_response, dataframes

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running game_playbyplay smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_playbyplay_basic()
        period_filtered_data, event_filtered_data = test_fetch_playbyplay_with_filters()
        json_response, dataframes = test_fetch_playbyplay_dataframe()
        filtered_json, filtered_dfs = test_fetch_playbyplay_with_filters_and_dataframe()
        
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

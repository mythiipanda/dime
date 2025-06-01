"""
Smoke test for the get_play_by_play tool.
Tests the functionality of the tool with both JSON and DataFrame outputs.
"""
import os
import sys

import json
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
from tool_kits.game_tools import get_play_by_play

# Sample game ID for testing (2023-24 regular season game)
SAMPLE_GAME_ID = "0022300161"  # Change this to a valid game ID if needed

def test_get_play_by_play_basic():
    """Test the get_play_by_play tool with default parameters."""
    print("\n=== Testing get_play_by_play (basic) ===")
    
    # Call the tool with default parameters
    json_response = get_play_by_play(SAMPLE_GAME_ID)
    
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
        
        # Print some information about the data
        print(f"Source: {data.get('source', 'N/A')}")
        print(f"Has video: {data.get('has_video', 'N/A')}")
        print(f"Number of periods: {len(data.get('periods', []))}")
        
        # Print details of a few plays if available
        periods = data.get('periods', [])
        if periods:
            first_period = periods[0]
            plays = first_period.get('plays', [])
            if plays:
                print("\nSample plays from first period:")
                for i, play in enumerate(plays[:3]):  # Show first 3 plays
                    print(f"\nPlay {i+1}:")
                    print(f"  Clock: {play.get('clock', 'N/A')}")
                    print(f"  Description: {play.get('description', 'N/A')}")
                    print(f"  Event Type: {play.get('event_type', 'N/A')}")
    
    print("\n=== Basic test completed ===")
    return data

def test_get_play_by_play_with_filters():
    """Test the get_play_by_play tool with various filters."""
    print("\n=== Testing get_play_by_play with filters ===")
    
    # Test with period filters
    print("\nTesting with period filters (period 1 only):")
    period_filtered_json = get_play_by_play(SAMPLE_GAME_ID, start_period=1, end_period=1)
    period_filtered_data = json.loads(period_filtered_json)
    
    if "error" not in period_filtered_data:
        periods = period_filtered_data.get("periods", [])
        print(f"Number of periods returned: {len(periods)}")
        if periods:
            period_nums = [p.get("period") for p in periods]
            print(f"Period numbers: {period_nums}")
    
    # Test with event type filter (shots only)
    print("\nTesting with event type filter (SHOT only):")
    event_filtered_json = get_play_by_play(SAMPLE_GAME_ID, event_types="SHOT")
    event_filtered_data = json.loads(event_filtered_json)
    
    if "error" not in event_filtered_data:
        all_plays = []
        for period in event_filtered_data.get("periods", []):
            all_plays.extend(period.get("plays", []))
        
        print(f"Number of shot plays: {len(all_plays)}")
        if all_plays:
            event_types = set(play.get("action_type", "") for play in all_plays)
            print(f"Event types found: {event_types}")
    
    # Test with multiple filters
    print("\nTesting with multiple filters (period 1, SHOT and REBOUND events):")
    multi_filtered_json = get_play_by_play(
        SAMPLE_GAME_ID, 
        start_period=1, 
        end_period=1, 
        event_types="SHOT,REBOUND"
    )
    multi_filtered_data = json.loads(multi_filtered_json)
    
    if "error" not in multi_filtered_data:
        all_plays = []
        for period in multi_filtered_data.get("periods", []):
            all_plays.extend(period.get("plays", []))
        
        print(f"Number of filtered plays: {len(all_plays)}")
        if all_plays:
            event_types = set(play.get("action_type", "") for play in all_plays)
            print(f"Event types found: {event_types}")
    
    print("\n=== Filter tests completed ===")
    return period_filtered_data, event_filtered_data, multi_filtered_data

def test_get_play_by_play_dataframe():
    """Test the get_play_by_play tool with DataFrame output."""
    print("\n=== Testing get_play_by_play with DataFrame output ===")
    
    # Call the tool with as_dataframe=True
    df_json_response = get_play_by_play(SAMPLE_GAME_ID, as_dataframe=True)
    
    # Parse the JSON response
    df_data = json.loads(df_json_response)
    
    # Check if the response has the expected structure
    assert isinstance(df_data, dict), "Response should be a dictionary"
    
    # Check if the dataframe_info field exists
    assert "dataframe_info" in df_data, "Response should have a 'dataframe_info' field when as_dataframe=True"
    
    # Print DataFrame info
    df_info = df_data["dataframe_info"]
    print(f"\nDataFrames available: {list(df_info.get('dataframes', {}).keys())}")
    
    # Check if CSV files were created
    for key, info in df_info.get("dataframes", {}).items():
        csv_path = info.get("csv_path")
        if csv_path:
            full_path = os.path.join(project_root, csv_path)
            if os.path.exists(full_path):
                print(f"CSV file exists for {key}: {csv_path}")
                print(f"File size: {os.path.getsize(full_path)} bytes")
            else:
                print(f"Warning: CSV file not found for {key}: {csv_path}")
    
    # Print sample data
    for key, info in df_info.get("dataframes", {}).items():
        sample_data = info.get("sample_data", [])
        if sample_data:
            print(f"\nSample data for {key} (first 3 records):")
            for i, record in enumerate(sample_data[:3]):
                print(f"\nRecord {i+1}:")
                for field, value in record.items():
                    print(f"  {field}: {value}")
    
    print("\n=== DataFrame test completed ===")
    return df_data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running get_play_by_play tool smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_get_play_by_play_basic()
        period_data, event_data, multi_data = test_get_play_by_play_with_filters()
        df_data = test_get_play_by_play_dataframe()
        
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

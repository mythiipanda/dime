"""
Smoke test for the game_tools module.
Tests the functionality of the game-related tools with both JSON and DataFrame outputs.
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

# Now import the tools
from tool_kits.game_tools import (
    get_boxscore_traditional,
    get_boxscore_advanced,
    get_boxscore_four_factors,
    get_boxscore_usage,
    get_boxscore_defensive,
    get_boxscore_summary
)

# Sample game ID for testing (2023-24 regular season game)
SAMPLE_GAME_ID = "0022300161"  # Change this to a valid game ID if needed

def test_get_boxscore_traditional():
    """Test the get_boxscore_traditional tool with both JSON and DataFrame outputs."""
    print("\n=== Testing get_boxscore_traditional ===")
    
    # Test with default parameters (JSON output)
    print("\nTesting JSON output:")
    json_response = get_boxscore_traditional(SAMPLE_GAME_ID)
    
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
        print(f"Number of teams: {len(data.get('teams', []))}")
        print(f"Number of players: {len(data.get('players', []))}")
    
    # Test with as_dataframe=True
    print("\nTesting DataFrame output:")
    df_json_response = get_boxscore_traditional(SAMPLE_GAME_ID, as_dataframe=True)
    
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
    
    print("\n=== get_boxscore_traditional test completed ===")
    return data, df_data

def test_get_boxscore_advanced():
    """Test the get_boxscore_advanced tool with DataFrame output."""
    print("\n=== Testing get_boxscore_advanced with DataFrame output ===")
    
    df_json_response = get_boxscore_advanced(SAMPLE_GAME_ID, as_dataframe=True)
    df_data = json.loads(df_json_response)
    
    assert "dataframe_info" in df_data, "Response should have a 'dataframe_info' field"
    
    print(f"DataFrames available: {list(df_data['dataframe_info'].get('dataframes', {}).keys())}")
    
    print("\n=== get_boxscore_advanced test completed ===")
    return df_data

def test_other_boxscore_tools():
    """Test the other boxscore tools with DataFrame output."""
    print("\n=== Testing other boxscore tools with DataFrame output ===")
    
    # Test Four Factors
    print("\nTesting Four Factors:")
    four_factors_response = get_boxscore_four_factors(SAMPLE_GAME_ID, as_dataframe=True)
    four_factors_data = json.loads(four_factors_response)
    assert "dataframe_info" in four_factors_data, "Response should have a 'dataframe_info' field"
    print(f"Four Factors DataFrames: {list(four_factors_data['dataframe_info'].get('dataframes', {}).keys())}")
    
    # Test Usage
    print("\nTesting Usage:")
    usage_response = get_boxscore_usage(SAMPLE_GAME_ID, as_dataframe=True)
    usage_data = json.loads(usage_response)
    assert "dataframe_info" in usage_data, "Response should have a 'dataframe_info' field"
    print(f"Usage DataFrames: {list(usage_data['dataframe_info'].get('dataframes', {}).keys())}")
    
    # Test Defensive
    print("\nTesting Defensive:")
    defensive_response = get_boxscore_defensive(SAMPLE_GAME_ID, as_dataframe=True)
    defensive_data = json.loads(defensive_response)
    assert "dataframe_info" in defensive_data, "Response should have a 'dataframe_info' field"
    print(f"Defensive DataFrames: {list(defensive_data['dataframe_info'].get('dataframes', {}).keys())}")
    
    # Test Summary
    print("\nTesting Summary:")
    summary_response = get_boxscore_summary(SAMPLE_GAME_ID, as_dataframe=True)
    summary_data = json.loads(summary_response)
    assert "dataframe_info" in summary_data, "Response should have a 'dataframe_info' field"
    print(f"Summary DataFrames: {list(summary_data['dataframe_info'].get('dataframes', {}).keys())}")
    
    # Check CSV files in the cache directory
    boxscores_dir = os.path.join(project_root, "backend", "cache", "boxscores")
    if os.path.exists(boxscores_dir):
        csv_files = [f for f in os.listdir(boxscores_dir) if f.startswith(SAMPLE_GAME_ID)]
        print(f"\nTotal CSV files created: {len(csv_files)}")
        print(f"CSV files: {csv_files[:5]}...")  # Show first 5 files
    
    print("\n=== Other boxscore tools test completed ===")
    return four_factors_data, usage_data, defensive_data, summary_data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running game_tools smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        traditional_data, traditional_df_data = test_get_boxscore_traditional()
        advanced_df_data = test_get_boxscore_advanced()
        four_factors_data, usage_data, defensive_data, summary_data = test_other_boxscore_tools()
        
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

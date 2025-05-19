"""
Smoke test for the player_clutch module.
Tests the functionality of fetching player clutch performance statistics.
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

from backend.api_tools.player_clutch import (
    fetch_player_clutch_stats_logic,
    PLAYER_CLUTCH_CSV_DIR
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, MeasureTypeDetailed, PerModeDetailed
)

# Sample player name and season for testing
SAMPLE_PLAYER_NAME = "LeBron James"  # A well-known player with a long career
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular  # Regular season

def test_fetch_player_clutch_stats_basic():
    """Test fetching player clutch stats with default parameters."""
    print("\n=== Testing fetch_player_clutch_stats_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_player_clutch_stats_logic(
        SAMPLE_PLAYER_NAME, 
        SAMPLE_SEASON, 
        SAMPLE_SEASON_TYPE
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
        # Check if the player_name field exists and matches the input
        assert "player_name" in data, "Response should have a 'player_name' field"
        assert data["player_name"] == SAMPLE_PLAYER_NAME, f"player_name should be {SAMPLE_PLAYER_NAME}"
        
        # Check if the parameters field exists
        assert "parameters" in data, "Response should have a 'parameters' field"
        
        # Check if the clutch_dashboards field exists
        assert "clutch_dashboards" in data, "Response should have a 'clutch_dashboards' field"
        
        # Print some information about the data
        print(f"Player: {data.get('player_name', 'N/A')} (ID: {data.get('player_id', 'N/A')})")
        print(f"Season: {data.get('parameters', {}).get('season', 'N/A')}")
        print(f"Season Type: {data.get('parameters', {}).get('season_type', 'N/A')}")
        
        # Print clutch dashboards
        if "clutch_dashboards" in data:
            dashboards = data["clutch_dashboards"]
            print(f"\nClutch Dashboards: {len(dashboards)} dashboards")
            for dash_name, dash_data in dashboards.items():
                print(f"\n{dash_name}: {len(dash_data)} rows")
                if dash_data:
                    # Print first row of each dashboard
                    first_row = dash_data[0]
                    print("Sample data (first row):")
                    for key, value in list(first_row.items())[:5]:  # Show first 5 columns
                        print(f"  {key}: {value}")
    
    print("\n=== Basic test completed ===")
    return data

def test_fetch_player_clutch_stats_advanced():
    """Test fetching player clutch stats with advanced measure type."""
    print("\n=== Testing fetch_player_clutch_stats_logic (advanced) ===")
    
    # Test with advanced measure type
    json_response = fetch_player_clutch_stats_logic(
        SAMPLE_PLAYER_NAME, 
        SAMPLE_SEASON, 
        SAMPLE_SEASON_TYPE,
        measure_type=MeasureTypeDetailed.advanced
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
        # Check if the measure_type parameter matches the input
        assert data.get("parameters", {}).get("measure_type") == MeasureTypeDetailed.advanced, \
            f"measure_type should be {MeasureTypeDetailed.advanced}"
        
        # Print some information about the data
        print(f"Player: {data.get('player_name', 'N/A')} (ID: {data.get('player_id', 'N/A')})")
        print(f"Measure Type: {data.get('parameters', {}).get('measure_type', 'N/A')}")
        
        # Print clutch dashboards
        if "clutch_dashboards" in data:
            dashboards = data["clutch_dashboards"]
            print(f"\nClutch Dashboards: {len(dashboards)} dashboards")
            for dash_name, dash_data in dashboards.items():
                print(f"\n{dash_name}: {len(dash_data)} rows")
                if dash_data:
                    # Print first row of each dashboard
                    first_row = dash_data[0]
                    print("Sample data (first row):")
                    for key, value in list(first_row.items())[:5]:  # Show first 5 columns
                        print(f"  {key}: {value}")
    
    print("\n=== Advanced test completed ===")
    return data

def test_fetch_player_clutch_stats_dataframe():
    """Test fetching player clutch stats with DataFrame output."""
    print("\n=== Testing fetch_player_clutch_stats_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_player_clutch_stats_logic(
        SAMPLE_PLAYER_NAME, 
        SAMPLE_SEASON, 
        SAMPLE_SEASON_TYPE,
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
    
    # Print DataFrame info
    print(f"\nDataFrames returned: {len(dataframes)} dashboards")
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nDataFrame '{key}' shape: {df.shape}")
            print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns
    
    # Check if the CSV files were created
    if os.path.exists(PLAYER_CLUTCH_CSV_DIR):
        csv_files = [f for f in os.listdir(PLAYER_CLUTCH_CSV_DIR) if f.startswith(SAMPLE_PLAYER_NAME.lower().replace(" ", "_"))]
        print(f"\nCSV files created: {len(csv_files)}")
        if csv_files:
            print(f"Sample CSV files: {csv_files[:3]}...")
    
    # Display a sample of one DataFrame if not empty
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nSample of DataFrame '{key}' (first 3 rows):")
            print(df.head(3))
            break
    
    print("\n=== DataFrame test completed ===")
    return json_response, dataframes

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running player_clutch smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_player_clutch_stats_basic()
        advanced_data = test_fetch_player_clutch_stats_advanced()
        json_response, dataframes = test_fetch_player_clutch_stats_dataframe()
        
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

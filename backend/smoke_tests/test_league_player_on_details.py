"""
Smoke test for the league_player_on_details module.
Tests the functionality of fetching NBA league player on details data.
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

from backend.api_tools.league_player_on_details import (
    fetch_league_player_on_details_logic
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed,
    MeasureTypeDetailedDefense
)

# Sample season and team ID for testing
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_TEAM_ID = 1610612747  # Los Angeles Lakers

def test_fetch_player_on_details_basic():
    """Test fetching league player on details with default parameters."""
    print("\n=== Testing fetch_league_player_on_details_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_league_player_on_details_logic(
        season=SAMPLE_SEASON,
        season_type=SeasonTypeAllStar.regular,
        measure_type=MeasureTypeDetailedDefense.base,
        per_mode=PerModeDetailed.totals,
        team_id=SAMPLE_TEAM_ID
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
        # Check if parameters exist
        assert "parameters" in data, "Response should have 'parameters'"
        
        # Print some information about the data
        print(f"Season: {data['parameters']['season']}")
        print(f"Team ID: {data['parameters']['team_id']}")
        
        # Check if league_player_on_details exist
        assert "league_player_on_details" in data, "Response should have 'league_player_on_details'"
        
        # Print some information about the player on details
        details = data["league_player_on_details"]
        print(f"\nNumber of player on details entries: {len(details)}")
        
        if details:
            print("\nSample player on details entry:")
            first_entry = details[0]
            # Print a few key fields (adjust based on actual response structure)
            for key, value in list(first_entry.items())[:5]:  # Show first 5 fields
                print(f"  {key}: {value}")
    
    print("\n=== Basic player on details test completed ===")
    return data

def test_fetch_player_on_details_dataframe():
    """Test fetching league player on details with DataFrame output."""
    print("\n=== Testing fetch_league_player_on_details_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_league_player_on_details_logic(
        season=SAMPLE_SEASON,
        season_type=SeasonTypeAllStar.regular,
        measure_type=MeasureTypeDetailedDefense.base,
        per_mode=PerModeDetailed.totals,
        team_id=SAMPLE_TEAM_ID,
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
    if "league_player_on_details" in dataframes and not dataframes["league_player_on_details"].empty:
        print(f"\nSample of league player on details DataFrame (first 3 rows):")
        print(dataframes["league_player_on_details"].head(3))
    
    print("\n=== DataFrame player on details test completed ===")
    return json_response, dataframes

def test_fetch_player_on_details_advanced():
    """Test fetching league player on details with advanced measure type."""
    print("\n=== Testing fetch_league_player_on_details_logic with advanced measure type ===")
    
    # Test with advanced measure type
    json_response = fetch_league_player_on_details_logic(
        season=SAMPLE_SEASON,
        season_type=SeasonTypeAllStar.regular,
        measure_type=MeasureTypeDetailedDefense.advanced,
        per_mode=PerModeDetailed.totals,
        team_id=SAMPLE_TEAM_ID
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
        # Check if the measure_type parameter was correctly used
        assert data["parameters"]["measure_type"] == MeasureTypeDetailedDefense.advanced, "Measure type should be Advanced"
        
        # Print some information about the data
        print(f"Season: {data['parameters']['season']}")
        print(f"Measure Type: {data['parameters']['measure_type']}")
        
        # Check if league_player_on_details exist
        assert "league_player_on_details" in data, "Response should have 'league_player_on_details'"
        
        # Print some information about the player on details
        details = data["league_player_on_details"]
        print(f"\nNumber of advanced player on details entries: {len(details)}")
    
    print("\n=== Advanced player on details test completed ===")
    return data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running league_player_on_details smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_player_on_details_basic()
        df_json, df_data = test_fetch_player_on_details_dataframe()
        advanced_data = test_fetch_player_on_details_advanced()
        
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

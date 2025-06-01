"""
Smoke test for the league_opponent_shot_dashboard module.
Tests the functionality of fetching opponent shot dashboard data.
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

from api_tools.league_opponent_shot_dashboard import (
    fetch_league_dash_opponent_pt_shot_logic
)
from nba_api.stats.library.parameters import (
    PerModeSimple,
    SeasonTypeAllStar
)

# Sample season for testing
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing

def test_fetch_opponent_shot_dashboard_basic():
    """Test fetching opponent shot dashboard with default parameters."""
    print("\n=== Testing fetch_league_dash_opponent_pt_shot_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_league_dash_opponent_pt_shot_logic(
        season=SAMPLE_SEASON,
        season_type=SeasonTypeAllStar.regular,
        per_mode_simple=PerModeSimple.totals
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
        print(f"Per Mode: {data['parameters']['per_mode_simple']}")
        
        # Check if opponent_shots exist
        assert "opponent_shots" in data, "Response should have 'opponent_shots'"
        
        # Print some information about the opponent shots
        shots = data["opponent_shots"]
        print(f"\nNumber of opponent shot entries: {len(shots)}")
        
        if shots:
            print("\nSample opponent shot entry:")
            first_shot = shots[0]
            # Print a few key fields (adjust based on actual response structure)
            for key, value in list(first_shot.items())[:5]:  # Show first 5 fields
                print(f"  {key}: {value}")
    
    print("\n=== Basic opponent shot dashboard test completed ===")
    return data

def test_fetch_opponent_shot_dashboard_dataframe():
    """Test fetching opponent shot dashboard with DataFrame output."""
    print("\n=== Testing fetch_league_dash_opponent_pt_shot_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_league_dash_opponent_pt_shot_logic(
        season=SAMPLE_SEASON,
        season_type=SeasonTypeAllStar.regular,
        per_mode_simple=PerModeSimple.totals,
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
    if "opponent_shots" in dataframes and not dataframes["opponent_shots"].empty:
        print(f"\nSample of opponent shots DataFrame (first 3 rows):")
        print(dataframes["opponent_shots"].head(3))
    
    print("\n=== DataFrame opponent shot dashboard test completed ===")
    return json_response, dataframes

def test_fetch_opponent_shot_dashboard_filtered():
    """Test fetching opponent shot dashboard with filters."""
    print("\n=== Testing fetch_league_dash_opponent_pt_shot_logic with filters ===")
    
    # Test with filters - using a specific team ID (Lakers: 1610612747)
    team_id = 1610612747
    
    json_response = fetch_league_dash_opponent_pt_shot_logic(
        season=SAMPLE_SEASON,
        season_type=SeasonTypeAllStar.regular,
        per_mode_simple=PerModeSimple.totals,
        team_id_nullable=team_id
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
        # Check if the team_id_nullable parameter was correctly used
        assert data["parameters"]["team_id_nullable"] == team_id, f"Team ID filter should be {team_id}"
        
        # Print some information about the data
        print(f"Season: {data['parameters']['season']}")
        print(f"Team ID Filter: {data['parameters']['team_id_nullable']}")
        
        # Check if opponent_shots exist
        assert "opponent_shots" in data, "Response should have 'opponent_shots'"
        
        # Print some information about the opponent shots
        shots = data["opponent_shots"]
        print(f"\nNumber of opponent shot entries for team {team_id}: {len(shots)}")
    
    print("\n=== Filtered opponent shot dashboard test completed ===")
    return data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running league_opponent_shot_dashboard smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_opponent_shot_dashboard_basic()
        df_json, df_data = test_fetch_opponent_shot_dashboard_dataframe()
        filtered_data = test_fetch_opponent_shot_dashboard_filtered()
        
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

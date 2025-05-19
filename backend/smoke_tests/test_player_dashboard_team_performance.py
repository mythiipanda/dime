"""
Smoke test for the player_dashboard_team_performance module.
Tests the functionality of fetching player dashboard statistics by team performance.
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

from backend.api_tools.player_dashboard_team_performance import (
    fetch_player_dashboard_by_team_performance_logic
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailed, LeagueID
)

# Sample player for testing
SAMPLE_PLAYER = "LeBron James"
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing

def test_fetch_player_dashboard_by_team_performance_basic():
    """Test fetching player dashboard by team performance with default parameters."""
    print("\n=== Testing fetch_player_dashboard_by_team_performance_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_player_dashboard_by_team_performance_logic(
        SAMPLE_PLAYER,
        SAMPLE_SEASON,
        SeasonTypeAllStar.regular,
        PerModeDetailed.per_game,
        MeasureTypeDetailed.base
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
        # Check if the player_name field exists
        assert "player_name" in data, "Response should have a 'player_name' field"
        assert "player_id" in data, "Response should have a 'player_id' field"
        
        # Print some information about the data
        print(f"Player Name: {data.get('player_name')}")
        print(f"Player ID: {data.get('player_id')}")
        
        # Check if team_performance_dashboards exist
        assert "team_performance_dashboards" in data, "Response should have 'team_performance_dashboards'"
        
        # Check if all dashboard types exist
        dashboards = data["team_performance_dashboards"]
        expected_dashboards = [
            "overall_player_dashboard",
            "points_scored_player_dashboard",
            "ponts_against_player_dashboard",
            "score_differential_player_dashboard"
        ]
        
        for dashboard in expected_dashboards:
            assert dashboard in dashboards, f"Response should have '{dashboard}'"
            
            # Print some information about each dashboard
            dashboard_data = dashboards[dashboard]
            print(f"\n{dashboard.replace('_', ' ').title()} entries: {len(dashboard_data)}")
            
            if dashboard_data:
                print("Sample data from first entry:")
                first_entry = dashboard_data[0]
                for key, value in list(first_entry.items())[:5]:  # Show first 5 fields
                    print(f"  {key}: {value}")
    
    print("\n=== Basic team performance test completed ===")
    return data

def test_fetch_player_dashboard_by_team_performance_dataframe():
    """Test fetching player dashboard by team performance with DataFrame output."""
    print("\n=== Testing fetch_player_dashboard_by_team_performance_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_player_dashboard_by_team_performance_logic(
        SAMPLE_PLAYER,
        SAMPLE_SEASON,
        SeasonTypeAllStar.regular,
        PerModeDetailed.per_game,
        MeasureTypeDetailed.base,
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
    
    # Check if the CSV files were created
    if "dataframe_info" in data:
        for df_key, df_info in data["dataframe_info"].get("dataframes", {}).items():
            csv_path = df_info.get("csv_path")
            if csv_path:
                full_path = os.path.join(backend_dir, csv_path)
                if os.path.exists(full_path):
                    print(f"\nCSV file exists: {csv_path}")
                else:
                    print(f"\nCSV file does not exist: {csv_path}")
    
    # Display a sample of one DataFrame if not empty
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nSample of DataFrame '{key}' (first 3 rows):")
            print(df.head(3))
            break
    
    print("\n=== DataFrame team performance test completed ===")
    return json_response, dataframes

def test_fetch_player_dashboard_by_team_performance_advanced():
    """Test fetching player dashboard by team performance with advanced measure type."""
    print("\n=== Testing fetch_player_dashboard_by_team_performance_logic with advanced measure type ===")
    
    # Test with advanced measure type
    json_response = fetch_player_dashboard_by_team_performance_logic(
        SAMPLE_PLAYER,
        SAMPLE_SEASON,
        SeasonTypeAllStar.regular,
        PerModeDetailed.per_game,
        MeasureTypeDetailed.advanced
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
        assert data["parameters"]["measure_type"] == MeasureTypeDetailed.advanced, "Measure type should be 'Advanced'"
        
        # Print some information about the data
        print(f"Player Name: {data.get('player_name')}")
        print(f"Measure Type: {data['parameters']['measure_type']}")
        
        # Check if team_performance_dashboards exist
        assert "team_performance_dashboards" in data, "Response should have 'team_performance_dashboards'"
        
        # Print some information about the overall dashboard
        overall_dashboard = data["team_performance_dashboards"]["overall_player_dashboard"]
        if overall_dashboard:
            print("\nSample advanced metrics from overall dashboard:")
            first_entry = overall_dashboard[0]
            # Advanced metrics typically include these fields
            advanced_fields = ["TS_PCT", "EFG_PCT", "USG_PCT", "PACE", "PIE", "OFF_RATING", "DEF_RATING", "NET_RATING"]
            for field in advanced_fields:
                if field in first_entry:
                    print(f"  {field}: {first_entry[field]}")
    
    print("\n=== Advanced measure type test completed ===")
    return data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running player_dashboard_team_performance smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_player_dashboard_by_team_performance_basic()
        df_json, df_data = test_fetch_player_dashboard_by_team_performance_dataframe()
        advanced_data = test_fetch_player_dashboard_by_team_performance_advanced()
        
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

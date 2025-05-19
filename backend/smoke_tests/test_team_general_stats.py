"""
Smoke test for the team_general_stats module.
Tests the functionality of fetching team general statistics.
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

from backend.api_tools.team_general_stats import (
    fetch_team_stats_logic,
    TEAM_GENERAL_CSV_DIR
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailedDefense, LeagueID
)

# Sample team name and season for testing
SAMPLE_TEAM_NAME = "Boston Celtics"  # A successful team with good stats
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular  # Regular season

def test_fetch_team_stats_basic():
    """Test fetching team general stats with default parameters."""
    print("\n=== Testing fetch_team_stats_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_team_stats_logic(
        SAMPLE_TEAM_NAME, 
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
        # Check if the team_name field exists and matches the input
        assert "team_name" in data, "Response should have a 'team_name' field"
        assert data["team_name"].lower() == SAMPLE_TEAM_NAME.lower(), f"team_name should be {SAMPLE_TEAM_NAME}"
        
        # Check if the parameters field exists
        assert "parameters" in data, "Response should have a 'parameters' field"
        
        # Check if the dashboard stats field exists
        assert "current_season_dashboard_stats" in data, "Response should have a 'current_season_dashboard_stats' field"
        
        # Check if the historical stats field exists
        assert "historical_year_by_year_stats" in data, "Response should have a 'historical_year_by_year_stats' field"
        
        # Print some information about the data
        print(f"Team: {data.get('team_name', 'N/A')} (ID: {data.get('team_id', 'N/A')})")
        print(f"Season for Dashboard: {data.get('parameters', {}).get('season_for_dashboard', 'N/A')}")
        print(f"Season Type for Dashboard: {data.get('parameters', {}).get('season_type_for_dashboard', 'N/A')}")
        
        # Print dashboard stats
        if "current_season_dashboard_stats" in data and data["current_season_dashboard_stats"]:
            dashboard = data["current_season_dashboard_stats"]
            print("\nDashboard Stats (sample):")
            for key, value in list(dashboard.items())[:5]:  # Show first 5 columns
                print(f"  {key}: {value}")
        
        # Print historical stats
        if "historical_year_by_year_stats" in data and data["historical_year_by_year_stats"]:
            historical = data["historical_year_by_year_stats"]
            print(f"\nHistorical Stats: {len(historical)} seasons")
            if historical:
                # Print first entry
                first_entry = historical[0]
                print("Sample data (first season):")
                for key, value in list(first_entry.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")
    
    print("\n=== Basic test completed ===")
    return data

def test_fetch_team_stats_advanced():
    """Test fetching team general stats with Advanced measure type."""
    print("\n=== Testing fetch_team_stats_logic (Advanced) ===")
    
    # Test with Advanced measure type
    json_response = fetch_team_stats_logic(
        SAMPLE_TEAM_NAME, 
        SAMPLE_SEASON, 
        SAMPLE_SEASON_TYPE,
        measure_type=MeasureTypeDetailedDefense.advanced
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
        assert data.get("parameters", {}).get("measure_type_for_dashboard") == MeasureTypeDetailedDefense.advanced, \
            f"measure_type should be {MeasureTypeDetailedDefense.advanced}"
        
        # Print some information about the data
        print(f"Team: {data.get('team_name', 'N/A')} (ID: {data.get('team_id', 'N/A')})")
        print(f"Measure Type: {data.get('parameters', {}).get('measure_type_for_dashboard', 'N/A')}")
        
        # Print dashboard stats
        if "current_season_dashboard_stats" in data and data["current_season_dashboard_stats"]:
            dashboard = data["current_season_dashboard_stats"]
            print("\nAdvanced Dashboard Stats (sample):")
            for key, value in list(dashboard.items())[:5]:  # Show first 5 columns
                print(f"  {key}: {value}")
    
    print("\n=== Advanced test completed ===")
    return data

def test_fetch_team_stats_dataframe():
    """Test fetching team general stats with DataFrame output."""
    print("\n=== Testing fetch_team_stats_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_team_stats_logic(
        SAMPLE_TEAM_NAME, 
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
    print(f"\nDataFrames returned: {list(dataframes.keys())}")
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nDataFrame '{key}' shape: {df.shape}")
            print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns
    
    # Check if the CSV files were created
    if os.path.exists(TEAM_GENERAL_CSV_DIR):
        # Parse the JSON response to get the team name
        data = json.loads(json_response)
        team_name = data.get("team_name", SAMPLE_TEAM_NAME)
        clean_team_name = team_name.lower().replace(" ", "_").replace(".", "")
        
        csv_files = [f for f in os.listdir(TEAM_GENERAL_CSV_DIR) if f.startswith(clean_team_name)]
        print(f"\nCSV files created: {len(csv_files)}")
        if csv_files:
            print(f"Sample CSV files: {csv_files[:2]}...")
    
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
    print(f"=== Running team_general_stats smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_team_stats_basic()
        advanced_data = test_fetch_team_stats_advanced()
        json_response, dataframes = test_fetch_team_stats_dataframe()
        
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

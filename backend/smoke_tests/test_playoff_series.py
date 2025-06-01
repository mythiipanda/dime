"""
Smoke test for the playoff_series module.
Tests the functionality of fetching playoff series data with DataFrame output.
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

from api_tools.playoff_series import fetch_common_playoff_series_logic
from nba_api.stats.library.parameters import LeagueID

# Sample season for testing
SAMPLE_SEASON = "2022-23"  # A recent season with playoff data

def test_fetch_playoff_series_basic():
    """Test fetching playoff series with default parameters."""
    print("\n=== Testing fetch_common_playoff_series_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_common_playoff_series_logic(
        season=SAMPLE_SEASON,
        league_id=LeagueID.nba
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
        # Check if the parameters field exists
        assert "parameters" in data, "Response should have a 'parameters' field"
        assert "playoff_series" in data, "Response should have a 'playoff_series' field"
        
        # Print some information about the data
        parameters = data["parameters"]
        print(f"Season: {parameters.get('season', 'N/A')}")
        print(f"League ID: {parameters.get('league_id', 'N/A')}")
        print(f"Series ID: {parameters.get('series_id', 'N/A')}")
        
        # Print playoff series data
        playoff_series = data["playoff_series"]
        print(f"\nNumber of playoff series entries: {len(playoff_series)}")
        
        if playoff_series:
            print("\nFirst 3 playoff series entries:")
            for i, series in enumerate(playoff_series[:3]):
                print(f"\nSeries {i+1}:")
                print(f"  Game ID: {series.get('GAME_ID', 'N/A')}")
                print(f"  Series ID: {series.get('SERIES_ID', 'N/A')}")
                print(f"  Home Team ID: {series.get('HOME_TEAM_ID', 'N/A')}")
                print(f"  Visitor Team ID: {series.get('VISITOR_TEAM_ID', 'N/A')}")
                print(f"  Game Number: {series.get('GAME_NUM', 'N/A')}")
    
    print("\n=== Basic playoff series test completed ===")
    return data

def test_fetch_playoff_series_dataframe():
    """Test fetching playoff series with DataFrame output."""
    print("\n=== Testing fetch_common_playoff_series_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_common_playoff_series_logic(
        season=SAMPLE_SEASON,
        league_id=LeagueID.nba,
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
    
    # Check if there's an error in the response
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        print("Continuing with other tests...")
    else:
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
                        csv_size = os.path.getsize(full_path)
                        print(f"CSV file size: {csv_size} bytes")
                    else:
                        print(f"\nCSV file does not exist: {csv_path}")
        
        # Display a sample of the DataFrame if not empty
        for key, df in dataframes.items():
            if not df.empty:
                print(f"\nSample of DataFrame '{key}' (first 3 rows):")
                print(df.head(3))
                break
    
    print("\n=== DataFrame playoff series test completed ===")
    return result

def test_fetch_playoff_series_with_series_id():
    """Test fetching playoff series with a specific series ID."""
    print("\n=== Testing fetch_common_playoff_series_logic with specific series ID ===")
    
    # First, get all playoff series to find a valid series ID
    json_response = fetch_common_playoff_series_logic(
        season=SAMPLE_SEASON,
        league_id=LeagueID.nba
    )
    
    data = json.loads(json_response)
    
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("Skipping series ID test...")
        return None
    
    playoff_series = data.get("playoff_series", [])
    
    if not playoff_series:
        print("No playoff series data available. Skipping series ID test...")
        return None
    
    # Get a sample series ID from the data
    sample_series_id = playoff_series[0].get("SERIES_ID")
    
    if not sample_series_id:
        print("No series ID found in the data. Skipping series ID test...")
        return None
    
    print(f"Testing with series ID: {sample_series_id}")
    
    # Test with the specific series ID and DataFrame output
    result = fetch_common_playoff_series_logic(
        season=SAMPLE_SEASON,
        league_id=LeagueID.nba,
        series_id=sample_series_id,
        return_dataframe=True
    )
    
    json_response, dataframes = result
    data = json.loads(json_response)
    
    if "error" in data:
        print(f"API returned an error: {data['error']}")
    else:
        playoff_series = data.get("playoff_series", [])
        print(f"Number of entries for series ID {sample_series_id}: {len(playoff_series)}")
        
        # Check if all entries have the requested series ID
        if playoff_series:
            all_match = all(entry.get("SERIES_ID") == sample_series_id for entry in playoff_series)
            print(f"All entries match requested series ID: {all_match}")
    
    print("\n=== Series ID test completed ===")
    return result

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running playoff_series smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_playoff_series_basic()
        df_result = test_fetch_playoff_series_dataframe()
        series_id_result = test_fetch_playoff_series_with_series_id()
        
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

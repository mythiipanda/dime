"""
Smoke test for the league_lineups module.
Tests the functionality of fetching league lineup statistics.
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime


from api_tools.league_lineups import (
    fetch_league_dash_lineups_logic
)
from nba_api.stats.library.parameters import (
    MeasureTypeDetailedDefense,
    PerModeDetailed,
    SeasonTypeAllStar
)

# Sample season for testing
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing

def test_fetch_league_dash_lineups_basic():
    """Test fetching league lineups with default parameters."""
    print("\n=== Testing fetch_league_dash_lineups_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_league_dash_lineups_logic(
        SAMPLE_SEASON,
        group_quantity=5,
        measure_type=MeasureTypeDetailedDefense.base,
        per_mode=PerModeDetailed.totals,
        season_type=SeasonTypeAllStar.regular
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
        
        # Print some information about the data
        print(f"Season: {data['parameters']['season']}")
        print(f"Group Quantity: {data['parameters']['group_quantity']}")
        
        # Check if lineups exist
        assert "lineups" in data, "Response should have 'lineups'"
        
        # Print some information about the lineups
        lineups = data["lineups"]
        print(f"\nNumber of lineups: {len(lineups)}")
        
        if lineups:
            print("\nSample lineup:")
            first_lineup = lineups[0]
            print(f"  GROUP_ID: {first_lineup.get('GROUP_ID', 'N/A')}")
            print(f"  GROUP_NAME: {first_lineup.get('GROUP_NAME', 'N/A')}")
            print(f"  GP: {first_lineup.get('GP', 'N/A')}")
            print(f"  MIN: {first_lineup.get('MIN', 'N/A')}")
    
    print("\n=== Basic lineups test completed ===")
    return data

def test_fetch_league_dash_lineups_dataframe():
    """Test fetching league lineups with DataFrame output."""
    print("\n=== Testing fetch_league_dash_lineups_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_league_dash_lineups_logic(
        SAMPLE_SEASON,
        group_quantity=5,
        measure_type=MeasureTypeDetailedDefense.base,
        per_mode=PerModeDetailed.totals,
        season_type=SeasonTypeAllStar.regular,
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
                full_path = os.path.join(os.getcwd(), csv_path)
                if os.path.exists(full_path):
                    print(f"\nCSV file exists: {csv_path}")
                else:
                    print(f"\nCSV file does not exist: {csv_path}")
    
    # Display a sample of the DataFrame if not empty
    if "lineups" in dataframes and not dataframes["lineups"].empty:
        print(f"\nSample of lineups DataFrame (first 3 rows):")
        print(dataframes["lineups"].head(3))
    
    print("\n=== DataFrame lineups test completed ===")
    return json_response, dataframes

def test_fetch_league_dash_lineups_advanced():
    """Test fetching league lineups with advanced measure type."""
    print("\n=== Testing fetch_league_dash_lineups_logic with advanced measure type ===")
    
    # Test with advanced measure type
    json_response = fetch_league_dash_lineups_logic(
        SAMPLE_SEASON,
        group_quantity=5,
        measure_type=MeasureTypeDetailedDefense.advanced,
        per_mode=PerModeDetailed.totals,
        season_type=SeasonTypeAllStar.regular
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
        assert data["parameters"]["measure_type"] == MeasureTypeDetailedDefense.advanced, "Measure type should be 'Advanced'"
        
        # Print some information about the data
        print(f"Season: {data['parameters']['season']}")
        print(f"Measure Type: {data['parameters']['measure_type']}")
        
        # Check if lineups exist
        assert "lineups" in data, "Response should have 'lineups'"
        
        # Print some information about the lineups
        lineups = data["lineups"]
        print(f"\nNumber of lineups: {len(lineups)}")
        
        if lineups:
            print("\nSample advanced lineup metrics:")
            first_lineup = lineups[0]
            advanced_metrics = ["OFF_RATING", "DEF_RATING", "NET_RATING", "AST_PCT", "AST_TO", "AST_RATIO"]
            for metric in advanced_metrics:
                if metric in first_lineup:
                    print(f"  {metric}: {first_lineup[metric]}")
    
    print("\n=== Advanced lineups test completed ===")
    return data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running league_lineups smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_league_dash_lineups_basic()
        df_json, df_data = test_fetch_league_dash_lineups_dataframe()
        advanced_data = test_fetch_league_dash_lineups_advanced()
        
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

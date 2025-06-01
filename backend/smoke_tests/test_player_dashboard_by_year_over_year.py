"""
Smoke test for the player_dashboard_by_year_over_year module.
Tests the functionality of fetching player dashboard statistics by year over year.
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

from api_tools.player_dashboard_by_year_over_year import (
    fetch_player_dashboard_by_year_over_year_logic,
    _get_csv_path_for_player_dashboard_by_year,
    PLAYER_DASHBOARD_BY_YEAR_CSV_DIR
)
from api_tools.utils import find_player_id_or_error

# Sample player for testing
SAMPLE_PLAYER_NAME = "LeBron James"
SAMPLE_PLAYER_ID = "2544"  # LeBron James ID
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing

def _verify_csv_exists(expected_path: str):
    """Verify that a CSV file exists at the expected path."""
    assert os.path.exists(expected_path), f"CSV file not found at {expected_path}"
    print(f"Verified CSV file exists: {expected_path}")

def test_fetch_player_dashboard_by_year_basic():
    """Test fetching player dashboard by year with basic parameters."""
    print(f"\n=== Testing fetch_player_dashboard_by_year_over_year_logic for {SAMPLE_PLAYER_NAME} ===")

    # Test JSON output with default parameters
    json_response_only = fetch_player_dashboard_by_year_over_year_logic(
        SAMPLE_PLAYER_NAME, 
        season=SAMPLE_SEASON
    )
    data_only = json.loads(json_response_only)
    assert isinstance(data_only, dict), "JSON only response should be a dictionary"
    
    if "error" in data_only:
        print(f"API (JSON only) returned an error: {data_only['error']}")
    else:
        assert "player_name" in data_only
        assert data_only["player_name"] == SAMPLE_PLAYER_NAME
        assert "season" in data_only
        assert data_only["season"] == SAMPLE_SEASON
        print(f"Dashboard by year (JSON only) fetched for {data_only.get('player_name')}")
        print(f"Data sets available: {data_only.get('data_sets', [])}")
        print(f"Total records: {data_only.get('total_records', 0)}")

    print("\n=== Basic test completed ===")
    return data_only

def test_fetch_player_dashboard_by_year_different_seasons():
    """Test fetching player dashboard by year with different seasons."""
    print(f"\n=== Testing different seasons ===")
    
    seasons = ["2021-22", "2022-23", "2023-24"]
    
    results = {}
    
    for season in seasons:
        print(f"\nTesting with season: {season}")
        json_response = fetch_player_dashboard_by_year_over_year_logic(
            SAMPLE_PLAYER_NAME,
            season=season
        )
        data = json.loads(json_response)
        
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            results[season] = "error"
        else:
            total_records = data.get("total_records", 0)
            print(f"Total records: {total_records}")
            results[season] = total_records
    
    print(f"\nSeason results: {results}")
    print("\n=== Season tests completed ===")
    return results

def test_fetch_player_dashboard_by_year_different_players():
    """Test fetching player dashboard by year for different players."""
    print(f"\n=== Testing different players ===")
    
    players = ["LeBron James", "Stephen Curry", "Kevin Durant"]
    
    results = {}
    
    for player in players:
        print(f"\nTesting with player: {player}")
        json_response = fetch_player_dashboard_by_year_over_year_logic(
            player,
            season=SAMPLE_SEASON
        )
        data = json.loads(json_response)
        
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            results[player] = "error"
        else:
            total_records = data.get("total_records", 0)
            print(f"Total records: {total_records}")
            results[player] = total_records
    
    print(f"\nPlayer results: {results}")
    print("\n=== Player tests completed ===")
    return results

def test_fetch_player_dashboard_by_year_dataframe():
    """Test fetching player dashboard by year with DataFrame output."""
    print(f"\n=== Testing DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_player_dashboard_by_year_over_year_logic(
        SAMPLE_PLAYER_NAME,
        season=SAMPLE_SEASON,
        return_dataframe=True
    )
    
    assert isinstance(result, tuple), "Result should be a tuple when return_dataframe=True"
    assert len(result) == 2, "Result tuple should have 2 elements"
    
    json_response, dataframes = result
    
    # Check if the first element is a JSON string
    assert isinstance(json_response, str), "First element should be a JSON string"
    
    # Check if the second element is a dictionary of DataFrames
    assert isinstance(dataframes, dict), "Second element should be a dictionary of DataFrames"
    
    data = json.loads(json_response)
    
    if "error" in data:
        print(f"API returned an error: {data['error']}")
    else:
        print(f"DataFrames returned: {list(dataframes.keys())}")
        player_id_for_csv = str(data.get("player_id", SAMPLE_PLAYER_ID))
        
        expected_dfs = ["by_year_player_dashboard", "overall_player_dashboard"]
        for key in expected_dfs:
            if key in dataframes:
                df = dataframes[key]
                print(f"\nDataFrame '{key}' shape: {df.shape}")
                print(f"DataFrame '{key}' columns: {df.columns.tolist()[:10]}...")  # Show first 10 columns
                
                if not df.empty:
                    print(f"Sample data from '{key}':")
                    print(df.head(2))
                    
                    # Verify CSV was created for main DataFrame
                    if key == "by_year_player_dashboard":
                        csv_path = _get_csv_path_for_player_dashboard_by_year(
                            player_id_for_csv, SAMPLE_SEASON
                        )
                        _verify_csv_exists(csv_path)
                else:
                    print(f"DataFrame '{key}' is empty.")
    
    print("\n=== DataFrame test completed ===")
    return json_response, dataframes

def test_fetch_player_dashboard_by_year_data_analysis():
    """Test analyzing the structure and content of player dashboard data."""
    print(f"\n=== Testing data analysis ===")
    
    result = fetch_player_dashboard_by_year_over_year_logic(
        SAMPLE_PLAYER_NAME,
        season=SAMPLE_SEASON,
        return_dataframe=True
    )
    
    json_response, dataframes = result
    data = json.loads(json_response)
    
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        return
    
    # Analyze by year data
    if "by_year_player_dashboard" in dataframes:
        df = dataframes["by_year_player_dashboard"]
        if not df.empty:
            print(f"By year dashboard data analysis:")
            print(f"  Total seasons: {len(df)}")
            print(f"  Columns: {df.columns.tolist()}")
            
            # Check for key columns
            key_columns = ['GROUP_SET', 'GROUP_VALUE', 'GP', 'PTS', 'REB', 'AST']
            available_key_cols = [col for col in key_columns if col in df.columns]
            print(f"  Key columns available: {available_key_cols}")
            
            if 'GROUP_VALUE' in df.columns:
                seasons = df['GROUP_VALUE'].unique()
                print(f"  Seasons covered: {sorted(seasons)}")
            
            if 'PTS' in df.columns:
                print(f"  Points range: {df['PTS'].min():.1f} - {df['PTS'].max():.1f}")
    
    # Analyze overall data
    if "overall_player_dashboard" in dataframes:
        df = dataframes["overall_player_dashboard"]
        if not df.empty:
            print(f"\nOverall dashboard data analysis:")
            print(f"  Records: {len(df)}")
            print(f"  Columns: {df.columns.tolist()}")
    
    print("\n=== Data analysis completed ===")

def test_fetch_player_dashboard_by_year_invalid_params():
    """Test fetching player dashboard by year with invalid parameters."""
    print(f"\n=== Testing invalid parameters ===")
    
    # Test with invalid player name
    json_response = fetch_player_dashboard_by_year_over_year_logic("Invalid Player Name")
    data = json.loads(json_response)
    assert "error" in data, "Should return error for invalid player name"
    print(f"Invalid player test passed: {data['error']}")
    
    # Test with invalid season format
    json_response = fetch_player_dashboard_by_year_over_year_logic(
        SAMPLE_PLAYER_NAME, season="invalid-season"
    )
    data = json.loads(json_response)
    assert "error" in data, "Should return error for invalid season format"
    print(f"Invalid season test passed: {data['error']}")
    
    print("\n=== Invalid parameters tests completed ===")

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running player_dashboard_by_year_over_year smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_player_dashboard_by_year_basic()
        season_results = test_fetch_player_dashboard_by_year_different_seasons()
        player_results = test_fetch_player_dashboard_by_year_different_players()
        json_response, dataframes = test_fetch_player_dashboard_by_year_dataframe()
        test_fetch_player_dashboard_by_year_data_analysis()
        test_fetch_player_dashboard_by_year_invalid_params()
        
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
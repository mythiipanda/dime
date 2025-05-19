"""
Smoke test for the analyze module.
Tests the functionality of fetching player analysis data with DataFrame output.
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

from backend.api_tools.analyze import (
    analyze_player_stats_logic
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed,
    LeagueID
)

# Sample player and season for testing
SAMPLE_PLAYER = "LeBron James"
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing

def test_analyze_player_stats_basic():
    """Test analyzing player stats with default parameters."""
    print("\n=== Testing analyze_player_stats_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = analyze_player_stats_logic(
        player_name=SAMPLE_PLAYER,
        season=SAMPLE_SEASON,
        season_type=SeasonTypeAllStar.regular,
        per_mode=PerModeDetailed.per_game,
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
        # Check if the player_name field exists
        assert "player_name" in data, "Response should have a 'player_name' field"
        assert "player_id" in data, "Response should have a 'player_id' field"
        assert "season" in data, "Response should have a 'season' field"
        
        # Print some information about the data
        print(f"Player Name: {data['player_name']}")
        print(f"Player ID: {data['player_id']}")
        print(f"Season: {data['season']}")
        
        # Check if overall_dashboard_stats exist
        assert "overall_dashboard_stats" in data, "Response should have 'overall_dashboard_stats'"
        
        # Print some information about the stats
        stats = data["overall_dashboard_stats"]
        if stats:
            print("\nSample stats:")
            # Print a few key stats
            if "PTS" in stats:
                print(f"  Points: {stats.get('PTS', 'N/A')}")
            if "AST" in stats:
                print(f"  Assists: {stats.get('AST', 'N/A')}")
            if "REB" in stats:
                print(f"  Rebounds: {stats.get('REB', 'N/A')}")
    
    print("\n=== Basic player analysis test completed ===")
    return data

def test_analyze_player_stats_dataframe():
    """Test analyzing player stats with DataFrame output."""
    print("\n=== Testing analyze_player_stats_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = analyze_player_stats_logic(
        player_name=SAMPLE_PLAYER,
        season=SAMPLE_SEASON,
        season_type=SeasonTypeAllStar.regular,
        per_mode=PerModeDetailed.per_game,
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
                    else:
                        print(f"\nCSV file does not exist: {csv_path}")
        
        # Display a sample of the DataFrame if not empty
        for key, df in dataframes.items():
            if not df.empty:
                print(f"\nSample of DataFrame '{key}' (first row):")
                print(df.head(1))
                break
    
    print("\n=== DataFrame player analysis test completed ===")
    return result

def test_analyze_player_stats_totals():
    """Test analyzing player stats with totals per mode."""
    print("\n=== Testing analyze_player_stats_logic with totals per mode ===")
    
    # Test with totals per mode
    json_response = analyze_player_stats_logic(
        player_name=SAMPLE_PLAYER,
        season=SAMPLE_SEASON,
        season_type=SeasonTypeAllStar.regular,
        per_mode=PerModeDetailed.totals,
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
        # Check if the per_mode parameter was correctly used
        assert data["per_mode"] == PerModeDetailed.totals, "Per mode should be Totals"
        
        # Print some information about the data
        print(f"Player Name: {data['player_name']}")
        print(f"Per Mode: {data['per_mode']}")
        
        # Check if overall_dashboard_stats exist
        assert "overall_dashboard_stats" in data, "Response should have 'overall_dashboard_stats'"
        
        # Print some information about the stats
        stats = data["overall_dashboard_stats"]
        if stats:
            print("\nSample totals stats:")
            # Print a few key stats
            if "PTS" in stats:
                print(f"  Total Points: {stats.get('PTS', 'N/A')}")
            if "AST" in stats:
                print(f"  Total Assists: {stats.get('AST', 'N/A')}")
            if "REB" in stats:
                print(f"  Total Rebounds: {stats.get('REB', 'N/A')}")
    
    print("\n=== Totals player analysis test completed ===")
    return data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running analyze smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_analyze_player_stats_basic()
        df_result = test_analyze_player_stats_dataframe()
        totals_data = test_analyze_player_stats_totals()
        
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

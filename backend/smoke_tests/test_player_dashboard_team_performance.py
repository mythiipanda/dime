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
    fetch_player_dashboard_by_team_performance_logic,
    _get_csv_path_for_team_performance,  # For verification
    PLAYER_TEAM_PERFORMANCE_CSV_DIR      # For ensuring directory exists
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailed, LeagueID
)

# Sample player for testing
SAMPLE_PLAYER_NAME = "LeBron James"
SAMPLE_PLAYER_ID = "2544" # LeBron James ID, actual ID will be resolved from response
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
DEFAULT_SEASON_TYPE = SeasonTypeAllStar.regular
DEFAULT_PER_MODE = PerModeDetailed.per_game
DEFAULT_MEASURE_TYPE = MeasureTypeDetailed.base

def _verify_csv_exists(expected_path: str):
    assert os.path.exists(expected_path), f"CSV file not found at {expected_path}"
    print(f"Verified CSV file exists: {expected_path}")

def test_fetch_player_dashboard_by_team_performance_basic():
    """Test fetching player dashboard by team performance with default parameters."""
    print("\n=== Testing fetch_player_dashboard_by_team_performance_logic (basic) ===")
    
    json_response = fetch_player_dashboard_by_team_performance_logic(
        SAMPLE_PLAYER_NAME,
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        DEFAULT_MEASURE_TYPE
    )
    data = json.loads(json_response)
    assert isinstance(data, dict), "Response should be a dictionary"
    if "error" in data:
        print(f"API returned an error: {data['error']}")
    else:
        assert "player_name" in data
        assert "team_performance_dashboards" in data
        print(f"Basic team performance fetched for {data.get('player_name')}")
    print("\n=== Basic team performance test completed ===")
    return data

def test_fetch_player_dashboard_by_team_performance_dataframe():
    """Test fetching player dashboard by team performance with DataFrame output."""
    print("\n=== Testing fetch_player_dashboard_by_team_performance_logic with DataFrame output ===")
    
    result = fetch_player_dashboard_by_team_performance_logic(
        SAMPLE_PLAYER_NAME,
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        DEFAULT_MEASURE_TYPE,
        return_dataframe=True
    )
    assert isinstance(result, tuple) and len(result) == 2
    json_response, dataframes_dict = result # Renamed dataframes to dataframes_dict to avoid conflict
    
    assert isinstance(json_response, str)
    assert isinstance(dataframes_dict, dict)
    
    data = json.loads(json_response)
    
    if "error" in data:
        print(f"API (DataFrame) returned an error: {data['error']}")
    else:
        print(f"Team performance (DataFrame) fetched for {data.get('player_name')}")
        player_id_for_csv = str(data.get("player_id", SAMPLE_PLAYER_ID))

        print(f"\nDataFrames returned: {list(dataframes_dict.keys())}")
        for key, df in dataframes_dict.items():
            if not df.empty:
                print(f"\nDataFrame '{key}' shape: {df.shape}")
                print(df.head(2))
                # Construct expected CSV path directly using the imported helper
                csv_path = _get_csv_path_for_team_performance(
                    player_id_for_csv,
                    SAMPLE_SEASON,
                    DEFAULT_SEASON_TYPE,
                    DEFAULT_PER_MODE,
                    DEFAULT_MEASURE_TYPE,
                    dashboard_type=key # The key is used as dashboard_type in main logic
                )
                _verify_csv_exists(csv_path)
            else:
                print(f"\nDataFrame '{key}' is empty.")
    
    print("\n=== DataFrame team performance test completed ===")
    return json_response, dataframes_dict

def test_fetch_player_dashboard_by_team_performance_advanced():
    """Test fetching player dashboard by team performance with advanced measure type."""
    print("\n=== Testing fetch_player_dashboard_by_team_performance_logic with advanced measure type ===")
    
    json_response = fetch_player_dashboard_by_team_performance_logic(
        SAMPLE_PLAYER_NAME,
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        MeasureTypeDetailed.advanced # Test with Advanced
    )
    data = json.loads(json_response)
    assert isinstance(data, dict)
    if "error" in data:
        print(f"API returned an error: {data['error']}")
    else:
        assert data["parameters"]["measure_type"] == MeasureTypeDetailed.advanced
        print(f"Advanced team performance fetched for {data.get('player_name')}")
    print("\n=== Advanced measure type test completed ===")
    return data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running player_dashboard_team_performance smoke tests at {datetime.now().isoformat()} ===\n")
    
    # Ensure cache directory exists
    os.makedirs(PLAYER_TEAM_PERFORMANCE_CSV_DIR, exist_ok=True)

    test_fetch_player_dashboard_by_team_performance_basic()
    test_fetch_player_dashboard_by_team_performance_dataframe()
    test_fetch_player_dashboard_by_team_performance_advanced()
        
    print("\n\n=== All player_dashboard_team_performance tests completed successfully ===")

if __name__ == "__main__":
    run_all_tests()

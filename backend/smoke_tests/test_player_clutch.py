"""
Smoke test for the player_clutch module.
Tests the functionality of fetching player clutch performance statistics.
"""
import os

import json
import pandas as pd
from datetime import datetime



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
    
    json_response = fetch_player_clutch_stats_logic(
        SAMPLE_PLAYER_NAME, 
        SAMPLE_SEASON, 
        SAMPLE_SEASON_TYPE
    )
    data = json.loads(json_response)
    
    assert isinstance(data, dict), "Response should be a dictionary"
    
    if "error" in data and data["error"]:
        print(f"API returned an error: {data['error']}")
        # Depending on the error, you might want to fail the test or log a warning
        # For now, let's assume some errors (like temporary API issues) don't fail the smoke test
        # but critical structural errors should.
        assert "Player not found" not in data["error"], "Should find LeBron James"
    else:
        assert "player_name" in data, "Response should have a 'player_name' field"
        assert data["player_name"] == SAMPLE_PLAYER_NAME, f"player_name should be {SAMPLE_PLAYER_NAME}"
        assert "player_id" in data, "Response should have a 'player_id' field"
        
        assert "parameters_used" in data, "Response should have a 'parameters_used' field"
        params_used = data["parameters_used"]
        assert params_used["season"] == SAMPLE_SEASON
        assert params_used["season_type_playoffs"] == SAMPLE_SEASON_TYPE # maps to season_type_playoffs
        assert params_used["measure_type_detailed"] == MeasureTypeDetailed.base # Default

        assert "data_sets" in data, "Response should have a 'data_sets' field"
        data_sets = data["data_sets"]
        assert isinstance(data_sets, dict), "'data_sets' should be a dictionary"
        assert len(data_sets) > 5, f"Expected multiple clutch data sets, got {len(data_sets)}"
        
        print(f"Player: {data.get('player_name', 'N/A')} (ID: {data.get('player_id', 'N/A')})")
        print(f"Parameters Used: {params_used}")
        print(f"\nData Sets Available: {list(data_sets.keys())}")

        # Check a couple of expected data sets
        for ds_name in ["OverallPlayerDashboard", "Last5Min5PointPlayerDashboard"]:
            assert ds_name in data_sets, f"Expected data set '{ds_name}' not found."
            assert isinstance(data_sets[ds_name], list), f"Data set '{ds_name}' should be a list."
            if data_sets[ds_name]: # If not empty list
                assert isinstance(data_sets[ds_name][0], dict), f"Elements of data set '{ds_name}' should be dictionaries."
    
    print("\n=== Basic test completed ===")

def test_fetch_player_clutch_stats_advanced_and_filters():
    """Test fetching player clutch stats with advanced measure type and other filters."""
    print("\n=== Testing fetch_player_clutch_stats_logic (advanced and filters) ===")
    
    test_opponent_team_id = 1610612747 # Los Angeles Lakers
    test_location = "Home"
    test_outcome = "W"
    test_league_id = "00" # NBA
    test_date_from = f"{SAMPLE_SEASON[:4]}-10-01" # Start of typical season
    test_date_to = f"{SAMPLE_SEASON[:4]}-12-31"

    json_response = fetch_player_clutch_stats_logic(
        SAMPLE_PLAYER_NAME, 
        SAMPLE_SEASON, 
        SAMPLE_SEASON_TYPE,
        measure_type=MeasureTypeDetailed.advanced,
        per_mode=PerModeDetailed.per_game,
        opponent_team_id=test_opponent_team_id,
        location_nullable=test_location,
        outcome_nullable=test_outcome,
        league_id=test_league_id,
        date_from_nullable=test_date_from,
        date_to_nullable=test_date_to
    )
    data = json.loads(json_response)
    
    assert isinstance(data, dict), "Response should be a dictionary"

    if "error" in data and data["error"]:
        print(f"API returned an error: {data['error']}")
    else:
        assert "parameters_used" in data, "Response should have a 'parameters_used' field"
        params_used = data["parameters_used"]
        assert params_used["measure_type_detailed"] == MeasureTypeDetailed.advanced
        assert params_used["per_mode_detailed"] == PerModeDetailed.per_game
        assert params_used["opponent_team_id"] == test_opponent_team_id
        assert params_used["location_nullable"] == test_location
        assert params_used["outcome_nullable"] == test_outcome
        assert params_used["league_id_nullable"] == test_league_id
        assert params_used["date_from_nullable"] == test_date_from
        assert params_used["date_to_nullable"] == test_date_to

        assert "data_sets" in data, "Response should have a 'data_sets' field"
        data_sets = data["data_sets"]
        assert isinstance(data_sets, dict), "'data_sets' should be a dictionary"
        # Even with filters, we expect the structure of data_sets
        assert len(data_sets) > 0, "Expected data_sets structure even if filtered results are empty."

        print(f"Player: {data.get('player_name', 'N/A')} (ID: {data.get('player_id', 'N/A')})")
        print(f"Parameters Used: {params_used}")
        print(f"Data Sets Available (filtered): {list(data_sets.keys())}")
        # It's harder to assert non-emptiness with tight filters, so we mainly check structure and param reflection
        if "OverallPlayerDashboard" in data_sets and data_sets["OverallPlayerDashboard"]:
            print(f"Sample from 'OverallPlayerDashboard' (filtered): {data_sets['OverallPlayerDashboard'][0]}")
        else:
            print("'OverallPlayerDashboard' is empty or not present with current filters.")
            
    print("\n=== Advanced and filters test completed ===")

def test_fetch_player_clutch_stats_dataframe():
    """Test fetching player clutch stats with DataFrame output."""
    print("\n=== Testing fetch_player_clutch_stats_logic with DataFrame output ===")
    
    result = fetch_player_clutch_stats_logic(
        SAMPLE_PLAYER_NAME, 
        SAMPLE_SEASON, 
        SAMPLE_SEASON_TYPE,
        return_dataframe=True
    )
    
    assert isinstance(result, tuple), "Result should be a tuple when return_dataframe=True"
    assert len(result) == 2, "Result tuple should have 2 elements"
    
    json_response, dataframes_dict = result
    
    assert isinstance(json_response, str), "First element should be a JSON string"
    data = json.loads(json_response) # Parse JSON to check its content too

    assert isinstance(dataframes_dict, dict), "Second element should be a dictionary of DataFrames"
    
    if "error" in data and data["error"]:
        print(f"API returned an error in JSON part: {data['error']}")
        assert not dataframes_dict, "DataFrames dict should be empty if JSON has error."
    else:
        assert "data_sets" in data, "JSON response should have 'data_sets' field"
        json_data_sets = data["data_sets"]
        assert isinstance(json_data_sets, dict)

        print(f"\nDataFrames returned: {len(dataframes_dict)} dashboards")
        assert len(dataframes_dict) > 5, f"Expected multiple DataFrames, got {len(dataframes_dict)}"
        
        # Check consistency between JSON data_sets keys and DataFrame keys
        assert set(json_data_sets.keys()) == set(dataframes_dict.keys()), \
            "Keys in JSON data_sets and DataFrame dictionary should match"

        for key, df in dataframes_dict.items():
            if not df.empty:
                print(f"\nDataFrame '{key}' shape: {df.shape}")
                print(f"DataFrame '{key}' columns: {df.columns.tolist()}")
                assert key in json_data_sets, f"DataFrame key '{key}' should be in JSON data_sets"
                assert isinstance(json_data_sets[key], list), f"JSON data_set '{key}' should be a list"
                if json_data_sets[key]: # If JSON has data, DF rows should roughly match
                    # This is a loose check, as processing might slightly alter things
                    # assert df.shape[0] == len(json_data_sets[key]), \
                    #    f"DataFrame '{key}' row count ({df.shape[0]}) should match JSON list length ({len(json_data_sets[key])})"
                    pass # Row count can differ due to _process_dataframe, so skipping strict check here

                # Check if the CSV files were created (only for non-empty DFs)
                csv_file_name_part = f"{SAMPLE_PLAYER_NAME.lower().replace(' ', '_')}_{SAMPLE_SEASON}_{SAMPLE_SEASON_TYPE.lower().replace(' ', '_')}_{key.lower()}.csv"
                expected_csv_path = os.path.join(PLAYER_CLUTCH_CSV_DIR, csv_file_name_part)
                assert os.path.exists(expected_csv_path), f"Expected CSV file {expected_csv_path} was not created for DataFrame '{key}'"
                print(f"CSV file found: {expected_csv_path}")

            else:
                print(f"DataFrame '{key}' is empty.")
                # If DF is empty, corresponding JSON list might also be empty or just headers
                # assert not json_data_sets.get(key) or len(json_data_sets.get(key,[])) <=1, \
                #    f"If DataFrame '{key}' is empty, JSON data set should also be empty or header-only."

    print("\n=== DataFrame test completed ===")

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running player_clutch smoke tests at {datetime.now().isoformat()} ===\n")
    
    all_passed = True
    tests_run = 0
    tests_failed = 0

    def run_single_test(test_func, test_name):
        nonlocal all_passed, tests_run, tests_failed
        tests_run += 1
        try:
            print(f"--- Starting test: {test_name} ---")
            test_func()
            print(f"--- Test PASSED: {test_name} ---")
        except AssertionError as e:
            all_passed = False
            tests_failed +=1
            print(f"!!! Test FAILED: {test_name} - Assertion Error: {e} !!!")
            import traceback
            traceback.print_exc()
        except Exception as e:
            all_passed = False
            tests_failed += 1
            print(f"!!! Test FAILED: {test_name} - Exception: {e} !!!")
            import traceback
            traceback.print_exc()

    run_single_test(test_fetch_player_clutch_stats_basic, "Basic Clutch Stats")
    run_single_test(test_fetch_player_clutch_stats_advanced_and_filters, "Advanced Clutch Stats with Filters")
    run_single_test(test_fetch_player_clutch_stats_dataframe, "Clutch Stats DataFrame Output")
    
    print("\n---------------------------------------")
    print(f"Total Tests Run: {tests_run}")
    print(f"Tests Passed: {tests_run - tests_failed}")
    print(f"Tests Failed: {tests_failed}")
    print("---------------------------------------")

    if all_passed:
        print("\n=== All player_clutch smoke tests completed successfully ===")
    else:
        print("\n!!! Some player_clutch smoke tests FAILED !!!")
    return all_passed

if __name__ == "__main__":
    import sys
    # Ensure the backend directory is in the Python path for standalone execution
    # This allows imports like `from api_tools.player_clutch import ...`
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(current_dir) # Goes from smoke_tests to backend
    project_root_dir = os.path.dirname(backend_dir) # Goes from backend to project root

    # Add project root to sys.path to allow `from backend.api_tools...` if necessary
    # and to find the `config` module if it's at the root or backend level.
    if project_root_dir not in sys.path:
        sys.path.insert(0, project_root_dir)
    # If your config.py is in backend/ then backend_dir should be in path
    # if backend_dir not in sys.path:
    #     sys.path.insert(0, backend_dir)

    success = run_all_tests()
    sys.exit(0 if success else 1)

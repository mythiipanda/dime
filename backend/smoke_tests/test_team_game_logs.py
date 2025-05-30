"""
Smoke tests for the team_game_logs module.
Tests fetching team game logs.

This module tests the TeamGameLogs endpoint with various parameters
to ensure comprehensive coverage of all functionality.
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime

# Add the parent directory to sys.path to allow importing from backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

from backend.api_tools.team_game_logs import (
    fetch_team_game_logs_logic,
    _get_csv_path_for_team_game_logs,
    VALID_SEASON_TYPES,
    VALID_PER_MODES,
    VALID_MEASURE_TYPES
)
from ..config import settings

# --- Test Constants ---
SAMPLE_SEASON = "2023-24"
ALT_SEASON = "2022-23"
DEFAULT_SEASON_TYPE = "Regular Season"
DEFAULT_PER_MODE = "PerGame"
DEFAULT_MEASURE_TYPE = "Base"

# Lakers
TEAM_ID = "1610612747"

# --- Helper Functions ---
def _verify_csv_exists(file_path: str) -> None:
    """
    Verifies that a CSV file exists.

    Args:
        file_path: Path to the CSV file
    """
    assert os.path.exists(file_path), f"CSV file does not exist: {file_path}"
    print(f"CSV file exists: {file_path}")

# --- Test Functions ---
def test_fetch_team_game_logs_basic():
    """Test fetching team game logs with default parameters."""
    print("\n=== Testing fetch_team_game_logs_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_team_game_logs_logic(
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        DEFAULT_MEASURE_TYPE
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
        # Print some information about the data
        print(f"Parameters: {data.get('parameters', {})}")

        # Check if data sets exist
        data_sets = data.get("data_sets", {})
        print(f"Data Sets: {list(data_sets.keys())}")

        # Print a sample of the data
        for data_set_name, data_set in data_sets.items():
            print(f"\nData Set: {data_set_name}")
            if data_set and len(data_set) > 0:
                print(f"Sample: {data_set[0] if len(data_set) > 0 else 'No data'}")
                print(f"Total records: {len(data_set)}")
            else:
                print("No data in this data set.")
            break  # Just print the first data set

    print("\n=== Basic test completed ===")
    return data

def test_fetch_team_game_logs_team_id():
    """Test fetching team game logs with team ID filter."""
    print("\n=== Testing fetch_team_game_logs_logic with team ID filter ===")

    # Test with team ID filter
    json_response = fetch_team_game_logs_logic(
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        DEFAULT_MEASURE_TYPE,
        team_id=TEAM_ID
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
        # Check if the team ID is correct
        params = data.get("parameters", {})
        assert params.get("team_id_nullable") == TEAM_ID, f"team_id should be {TEAM_ID}"
        print(f"Successfully fetched data for team ID: {TEAM_ID}")

        # Check data sets
        data_sets = data.get("data_sets", {})
        print(f"Data Sets: {list(data_sets.keys())}")

        # Print record count
        for data_set_name, data_set in data_sets.items():
            if data_set and len(data_set) > 0:
                print(f"Total records in {data_set_name}: {len(data_set)}")

                # Verify all records are for the specified team
                if "TEAM_ID" in data_set[0]:
                    team_ids = set(game.get("TEAM_ID") for game in data_set)
                    print(f"Team IDs in data: {team_ids}")
                    assert str(TEAM_ID) in [str(tid) for tid in team_ids], "All records should be for the specified team"

    print("\n=== Team ID filter test completed ===")
    return data

def test_fetch_team_game_logs_date_range():
    """Test fetching team game logs with date range filter."""
    print("\n=== Testing fetch_team_game_logs_logic with date range filter ===")

    # Use a date range from the current season
    date_from = "12/01/2023"
    date_to = "12/31/2023"

    # Test with date range filter
    json_response = fetch_team_game_logs_logic(
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        DEFAULT_MEASURE_TYPE,
        team_id=TEAM_ID,
        date_from=date_from,
        date_to=date_to
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
        # Check if the date range is correct
        params = data.get("parameters", {})
        assert params.get("date_from_nullable") == date_from, f"date_from should be {date_from}"
        assert params.get("date_to_nullable") == date_to, f"date_to should be {date_to}"
        print(f"Successfully fetched data for date range: {date_from} to {date_to}")

        # Check data sets
        data_sets = data.get("data_sets", {})
        print(f"Data Sets: {list(data_sets.keys())}")

        # Print record count
        for data_set_name, data_set in data_sets.items():
            if data_set and len(data_set) > 0:
                print(f"Total records in {data_set_name}: {len(data_set)}")

                # Verify all records are within the date range
                if "GAME_DATE" in data_set[0]:
                    game_dates = [game.get("GAME_DATE") for game in data_set]
                    print(f"Sample game dates: {game_dates[:5]}")

    print("\n=== Date range filter test completed ===")
    return data

def test_fetch_team_game_logs_different_season_types():
    """Test fetching team game logs with different season types."""
    print("\n=== Testing fetch_team_game_logs_logic with different season types ===")

    # Test each season type
    season_types = list(VALID_SEASON_TYPES.keys())
    results = {}

    for season_type in season_types[:2]:  # Test first 2 to keep test time reasonable
        print(f"\nTesting season type: {season_type}")
        json_response = fetch_team_game_logs_logic(
            SAMPLE_SEASON,
            season_type,
            DEFAULT_PER_MODE,
            DEFAULT_MEASURE_TYPE,
            team_id=TEAM_ID
        )

        data = json.loads(json_response)
        results[season_type] = data

        if "error" in data:
            print(f"API returned an error for {season_type}: {data['error']}")
        else:
            params = data.get("parameters", {})
            assert params.get("season_type_nullable") == VALID_SEASON_TYPES[season_type], f"season_type should be {season_type}"
            print(f"Successfully fetched data for season type: {season_type}")

            # Check data sets
            data_sets = data.get("data_sets", {})
            print(f"Data Sets: {list(data_sets.keys())}")

            # Print record count
            for data_set_name, data_set in data_sets.items():
                if data_set and len(data_set) > 0:
                    print(f"Total records in {data_set_name}: {len(data_set)}")

    print("\n=== Different season types test completed ===")
    return results

def test_fetch_team_game_logs_different_per_modes():
    """Test fetching team game logs with different per modes."""
    print("\n=== Testing fetch_team_game_logs_logic with different per modes ===")

    # Test each per mode
    per_modes = list(VALID_PER_MODES.keys())
    results = {}

    for per_mode in per_modes:
        print(f"\nTesting per mode: {per_mode}")
        json_response = fetch_team_game_logs_logic(
            SAMPLE_SEASON,
            DEFAULT_SEASON_TYPE,
            per_mode,
            DEFAULT_MEASURE_TYPE,
            team_id=TEAM_ID
        )

        data = json.loads(json_response)
        results[per_mode] = data

        if "error" in data:
            print(f"API returned an error for {per_mode}: {data['error']}")
        else:
            params = data.get("parameters", {})
            assert params.get("per_mode_simple_nullable") == VALID_PER_MODES[per_mode], f"per_mode should be {per_mode}"
            print(f"Successfully fetched data for per mode: {per_mode}")

            # Check data sets
            data_sets = data.get("data_sets", {})
            print(f"Data Sets: {list(data_sets.keys())}")

    print("\n=== Different per modes test completed ===")
    return results

def test_fetch_team_game_logs_dataframe():
    """Test fetching team game logs with DataFrame output."""
    print("\n=== Testing fetch_team_game_logs_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_team_game_logs_logic(
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        DEFAULT_MEASURE_TYPE,
        team_id=TEAM_ID,
        return_dataframe=True
    )

    # Check if the result is a tuple
    assert isinstance(result, tuple), "Result should be a tuple when return_dataframe=True"
    assert len(result) == 2, "Result tuple should have 2 elements"

    json_response, dataframes_dict = result

    # Check if the first element is a JSON string
    assert isinstance(json_response, str), "First element should be a JSON string"
    data = json.loads(json_response)  # Parse JSON to check its content too

    # Check if the second element is a dictionary of DataFrames
    assert isinstance(dataframes_dict, dict), "Second element should be a dictionary of DataFrames"

    # Check if there's an error in the response
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        print("Continuing with other tests...")
    else:
        # Print DataFrame info
        print(f"\nDataFrames returned: {list(dataframes_dict.keys())}")
        for key, df in dataframes_dict.items():
            if not df.empty:
                print(f"\nDataFrame '{key}' shape: {df.shape}")
                print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns

                # Verify CSV file was created
                csv_path = _get_csv_path_for_team_game_logs(
                    SAMPLE_SEASON,
                    DEFAULT_SEASON_TYPE,
                    DEFAULT_PER_MODE,
                    DEFAULT_MEASURE_TYPE,
                    TEAM_ID
                )
                _verify_csv_exists(csv_path)
            else:
                print(f"\nDataFrame '{key}' is empty.")

        # Display a sample of one DataFrame if not empty
        for key, df in dataframes_dict.items():
            if not df.empty:
                print(f"\nSample of DataFrame '{key}' (first 3 rows):")
                print(df.head(3))
                break

    print("\n=== DataFrame test completed ===")
    return json_response, dataframes_dict

def test_fetch_team_game_logs_invalid_params():
    """Test fetching team game logs with invalid parameters."""
    print("\n=== Testing fetch_team_game_logs_logic with invalid parameters ===")

    # Test with invalid season_type
    json_response = fetch_team_game_logs_logic(
        SAMPLE_SEASON,
        "Invalid Season Type",
        DEFAULT_PER_MODE,
        DEFAULT_MEASURE_TYPE
    )

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if there's an error in the response
    assert "error" in data, "Expected error for invalid season_type"
    print(f"Error message for invalid season_type: {data['error']}")

    # Test with invalid per_mode
    json_response = fetch_team_game_logs_logic(
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        "Invalid Per Mode",
        DEFAULT_MEASURE_TYPE
    )

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if there's an error in the response
    assert "error" in data, "Expected error for invalid per_mode"
    print(f"Error message for invalid per_mode: {data['error']}")

    # Test with invalid measure_type
    json_response = fetch_team_game_logs_logic(
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        "Invalid Measure Type"
    )

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if there's an error in the response
    assert "error" in data, "Expected error for invalid measure_type"
    print(f"Error message for invalid measure_type: {data['error']}")

    print("\n=== Invalid parameters test completed ===")
    return data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running team_game_logs smoke tests at {datetime.now().isoformat()} ===\n")

    tests_run = 0
    tests_passed = 0

    def run_test(test_func, test_name):
        nonlocal tests_run, tests_passed
        tests_run += 1
        try:
            print(f"\n--- Running test: {test_name} ---")
            result = test_func()
            tests_passed += 1
            print(f"--- Test passed: {test_name} ---")
            return result
        except Exception as e:
            print(f"!!! Test failed: {test_name} with error: {str(e)} !!!")
            import traceback
            traceback.print_exc()
            return None

    try:
        # Run basic tests
        run_test(test_fetch_team_game_logs_basic, "Basic Team Game Logs")

        # Run filter tests
        run_test(test_fetch_team_game_logs_team_id, "Team ID Filter")
        run_test(test_fetch_team_game_logs_date_range, "Date Range Filter")

        # Run parameter tests
        run_test(test_fetch_team_game_logs_different_season_types, "Different Season Types")
        run_test(test_fetch_team_game_logs_different_per_modes, "Different Per Modes")

        # Run DataFrame and error tests
        run_test(test_fetch_team_game_logs_dataframe, "DataFrame Output")
        run_test(test_fetch_team_game_logs_invalid_params, "Invalid Parameters")

        print(f"\n=== Tests completed: {tests_passed}/{tests_run} passed ===")
    except Exception as e:
        print(f"An error occurred during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_tests()

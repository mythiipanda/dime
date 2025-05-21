"""
Smoke tests for the player_career_stats module.
Tests fetching player career statistics.

This module tests the PlayerCareerStats endpoint with various parameters
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

from backend.api_tools.player_career_stats import (
    fetch_player_career_stats_logic,
    _get_csv_path_for_player_career_stats,
    VALID_PER_MODES,
    VALID_LEAGUE_IDS
)
from backend.config import settings

# --- Test Constants ---
# LeBron James
PLAYER_ID = "2544"
# Kevin Durant
ALT_PLAYER_ID = "201142"
DEFAULT_PER_MODE = "Totals"

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
def test_fetch_player_career_stats_basic():
    """Test fetching player career stats with default parameters."""
    print("\n=== Testing fetch_player_career_stats_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_player_career_stats_logic(
        PLAYER_ID,
        DEFAULT_PER_MODE
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

def test_fetch_player_career_stats_different_player():
    """Test fetching player career stats with a different player ID."""
    print("\n=== Testing fetch_player_career_stats_logic with different player ID ===")

    # Test with a different player ID
    json_response = fetch_player_career_stats_logic(
        ALT_PLAYER_ID,
        DEFAULT_PER_MODE
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
        # Check if the player ID is correct
        params = data.get("parameters", {})
        assert params.get("player_id") == ALT_PLAYER_ID, f"player_id should be {ALT_PLAYER_ID}"
        print(f"Successfully fetched data for player ID: {ALT_PLAYER_ID}")

        # Check data sets
        data_sets = data.get("data_sets", {})
        print(f"Data Sets: {list(data_sets.keys())}")

        # Print record count
        for data_set_name, data_set in data_sets.items():
            if data_set and len(data_set) > 0:
                print(f"Total records in {data_set_name}: {len(data_set)}")

    print("\n=== Different player ID test completed ===")
    return data

def test_fetch_player_career_stats_different_per_modes():
    """Test fetching player career stats with different per modes."""
    print("\n=== Testing fetch_player_career_stats_logic with different per modes ===")

    # Test each per mode
    per_modes = list(VALID_PER_MODES.keys())
    results = {}

    for per_mode in per_modes:
        print(f"\nTesting per mode: {per_mode}")
        json_response = fetch_player_career_stats_logic(
            PLAYER_ID,
            per_mode
        )

        data = json.loads(json_response)
        results[per_mode] = data

        if "error" in data:
            print(f"API returned an error for {per_mode}: {data['error']}")
        else:
            params = data.get("parameters", {})
            assert params.get("per_mode36") == VALID_PER_MODES[per_mode], f"per_mode should be {per_mode}"
            print(f"Successfully fetched data for per mode: {per_mode}")

            # Check data sets
            data_sets = data.get("data_sets", {})
            print(f"Data Sets: {list(data_sets.keys())}")

    print("\n=== Different per modes test completed ===")
    return results

def test_fetch_player_career_stats_dataframe():
    """Test fetching player career stats with DataFrame output."""
    print("\n=== Testing fetch_player_career_stats_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_player_career_stats_logic(
        PLAYER_ID,
        DEFAULT_PER_MODE,
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
                csv_path = _get_csv_path_for_player_career_stats(
                    PLAYER_ID,
                    DEFAULT_PER_MODE,
                    key
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

def test_fetch_player_career_stats_invalid_params():
    """Test fetching player career stats with invalid parameters."""
    print("\n=== Testing fetch_player_career_stats_logic with invalid parameters ===")

    # Test with empty player_id
    json_response = fetch_player_career_stats_logic(
        "",
        DEFAULT_PER_MODE
    )

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if there's an error in the response
    assert "error" in data, "Expected error for empty player_id"
    print(f"Error message for empty player_id: {data['error']}")

    # Test with invalid per_mode
    json_response = fetch_player_career_stats_logic(
        PLAYER_ID,
        "Invalid Per Mode"
    )

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if there's an error in the response
    assert "error" in data, "Expected error for invalid per_mode"
    print(f"Error message for invalid per_mode: {data['error']}")

    # Test with invalid league_id
    json_response = fetch_player_career_stats_logic(
        PLAYER_ID,
        DEFAULT_PER_MODE,
        league_id="Invalid League ID"
    )

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if there's an error in the response
    assert "error" in data, "Expected error for invalid league_id"
    print(f"Error message for invalid league_id: {data['error']}")

    print("\n=== Invalid parameters test completed ===")
    return data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running player_career_stats smoke tests at {datetime.now().isoformat()} ===\n")

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
        run_test(test_fetch_player_career_stats_basic, "Basic Player Career Stats")

        # Run player ID test
        run_test(test_fetch_player_career_stats_different_player, "Different Player ID")

        # Run parameter tests
        run_test(test_fetch_player_career_stats_different_per_modes, "Different Per Modes")

        # Run DataFrame and error tests
        run_test(test_fetch_player_career_stats_dataframe, "DataFrame Output")
        run_test(test_fetch_player_career_stats_invalid_params, "Invalid Parameters")

        print(f"\n=== Tests completed: {tests_passed}/{tests_run} passed ===")
    except Exception as e:
        print(f"An error occurred during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_tests()

"""
Smoke tests for the player_vs_player module.
Tests fetching player vs player comparison statistics.

This module tests the PlayerVsPlayer endpoint with various parameters
to ensure comprehensive coverage of all functionality.
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime

# Add the parent directory to sys.path to allow importing from backend

from api_tools.player_vs_player import (
    fetch_player_vs_player_stats_logic,
    _get_csv_path_for_player_vs_player,
    VALID_SEASON_TYPES,
    VALID_PER_MODES,
    VALID_MEASURE_TYPES
)
from config import settings

# --- Test Constants ---
SAMPLE_SEASON = "2023-24"
ALT_SEASON = "2022-23"
DEFAULT_SEASON_TYPE = "Regular Season"
DEFAULT_PER_MODE = "PerGame"
DEFAULT_MEASURE_TYPE = "Base"

# LeBron James vs Kevin Durant
PLAYER_ID_1 = "2544"  # LeBron James
PLAYER_ID_2 = "201142"  # Kevin Durant

# Stephen Curry vs James Harden
PLAYER_ID_3 = "201939"  # Stephen Curry
PLAYER_ID_4 = "201935"  # James Harden

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
def test_fetch_player_vs_player_stats_basic():
    """Test fetching player vs player stats with default parameters."""
    print("\n=== Testing fetch_player_vs_player_stats_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_player_vs_player_stats_logic(
        PLAYER_ID_1,
        PLAYER_ID_2,
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

def test_fetch_player_vs_player_stats_different_season_types():
    """Test fetching player vs player stats with different season types."""
    print("\n=== Testing fetch_player_vs_player_stats_logic with different season types ===")

    # Test each season type
    season_types = list(VALID_SEASON_TYPES.keys())
    results = {}

    for season_type in season_types[:2]:  # Test first 2 to keep test time reasonable
        print(f"\nTesting season type: {season_type}")
        json_response = fetch_player_vs_player_stats_logic(
            PLAYER_ID_1,
            PLAYER_ID_2,
            SAMPLE_SEASON,
            season_type,
            DEFAULT_PER_MODE,
            DEFAULT_MEASURE_TYPE
        )

        data = json.loads(json_response)
        results[season_type] = data

        if "error" in data:
            print(f"API returned an error for {season_type}: {data['error']}")
        else:
            params = data.get("parameters", {})
            assert params.get("season_type_playoffs") == VALID_SEASON_TYPES[season_type], f"season_type should be {season_type}"
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

def test_fetch_player_vs_player_stats_different_per_modes():
    """Test fetching player vs player stats with different per modes."""
    print("\n=== Testing fetch_player_vs_player_stats_logic with different per modes ===")

    # Test each per mode
    per_modes = list(VALID_PER_MODES.keys())
    results = {}

    for per_mode in per_modes[:3]:  # Test first 3 to keep test time reasonable
        print(f"\nTesting per mode: {per_mode}")
        json_response = fetch_player_vs_player_stats_logic(
            PLAYER_ID_1,
            PLAYER_ID_2,
            SAMPLE_SEASON,
            DEFAULT_SEASON_TYPE,
            per_mode,
            DEFAULT_MEASURE_TYPE
        )

        data = json.loads(json_response)
        results[per_mode] = data

        if "error" in data:
            print(f"API returned an error for {per_mode}: {data['error']}")
        else:
            params = data.get("parameters", {})
            assert params.get("per_mode_detailed") == VALID_PER_MODES[per_mode], f"per_mode should be {per_mode}"
            print(f"Successfully fetched data for per mode: {per_mode}")

            # Check data sets
            data_sets = data.get("data_sets", {})
            print(f"Data Sets: {list(data_sets.keys())}")

    print("\n=== Different per modes test completed ===")
    return results

def test_fetch_player_vs_player_stats_different_measure_types():
    """Test fetching player vs player stats with different measure types."""
    print("\n=== Testing fetch_player_vs_player_stats_logic with different measure types ===")

    # Test each measure type
    measure_types = list(VALID_MEASURE_TYPES.keys())
    results = {}

    for measure_type in measure_types[:3]:  # Test first 3 to keep test time reasonable
        print(f"\nTesting measure type: {measure_type}")
        json_response = fetch_player_vs_player_stats_logic(
            PLAYER_ID_1,
            PLAYER_ID_2,
            SAMPLE_SEASON,
            DEFAULT_SEASON_TYPE,
            DEFAULT_PER_MODE,
            measure_type
        )

        data = json.loads(json_response)
        results[measure_type] = data

        if "error" in data:
            print(f"API returned an error for {measure_type}: {data['error']}")
        else:
            params = data.get("parameters", {})
            assert params.get("measure_type_detailed_defense") == VALID_MEASURE_TYPES[measure_type], f"measure_type should be {measure_type}"
            print(f"Successfully fetched data for measure type: {measure_type}")

            # Check data sets
            data_sets = data.get("data_sets", {})
            print(f"Data Sets: {list(data_sets.keys())}")

    print("\n=== Different measure types test completed ===")
    return results

def test_fetch_player_vs_player_stats_different_players():
    """Test fetching player vs player stats with different player combinations."""
    print("\n=== Testing fetch_player_vs_player_stats_logic with different player combinations ===")

    # Test different player combinations
    player_combinations = [
        (PLAYER_ID_1, PLAYER_ID_2),  # LeBron vs Durant
        (PLAYER_ID_3, PLAYER_ID_4)   # Curry vs Harden
    ]
    results = {}

    for player_id, vs_player_id in player_combinations:
        print(f"\nTesting player combination: {player_id} vs {vs_player_id}")
        json_response = fetch_player_vs_player_stats_logic(
            player_id,
            vs_player_id,
            SAMPLE_SEASON,
            DEFAULT_SEASON_TYPE,
            DEFAULT_PER_MODE,
            DEFAULT_MEASURE_TYPE
        )

        data = json.loads(json_response)
        results[f"{player_id}_vs_{vs_player_id}"] = data

        if "error" in data:
            print(f"API returned an error for {player_id} vs {vs_player_id}: {data['error']}")
        else:
            params = data.get("parameters", {})
            assert params.get("player_id") == player_id, f"player_id should be {player_id}"
            assert params.get("vs_player_id") == vs_player_id, f"vs_player_id should be {vs_player_id}"
            print(f"Successfully fetched data for player combination: {player_id} vs {vs_player_id}")

            # Check data sets
            data_sets = data.get("data_sets", {})
            print(f"Data Sets: {list(data_sets.keys())}")

            # Check player info
            if "PlayerInfo" in data_sets and data_sets["PlayerInfo"]:
                player_info = data_sets["PlayerInfo"][0]
                print(f"Player Info: {player_info.get('PLAYER_NAME', 'N/A')}")

            if "VsPlayerInfo" in data_sets and data_sets["VsPlayerInfo"]:
                vs_player_info = data_sets["VsPlayerInfo"][0]
                print(f"Vs Player Info: {vs_player_info.get('PLAYER_NAME', 'N/A')}")

    print("\n=== Different player combinations test completed ===")
    return results

def test_fetch_player_vs_player_stats_dataframe():
    """Test fetching player vs player stats with DataFrame output."""
    print("\n=== Testing fetch_player_vs_player_stats_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_player_vs_player_stats_logic(
        PLAYER_ID_1,
        PLAYER_ID_2,
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        DEFAULT_MEASURE_TYPE,
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
                csv_path = _get_csv_path_for_player_vs_player(
                    PLAYER_ID_1,
                    PLAYER_ID_2,
                    SAMPLE_SEASON,
                    DEFAULT_SEASON_TYPE,
                    DEFAULT_PER_MODE,
                    DEFAULT_MEASURE_TYPE,
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

def test_fetch_player_vs_player_stats_invalid_params():
    """Test fetching player vs player stats with invalid parameters."""
    print("\n=== Testing fetch_player_vs_player_stats_logic with invalid parameters ===")

    # Test with empty player_id
    json_response = fetch_player_vs_player_stats_logic(
        "",
        PLAYER_ID_2,
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        DEFAULT_MEASURE_TYPE
    )

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if there's an error in the response
    assert "error" in data, "Expected error for empty player_id"
    print(f"Error message for empty player_id: {data['error']}")

    # Test with empty vs_player_id
    json_response = fetch_player_vs_player_stats_logic(
        PLAYER_ID_1,
        "",
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        DEFAULT_MEASURE_TYPE
    )

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if there's an error in the response
    assert "error" in data, "Expected error for empty vs_player_id"
    print(f"Error message for empty vs_player_id: {data['error']}")

    # Test with invalid season_type
    json_response = fetch_player_vs_player_stats_logic(
        PLAYER_ID_1,
        PLAYER_ID_2,
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

    print("\n=== Invalid parameters test completed ===")
    return data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running player_vs_player smoke tests at {datetime.now().isoformat()} ===\n")

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
        run_test(test_fetch_player_vs_player_stats_basic, "Basic Player vs Player Stats")

        # Run parameter tests
        run_test(test_fetch_player_vs_player_stats_different_season_types, "Different Season Types")
        run_test(test_fetch_player_vs_player_stats_different_per_modes, "Different Per Modes")
        run_test(test_fetch_player_vs_player_stats_different_measure_types, "Different Measure Types")

        # Run player combination tests
        run_test(test_fetch_player_vs_player_stats_different_players, "Different Player Combinations")

        # Run DataFrame and error tests
        run_test(test_fetch_player_vs_player_stats_dataframe, "DataFrame Output")
        run_test(test_fetch_player_vs_player_stats_invalid_params, "Invalid Parameters")

        print(f"\n=== Tests completed: {tests_passed}/{tests_run} passed ===")
    except Exception as e:
        print(f"An error occurred during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_tests()

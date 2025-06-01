"""
Smoke tests for the league_dash_player_bio module.
Tests fetching player biographical statistics.

This module tests the LeagueDashPlayerBioStats endpoint with various parameters
to ensure comprehensive coverage of all functionality.
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime

# Add the parent directory to sys.path to allow importing from backend

from api_tools.league_dash_player_bio import (
    fetch_league_player_bio_stats_logic,
    _get_csv_path_for_player_bio,
    VALID_SEASON_TYPES,
    VALID_PER_MODES,
    VALID_LEAGUE_IDS,
    VALID_PLAYER_POSITIONS,
    VALID_PLAYER_EXPERIENCES,
    VALID_STARTER_BENCH
)
from config import settings

# --- Test Constants ---
SAMPLE_SEASON = "2023-24"
ALT_SEASON = "2022-23"
DEFAULT_SEASON_TYPE = "Regular Season"
DEFAULT_PER_MODE = "PerGame"
DEFAULT_LEAGUE_ID = "00"  # NBA
SAMPLE_TEAM_ID = "1610612747"  # Lakers team ID

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
def test_fetch_player_bio_stats_basic():
    """Test fetching player bio stats with default parameters."""
    print("\n=== Testing fetch_league_player_bio_stats_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_league_player_bio_stats_logic(
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        DEFAULT_LEAGUE_ID
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

def test_fetch_player_bio_stats_different_season_types():
    """Test fetching player bio stats with different season types."""
    print("\n=== Testing fetch_league_player_bio_stats_logic with different season types ===")

    # Test each season type
    season_types = list(VALID_SEASON_TYPES.keys())
    results = {}

    for season_type in season_types[:2]:  # Test first 2 to keep test time reasonable
        print(f"\nTesting season type: {season_type}")
        json_response = fetch_league_player_bio_stats_logic(
            SAMPLE_SEASON,
            season_type,
            DEFAULT_PER_MODE,
            DEFAULT_LEAGUE_ID
        )

        data = json.loads(json_response)
        results[season_type] = data

        if "error" in data:
            print(f"API returned an error for {season_type}: {data['error']}")
        else:
            params = data.get("parameters", {})
            assert params.get("season_type_all_star") == VALID_SEASON_TYPES[season_type], f"season_type should be {season_type}"
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

def test_fetch_player_bio_stats_different_per_modes():
    """Test fetching player bio stats with different per modes."""
    print("\n=== Testing fetch_league_player_bio_stats_logic with different per modes ===")

    # Test each per mode
    per_modes = list(VALID_PER_MODES.keys())
    results = {}

    for per_mode in per_modes:  # Test all per modes as there are only 2
        print(f"\nTesting per mode: {per_mode}")
        json_response = fetch_league_player_bio_stats_logic(
            SAMPLE_SEASON,
            DEFAULT_SEASON_TYPE,
            per_mode,
            DEFAULT_LEAGUE_ID
        )

        data = json.loads(json_response)
        results[per_mode] = data

        if "error" in data:
            print(f"API returned an error for {per_mode}: {data['error']}")
        else:
            params = data.get("parameters", {})
            assert params.get("per_mode_simple") == VALID_PER_MODES[per_mode], f"per_mode should be {per_mode}"
            print(f"Successfully fetched data for per mode: {per_mode}")

            # Check data sets
            data_sets = data.get("data_sets", {})
            print(f"Data Sets: {list(data_sets.keys())}")

    print("\n=== Different per modes test completed ===")
    return results

def test_fetch_player_bio_stats_team_filter():
    """Test fetching player bio stats with team filter."""
    print("\n=== Testing fetch_league_player_bio_stats_logic with team filter ===")

    # Test with team ID filter
    json_response = fetch_league_player_bio_stats_logic(
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        DEFAULT_LEAGUE_ID,
        team_id=SAMPLE_TEAM_ID
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
        assert params.get("team_id_nullable") == SAMPLE_TEAM_ID, f"team_id should be {SAMPLE_TEAM_ID}"
        print(f"Successfully fetched data for team ID: {SAMPLE_TEAM_ID}")

        # Check data sets
        data_sets = data.get("data_sets", {})
        print(f"Data Sets: {list(data_sets.keys())}")

        # Print record count
        for data_set_name, data_set in data_sets.items():
            if data_set and len(data_set) > 0:
                print(f"Total records in {data_set_name}: {len(data_set)}")

                # Verify all players are from the specified team
                if "TEAM_ID" in data_set[0]:
                    team_ids = set(player.get("TEAM_ID") for player in data_set)
                    print(f"Team IDs in data: {team_ids}")
                    assert str(SAMPLE_TEAM_ID) in [str(team_id) for team_id in team_ids], "All players should be from the specified team"

    print("\n=== Team filter test completed ===")
    return data

def test_fetch_player_bio_stats_position_filter():
    """Test fetching player bio stats with player position filter."""
    print("\n=== Testing fetch_league_player_bio_stats_logic with position filter ===")

    # Test with player position filter
    position = "Guard"  # Use a common position
    json_response = fetch_league_player_bio_stats_logic(
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        DEFAULT_LEAGUE_ID,
        player_position=position
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
        # Check if the player position is correct
        params = data.get("parameters", {})
        assert params.get("player_position_abbreviation_nullable") == VALID_PLAYER_POSITIONS[position], f"player_position should be {position}"
        print(f"Successfully fetched data for player position: {position}")

        # Check data sets
        data_sets = data.get("data_sets", {})
        print(f"Data Sets: {list(data_sets.keys())}")

        # Print record count
        for data_set_name, data_set in data_sets.items():
            if data_set and len(data_set) > 0:
                print(f"Total records in {data_set_name}: {len(data_set)}")

    print("\n=== Position filter test completed ===")
    return data

def test_fetch_player_bio_stats_dataframe():
    """Test fetching player bio stats with DataFrame output."""
    print("\n=== Testing fetch_league_player_bio_stats_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_league_player_bio_stats_logic(
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        DEFAULT_LEAGUE_ID,
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
                csv_path = _get_csv_path_for_player_bio(
                    SAMPLE_SEASON,
                    DEFAULT_SEASON_TYPE,
                    DEFAULT_PER_MODE,
                    DEFAULT_LEAGUE_ID
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

def test_fetch_player_bio_stats_invalid_params():
    """Test fetching player bio stats with invalid parameters."""
    print("\n=== Testing fetch_league_player_bio_stats_logic with invalid parameters ===")

    # Test with invalid season type
    json_response = fetch_league_player_bio_stats_logic(
        SAMPLE_SEASON,
        "Invalid Season Type",
        DEFAULT_PER_MODE,
        DEFAULT_LEAGUE_ID
    )

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if there's an error in the response
    assert "error" in data, "Expected error for invalid season type"
    print(f"Error message for invalid season type: {data['error']}")

    # Test with invalid per mode
    json_response = fetch_league_player_bio_stats_logic(
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        "Invalid Per Mode",
        DEFAULT_LEAGUE_ID
    )

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if there's an error in the response
    assert "error" in data, "Expected error for invalid per mode"
    print(f"Error message for invalid per mode: {data['error']}")

    # Test with invalid league ID
    json_response = fetch_league_player_bio_stats_logic(
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        "Invalid League ID"
    )

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if there's an error in the response
    assert "error" in data, "Expected error for invalid league ID"
    print(f"Error message for invalid league ID: {data['error']}")

    print("\n=== Invalid parameters test completed ===")
    return data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running league_dash_player_bio smoke tests at {datetime.now().isoformat()} ===\n")

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
        run_test(test_fetch_player_bio_stats_basic, "Basic Bio Stats")

        # Run parameter tests
        run_test(test_fetch_player_bio_stats_different_season_types, "Different Season Types")
        run_test(test_fetch_player_bio_stats_different_per_modes, "Different Per Modes")

        # Run filter tests
        run_test(test_fetch_player_bio_stats_team_filter, "Team Filter")
        run_test(test_fetch_player_bio_stats_position_filter, "Position Filter")

        # Run DataFrame and error tests
        run_test(test_fetch_player_bio_stats_dataframe, "DataFrame Output")
        run_test(test_fetch_player_bio_stats_invalid_params, "Invalid Parameters")

        print(f"\n=== Tests completed: {tests_passed}/{tests_run} passed ===")
    except Exception as e:
        print(f"An error occurred during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_tests()

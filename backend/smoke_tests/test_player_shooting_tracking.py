"""
Smoke test for the player_shooting_tracking module.
Tests the functionality of fetching player shooting tracking statistics.
"""
import os

import json
import pandas as pd
from datetime import datetime



import os
import sys

# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

from api_tools.player_shooting_tracking import (
    fetch_player_shots_tracking_logic,
    PLAYER_SHOOTING_TRACKING_CSV_DIR
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeSimple
)

# Sample player name and season for testing
SAMPLE_PLAYER_NAME = "Stephen Curry"  # A player known for shooting
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular  # Regular season

def test_fetch_player_shots_tracking_basic():
    """Test fetching player shooting tracking stats with default parameters."""
    print("\n=== Testing fetch_player_shots_tracking_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_player_shots_tracking_logic(
        SAMPLE_PLAYER_NAME,
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE
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
        # Check if the player_name field exists and matches the input
        assert "player_name" in data, "Response should have a 'player_name' field"
        assert data["player_name"] == SAMPLE_PLAYER_NAME, f"player_name should be {SAMPLE_PLAYER_NAME}"

        # Check if the parameters field exists
        assert "parameters" in data, "Response should have a 'parameters' field"

        # Check if the shooting data fields exist
        assert "general_shooting" in data, "Response should have a 'general_shooting' field"
        assert "by_shot_clock" in data, "Response should have a 'by_shot_clock' field"
        assert "by_dribble_count" in data, "Response should have a 'by_dribble_count' field"
        assert "by_touch_time" in data, "Response should have a 'by_touch_time' field"
        assert "by_defender_distance" in data, "Response should have a 'by_defender_distance' field"
        assert "by_defender_distance_10ft_plus" in data, "Response should have a 'by_defender_distance_10ft_plus' field"

        # Print some information about the data
        print(f"Player: {data.get('player_name', 'N/A')} (ID: {data.get('player_id', 'N/A')})")
        print(f"Team ID: {data.get('team_id', 'N/A')}")
        print(f"Season: {data.get('parameters', {}).get('season', 'N/A')}")
        print(f"Season Type: {data.get('parameters', {}).get('season_type', 'N/A')}")
        print(f"Per Mode: {data.get('parameters', {}).get('per_mode', 'N/A')}")

        # Print general shooting stats
        if "general_shooting" in data and data["general_shooting"]:
            general = data["general_shooting"]
            print(f"\nGeneral Shooting: {len(general)} entries")
            if general:
                # Print first entry
                first_entry = general[0]
                print("Sample data (first entry):")
                for key, value in list(first_entry.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

        # Print shot clock stats
        if "by_shot_clock" in data and data["by_shot_clock"]:
            shot_clock = data["by_shot_clock"]
            print(f"\nShot Clock Shooting: {len(shot_clock)} entries")
            if shot_clock:
                # Print first entry
                first_entry = shot_clock[0]
                print("Sample data (first entry):")
                for key, value in list(first_entry.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

    print("\n=== Basic test completed ===")
    return data

def test_fetch_player_shots_tracking_per_game():
    """Test fetching player shooting tracking stats with PerGame per mode."""
    print("\n=== Testing fetch_player_shots_tracking_logic (PerGame) ===")

    # Test with PerGame per mode
    json_response = fetch_player_shots_tracking_logic(
        SAMPLE_PLAYER_NAME,
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        per_mode=PerModeSimple.per_game
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
        # Check if the per_mode parameter matches the input
        assert data.get("parameters", {}).get("per_mode") == PerModeSimple.per_game, \
            f"per_mode should be {PerModeSimple.per_game}"

        # Print some information about the data
        print(f"Player: {data.get('player_name', 'N/A')} (ID: {data.get('player_id', 'N/A')})")
        print(f"Per Mode: {data.get('parameters', {}).get('per_mode', 'N/A')}")

        # Print general shooting stats
        if "general_shooting" in data and data["general_shooting"]:
            general = data["general_shooting"]
            print(f"\nGeneral Shooting (PerGame): {len(general)} entries")
            if general:
                # Print first entry
                first_entry = general[0]
                print("Sample data (first entry):")
                for key, value in list(first_entry.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

    print("\n=== PerGame test completed ===")
    return data

def test_fetch_player_shots_tracking_with_filters():
    """Test fetching player shooting tracking stats with additional filters."""
    print("\n=== Testing fetch_player_shots_tracking_logic with filters ===")

    # Test with additional filters
    json_response = fetch_player_shots_tracking_logic(
        SAMPLE_PLAYER_NAME,
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        per_mode=PerModeSimple.per_game,
        last_n_games=10,  # Last 10 games
        location_nullable="Home"  # Only home games
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
        # Check if the parameters field exists and contains the filter values
        assert "parameters" in data, "Response should have a 'parameters' field"
        params = data["parameters"]

        # Check if the filter parameters are included in the response
        assert "last_n_games" in params, "Parameters should include 'last_n_games'"
        assert "location" in params, "Parameters should include 'location'"

        # Check if the filter values match what we provided
        assert params["last_n_games"] == 10, "last_n_games should be 10"
        assert params["location"] == "Home", "location should be 'Home'"

        # Print filter information
        print(f"Player: {data.get('player_name', 'N/A')} (ID: {data.get('player_id', 'N/A')})")
        print(f"Filters applied:")
        print(f"  Last N Games: {params.get('last_n_games', 'N/A')}")
        print(f"  Location: {params.get('location', 'N/A')}")

        # Print general shooting stats
        if "general_shooting" in data and data["general_shooting"]:
            general = data["general_shooting"]
            print(f"\nFiltered General Shooting: {len(general)} entries")
            if general:
                # Print first entry
                first_entry = general[0]
                print("Sample data (first entry):")
                for key, value in list(first_entry.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

    print("\n=== Filters test completed ===")
    return data

def test_fetch_player_shots_tracking_dataframe():
    """Test fetching player shooting tracking stats with DataFrame output."""
    print("\n=== Testing fetch_player_shots_tracking_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_player_shots_tracking_logic(
        SAMPLE_PLAYER_NAME,
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
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

    # Print DataFrame info
    print(f"\nDataFrames returned: {list(dataframes.keys())}")
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nDataFrame '{key}' shape: {df.shape}")
            print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns

    # Check if the CSV files were created
    if os.path.exists(PLAYER_SHOOTING_TRACKING_CSV_DIR):
        csv_files = [f for f in os.listdir(PLAYER_SHOOTING_TRACKING_CSV_DIR) if f.startswith(SAMPLE_PLAYER_NAME.lower().replace(" ", "_"))]
        print(f"\nCSV files created: {len(csv_files)}")
        if csv_files:
            print(f"Sample CSV files: {csv_files[:3]}...")

    # Display a sample of one DataFrame if not empty
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nSample of DataFrame '{key}' (first 3 rows):")
            print(df.head(3))
            break

    print("\n=== DataFrame test completed ===")
    return json_response, dataframes

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running player_shooting_tracking smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        basic_data = test_fetch_player_shots_tracking_basic()
        per_game_data = test_fetch_player_shots_tracking_per_game()
        filters_data = test_fetch_player_shots_tracking_with_filters()
        json_response, dataframes = test_fetch_player_shots_tracking_dataframe()

        print("\n=== All tests completed successfully ===")
        return True
    except Exception as e:
        print(f"\n!!! Test failed with error: {str(e)} !!!")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    # Add the parent directory to the Python path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    success = run_all_tests()
    sys.exit(0 if success else 1)

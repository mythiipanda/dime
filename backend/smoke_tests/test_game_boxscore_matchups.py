"""
Smoke tests for the game_boxscore_matchups module.
Tests fetching player matchup data using BoxScoreMatchupsV3 endpoint.
"""
import os
import sys
import json
import pandas as pd
from typing import Dict, Any
from datetime import datetime

# Add the parent directory to sys.path to allow importing from backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

from backend.api_tools.game_boxscore_matchups import (
    fetch_game_boxscore_matchups_logic,
    BOXSCORE_MATCHUPS_CSV_DIR
)

# Test constants
TEST_GAME_ID = "0022300001"  # Use a known game ID for testing
INVALID_GAME_ID = "invalid_id"
NONEXISTENT_GAME_ID = "9999999999"  # Valid format but doesn't exist

def test_fetch_game_boxscore_matchups_basic():
    """Test basic functionality of fetch_game_boxscore_matchups_logic."""
    print("\n=== Testing fetch_game_boxscore_matchups_logic ===")

    # Call the function
    json_response = fetch_game_boxscore_matchups_logic(TEST_GAME_ID)

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
        # Check if the game_id field exists and matches the input
        assert "game_id" in data, "Response should have a 'game_id' field"
        assert data["game_id"] == TEST_GAME_ID, f"game_id should be {TEST_GAME_ID}"

        # Check if the matchups field exists and is a list
        assert "matchups" in data, "Response should have a 'matchups' field"
        assert isinstance(data["matchups"], list), "'matchups' field should be a list"

        # Print some information about the data
        print(f"Number of matchups: {len(data['matchups'])}")

        if data["matchups"]:
            # Print details of the first matchup
            first_matchup = data["matchups"][0]
            print("\nFirst matchup details:")
            print(f"Offensive Player: {first_matchup.get('nameIOff', 'N/A')}")
            print(f"Defensive Player: {first_matchup.get('nameIDef', 'N/A')}")
            print(f"Matchup Minutes: {first_matchup.get('matchupMinutes', 'N/A')}")
            print(f"Points Scored: {first_matchup.get('playerPoints', 'N/A')}")
            print(f"FG: {first_matchup.get('matchupFieldGoalsMade', 'N/A')}/{first_matchup.get('matchupFieldGoalsAttempted', 'N/A')} ({first_matchup.get('matchupFieldGoalsPercentage', 'N/A')})")

    print("\n=== JSON test completed ===")

    return json_response

def test_fetch_game_boxscore_matchups_with_dataframe():
    """Test fetch_game_boxscore_matchups_logic with DataFrame output."""
    print("\n=== Testing fetch_game_boxscore_matchups_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_game_boxscore_matchups_logic(TEST_GAME_ID, return_dataframe=True)

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
        print(f"\nDataFrame '{key}' shape: {df.shape}")
        print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns

    # Check if the CSV files were created
    csv_files = [f for f in os.listdir(BOXSCORE_MATCHUPS_CSV_DIR) if f.startswith(TEST_GAME_ID)]
    print(f"\nCSV files created: {csv_files}")

    # Display a sample of one DataFrame if not empty
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nSample of DataFrame '{key}' (first 3 rows):")
            print(df.head(3)[['gameId', 'nameIOff', 'nameIDef', 'matchupMinutes', 'playerPoints']])
            break

    print("\n=== DataFrame test completed ===")
    return json_response, dataframes

def test_fetch_game_boxscore_matchups_invalid_id():
    """Test fetch_game_boxscore_matchups_logic with an invalid game ID."""
    print("\n=== Testing fetch_game_boxscore_matchups_logic with invalid game ID ===")

    # Call the function with an invalid game ID
    result = fetch_game_boxscore_matchups_logic(INVALID_GAME_ID)

    # Parse the JSON response
    response = json.loads(result)

    # Check for error
    assert "error" in response, "Expected error for invalid game ID"
    print(f"Error message: {response['error']}")

    print("\n=== Invalid game ID test completed ===")

def test_fetch_game_boxscore_matchups_empty_id():
    """Test fetch_game_boxscore_matchups_logic with an empty game ID."""
    print("\n=== Testing fetch_game_boxscore_matchups_logic with empty game ID ===")

    # Call the function with an empty game ID
    result = fetch_game_boxscore_matchups_logic("")

    # Parse the JSON response
    response = json.loads(result)

    # Check for error
    assert "error" in response, "Expected error for empty game ID"
    print(f"Error message: {response['error']}")

    print("\n=== Empty game ID test completed ===")

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running game_boxscore_matchups smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        json_response = test_fetch_game_boxscore_matchups_basic()
        json_response, dataframes = test_fetch_game_boxscore_matchups_with_dataframe()
        test_fetch_game_boxscore_matchups_invalid_id()
        test_fetch_game_boxscore_matchups_empty_id()

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

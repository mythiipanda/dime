"""
Smoke test for the game_boxscores module.
Tests the functionality of fetching various types of box score data for NBA games.
"""
import os
import sys # Import sys

# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

import json
import pandas as pd
from datetime import datetime



from backend.api_tools.game_boxscores import (
    fetch_boxscore_traditional_logic,
    fetch_boxscore_advanced_logic,
    fetch_boxscore_four_factors_logic,
    fetch_boxscore_usage_logic,
    fetch_boxscore_defensive_logic,
    fetch_boxscore_summary_logic,
    fetch_boxscore_misc_logic,
    fetch_boxscore_playertrack_logic,
    fetch_boxscore_scoring_logic,
    fetch_boxscore_hustle_logic,
    BOXSCORE_CSV_DIR
)

# Sample game ID for testing (2023-24 regular season game)
SAMPLE_GAME_ID = "0022300161"  # Change this to a valid game ID if needed

def test_fetch_boxscore_traditional():
    """Test fetching traditional box score data."""
    print("\n=== Testing fetch_boxscore_traditional_logic ===")

    # Test with default parameters (JSON output)
    json_response = fetch_boxscore_traditional_logic(SAMPLE_GAME_ID)

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
        assert data["game_id"] == SAMPLE_GAME_ID, f"game_id should be {SAMPLE_GAME_ID}"

        # Check if the teams field exists and is a list
        assert "teams" in data, "Response should have a 'teams' field"
        assert isinstance(data["teams"], list), "'teams' field should be a list"

        # Check if the players field exists and is a list
        assert "players" in data, "Response should have a 'players' field"
        assert isinstance(data["players"], list), "'players' field should be a list"

        # Print some information about the data
        print(f"Number of teams: {len(data['teams'])}")
        print(f"Number of players: {len(data['players'])}")

        if data["players"]:
            # Print details of the first player
            first_player = data["players"][0]
            print("\nFirst player details:")
            print(f"Player Name: {first_player.get('PLAYER_NAME', 'N/A')}")
            print(f"Team: {first_player.get('TEAM_ABBREVIATION', 'N/A')}")
            print(f"Minutes: {first_player.get('MIN', 'N/A')}")
            print(f"Points: {first_player.get('PTS', 'N/A')}")
            print(f"Rebounds: {first_player.get('REB', 'N/A')}")
            print(f"Assists: {first_player.get('AST', 'N/A')}")

    print("\n=== JSON test completed ===")

    # Test with return_dataframe=True
    print("\n=== Testing fetch_boxscore_traditional_logic with DataFrame output ===")
    result = fetch_boxscore_traditional_logic(SAMPLE_GAME_ID, return_dataframe=True)

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
    csv_files = [f for f in os.listdir(BOXSCORE_CSV_DIR) if f.startswith(SAMPLE_GAME_ID)]
    print(f"\nCSV files created: {csv_files}")

    # Display a sample of one DataFrame if not empty
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nSample of DataFrame '{key}' (first 3 rows):")
            print(df.head(3))
            break

    print("\n=== DataFrame test completed ===")
    return json_response, dataframes

def test_fetch_boxscore_advanced():
    """Test fetching advanced box score data with DataFrame output."""
    print("\n=== Testing fetch_boxscore_advanced_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_boxscore_advanced_logic(SAMPLE_GAME_ID, return_dataframe=True)

    # Check if the result is a tuple
    assert isinstance(result, tuple), "Result should be a tuple when return_dataframe=True"

    json_response, dataframes = result

    # Print DataFrame info
    print(f"\nDataFrames returned: {list(dataframes.keys())}")
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nDataFrame '{key}' shape: {df.shape}")
            print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns
            print(f"Sample data (first row):")
            # Print the first row with all columns
            first_row_dict = {col: df.iloc[0][col] for col in df.columns[:5]}  # First 5 columns
            print(first_row_dict)

    print("\n=== Advanced box score test completed ===")
    return json_response, dataframes

def test_other_boxscore_types():
    """Test fetching other types of box score data."""
    print("\n=== Testing other box score types ===")

    # Test Four Factors
    print("\nTesting Four Factors box score:")
    result = fetch_boxscore_four_factors_logic(SAMPLE_GAME_ID, return_dataframe=True)
    json_response, dataframes = result
    print(f"Four Factors DataFrames returned: {list(dataframes.keys())}")

    # Test Usage
    print("\nTesting Usage box score:")
    result = fetch_boxscore_usage_logic(SAMPLE_GAME_ID, return_dataframe=True)
    json_response, dataframes = result
    print(f"Usage DataFrames returned: {list(dataframes.keys())}")

    # Test Defensive
    print("\nTesting Defensive box score:")
    result = fetch_boxscore_defensive_logic(SAMPLE_GAME_ID, return_dataframe=True)
    json_response, dataframes = result
    print(f"Defensive DataFrames returned: {list(dataframes.keys())}")

    # Test Summary
    print("\nTesting Summary box score:")
    result = fetch_boxscore_summary_logic(SAMPLE_GAME_ID, return_dataframe=True)
    json_response, dataframes = result
    print(f"Summary DataFrames returned: {list(dataframes.keys())}")

    # Check CSV files
    csv_files = [f for f in os.listdir(BOXSCORE_CSV_DIR) if f.startswith(SAMPLE_GAME_ID)]
    print(f"\nTotal CSV files created: {len(csv_files)}")
    print(f"CSV files: {csv_files[:5]}...")  # Show first 5 files

    print("\n=== Other box score types test completed ===")

def test_fetch_boxscore_misc():
    """Test fetching miscellaneous box score data with DataFrame output."""
    print("\n=== Testing fetch_boxscore_misc_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_boxscore_misc_logic(SAMPLE_GAME_ID, return_dataframe=True)

    # Check if the result is a tuple
    assert isinstance(result, tuple), "Result should be a tuple when return_dataframe=True"

    json_response, dataframes = result

    # Print DataFrame info
    print(f"\nDataFrames returned: {list(dataframes.keys())}")
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nDataFrame '{key}' shape: {df.shape}")
            print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns
            print(f"Sample data (first row):")
            first_row_dict = {col: df.iloc[0][col] for col in df.columns[:5]}  # First 5 columns
            print(first_row_dict)

    print("\n=== Miscellaneous box score test completed ===")
    return json_response, dataframes

def test_fetch_boxscore_playertrack():
    """Test fetching player tracking box score data with DataFrame output."""
    print("\n=== Testing fetch_boxscore_playertrack_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_boxscore_playertrack_logic(SAMPLE_GAME_ID, return_dataframe=True)

    # Check if the result is a tuple
    assert isinstance(result, tuple), "Result should be a tuple when return_dataframe=True"

    json_response, dataframes = result

    # Print DataFrame info
    print(f"\nDataFrames returned: {list(dataframes.keys())}")
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nDataFrame '{key}' shape: {df.shape}")
            print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns
            print(f"Sample data (first row):")
            first_row_dict = {col: df.iloc[0][col] for col in df.columns[:5]}  # First 5 columns
            print(first_row_dict)

    print("\n=== Player tracking box score test completed ===")
    return json_response, dataframes

def test_fetch_boxscore_scoring():
    """Test fetching scoring box score data with DataFrame output."""
    print("\n=== Testing fetch_boxscore_scoring_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_boxscore_scoring_logic(SAMPLE_GAME_ID, return_dataframe=True)

    # Check if the result is a tuple
    assert isinstance(result, tuple), "Result should be a tuple when return_dataframe=True"

    json_response, dataframes = result

    # Print DataFrame info
    print(f"\nDataFrames returned: {list(dataframes.keys())}")
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nDataFrame '{key}' shape: {df.shape}")
            print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns
            print(f"Sample data (first row):")
            first_row_dict = {col: df.iloc[0][col] for col in df.columns[:5]}  # First 5 columns
            print(first_row_dict)

    print("\n=== Scoring box score test completed ===")
    return json_response, dataframes

def test_fetch_boxscore_hustle():
    """Test fetching hustle box score data with DataFrame output."""
    print("\n=== Testing fetch_boxscore_hustle_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_boxscore_hustle_logic(SAMPLE_GAME_ID, return_dataframe=True)

    # Check if the result is a tuple
    assert isinstance(result, tuple), "Result should be a tuple when return_dataframe=True"

    json_response, dataframes = result

    # Print DataFrame info
    print(f"\nDataFrames returned: {list(dataframes.keys())}")
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nDataFrame '{key}' shape: {df.shape}")
            print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns
            print(f"Sample data (first row):")
            first_row_dict = {col: df.iloc[0][col] for col in df.columns[:5]}  # First 5 columns
            print(first_row_dict)

    print("\n=== Hustle box score test completed ===")
    return json_response, dataframes

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running game_boxscores smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        traditional_json, traditional_dfs = test_fetch_boxscore_traditional()
        advanced_json, advanced_dfs = test_fetch_boxscore_advanced()
        test_other_boxscore_types()
        test_fetch_boxscore_misc()
        test_fetch_boxscore_playertrack()
        test_fetch_boxscore_scoring()
        hustle_json, hustle_dfs = test_fetch_boxscore_hustle()

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

"""
Smoke test for the scoreboard_tools module.
Tests the functionality of fetching scoreboard data with DataFrame output.
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime, date, timedelta

# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

from api_tools.scoreboard_tools import fetch_scoreboard_data_logic
from nba_api.stats.library.parameters import LeagueID

def test_fetch_scoreboard_data_basic():
    """Test fetching scoreboard data with default parameters."""
    print("\n=== Testing fetch_scoreboard_data_logic (basic) ===")

    # Use today's date
    test_date = date.today().strftime('%Y-%m-%d')
    print(f"Testing with date: {test_date}")

    # Test with default parameters (JSON output)
    json_response = fetch_scoreboard_data_logic(
        game_date=test_date,
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
        # Check if the key fields exist
        assert "gameDate" in data, "Response should have a 'gameDate' field"
        assert "games" in data, "Response should have a 'games' field"

        # Print some information about the data
        print(f"Game Date: {data['gameDate']}")
        games = data["games"]
        print(f"Number of games: {len(games)}")

        # Print details of the first few games
        if games:
            print("\nFirst 2 games:")
            for i, game in enumerate(games[:2]):
                print(f"\nGame {i+1}:")
                print(f"  Game ID: {game.get('gameId', 'N/A')}")
                print(f"  Status: {game.get('gameStatusText', 'N/A')}")

                home_team = game.get("homeTeam", {})
                away_team = game.get("awayTeam", {})

                print(f"  Home Team: {home_team.get('teamTricode', 'N/A')} - Score: {home_team.get('score', 'N/A')}")
                print(f"  Away Team: {away_team.get('teamTricode', 'N/A')} - Score: {away_team.get('score', 'N/A')}")

    print("\n=== Basic scoreboard data test completed ===")
    return data

def test_fetch_scoreboard_data_dataframe():
    """Test fetching scoreboard data with DataFrame output."""
    print("\n=== Testing fetch_scoreboard_data_logic with DataFrame output ===")

    # Use May 18, 2025 which had games
    test_date = "2025-05-18"  # May 18, 2025 with games
    print(f"Testing with date: {test_date}")

    # Test with return_dataframe=True
    result = fetch_scoreboard_data_logic(
        game_date=test_date,
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

        # Check if the CSV files were created
        if "dataframe_info" in data:
            for df_key, df_info in data["dataframe_info"].get("dataframes", {}).items():
                csv_path = df_info.get("csv_path")
                if csv_path:
                    full_path = os.path.join(backend_dir, csv_path)
                    if os.path.exists(full_path):
                        print(f"\nCSV file exists: {csv_path}")
                        csv_size = os.path.getsize(full_path)
                        print(f"CSV file size: {csv_size} bytes")
                    else:
                        print(f"\nCSV file does not exist: {csv_path}")

        # Display a sample of each DataFrame if not empty
        for key, df in dataframes.items():
            if not df.empty:
                print(f"\nSample of DataFrame '{key}' (first 2 rows):")
                print(df.head(2))

    print("\n=== DataFrame scoreboard data test completed ===")
    return result

def test_fetch_scoreboard_data_invalid_date():
    """Test fetching scoreboard data with an invalid date format."""
    print("\n=== Testing fetch_scoreboard_data_logic with invalid date ===")

    # Test with an invalid date format
    json_response = fetch_scoreboard_data_logic(
        game_date="invalid-date",
        league_id=LeagueID.nba
    )

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if there's an error in the response
    assert "error" in data, "Response should contain an error for invalid date format"
    print(f"Error message: {data['error']}")

    print("\n=== Invalid date test completed ===")
    return data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running scoreboard_tools smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        basic_data = test_fetch_scoreboard_data_basic()
        df_result = test_fetch_scoreboard_data_dataframe()
        invalid_date_result = test_fetch_scoreboard_data_invalid_date()

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

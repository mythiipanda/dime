"""
Smoke test for the league_game_log module.
Tests the functionality of fetching game logs for the entire league.
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime


from api_tools.league_game_log import (
    fetch_league_game_log_logic,
    LEAGUE_GAME_LOG_CSV_DIR
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, LeagueID, Direction, PlayerOrTeamAbbreviation, Sorter
)

# Sample season for testing
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular  # Regular season

def test_fetch_league_game_log_basic():
    """Test fetching game logs with default parameters."""
    print("\n=== Testing fetch_league_game_log_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_league_game_log_logic(
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
        # Check if the parameters field exists
        assert "parameters" in data, "Response should have a 'parameters' field"

        # Check if the game_log field exists
        assert "game_log" in data, "Response should have a 'game_log' field"

        # Print some information about the data
        print(f"Season: {data.get('parameters', {}).get('season', 'N/A')}")
        print(f"Season Type: {data.get('parameters', {}).get('season_type_all_star', 'N/A')}")
        print(f"Player/Team: {data.get('parameters', {}).get('player_or_team_abbreviation', 'N/A')}")

        # Print game log data
        if "game_log" in data and data["game_log"]:
            game_log = data["game_log"]
            print(f"\nGame Logs: {len(game_log)} games")
            if game_log:
                # Print first game
                first_game = game_log[0]
                print("Sample data (first game):")
                for key, value in list(first_game.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

                # Print game statistics
                print("\nGame statistics:")
                for key in ["PTS", "REB", "AST", "STL", "BLK"]:
                    if key in first_game:
                        print(f"  {key}: {first_game[key]}")

    print("\n=== Basic test completed ===")
    return data

def test_fetch_league_game_log_player():
    """Test fetching player game logs."""
    print("\n=== Testing fetch_league_game_log_logic (player game logs) ===")

    # Test with player game logs
    json_response = fetch_league_game_log_logic(
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        player_or_team=PlayerOrTeamAbbreviation.player
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
        # Check if the parameters field exists and contains the player_or_team value
        assert "parameters" in data, "Response should have a 'parameters' field"
        params = data["parameters"]

        # Check if the player_or_team_abbreviation parameter is included in the response
        assert "player_or_team_abbreviation" in params, "Parameters should include 'player_or_team_abbreviation'"

        # Check if the player_or_team_abbreviation value matches what we provided
        assert params["player_or_team_abbreviation"] == PlayerOrTeamAbbreviation.player, f"player_or_team_abbreviation should be '{PlayerOrTeamAbbreviation.player}'"

        # Print game log data
        if "game_log" in data and data["game_log"]:
            game_log = data["game_log"]
            print(f"Player Game Logs: {len(game_log)} games")
            if game_log:
                # Print first game
                first_game = game_log[0]
                print("Sample data (first game):")
                for key, value in list(first_game.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

    print("\n=== Player game logs test completed ===")
    return data

def test_fetch_league_game_log_with_filters():
    """Test fetching game logs with additional filters."""
    print("\n=== Testing fetch_league_game_log_logic with filters ===")

    # Test with additional filters
    json_response = fetch_league_game_log_logic(
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        date_from_nullable="2023-01-01",  # Only games from January 1, 2023
        date_to_nullable="2023-01-31",  # Only games until January 31, 2023
        direction=Direction.desc,  # Descending order
        sorter=Sorter.pts  # Sort by points
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
        assert "date_from_nullable" in params, "Parameters should include 'date_from_nullable'"
        assert "date_to_nullable" in params, "Parameters should include 'date_to_nullable'"
        assert "direction" in params, "Parameters should include 'direction'"
        assert "sorter" in params, "Parameters should include 'sorter'"

        # Check if the filter values match what we provided
        assert params["date_from_nullable"] == "2023-01-01", "date_from_nullable should be '2023-01-01'"
        assert params["date_to_nullable"] == "2023-01-31", "date_to_nullable should be '2023-01-31'"
        assert params["direction"] == Direction.desc, f"direction should be '{Direction.desc}'"
        assert params["sorter"] == Sorter.pts, f"sorter should be '{Sorter.pts}'"

        # Print filter information
        print(f"Filters applied:")
        print(f"  Date From: {params.get('date_from_nullable', 'N/A')}")
        print(f"  Date To: {params.get('date_to_nullable', 'N/A')}")
        print(f"  Direction: {params.get('direction', 'N/A')}")
        print(f"  Sorter: {params.get('sorter', 'N/A')}")

        # Print game log data
        if "game_log" in data and data["game_log"]:
            game_log = data["game_log"]
            print(f"\nFiltered Game Logs: {len(game_log)} games")
            if game_log:
                # Print first game
                first_game = game_log[0]
                print("Sample data (first game):")
                for key, value in list(first_game.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

                # Print points to verify sorting
                if "PTS" in first_game:
                    print(f"  Points: {first_game['PTS']}")
        else:
            print("No data returned with these filters - they may be too restrictive")

    print("\n=== Filters test completed ===")
    return data

def test_fetch_league_game_log_parameter_validation():
    """Test parameter validation in the league game log function."""
    print("\n=== Testing fetch_league_game_log_logic parameter validation ===")

    # Test with invalid season format
    print("\nTesting with invalid season format:")
    json_response = fetch_league_game_log_logic(
        "20222023",  # Invalid season format
        SAMPLE_SEASON_TYPE
    )
    data = json.loads(json_response)
    assert "error" in data, "Response should have an 'error' field for invalid season format"
    print(f"Error message: {data.get('error', 'N/A')}")

    # Test with invalid season type
    print("\nTesting with invalid season type:")
    json_response = fetch_league_game_log_logic(
        SAMPLE_SEASON,
        "Invalid Season Type"  # Invalid season type
    )
    data = json.loads(json_response)
    assert "error" in data, "Response should have an 'error' field for invalid season type"
    print(f"Error message: {data.get('error', 'N/A')}")

    # Test with invalid player_or_team
    print("\nTesting with invalid player_or_team:")
    json_response = fetch_league_game_log_logic(
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        player_or_team="X"  # Invalid player_or_team
    )
    data = json.loads(json_response)
    assert "error" in data, "Response should have an 'error' field for invalid player_or_team"
    print(f"Error message: {data.get('error', 'N/A')}")

    # Test with invalid date format
    print("\nTesting with invalid date format:")
    json_response = fetch_league_game_log_logic(
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        date_from_nullable="01/01/2023"  # Invalid date format
    )
    data = json.loads(json_response)
    assert "error" in data, "Response should have an 'error' field for invalid date format"
    print(f"Error message: {data.get('error', 'N/A')}")

    print("\n=== Parameter validation test completed ===")
    return data

def test_fetch_league_game_log_dataframe():
    """Test fetching game logs with DataFrame output."""
    print("\n=== Testing fetch_league_game_log_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_league_game_log_logic(
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
            print(f"DataFrame '{key}' columns: {df.columns.tolist()}")

    # Check if the CSV files were created
    if os.path.exists(LEAGUE_GAME_LOG_CSV_DIR):
        csv_files = [f for f in os.listdir(LEAGUE_GAME_LOG_CSV_DIR) if f.startswith("game_log")]
        print(f"\nCSV files created: {len(csv_files)}")
        if csv_files:
            print(f"Sample CSV files: {csv_files[:2]}...")

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
    print(f"=== Running league_game_log smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        test_fetch_league_game_log_basic()
        test_fetch_league_game_log_player()
        test_fetch_league_game_log_with_filters()
        test_fetch_league_game_log_parameter_validation()
        test_fetch_league_game_log_dataframe()

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

"""
Smoke test for the search module.
Tests the functionality of searching for players, teams, and games.
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime

# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

from backend.api_tools.search import (
    search_players_logic,
    search_teams_logic,
    search_games_logic
)
from nba_api.stats.library.parameters import SeasonTypeAllStar

# Sample data for testing
SAMPLE_PLAYER_QUERY = "James"  # Should match multiple players
SAMPLE_TEAM_QUERY = "Lakers"  # Should match the Los Angeles Lakers
SAMPLE_GAME_QUERY = "Lakers vs Celtics"  # Should match games between Lakers and Celtics
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular  # Regular season

def test_search_players_basic():
    """Test searching for players with default parameters."""
    print("\n=== Testing search_players_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = search_players_logic(SAMPLE_PLAYER_QUERY)

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
        # Check if the players field exists
        assert "players" in data, "Response should have a 'players' field"

        # Print player info
        if "players" in data:
            players = data["players"]
            print(f"\nFound {len(players)} players matching '{SAMPLE_PLAYER_QUERY}':")
            for i, player in enumerate(players[:5]):  # Show first 5 players
                print(f"  {i+1}. {player.get('full_name', 'N/A')} (ID: {player.get('id', 'N/A')}, Active: {player.get('is_active', 'N/A')})")

    print("\n=== Basic player search test completed ===")
    return data

def test_search_players_dataframe():
    """Test searching for players with DataFrame output."""
    print("\n=== Testing search_players_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = search_players_logic(SAMPLE_PLAYER_QUERY, return_dataframe=True)

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
        print(f"DataFrame '{key}' columns: {df.columns.tolist()}")

    # Check if the CSV files were created
    data = json.loads(json_response)
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

    # Display a sample of one DataFrame if not empty
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nSample of DataFrame '{key}' (first 3 rows):")
            print(df.head(3))
            break

    print("\n=== DataFrame player search test completed ===")
    return json_response, dataframes

def test_search_teams_basic():
    """Test searching for teams with default parameters."""
    print("\n=== Testing search_teams_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = search_teams_logic(SAMPLE_TEAM_QUERY)

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
        # Check if the teams field exists
        assert "teams" in data, "Response should have a 'teams' field"

        # Print team info
        if "teams" in data:
            teams = data["teams"]
            print(f"\nFound {len(teams)} teams matching '{SAMPLE_TEAM_QUERY}':")
            for i, team in enumerate(teams):
                print(f"  {i+1}. {team.get('full_name', 'N/A')} ({team.get('abbreviation', 'N/A')}, ID: {team.get('id', 'N/A')})")

    print("\n=== Basic team search test completed ===")
    return data

def test_search_teams_dataframe():
    """Test searching for teams with DataFrame output."""
    print("\n=== Testing search_teams_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = search_teams_logic(SAMPLE_TEAM_QUERY, return_dataframe=True)

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
        print(f"DataFrame '{key}' columns: {df.columns.tolist()}")

    # Check if the CSV files were created
    data = json.loads(json_response)
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

    # Display a sample of one DataFrame if not empty
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nSample of DataFrame '{key}' (first 3 rows):")
            print(df.head(3))
            break

    print("\n=== DataFrame team search test completed ===")
    return json_response, dataframes

def test_search_games_basic():
    """Test searching for games with default parameters."""
    print("\n=== Testing search_games_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = search_games_logic(SAMPLE_GAME_QUERY, SAMPLE_SEASON, SAMPLE_SEASON_TYPE)

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
        # Check if the games field exists
        assert "games" in data, "Response should have a 'games' field"

        # Print game info
        if "games" in data:
            games = data["games"]
            print(f"\nFound {len(games)} games matching '{SAMPLE_GAME_QUERY}' in {SAMPLE_SEASON} {SAMPLE_SEASON_TYPE}:")
            for i, game in enumerate(games[:3]):  # Show first 3 games
                print(f"\nGame {i+1}:")
                print(f"  Date: {game.get('GAME_DATE', 'N/A')}")
                print(f"  Matchup: {game.get('MATCHUP', 'N/A')}")
                print(f"  Result: {game.get('WL', 'N/A')}")
                print(f"  Points: {game.get('PTS', 'N/A')}")

    print("\n=== Basic game search test completed ===")
    return data

def test_search_games_dataframe():
    """Test searching for games with DataFrame output."""
    print("\n=== Testing search_games_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = search_games_logic(SAMPLE_GAME_QUERY, SAMPLE_SEASON, SAMPLE_SEASON_TYPE, return_dataframe=True)

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
    data = json.loads(json_response)
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

    # Display a sample of one DataFrame if not empty
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nSample of DataFrame '{key}' (first 3 rows):")
            print(df.head(3))
            break

    print("\n=== DataFrame game search test completed ===")
    return json_response, dataframes

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running search smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        player_data = test_search_players_basic()
        player_json, player_dataframes = test_search_players_dataframe()

        team_data = test_search_teams_basic()
        team_json, team_dataframes = test_search_teams_dataframe()

        game_data = test_search_games_basic()
        game_json, game_dataframes = test_search_games_dataframe()

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

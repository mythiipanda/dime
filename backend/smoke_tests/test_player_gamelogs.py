"""
Smoke test for the player_gamelogs module.
Tests the functionality of fetching player game logs for a specific season and season type.
"""
import os
import sys
import json
from datetime import datetime

# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

from api_tools.player_gamelogs import (
    fetch_player_gamelog_logic,
    PLAYER_GAMELOG_CSV_DIR
)
from nba_api.stats.library.parameters import SeasonTypeAllStar

# Sample player name and season for testing
SAMPLE_PLAYER_NAME = "LeBron James"  # A well-known player with a long career
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular  # Regular season

def test_fetch_player_gamelog_basic():
    """Test fetching player game logs with default parameters."""
    print("\n=== Testing fetch_player_gamelog_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_player_gamelog_logic(SAMPLE_PLAYER_NAME, SAMPLE_SEASON, SAMPLE_SEASON_TYPE)

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

        # Check if the season field exists and matches the input
        assert "season" in data, "Response should have a 'season' field"
        assert data["season"] == SAMPLE_SEASON, f"season should be {SAMPLE_SEASON}"

        # Check if the season_type field exists and matches the input
        assert "season_type" in data, "Response should have a 'season_type' field"
        assert data["season_type"] == SAMPLE_SEASON_TYPE, f"season_type should be {SAMPLE_SEASON_TYPE}"

        # Print some information about the data
        print(f"Player: {data.get('player_name', 'N/A')} (ID: {data.get('player_id', 'N/A')})")
        print(f"Season: {data.get('season', 'N/A')}")
        print(f"Season Type: {data.get('season_type', 'N/A')}")

        # Print game log
        if "gamelog" in data:
            gamelog = data["gamelog"]
            print(f"\nGame Log: {len(gamelog)} games")
            if gamelog:
                print("\nFirst 3 games:")
                for i, game in enumerate(gamelog[:3]):
                    print(f"\nGame {i+1}:")
                    print(f"  Date: {game.get('GAME_DATE', 'N/A')}")
                    print(f"  Matchup: {game.get('MATCHUP', 'N/A')}")
                    print(f"  Result: {game.get('WL', 'N/A')}")
                    print(f"  Points: {game.get('PTS', 'N/A')}")
                    print(f"  Rebounds: {game.get('REB', 'N/A')}")
                    print(f"  Assists: {game.get('AST', 'N/A')}")

    print("\n=== Basic test completed ===")
    return data

def test_fetch_player_gamelog_playoffs():
    """Test fetching player game logs for playoffs."""
    print("\n=== Testing fetch_player_gamelog_logic (playoffs) ===")

    # Test with playoffs season type
    json_response = fetch_player_gamelog_logic(SAMPLE_PLAYER_NAME, SAMPLE_SEASON, SeasonTypeAllStar.playoffs)

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
        # Check if the season_type field exists and matches the input
        assert "season_type" in data, "Response should have a 'season_type' field"
        assert data["season_type"] == SeasonTypeAllStar.playoffs, f"season_type should be {SeasonTypeAllStar.playoffs}"

        # Print some information about the data
        print(f"Player: {data.get('player_name', 'N/A')} (ID: {data.get('player_id', 'N/A')})")
        print(f"Season: {data.get('season', 'N/A')}")
        print(f"Season Type: {data.get('season_type', 'N/A')}")

        # Print game log
        if "gamelog" in data:
            gamelog = data["gamelog"]
            print(f"\nPlayoff Game Log: {len(gamelog)} games")
            if gamelog:
                print("\nFirst 3 playoff games:")
                for i, game in enumerate(gamelog[:3]):
                    print(f"\nGame {i+1}:")
                    print(f"  Date: {game.get('GAME_DATE', 'N/A')}")
                    print(f"  Matchup: {game.get('MATCHUP', 'N/A')}")
                    print(f"  Result: {game.get('WL', 'N/A')}")
                    print(f"  Points: {game.get('PTS', 'N/A')}")

    print("\n=== Playoffs test completed ===")
    return data



def test_fetch_player_gamelog_dataframe():
    """Test fetching player game logs with DataFrame output."""
    print("\n=== Testing fetch_player_gamelog_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_player_gamelog_logic(SAMPLE_PLAYER_NAME, SAMPLE_SEASON, SAMPLE_SEASON_TYPE, return_dataframe=True)

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
    if os.path.exists(PLAYER_GAMELOG_CSV_DIR):
        csv_files = [f for f in os.listdir(PLAYER_GAMELOG_CSV_DIR) if f.startswith(SAMPLE_PLAYER_NAME.lower().replace(" ", "_"))]
        print(f"\nCSV files created: {csv_files}")

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
    print(f"=== Running player_gamelogs smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        basic_data = test_fetch_player_gamelog_basic()
        playoffs_data = test_fetch_player_gamelog_playoffs()
        json_response, dataframes = test_fetch_player_gamelog_dataframe()

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

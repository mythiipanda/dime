"""
Smoke test for the player_common_info module.
Tests the functionality of fetching player information, headline stats, and available seasons.
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

# Import directly from nba_api for league ID constants
from nba_api.stats.library.parameters import LeagueID

from api_tools.player_common_info import (
    fetch_player_info_logic,
    get_player_headshot_url,
    PLAYER_INFO_CSV_DIR
)

# Sample player name for testing
SAMPLE_PLAYER_NAME = "LeBron James"  # A well-known player with a long career

def test_fetch_player_info_basic():
    """Test fetching player info with default parameters."""
    print("\n=== Testing fetch_player_info_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_player_info_logic(SAMPLE_PLAYER_NAME)

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
        # Check if the player_info field exists
        assert "player_info" in data, "Response should have a 'player_info' field"

        # Print player info
        if "player_info" in data:
            info = data["player_info"]
            print("\nPlayer Info:")
            print(f"  Name: {info.get('FIRST_NAME', '')} {info.get('LAST_NAME', '')}")
            print(f"  Team: {info.get('TEAM_NAME', 'N/A')}")
            print(f"  Position: {info.get('POSITION', 'N/A')}")
            print(f"  Height: {info.get('HEIGHT', 'N/A')}")
            print(f"  Weight: {info.get('WEIGHT', 'N/A')}")
            print(f"  Draft: {info.get('DRAFT_YEAR', 'N/A')}")
            print(f"  Country: {info.get('COUNTRY', 'N/A')}")

            # Get headshot URL
            if "PERSON_ID" in info:
                player_id = int(info["PERSON_ID"])
                headshot_url = get_player_headshot_url(player_id)
                print(f"  Headshot URL: {headshot_url}")

        # Print headline stats
        if "headline_stats" in data:
            headline = data["headline_stats"]
            print("\nHeadline Stats:")
            print(f"  PPG: {headline.get('PTS', 'N/A')}")
            print(f"  RPG: {headline.get('REB', 'N/A')}")
            print(f"  APG: {headline.get('AST', 'N/A')}")
            print(f"  PIE: {headline.get('PIE', 'N/A')}")

        # Print available seasons
        if "available_seasons" in data:
            seasons = data["available_seasons"]
            print(f"\nAvailable Seasons: {len(seasons)}")
            if seasons:
                print(f"  First Season: {seasons[0].get('SEASON_ID', 'N/A')}")
                print(f"  Last Season: {seasons[-1].get('SEASON_ID', 'N/A')}")

    print("\n=== Basic test completed ===")
    return data

def test_fetch_player_info_dataframe():
    """Test fetching player info with DataFrame output."""
    print("\n=== Testing fetch_player_info_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_player_info_logic(SAMPLE_PLAYER_NAME, return_dataframe=True)

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
    if os.path.exists(PLAYER_INFO_CSV_DIR):
        csv_files = [f for f in os.listdir(PLAYER_INFO_CSV_DIR) if f.startswith(SAMPLE_PLAYER_NAME.lower().replace(" ", "_"))]
        print(f"\nCSV files created: {csv_files}")

    # Display a sample of one DataFrame if not empty
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nSample of DataFrame '{key}' (first 3 rows):")
            print(df.head(3))
            break

    print("\n=== DataFrame test completed ===")
    return json_response, dataframes

def test_fetch_player_info_with_league_id():
    """Test fetching player info with league_id parameter."""
    print("\n=== Testing fetch_player_info_logic with league_id parameter ===")

    # Test with league_id parameter
    json_response = fetch_player_info_logic(SAMPLE_PLAYER_NAME, league_id_nullable=LeagueID.nba)

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if the response has the expected structure
    assert isinstance(data, dict), "Response should be a dictionary"

    # Check if there's an error in the response
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
    else:
        # Check if the parameters field exists
        assert "parameters" in data, "Response should have a 'parameters' field"

        # Check if the league_id parameter is correctly included
        assert "league_id" in data["parameters"], "Parameters should include 'league_id'"
        assert data["parameters"]["league_id"] == LeagueID.nba, f"League ID should be '{LeagueID.nba}'"

        print(f"League ID parameter correctly included: {data['parameters']['league_id']}")

        # Print player info
        if "player_info" in data:
            info = data["player_info"]
            print(f"Player: {info.get('FIRST_NAME', '')} {info.get('LAST_NAME', '')}")

    print("\n=== League ID parameter test completed ===")
    return data

def test_get_player_headshot_url():
    """Test getting player headshot URL."""
    print("\n=== Testing get_player_headshot_url ===")

    # Get player ID from player info
    json_response = fetch_player_info_logic(SAMPLE_PLAYER_NAME)
    data = json.loads(json_response)

    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("Skipping headshot URL test...")
        return

    player_info = data.get("player_info", {})
    player_id = int(player_info.get("PERSON_ID", 0))

    if player_id > 0:
        # Test with valid player ID
        headshot_url = get_player_headshot_url(player_id)
        print(f"Player ID: {player_id}")
        print(f"Headshot URL: {headshot_url}")

        # Check if the URL is valid
        assert isinstance(headshot_url, str), "Headshot URL should be a string"
        assert headshot_url.startswith("https://"), "Headshot URL should start with 'https://'"
        assert headshot_url.endswith(".png"), "Headshot URL should end with '.png'"

        # Test with invalid player ID
        try:
            get_player_headshot_url(-1)
            assert False, "Should have raised ValueError for negative player ID"
        except ValueError:
            print("Correctly raised ValueError for negative player ID")

        try:
            get_player_headshot_url("invalid")
            assert False, "Should have raised ValueError for non-integer player ID"
        except (ValueError, TypeError):
            print("Correctly raised error for non-integer player ID")
    else:
        print(f"Could not get valid player ID for {SAMPLE_PLAYER_NAME}")

    print("\n=== Headshot URL test completed ===")

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running player_common_info smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        player_data = test_fetch_player_info_basic()
        json_response, dataframes = test_fetch_player_info_dataframe()
        league_id_data = test_fetch_player_info_with_league_id()
        test_get_player_headshot_url()

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

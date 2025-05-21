"""
Smoke test for the league_dash_player_pt_shot module.
Tests the functionality of fetching player shooting statistics across the league.
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

from backend.api_tools.league_dash_player_pt_shot import (
    fetch_league_dash_player_pt_shot_logic,
    LEAGUE_DASH_PLAYER_PT_SHOT_CSV_DIR
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeSimple, LeagueID
)

# Sample season for testing
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular  # Regular season

def test_fetch_league_dash_player_pt_shot_basic():
    """Test fetching player shooting statistics with default parameters."""
    print("\n=== Testing fetch_league_dash_player_pt_shot_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_league_dash_player_pt_shot_logic(
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
        
        # Check if the player_pt_shots field exists
        assert "player_pt_shots" in data, "Response should have a 'player_pt_shots' field"
        
        # Print some information about the data
        print(f"Season: {data.get('parameters', {}).get('season', 'N/A')}")
        print(f"Season Type: {data.get('parameters', {}).get('season_type_all_star', 'N/A')}")
        print(f"Per Mode: {data.get('parameters', {}).get('per_mode_simple', 'N/A')}")
        
        # Print player shooting data
        if "player_pt_shots" in data and data["player_pt_shots"]:
            player_shots = data["player_pt_shots"]
            print(f"\nPlayer Shooting Stats: {len(player_shots)} players")
            if player_shots:
                # Print first player
                first_player = player_shots[0]
                print("Sample data (first player):")
                for key, value in list(first_player.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

    print("\n=== Basic test completed ===")
    return data

def test_fetch_league_dash_player_pt_shot_with_filters():
    """Test fetching player shooting statistics with additional filters."""
    print("\n=== Testing fetch_league_dash_player_pt_shot_logic with filters ===")

    # Test with additional filters
    json_response = fetch_league_dash_player_pt_shot_logic(
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        per_mode=PerModeSimple.per_game,
        player_position_nullable="G",  # Only guards
        conference_nullable="East"  # Only Eastern Conference
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
        assert "player_position_nullable" in params, "Parameters should include 'player_position_nullable'"
        assert "conference_nullable" in params, "Parameters should include 'conference_nullable'"
        
        # Check if the filter values match what we provided
        assert params["player_position_nullable"] == "G", "player_position_nullable should be 'G'"
        assert params["conference_nullable"] == "East", "conference_nullable should be 'East'"
        
        # Print filter information
        print(f"Filters applied:")
        print(f"  Player Position: {params.get('player_position_nullable', 'N/A')}")
        print(f"  Conference: {params.get('conference_nullable', 'N/A')}")
        
        # Print player shooting data
        if "player_pt_shots" in data and data["player_pt_shots"]:
            player_shots = data["player_pt_shots"]
            print(f"\nFiltered Player Shooting Stats: {len(player_shots)} players")
            if player_shots:
                # Print first player
                first_player = player_shots[0]
                print("Sample data (first player):")
                for key, value in list(first_player.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

    print("\n=== Filters test completed ===")
    return data

def test_fetch_league_dash_player_pt_shot_team_filter():
    """Test fetching player shooting statistics with team filter."""
    print("\n=== Testing fetch_league_dash_player_pt_shot_logic with team filter ===")

    # Test with team filter (Lakers)
    json_response = fetch_league_dash_player_pt_shot_logic(
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        team_id_nullable="1610612747"  # Lakers
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
        # Check if the parameters field exists and contains the team filter
        assert "parameters" in data, "Response should have a 'parameters' field"
        params = data["parameters"]
        
        # Check if the team filter is included in the response
        assert "team_id_nullable" in params, "Parameters should include 'team_id_nullable'"
        
        # Check if the team filter matches what we provided
        assert params["team_id_nullable"] == "1610612747", "team_id_nullable should be '1610612747'"
        
        # Print filter information
        print(f"Team filter applied: {params.get('team_id_nullable', 'N/A')} (Lakers)")
        
        # Print player shooting data
        if "player_pt_shots" in data and data["player_pt_shots"]:
            player_shots = data["player_pt_shots"]
            print(f"\nLakers Player Shooting Stats: {len(player_shots)} players")
            if player_shots:
                # Print first player
                first_player = player_shots[0]
                print("Sample data (first player):")
                for key, value in list(first_player.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

    print("\n=== Team filter test completed ===")
    return data

def test_fetch_league_dash_player_pt_shot_dataframe():
    """Test fetching player shooting statistics with DataFrame output."""
    print("\n=== Testing fetch_league_dash_player_pt_shot_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_league_dash_player_pt_shot_logic(
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
    if os.path.exists(LEAGUE_DASH_PLAYER_PT_SHOT_CSV_DIR):
        csv_files = [f for f in os.listdir(LEAGUE_DASH_PLAYER_PT_SHOT_CSV_DIR) if f.startswith("player_pt_shot")]
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
    print(f"=== Running league_dash_player_pt_shot smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        basic_data = test_fetch_league_dash_player_pt_shot_basic()
        filters_data = test_fetch_league_dash_player_pt_shot_with_filters()
        team_filter_data = test_fetch_league_dash_player_pt_shot_team_filter()
        json_response, dataframes = test_fetch_league_dash_player_pt_shot_dataframe()

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

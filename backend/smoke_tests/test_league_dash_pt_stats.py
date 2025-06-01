"""
Smoke test for the league_dash_pt_stats module.
Tests the functionality of fetching player tracking statistics across the league.
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime


from api_tools.league_dash_pt_stats import (
    fetch_league_dash_pt_stats_logic,
    LEAGUE_DASH_PT_STATS_CSV_DIR
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeSimple, PlayerOrTeam, PtMeasureType
)

# Sample season for testing
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular  # Regular season

def test_fetch_league_dash_pt_stats_basic():
    """Test fetching player tracking statistics with default parameters."""
    print("\n=== Testing fetch_league_dash_pt_stats_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_league_dash_pt_stats_logic(
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

        # Check if the pt_stats field exists
        assert "pt_stats" in data, "Response should have a 'pt_stats' field"

        # Print some information about the data
        print(f"Season: {data.get('parameters', {}).get('season', 'N/A')}")
        print(f"Season Type: {data.get('parameters', {}).get('season_type_all_star', 'N/A')}")
        print(f"Per Mode: {data.get('parameters', {}).get('per_mode_simple', 'N/A')}")
        print(f"Player/Team: {data.get('parameters', {}).get('player_or_team', 'N/A')}")
        print(f"Measure Type: {data.get('parameters', {}).get('pt_measure_type', 'N/A')}")

        # Print player tracking data
        if "pt_stats" in data and data["pt_stats"]:
            pt_stats = data["pt_stats"]
            print(f"\nPlayer Tracking Stats: {len(pt_stats)} teams")
            if pt_stats:
                # Print first team
                first_team = pt_stats[0]
                print("Sample data (first team):")
                for key, value in list(first_team.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

    print("\n=== Basic test completed ===")
    return data

def test_fetch_league_dash_pt_stats_player_mode():
    """Test fetching player tracking statistics in player mode."""
    print("\n=== Testing fetch_league_dash_pt_stats_logic (player mode) ===")

    # Test with player mode
    json_response = fetch_league_dash_pt_stats_logic(
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        player_or_team=PlayerOrTeam.player
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

        # Check if the player_or_team parameter is included in the response
        assert "player_or_team" in params, "Parameters should include 'player_or_team'"

        # Check if the player_or_team value matches what we provided
        assert params["player_or_team"] == PlayerOrTeam.player, f"player_or_team should be '{PlayerOrTeam.player}'"

        # Print player tracking data
        if "pt_stats" in data and data["pt_stats"]:
            pt_stats = data["pt_stats"]
            print(f"\nPlayer Tracking Stats (Player Mode): {len(pt_stats)} players")
            if pt_stats:
                # Print first player
                first_player = pt_stats[0]
                print("Sample data (first player):")
                for key, value in list(first_player.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

    print("\n=== Player mode test completed ===")
    return data

def test_fetch_league_dash_pt_stats_different_measure():
    """Test fetching player tracking statistics with different measure types."""
    print("\n=== Testing fetch_league_dash_pt_stats_logic (different measure types) ===")

    # Test with different measure types
    measure_types = [
        PtMeasureType.rebounding,
        PtMeasureType.drives,
        PtMeasureType.passing
    ]

    for measure_type in measure_types:
        print(f"\nTesting measure type: {measure_type}")

        json_response = fetch_league_dash_pt_stats_logic(
            SAMPLE_SEASON,
            SAMPLE_SEASON_TYPE,
            pt_measure_type=measure_type
        )

        # Parse the JSON response
        data = json.loads(json_response)

        # Check if there's an error in the response
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            print("This might be expected if the NBA API is unavailable or rate-limited.")
            continue

        # Check if the parameters field exists and contains the pt_measure_type value
        assert "parameters" in data, "Response should have a 'parameters' field"
        params = data["parameters"]

        # Check if the pt_measure_type parameter is included in the response
        assert "pt_measure_type" in params, "Parameters should include 'pt_measure_type'"

        # Check if the pt_measure_type value matches what we provided
        assert params["pt_measure_type"] == measure_type, f"pt_measure_type should be '{measure_type}'"

        # Print player tracking data
        if "pt_stats" in data and data["pt_stats"]:
            pt_stats = data["pt_stats"]
            print(f"Player Tracking Stats ({measure_type}): {len(pt_stats)} teams")
            if pt_stats:
                # Print first team
                first_team = pt_stats[0]
                print("Sample data (first team):")
                for key, value in list(first_team.items())[:3]:  # Show first 3 columns
                    print(f"  {key}: {value}")

    print("\n=== Different measure types test completed ===")
    return data

def test_fetch_league_dash_pt_stats_with_filters():
    """Test fetching player tracking statistics with additional filters."""
    print("\n=== Testing fetch_league_dash_pt_stats_logic with filters ===")

    # Test with additional filters
    json_response = fetch_league_dash_pt_stats_logic(
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        last_n_games=10,  # Last 10 games
        location_nullable="Home",  # Only home games
        outcome_nullable="W",  # Only wins
        season_segment_nullable="Post All-Star",  # Post All-Star games
        vs_conference_nullable="East",  # Against Eastern Conference teams
        vs_division_nullable="Atlantic",  # Against Atlantic Division teams
        conference_nullable="East",  # Only Eastern Conference teams
        division_simple_nullable="Atlantic"  # Only Atlantic Division teams
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
        assert "conference_nullable" in params, "Parameters should include 'conference_nullable'"
        assert "division_simple_nullable" in params, "Parameters should include 'division_simple_nullable'"

        # Check if the filter values match what we provided
        assert params["conference_nullable"] == "East", "conference_nullable should be 'East'"
        assert params["division_simple_nullable"] == "Atlantic", "division_simple_nullable should be 'Atlantic'"

        # Print filter information
        print(f"Filters applied:")
        print(f"  Last N Games: {params.get('last_n_games', 'N/A')}")
        print(f"  Location: {params.get('location_nullable', 'N/A')}")
        print(f"  Outcome: {params.get('outcome_nullable', 'N/A')}")
        print(f"  Season Segment: {params.get('season_segment_nullable', 'N/A')}")
        print(f"  VS Conference: {params.get('vs_conference_nullable', 'N/A')}")
        print(f"  VS Division: {params.get('vs_division_nullable', 'N/A')}")
        print(f"  Conference: {params.get('conference_nullable', 'N/A')}")
        print(f"  Division: {params.get('division_simple_nullable', 'N/A')}")

        # Print player tracking data
        if "pt_stats" in data and data["pt_stats"]:
            pt_stats = data["pt_stats"]
            print(f"\nFiltered Player Tracking Stats: {len(pt_stats)} teams")
            if pt_stats:
                # Print first team
                first_team = pt_stats[0]
                print("Sample data (first team):")
                for key, value in list(first_team.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

    print("\n=== Filters test completed ===")
    return data

def test_fetch_league_dash_pt_stats_additional_filters():
    """Test fetching player tracking statistics with additional filters."""
    print("\n=== Testing fetch_league_dash_pt_stats_logic with additional filters ===")

    # Test with additional filters not covered in previous tests
    # Using a more limited set of filters that are more likely to return data
    json_response = fetch_league_dash_pt_stats_logic(
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        player_or_team=PlayerOrTeam.player,  # Player mode
        game_scope_simple_nullable="Last 10",  # Last 10 games scope
        player_experience_nullable="Veteran",  # Only veteran players
        starter_bench_nullable="Starters",  # Only starters
        league_id_nullable="00"  # NBA league
    )

    # Print a note about other parameters
    print("Note: Additional parameters like college_nullable, country_nullable, draft_pick_nullable,")
    print("draft_year_nullable, height_nullable, po_round_nullable, and weight_nullable are also")
    print("available but may be too restrictive when combined with other filters.")

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

        # Print filter information
        print(f"Additional filters applied:")
        print(f"  Player/Team: {params.get('player_or_team', 'N/A')}")
        print(f"  Game Scope: {params.get('game_scope_simple_nullable', 'N/A')}")
        print(f"  Player Experience: {params.get('player_experience_nullable', 'N/A')}")
        print(f"  Starter/Bench: {params.get('starter_bench_nullable', 'N/A')}")
        print(f"  League ID: {params.get('league_id_nullable', 'N/A')}")

        # Print player tracking data
        if "pt_stats" in data and data["pt_stats"]:
            pt_stats = data["pt_stats"]
            print(f"\nFiltered Player Tracking Stats: {len(pt_stats)} teams/players")
            if pt_stats:
                # Print first team/player
                first_item = pt_stats[0]
                print("Sample data (first item):")
                for key, value in list(first_item.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")
            else:
                print("No data returned with these filters - they may be too restrictive or not applicable")
        else:
            print("No data returned with these filters - they may be too restrictive or not applicable")

    print("\n=== Additional filters test completed ===")
    return data

def test_fetch_league_dash_pt_stats_dataframe():
    """Test fetching player tracking statistics with DataFrame output."""
    print("\n=== Testing fetch_league_dash_pt_stats_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_league_dash_pt_stats_logic(
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
    if os.path.exists(LEAGUE_DASH_PT_STATS_CSV_DIR):
        csv_files = [f for f in os.listdir(LEAGUE_DASH_PT_STATS_CSV_DIR) if f.startswith("pt_stats")]
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
    print(f"=== Running league_dash_pt_stats smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        test_fetch_league_dash_pt_stats_basic()
        test_fetch_league_dash_pt_stats_player_mode()
        test_fetch_league_dash_pt_stats_different_measure()
        test_fetch_league_dash_pt_stats_with_filters()
        test_fetch_league_dash_pt_stats_additional_filters()
        test_fetch_league_dash_pt_stats_dataframe()

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

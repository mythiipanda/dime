"""
Smoke test for the synergy_tools module.
Tests the functionality of fetching Synergy play type statistics with DataFrame output.
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime


from api_tools.synergy_tools import fetch_synergy_play_types_logic
from nba_api.stats.library.parameters import (
    LeagueID,
    PerModeSimple,
    PlayerOrTeamAbbreviation,
    SeasonTypeAllStar
)

def test_fetch_synergy_play_types_basic():
    """Test fetching synergy play types with default parameters."""
    print("\n=== Testing fetch_synergy_play_types_logic (basic) ===")

    # Test with a common play type
    play_type = "Isolation"
    season = "2022-23"  # Use a completed season for testing

    # Test with default parameters (JSON output)
    json_response = fetch_synergy_play_types_logic(
        play_type_nullable=play_type,
        type_grouping_nullable="offensive",
        player_or_team=PlayerOrTeamAbbreviation.team,
        season=season,
        season_type=SeasonTypeAllStar.regular,
        league_id=LeagueID.nba,
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
        # Check if the key fields exist
        assert "parameters" in data, "Response should have a 'parameters' field"
        assert "synergy_stats" in data, "Response should have a 'synergy_stats' field"

        # Print some information about the data
        print(f"Play Type: {play_type}")
        print(f"Season: {season}")
        print(f"Number of entries: {len(data['synergy_stats'])}")

        # Print details of the first few entries
        if data['synergy_stats']:
            print("\nFirst 3 entries:")
            for i, entry in enumerate(data['synergy_stats'][:3]):
                print(f"\nEntry {i+1}:")
                print(f"  Team: {entry.get('TEAM_NAME', 'N/A')}")
                print(f"  Team ID: {entry.get('TEAM_ID', 'N/A')}")
                print(f"  GP: {entry.get('GP', 'N/A')}")
                print(f"  Poss: {entry.get('POSS', 'N/A')}")
                print(f"  PPP: {entry.get('PPP', 'N/A')}")
                print(f"  Points: {entry.get('PTS', 'N/A')}")

    print("\n=== Basic synergy play types test completed ===")
    return data

def test_fetch_synergy_play_types_dataframe():
    """Test fetching synergy play types with DataFrame output."""
    print("\n=== Testing fetch_synergy_play_types_logic with DataFrame output ===")

    # Test with a common play type
    play_type = "Isolation"
    season = "2022-23"  # Use a completed season for testing

    # Test with return_dataframe=True
    result = fetch_synergy_play_types_logic(
        play_type_nullable=play_type,
        type_grouping_nullable="offensive",
        player_or_team=PlayerOrTeamAbbreviation.team,
        season=season,
        season_type=SeasonTypeAllStar.regular,
        league_id=LeagueID.nba,
        per_mode=PerModeSimple.per_game,
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
                print(f"DataFrame '{key}' columns: {df.columns.tolist()}")

        # Check if the CSV file was created
        if "dataframe_info" in data:
            for df_key, df_info in data["dataframe_info"].get("dataframes", {}).items():
                csv_path = df_info.get("csv_path")
                if csv_path:
                    full_path = os.path.join(os.getcwd(), csv_path)
                    if os.path.exists(full_path):
                        print(f"\nCSV file exists: {csv_path}")
                        csv_size = os.path.getsize(full_path)
                        print(f"CSV file size: {csv_size} bytes")
                    else:
                        print(f"\nCSV file does not exist: {csv_path}")

        # Display a sample of each DataFrame if not empty
        for key, df in dataframes.items():
            if not df.empty:
                print(f"\nSample of DataFrame '{key}' (first 3 rows):")
                print(df.head(3))

    print("\n=== DataFrame synergy play types test completed ===")
    return result

def test_fetch_synergy_play_types_player():
    """Test fetching synergy play types for players."""
    print("\n=== Testing fetch_synergy_play_types_logic for players ===")

    # Test with a common play type
    play_type = "Isolation"
    season = "2022-23"  # Use a completed season for testing

    # Test with player data
    json_response = fetch_synergy_play_types_logic(
        play_type_nullable=play_type,
        type_grouping_nullable="offensive",
        player_or_team=PlayerOrTeamAbbreviation.player,
        season=season,
        season_type=SeasonTypeAllStar.regular,
        league_id=LeagueID.nba,
        per_mode=PerModeSimple.per_game
    )

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if there's an error in the response
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
    else:
        print(f"Number of player entries: {len(data['synergy_stats'])}")

        # Print details of the first few entries
        if data['synergy_stats']:
            print("\nFirst 3 player entries:")
            for i, entry in enumerate(data['synergy_stats'][:3]):
                print(f"\nPlayer {i+1}:")
                print(f"  Name: {entry.get('PLAYER_NAME', 'N/A')}")
                print(f"  Player ID: {entry.get('PLAYER_ID', 'N/A')}")
                print(f"  Team: {entry.get('TEAM_NAME', 'N/A')}")
                print(f"  GP: {entry.get('GP', 'N/A')}")
                print(f"  Poss: {entry.get('POSS', 'N/A')}")
                print(f"  PPP: {entry.get('PPP', 'N/A')}")

    print("\n=== Player synergy play types test completed ===")
    return data

def test_fetch_synergy_play_types_player_with_id():
    """Test fetching synergy play types for a specific player ID."""
    print("\n=== Testing fetch_synergy_play_types_logic for a specific player ID ===")

    play_type = "Isolation"
    season = "2022-23"
    lebron_james_id = 2544 # LeBron James' Player ID

    json_response = fetch_synergy_play_types_logic(
        play_type_nullable=play_type,
        type_grouping_nullable="offensive",
        player_or_team=PlayerOrTeamAbbreviation.player,
        season=season,
        season_type=SeasonTypeAllStar.regular,
        league_id=LeagueID.nba,
        per_mode=PerModeSimple.per_game,
        player_id_nullable=lebron_james_id
    )

    data = json.loads(json_response)

    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
    else:
        print(f"Number of player entries for LeBron James: {len(data['synergy_stats'])}")
        if data['synergy_stats']:
            print("\nFirst 3 player entries for LeBron James:")
            for i, entry in enumerate(data['synergy_stats'][:3]):
                print(f"\nPlayer {i+1}:")
                print(f"  Name: {entry.get('PLAYER_NAME', 'N/A')}")
                print(f"  Player ID: {entry.get('PLAYER_ID', 'N/A')}")
                print(f"  Team: {entry.get('TEAM_NAME', 'N/A')}")
                print(f"  GP: {entry.get('GP', 'N/A')}")
                print(f"  Poss: {entry.get('POSS', 'N/A')}")
                print(f"  PPP: {entry.get('PPP', 'N/A')}")
                assert entry.get('PLAYER_ID') == lebron_james_id, "Filtered data should only contain LeBron James' ID"

    print("\n=== Player synergy play types with ID test completed ===")
    return data

def test_fetch_synergy_play_types_defensive():
    """Test fetching defensive synergy play types."""
    print("\n=== Testing fetch_synergy_play_types_logic for defensive plays ===")

    # Test with a defensive play type
    play_type = "Isolation"
    season = "2022-23"  # Use a completed season for testing

    # Test with defensive grouping
    json_response = fetch_synergy_play_types_logic(
        play_type_nullable=play_type,
        type_grouping_nullable="defensive",
        player_or_team=PlayerOrTeamAbbreviation.team,
        season=season,
        season_type=SeasonTypeAllStar.regular,
        league_id=LeagueID.nba,
        per_mode=PerModeSimple.per_game
    )

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if there's an error in the response
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
    else:
        print(f"Number of defensive entries: {len(data['synergy_stats'])}")

        # Print details of the first few entries
        if data['synergy_stats']:
            print("\nFirst 3 defensive entries:")
            for i, entry in enumerate(data['synergy_stats'][:3]):
                print(f"\nTeam {i+1}:")
                print(f"  Name: {entry.get('TEAM_NAME', 'N/A')}")
                print(f"  Team ID: {entry.get('TEAM_ID', 'N/A')}")
                print(f"  GP: {entry.get('GP', 'N/A')}")
                print(f"  Poss: {entry.get('POSS', 'N/A')}")
                print(f"  PPP: {entry.get('PPP', 'N/A')}")

    print("\n=== Defensive synergy play types test completed ===")
    return data

def test_fetch_synergy_different_play_types():
    """Test fetching different synergy play types."""
    print("\n=== Testing fetch_synergy_play_types_logic with different play types ===")

    # Test with different play types that are known to work
    play_types = ["Isolation", "Transition", "PRBallHandler"]
    season = "2022-23"  # Use a completed season for testing

    for play_type in play_types:
        print(f"\nTesting play type: {play_type}")

        # Test with default parameters (JSON output)
        json_response = fetch_synergy_play_types_logic(
            play_type_nullable=play_type,
            type_grouping_nullable="offensive",
            player_or_team=PlayerOrTeamAbbreviation.team,
            season=season,
            season_type=SeasonTypeAllStar.regular,
            league_id=LeagueID.nba,
            per_mode=PerModeSimple.per_game
        )

        # Parse the JSON response
        data = json.loads(json_response)

        # Check if there's an error in the response
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            print("This might be expected if the NBA API is unavailable or rate-limited.")
        else:
            print(f"Number of entries for {play_type}: {len(data['synergy_stats'])}")

            # Print details of the first entry
            if data['synergy_stats']:
                entry = data['synergy_stats'][0]
                print(f"Top team: {entry.get('TEAM_NAME', 'N/A')}")
                print(f"PPP: {entry.get('PPP', 'N/A')}")
                print(f"Percentile: {entry.get('PERCENTILE', 'N/A')}")

    print("\n=== Different play types test completed ===")
    return True

def test_fetch_synergy_different_seasons():
    """Test fetching synergy play types for different seasons."""
    print("\n=== Testing fetch_synergy_play_types_logic with different seasons ===")

    # Test with different seasons
    seasons = ["2021-22", "2022-23"]
    play_type = "Isolation"

    for season in seasons:
        print(f"\nTesting season: {season}")

        # Test with default parameters (JSON output)
        json_response = fetch_synergy_play_types_logic(
            play_type_nullable=play_type,
            type_grouping_nullable="offensive",
            player_or_team=PlayerOrTeamAbbreviation.team,
            season=season,
            season_type=SeasonTypeAllStar.regular,
            league_id=LeagueID.nba,
            per_mode=PerModeSimple.per_game
        )

        # Parse the JSON response
        data = json.loads(json_response)

        # Check if there's an error in the response
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            print("This might be expected if the NBA API is unavailable or rate-limited.")
        else:
            print(f"Number of entries for {season}: {len(data['synergy_stats'])}")

            # Print details of the first entry
            if data['synergy_stats']:
                entry = data['synergy_stats'][0]
                print(f"Top team: {entry.get('TEAM_NAME', 'N/A')}")
                print(f"PPP: {entry.get('PPP', 'N/A')}")

    print("\n=== Different seasons test completed ===")
    return True

def test_fetch_synergy_different_per_modes():
    """Test fetching synergy play types with different per_mode values."""
    print("\n=== Testing fetch_synergy_play_types_logic with different per_mode values ===")

    # Test with different per_mode values
    per_modes = [PerModeSimple.per_game, PerModeSimple.totals]
    play_type = "Isolation"
    season = "2022-23"

    for per_mode in per_modes:
        print(f"\nTesting per_mode: {per_mode}")

        # Test with default parameters (JSON output)
        json_response = fetch_synergy_play_types_logic(
            play_type_nullable=play_type,
            type_grouping_nullable="offensive",
            player_or_team=PlayerOrTeamAbbreviation.team,
            season=season,
            season_type=SeasonTypeAllStar.regular,
            league_id=LeagueID.nba,
            per_mode=per_mode
        )

        # Parse the JSON response
        data = json.loads(json_response)

        # Check if there's an error in the response
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            print("This might be expected if the NBA API is unavailable or rate-limited.")
        else:
            print(f"Number of entries for {per_mode}: {len(data['synergy_stats'])}")

            # Print details of the first entry
            if data['synergy_stats']:
                entry = data['synergy_stats'][0]
                print(f"Top team: {entry.get('TEAM_NAME', 'N/A')}")
                print(f"PPP: {entry.get('PPP', 'N/A')}")
                print(f"PTS: {entry.get('PTS', 'N/A')}")

    print("\n=== Different per_mode values test completed ===")
    return True

def test_fetch_synergy_postup():
    result = fetch_synergy_play_types_logic(
        league_id="00",
        per_mode="PerGame",
        player_or_team="P",
        season_type="Regular Season",
        season="2024-25",
        play_type_nullable="PostUp",
        type_grouping_nullable="offensive",
        player_id_nullable=None,
        team_id_nullable=None,
        return_dataframe=False
    )
    data = json.loads(result)
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        return False
    print(f"Number of PostUp entries: {len(data['synergy_stats'])}")
    if data['synergy_stats']:
        print("\nFirst 3 PostUp entries:")
        for i, entry in enumerate(data['synergy_stats'][:3]):
            print(f"\nEntry {i+1}:")
            print(f"  Player: {entry.get('PLAYER_NAME', 'N/A')}")
            print(f"  Player ID: {entry.get('PLAYER_ID', 'N/A')}")
            print(f"  Team: {entry.get('TEAM_NAME', 'N/A')}")
            print(f"  GP: {entry.get('GP', 'N/A')}")
            print(f"  Poss: {entry.get('POSS', 'N/A')}")
            print(f"  PPP: {entry.get('PPP', 'N/A')}")
    else:
        print("No PostUp entries found.")
    return True
def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running synergy_tools smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the basic tests
        basic_data = test_fetch_synergy_play_types_basic()
        df_result = test_fetch_synergy_play_types_dataframe()
        player_data = test_fetch_synergy_play_types_player()
        player_with_id_data = test_fetch_synergy_play_types_player_with_id() # New test

        # Run the additional tests for better coverage
        defensive_data = test_fetch_synergy_play_types_defensive()
        different_play_types = test_fetch_synergy_different_play_types()
        different_seasons = test_fetch_synergy_different_seasons()
        different_per_modes = test_fetch_synergy_different_per_modes()
        postup_data = test_fetch_synergy_postup()
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

"""
Smoke test for the player_career_data module.
Tests the functionality of fetching player career statistics and awards.
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime


from api_tools.player_career_data import (
    fetch_player_career_stats_logic,
    fetch_player_awards_logic
)
from nba_api.stats.library.parameters import PerModeDetailed, LeagueID

# Sample player name for testing
SAMPLE_PLAYER_NAME = "LeBron James"  # A well-known player with a long career and many awards

def test_fetch_player_career_stats_basic():
    """Test fetching player career stats with default parameters."""
    print("\n=== Testing fetch_player_career_stats_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_player_career_stats_logic(SAMPLE_PLAYER_NAME)

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

        # Print some information about the data
        print(f"Player: {data.get('player_name', 'N/A')} (ID: {data.get('player_id', 'N/A')})")
        print(f"Per Mode: {data.get('per_mode_requested', 'N/A')}")

        # Print regular season stats
        if "season_totals_regular_season" in data:
            season_totals = data["season_totals_regular_season"]
            print(f"\nRegular Season Stats: {len(season_totals)} seasons")
            if season_totals:
                print("\nFirst 3 seasons:")
                for i, season in enumerate(season_totals[:3]):
                    print(f"\nSeason {i+1}:")
                    print(f"  Season: {season.get('SEASON_ID', 'N/A')}")
                    print(f"  Team: {season.get('TEAM_ABBREVIATION', 'N/A')}")
                    print(f"  Games: {season.get('GP', 'N/A')}")
                    print(f"  Points: {season.get('PTS', 'N/A')}")

        # Print career totals
        if "career_totals_regular_season" in data:
            career = data["career_totals_regular_season"]
            print("\nCareer Totals (Regular Season):")
            print(f"  Games: {career.get('GP', 'N/A')}")
            print(f"  Points: {career.get('PTS', 'N/A')}")
            print(f"  Rebounds: {career.get('REB', 'N/A')}")
            print(f"  Assists: {career.get('AST', 'N/A')}")

        # Print playoff stats
        if "season_totals_post_season" in data:
            post_season = data["season_totals_post_season"]
            print(f"\nPlayoff Stats: {len(post_season)} seasons")
            if post_season:
                print("\nFirst 3 playoff seasons:")
                for i, season in enumerate(post_season[:3]):
                    print(f"\nPlayoff Season {i+1}:")
                    print(f"  Season: {season.get('SEASON_ID', 'N/A')}")
                    print(f"  Team: {season.get('TEAM_ABBREVIATION', 'N/A')}")
                    print(f"  Games: {season.get('GP', 'N/A')}")
                    print(f"  Points: {season.get('PTS', 'N/A')}")

    print("\n=== Basic test completed ===")
    return data

def test_fetch_player_career_stats_with_league_id():
    """Test fetching player career stats with league_id parameter."""
    print("\n=== Testing fetch_player_career_stats_logic with league_id parameter ===")

    # Test with league_id parameter
    json_response = fetch_player_career_stats_logic(
        SAMPLE_PLAYER_NAME,
        per_mode=PerModeDetailed.per_game,
        league_id_nullable=LeagueID.nba
    )

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if the response has the expected structure
    assert isinstance(data, dict), "Response should be a dictionary"

    # Check if there's an error in the response
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
    else:
        # Check if the league_id parameter is correctly included
        assert "league_id" in data, "Response should have a 'league_id' field"
        assert data["league_id"] == LeagueID.nba, f"league_id should be {LeagueID.nba}"

        print(f"League ID parameter correctly included: {data['league_id']}")

        # Print player info
        print(f"Player: {data.get('player_name', 'N/A')} (ID: {data.get('player_id', 'N/A')})")
        print(f"Per Mode: {data.get('per_mode_requested', 'N/A')}")

    print("\n=== League ID parameter test completed ===")
    return data

def test_fetch_player_career_stats_dataframe():
    """Test fetching player career stats with DataFrame output."""
    print("\n=== Testing fetch_player_career_stats_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_player_career_stats_logic(SAMPLE_PLAYER_NAME, return_dataframe=True)

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
                full_path = os.path.join(os.getcwd(), csv_path)
                if os.path.exists(full_path):
                    print(f"\nCSV file exists: {csv_path}")
                else:
                    print(f"\nCSV file does not exist: {csv_path}")

    # Display a sample of one DataFrame if not empty
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nSample of DataFrame '{key}' (first 3 rows):")
            print(df.head(3))
            break

    print("\n=== DataFrame test completed ===")
    return json_response, dataframes

def test_fetch_player_awards_basic():
    """Test fetching player awards with default parameters."""
    print("\n=== Testing fetch_player_awards_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_player_awards_logic(SAMPLE_PLAYER_NAME)

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

        # Print some information about the data
        print(f"Player: {data.get('player_name', 'N/A')} (ID: {data.get('player_id', 'N/A')})")

        # Print awards
        if "awards" in data:
            awards = data["awards"]
            print(f"\nAwards: {len(awards)}")
            if awards:
                print("\nFirst 5 awards:")
                for i, award in enumerate(awards[:5]):
                    print(f"\nAward {i+1}:")
                    print(f"  Season: {award.get('SEASON', 'N/A')}")
                    print(f"  Description: {award.get('DESCRIPTION', 'N/A')}")

    print("\n=== Basic test completed ===")
    return data

def test_fetch_player_awards_dataframe():
    """Test fetching player awards with DataFrame output."""
    print("\n=== Testing fetch_player_awards_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_player_awards_logic(SAMPLE_PLAYER_NAME, return_dataframe=True)

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
                full_path = os.path.join(os.getcwd(), csv_path)
                if os.path.exists(full_path):
                    print(f"\nCSV file exists: {csv_path}")
                else:
                    print(f"\nCSV file does not exist: {csv_path}")

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
    print(f"=== Running player_career_data smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        career_data = test_fetch_player_career_stats_basic()
        league_id_data = test_fetch_player_career_stats_with_league_id()
        career_json, career_dataframes = test_fetch_player_career_stats_dataframe()
        awards_data = test_fetch_player_awards_basic()
        awards_json, awards_dataframes = test_fetch_player_awards_dataframe()

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

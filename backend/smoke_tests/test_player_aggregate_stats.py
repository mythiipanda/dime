"""
Smoke test for the player_aggregate_stats module.
Tests the functionality of fetching aggregated player statistics.
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime


from api_tools.player_aggregate_stats import (
    fetch_player_stats_logic
)

# Sample player name for testing
SAMPLE_PLAYER_NAME = "LeBron James"  # A well-known player with a long career
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing

def test_fetch_player_stats_basic():
    """Test fetching player aggregate stats with default parameters."""
    print("\n=== Testing fetch_player_stats_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_player_stats_logic(SAMPLE_PLAYER_NAME, SAMPLE_SEASON)

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

        # Check if the season_requested_for_gamelog field exists and matches the input
        assert "season_requested_for_gamelog" in data, "Response should have a 'season_requested_for_gamelog' field"
        assert data["season_requested_for_gamelog"] == SAMPLE_SEASON, f"season_requested_for_gamelog should be {SAMPLE_SEASON}"

        # Print some information about the data
        print(f"Player: {data.get('player_name', 'N/A')} (ID: {data.get('player_id', 'N/A')})")
        print(f"Season: {data.get('season_requested_for_gamelog', 'N/A')}")

        # Print player info
        if "info" in data:
            print("\nPlayer Info:")
            info = data["info"]
            print(f"  Team: {info.get('TEAM_NAME', 'N/A')}")
            print(f"  Position: {info.get('POSITION', 'N/A')}")
            print(f"  Height: {info.get('HEIGHT', 'N/A')}")
            print(f"  Weight: {info.get('WEIGHT', 'N/A')}")
            print(f"  Draft: {info.get('DRAFT_YEAR', 'N/A')}")

        # Print headline stats
        if "headline_stats" in data:
            print("\nHeadline Stats:")
            headline = data["headline_stats"]
            print(f"  PPG: {headline.get('PTS', 'N/A')}")
            print(f"  RPG: {headline.get('REB', 'N/A')}")
            print(f"  APG: {headline.get('AST', 'N/A')}")

        # Print available seasons
        if "available_seasons" in data:
            seasons = data["available_seasons"]
            print(f"\nAvailable Seasons: {len(seasons)}")
            if seasons:
                print(f"  First Season: {seasons[0].get('SEASON_ID', 'N/A')}")
                print(f"  Last Season: {seasons[-1].get('SEASON_ID', 'N/A')}")

        # Print career stats
        if "career_stats" in data:
            career = data["career_stats"]
            print("\nCareer Stats:")

            # Regular season totals
            reg_season = career.get("career_totals_regular_season", {})
            if reg_season:
                print(f"  Regular Season Games: {reg_season.get('GP', 'N/A')}")
                print(f"  Regular Season Points: {reg_season.get('PTS', 'N/A')}")

            # Post season totals
            post_season = career.get("career_totals_post_season", {})
            if post_season:
                print(f"  Playoff Games: {post_season.get('GP', 'N/A')}")
                print(f"  Playoff Points: {post_season.get('PTS', 'N/A')}")

        # Print game log
        if "season_gamelog" in data:
            gamelog = data["season_gamelog"]
            print(f"\nSeason Game Log: {len(gamelog)} games")
            if gamelog:
                print("\nFirst 3 games:")
                for i, game in enumerate(gamelog[:3]):
                    print(f"\nGame {i+1}:")
                    print(f"  Date: {game.get('GAME_DATE', 'N/A')}")
                    print(f"  Matchup: {game.get('MATCHUP', 'N/A')}")
                    print(f"  Points: {game.get('PTS', 'N/A')}")

        # Print awards
        if "awards" in data:
            awards = data["awards"]
            print(f"\nAwards: {len(awards)}")
            if awards:
                print("\nFirst 3 awards:")
                for i, award in enumerate(awards[:3]):
                    print(f"\nAward {i+1}:")
                    print(f"  Season: {award.get('SEASON', 'N/A')}")
                    print(f"  Description: {award.get('DESCRIPTION', 'N/A')}")

    print("\n=== Basic test completed ===")
    return data

def test_fetch_player_stats_dataframe():
    """Test fetching player aggregate stats with DataFrame output."""
    print("\n=== Testing fetch_player_stats_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_player_stats_logic(SAMPLE_PLAYER_NAME, SAMPLE_SEASON, return_dataframe=True)

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
                full_path = csv_path
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
    print(f"=== Running player_aggregate_stats smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        basic_data = test_fetch_player_stats_basic()
        json_response, dataframes = test_fetch_player_stats_dataframe()

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

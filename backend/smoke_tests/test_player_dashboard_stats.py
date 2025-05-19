"""
Smoke test for the player_dashboard_stats module.
Tests the functionality of fetching player dashboard statistics.
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

from backend.api_tools.player_dashboard_stats import (
    fetch_player_profile_logic,
    fetch_player_defense_logic,
    fetch_player_hustle_stats_logic,
    _get_csv_path_for_player_profile,  # For verification
    _get_csv_path_for_player_defense,  # For verification
    _get_csv_path_for_player_hustle,   # For verification
    PLAYER_PROFILE_CSV_DIR, # Base dir for profile CSVs
    PLAYER_DEFENSE_CSV_DIR, # Base dir for defense CSVs
    PLAYER_HUSTLE_CSV_DIR   # Base dir for hustle CSVs
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailedDefense, LeagueID, PerModeSimple
)
from backend.api_tools.utils import find_player_id_or_error # To get player ID for CSV path construction

# Sample player for testing
SAMPLE_PLAYER_NAME = "LeBron James"
SAMPLE_PLAYER_ID = "2544" # LeBron James ID, replace if needed or fetch dynamically
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
DEFAULT_PER_MODE_PROFILE = PerModeDetailed.per_game
DEFAULT_MEASURE_TYPE_PROFILE = MeasureTypeDetailedDefense.base
DEFAULT_PER_MODE_DEFENSE = PerModeDetailed.per_game
DEFAULT_PER_MODE_HUSTLE = PerModeSimple.per_game

def _verify_csv_exists(expected_path: str):
    assert os.path.exists(expected_path), f"CSV file not found at {expected_path}"
    print(f"Verified CSV file exists: {expected_path}")

def test_fetch_player_profile():
    """Test fetching player profile with JSON and DataFrame output."""
    print(f"\n=== Testing fetch_player_profile_logic for {SAMPLE_PLAYER_NAME} ===")
    
    # Test JSON output
    json_response_only = fetch_player_profile_logic(SAMPLE_PLAYER_NAME, per_mode=DEFAULT_PER_MODE_PROFILE)
    data_only = json.loads(json_response_only)
    assert isinstance(data_only, dict), "JSON only response should be a dictionary"
    if "error" in data_only:
        print(f"API (JSON only) returned an error: {data_only['error']}")
    else:
        assert "player_name" in data_only
        assert data_only["player_name"] == SAMPLE_PLAYER_NAME # Or actual name if resolved differently
        print(f"Profile (JSON only) fetched for {data_only.get('player_name')}")

    # Test with return_dataframe=True
    result = fetch_player_profile_logic(SAMPLE_PLAYER_NAME, per_mode=DEFAULT_PER_MODE_PROFILE, return_dataframe=True)
    assert isinstance(result, tuple) and len(result) == 2, "Result should be a tuple (json, dataframes)"
    
    json_response, dataframes = result
    data = json.loads(json_response)
    assert isinstance(dataframes, dict), "Second element should be a dictionary of DataFrames"

    if "error" in data:
        print(f"API (DataFrame) returned an error: {data['error']}")
    else:
        print(f"Profile (DataFrame) fetched for {data.get('player_name')}")
        player_id_for_csv = str(data.get("player_id", SAMPLE_PLAYER_ID))

        expected_dfs = [
            "career_totals_regular_season", "season_totals_regular_season",
            "career_totals_post_season", "season_totals_post_season",
            "season_highs", "career_highs", "next_game"
        ]
        for key in expected_dfs:
            assert key in dataframes, f"DataFrame key '{key}' missing"
            df = dataframes[key]
            if not df.empty:
                print(f"\nDataFrame '{key}' shape: {df.shape}")
                print(df.head(2))
                # Construct specific CSV path for each df based on how they are saved in main logic
                if key == "career_totals_regular_season": # Main profile CSV often uses just per_mode
                     csv_path = _get_csv_path_for_player_profile(player_id_for_csv, DEFAULT_PER_MODE_PROFILE)
                     _verify_csv_exists(csv_path)
                elif key == "season_totals_regular_season":
                    csv_path = os.path.join(PLAYER_PROFILE_CSV_DIR, f"player_{player_id_for_csv}_season_totals_rs_{DEFAULT_PER_MODE_PROFILE.replace(' ', '_').lower()}.csv")
                    _verify_csv_exists(csv_path)
                # Add checks for other specific CSVs if their naming pattern is distinct in main logic
            else:
                print(f"\nDataFrame '{key}' is empty.")
    print("\n=== Profile test completed ===")

def test_fetch_player_defense():
    """Test fetching player defense stats with JSON and DataFrame output."""
    print(f"\n=== Testing fetch_player_defense_logic for {SAMPLE_PLAYER_NAME}, Season: {SAMPLE_SEASON} ===")

    # Test JSON output
    json_response_only = fetch_player_defense_logic(
        SAMPLE_PLAYER_NAME, SAMPLE_SEASON, SeasonTypeAllStar.regular, DEFAULT_PER_MODE_DEFENSE
    )
    data_only = json.loads(json_response_only)
    assert isinstance(data_only, dict)
    if "error" in data_only:
        print(f"API (JSON only) returned an error: {data_only['error']}")
    else:
        assert "player_name" in data_only
        print(f"Defense (JSON only) fetched for {data_only.get('player_name')}")

    # Test with return_dataframe=True
    result = fetch_player_defense_logic(
        SAMPLE_PLAYER_NAME, SAMPLE_SEASON, SeasonTypeAllStar.regular, DEFAULT_PER_MODE_DEFENSE, return_dataframe=True
    )
    assert isinstance(result, tuple) and len(result) == 2
    json_response, dataframes = result
    data = json.loads(json_response)
    assert isinstance(dataframes, dict)

    if "error" in data:
        print(f"API (DataFrame) returned an error: {data['error']}")
    else:
        print(f"Defense (DataFrame) fetched for {data.get('player_name')}")
        player_id_for_csv = str(data.get("player_id", SAMPLE_PLAYER_ID))
        assert "defending_shots" in dataframes
        df = dataframes["defending_shots"]
        if not df.empty:
            print(f"\nDataFrame 'defending_shots' shape: {df.shape}")
            print(df.head(2))
            csv_path = _get_csv_path_for_player_defense(
                player_id_for_csv, SAMPLE_SEASON, SeasonTypeAllStar.regular, DEFAULT_PER_MODE_DEFENSE, 0 # opponent_team_id=0 default
            )
            _verify_csv_exists(csv_path)
        else:
            print("\nDataFrame 'defending_shots' is empty.")
    print("\n=== Defense test completed ===")

def test_fetch_player_hustle():
    """Test fetching player hustle stats with JSON and DataFrame output."""
    print(f"\n=== Testing fetch_player_hustle_stats_logic for {SAMPLE_PLAYER_NAME}, Season: {SAMPLE_SEASON} ===")

    # Test JSON output
    json_response_only = fetch_player_hustle_stats_logic(
        season=SAMPLE_SEASON, player_name=SAMPLE_PLAYER_NAME, per_mode=DEFAULT_PER_MODE_HUSTLE
    )
    data_only = json.loads(json_response_only)
    assert isinstance(data_only, dict)
    if "error" in data_only:
        print(f"API (JSON only) returned an error: {data_only['error']}")
    else:
        assert "parameters" in data_only and data_only["parameters"].get("player_name_filter") is not None
        print(f"Hustle (JSON only) fetched for player: {data_only['parameters']['player_name_filter']}")

    # Test with return_dataframe=True
    result = fetch_player_hustle_stats_logic(
        season=SAMPLE_SEASON, player_name=SAMPLE_PLAYER_NAME, per_mode=DEFAULT_PER_MODE_HUSTLE, return_dataframe=True
    )
    assert isinstance(result, tuple) and len(result) == 2
    json_response, dataframes = result
    data = json.loads(json_response)
    assert isinstance(dataframes, dict)

    if "error" in data:
        print(f"API (DataFrame) returned an error: {data['error']}")
    else:
        print(f"Hustle (DataFrame) fetched for player: {data['parameters']['player_name_filter']}")
        player_id_for_csv = str(data["parameters"].get("player_id_filter", SAMPLE_PLAYER_ID))
        
        assert "hustle_stats" in dataframes
        df = dataframes["hustle_stats"]
        if not df.empty:
            print(f"\nDataFrame 'hustle_stats' shape: {df.shape}")
            print(df.head(2))
            # For player-specific hustle, team_id is None in path generation by default
            csv_path = _get_csv_path_for_player_hustle(
                SAMPLE_SEASON, SeasonTypeAllStar.regular, DEFAULT_PER_MODE_HUSTLE, player_id=player_id_for_csv 
            )
            _verify_csv_exists(csv_path)
        else:
            print("\nDataFrame 'hustle_stats' is empty.")
    print("\n=== Player Hustle test completed ===")

def test_fetch_league_hustle():
    """Test fetching league-wide hustle stats with DataFrame output."""
    print(f"\n=== Testing fetch_player_hustle_stats_logic for league-wide, Season: {SAMPLE_SEASON} ===")
    
    result = fetch_player_hustle_stats_logic(
        season=SAMPLE_SEASON, per_mode=DEFAULT_PER_MODE_HUSTLE, return_dataframe=True
    ) # No player, no team
    assert isinstance(result, tuple) and len(result) == 2
    json_response, dataframes = result
    data = json.loads(json_response)
    assert isinstance(dataframes, dict)

    if "error" in data:
        print(f"API (League Hustle DataFrame) returned an error: {data['error']}")
    else:
        print(f"League Hustle (DataFrame) fetched.")
        assert "hustle_stats" in dataframes
        df = dataframes["hustle_stats"]
        if not df.empty:
            print(f"\nDataFrame 'hustle_stats' (league) shape: {df.shape}")
            print(df.head(2))
            csv_path = _get_csv_path_for_player_hustle(
                SAMPLE_SEASON, SeasonTypeAllStar.regular, DEFAULT_PER_MODE_HUSTLE, player_id=None, team_id=None 
            )
            _verify_csv_exists(csv_path)
        else:
            print("\nDataFrame 'hustle_stats' (league) is empty.")
    print("\n=== League Hustle test completed ===")


def run_all_tests():
    """Run all tests in sequence."""
    # Resolve player ID once if needed consistently across tests
    # For now, using hardcoded SAMPLE_PLAYER_ID and resolving from response
    # try:
    #     pid, _ = find_player_id_or_error(SAMPLE_PLAYER_NAME)
    #     global SAMPLE_PLAYER_ID
    #     SAMPLE_PLAYER_ID = str(pid)
    #     print(f"Resolved {SAMPLE_PLAYER_NAME} to ID: {SAMPLE_PLAYER_ID}")
    # except Exception as e:
    #     print(f"Could not resolve player ID for {SAMPLE_PLAYER_NAME}: {e}. Using default {SAMPLE_PLAYER_ID}")


    print(f"\n=== Running player_dashboard_stats smoke tests at {datetime.now().isoformat()} ===\n")
    
    test_fetch_player_profile()
    test_fetch_player_defense()
    test_fetch_player_hustle()
    test_fetch_league_hustle()
        
    print("\n\n=== All player_dashboard_stats tests completed successfully ===")

if __name__ == "__main__":
    # Ensure cache directories exist before running tests
    os.makedirs(PLAYER_PROFILE_CSV_DIR, exist_ok=True)
    os.makedirs(PLAYER_DEFENSE_CSV_DIR, exist_ok=True)
    os.makedirs(PLAYER_HUSTLE_CSV_DIR, exist_ok=True)
    
    run_all_tests() 
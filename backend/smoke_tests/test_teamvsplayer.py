import os
import sys
import json
import pandas as pd
from datetime import datetime


from api_tools.teamvsplayer import (
    fetch_teamvsplayer_logic,
    _get_csv_path_for_team_vs_player, # For verification
    TEAM_VS_PLAYER_CSV_DIR          # For ensuring directory exists
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailedDefense, LeagueID
)

SAMPLE_TEAM_NAME = "Los Angeles Lakers"
SAMPLE_TEAM_ID = "1610612747" # Lakers ID
SAMPLE_VS_PLAYER_NAME = "Stephen Curry"
SAMPLE_VS_PLAYER_ID = "201939" # Stephen Curry ID
SAMPLE_SEASON = "2022-23"
DEFAULT_SEASON_TYPE = SeasonTypeAllStar.regular
DEFAULT_PER_MODE = PerModeDetailed.totals
DEFAULT_MEASURE_TYPE = MeasureTypeDetailedDefense.base

# Expected DataFrame keys from the teamvsplayer endpoint
EXPECTED_DATAFRAME_KEYS = [
    "overall", "on_off_court", "shot_area_overall", "shot_area_on_court",
    "shot_area_off_court", "shot_distance_overall", "shot_distance_on_court",
    "shot_distance_off_court", "vs_player_overall"
]

def _verify_csv_exists(expected_path: str):
    assert os.path.exists(expected_path), f"CSV file not found at {expected_path}"
    print(f"Verified CSV file exists: {expected_path}")

def test_fetch_teamvsplayer_basic():
    """Test fetching team vs player with default parameters."""
    print("\n=== Testing fetch_teamvsplayer_logic (basic) ===")
    json_response = fetch_teamvsplayer_logic(
        SAMPLE_TEAM_NAME,
        SAMPLE_VS_PLAYER_NAME,
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        DEFAULT_MEASURE_TYPE
    )
    data = json.loads(json_response)
    assert isinstance(data, dict), "Response should be a dictionary"
    if "error" in data:
        print(f"API returned an error: {data['error']}")
    else:
        assert "team_name" in data
        assert "vs_player_name" in data
        print(f"Basic team vs player fetched for {data.get('team_name')} vs {data.get('vs_player_name')}")
    print("\n=== Basic team vs player test completed ===")
    return data

def test_fetch_teamvsplayer_dataframe():
    """Test fetching team vs player with DataFrame output and CSV verification."""
    print("\n=== Testing fetch_teamvsplayer_logic with DataFrame output ===")
    result = fetch_teamvsplayer_logic(
        SAMPLE_TEAM_NAME,
        SAMPLE_VS_PLAYER_NAME,
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        DEFAULT_MEASURE_TYPE,
        return_dataframe=True
    )
    assert isinstance(result, tuple) and len(result) == 2
    json_response, dataframes_dict = result
    assert isinstance(json_response, str)
    assert isinstance(dataframes_dict, dict)

    data = json.loads(json_response)
    if "error" in data:
        print(f"API (DataFrame) returned an error: {data['error']}")
    else:
        print(f"Team vs player (DataFrame) fetched for {data.get('team_name')} vs {data.get('vs_player_name')}")
        team_id_for_csv = str(data.get("team_id", SAMPLE_TEAM_ID))
        vs_player_id_for_csv = str(data.get("vs_player_id", SAMPLE_VS_PLAYER_ID))

        print(f"\nDataFrames returned: {list(dataframes_dict.keys())}")
        for key in EXPECTED_DATAFRAME_KEYS:
            assert key in dataframes_dict, f"Expected DataFrame key '{key}' missing"
            df = dataframes_dict[key]
            if not df.empty:
                print(f"\nDataFrame '{key}' shape: {df.shape}")
                print(df.head(2))
                csv_path = _get_csv_path_for_team_vs_player(
                    team_id_for_csv,
                    vs_player_id_for_csv,
                    SAMPLE_SEASON,
                    DEFAULT_SEASON_TYPE,
                    DEFAULT_PER_MODE,
                    DEFAULT_MEASURE_TYPE,
                    dashboard_type=key
                )
                _verify_csv_exists(csv_path)
            else:
                print(f"\nDataFrame '{key}' is empty.")

    print("\n=== DataFrame team vs player test completed ===")
    return json_response, dataframes_dict

def test_fetch_teamvsplayer_advanced():
    """Test fetching team vs player with advanced measure type and additional parameters."""
    print("\n=== Testing fetch_teamvsplayer_logic with advanced measure type and additional parameters ===")
    json_response = fetch_teamvsplayer_logic(
        SAMPLE_TEAM_NAME,
        SAMPLE_VS_PLAYER_NAME,
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        MeasureTypeDetailedDefense.advanced, # Test with Advanced
        last_n_games=10,
        vs_conference_nullable="East",
        location_nullable="Home",
        league_id_nullable=LeagueID.nba
    )
    data = json.loads(json_response)
    assert isinstance(data, dict)
    if "error" in data:
        print(f"API returned an error: {data['error']}")
    else:
        assert data["parameters"]["measure_type"] == MeasureTypeDetailedDefense.advanced
        assert data["parameters"]["last_n_games"] == 10
        assert data["parameters"]["vs_conference"] == "East"
        assert data["parameters"]["location"] == "Home"
        assert data["parameters"]["league_id"] == LeagueID.nba
        print(f"Advanced team vs player fetched for {data.get('team_name')} vs {data.get('vs_player_name')}")
        print(f"Parameters: last_n_games={data['parameters']['last_n_games']}, vs_conference={data['parameters']['vs_conference']}, location={data['parameters']['location']}")
    print("\n=== Advanced measure type and parameters test completed ===")
    return data

# Minimal set of validation tests
def test_invalid_parameters_teamvsplayer():
    print("\n=== Testing invalid parameters for teamvsplayer ===")
    # Test invalid season format
    json_response_season = fetch_teamvsplayer_logic(SAMPLE_TEAM_NAME, SAMPLE_VS_PLAYER_NAME, "20XX-YY")
    data_season = json.loads(json_response_season)
    assert "error" in data_season
    print(f"Invalid season error: {data_season['error']}")

    # Test invalid team identifier
    json_response_team = fetch_teamvsplayer_logic("NotATeam", SAMPLE_VS_PLAYER_NAME, SAMPLE_SEASON)
    data_team = json.loads(json_response_team)
    assert "error" in data_team
    print(f"Invalid team error: {data_team['error']}")

    # Test invalid vs_player identifier
    json_response_vs_player = fetch_teamvsplayer_logic(SAMPLE_TEAM_NAME, "NotAPlayer", SAMPLE_SEASON)
    data_vs_player = json.loads(json_response_vs_player)
    assert "error" in data_vs_player
    print(f"Invalid vs_player error: {data_vs_player['error']}")


def run_all_tests():
    print(f"\n=== Running teamvsplayer smoke tests at {datetime.now().isoformat()} ===\n")

    # Ensure cache directory exists
    os.makedirs(TEAM_VS_PLAYER_CSV_DIR, exist_ok=True)

    test_fetch_teamvsplayer_basic()
    test_fetch_teamvsplayer_dataframe()
    test_fetch_teamvsplayer_advanced()
    test_invalid_parameters_teamvsplayer()

    print("\n\n=== All teamvsplayer tests completed successfully ===")

if __name__ == "__main__":
    run_all_tests()
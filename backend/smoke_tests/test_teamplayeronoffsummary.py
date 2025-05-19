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

from backend.api_tools.teamplayeronoffsummary import (
    fetch_teamplayeronoffsummary_logic,
    _get_csv_path_for_team_player_on_off_summary, # For verification
    TEAM_PLAYER_ON_OFF_CSV_DIR # For ensuring directory exists
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailedDefense, LeagueID
)

SAMPLE_TEAM_NAME = "Los Angeles Lakers"
SAMPLE_TEAM_ID = "1610612747" # Lakers ID, actual ID will be resolved from response
SAMPLE_SEASON = "2022-23"
DEFAULT_SEASON_TYPE = SeasonTypeAllStar.regular
DEFAULT_PER_MODE = PerModeDetailed.totals
DEFAULT_MEASURE_TYPE = MeasureTypeDetailedDefense.base

def _verify_csv_exists(expected_path: str):
    assert os.path.exists(expected_path), f"CSV file not found at {expected_path}"
    print(f"Verified CSV file exists: {expected_path}")

def test_fetch_teamplayeronoffsummary_basic():
    """Test fetching team player on/off summary with default parameters."""
    print("\n=== Testing fetch_teamplayeronoffsummary_logic (basic) ===")
    json_response = fetch_teamplayeronoffsummary_logic(
        SAMPLE_TEAM_NAME,
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
        print(f"Basic on/off summary fetched for {data.get('team_name')}")
    print("\n=== Basic team player on/off summary test completed ===")
    return data

def test_fetch_teamplayeronoffsummary_dataframe():
    """Test fetching team player on/off summary with DataFrame output."""
    print("\n=== Testing fetch_teamplayeronoffsummary_logic with DataFrame output ===")
    result = fetch_teamplayeronoffsummary_logic(
        SAMPLE_TEAM_NAME,
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
        print(f"On/off summary (DataFrame) fetched for {data.get('team_name')}")
        team_id_for_csv = str(data.get("team_id", SAMPLE_TEAM_ID))

        print(f"\nDataFrames returned: {list(dataframes_dict.keys())}")
        expected_df_keys = ["overall", "off_court", "on_court"]
        for key in expected_df_keys:
            assert key in dataframes_dict, f"DataFrame key '{key}' missing"
            df = dataframes_dict[key]
            if not df.empty:
                print(f"\nDataFrame '{key}' shape: {df.shape}")
                print(df.head(2))
                csv_path = _get_csv_path_for_team_player_on_off_summary(
                    team_id_for_csv,
                    SAMPLE_SEASON,
                    DEFAULT_SEASON_TYPE,
                    DEFAULT_PER_MODE,
                    DEFAULT_MEASURE_TYPE,
                    dashboard_type=key
                )
                _verify_csv_exists(csv_path)
            else:
                print(f"\nDataFrame '{key}' is empty.")

    print("\n=== DataFrame team player on/off summary test completed ===")
    return json_response, dataframes_dict

def test_fetch_teamplayeronoffsummary_advanced():
    """Test fetching team player on/off summary with advanced measure type."""
    print("\n=== Testing fetch_teamplayeronoffsummary_logic with advanced measure type ===")
    json_response = fetch_teamplayeronoffsummary_logic(
        SAMPLE_TEAM_NAME,
        SAMPLE_SEASON,
        DEFAULT_SEASON_TYPE,
        DEFAULT_PER_MODE,
        MeasureTypeDetailedDefense.advanced # Test with Advanced
    )
    data = json.loads(json_response)
    assert isinstance(data, dict)
    if "error" in data:
        print(f"API returned an error: {data['error']}")
    else:
        assert data["parameters"]["measure_type"] == MeasureTypeDetailedDefense.advanced
        print(f"Advanced on/off summary fetched for {data.get('team_name')}")
    print("\n=== Advanced measure type test completed ===")
    return data

# Minimal set of validation tests for brevity, expand as needed
def test_invalid_parameters_teamplayeronoffsummary():
    print("\n=== Testing invalid parameters for teamplayeronoffsummary ===")
    # Test invalid season format
    json_response_season = fetch_teamplayeronoffsummary_logic(SAMPLE_TEAM_NAME, "20XX-YY")
    data_season = json.loads(json_response_season)
    assert "error" in data_season
    print(f"Invalid season error: {data_season['error']}")

    # Test invalid team identifier
    json_response_team = fetch_teamplayeronoffsummary_logic("NotATeam", SAMPLE_SEASON)
    data_team = json.loads(json_response_team)
    assert "error" in data_team
    print(f"Invalid team error: {data_team['error']}")


def run_all_tests():
    print(f"\n=== Running teamplayeronoffsummary smoke tests at {datetime.now().isoformat()} ===\n")
    
    # Ensure cache directory exists
    os.makedirs(TEAM_PLAYER_ON_OFF_CSV_DIR, exist_ok=True)

    test_fetch_teamplayeronoffsummary_basic()
    test_fetch_teamplayeronoffsummary_dataframe()
    test_fetch_teamplayeronoffsummary_advanced()
    test_invalid_parameters_teamplayeronoffsummary()
        
    print("\n\n=== All teamplayeronoffsummary tests completed successfully ===")

if __name__ == "__main__":
    run_all_tests() 
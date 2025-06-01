"""
Smoke test for the team_history (CommonTeamYears) module.
Tests fetching team history data and CSV caching.
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

from api_tools.team_history import (
    fetch_common_team_years_logic,
    _get_csv_path_for_team_history,  # For verification
    TEAM_HISTORY_CSV_DIR             # For ensuring directory exists
)
from nba_api.stats.library.parameters import LeagueID
SAMPLE_LEAGUE_ID = LeagueID.nba # "00"

def _verify_csv_exists(expected_path: str):
    assert os.path.exists(expected_path), f"CSV file not found at {expected_path}"
    print(f"Verified CSV file exists: {expected_path}")

def test_fetch_common_team_years_basic():
    """Test fetching common team years with default parameters."""
    print("\n=== Testing fetch_common_team_years_logic (basic) ===")
    json_response = fetch_common_team_years_logic(league_id=SAMPLE_LEAGUE_ID)
    data = json.loads(json_response)
    assert isinstance(data, dict), "Response should be a dictionary"
    if "error" in data:
        print(f"API returned an error: {data['error']}")
    else:
        assert "parameters" in data
        assert data["parameters"]["league_id"] == SAMPLE_LEAGUE_ID
        assert "team_years" in data
        assert isinstance(data["team_years"], list)
        if data["team_years"]:
            assert "TEAM_ID" in data["team_years"][0]
        print(f"Basic team history fetched for League ID: {SAMPLE_LEAGUE_ID}, {len(data['team_years'])} entries found.")
    print("\n=== Basic team history test completed ===")
    return data

def test_fetch_common_team_years_dataframe():
    """Test fetching common team years with DataFrame output and CSV verification."""
    print("\n=== Testing fetch_common_team_years_logic with DataFrame output ===")
    result = fetch_common_team_years_logic(league_id=SAMPLE_LEAGUE_ID, return_dataframe=True)

    assert isinstance(result, tuple) and len(result) == 2, "Result should be a tuple (json_str, df_dict)"
    json_response, dataframes_dict = result
    assert isinstance(json_response, str), "First element of tuple should be JSON string"
    assert isinstance(dataframes_dict, dict), "Second element of tuple should be a dictionary of DataFrames"

    data = json.loads(json_response)
    if "error" in data:
        print(f"API (DataFrame) returned an error: {data['error']}")
    else:
        print(f"Team history (DataFrame) fetched for League ID: {SAMPLE_LEAGUE_ID}")
        assert "team_years" in dataframes_dict, "'team_years' DataFrame missing"

        team_years_df = dataframes_dict["team_years"]
        assert isinstance(team_years_df, pd.DataFrame), "'team_years' should be a DataFrame"

        if not team_years_df.empty:
            print(f"\nDataFrame 'team_years' shape: {team_years_df.shape}")
            print(team_years_df.head(2))

            # Check if the dataframe_info field exists in the response
            if "dataframe_info" in data:
                print("\nDataFrame info found in response:")
                print(f"Message: {data['dataframe_info'].get('message', 'N/A')}")

                # Check if the CSV paths are included
                for df_key, df_info in data["dataframe_info"].get("dataframes", {}).items():
                    csv_path = df_info.get("csv_path")
                    if csv_path:
                        full_path = os.path.join(backend_dir, csv_path)
                        if os.path.exists(full_path):
                            print(f"\nCSV file exists: {csv_path}")
                            csv_size = os.path.getsize(full_path)
                            print(f"CSV file size: {csv_size} bytes")
                        else:
                            print(f"\nCSV file does not exist: {csv_path}")
            else:
                print("\nNo DataFrame info found in response (this is unexpected).")

            # Also verify using the old method
            csv_path = _get_csv_path_for_team_history(SAMPLE_LEAGUE_ID)
            _verify_csv_exists(csv_path)
        else:
            print("\nDataFrame 'team_years' is empty (this might be unexpected for NBA).")

    print("\n=== DataFrame team history test completed ===")
    return json_response, dataframes_dict

def test_invalid_league_id():
    """Test fetching with an invalid league ID."""
    print("\n=== Testing fetch_common_team_years_logic with invalid League ID ===")
    invalid_league_id = "99"
    json_response = fetch_common_team_years_logic(league_id=invalid_league_id)
    data = json.loads(json_response)
    assert "error" in data, "Should return an error for invalid league ID"
    print(f"Received expected error for invalid League ID '{invalid_league_id}': {data['error']}")
    print("\n=== Invalid League ID test completed ===")

def run_all_tests():
    print(f"\n=== Running team_history (CommonTeamYears) smoke tests at {datetime.now().isoformat()} ===\n")

    # Ensure cache directory exists
    os.makedirs(TEAM_HISTORY_CSV_DIR, exist_ok=True)

    test_fetch_common_team_years_basic()
    test_fetch_common_team_years_dataframe()
    test_invalid_league_id()

    print("\n\n=== All team_history tests completed successfully ===")

if __name__ == "__main__":
    run_all_tests()
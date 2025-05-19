import os
import sys
import json
import pandas as pd
import pytest

# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

from backend.api_tools.team_historical_leaders import fetch_team_historical_leaders_logic
from nba_api.stats.library.parameters import LeagueID
from backend.core.errors import Errors # For checking error messages

# Sample data for testing
SAMPLE_TEAM = "Los Angeles Lakers"
SAMPLE_TEAM_ID_STR = "1610612747"
SAMPLE_SEASON_ID = "22022"  # Corresponds to 2022-23 season
ALT_SEASON_ID = "22021" # Corresponds to 2021-22 season
INVALID_SEASON_ID_FORMAT = "2022" # Invalid format
NON_EXISTENT_TEAM = "Non Existent Team FC"

# Helper to run validation error tests
def run_validation_test(test_name, logic_kwargs, expected_error_substring):
    print(f"\n=== Testing Validation: {test_name} ===")
    json_response = fetch_team_historical_leaders_logic(**logic_kwargs)
    data = json.loads(json_response)
    assert "error" in data, f"Expected error for {test_name}, but got none."
    assert expected_error_substring.lower() in data["error"].lower(), \
        f"For {test_name}, expected error containing '{expected_error_substring}', but got '{data['error']}'"
    print(f"Got expected error: {data['error']}")

def test_fetch_team_historical_leaders_basic():
    """Test basic fetching of team historical leaders."""
    print(f"\n=== Testing fetch_team_historical_leaders_logic (basic) for {SAMPLE_TEAM}, SeasonID: {SAMPLE_SEASON_ID} ===")
    json_response = fetch_team_historical_leaders_logic(SAMPLE_TEAM, SAMPLE_SEASON_ID)
    print("\n=== RAW JSON RESPONSE (BASIC) ===")
    print(json_response)
    data = json.loads(json_response)
    assert isinstance(data, dict), "Response should be a dictionary"
    if "error" in data:
        print(f"API returned an error (might be due to API limits/availability or no data for this combo): {data['error']}")
    else:
        assert "team_name" in data and data["team_name"].lower() == SAMPLE_TEAM.lower()
        assert "team_id" in data and data["team_id"] == int(SAMPLE_TEAM_ID_STR)
        assert "parameters" in data
        assert data["parameters"]["season_id"] == SAMPLE_SEASON_ID
        assert "career_leaders_by_team" in data, "Missing 'career_leaders_by_team' in response"
        assert isinstance(data["career_leaders_by_team"], list), "'career_leaders_by_team' should be a list"
        print(f"Team Name: {data.get('team_name')}, Team ID: {data.get('team_id')}")
        print(f"Leaders count: {len(data['career_leaders_by_team'])}")
        if data['career_leaders_by_team']:
            print("Sample Leader:", data['career_leaders_by_team'][0])
    print("=== Basic test completed ===")

def test_fetch_team_historical_leaders_dataframe():
    """Test fetching with DataFrame output."""
    print(f"\n=== Testing fetch_team_historical_leaders_logic (DataFrame) for {SAMPLE_TEAM}, SeasonID: {SAMPLE_SEASON_ID} ===")
    result = fetch_team_historical_leaders_logic(SAMPLE_TEAM, SAMPLE_SEASON_ID, return_dataframe=True)
    assert isinstance(result, tuple) and len(result) == 2
    json_response, dataframes = result
    data = json.loads(json_response) # To check for errors
    assert isinstance(dataframes, dict)
    if "error" not in data:
        assert "career_leaders_by_team" in dataframes
        print(f"DataFrame 'career_leaders_by_team' returned.")
        df = dataframes["career_leaders_by_team"]
        assert isinstance(df, pd.DataFrame)
        print(f"DataFrame shape: {df.shape}")
        if not df.empty: print(df.head(2))
    else:
        print(f"API Error, DataFrames might be empty or not as expected: {data['error']}")
        # Check if it's a validation error we expect an empty dict for
        if any(err_msg_part in data['error'] for err_msg_part in [
            Errors.TEAM_IDENTIFIER_EMPTY, "SeasonID format", "league_id"
        ]):
            assert dataframes == {}, "DataFrames should be empty on pre-API validation error"
    print("=== DataFrame test completed ===")

def test_all_parameters_set():
    """Test calling with all parameters, including non-default league_id."""
    print(f"\n=== Testing with all parameters for {SAMPLE_TEAM}, SeasonID: {ALT_SEASON_ID}, LeagueID: WNBA ===")
    json_response = fetch_team_historical_leaders_logic(
        team_identifier=SAMPLE_TEAM, # Lakers ID is NBA specific, so this will likely fail gracefully or return empty.
        season_id=ALT_SEASON_ID,
        league_id=LeagueID.wnba # "10"
    )
    print("\n=== RAW JSON RESPONSE (ALL PARAMS) ===")
    print(json_response)
    data = json.loads(json_response)
    assert isinstance(data, dict)
    if "error" in data:
        # It's expected that an NBA team_id might not work for WNBA, or WNBA has no data for this specific "team"
        print(f"API Error or no data for WNBA context: {data['error']}")
    else:
        assert data["parameters"]["league_id"] == LeagueID.wnba
        assert data["parameters"]["season_id"] == ALT_SEASON_ID
        # Data presence for this specific cross-league query isn't strictly asserted
        print(f"Leaders count for WNBA context: {len(data['career_leaders_by_team'])}")
    print("=== All parameters test completed ===")

def test_validation_errors_main():
    """Test various parameter validation errors."""
    run_validation_test(
        "Empty Team Identifier", 
        {"team_identifier": "", "season_id": SAMPLE_SEASON_ID}, 
        Errors.TEAM_IDENTIFIER_EMPTY
    )
    run_validation_test(
        "Invalid SeasonID Format (too short)", 
        {"team_identifier": SAMPLE_TEAM, "season_id": "2202"}, 
        "Invalid format for parameter 'SeasonID'"
    )
    run_validation_test(
        "Invalid SeasonID Format (non-digit)", 
        {"team_identifier": SAMPLE_TEAM, "season_id": "ABCDE"}, 
        "Invalid format for parameter 'SeasonID'"
    )
    run_validation_test(
        "Invalid League ID", 
        {"team_identifier": SAMPLE_TEAM, "season_id": SAMPLE_SEASON_ID, "league_id": "99"}, 
        "Invalid league_id"
    )

def test_team_not_found_error():
    print(f"\n=== Testing Team Not Found: {NON_EXISTENT_TEAM} ===")
    json_response = fetch_team_historical_leaders_logic(NON_EXISTENT_TEAM, SAMPLE_SEASON_ID)
    data = json.loads(json_response)
    assert "error" in data
    assert NON_EXISTENT_TEAM.lower() in data["error"].lower() or "not found" in data["error"].lower()
    print(f"Got expected error for non-existent team: {data['error']}")
    print("=== Team Not Found test completed ===")

def test_empty_results_scenario_very_old_season():
    """Test a scenario likely to yield empty results (e.g., very old season)."""
    old_season_id = "00001" # Hypothetical very old season for testing empty returns
    print(f"\n=== Testing likely empty results for {SAMPLE_TEAM}, SeasonID: {old_season_id} ===")
    json_response = fetch_team_historical_leaders_logic(SAMPLE_TEAM, old_season_id)
    data = json.loads(json_response)
    assert isinstance(data, dict)
    if "error" in data:
        print(f"API error for old season (might be expected): {data['error']}")
    else:
        assert "career_leaders_by_team" in data and isinstance(data["career_leaders_by_team"], list)
        print(f"Leaders count for old season: {len(data['career_leaders_by_team'])}")
        # It's possible/likely this returns empty, which is okay.
        assert len(data['career_leaders_by_team']) == 0, "Expected empty list for a very old or non-existent season data for a team"

    print("=== Empty results scenario test completed ===")

def test_api_error_simulation(monkeypatch):
    """Test simulation of an NBA API internal error."""
    print("\n=== Testing API error simulation ===")
    
    # Dynamically get the module and class to mock
    module_path = 'nba_api.stats.endpoints.teamhistoricalleaders'
    class_name = 'TeamHistoricalLeaders'

    original_endpoint_class = getattr(sys.modules[module_path], class_name)

    class MockTeamHistoricalLeaders:
        def __init__(self, *args, **kwargs):
            # Simulate an error during instantiation or API call phase
            raise Exception("Simulated NBA API internal server error")

        @property
        def career_leaders_by_team(self):
            # This property should not be reached if __init__ raises an error
            raise NotImplementedError("career_leaders_by_team should not be called if __init__ fails")

    monkeypatch.setattr(f"{module_path}.{class_name}", MockTeamHistoricalLeaders)
    
    json_response = fetch_team_historical_leaders_logic(SAMPLE_TEAM, SAMPLE_SEASON_ID)
    data = json.loads(json_response)
    
    assert "error" in data, "Error message should be present for simulated API failure"
    error_message = data["error"].lower()
    # Check if the primary simulation message OR the generic API error message (without specific details) is present
    assert "simulated nba api internal server error" in error_message or \
           Errors.NBA_API_ERROR.format(endpoint_name=class_name, error="").lower().split(':')[0] in error_message, \
        f"Error message did not contain expected simulation text. Got: {data['error']}"
    print(f"Simulated API error handled: {data['error']}")
    
    # Restore original class to avoid affecting other tests if run in the same session without full pytest isolation
    monkeypatch.setattr(f"{module_path}.{class_name}", original_endpoint_class)
    print("=== API error simulation test completed ===")

if __name__ == "__main__":
    print("Running tests directly (pytest is recommended for full functionality like monkeypatching)...")
    test_fetch_team_historical_leaders_basic()
    test_fetch_team_historical_leaders_dataframe()
    test_all_parameters_set()
    test_validation_errors_main()
    test_team_not_found_error()
    test_empty_results_scenario_very_old_season()
    print("\nTo run the API error simulation, use: pytest backend/smoke_tests/test_team_historical_leaders.py -k test_api_error_simulation -s")
    print("\nAll direct tests finished.") 
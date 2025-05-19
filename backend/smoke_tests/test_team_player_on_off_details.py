import os
import sys
import json
import pandas as pd
from datetime import datetime
import pytest # For monkeypatching

# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

from backend.api_tools.team_player_on_off_details import fetch_team_player_on_off_details_logic
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed,
    MeasureTypeDetailedDefense,
    LeagueID
)
from backend.core.errors import Errors # For checking error messages

# Sample data for testing
SAMPLE_TEAM = "Golden State Warriors"
SAMPLE_TEAM_ID = "1610612744"
SAMPLE_SEASON = "2022-23" # A season with known data
ALT_SEASON = "2021-22"
NON_EXISTENT_TEAM = "Non Existent Team FC"
# ERROR_SIM_TEAM = "Error Sim Team" # Placeholder for monkeypatching - not strictly needed if monkeypatching the endpoint directly

def test_fetch_team_player_on_off_details_basic():
    """Test basic fetching of team player on/off details."""
    print(f"\n=== Testing fetch_team_player_on_off_details_logic (basic) for {SAMPLE_TEAM}, {SAMPLE_SEASON} ===")
    json_response = fetch_team_player_on_off_details_logic(SAMPLE_TEAM, SAMPLE_SEASON)
    data = json.loads(json_response)
    assert isinstance(data, dict), "Response should be a dictionary"
    if "error" in data:
        print(f"API returned an error (might be due to API limits/availability): {data['error']}")
    else:
        assert "team_name" in data and data["team_name"].lower() == SAMPLE_TEAM.lower()
        assert "team_id" in data and data["team_id"] == int(SAMPLE_TEAM_ID)
        assert "parameters" in data
        for key in ["overall_team_player_on_off_details", "players_off_court_team_player_on_off_details", "players_on_court_team_player_on_off_details"]:
            assert key in data, f"Missing {key} in response"
            assert isinstance(data[key], list), f"{key} should be a list"
        print(f"Team Name: {data.get('team_name')}, Team ID: {data.get('team_id')}")
        print(f"Overall details count: {len(data['overall_team_player_on_off_details'])}")
        print(f"Off-court details count: {len(data['players_off_court_team_player_on_off_details'])}")
        print(f"On-court details count: {len(data['players_on_court_team_player_on_off_details'])}")
        if data['overall_team_player_on_off_details']: # Check if list is not empty
            print("Sample Overall Detail:", data['overall_team_player_on_off_details'][0])
        elif data['players_off_court_team_player_on_off_details']:
             print("Sample Off-Court Detail:", data['players_off_court_team_player_on_off_details'][0])
        elif data['players_on_court_team_player_on_off_details']:
             print("Sample On-Court Detail:", data['players_on_court_team_player_on_off_details'][0])

    print("=== Basic test completed ===")

def test_fetch_team_player_on_off_details_dataframe():
    """Test fetching with DataFrame output."""
    print(f"\n=== Testing fetch_team_player_on_off_details_logic (DataFrame) for {SAMPLE_TEAM}, {SAMPLE_SEASON} ===")
    result = fetch_team_player_on_off_details_logic(SAMPLE_TEAM, SAMPLE_SEASON, return_dataframe=True)
    assert isinstance(result, tuple) and len(result) == 2
    json_response, dataframes = result
    data = json.loads(json_response) # To check for errors
    assert isinstance(dataframes, dict)
    if "error" not in data:
        assert "overall" in dataframes
        assert "off_court" in dataframes
        assert "on_court" in dataframes
        print(f"DataFrames returned: {list(dataframes.keys())}")
        for name, df in dataframes.items():
            assert isinstance(df, pd.DataFrame)
            print(f"DataFrame '{name}' shape: {df.shape}")
            if not df.empty: print(df.head(1))
    else:
        print(f"API Error, DataFrames might be empty or not as expected: {data['error']}")
        # For pre-API validation errors, dataframes should be an empty dict.
        # For API errors after validation, it could be non-empty if some data was processed before error.
        # The core logic ensures dataframes is initialized to {} and returned as such with error before API call
        if any(err_msg_part in data['error'] for err_msg_part in [
            Errors.TEAM_IDENTIFIER_EMPTY,
            "season format", "date format", "season type", "per mode", "measure type", "league_id",
            "pace_adjust value", "plus_minus value", "rank value",
            "division value", "conference value", "season_segment value",
            "outcome value", "location value", "game_segment value"
        ]):
             assert dataframes == {}, "DataFrames should be empty on pre-API validation error"
    print("=== DataFrame test completed ===")

def test_all_optional_parameters_set():
    """Test calling the endpoint with all optional parameters populated."""
    print(f"\n=== Testing fetch_team_player_on_off_details_logic with all optional parameters for {SAMPLE_TEAM} ===")
    json_response = fetch_team_player_on_off_details_logic(
        team_identifier=SAMPLE_TEAM,
        season=ALT_SEASON, 
        season_type=SeasonTypeAllStar.playoffs,
        per_mode=PerModeDetailed.per_game,
        measure_type=MeasureTypeDetailedDefense.advanced,
        last_n_games=5,
        month=4, 
        opponent_team_id=1610612738, 
        pace_adjust="Y",
        period=1,
        plus_minus="Y",
        rank="Y",
        vs_division_nullable="Pacific",
        vs_conference_nullable="West",
        season_segment_nullable="Post All-Star",
        outcome_nullable="W",
        location_nullable="Home",
        league_id_nullable=LeagueID.nba,
        game_segment_nullable="First Half",
        date_from_nullable="2022-04-01",
        date_to_nullable="2022-04-30"
    )
    data = json.loads(json_response)
    assert isinstance(data, dict)
    if "error" in data:
        print(f"API Error with all optionals: {data['error']}")
    else:
        params = data["parameters"]
        assert params["season"] == ALT_SEASON
        assert params["season_type_all_star"] == SeasonTypeAllStar.playoffs
        assert params["per_mode_detailed"] == PerModeDetailed.per_game
        # ... (add more assertions for other params if crucial)
        print("Successfully called with all optional parameters.")
    print("=== All optional parameters test completed ===")

def run_validation_error_test(test_name, logic_kwargs, expected_error_substring):
    print(f"\n=== Testing: {test_name} ===")
    json_response = fetch_team_player_on_off_details_logic(**logic_kwargs)
    data = json.loads(json_response)
    assert "error" in data, f"Expected error for {test_name}, but got none."
    assert expected_error_substring.lower() in data["error"].lower(), \
        f"For {test_name}, expected error containing '{expected_error_substring}', but got '{data['error']}'"
    print(f"Got expected error: {data['error']}")
    print(f"=== {test_name} completed ===")

def test_validation_errors():
    base_args = {"team_identifier": SAMPLE_TEAM, "season": SAMPLE_SEASON}
    
    run_validation_error_test("Empty Team Identifier", {"team_identifier": "", "season": SAMPLE_SEASON}, Errors.TEAM_IDENTIFIER_EMPTY)
    run_validation_error_test("Invalid Season Format", {**base_args, "season": "2023"}, "Invalid season format")
    run_validation_error_test("Invalid Date From Format", {**base_args, "date_from_nullable": "01-01-2023"}, "Invalid date format")
    run_validation_error_test("Invalid Date To Format", {**base_args, "date_to_nullable": "2023/01/01"}, "Invalid date format")
    run_validation_error_test("Invalid Season Type", {**base_args, "season_type": "Invalid"}, "Invalid season_type")
    run_validation_error_test("Invalid Per Mode", {**base_args, "per_mode": "Invalid"}, "Invalid per_mode")
    run_validation_error_test("Invalid Measure Type", {**base_args, "measure_type": "Invalid"}, "Invalid measure_type")
    run_validation_error_test("Invalid League ID", {**base_args, "league_id_nullable": "99"}, "Invalid league_id")
    run_validation_error_test("Invalid Pace Adjust", {**base_args, "pace_adjust": "Maybe"}, "Invalid pace_adjust value")
    run_validation_error_test("Invalid Plus Minus", {**base_args, "plus_minus": "Perhaps"}, "Invalid plus_minus value")
    run_validation_error_test("Invalid Rank", {**base_args, "rank": "Sometimes"}, "Invalid rank value")
    run_validation_error_test("Invalid Vs Division", {**base_args, "vs_division_nullable": "NonExistent"}, "Invalid vs_division")
    run_validation_error_test("Invalid Vs Conference", {**base_args, "vs_conference_nullable": "SolarSystem"}, "Invalid vs_conference")
    run_validation_error_test("Invalid Season Segment", {**base_args, "season_segment_nullable": "Mid-Season"}, "Invalid season_segment")
    run_validation_error_test("Invalid Outcome", {**base_args, "outcome_nullable": "Draw"}, "Invalid outcome")
    run_validation_error_test("Invalid Location", {**base_args, "location_nullable": "Neutral"}, "Invalid location")
    run_validation_error_test("Invalid Game Segment", {**base_args, "game_segment_nullable": "HalfTimeShow"}, "Invalid game_segment")

def test_team_not_found():
    print(f"\n=== Testing Team Not Found: {NON_EXISTENT_TEAM} ===")
    json_response = fetch_team_player_on_off_details_logic(NON_EXISTENT_TEAM, SAMPLE_SEASON)
    data = json.loads(json_response)
    assert "error" in data
    assert NON_EXISTENT_TEAM.lower() in data["error"].lower() or "not found" in data["error"].lower()
    print(f"Got expected error for non-existent team: {data['error']}")
    print("=== Team Not Found test completed ===")

def test_empty_results_scenario():
    # Use a very old season or unlikely combination to try and get empty results
    # Note: The API might still return team shells or metadata.
    # The goal is to ensure it handles cases where data arrays are empty.
    print(f"\n=== Testing scenario likely to yield empty or minimal results (e.g., old season {SAMPLE_TEAM}, 1950-51) ===")
    json_response = fetch_team_player_on_off_details_logic(SAMPLE_TEAM, "1950-51") 
    data = json.loads(json_response)
    assert isinstance(data, dict)
    if "error" in data:
        print(f"API error for old season (might be expected): {data['error']}")
    else:
        assert "overall_team_player_on_off_details" in data and isinstance(data["overall_team_player_on_off_details"], list)
        assert "players_off_court_team_player_on_off_details" in data and isinstance(data["players_off_court_team_player_on_off_details"], list)
        assert "players_on_court_team_player_on_off_details" in data and isinstance(data["players_on_court_team_player_on_off_details"], list)
        # It's possible overall_team_player_on_off_details has one entry for the team itself, even if players lists are empty
        print(f"Overall details count: {len(data['overall_team_player_on_off_details'])}")
        print(f"Off-court details count: {len(data['players_off_court_team_player_on_off_details'])}")
        print(f"On-court details count: {len(data['players_on_court_team_player_on_off_details'])}")
        # Assert that player-specific lists are empty if the overall team context doesn't make sense for players (e.g. team didn't exist)
        # This specific check might need adjustment based on actual API behavior for such old seasons.
        # For now, we just check that the structure is correct and lists are present.
    print("=== Empty results scenario test completed ===")

def test_api_error_simulation(monkeypatch):
    print("\n=== Testing API error simulation ===")
    
    # Store the original endpoint class
    original_endpoint_class = sys.modules['nba_api.stats.endpoints.teamplayeronoffdetails'].TeamPlayerOnOffDetails

    class MockTeamPlayerOnOffDetails:
        def __init__(self, *args, **kwargs):
            # Simulate an API error during endpoint instantiation or a subsequent call
            raise Exception("Simulated NBA API internal server error during instantiation or call")

        # Mock the result set attributes expected by the logic
        @property
        def overall_team_player_on_off_details(self):
            # In a real scenario where instantiation might succeed but data fetching fails,
            # this mock would need a get_data_frame method raising an error.
            # For simplicity, if __init__ raises, these won't be called.
            raise NotImplementedError("This should not be called if __init__ fails")

        @property
        def players_off_court_team_player_on_off_details(self):
            raise NotImplementedError("This should not be called if __init__ fails")

        @property
        def players_on_court_team_player_on_off_details(self):
            raise NotImplementedError("This should not be called if __init__ fails")

    # Temporarily replace the real endpoint with our mock
    monkeypatch.setattr("nba_api.stats.endpoints.teamplayeronoffdetails.TeamPlayerOnOffDetails", MockTeamPlayerOnOffDetails)
    
    json_response = fetch_team_player_on_off_details_logic(SAMPLE_TEAM, SAMPLE_SEASON)
    data = json.loads(json_response)
    
    assert "error" in data, "Error message should be present in response for simulated API failure"
    assert "simulated nba api internal server error" in data["error"].lower(), \
        f"Error message should contain the simulated error, but got: {data['error']}"
    print(f"Simulated API error handled: {data['error']}")
    
    # Restore the original class to avoid affecting other tests if run in the same session
    # monkeypatch usually handles this, but good to be explicit if needed in other contexts.
    # sys.modules['nba_api.stats.endpoints.teamplayeronoffdetails'].TeamPlayerOnOffDetails = original_endpoint_class

    print("=== API error simulation test completed ===")

if __name__ == "__main__":
    # This allows running the test script directly, though pytest is preferred.
    # Note: monkeypatching might behave differently or require pytest to run.
    print("Running tests directly (pytest is recommended for full functionality like monkeypatching)...")
    test_fetch_team_player_on_off_details_basic()
    test_fetch_team_player_on_off_details_dataframe()
    test_all_optional_parameters_set()
    test_validation_errors()
    test_team_not_found()
    test_empty_results_scenario()
    # For test_api_error_simulation, it's best to run with pytest:
    # pytest backend/smoke_tests/test_team_player_on_off_details.py -k test_api_error_simulation -s
    print("\nTo run the API error simulation, use: pytest backend/smoke_tests/test_team_player_on_off_details.py -k test_api_error_simulation -s")
    print("\nAll direct tests finished.") 
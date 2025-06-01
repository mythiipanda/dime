import os
import sys
import json
import pandas as pd
from datetime import datetime
import pytest # For monkeypatching


from api_tools.team_player_on_off_details import fetch_team_player_on_off_details_logic
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed,
    MeasureTypeDetailedDefense,
    LeagueID
)
from core.errors import Errors # For checking error messages
# Sample data for testing
SAMPLE_TEAM = "Golden State Warriors"
SAMPLE_TEAM_ID = "1610612744"
SAMPLE_SEASON = "2022-23" # A season with known data
ALT_SEASON = "2021-22"
NON_EXISTENT_TEAM = "Non Existent Team FC"

def test_fetch_team_player_on_off_details_basic():
    """Test basic fetching of team player on/off details."""
    print(f"\n=== Testing fetch_team_player_on_off_details_logic (basic) for {SAMPLE_TEAM}, {SAMPLE_SEASON} ===")
    json_response = fetch_team_player_on_off_details_logic(SAMPLE_TEAM, SAMPLE_SEASON)
    print("\n=== RAW JSON RESPONSE (BASIC) ===")
    print(json_response)
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
    print("\n=== RAW JSON RESPONSE (ALL OPTIONALS) ===")
    print(json_response)
    data = json.loads(json_response)
    assert isinstance(data, dict)
    if "error" in data:
        print(f"API Error with all optionals: {data['error']}")
    else:
        params = data["parameters"]
        assert params["season"] == ALT_SEASON
        assert params["season_type_all_star"] == SeasonTypeAllStar.playoffs
        assert params["per_mode_detailed"] == PerModeDetailed.per_game
        assert params["measure_type_detailed_defense"] == MeasureTypeDetailedDefense.advanced
        assert params["last_n_games"] == 5
        assert params["month"] == 4
        assert params["opponent_team_id"] == 1610612738
        assert params["pace_adjust"] == "Y"
        assert params["period"] == 1
        assert params["plus_minus"] == "Y"
        assert params["rank"] == "Y"
        assert params["vs_division_nullable"] == "Pacific"
        assert params["vs_conference_nullable"] == "West"
        assert params["season_segment_nullable"] == "Post All-Star"
        assert params["outcome_nullable"] == "W"
        assert params["location_nullable"] == "Home"
        assert params["league_id_nullable"] == LeagueID.nba
        assert params["game_segment_nullable"] == "First Half"
        assert params["date_from_nullable"] == "2022-04-01"
        assert params["date_to_nullable"] == "2022-04-30"
        print("Successfully called with all optional parameters and validated parameters in response (data presence not strictly asserted for this specific combination).")
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
        print(f"Overall details count: {len(data['overall_team_player_on_off_details'])}")
        print(f"Off-court details count: {len(data['players_off_court_team_player_on_off_details'])}")
        print(f"On-court details count: {len(data['players_on_court_team_player_on_off_details'])}")
    print("=== Empty results scenario test completed ===")

def test_api_error_simulation(monkeypatch):
    print("\n=== Testing API error simulation ===")
    
    original_endpoint_class = sys.modules['nba_api.stats.endpoints.teamplayeronoffdetails'].TeamPlayerOnOffDetails

    class MockTeamPlayerOnOffDetails:
        def __init__(self, *args, **kwargs):
            raise Exception("Simulated NBA API internal server error during instantiation or call")

        @property
        def overall_team_player_on_off_details(self):
            raise NotImplementedError("This should not be called if __init__ fails")

        @property
        def players_off_court_team_player_on_off_details(self):
            raise NotImplementedError("This should not be called if __init__ fails")

        @property
        def players_on_court_team_player_on_off_details(self):
            raise NotImplementedError("This should not be called if __init__ fails")

    monkeypatch.setattr("nba_api.stats.endpoints.teamplayeronoffdetails.TeamPlayerOnOffDetails", MockTeamPlayerOnOffDetails)
    
    json_response = fetch_team_player_on_off_details_logic(SAMPLE_TEAM, SAMPLE_SEASON)
    data = json.loads(json_response)
    
    assert "error" in data, "Error message should be present in response for simulated API failure"
    assert "simulated nba api internal server error" in data["error"].lower(), \
        f"Error message should contain the simulated error, but got: {data['error']}"
    print(f"Simulated API error handled: {data['error']}")
    
    print("=== API error simulation test completed ===")

if __name__ == "__main__":
    print("Running tests directly (pytest is recommended for full functionality like monkeypatching)...")
    test_fetch_team_player_on_off_details_basic()
    test_fetch_team_player_on_off_details_dataframe()
    test_all_optional_parameters_set()
    test_validation_errors()
    test_team_not_found()
    test_empty_results_scenario()
    print("\nTo run the API error simulation, use: pytest backend/smoke_tests/test_team_player_on_off_details.py -k test_api_error_simulation -s")
    print("\nAll direct tests finished.") 
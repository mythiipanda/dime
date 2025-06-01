import os
import sys
import json
import pandas as pd
from datetime import datetime


from api_tools.team_player_dashboard import fetch_team_player_dashboard_logic
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailedDefense, LeagueID
)

# Sample data for testing
SAMPLE_TEAM = "Golden State Warriors"
SAMPLE_SEASON = "2022-23" # A season with known data

def test_fetch_team_player_dashboard_basic():
    """Test fetching team player dashboard with default parameters."""
    print(f"\n=== Testing fetch_team_player_dashboard_logic (basic) for {SAMPLE_TEAM} ===")
    json_response = fetch_team_player_dashboard_logic(
        SAMPLE_TEAM,
        SAMPLE_SEASON
    )
    data = json.loads(json_response)
    assert isinstance(data, dict), "Response should be a dictionary"
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited for this team/season.")
    else:
        assert "team_name" in data, "Response should have a 'team_name' field"
        assert data["team_name"].lower() == SAMPLE_TEAM.lower(), f"Team name should be {SAMPLE_TEAM}"
        assert "team_id" in data, "Response should have a 'team_id' field"
        assert "players_season_totals" in data, "Response should have 'players_season_totals'"
        assert "team_overall" in data, "Response should have 'team_overall'"
        print(f"Team Name: {data.get('team_name')}, Team ID: {data.get('team_id')}")
        print(f"Players Season Totals entries: {len(data['players_season_totals'])}")
        if data['players_season_totals']:
            print("Sample player data:", data['players_season_totals'][0])
        print(f"Team Overall data: {data['team_overall']}")
    print("=== Basic test completed ===")
    return data

def test_fetch_team_player_dashboard_dataframe():
    """Test fetching team player dashboard with DataFrame output."""
    print(f"\n=== Testing fetch_team_player_dashboard_logic (DataFrame) for {SAMPLE_TEAM} ===")
    result = fetch_team_player_dashboard_logic(
        SAMPLE_TEAM,
        SAMPLE_SEASON,
        return_dataframe=True
    )
    assert isinstance(result, tuple), "Result should be a tuple"
    assert len(result) == 2, "Result tuple should have 2 elements"
    json_response, dataframes = result
    assert isinstance(json_response, str), "First element should be JSON string"
    assert isinstance(dataframes, dict), "Second element should be dict of DataFrames"
    assert "players_season_totals" in dataframes
    assert "team_overall" in dataframes
    print(f"DataFrames returned: {list(dataframes.keys())}")
    if not dataframes["players_season_totals"].empty:
        print(f"Players Season Totals DF shape: {dataframes['players_season_totals'].shape}")
        print(dataframes["players_season_totals"].head(2))
    if not dataframes["team_overall"].empty:
        print(f"Team Overall DF shape: {dataframes['team_overall'].shape}")
        print(dataframes["team_overall"].head())
    print("=== DataFrame test completed ===")
    return json_response, dataframes

def test_fetch_team_player_dashboard_advanced_params():
    """Test with advanced measure type and per mode."""
    print(f"\n=== Testing fetch_team_player_dashboard_logic (Advanced Params) for {SAMPLE_TEAM} ===")
    json_response = fetch_team_player_dashboard_logic(
        SAMPLE_TEAM,
        SAMPLE_SEASON,
        per_mode=PerModeDetailed.per_game,
        measure_type=MeasureTypeDetailedDefense.advanced
    )
    data = json.loads(json_response)
    assert isinstance(data, dict)
    if "error" not in data:
        assert data["parameters"]["per_mode"] == PerModeDetailed.per_game
        assert data["parameters"]["measure_type"] == MeasureTypeDetailedDefense.advanced
        print(f"PerMode: {data['parameters']['per_mode']}, MeasureType: {data['parameters']['measure_type']}")
        if data['players_season_totals']:
            print("Sample advanced player data:", data['players_season_totals'][0])
    else:
        print(f"API Error: {data['error']}")
    print("=== Advanced params test completed ===")

def test_invalid_season_format():
    print("\n=== Testing invalid season format ===")
    json_response = fetch_team_player_dashboard_logic(SAMPLE_TEAM, "20XX-YY")
    data = json.loads(json_response)
    assert "error" in data and "season format" in data["error"].lower()
    print(f"Error: {data['error']}")

def test_invalid_date_format():
    print("\n=== Testing invalid date_from format ===")
    json_response = fetch_team_player_dashboard_logic(SAMPLE_TEAM, SAMPLE_SEASON, date_from_nullable="2022/01/01")
    data = json.loads(json_response)
    assert "error" in data and "date format" in data["error"].lower()
    print(f"Error: {data['error']}")

def test_invalid_enum_params():
    print("\n=== Testing invalid enum parameters (season_type, per_mode, measure_type, league_id) ===")
    invalid_params = [
        ("season_type", "InvalidSeasonType"),
        ("per_mode", "InvalidPerMode"),
        ("measure_type", "InvalidMeasure"),
        ("league_id_nullable", "InvalidLeague")
    ]
    for param, value in invalid_params:
        print(f"Testing invalid {param}: {value}")
        kwargs = {param: value}
        json_response = fetch_team_player_dashboard_logic(SAMPLE_TEAM, SAMPLE_SEASON, **kwargs)
        data = json.loads(json_response)
        assert "error" in data, f"Should error for invalid {param}"
        print(f"Error for {param}: {data['error']}")

def test_invalid_choice_params():
    print("\n=== Testing invalid choice parameters (pace_adjust, plus_minus, rank, outcome, location, game_segment) ===")
    invalid_choices = [
        ("pace_adjust", "X"),
        ("plus_minus", "X"),
        ("rank", "X"),
        ("outcome_nullable", "X"),
        ("location_nullable", "Somewhere"),
        ("game_segment_nullable", "HalfTime")
    ]
    for param, value in invalid_choices:
        print(f"Testing invalid {param}: {value}")
        kwargs = {param: value}
        json_response = fetch_team_player_dashboard_logic(SAMPLE_TEAM, SAMPLE_SEASON, **kwargs)
        data = json.loads(json_response)
        assert "error" in data, f"Should error for invalid {param}"
        print(f"Error for {param}: {data['error']}")

def test_invalid_team_identifier():
    print("\n=== Testing invalid team_identifier ===")
    json_response = fetch_team_player_dashboard_logic("Not A Real Team", SAMPLE_SEASON)
    data = json.loads(json_response)
    assert "error" in data and ("not found" in data["error"].lower() or "could not find" in data["error"].lower())
    print(f"Error: {data['error']}")

def test_all_optional_parameters():
    print("\n=== Testing all optional parameters set ===")
    json_response = fetch_team_player_dashboard_logic(
        SAMPLE_TEAM, SAMPLE_SEASON,
        last_n_games=5, month=1, opponent_team_id=1610612738, # BOS
        pace_adjust='Y', period=1, plus_minus='Y', rank='Y',
        vs_division_nullable='Pacific', vs_conference_nullable='West', 
        shot_clock_range_nullable='15-7 Average', season_segment_nullable='Post All-Star',
        po_round_nullable=1, outcome_nullable='W', location_nullable='Home',
        league_id_nullable=LeagueID.nba, game_segment_nullable='First Half',
        date_from_nullable="2023-01-01", date_to_nullable="2023-01-31"
    )
    data = json.loads(json_response)
    assert isinstance(data, dict), "Should return a dictionary"
    if "error" in data:
        print(f"API Error with all optionals: {data['error']}")
    else:
        assert data["parameters"]["last_n_games"] == 5
        print("Successfully called with all optional parameters.")
        print("Sample parameters:", data.get("parameters"))

def test_empty_results_scenario():
    # Use a very old season or unlikely combination to get empty results
    print("\n=== Testing scenario likely to yield empty results ===")
    json_response = fetch_team_player_dashboard_logic(SAMPLE_TEAM, "1950-51", measure_type=MeasureTypeDetailedDefense.base)
    data = json.loads(json_response)
    assert isinstance(data, dict), "Response should be a dictionary"
    if "error" in data:
        print(f"API Error (expected for old season): {data['error']}")
    else:
        assert "players_season_totals" in data
        assert "team_overall" in data
        assert len(data["players_season_totals"]) == 0, "Expected empty players_season_totals for old season"
        # TeamOverall might still have a row with zeros or team info, or be an empty dict if fully empty
        assert not data["team_overall"] or all(value == 0 or isinstance(value, str) for key, value in data["team_overall"].items() if key not in ['GROUP_SET', 'TEAM_ID', 'TEAM_NAME', 'GROUP_VALUE'] ), "Expected empty or zeroed team_overall data"
        print("Empty results scenario test completed as expected.")

def test_api_error_simulation(monkeypatch):
    print("\n=== Testing API error simulation ===")
    
    class MockTeamPlayerDashboard:
        def __init__(self, *args, **kwargs):
            raise Exception("Simulated NBA API internal server error")
        def players_season_totals(self):
            return self
        def team_overall(self):
            return self
        def get_data_frame(self):
            # This won't be reached if constructor fails, but good practice
            return pd.DataFrame() 

    # Temporarily replace the real endpoint with our mock
    monkeypatch.setattr("backend.api_tools.team_player_dashboard.teamplayerdashboard.TeamPlayerDashboard", MockTeamPlayerDashboard)
    
    json_response = fetch_team_player_dashboard_logic(SAMPLE_TEAM, SAMPLE_SEASON)
    data = json.loads(json_response)
    
    assert "error" in data, "Error message should be present in response"
    assert "Simulated NBA API internal server error" in data["error"], "Error message should contain the simulated error"
    print(f"Simulated API error handled: {data['error']}")
    print("=== API error simulation test completed ===")

def run_all_tests():
    print(f"=== Running TeamPlayerDashboard smoke tests at {datetime.now().isoformat()} ===\n")
    # Pytest runs tests individually, no need for explicit calls here if run with pytest
    # For standalone script execution, one would call them:
    # test_fetch_team_player_dashboard_basic()
    # test_fetch_team_player_dashboard_dataframe()
    # ... and so on
    pass

if __name__ == "__main__":
    # This part is for running the script directly, e.g., python test_team_player_dashboard.py
    # For pytest, it will discover and run tests automatically.
    print("Running tests directly...")
    test_fetch_team_player_dashboard_basic()
    test_fetch_team_player_dashboard_dataframe()
    test_fetch_team_player_dashboard_advanced_params()
    test_invalid_season_format()
    test_invalid_date_format()
    test_invalid_enum_params()
    test_invalid_choice_params()
    test_invalid_team_identifier()
    test_all_optional_parameters()
    test_empty_results_scenario()
    # test_api_error_simulation() # Requires pytest for monkeypatch
    print("\nDirect execution of tests finished. For full testing including error simulation, run with pytest.") 
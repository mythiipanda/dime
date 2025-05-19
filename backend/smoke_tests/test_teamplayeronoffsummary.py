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

from backend.api_tools.teamplayeronoffsummary import fetch_teamplayeronoffsummary_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailedDefense, LeagueID

SAMPLE_TEAM = "Los Angeles Lakers"
SAMPLE_SEASON = "2022-23"


def test_fetch_teamplayeronoffsummary_basic():
    """Test fetching team player on/off summary with default parameters."""
    print("\n=== Testing fetch_teamplayeronoffsummary_logic (basic) ===")
    json_response = fetch_teamplayeronoffsummary_logic(
        SAMPLE_TEAM,
        SAMPLE_SEASON,
        SeasonTypeAllStar.regular,
        PerModeDetailed.totals,
        MeasureTypeDetailedDefense.base
    )
    data = json.loads(json_response)
    assert isinstance(data, dict), "Response should be a dictionary"
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        print("Continuing with other tests...")
    else:
        assert "team_name" in data, "Response should have a 'team_name' field"
        assert "team_id" in data, "Response should have a 'team_id' field"
        print(f"Team Name: {data.get('team_name')}")
        print(f"Team ID: {data.get('team_id')}")
        for key in [
            "overall_team_player_on_off_summary",
            "players_off_court_team_player_on_off_summary",
            "players_on_court_team_player_on_off_summary"
        ]:
            assert key in data, f"Response should have '{key}'"
            print(f"{key} entries: {len(data[key])}")
            if data[key]:
                print("Sample data from first entry:")
                first_entry = data[key][0]
                for k, v in list(first_entry.items())[:5]:
                    print(f"  {k}: {v}")
    print("\n=== Basic team player on/off summary test completed ===")
    return data

def test_fetch_teamplayeronoffsummary_dataframe():
    """Test fetching team player on/off summary with DataFrame output."""
    print("\n=== Testing fetch_teamplayeronoffsummary_logic with DataFrame output ===")
    result = fetch_teamplayeronoffsummary_logic(
        SAMPLE_TEAM,
        SAMPLE_SEASON,
        SeasonTypeAllStar.regular,
        PerModeDetailed.totals,
        MeasureTypeDetailedDefense.base,
        return_dataframe=True
    )
    assert isinstance(result, tuple), "Result should be a tuple when return_dataframe=True"
    assert len(result) == 2, "Result tuple should have 2 elements"
    json_response, dataframes = result
    assert isinstance(json_response, str), "First element should be a JSON string"
    assert isinstance(dataframes, dict), "Second element should be a dictionary of DataFrames"
    data = json.loads(json_response)
    print(f"\nDataFrames returned: {list(dataframes.keys())}")
    for key, df in dataframes.items():
        if not df.empty:
            print(f"DataFrame '{key}' shape: {df.shape}")
            print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nSample of DataFrame '{key}' (first 3 rows):")
            print(df.head(3))
            break
    print("\n=== DataFrame team player on/off summary test completed ===")
    return json_response, dataframes

def test_fetch_teamplayeronoffsummary_advanced():
    """Test fetching team player on/off summary with advanced measure type."""
    print("\n=== Testing fetch_teamplayeronoffsummary_logic with advanced measure type ===")
    json_response = fetch_teamplayeronoffsummary_logic(
        SAMPLE_TEAM,
        SAMPLE_SEASON,
        SeasonTypeAllStar.regular,
        PerModeDetailed.totals,
        MeasureTypeDetailedDefense.advanced
    )
    data = json.loads(json_response)
    assert isinstance(data, dict), "Response should be a dictionary"
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        print("Continuing with other tests...")
    else:
        assert data["parameters"]["measure_type"] == MeasureTypeDetailedDefense.advanced, "Measure type should be 'Advanced'"
        print(f"Team Name: {data.get('team_name')}")
        print(f"Measure Type: {data['parameters']['measure_type']}")
        overall = data["overall_team_player_on_off_summary"]
        if overall:
            print("\nSample advanced metrics from overall summary:")
            first_entry = overall[0]
            advanced_fields = ["TS_PCT", "EFG_PCT", "USG_PCT", "PACE", "PIE", "OFF_RATING", "DEF_RATING", "NET_RATING"]
            for field in advanced_fields:
                if field in first_entry:
                    print(f"  {field}: {first_entry[field]}")
    print("\n=== Advanced measure type test completed ===")
    return data

def test_invalid_season_format():
    print("\n=== Testing invalid season format ===")
    json_response = fetch_teamplayeronoffsummary_logic(
        SAMPLE_TEAM, "20XX-YY"  # Invalid format
    )
    data = json.loads(json_response)
    assert "error" in data, "Should return error for invalid season format"
    print(f"Error: {data['error']}")

def test_invalid_date_format():
    print("\n=== Testing invalid date_from format ===")
    json_response = fetch_teamplayeronoffsummary_logic(
        SAMPLE_TEAM, SAMPLE_SEASON, date_from="2022/01/01"
    )
    data = json.loads(json_response)
    assert "error" in data, "Should return error for invalid date_from format"
    print(f"Error: {data['error']}")

def test_invalid_season_type():
    print("\n=== Testing invalid season_type ===")
    json_response = fetch_teamplayeronoffsummary_logic(
        SAMPLE_TEAM, SAMPLE_SEASON, season_type="InvalidSeasonType"
    )
    data = json.loads(json_response)
    assert "error" in data, "Should return error for invalid season_type"
    print(f"Error: {data['error']}")

def test_invalid_per_mode():
    print("\n=== Testing invalid per_mode ===")
    json_response = fetch_teamplayeronoffsummary_logic(
        SAMPLE_TEAM, SAMPLE_SEASON, per_mode="InvalidPerMode"
    )
    data = json.loads(json_response)
    assert "error" in data, "Should return error for invalid per_mode"
    print(f"Error: {data['error']}")

def test_invalid_measure_type():
    print("\n=== Testing invalid measure_type ===")
    json_response = fetch_teamplayeronoffsummary_logic(
        SAMPLE_TEAM, SAMPLE_SEASON, measure_type="InvalidMeasureType"
    )
    data = json.loads(json_response)
    assert "error" in data, "Should return error for invalid measure_type"
    print(f"Error: {data['error']}")

def test_invalid_league_id():
    print("\n=== Testing invalid league_id ===")
    json_response = fetch_teamplayeronoffsummary_logic(
        SAMPLE_TEAM, SAMPLE_SEASON, league_id="InvalidLeague"
    )
    data = json.loads(json_response)
    assert "error" in data, "Should return error for invalid league_id"
    print(f"Error: {data['error']}")

def test_invalid_team_identifier():
    print("\n=== Testing invalid team_identifier ===")
    json_response = fetch_teamplayeronoffsummary_logic(
        "NotATeam", SAMPLE_SEASON
    )
    data = json.loads(json_response)
    assert "error" in data, "Should return error for invalid team_identifier"
    print(f"Error: {data['error']}")

def test_all_optional_parameters():
    print("\n=== Testing all optional parameters set ===")
    json_response = fetch_teamplayeronoffsummary_logic(
        SAMPLE_TEAM, SAMPLE_SEASON,
        last_n_games=5, month=2, opponent_team_id=1610612738, pace_adjust='Y', period=2,
        plus_minus='Y', rank='Y', vs_division='Pacific', vs_conference='West', season_segment='Pre All-Star',
        outcome='W', location='Home', league_id=LeagueID.nba, game_segment='First Half', date_from="2022-01-01", date_to="2022-02-01"
    )
    data = json.loads(json_response)
    assert isinstance(data, dict), "Should return a dictionary even with all optional params"
    print(f"Keys: {list(data.keys())}")
    print("Sample parameters:", data.get("parameters", {}))

def test_empty_results():
    print("\n=== Testing empty results (use a team/season with no data) ===")
    json_response = fetch_teamplayeronoffsummary_logic(
        SAMPLE_TEAM, "1990-91"  # Lakers did not exist in this form then
    )
    data = json.loads(json_response)
    assert isinstance(data, dict), "Should return a dictionary"
    for key in [
        "overall_team_player_on_off_summary",
        "players_off_court_team_player_on_off_summary",
        "players_on_court_team_player_on_off_summary"
    ]:
        assert key in data, f"Should have key {key}"
        print(f"{key} entries: {len(data[key])}")
    print("Empty results test completed.")

def test_api_error(monkeypatch=None):
    print("\n=== Testing API error handling (simulate error) ===")
    # Monkeypatch the endpoint to raise an Exception
    original = fetch_teamplayeronoffsummary_logic.__globals__["teamplayeronoffsummary"]
    class FakeEndpoint:
        class TeamPlayerOnOffSummary:
            def __init__(*a, **kw):
                raise Exception("Simulated API failure")
    fetch_teamplayeronoffsummary_logic.__globals__["teamplayeronoffsummary"] = FakeEndpoint
    try:
        json_response = fetch_teamplayeronoffsummary_logic(SAMPLE_TEAM, SAMPLE_SEASON)
        data = json.loads(json_response)
        assert "error" in data, "Should return error on simulated API failure"
        print(f"Error: {data['error']}")
    finally:
        fetch_teamplayeronoffsummary_logic.__globals__["teamplayeronoffsummary"] = original

def run_all_tests():
    print(f"=== Running teamplayeronoffsummary smoke tests at {datetime.now().isoformat()} ===\n")
    try:
        basic_data = test_fetch_teamplayeronoffsummary_basic()
        df_json, df_data = test_fetch_teamplayeronoffsummary_dataframe()
        advanced_data = test_fetch_teamplayeronoffsummary_advanced()
        test_invalid_season_format()
        test_invalid_date_format()
        test_invalid_season_type()
        test_invalid_per_mode()
        test_invalid_measure_type()
        test_invalid_league_id()
        test_invalid_team_identifier()
        test_all_optional_parameters()
        test_empty_results()
        test_api_error()
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
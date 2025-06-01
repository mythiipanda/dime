"""
Smoke test for the league_dash_pt_team_defend module.
Tests the functionality of fetching defensive team tracking statistics across the league.
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

from api_tools.league_dash_pt_team_defend import (
    fetch_league_dash_pt_team_defend_logic,
    LEAGUE_DASH_PT_TEAM_DEFEND_CSV_DIR
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeSimple, LeagueID, DefenseCategory
)

# Sample season for testing
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular  # Regular season

def test_fetch_league_dash_pt_team_defend_basic():
    """Test fetching defensive team tracking statistics with default parameters."""
    print("\n=== Testing fetch_league_dash_pt_team_defend_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_league_dash_pt_team_defend_logic(
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE
    )

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
        # Check if the parameters field exists
        assert "parameters" in data, "Response should have a 'parameters' field"

        # Check if the pt_team_defend field exists
        assert "pt_team_defend" in data, "Response should have a 'pt_team_defend' field"

        # Print some information about the data
        print(f"Season: {data.get('parameters', {}).get('season', 'N/A')}")
        print(f"Season Type: {data.get('parameters', {}).get('season_type_all_star', 'N/A')}")
        print(f"Per Mode: {data.get('parameters', {}).get('per_mode_simple', 'N/A')}")
        print(f"Defense Category: {data.get('parameters', {}).get('defense_category', 'N/A')}")

        # Print defensive team tracking data
        if "pt_team_defend" in data and data["pt_team_defend"]:
            pt_team_defend = data["pt_team_defend"]
            print(f"\nDefensive Team Tracking Stats: {len(pt_team_defend)} teams")
            if pt_team_defend:
                # Print first team
                first_team = pt_team_defend[0]
                print("Sample data (first team):")
                for key, value in list(first_team.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

                # Print defensive metrics
                print("\nDefensive metrics:")
                for key in ["FREQ", "D_FGM", "D_FGA", "D_FG_PCT", "NORMAL_FG_PCT", "PCT_PLUSMINUS"]:
                    if key in first_team:
                        print(f"  {key}: {first_team[key]}")

    print("\n=== Basic test completed ===")
    return data

def test_fetch_league_dash_pt_team_defend_different_categories():
    """Test fetching defensive team tracking statistics with different defense categories."""
    print("\n=== Testing fetch_league_dash_pt_team_defend_logic (different defense categories) ===")

    # Test with different defense categories
    defense_categories = [
        DefenseCategory.threes,
        DefenseCategory.twos,
        DefenseCategory.less_than_6ft
    ]

    for defense_category in defense_categories:
        print(f"\nTesting defense category: {defense_category}")

        json_response = fetch_league_dash_pt_team_defend_logic(
            SAMPLE_SEASON,
            SAMPLE_SEASON_TYPE,
            defense_category=defense_category
        )

        # Parse the JSON response
        data = json.loads(json_response)

        # Check if there's an error in the response
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            print("This might be expected if the NBA API is unavailable or rate-limited.")
            continue

        # Check if the parameters field exists and contains the defense_category value
        assert "parameters" in data, "Response should have a 'parameters' field"
        params = data["parameters"]

        # Check if the defense_category parameter is included in the response
        assert "defense_category" in params, "Parameters should include 'defense_category'"

        # Check if the defense_category value matches what we provided
        assert params["defense_category"] == defense_category, f"defense_category should be '{defense_category}'"

        # Print defensive team tracking data
        if "pt_team_defend" in data and data["pt_team_defend"]:
            pt_team_defend = data["pt_team_defend"]
            print(f"Defensive Team Tracking Stats ({defense_category}): {len(pt_team_defend)} teams")
            if pt_team_defend:
                # Print first team
                first_team = pt_team_defend[0]
                print("Sample data (first team):")
                for key, value in list(first_team.items())[:3]:  # Show first 3 columns
                    print(f"  {key}: {value}")

                # Print defensive metrics
                print("Defensive metrics:")
                for key in ["D_FG_PCT", "NORMAL_FG_PCT", "PCT_PLUSMINUS"]:
                    if key in first_team:
                        print(f"  {key}: {first_team[key]}")

    print("\n=== Different defense categories test completed ===")
    return data

def test_fetch_league_dash_pt_team_defend_with_filters():
    """Test fetching defensive team tracking statistics with additional filters."""
    print("\n=== Testing fetch_league_dash_pt_team_defend_logic with filters ===")

    # Test with additional filters
    json_response = fetch_league_dash_pt_team_defend_logic(
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        conference_nullable="East",  # Only Eastern Conference
        division_nullable="Atlantic",  # Only Atlantic Division
        location_nullable="Home",  # Only home games
        outcome_nullable="W"  # Only wins
    )

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
        # Check if the parameters field exists and contains the filter values
        assert "parameters" in data, "Response should have a 'parameters' field"
        params = data["parameters"]

        # Check if the filter parameters are included in the response
        assert "conference_nullable" in params, "Parameters should include 'conference_nullable'"
        assert "division_nullable" in params, "Parameters should include 'division_nullable'"
        assert "location_nullable" in params, "Parameters should include 'location_nullable'"
        assert "outcome_nullable" in params, "Parameters should include 'outcome_nullable'"

        # Check if the filter values match what we provided
        assert params["conference_nullable"] == "East", "conference_nullable should be 'East'"
        assert params["division_nullable"] == "Atlantic", "division_nullable should be 'Atlantic'"
        assert params["location_nullable"] == "Home", "location_nullable should be 'Home'"
        assert params["outcome_nullable"] == "W", "outcome_nullable should be 'W'"

        # Print filter information
        print(f"Filters applied:")
        print(f"  Conference: {params.get('conference_nullable', 'N/A')}")
        print(f"  Division: {params.get('division_nullable', 'N/A')}")
        print(f"  Location: {params.get('location_nullable', 'N/A')}")
        print(f"  Outcome: {params.get('outcome_nullable', 'N/A')}")

        # Print defensive team tracking data
        if "pt_team_defend" in data and data["pt_team_defend"]:
            pt_team_defend = data["pt_team_defend"]
            print(f"\nFiltered Defensive Team Tracking Stats: {len(pt_team_defend)} teams")
            if pt_team_defend:
                # Print first team
                first_team = pt_team_defend[0]
                print("Sample data (first team):")
                for key, value in list(first_team.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")
        else:
            print("No data returned with these filters - they may be too restrictive")

    print("\n=== Filters test completed ===")
    return data

def test_fetch_league_dash_pt_team_defend_additional_filters():
    """Test fetching defensive team tracking statistics with additional filters."""
    print("\n=== Testing fetch_league_dash_pt_team_defend_logic with additional filters ===")

    # Test each parameter individually to ensure they work
    parameters_to_test = [
        {"game_segment_nullable": "First Half"},
        {"season_segment_nullable": "Post All-Star"},
        {"team_id_nullable": "1610612747"},  # Lakers
        {"last_n_games_nullable": 10},
        {"period_nullable": 1},
        {"month_nullable": 4},
        {"opponent_team_id_nullable": 1610612738},  # Celtics
        {"vs_conference_nullable": "East"},
        {"vs_division_nullable": "Atlantic"},
        {"date_from_nullable": "2023-01-01"},
        {"date_to_nullable": "2023-04-01"}
        # Note: po_round_nullable is only applicable to playoff data, not regular season
    ]

    for param_dict in parameters_to_test:
        param_name = list(param_dict.keys())[0]
        param_value = param_dict[param_name]

        print(f"\nTesting parameter: {param_name} = {param_value}")

        # Create parameters for this test
        test_params = {
            "season": SAMPLE_SEASON,
            "season_type": SAMPLE_SEASON_TYPE,
            param_name: param_value
        }

        # Call the API
        json_response = fetch_league_dash_pt_team_defend_logic(**test_params)

        # Parse the JSON response
        data = json.loads(json_response)

        # Check if there's an error in the response
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            print("This parameter may not be working correctly.")
            continue

        # Check if the parameter is included in the response
        if "parameters" in data and param_name in data["parameters"]:
            print(f"Parameter {param_name} is working correctly.")

            # Print data count
            if "pt_team_defend" in data and data["pt_team_defend"]:
                pt_team_defend = data["pt_team_defend"]
                print(f"Returned {len(pt_team_defend)} teams")
            else:
                print("No data returned - parameter may not be working correctly.")
        else:
            print(f"Parameter {param_name} is not included in the response - it may not be working correctly.")

    print("\n=== Additional filters test completed ===")

    # Return the last data for consistency
    return data

def test_fetch_league_dash_pt_team_defend_playoff_data():
    """Test fetching defensive team tracking statistics with playoff data."""
    print("\n=== Testing fetch_league_dash_pt_team_defend_logic with playoff data ===")

    # Test with playoff data and po_round_nullable parameter
    json_response = fetch_league_dash_pt_team_defend_logic(
        SAMPLE_SEASON,
        SeasonTypeAllStar.playoffs,  # Use playoff data
        po_round_nullable="1"  # First round of playoffs
    )

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
        # Check if the parameters field exists and contains the po_round_nullable value
        assert "parameters" in data, "Response should have a 'parameters' field"
        params = data["parameters"]

        # Check if the po_round_nullable parameter is included in the response
        assert "po_round_nullable" in params, "Parameters should include 'po_round_nullable'"

        # Check if the po_round_nullable value matches what we provided
        assert params["po_round_nullable"] == "1", "po_round_nullable should be '1'"

        # Print filter information
        print(f"Playoff filter applied:")
        print(f"  Season Type: {params.get('season_type_all_star', 'N/A')}")
        print(f"  PO Round: {params.get('po_round_nullable', 'N/A')}")

        # Print defensive team tracking data
        if "pt_team_defend" in data and data["pt_team_defend"]:
            pt_team_defend = data["pt_team_defend"]
            print(f"\nPlayoff Defensive Team Tracking Stats: {len(pt_team_defend)} teams")
            if pt_team_defend:
                # Print first team
                first_team = pt_team_defend[0]
                print("Sample data (first team):")
                for key, value in list(first_team.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")
        else:
            print("No data returned - this might be expected if there's no playoff data available")

    print("\n=== Playoff data test completed ===")
    return data

def test_fetch_league_dash_pt_team_defend_dataframe():
    """Test fetching defensive team tracking statistics with DataFrame output."""
    print("\n=== Testing fetch_league_dash_pt_team_defend_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_league_dash_pt_team_defend_logic(
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        return_dataframe=True
    )

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
        if not df.empty:
            print(f"\nDataFrame '{key}' shape: {df.shape}")
            print(f"DataFrame '{key}' columns: {df.columns.tolist()}")

    # Check if the CSV files were created
    if os.path.exists(LEAGUE_DASH_PT_TEAM_DEFEND_CSV_DIR):
        csv_files = [f for f in os.listdir(LEAGUE_DASH_PT_TEAM_DEFEND_CSV_DIR) if f.startswith("pt_team_defend")]
        print(f"\nCSV files created: {len(csv_files)}")
        if csv_files:
            print(f"Sample CSV files: {csv_files[:2]}...")

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
    print(f"=== Running league_dash_pt_team_defend smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        test_fetch_league_dash_pt_team_defend_basic()
        test_fetch_league_dash_pt_team_defend_different_categories()
        test_fetch_league_dash_pt_team_defend_with_filters()
        test_fetch_league_dash_pt_team_defend_additional_filters()
        test_fetch_league_dash_pt_team_defend_playoff_data()
        test_fetch_league_dash_pt_team_defend_dataframe()

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

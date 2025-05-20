"""
Smoke test for the team_passing_tracking module.
Tests the functionality of fetching team passing tracking statistics.
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

from backend.api_tools.team_passing_tracking import (
    fetch_team_passing_stats_logic,
    TEAM_PASSING_CSV_DIR
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeSimple
)

# Sample team name and season for testing
SAMPLE_TEAM_NAME = "Boston Celtics"  # A team known for good passing
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular  # Regular season

def test_fetch_team_passing_stats_basic():
    """Test fetching team passing stats with default parameters."""
    print("\n=== Testing fetch_team_passing_stats_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_team_passing_stats_logic(
        SAMPLE_TEAM_NAME,
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
        # Check if the team_name field exists and matches the input
        assert "team_name" in data, "Response should have a 'team_name' field"
        assert data["team_name"].lower() == SAMPLE_TEAM_NAME.lower(), f"team_name should be {SAMPLE_TEAM_NAME}"

        # Check if the season field exists and matches the input
        assert "season" in data, "Response should have a 'season' field"
        assert data["season"] == SAMPLE_SEASON, f"season should be {SAMPLE_SEASON}"

        # Check if the season_type field exists and matches the input
        assert "season_type" in data, "Response should have a 'season_type' field"
        assert data["season_type"] == SAMPLE_SEASON_TYPE, f"season_type should be {SAMPLE_SEASON_TYPE}"

        # Check if the passing data fields exist
        assert "passes_made" in data, "Response should have a 'passes_made' field"
        assert "passes_received" in data, "Response should have a 'passes_received' field"

        # Print some information about the data
        print(f"Team: {data.get('team_name', 'N/A')} (ID: {data.get('team_id', 'N/A')})")
        print(f"Season: {data.get('season', 'N/A')}")
        print(f"Season Type: {data.get('season_type', 'N/A')}")
        print(f"Per Mode: {data.get('parameters', {}).get('per_mode', 'N/A')}")

        # Print passes made stats
        if "passes_made" in data and data["passes_made"]:
            passes_made = data["passes_made"]
            print(f"\nPasses Made: {len(passes_made)} entries")
            if passes_made:
                # Print first few entries
                for i, entry in enumerate(passes_made[:3]):
                    print(f"\nPass Made Entry {i+1}:")
                    for key, value in list(entry.items())[:5]:  # Show first 5 columns
                        print(f"  {key}: {value}")

        # Print passes received stats
        if "passes_received" in data and data["passes_received"]:
            passes_received = data["passes_received"]
            print(f"\nPasses Received: {len(passes_received)} entries")
            if passes_received:
                # Print first few entries
                for i, entry in enumerate(passes_received[:3]):
                    print(f"\nPass Received Entry {i+1}:")
                    for key, value in list(entry.items())[:5]:  # Show first 5 columns
                        print(f"  {key}: {value}")

    print("\n=== Basic test completed ===")
    return data

def test_fetch_team_passing_stats_totals():
    """Test fetching team passing stats with Totals per mode."""
    print("\n=== Testing fetch_team_passing_stats_logic (Totals) ===")

    # Test with Totals per mode
    json_response = fetch_team_passing_stats_logic(
        SAMPLE_TEAM_NAME,
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        per_mode=PerModeSimple.totals
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
        # Check if the per_mode parameter matches the input
        assert data.get("parameters", {}).get("per_mode") == PerModeSimple.totals, \
            f"per_mode should be {PerModeSimple.totals}"

        # Print some information about the data
        print(f"Team: {data.get('team_name', 'N/A')} (ID: {data.get('team_id', 'N/A')})")
        print(f"Per Mode: {data.get('parameters', {}).get('per_mode', 'N/A')}")

        # Print passes made stats
        if "passes_made" in data and data["passes_made"]:
            passes_made = data["passes_made"]
            print(f"\nPasses Made (Totals): {len(passes_made)} entries")
            if passes_made:
                # Print first entry
                first_entry = passes_made[0]
                print("Sample data (first entry):")
                for key, value in list(first_entry.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

    print("\n=== Totals test completed ===")
    return data

def test_fetch_team_passing_stats_with_filters():
    """Test fetching team passing stats with additional filters."""
    print("\n=== Testing fetch_team_passing_stats_logic with filters ===")

    # Test with additional filters
    json_response = fetch_team_passing_stats_logic(
        SAMPLE_TEAM_NAME,
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        per_mode=PerModeSimple.per_game,
        last_n_games=10,  # Last 10 games
        location_nullable="Home"  # Only home games
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
        assert "last_n_games" in params, "Parameters should include 'last_n_games'"
        assert "location" in params, "Parameters should include 'location'"

        # Check if the filter values match what we provided
        assert params["last_n_games"] == 10, "last_n_games should be 10"
        assert params["location"] == "Home", "location should be 'Home'"

        # Print filter information
        print(f"Team: {data.get('team_name', 'N/A')} (ID: {data.get('team_id', 'N/A')})")
        print(f"Filters applied:")
        print(f"  Last N Games: {params.get('last_n_games', 'N/A')}")
        print(f"  Location: {params.get('location', 'N/A')}")

        # Print passes made and received counts
        print(f"\nPasses Made Count: {len(data.get('passes_made', []))}")
        print(f"Passes Received Count: {len(data.get('passes_received', []))}")

    print("\n=== Filters test completed ===")
    return data

def test_fetch_team_passing_stats_dataframe():
    """Test fetching team passing stats with DataFrame output."""
    print("\n=== Testing fetch_team_passing_stats_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_team_passing_stats_logic(
        SAMPLE_TEAM_NAME,
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
            print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns

    # Check if the CSV files were created
    if os.path.exists(TEAM_PASSING_CSV_DIR):
        # Parse the JSON response to get the team name
        data = json.loads(json_response)
        team_name = data.get("team_name", SAMPLE_TEAM_NAME)
        clean_team_name = team_name.lower().replace(" ", "_").replace(".", "")

        csv_files = [f for f in os.listdir(TEAM_PASSING_CSV_DIR) if f.startswith(clean_team_name)]
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
    print(f"=== Running team_passing_tracking smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        basic_data = test_fetch_team_passing_stats_basic()
        totals_data = test_fetch_team_passing_stats_totals()
        filters_data = test_fetch_team_passing_stats_with_filters()
        json_response, dataframes = test_fetch_team_passing_stats_dataframe()

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

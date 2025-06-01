"""
Smoke test for the league_leaders_data module.
Tests the functionality of fetching league leaders data.
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

from api_tools.league_leaders_data import (
    fetch_league_leaders_logic,
    LEAGUE_LEADERS_CSV_DIR
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerMode48, LeagueID, Scope, StatCategoryAbbreviation
)

# Sample season and stat category for testing
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_STAT_CATEGORY = StatCategoryAbbreviation.pts  # Points
SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular  # Regular season
SAMPLE_PER_MODE = PerMode48.per_game  # Per game
SAMPLE_LEAGUE_ID = LeagueID.nba  # NBA
SAMPLE_SCOPE = Scope.s  # Season
SAMPLE_TOP_N = 10  # Top 10 leaders

def test_fetch_league_leaders_basic():
    """Test fetching league leaders with default parameters."""
    print("\n=== Testing fetch_league_leaders_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_league_leaders_logic(
        SAMPLE_SEASON,
        SAMPLE_STAT_CATEGORY,
        SAMPLE_SEASON_TYPE,
        SAMPLE_PER_MODE,
        SAMPLE_LEAGUE_ID,
        SAMPLE_SCOPE,
        SAMPLE_TOP_N
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
        # Check if the leaders field exists
        assert "leaders" in data, "Response should have a 'leaders' field"

        # Check if the leaders is a list
        assert isinstance(data["leaders"], list), "leaders should be a list"

        # Print some information about the data
        print(f"Number of leaders: {len(data.get('leaders', []))}")

        # Print sample leader data
        if data.get("leaders"):
            sample_leader = data["leaders"][0]
            print("\nSample leader data:")
            for key, value in list(sample_leader.items())[:10]:  # Show first 10 fields
                print(f"  {key}: {value}")

    print("\n=== Basic test completed ===")
    return data

def test_fetch_league_leaders_rebounds():
    """Test fetching league leaders for rebounds."""
    print("\n=== Testing fetch_league_leaders_logic (rebounds) ===")

    # Test with rebounds
    json_response = fetch_league_leaders_logic(
        SAMPLE_SEASON,
        StatCategoryAbbreviation.reb,
        SAMPLE_SEASON_TYPE,
        SAMPLE_PER_MODE,
        SAMPLE_LEAGUE_ID,
        SAMPLE_SCOPE,
        SAMPLE_TOP_N
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
        # Check if the leaders field exists
        assert "leaders" in data, "Response should have a 'leaders' field"

        # Print some information about the data
        print(f"Number of leaders: {len(data.get('leaders', []))}")

        # Print sample leader data
        if data.get("leaders"):
            sample_leader = data["leaders"][0]
            print("\nSample leader data:")
            for key, value in list(sample_leader.items())[:10]:  # Show first 10 fields
                print(f"  {key}: {value}")

    print("\n=== Rebounds test completed ===")
    return data

def test_fetch_league_leaders_dataframe():
    """Test fetching league leaders with DataFrame output."""
    print("\n=== Testing fetch_league_leaders_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_league_leaders_logic(
        SAMPLE_SEASON,
        SAMPLE_STAT_CATEGORY,
        SAMPLE_SEASON_TYPE,
        SAMPLE_PER_MODE,
        SAMPLE_LEAGUE_ID,
        SAMPLE_SCOPE,
        SAMPLE_TOP_N,
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
    if os.path.exists(LEAGUE_LEADERS_CSV_DIR):
        csv_files = [f for f in os.listdir(LEAGUE_LEADERS_CSV_DIR) if f.startswith(f"leaders_{SAMPLE_SEASON}")]
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
    print(f"=== Running league_leaders smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        basic_data = test_fetch_league_leaders_basic()
        rebounds_data = test_fetch_league_leaders_rebounds()
        json_response, dataframes = test_fetch_league_leaders_dataframe()

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

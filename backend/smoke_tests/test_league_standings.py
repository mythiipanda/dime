"""
Smoke test for the league_standings module.
Tests the functionality of fetching league standings.
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

from api_tools.league_standings import (
    fetch_league_standings_logic,
    LEAGUE_STANDINGS_CSV_DIR
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, LeagueID
)

# Sample season for testing
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular  # Regular season
SAMPLE_LEAGUE_ID = LeagueID.nba  # NBA

def test_fetch_league_standings_basic():
    """Test fetching league standings with default parameters."""
    print("\n=== Testing fetch_league_standings_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_league_standings_logic(
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        SAMPLE_LEAGUE_ID
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
        # Check if the standings field exists
        assert "standings" in data, "Response should have a 'standings' field"

        # Check if the league_id_processed field exists
        assert "league_id_processed" in data, "Response should have a 'league_id_processed' field"

        # Check if the league_id_processed matches the input
        assert data["league_id_processed"] == SAMPLE_LEAGUE_ID, f"league_id_processed should be {SAMPLE_LEAGUE_ID}"

        # Check if the standings is a list
        assert isinstance(data["standings"], list), "standings should be a list"

        # Print some information about the data
        print(f"League ID: {data.get('league_id_processed', 'N/A')}")
        print(f"Number of teams in standings: {len(data.get('standings', []))}")

        # Print sample team data
        if data.get("standings"):
            sample_team = data["standings"][0]
            print("\nSample team data:")
            for key, value in list(sample_team.items())[:10]:  # Show first 10 fields
                print(f"  {key}: {value}")

    print("\n=== Basic test completed ===")
    return data

def test_fetch_league_standings_preseason():
    """Test fetching league standings for preseason."""
    print("\n=== Testing fetch_league_standings_logic (preseason) ===")

    # Test with preseason
    json_response = fetch_league_standings_logic(
        SAMPLE_SEASON,
        SeasonTypeAllStar.preseason,
        SAMPLE_LEAGUE_ID
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
        # Check if the standings field exists
        assert "standings" in data, "Response should have a 'standings' field"

        # Print some information about the data
        print(f"League ID: {data.get('league_id_processed', 'N/A')}")
        print(f"Number of teams in standings: {len(data.get('standings', []))}")

    print("\n=== Preseason test completed ===")
    return data

def test_fetch_league_standings_dataframe():
    """Test fetching league standings with DataFrame output."""
    print("\n=== Testing fetch_league_standings_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_league_standings_logic(
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        SAMPLE_LEAGUE_ID,
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
    if os.path.exists(LEAGUE_STANDINGS_CSV_DIR):
        csv_files = [f for f in os.listdir(LEAGUE_STANDINGS_CSV_DIR) if f.startswith(f"standings_{SAMPLE_SEASON}")]
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
    print(f"=== Running league_standings smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        basic_data = test_fetch_league_standings_basic()
        preseason_data = test_fetch_league_standings_preseason()
        json_response, dataframes = test_fetch_league_standings_dataframe()

        print("\n=== All tests completed successfully ===")
        return True
    except Exception as e:
        print(f"\n!!! Test failed with error: {str(e)} !!!")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)

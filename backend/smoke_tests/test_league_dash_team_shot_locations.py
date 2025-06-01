"""
Smoke test for the league_dash_team_shot_locations module.
Tests the functionality of fetching team shot location statistics across the league.
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

from api_tools.league_dash_team_shot_locations import (
    fetch_league_team_shot_locations_logic,
    LEAGUE_DASH_TEAM_SHOT_LOCATIONS_CSV_DIR
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, MeasureTypeSimple, DistanceRange
)

# Sample season for testing
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular  # Regular season

def test_fetch_league_team_shot_locations_basic():
    """Test fetching team shot location statistics with default parameters."""
    print("\n=== Testing fetch_league_team_shot_locations_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_league_team_shot_locations_logic(
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
        
        # Check if the shot_locations field exists
        assert "shot_locations" in data, "Response should have a 'shot_locations' field"
        
        # Print some information about the data
        print(f"Season: {data.get('parameters', {}).get('season', 'N/A')}")
        print(f"Season Type: {data.get('parameters', {}).get('season_type_all_star', 'N/A')}")
        print(f"Distance Range: {data.get('parameters', {}).get('distance_range', 'N/A')}")
        
        # Print shot locations data
        if "shot_locations" in data and data["shot_locations"]:
            shot_locations = data["shot_locations"]
            print(f"\nShot Locations: {len(shot_locations)} teams")
            if shot_locations:
                # Print first team
                first_team = shot_locations[0]
                print("Sample data (first team):")
                for key, value in list(first_team.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

    print("\n=== Basic test completed ===")
    return data

def test_fetch_league_team_shot_locations_distance_range():
    """Test fetching team shot location statistics with different distance ranges."""
    print("\n=== Testing fetch_league_team_shot_locations_logic (distance ranges) ===")

    # Test with 5ft Range distance range
    json_response = fetch_league_team_shot_locations_logic(
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        distance_range=DistanceRange.range_5ft
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
        # Check if the distance_range parameter matches the input
        assert data.get("parameters", {}).get("distance_range") == DistanceRange.range_5ft, \
            f"distance_range should be {DistanceRange.range_5ft}"
        
        # Print some information about the data
        print(f"Distance Range: {data.get('parameters', {}).get('distance_range', 'N/A')}")
        
        # Print shot locations data
        if "shot_locations" in data and data["shot_locations"]:
            shot_locations = data["shot_locations"]
            print(f"\nShot Locations (5ft Range): {len(shot_locations)} teams")
            if shot_locations:
                # Print first team
                first_team = shot_locations[0]
                print("Sample data (first team):")
                for key, value in list(first_team.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

    print("\n=== Distance range test completed ===")
    return data

def test_fetch_league_team_shot_locations_with_filters():
    """Test fetching team shot location statistics with additional filters."""
    print("\n=== Testing fetch_league_team_shot_locations_logic with filters ===")

    # Test with additional filters
    json_response = fetch_league_team_shot_locations_logic(
        SAMPLE_SEASON,
        SAMPLE_SEASON_TYPE,
        per_mode=PerModeDetailed.per_game,
        measure_type=MeasureTypeSimple.base,
        distance_range=DistanceRange.by_zone,
        conference_nullable="East"  # Only Eastern Conference teams
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
        
        # Check if the filter values match what we provided
        assert params["conference_nullable"] == "East", "conference_nullable should be 'East'"
        
        # Print filter information
        print(f"Filters applied:")
        print(f"  Conference: {params.get('conference_nullable', 'N/A')}")
        
        # Print shot locations data
        if "shot_locations" in data and data["shot_locations"]:
            shot_locations = data["shot_locations"]
            print(f"\nFiltered Shot Locations: {len(shot_locations)} teams")
            if shot_locations:
                # Print first team
                first_team = shot_locations[0]
                print("Sample data (first team):")
                for key, value in list(first_team.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

    print("\n=== Filters test completed ===")
    return data

def test_fetch_league_team_shot_locations_dataframe():
    """Test fetching team shot location statistics with DataFrame output."""
    print("\n=== Testing fetch_league_team_shot_locations_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_league_team_shot_locations_logic(
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
    if os.path.exists(LEAGUE_DASH_TEAM_SHOT_LOCATIONS_CSV_DIR):
        csv_files = [f for f in os.listdir(LEAGUE_DASH_TEAM_SHOT_LOCATIONS_CSV_DIR) if f.startswith("team_shot_locations")]
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
    print(f"=== Running league_dash_team_shot_locations smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        basic_data = test_fetch_league_team_shot_locations_basic()
        distance_range_data = test_fetch_league_team_shot_locations_distance_range()
        filters_data = test_fetch_league_team_shot_locations_with_filters()
        json_response, dataframes = test_fetch_league_team_shot_locations_dataframe()

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

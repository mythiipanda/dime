"""
Smoke test for the team_passing_analytics module.
Tests the functionality of fetching team passing statistics with DataFrame output.
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

from api_tools.team_passing_analytics import fetch_team_passing_stats_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

def test_fetch_team_passing_stats_basic():
    """Test fetching team passing stats with default parameters."""
    print("\n=== Testing fetch_team_passing_stats_logic (basic) ===")

    # Test with a well-known team
    team_identifier = "Boston Celtics"
    season = "2022-23"  # Use a completed season for testing

    # Test with default parameters (JSON output)
    json_response = fetch_team_passing_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=SeasonTypeAllStar.regular,
        per_mode=PerModeSimple.per_game
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
        # Check if the key fields exist
        assert "team_id" in data, "Response should have a 'team_id' field"
        assert "team_name" in data, "Response should have a 'team_name' field"
        assert "passes_made" in data, "Response should have a 'passes_made' field"
        assert "passes_received" in data, "Response should have a 'passes_received' field"

        # Print some information about the data
        print(f"Team: {data['team_name']} (ID: {data['team_id']})")
        print(f"Season: {data['season']}")

        # Print details of the passes made
        if data['passes_made']:
            print(f"\nPasses Made Count: {len(data['passes_made'])}")
            print("\nFirst 3 passes made entries:")
            for i, entry in enumerate(data['passes_made'][:3]):
                print(f"\nEntry {i+1}:")
                print(f"  Player From: {entry.get('PASS_FROM', 'N/A')}")
                print(f"  Pass Type: {entry.get('PASS_TYPE', 'N/A')}")
                print(f"  Passes: {entry.get('PASS', 'N/A')}")
                print(f"  FGM: {entry.get('FGM', 'N/A')}")
                print(f"  FGA: {entry.get('FGA', 'N/A')}")
                print(f"  FG%: {entry.get('FG_PCT', 'N/A')}")

        # Print details of the passes received
        if data['passes_received']:
            print(f"\nPasses Received Count: {len(data['passes_received'])}")
            print("\nFirst 3 passes received entries:")
            for i, entry in enumerate(data['passes_received'][:3]):
                print(f"\nEntry {i+1}:")
                print(f"  Player To: {entry.get('PASS_TO', 'N/A')}")
                print(f"  Pass Type: {entry.get('PASS_TYPE', 'N/A')}")
                print(f"  Passes: {entry.get('PASS', 'N/A')}")
                print(f"  FGM: {entry.get('FGM', 'N/A')}")
                print(f"  FGA: {entry.get('FGA', 'N/A')}")
                print(f"  FG%: {entry.get('FG_PCT', 'N/A')}")

    print("\n=== Basic team passing stats test completed ===")
    return data

def test_fetch_team_passing_stats_dataframe():
    """Test fetching team passing stats with DataFrame output."""
    print("\n=== Testing fetch_team_passing_stats_logic with DataFrame output ===")

    # Test with a well-known team
    team_identifier = "Boston Celtics"
    season = "2022-23"  # Use a completed season for testing

    # Test with return_dataframe=True
    result = fetch_team_passing_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=SeasonTypeAllStar.regular,
        per_mode=PerModeSimple.per_game,
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

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if there's an error in the response
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        print("Continuing with other tests...")
    else:
        # Print DataFrame info
        print(f"\nDataFrames returned: {list(dataframes.keys())}")
        for key, df in dataframes.items():
            if not df.empty:
                print(f"\nDataFrame '{key}' shape: {df.shape}")
                print(f"DataFrame '{key}' columns: {df.columns.tolist()}")

        # Check if the dataframe_info field exists
        if "dataframe_info" in data:
            print("\nDataFrame info found in response:")
            print(f"Message: {data['dataframe_info'].get('message', 'N/A')}")

            # Check if the CSV paths are included
            for df_key, df_info in data["dataframe_info"].get("dataframes", {}).items():
                csv_path = df_info.get("csv_path")
                if csv_path:
                    full_path = os.path.join(backend_dir, csv_path)
                    if os.path.exists(full_path):
                        print(f"\nCSV file exists: {csv_path}")
                        csv_size = os.path.getsize(full_path)
                        print(f"CSV file size: {csv_size} bytes")
                    else:
                        print(f"\nCSV file does not exist: {csv_path}")

        # Display a sample of each DataFrame if not empty
        for key, df in dataframes.items():
            if not df.empty:
                print(f"\nSample of DataFrame '{key}' (first 3 rows):")
                print(df.head(3))

    print("\n=== DataFrame team passing stats test completed ===")
    return result

def test_fetch_team_passing_stats_with_filters():
    """Test fetching team passing stats with additional filters."""
    print("\n=== Testing fetch_team_passing_stats_logic with filters ===")

    # Test with a well-known team
    team_identifier = "Boston Celtics"
    season = "2022-23"  # Use a completed season for testing

    # Test with additional filters
    json_response = fetch_team_passing_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=SeasonTypeAllStar.regular,
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

def test_fetch_team_passing_stats_different_per_modes():
    """Test fetching team passing stats with different per_mode values."""
    print("\n=== Testing fetch_team_passing_stats_logic with different per_mode values ===")

    # Test with a well-known team
    team_identifier = "Boston Celtics"
    season = "2022-23"  # Use a completed season for testing

    # Test with different per_mode values
    per_modes = [PerModeSimple.per_game, PerModeSimple.totals]

    for per_mode in per_modes:
        print(f"\nTesting per_mode: {per_mode}")

        # Test with default parameters (JSON output)
        json_response = fetch_team_passing_stats_logic(
            team_identifier=team_identifier,
            season=season,
            season_type=SeasonTypeAllStar.regular,
            per_mode=per_mode
        )

        # Parse the JSON response
        data = json.loads(json_response)

        # Check if there's an error in the response
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            print("This might be expected if the NBA API is unavailable or rate-limited.")
        else:
            print(f"Team: {data['team_name']} (ID: {data['team_id']})")
            print(f"Per Mode: {data['parameters']['per_mode']}")

            # Print count of passes made and received
            print(f"Passes Made Count: {len(data['passes_made'])}")
            print(f"Passes Received Count: {len(data['passes_received'])}")

            # Print details of the first passes made entry
            if data['passes_made']:
                entry = data['passes_made'][0]
                print(f"\nFirst passes made entry:")
                print(f"  Player From: {entry.get('PASS_FROM', 'N/A')}")
                print(f"  Passes: {entry.get('PASS', 'N/A')}")
                print(f"  FGM: {entry.get('FGM', 'N/A')}")
                print(f"  FGA: {entry.get('FGA', 'N/A')}")

    print("\n=== Different per_mode values test completed ===")
    return True

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running team_passing_analytics smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        basic_data = test_fetch_team_passing_stats_basic()
        df_result = test_fetch_team_passing_stats_dataframe()
        filters_data = test_fetch_team_passing_stats_with_filters()
        different_per_modes = test_fetch_team_passing_stats_different_per_modes()

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

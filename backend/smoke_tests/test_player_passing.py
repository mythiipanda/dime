"""
Smoke test for the player_passing module.
Tests the functionality of fetching player passing statistics.
"""
import os

import json
import pandas as pd
from datetime import datetime



from api_tools.player_passing import (
    fetch_player_passing_stats_logic,
    PLAYER_PASSING_CSV_DIR
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeSimple
)

# Sample player name and season for testing
SAMPLE_PLAYER_NAME = "LeBron James"  # A player known for passing
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular  # Regular season

def test_fetch_player_passing_stats_basic():
    """Test fetching player passing stats with default parameters."""
    print("\n=== Testing fetch_player_passing_stats_logic (basic) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_player_passing_stats_logic(
        SAMPLE_PLAYER_NAME,
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
        # Check if the player_name field exists and matches the input
        assert "player_name" in data, "Response should have a 'player_name' field"
        assert data["player_name"] == SAMPLE_PLAYER_NAME, f"player_name should be {SAMPLE_PLAYER_NAME}"

        # Check if the parameters field exists
        assert "parameters" in data, "Response should have a 'parameters' field"

        # Check if the passes_made and passes_received fields exist
        assert "passes_made" in data, "Response should have a 'passes_made' field"
        assert "passes_received" in data, "Response should have a 'passes_received' field"

        # Print some information about the data
        print(f"Player: {data.get('player_name', 'N/A')} (ID: {data.get('player_id', 'N/A')})")
        print(f"Season: {data.get('parameters', {}).get('season', 'N/A')}")
        print(f"Season Type: {data.get('parameters', {}).get('season_type', 'N/A')}")
        print(f"Per Mode: {data.get('parameters', {}).get('per_mode', 'N/A')}")

        # Print passes made and received
        if "passes_made" in data:
            passes_made = data["passes_made"]
            print(f"\nPasses Made: {len(passes_made)} entries")
            if passes_made:
                # Print first few entries
                for i, entry in enumerate(passes_made[:3]):
                    print(f"\nPass Made Entry {i+1}:")
                    for key, value in list(entry.items())[:5]:  # Show first 5 columns
                        print(f"  {key}: {value}")

        if "passes_received" in data:
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

def test_fetch_player_passing_stats_totals():
    """Test fetching player passing stats with Totals per mode."""
    print("\n=== Testing fetch_player_passing_stats_logic (Totals) ===")

    # Test with Totals per mode
    json_response = fetch_player_passing_stats_logic(
        SAMPLE_PLAYER_NAME,
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
        print(f"Player: {data.get('player_name', 'N/A')} (ID: {data.get('player_id', 'N/A')})")
        print(f"Per Mode: {data.get('parameters', {}).get('per_mode', 'N/A')}")

        # Print passes made and received
        if "passes_made" in data:
            passes_made = data["passes_made"]
            print(f"\nPasses Made: {len(passes_made)} entries")
            if passes_made:
                # Print first entry
                first_entry = passes_made[0]
                print("Sample data (first entry):")
                for key, value in list(first_entry.items())[:5]:  # Show first 5 columns
                    print(f"  {key}: {value}")

    print("\n=== Totals test completed ===")
    return data

def test_fetch_player_passing_stats_dataframe():
    """Test fetching player passing stats with DataFrame output."""
    print("\n=== Testing fetch_player_passing_stats_logic with DataFrame output ===")

    # Test with return_dataframe=True
    result = fetch_player_passing_stats_logic(
        SAMPLE_PLAYER_NAME,
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
    if os.path.exists(PLAYER_PASSING_CSV_DIR):
        csv_files = [f for f in os.listdir(PLAYER_PASSING_CSV_DIR) if f.startswith(SAMPLE_PLAYER_NAME.lower().replace(" ", "_"))]
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
    print(f"=== Running player_passing smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        basic_data = test_fetch_player_passing_stats_basic()
        totals_data = test_fetch_player_passing_stats_totals()
        json_response, dataframes = test_fetch_player_passing_stats_dataframe()

        print("\n=== All tests completed successfully ===")
        return True
    except Exception as e:
        print(f"\n!!! Test failed with error: {str(e)} !!!")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    # Add the parent directory to the Python path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    success = run_all_tests()
    sys.exit(0 if success else 1)

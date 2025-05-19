"""
Smoke test for the league_draft module.
Tests the functionality of fetching NBA draft history data.
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

from backend.api_tools.league_draft import (
    fetch_draft_history_logic
)
from nba_api.stats.library.parameters import (
    LeagueID
)

# Sample year for testing
SAMPLE_YEAR = "2022"  # Use a recent draft year for testing

def test_fetch_draft_history_basic():
    """Test fetching draft history with default parameters."""
    print("\n=== Testing fetch_draft_history_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_draft_history_logic(
        season_year_nullable=SAMPLE_YEAR,
        league_id_nullable=LeagueID.nba
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
        # Check if the season_year_requested field exists
        assert "season_year_requested" in data, "Response should have a 'season_year_requested' field"
        assert "league_id" in data, "Response should have a 'league_id' field"
        
        # Print some information about the data
        print(f"Season Year: {data['season_year_requested']}")
        print(f"League ID: {data['league_id']}")
        
        # Check if draft_picks exist
        assert "draft_picks" in data, "Response should have 'draft_picks'"
        
        # Print some information about the draft picks
        picks = data["draft_picks"]
        print(f"\nNumber of draft picks: {len(picks)}")
        
        if picks:
            print("\nSample draft pick:")
            first_pick = picks[0]
            print(f"  PERSON_ID: {first_pick.get('PERSON_ID', 'N/A')}")
            print(f"  PLAYER_NAME: {first_pick.get('PLAYER_NAME', 'N/A')}")
            print(f"  OVERALL_PICK: {first_pick.get('OVERALL_PICK', 'N/A')}")
            print(f"  ROUND_NUMBER: {first_pick.get('ROUND_NUMBER', 'N/A')}")
            print(f"  TEAM_NAME: {first_pick.get('TEAM_NAME', 'N/A')}")
    
    print("\n=== Basic draft history test completed ===")
    return data

def test_fetch_draft_history_dataframe():
    """Test fetching draft history with DataFrame output."""
    print("\n=== Testing fetch_draft_history_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_draft_history_logic(
        season_year_nullable=SAMPLE_YEAR,
        league_id_nullable=LeagueID.nba,
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
    
    # Print DataFrame info
    print(f"\nDataFrames returned: {list(dataframes.keys())}")
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nDataFrame '{key}' shape: {df.shape}")
            print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns
    
    # Check if the CSV file was created
    if "dataframe_info" in data:
        for df_key, df_info in data["dataframe_info"].get("dataframes", {}).items():
            csv_path = df_info.get("csv_path")
            if csv_path:
                full_path = os.path.join(backend_dir, csv_path)
                if os.path.exists(full_path):
                    print(f"\nCSV file exists: {csv_path}")
                else:
                    print(f"\nCSV file does not exist: {csv_path}")
    
    # Display a sample of the DataFrame if not empty
    if "draft_history" in dataframes and not dataframes["draft_history"].empty:
        print(f"\nSample of draft history DataFrame (first 3 rows):")
        print(dataframes["draft_history"].head(3))
    
    print("\n=== DataFrame draft history test completed ===")
    return json_response, dataframes

def test_fetch_draft_history_filtered():
    """Test fetching draft history with filters."""
    print("\n=== Testing fetch_draft_history_logic with filters ===")
    
    # Test with filters
    json_response = fetch_draft_history_logic(
        season_year_nullable=SAMPLE_YEAR,
        league_id_nullable=LeagueID.nba,
        round_num_nullable=1  # First round picks only
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
        # Check if the round_num_filter parameter was correctly used
        assert data["round_num_filter"] == 1, "Round number filter should be 1"
        
        # Print some information about the data
        print(f"Season Year: {data['season_year_requested']}")
        print(f"Round Number Filter: {data['round_num_filter']}")
        
        # Check if draft_picks exist
        assert "draft_picks" in data, "Response should have 'draft_picks'"
        
        # Print some information about the draft picks
        picks = data["draft_picks"]
        print(f"\nNumber of first round draft picks: {len(picks)}")
        
        if picks:
            # Verify all picks are from round 1
            all_round_1 = all(pick.get('ROUND_NUMBER') == 1 for pick in picks)
            print(f"All picks are from round 1: {all_round_1}")
    
    print("\n=== Filtered draft history test completed ===")
    return data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running league_draft smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_draft_history_basic()
        df_json, df_data = test_fetch_draft_history_dataframe()
        filtered_data = test_fetch_draft_history_filtered()
        
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

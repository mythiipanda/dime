"""
Smoke test for the matchup_tools module.
Tests the functionality of fetching player matchup data with DataFrame output.
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime


from api_tools.matchup_tools import (
    fetch_league_season_matchups_logic,
    fetch_matchups_rollup_logic
)
from nba_api.stats.library.parameters import SeasonTypeAllStar

# Sample players and season for testing
DEF_PLAYER = "Rudy Gobert"
OFF_PLAYER = "LeBron James"
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing

def test_fetch_league_season_matchups_basic():
    """Test fetching season matchups with default parameters."""
    print("\n=== Testing fetch_league_season_matchups_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_league_season_matchups_logic(
        def_player_identifier=DEF_PLAYER,
        off_player_identifier=OFF_PLAYER,
        season=SAMPLE_SEASON,
        season_type=SeasonTypeAllStar.regular,
        bypass_cache=True  # Always bypass cache for testing
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
        # Check if the player fields exist
        assert "def_player_name" in data, "Response should have a 'def_player_name' field"
        assert "off_player_name" in data, "Response should have a 'off_player_name' field"
        assert "matchups" in data, "Response should have a 'matchups' field"
        
        # Print some information about the data
        print(f"Defensive Player: {data['def_player_name']}")
        print(f"Offensive Player: {data['off_player_name']}")
        print(f"Number of matchups: {len(data['matchups'])}")
        
        # Print information about a few matchups if available
        if data['matchups']:
            print("\nSample matchups:")
            for i, matchup in enumerate(data['matchups'][:2]):  # Show first 2 matchups
                print(f"  Matchup {i+1}:")
                if "GAME_DATE" in matchup:
                    print(f"    Date: {matchup.get('GAME_DATE', 'N/A')}")
                if "PARTIAL_POSS" in matchup:
                    print(f"    Possessions: {matchup.get('PARTIAL_POSS', 'N/A')}")
                if "PLAYER_PTS" in matchup:
                    print(f"    Points: {matchup.get('PLAYER_PTS', 'N/A')}")
    
    print("\n=== Basic season matchups test completed ===")
    return data

def test_fetch_league_season_matchups_dataframe():
    """Test fetching season matchups with DataFrame output."""
    print("\n=== Testing fetch_league_season_matchups_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_league_season_matchups_logic(
        def_player_identifier=DEF_PLAYER,
        off_player_identifier=OFF_PLAYER,
        season=SAMPLE_SEASON,
        season_type=SeasonTypeAllStar.regular,
        bypass_cache=True,  # Always bypass cache for testing
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
                print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns
        
        # Check if the CSV file was created
        if "dataframe_info" in data:
            for df_key, df_info in data["dataframe_info"].get("dataframes", {}).items():
                csv_path = df_info.get("csv_path")
                if csv_path:
                    full_path = os.path.join(os.getcwd(), csv_path)
                    if os.path.exists(full_path):
                        print(f"\nCSV file exists: {csv_path}")
                    else:
                        print(f"\nCSV file does not exist: {csv_path}")
        
        # Display a sample of the DataFrame if not empty
        for key, df in dataframes.items():
            if not df.empty:
                print(f"\nSample of DataFrame '{key}' (first row):")
                print(df.head(1))
                break
    
    print("\n=== DataFrame season matchups test completed ===")
    return result

def test_fetch_matchups_rollup_basic():
    """Test fetching matchups rollup with default parameters."""
    print("\n=== Testing fetch_matchups_rollup_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_matchups_rollup_logic(
        def_player_identifier=DEF_PLAYER,
        season=SAMPLE_SEASON,
        season_type=SeasonTypeAllStar.regular,
        bypass_cache=True  # Always bypass cache for testing
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
        # Check if the player fields exist
        assert "def_player_name" in data, "Response should have a 'def_player_name' field"
        assert "rollup" in data, "Response should have a 'rollup' field"
        
        # Print some information about the data
        print(f"Defensive Player: {data['def_player_name']}")
        print(f"Number of rollup entries: {len(data['rollup'])}")
        
        # Print information about a few rollup entries if available
        if data['rollup']:
            print("\nSample rollup entries:")
            for i, entry in enumerate(data['rollup'][:2]):  # Show first 2 entries
                print(f"  Entry {i+1}:")
                if "OFF_PLAYER_NAME" in entry:
                    print(f"    Offensive Player: {entry.get('OFF_PLAYER_NAME', 'N/A')}")
                if "PARTIAL_POSS" in entry:
                    print(f"    Possessions: {entry.get('PARTIAL_POSS', 'N/A')}")
                if "PLAYER_PTS" in entry:
                    print(f"    Points: {entry.get('PLAYER_PTS', 'N/A')}")
    
    print("\n=== Basic matchups rollup test completed ===")
    return data

def test_fetch_matchups_rollup_dataframe():
    """Test fetching matchups rollup with DataFrame output."""
    print("\n=== Testing fetch_matchups_rollup_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_matchups_rollup_logic(
        def_player_identifier=DEF_PLAYER,
        season=SAMPLE_SEASON,
        season_type=SeasonTypeAllStar.regular,
        bypass_cache=True,  # Always bypass cache for testing
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
                print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns
        
        # Check if the CSV file was created
        if "dataframe_info" in data:
            for df_key, df_info in data["dataframe_info"].get("dataframes", {}).items():
                csv_path = df_info.get("csv_path")
                if csv_path:
                    full_path = os.path.join(os.getcwd(), csv_path)
                    if os.path.exists(full_path):
                        print(f"\nCSV file exists: {csv_path}")
                    else:
                        print(f"\nCSV file does not exist: {csv_path}")
        
        # Display a sample of the DataFrame if not empty
        for key, df in dataframes.items():
            if not df.empty:
                print(f"\nSample of DataFrame '{key}' (first row):")
                print(df.head(1))
                break
    
    print("\n=== DataFrame matchups rollup test completed ===")
    return result

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running matchup_tools smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        season_matchups_data = test_fetch_league_season_matchups_basic()
        season_matchups_df_result = test_fetch_league_season_matchups_dataframe()
        rollup_data = test_fetch_matchups_rollup_basic()
        rollup_df_result = test_fetch_matchups_rollup_dataframe()
        
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

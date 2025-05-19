"""
Smoke test for the player_dashboard_stats module.
Tests the functionality of fetching player dashboard statistics.
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

from backend.api_tools.player_dashboard_stats import (
    fetch_player_profile_logic,
    fetch_player_defense_logic,
    fetch_player_hustle_stats_logic,
    fetch_player_fantasy_profile_logic,
    fetch_player_fantasy_profile_bargraph_logic
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, PerModeSimple, LeagueID
)

# Sample player for testing
SAMPLE_PLAYER = "LeBron James"
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing

def test_fetch_player_profile_basic():
    """Test fetching player profile with default parameters."""
    print("\n=== Testing fetch_player_profile_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_player_profile_logic(SAMPLE_PLAYER)
    
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
        # Check if the player_name field exists
        assert "player_name" in data, "Response should have a 'player_name' field"
        assert "player_id" in data, "Response should have a 'player_id' field"
        
        # Print some information about the data
        print(f"Player Name: {data.get('player_name')}")
        print(f"Player ID: {data.get('player_id')}")
        
        # Check if career totals exist
        assert "career_totals" in data, "Response should have 'career_totals'"
        assert "regular_season" in data["career_totals"], "Career totals should have 'regular_season'"
        
        # Print some career stats
        career_rs = data["career_totals"]["regular_season"]
        if career_rs:
            print("\nCareer Regular Season Stats:")
            for key, value in list(career_rs.items())[:5]:  # Show first 5 fields
                print(f"  {key}: {value}")
    
    print("\n=== Basic profile test completed ===")
    return data

def test_fetch_player_profile_dataframe():
    """Test fetching player profile with DataFrame output."""
    print("\n=== Testing fetch_player_profile_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_player_profile_logic(SAMPLE_PLAYER, return_dataframe=True)
    
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
    
    # Check if the CSV files were created
    if "dataframe_info" in data:
        for df_key, df_info in data["dataframe_info"].get("dataframes", {}).items():
            csv_path = df_info.get("csv_path")
            if csv_path:
                full_path = os.path.join(backend_dir, csv_path)
                if os.path.exists(full_path):
                    print(f"\nCSV file exists: {csv_path}")
                else:
                    print(f"\nCSV file does not exist: {csv_path}")
    
    # Display a sample of one DataFrame if not empty
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nSample of DataFrame '{key}' (first 3 rows):")
            print(df.head(3))
            break
    
    print("\n=== DataFrame profile test completed ===")
    return json_response, dataframes

def test_fetch_player_defense():
    """Test fetching player defense stats."""
    print("\n=== Testing fetch_player_defense_logic ===")
    
    # Test with default parameters
    json_response = fetch_player_defense_logic(
        SAMPLE_PLAYER,
        SAMPLE_SEASON,
        SeasonTypeAllStar.regular,
        PerModeSimple.per_game
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
        # Check if the player_name field exists
        assert "player_name" in data, "Response should have a 'player_name' field"
        assert "player_id" in data, "Response should have a 'player_id' field"
        
        # Print some information about the data
        print(f"Player Name: {data.get('player_name')}")
        print(f"Player ID: {data.get('player_id')}")
        
        # Check if summary exists
        assert "summary" in data, "Response should have 'summary'"
        
        # Print some defense stats
        summary = data["summary"]
        if summary:
            print("\nDefense Summary:")
            print(f"  Games Played: {summary.get('games_played')}")
            
            overall = summary.get("overall_defense", {})
            print("\nOverall Defense:")
            for key, value in overall.items():
                print(f"  {key}: {value}")
    
    print("\n=== Defense test completed ===")
    return data

def test_fetch_player_hustle():
    """Test fetching player hustle stats."""
    print("\n=== Testing fetch_player_hustle_stats_logic ===")
    
    # Test with player filter
    json_response = fetch_player_hustle_stats_logic(
        SAMPLE_SEASON,
        SeasonTypeAllStar.regular,
        PerModeDetailed.per_game,
        SAMPLE_PLAYER
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
        # Check if the hustle_stats field exists
        assert "hustle_stats" in data, "Response should have a 'hustle_stats' field"
        
        # Print some information about the data
        hustle_stats = data["hustle_stats"]
        print(f"Number of hustle stats entries: {len(hustle_stats)}")
        
        if hustle_stats:
            print("\nSample hustle stats:")
            for key, value in list(hustle_stats[0].items())[:10]:  # Show first 10 fields
                print(f"  {key}: {value}")
    
    print("\n=== Hustle test completed ===")
    return data

def test_fetch_player_fantasy_profile():
    """Test fetching player fantasy profile with JSON and DataFrame output."""
    print("\n=== Testing fetch_player_fantasy_profile_logic (JSON) ===")
    json_response = fetch_player_fantasy_profile_logic(SAMPLE_PLAYER, SAMPLE_SEASON)
    data = json.loads(json_response)
    assert isinstance(data, dict), "Response should be a dictionary"
    if "error" in data:
        print(f"API returned an error: {data['error']}")
    else:
        print(f"Player Name: {data.get('player_name')}")
        print(f"Season: {data.get('season')}")
        print(f"Per Mode: {data.get('per_mode')}")
        fantasy = data.get("fantasy_profile", {})
        for key, val in fantasy.items():
            print(f"\nSection: {key}, Entries: {len(val) if isinstance(val, list) else 'N/A'}")
            if isinstance(val, list) and val:
                print(f"Sample: {val[0]}")
    print("\n=== Testing fetch_player_fantasy_profile_logic (DataFrame) ===")
    result = fetch_player_fantasy_profile_logic(SAMPLE_PLAYER, SAMPLE_SEASON, return_dataframe=True)
    assert isinstance(result, tuple) and len(result) == 2, "Result should be a tuple of (json, dataframes)"
    json_response, dataframes = result
    data = json.loads(json_response)
    print(f"DataFrames returned: {list(dataframes.keys())}")
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nDataFrame '{key}' shape: {df.shape}")
            print(f"Columns: {df.columns.tolist()[:5]}...")
            print(f"Sample data:\n{df.head(2)}")
    print("\n=== Fantasy profile test completed ===")
    return data

def test_fetch_player_fantasy_profile_bargraph():
    """Test fetching player fantasy profile bar graph with JSON and DataFrame output."""
    print("\n=== Testing fetch_player_fantasy_profile_bargraph_logic (JSON) ===")
    json_response = fetch_player_fantasy_profile_bargraph_logic(SAMPLE_PLAYER, SAMPLE_SEASON)
    data = json.loads(json_response)
    assert isinstance(data, dict), "Response should be a dictionary"
    if "error" in data:
        print(f"API returned an error: {data['error']}")
    else:
        print(f"Player Name: {data.get('player_name')}")
        print(f"Season: {data.get('season')}")
        print(f"Season Type: {data.get('season_type')}")
        bargraph = data.get("fantasy_profile_bargraph", {})
        for key, val in bargraph.items():
            print(f"\nSection: {key}, Entries: {len(val) if isinstance(val, list) else 'N/A'}")
            if isinstance(val, list) and val:
                print(f"Sample: {val[0]}")
    print("\n=== Testing fetch_player_fantasy_profile_bargraph_logic (DataFrame) ===")
    result = fetch_player_fantasy_profile_bargraph_logic(SAMPLE_PLAYER, SAMPLE_SEASON, return_dataframe=True)
    assert isinstance(result, tuple) and len(result) == 2, "Result should be a tuple of (json, dataframes)"
    json_response, dataframes = result
    data = json.loads(json_response)
    print(f"DataFrames returned: {list(dataframes.keys())}")
    for key, df in dataframes.items():
        if not df.empty:
            print(f"\nDataFrame '{key}' shape: {df.shape}")
            print(f"Columns: {df.columns.tolist()[:5]}...")
            print(f"Sample data:\n{df.head(2)}")
    print("\n=== Fantasy profile bargraph test completed ===")
    return data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running player_dashboard smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        profile_data = test_fetch_player_profile_basic()
        profile_json, profile_dfs = test_fetch_player_profile_dataframe()
        defense_data = test_fetch_player_defense()
        hustle_data = test_fetch_player_hustle()
        fantasy_data = test_fetch_player_fantasy_profile()
        fantasy_bargraph_data = test_fetch_player_fantasy_profile_bargraph()
        
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

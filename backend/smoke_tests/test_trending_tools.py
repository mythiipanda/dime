"""
Smoke test for the trending_tools module.
Tests the functionality of fetching top-performing players with DataFrame output.
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

from backend.api_tools.trending_tools import fetch_top_performers_logic
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, StatCategoryAbbreviation, PerMode48, Scope, LeagueID
)

# Define the cache directory path
TRENDING_PLAYERS_CSV_DIR = os.path.join(backend_dir, "cache", "trending_players")

# Sample parameters for testing
SAMPLE_CATEGORY = StatCategoryAbbreviation.pts  # Points
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular  # Regular season
SAMPLE_PER_MODE = PerMode48.per_game  # Per game stats
SAMPLE_SCOPE = Scope.s  # Season scope
SAMPLE_LEAGUE_ID = LeagueID.nba  # NBA
SAMPLE_TOP_N = 5  # Top 5 performers

def test_fetch_top_performers_basic():
    """Test fetching top performers with default parameters."""
    print("\n=== Testing fetch_top_performers_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_top_performers_logic(
        category=SAMPLE_CATEGORY, 
        season=SAMPLE_SEASON, 
        season_type=SAMPLE_SEASON_TYPE,
        per_mode=SAMPLE_PER_MODE,
        scope=SAMPLE_SCOPE,
        league_id=SAMPLE_LEAGUE_ID,
        top_n=SAMPLE_TOP_N
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
        assert "season" in data, "Response should have a 'season' field"
        assert "stat_category" in data, "Response should have a 'stat_category' field"
        assert "season_type" in data, "Response should have a 'season_type' field"
        assert "per_mode" in data, "Response should have a 'per_mode' field"
        assert "scope" in data, "Response should have a 'scope' field"
        assert "league_id" in data, "Response should have a 'league_id' field"
        assert "requested_top_n" in data, "Response should have a 'requested_top_n' field"
        assert "top_performers" in data, "Response should have a 'top_performers' field"
        
        # Print some information about the data
        print(f"Season: {data.get('season', 'N/A')}")
        print(f"Stat Category: {data.get('stat_category', 'N/A')}")
        print(f"Season Type: {data.get('season_type', 'N/A')}")
        print(f"Per Mode: {data.get('per_mode', 'N/A')}")
        print(f"Scope: {data.get('scope', 'N/A')}")
        print(f"League ID: {data.get('league_id', 'N/A')}")
        print(f"Requested Top N: {data.get('requested_top_n', 'N/A')}")
        
        # Print details of the top performers
        top_performers = data.get("top_performers", [])
        print(f"\nTop Performers Count: {len(top_performers)}")
        
        if top_performers:
            print("\nTop 3 performers:")
            for i, player in enumerate(top_performers[:3]):
                print(f"\nPlayer {i+1}:")
                print(f"  Player Name: {player.get('PLAYER_NAME', 'N/A')}")
                print(f"  Team: {player.get('TEAM_NAME', 'N/A')}")
                print(f"  Rank: {player.get('RANK', 'N/A')}")
                print(f"  Value: {player.get('VALUE', 'N/A')}")
    
    print("\n=== Basic test completed ===")
    return data

def test_fetch_top_performers_different_categories():
    """Test fetching top performers with different statistical categories."""
    print("\n=== Testing fetch_top_performers_logic with different categories ===")
    
    # Test with different statistical categories
    categories = [StatCategoryAbbreviation.pts, StatCategoryAbbreviation.ast, StatCategoryAbbreviation.reb]
    
    for category in categories:
        print(f"\nTesting category: {category}")
        
        # Test with default parameters (JSON output)
        json_response = fetch_top_performers_logic(
            category=category, 
            season=SAMPLE_SEASON, 
            season_type=SAMPLE_SEASON_TYPE,
            per_mode=SAMPLE_PER_MODE,
            scope=SAMPLE_SCOPE,
            league_id=SAMPLE_LEAGUE_ID,
            top_n=SAMPLE_TOP_N
        )
        
        # Parse the JSON response
        data = json.loads(json_response)
        
        # Check if there's an error in the response
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            print("This might be expected if the NBA API is unavailable or rate-limited.")
        else:
            # Print some information about the data
            print(f"Stat Category: {data.get('stat_category', 'N/A')}")
            
            # Print count of top performers
            top_performers = data.get("top_performers", [])
            print(f"Top Performers Count: {len(top_performers)}")
            
            # Print the first performer
            if top_performers:
                player = top_performers[0]
                print(f"\nTop Performer:")
                print(f"  Player Name: {player.get('PLAYER_NAME', 'N/A')}")
                print(f"  Team: {player.get('TEAM_NAME', 'N/A')}")
                print(f"  Value: {player.get('VALUE', 'N/A')}")
    
    print("\n=== Different categories test completed ===")
    return True

def test_fetch_top_performers_dataframe():
    """Test fetching top performers with DataFrame output."""
    print("\n=== Testing fetch_top_performers_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_top_performers_logic(
        category=SAMPLE_CATEGORY, 
        season=SAMPLE_SEASON, 
        season_type=SAMPLE_SEASON_TYPE,
        per_mode=SAMPLE_PER_MODE,
        scope=SAMPLE_SCOPE,
        league_id=SAMPLE_LEAGUE_ID,
        top_n=SAMPLE_TOP_N,
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
        else:
            print("\nNo DataFrame info found in response (this is unexpected).")
        
        # Display a sample of each DataFrame if not empty
        for key, df in dataframes.items():
            if not df.empty:
                print(f"\nSample of DataFrame '{key}' (first 3 rows):")
                print(df.head(3))
    
    print("\n=== DataFrame test completed ===")
    return result

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running trending_tools smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        test_fetch_top_performers_basic()
        test_fetch_top_performers_different_categories()
        test_fetch_top_performers_dataframe()
        
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

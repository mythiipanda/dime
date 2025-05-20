"""
Smoke test for the trending_team_tools module.
Tests the functionality of fetching top-performing teams with DataFrame output.
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

from backend.api_tools.trending_team_tools import fetch_top_teams_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID

# Define the cache directory path
TRENDING_TEAMS_CSV_DIR = os.path.join(backend_dir, "cache", "trending_teams")

# Sample season for testing
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular  # Regular season
SAMPLE_LEAGUE_ID = LeagueID.nba  # NBA
SAMPLE_TOP_N = 5  # Top 5 teams

def test_fetch_top_teams_basic():
    """Test fetching top teams with default parameters."""
    print("\n=== Testing fetch_top_teams_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_top_teams_logic(
        season=SAMPLE_SEASON, 
        season_type=SAMPLE_SEASON_TYPE,
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
        assert "season_type" in data, "Response should have a 'season_type' field"
        assert "league_id" in data, "Response should have a 'league_id' field"
        assert "requested_top_n" in data, "Response should have a 'requested_top_n' field"
        assert "top_teams" in data, "Response should have a 'top_teams' field"
        
        # Print some information about the data
        print(f"Season: {data.get('season', 'N/A')}")
        print(f"Season Type: {data.get('season_type', 'N/A')}")
        print(f"League ID: {data.get('league_id', 'N/A')}")
        print(f"Requested Top N: {data.get('requested_top_n', 'N/A')}")
        
        # Print details of the top teams
        top_teams = data.get("top_teams", [])
        print(f"\nTop Teams Count: {len(top_teams)}")
        
        if top_teams:
            print("\nTop 3 teams:")
            for i, team in enumerate(top_teams[:3]):
                print(f"\nTeam {i+1}:")
                print(f"  Team Name: {team.get('TeamName', 'N/A')}")
                print(f"  Conference: {team.get('Conference', 'N/A')}")
                print(f"  Win Percentage: {team.get('WinPct', 'N/A')}")
                print(f"  Record: {team.get('Record', 'N/A')}")
                print(f"  League Rank: {team.get('LeagueRank', 'N/A')}")
    
    print("\n=== Basic test completed ===")
    return data

def test_fetch_top_teams_different_top_n():
    """Test fetching top teams with different top_n values."""
    print("\n=== Testing fetch_top_teams_logic with different top_n values ===")
    
    # Test with different top_n values
    top_n_values = [3, 10]
    
    for top_n in top_n_values:
        print(f"\nTesting top_n: {top_n}")
        
        # Test with default parameters (JSON output)
        json_response = fetch_top_teams_logic(
            season=SAMPLE_SEASON, 
            season_type=SAMPLE_SEASON_TYPE,
            league_id=SAMPLE_LEAGUE_ID,
            top_n=top_n
        )
        
        # Parse the JSON response
        data = json.loads(json_response)
        
        # Check if there's an error in the response
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            print("This might be expected if the NBA API is unavailable or rate-limited.")
        else:
            # Print some information about the data
            print(f"Requested Top N: {data.get('requested_top_n', 'N/A')}")
            
            # Print count of top teams
            top_teams = data.get("top_teams", [])
            print(f"Top Teams Count: {len(top_teams)}")
            
            # Print the first team
            if top_teams:
                team = top_teams[0]
                print(f"\nTop Team:")
                print(f"  Team Name: {team.get('TeamName', 'N/A')}")
                print(f"  Win Percentage: {team.get('WinPct', 'N/A')}")
    
    print("\n=== Different top_n values test completed ===")
    return True

def test_fetch_top_teams_dataframe():
    """Test fetching top teams with DataFrame output."""
    print("\n=== Testing fetch_top_teams_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_top_teams_logic(
        season=SAMPLE_SEASON, 
        season_type=SAMPLE_SEASON_TYPE,
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
    print(f"=== Running trending_team_tools smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        test_fetch_top_teams_basic()
        test_fetch_top_teams_different_top_n()
        test_fetch_top_teams_dataframe()
        
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

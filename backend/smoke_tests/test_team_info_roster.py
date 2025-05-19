"""
Smoke test for the team_info_roster module.
Tests the functionality of fetching team information and roster with DataFrame output.
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

from backend.api_tools.team_info_roster import fetch_team_info_and_roster_logic
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar

def test_fetch_team_info_roster_basic():
    """Test fetching team info and roster with default parameters."""
    print("\n=== Testing fetch_team_info_and_roster_logic (basic) ===")
    
    # Test with a well-known team
    team_identifier = "Boston Celtics"
    season = "2022-23"  # Use a completed season for testing
    
    # Test with default parameters (JSON output)
    json_response = fetch_team_info_and_roster_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=SeasonTypeAllStar.regular,
        league_id=LeagueID.nba
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
        assert "info" in data, "Response should have an 'info' field"
        assert "ranks" in data, "Response should have a 'ranks' field"
        assert "roster" in data, "Response should have a 'roster' field"
        assert "coaches" in data, "Response should have a 'coaches' field"
        
        # Print some information about the data
        print(f"Team: {data['team_name']} (ID: {data['team_id']})")
        print(f"Season: {data['season']}")
        
        # Print details of the team info
        if data['info']:
            print("\nTeam Info:")
            print(f"  City: {data['info'].get('TEAM_CITY', 'N/A')}")
            print(f"  Abbreviation: {data['info'].get('TEAM_ABBREVIATION', 'N/A')}")
            print(f"  Conference: {data['info'].get('TEAM_CONFERENCE', 'N/A')}")
            print(f"  Division: {data['info'].get('TEAM_DIVISION', 'N/A')}")
        
        # Print details of the team ranks
        if data['ranks']:
            print("\nTeam Ranks:")
            print(f"  PTS Rank: {data['ranks'].get('PTS_RANK', 'N/A')}")
            print(f"  REB Rank: {data['ranks'].get('REB_RANK', 'N/A')}")
            print(f"  AST Rank: {data['ranks'].get('AST_RANK', 'N/A')}")
        
        # Print details of the roster
        if data['roster']:
            print(f"\nRoster Size: {len(data['roster'])}")
            if data['roster']:
                print("\nFirst 3 players:")
                for i, player in enumerate(data['roster'][:3]):
                    print(f"\nPlayer {i+1}:")
                    print(f"  Name: {player.get('PLAYER', 'N/A')}")
                    print(f"  Number: {player.get('NUM', 'N/A')}")
                    print(f"  Position: {player.get('POSITION', 'N/A')}")
                    print(f"  Height: {player.get('HEIGHT', 'N/A')}")
                    print(f"  Weight: {player.get('WEIGHT', 'N/A')}")
        
        # Print details of the coaches
        if data['coaches']:
            print(f"\nCoaches Count: {len(data['coaches'])}")
            if data['coaches']:
                print("\nFirst 2 coaches:")
                for i, coach in enumerate(data['coaches'][:2]):
                    print(f"\nCoach {i+1}:")
                    print(f"  Name: {coach.get('COACH_NAME', 'N/A')}")
                    print(f"  Type: {coach.get('COACH_TYPE', 'N/A')}")
    
    print("\n=== Basic team info and roster test completed ===")
    return data

def test_fetch_team_info_roster_dataframe():
    """Test fetching team info and roster with DataFrame output."""
    print("\n=== Testing fetch_team_info_and_roster_logic with DataFrame output ===")
    
    # Test with a well-known team
    team_identifier = "Boston Celtics"
    season = "2022-23"  # Use a completed season for testing
    
    # Test with return_dataframe=True
    result = fetch_team_info_and_roster_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=SeasonTypeAllStar.regular,
        league_id=LeagueID.nba,
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
    
    print("\n=== DataFrame team info and roster test completed ===")
    return result

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running team_info_roster smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_team_info_roster_basic()
        df_result = test_fetch_team_info_roster_dataframe()
        
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

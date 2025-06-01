"""
Smoke test for the game_visuals_analytics module's shotchart functionality.
Tests the functionality of fetching shot chart data for NBA games.
"""
import os

import json
import pandas as pd
from datetime import datetime



from api_tools.game_visuals_analytics import (
    fetch_shotchart_logic,
    SHOTCHART_CSV_DIR
)

# Sample game ID for testing (2023-24 regular season game)
SAMPLE_GAME_ID = "0022300161"  # Change this to a valid game ID if needed

def test_fetch_shotchart_basic():
    """Test fetching shot chart data with default parameters."""
    print("\n=== Testing fetch_shotchart_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_shotchart_logic(SAMPLE_GAME_ID)
    
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
        # Check if the game_id field exists and matches the input
        assert "game_id" in data, "Response should have a 'game_id' field"
        assert data["game_id"] == SAMPLE_GAME_ID, f"game_id should be {SAMPLE_GAME_ID}"
        
        # Check if the teams field exists and is a list
        assert "teams" in data, "Response should have a 'teams' field"
        assert isinstance(data["teams"], list), "'teams' field should be a list"
        
        # Print some information about the data
        print(f"Number of teams: {len(data['teams'])}")
        
        if data["teams"]:
            # Print details of the first team
            first_team = data["teams"][0]
            print(f"\nTeam: {first_team.get('team_name', 'N/A')} (ID: {first_team.get('team_id', 'N/A')})")
            shots = first_team.get("shots", [])
            print(f"Number of shots: {len(shots)}")
            
            if shots:
                # Print details of the first few shots
                print("\nFirst 3 shots:")
                for i, shot in enumerate(shots[:3]):
                    print(f"\nShot {i+1}:")
                    print(f"  Player: {shot.get('player', {}).get('name', 'N/A')}")
                    print(f"  Period: {shot.get('period', 'N/A')}")
                    print(f"  Shot Type: {shot.get('shot_type', 'N/A')}")
                    print(f"  Made: {shot.get('made', 'N/A')}")
                    print(f"  Coordinates: {shot.get('coordinates', {})}")
                    print(f"  Zone: {shot.get('shot_zone_basic', 'N/A')}")
    
    print("\n=== Basic test completed ===")
    return data

def test_fetch_shotchart_with_filters():
    """Test fetching shot chart data with various filters."""
    print("\n=== Testing fetch_shotchart_logic with filters ===")
    
    # Test with team filter
    print("\nTesting with team filter:")
    if len(test_fetch_shotchart_basic().get("teams", [])) > 0:
        team_id = test_fetch_shotchart_basic().get("teams", [])[0].get("team_id")
        team_filtered_json = fetch_shotchart_logic(SAMPLE_GAME_ID, team_id=team_id)
        team_filtered_data = json.loads(team_filtered_json)
        
        if "error" not in team_filtered_data:
            teams = team_filtered_data.get("teams", [])
            print(f"Number of teams returned: {len(teams)}")
            if teams:
                team_ids = [t.get("team_id") for t in teams]
                print(f"Team IDs: {team_ids}")
    
    # Test with period filter
    print("\nTesting with period filter (period 1 only):")
    period_filtered_json = fetch_shotchart_logic(SAMPLE_GAME_ID, period=1)
    period_filtered_data = json.loads(period_filtered_json)
    
    if "error" not in period_filtered_data:
        all_shots = []
        for team in period_filtered_data.get("teams", []):
            all_shots.extend(team.get("shots", []))
        
        print(f"Number of shots in period 1: {len(all_shots)}")
        if all_shots:
            periods = set(shot.get("period") for shot in all_shots)
            print(f"Periods found: {periods}")
    
    # Test with shot_made filter
    print("\nTesting with shot_made filter (made shots only):")
    made_filtered_json = fetch_shotchart_logic(SAMPLE_GAME_ID, shot_made=True)
    made_filtered_data = json.loads(made_filtered_json)
    
    if "error" not in made_filtered_data:
        all_made_shots = []
        for team in made_filtered_data.get("teams", []):
            all_made_shots.extend(team.get("shots", []))
        
        print(f"Number of made shots: {len(all_made_shots)}")
        if all_made_shots:
            made_values = set(shot.get("made") for shot in all_made_shots)
            print(f"Made values found: {made_values}")
    
    print("\n=== Filter tests completed ===")
    return period_filtered_data, made_filtered_data

def test_fetch_shotchart_dataframe():
    """Test fetching shot chart data with DataFrame output."""
    print("\n=== Testing fetch_shotchart_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_shotchart_logic(SAMPLE_GAME_ID, return_dataframe=True)
    
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
        print(f"\nDataFrame '{key}' shape: {df.shape}")
        print(f"DataFrame '{key}' columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns
    
    # Check if the CSV files were created
    if os.path.exists(SHOTCHART_CSV_DIR):
        csv_files = [f for f in os.listdir(SHOTCHART_CSV_DIR) if f.startswith(SAMPLE_GAME_ID)]
        print(f"\nCSV files created: {csv_files}")
    
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
    print(f"=== Running game_shotchart smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_shotchart_basic()
        period_filtered_data, made_filtered_data = test_fetch_shotchart_with_filters()
        json_response, dataframes = test_fetch_shotchart_dataframe()
        
        print("\n=== All tests completed successfully ===")
        return True
    except Exception as e:
        print(f"\n!!! Test failed with error: {str(e)} !!!")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    # Add the parent directory to the Python path to find 'api_tools', 'tool_kits', etc.
    success = run_all_tests()
    sys.exit(0 if success else 1)

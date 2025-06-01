"""
Smoke test for the shot_charts module.
Tests the functionality of fetching player shot charts with DataFrame output.
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime


from api_tools.shot_charts import fetch_player_shot_chart

def test_fetch_player_shot_chart_basic():
    """Test fetching player shot chart with default parameters."""
    print("\n=== Testing fetch_player_shot_chart (basic) ===")
    
    # Test with a well-known player
    player_name = "Stephen Curry"
    season = "2022-23"  # Use a completed season for testing
    
    # Test with default parameters (JSON output)
    json_response = fetch_player_shot_chart(
        player_name=player_name,
        season=season
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
        assert "player_name" in data, "Response should have a 'player_name' field"
        assert "player_id" in data, "Response should have a 'player_id' field"
        assert "shots" in data, "Response should have a 'shots' field"
        assert "zones" in data, "Response should have a 'zones' field"
        
        # Print some information about the data
        print(f"Player: {data['player_name']} (ID: {data['player_id']})")
        print(f"Team: {data.get('team_name', 'N/A')} (ID: {data.get('team_id', 'N/A')})")
        print(f"Season: {data.get('season', 'N/A')}")
        print(f"Number of shots: {len(data['shots'])}")
        print(f"Number of zones: {len(data['zones'])}")
        
        # Print details of the first few shots
        if data['shots']:
            print("\nFirst 3 shots:")
            for i, shot in enumerate(data['shots'][:3]):
                print(f"\nShot {i+1}:")
                print(f"  Position: ({shot.get('x', 'N/A')}, {shot.get('y', 'N/A')})")
                print(f"  Made: {shot.get('made', 'N/A')}")
                print(f"  Value: {shot.get('value', 'N/A')} points")
                print(f"  Type: {shot.get('shot_type', 'N/A')}")
                print(f"  Zone: {shot.get('shot_zone', 'N/A')}")
                print(f"  Distance: {shot.get('distance', 'N/A')} feet")
        
        # Print details of the first few zones
        if data['zones']:
            print("\nFirst 3 zones:")
            for i, zone in enumerate(data['zones'][:3]):
                print(f"\nZone {i+1}:")
                print(f"  Name: {zone.get('zone', 'N/A')}")
                print(f"  Attempts: {zone.get('attempts', 'N/A')}")
                print(f"  Made: {zone.get('made', 'N/A')}")
                print(f"  Percentage: {zone.get('percentage', 'N/A'):.3f}")
                print(f"  League Percentage: {zone.get('leaguePercentage', 'N/A'):.3f}")
                print(f"  Relative Percentage: {zone.get('relativePercentage', 'N/A'):.3f}")
    
    print("\n=== Basic shot chart test completed ===")
    return data

def test_fetch_player_shot_chart_dataframe():
    """Test fetching player shot chart with DataFrame output."""
    print("\n=== Testing fetch_player_shot_chart with DataFrame output ===")
    
    # Test with a well-known player
    player_name = "Stephen Curry"
    season = "2022-23"  # Use a completed season for testing
    
    # Test with return_dataframe=True
    result = fetch_player_shot_chart(
        player_name=player_name,
        season=season,
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
        
        # Check if the CSV file was created
        if "dataframe_info" in data:
            for df_key, df_info in data["dataframe_info"].get("dataframes", {}).items():
                csv_path = df_info.get("csv_path")
                if csv_path:
                    full_path = os.path.join(os.getcwd(), csv_path)
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
    
    print("\n=== DataFrame shot chart test completed ===")
    return result

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running shot_charts smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_player_shot_chart_basic()
        df_result = test_fetch_player_shot_chart_dataframe()
        
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

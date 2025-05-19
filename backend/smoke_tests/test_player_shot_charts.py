"""
Smoke test for the player_shot_charts module.
Tests the functionality of fetching player shot chart data and generating visualizations.
"""
import os

import json
import pandas as pd
from datetime import datetime



from api_tools.player_shot_charts import (
    fetch_player_shotchart_logic,
    PLAYER_SHOTCHART_CSV_DIR,
    _calculate_overall_shot_stats,
    _calculate_zone_summary
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar
)

# Sample player name and season for testing
SAMPLE_PLAYER_NAME = "Stephen Curry"  # A player known for shooting
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing
SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular  # Regular season

def test_fetch_player_shotchart_basic():
    """Test fetching player shot chart data with default parameters."""
    print("\n=== Testing fetch_player_shotchart_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_player_shotchart_logic(
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
        
        # Check if the season field exists and matches the input
        assert "season" in data, "Response should have a 'season' field"
        assert data["season"] == SAMPLE_SEASON, f"season should be {SAMPLE_SEASON}"
        
        # Check if the season_type field exists and matches the input
        assert "season_type" in data, "Response should have a 'season_type' field"
        assert data["season_type"] == SAMPLE_SEASON_TYPE, f"season_type should be {SAMPLE_SEASON_TYPE}"
        
        # Check if the shot chart data fields exist
        assert "overall_stats" in data, "Response should have an 'overall_stats' field"
        assert "zone_breakdown" in data, "Response should have a 'zone_breakdown' field"
        assert "shot_data_summary" in data, "Response should have a 'shot_data_summary' field"
        assert "league_averages" in data, "Response should have a 'league_averages' field"
        assert "visualization_path" in data, "Response should have a 'visualization_path' field"
        
        # Print some information about the data
        print(f"Player: {data.get('player_name', 'N/A')} (ID: {data.get('player_id', 'N/A')})")
        print(f"Season: {data.get('season', 'N/A')}")
        print(f"Season Type: {data.get('season_type', 'N/A')}")
        
        # Print overall shot stats
        if "overall_stats" in data and data["overall_stats"]:
            overall = data["overall_stats"]
            print("\nOverall Shot Stats:")
            print(f"  Total Shots: {overall.get('total_shots', 'N/A')}")
            print(f"  Made Shots: {overall.get('made_shots', 'N/A')}")
            print(f"  Field Goal Percentage: {overall.get('field_goal_percentage', 'N/A')}%")
        
        # Print zone breakdown
        if "zone_breakdown" in data and data["zone_breakdown"]:
            zones = data["zone_breakdown"]
            print(f"\nZone Breakdown: {len(zones)} zones")
            for zone, stats in zones.items():
                print(f"  {zone}: {stats.get('made', 'N/A')}/{stats.get('attempts', 'N/A')} ({stats.get('percentage', 'N/A')}%)")
        
        # Print visualization path
        if "visualization_path" in data and data["visualization_path"]:
            print(f"\nVisualization Path: {data.get('visualization_path', 'N/A')}")
            # Check if the visualization file exists
            if os.path.exists(data["visualization_path"]):
                print("  Visualization file exists.")
            else:
                print("  Visualization file does not exist.")
    
    print("\n=== Basic test completed ===")
    return data

def test_fetch_player_shotchart_playoffs():
    """Test fetching player shot chart data for playoffs."""
    print("\n=== Testing fetch_player_shotchart_logic (Playoffs) ===")
    
    # Test with Playoffs season type
    json_response = fetch_player_shotchart_logic(
        SAMPLE_PLAYER_NAME, 
        SAMPLE_SEASON, 
        SeasonTypeAllStar.playoffs
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
        # Check if the season_type parameter matches the input
        assert data.get("season_type") == SeasonTypeAllStar.playoffs, \
            f"season_type should be {SeasonTypeAllStar.playoffs}"
        
        # Print some information about the data
        print(f"Player: {data.get('player_name', 'N/A')} (ID: {data.get('player_id', 'N/A')})")
        print(f"Season Type: {data.get('season_type', 'N/A')}")
        
        # Print overall shot stats
        if "overall_stats" in data and data["overall_stats"]:
            overall = data["overall_stats"]
            print("\nOverall Shot Stats (Playoffs):")
            print(f"  Total Shots: {overall.get('total_shots', 'N/A')}")
            print(f"  Made Shots: {overall.get('made_shots', 'N/A')}")
            print(f"  Field Goal Percentage: {overall.get('field_goal_percentage', 'N/A')}%")
    
    print("\n=== Playoffs test completed ===")
    return data

def test_fetch_player_shotchart_dataframe():
    """Test fetching player shot chart data with DataFrame output."""
    print("\n=== Testing fetch_player_shotchart_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_player_shotchart_logic(
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
    if os.path.exists(PLAYER_SHOTCHART_CSV_DIR):
        csv_files = [f for f in os.listdir(PLAYER_SHOTCHART_CSV_DIR) if f.startswith(SAMPLE_PLAYER_NAME.lower().replace(" ", "_"))]
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
    print(f"=== Running player_shot_charts smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_player_shotchart_basic()
        playoffs_data = test_fetch_player_shotchart_playoffs()
        json_response, dataframes = test_fetch_player_shotchart_dataframe()
        
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

"""
Smoke test for the advanced_metrics module.
Tests the functionality of fetching advanced metrics, skill grades, and similar players.
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

from backend.api_tools.advanced_metrics import (
    fetch_player_advanced_analysis_logic
)

# Sample player for testing
SAMPLE_PLAYER = "LeBron James"
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing

def test_fetch_player_advanced_analysis_basic():
    """Test fetching player advanced analysis with default parameters."""
    print("\n=== Testing fetch_player_advanced_analysis_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_player_advanced_analysis_logic(
        SAMPLE_PLAYER,
        SAMPLE_SEASON
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
        
        # Check if advanced_metrics exist
        assert "advanced_metrics" in data, "Response should have 'advanced_metrics'"
        
        # Print some information about the metrics
        metrics = data["advanced_metrics"]
        print("\nAdvanced Metrics:")
        for key, value in list(metrics.items())[:5]:  # Show first 5 metrics
            print(f"  {key}: {value}")
        
        # Check if skill_grades exist
        assert "skill_grades" in data, "Response should have 'skill_grades'"
        
        # Print some information about the skill grades
        grades = data["skill_grades"]
        print("\nSkill Grades:")
        for key, value in grades.items():
            print(f"  {key}: {value}")
        
        # Check if similar_players exist
        assert "similar_players" in data, "Response should have 'similar_players'"
        
        # Print some information about the similar players
        similar = data["similar_players"]
        print(f"\nNumber of similar players: {len(similar)}")
        if similar:
            print("\nSample similar player:")
            first_player = similar[0]
            print(f"  Player: {first_player.get('player_name')} (ID: {first_player.get('player_id')})")
            print(f"  Similarity Score: {first_player.get('similarity_score')}")
    
    print("\n=== Basic advanced metrics test completed ===")
    return data

def test_fetch_player_advanced_analysis_dataframe():
    """Test fetching player advanced analysis with DataFrame output."""
    print("\n=== Testing fetch_player_advanced_analysis_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_player_advanced_analysis_logic(
        SAMPLE_PLAYER,
        SAMPLE_SEASON,
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
        if not df.empty and key in ["advanced_metrics", "skill_grades", "raptor_metrics"]:
            print(f"\nSample of DataFrame '{key}' (first 3 rows):")
            print(df.head(3))
            break
    
    print("\n=== DataFrame advanced metrics test completed ===")
    return json_response, dataframes

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running advanced_metrics smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_player_advanced_analysis_basic()
        df_json, df_data = test_fetch_player_advanced_analysis_dataframe()
        
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

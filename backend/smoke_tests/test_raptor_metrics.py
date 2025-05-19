"""
Smoke test for the raptor_metrics module.
Tests the functionality of calculating RAPTOR metrics with DataFrame output.
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

from backend.api_tools.raptor_metrics import get_player_raptor_metrics

# Sample player for testing
SAMPLE_PLAYER_ID = 2544  # LeBron James
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing

def test_get_player_raptor_metrics_basic():
    """Test calculating RAPTOR metrics with default parameters."""
    print("\n=== Testing get_player_raptor_metrics (basic) ===")
    
    # Test with default parameters (JSON output)
    metrics = get_player_raptor_metrics(
        player_id=SAMPLE_PLAYER_ID,
        season=SAMPLE_SEASON
    )
    
    # Check if the response has the expected structure
    assert isinstance(metrics, dict), "Response should be a dictionary"
    
    # Check if there's an error in the response
    if "error" in metrics:
        print(f"API returned an error: {metrics['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        print("Continuing with other tests...")
    else:
        # Check if the key metrics exist
        assert "PLAYER_NAME" in metrics, "Response should have a 'PLAYER_NAME' field"
        assert "POSITION" in metrics, "Response should have a 'POSITION' field"
        assert "RAPTOR_OFFENSE" in metrics, "Response should have a 'RAPTOR_OFFENSE' field"
        assert "RAPTOR_DEFENSE" in metrics, "Response should have a 'RAPTOR_DEFENSE' field"
        assert "RAPTOR_TOTAL" in metrics, "Response should have a 'RAPTOR_TOTAL' field"
        assert "ELO_RATING" in metrics, "Response should have an 'ELO_RATING' field"
        assert "SKILL_GRADES" in metrics, "Response should have a 'SKILL_GRADES' field"
        
        # Print some information about the data
        print(f"Player Name: {metrics['PLAYER_NAME']}")
        print(f"Position: {metrics['POSITION']}")
        
        # Print RAPTOR metrics
        print("\nRAPTOR Metrics:")
        print(f"  Offensive RAPTOR: {metrics['RAPTOR_OFFENSE']}")
        print(f"  Defensive RAPTOR: {metrics['RAPTOR_DEFENSE']}")
        print(f"  Total RAPTOR: {metrics['RAPTOR_TOTAL']}")
        print(f"  ELO Rating: {metrics['ELO_RATING']}")
        
        # Print skill grades
        skill_grades = metrics["SKILL_GRADES"]
        print("\nSkill Grades:")
        for skill, grade in skill_grades.items():
            print(f"  {skill.replace('_', ' ').title()}: {grade}")
    
    print("\n=== Basic RAPTOR metrics test completed ===")
    return metrics

def test_get_player_raptor_metrics_dataframe():
    """Test calculating RAPTOR metrics with DataFrame output."""
    print("\n=== Testing get_player_raptor_metrics with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = get_player_raptor_metrics(
        player_id=SAMPLE_PLAYER_ID,
        season=SAMPLE_SEASON,
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
        
        # Check if the CSV files were created
        if "dataframe_info" in data:
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
        
        # Display a sample of the metrics DataFrame if not empty
        if "raptor_metrics" in dataframes and not dataframes["raptor_metrics"].empty:
            print("\nSample of RAPTOR metrics DataFrame:")
            metrics_df = dataframes["raptor_metrics"]
            
            # Select key columns to display
            key_columns = [col for col in metrics_df.columns if col in [
                "PLAYER_NAME", "POSITION", "RAPTOR_OFFENSE", "RAPTOR_DEFENSE", 
                "RAPTOR_TOTAL", "ELO_RATING"
            ]]
            
            print(metrics_df[key_columns])
        
        # Display a sample of the skill grades DataFrame if not empty
        if "skill_grades" in dataframes and not dataframes["skill_grades"].empty:
            print("\nSample of skill grades DataFrame:")
            print(dataframes["skill_grades"])
    
    print("\n=== DataFrame RAPTOR metrics test completed ===")
    return result

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running raptor_metrics smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_metrics = test_get_player_raptor_metrics_basic()
        df_result = test_get_player_raptor_metrics_dataframe()
        
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

"""
Smoke test for the advanced_shot_charts module.
Tests the functionality of generating advanced shot charts with DataFrame output.
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

from backend.api_tools.advanced_shot_charts import (
    process_shot_data_for_visualization
)

# Sample player and season for testing
SAMPLE_PLAYER = "LeBron James"
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing

def test_process_shot_data_basic():
    """Test processing shot data with default parameters."""
    print("\n=== Testing process_shot_data_for_visualization (basic) ===")
    
    # Test with default parameters (JSON output)
    result = process_shot_data_for_visualization(
        player_name=SAMPLE_PLAYER,
        season=SAMPLE_SEASON,
        chart_type="scatter",
        output_format="base64",
        use_cache=False
    )
    
    # Check if the result has the expected structure
    assert isinstance(result, dict), "Result should be a dictionary"
    
    # Check if there's an error in the result
    if "error" in result:
        print(f"API returned an error: {result['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        print("Continuing with other tests...")
    else:
        # Check if the image_data field exists
        assert "image_data" in result, "Result should have an 'image_data' field"
        assert result["image_data"].startswith("data:image/png;base64,"), "image_data should be a base64-encoded PNG"
        
        # Print some information about the result
        print(f"Chart type: {result.get('chart_type', 'N/A')}")
        print(f"Image data length: {len(result.get('image_data', ''))}")
    
    print("\n=== Basic shot chart test completed ===")
    return result

def test_process_shot_data_dataframe():
    """Test processing shot data with DataFrame output."""
    print("\n=== Testing process_shot_data_for_visualization with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = process_shot_data_for_visualization(
        player_name=SAMPLE_PLAYER,
        season=SAMPLE_SEASON,
        chart_type="scatter",
        output_format="base64",
        use_cache=False,
        return_dataframe=True
    )
    
    # Check if the result is a tuple
    assert isinstance(result, tuple), "Result should be a tuple when return_dataframe=True"
    assert len(result) == 2, "Result tuple should have 2 elements"
    
    json_result, dataframes = result
    
    # Check if the first element is a dictionary
    assert isinstance(json_result, dict), "First element should be a dictionary"
    
    # Check if the second element is a dictionary of DataFrames
    assert isinstance(dataframes, dict), "Second element should be a dictionary of DataFrames"
    
    # Check if there's an error in the result
    if "error" in json_result:
        print(f"API returned an error: {json_result['error']}")
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
        if "dataframe_info" in json_result:
            for df_key, df_info in json_result["dataframe_info"].get("dataframes", {}).items():
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
    
    print("\n=== DataFrame shot chart test completed ===")
    return result

def test_process_shot_data_heatmap():
    """Test processing shot data with heatmap chart type."""
    print("\n=== Testing process_shot_data_for_visualization with heatmap chart type ===")
    
    # Test with heatmap chart type
    result = process_shot_data_for_visualization(
        player_name=SAMPLE_PLAYER,
        season=SAMPLE_SEASON,
        chart_type="heatmap",
        output_format="base64",
        use_cache=False
    )
    
    # Check if the result has the expected structure
    assert isinstance(result, dict), "Result should be a dictionary"
    
    # Check if there's an error in the result
    if "error" in result:
        print(f"API returned an error: {result['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        print("Continuing with other tests...")
    else:
        # Check if the image_data field exists
        assert "image_data" in result, "Result should have an 'image_data' field"
        assert result["image_data"].startswith("data:image/png;base64,"), "image_data should be a base64-encoded PNG"
        
        # Print some information about the result
        print(f"Chart type: {result.get('chart_type', 'N/A')}")
        print(f"Image data length: {len(result.get('image_data', ''))}")
    
    print("\n=== Heatmap shot chart test completed ===")
    return result

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running advanced_shot_charts smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_result = test_process_shot_data_basic()
        df_result = test_process_shot_data_dataframe()
        heatmap_result = test_process_shot_data_heatmap()
        
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

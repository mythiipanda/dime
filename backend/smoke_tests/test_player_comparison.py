"""
Smoke test for the player_comparison module.
Tests the functionality of comparing player shot charts.
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime


from api_tools.player_comparison import (
    compare_player_shots
)

# Sample players for testing
SAMPLE_PLAYERS = ["LeBron James", "Stephen Curry"]
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing

def test_compare_player_shots_basic():
    """Test comparing player shots with default parameters."""
    print("\n=== Testing compare_player_shots (basic) ===")

    # Test with default parameters (JSON output)
    result = compare_player_shots(
        SAMPLE_PLAYERS,
        SAMPLE_SEASON,
        "Regular Season",
        "base64",
        "scatter"
    )

    # Check if the response has the expected structure
    assert isinstance(result, dict), "Response should be a dictionary"

    # Check if there's an error in the response
    if "error" in result:
        print(f"API returned an error: {result['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        print("Continuing with other tests...")
    else:
        # Check if the image_data field exists for visualization
        assert "image_data" in result, "Response should have an 'image_data' field"
        assert "chart_type" in result, "Response should have a 'chart_type' field"

        # Print some information about the data
        print(f"Chart Type: {result['chart_type']}")
        print(f"Image Data Length: {len(result['image_data']) if 'image_data' in result else 'N/A'}")

        # Check if the image data starts with the expected format
        if "image_data" in result:
            assert result["image_data"].startswith("data:image/png;base64,"), "Image data should be in base64 format"

    print("\n=== Basic comparison test completed ===")
    return result

def test_compare_player_shots_dataframe():
    """Test comparing player shots with DataFrame output."""
    print("\n=== Testing compare_player_shots with DataFrame output ===")

    # Test with return_dataframe=True
    result = compare_player_shots(
        SAMPLE_PLAYERS,
        SAMPLE_SEASON,
        "Regular Season",
        "base64",
        "scatter",
        return_dataframe=True
    )

    # Check if the result is a tuple
    assert isinstance(result, tuple), "Result should be a tuple when return_dataframe=True"
    assert len(result) == 2, "Result tuple should have 2 elements"

    visualization_data, dataframes = result

    # Check if the first element is a dictionary
    assert isinstance(visualization_data, dict), "First element should be a dictionary"

    # Check if the second element is a dictionary of DataFrames
    assert isinstance(dataframes, dict), "Second element should be a dictionary of DataFrames"

    # Check if there's an error in the response
    if "error" in visualization_data:
        print(f"API returned an error: {visualization_data['error']}")
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
        if "dataframe_info" in visualization_data:
            for df_key, df_info in visualization_data["dataframe_info"].get("dataframes", {}).items():
                csv_path = df_info.get("csv_path")
                if csv_path:
                    full_path = os.path.join(os.getcwd(), csv_path)
                    if os.path.exists(full_path):
                        print(f"\nCSV file exists: {csv_path}")
                    else:
                        print(f"\nCSV file does not exist: {csv_path}")

        # Display a sample of the zone breakdown DataFrame if available
        if "zone_breakdown" in dataframes and not dataframes["zone_breakdown"].empty:
            print(f"\nSample of zone breakdown DataFrame (first 3 rows):")
            print(dataframes["zone_breakdown"].head(3))

    print("\n=== DataFrame comparison test completed ===")
    return visualization_data, dataframes

def test_compare_player_shots_heatmap():
    """Test comparing player shots with heatmap chart type."""
    print("\n=== Testing compare_player_shots with heatmap chart type ===")

    # Test with heatmap chart type
    result = compare_player_shots(
        SAMPLE_PLAYERS,
        SAMPLE_SEASON,
        "Regular Season",
        "base64",
        "heatmap"
    )

    # Check if the response has the expected structure
    assert isinstance(result, dict), "Response should be a dictionary"

    # Check if there's an error in the response
    if "error" in result:
        print(f"API returned an error: {result['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        print("Continuing with other tests...")
    else:
        # Check if the chart_type parameter was correctly used
        assert result["chart_type"] == "comparison_heatmap", "Chart type should be 'comparison_heatmap'"

        # Print some information about the data
        print(f"Chart Type: {result['chart_type']}")
        print(f"Image Data Length: {len(result['image_data']) if 'image_data' in result else 'N/A'}")

    print("\n=== Heatmap comparison test completed ===")
    return result

def test_compare_player_shots_zones():
    """Test comparing player shots with zones chart type."""
    print("\n=== Testing compare_player_shots with zones chart type ===")

    # Test with zones chart type
    result = compare_player_shots(
        SAMPLE_PLAYERS,
        SAMPLE_SEASON,
        "Regular Season",
        "base64",
        "zones"
    )

    # Check if the response has the expected structure
    assert isinstance(result, dict), "Response should be a dictionary"

    # Check if there's an error in the response
    if "error" in result:
        print(f"API returned an error: {result['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        print("Continuing with other tests...")
    else:
        # Check if the chart_type parameter was correctly used
        assert result["chart_type"] == "comparison_zones", "Chart type should be 'comparison_zones'"

        # Print some information about the data
        print(f"Chart Type: {result['chart_type']}")
        print(f"Image Data Length: {len(result['image_data']) if 'image_data' in result else 'N/A'}")

    print("\n=== Zones comparison test completed ===")
    return result

def test_compare_player_shots_with_filters():
    """Test comparing player shots with additional filter parameters."""
    print("\n=== Testing compare_player_shots with filter parameters ===")

    # Test with minimal additional parameters that are known to work
    result = compare_player_shots(
        SAMPLE_PLAYERS,
        SAMPLE_SEASON,
        "Regular Season",
        "base64",
        "scatter",
        context_measure="FGM"
    )

    # Check if the response has the expected structure
    assert isinstance(result, dict), "Response should be a dictionary"

    # Check if there's an error in the response
    if "error" in result:
        print(f"API returned an error: {result['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        print("Continuing with other tests...")
    else:
        # Check if the image_data field exists for visualization
        assert "image_data" in result, "Response should have an 'image_data' field"
        assert "chart_type" in result, "Response should have a 'chart_type' field"

        # Print some information about the data
        print(f"Chart Type: {result['chart_type']}")
        print(f"Image Data Length: {len(result['image_data']) if 'image_data' in result else 'N/A'}")

    print("\n=== Filter parameters test completed ===")
    return result

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running player_comparison smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        basic_result = test_compare_player_shots_basic()
        df_result, dataframes = test_compare_player_shots_dataframe()
        heatmap_result = test_compare_player_shots_heatmap()
        zones_result = test_compare_player_shots_zones()
        filters_result = test_compare_player_shots_with_filters()

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

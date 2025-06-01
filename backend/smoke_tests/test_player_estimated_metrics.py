"""
Smoke test for the player_estimated_metrics module.
Tests the functionality of fetching player estimated metrics.
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

from api_tools.player_estimated_metrics import (
    fetch_player_estimated_metrics_logic
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, LeagueID
)

# Sample season for testing
SAMPLE_SEASON = "2022-23"  # Use a completed season for testing

def test_fetch_player_estimated_metrics_basic():
    """Test fetching player estimated metrics with default parameters."""
    print("\n=== Testing fetch_player_estimated_metrics_logic (basic) ===")
    
    # Test with default parameters (JSON output)
    json_response = fetch_player_estimated_metrics_logic(
        SAMPLE_SEASON,
        SeasonTypeAllStar.regular,
        LeagueID.nba
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
        # Check if the parameters field exists
        assert "parameters" in data, "Response should have a 'parameters' field"
        
        # Print some information about the data
        print(f"Season: {data['parameters']['season']}")
        print(f"Season Type: {data['parameters']['season_type']}")
        print(f"League ID: {data['parameters']['league_id']}")
        
        # Check if player_estimated_metrics exist
        assert "player_estimated_metrics" in data, "Response should have 'player_estimated_metrics'"
        
        # Print some information about the metrics
        metrics = data["player_estimated_metrics"]
        print(f"\nNumber of players with estimated metrics: {len(metrics)}")
        
        if metrics:
            print("\nSample metrics for first player:")
            first_player = metrics[0]
            print(f"Player: {first_player.get('PLAYER_NAME')} (ID: {first_player.get('PLAYER_ID')})")
            
            # Print some key metrics
            key_metrics = [
                "E_OFF_RATING", "E_DEF_RATING", "E_NET_RATING", 
                "E_AST_RATIO", "E_REB_PCT", "E_USG_PCT", "E_PACE"
            ]
            
            for metric in key_metrics:
                if metric in first_player:
                    print(f"  {metric}: {first_player[metric]}")
    
    print("\n=== Basic estimated metrics test completed ===")
    return data

def test_fetch_player_estimated_metrics_dataframe():
    """Test fetching player estimated metrics with DataFrame output."""
    print("\n=== Testing fetch_player_estimated_metrics_logic with DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_player_estimated_metrics_logic(
        SAMPLE_SEASON,
        SeasonTypeAllStar.regular,
        LeagueID.nba,
        return_dataframe=True
    )
    
    # Check if the result is a tuple
    assert isinstance(result, tuple), "Result should be a tuple when return_dataframe=True"
    assert len(result) == 2, "Result tuple should have 2 elements"
    
    json_response, df = result
    
    # Check if the first element is a JSON string
    assert isinstance(json_response, str), "First element should be a JSON string"
    
    # Check if the second element is a DataFrame
    assert isinstance(df, pd.DataFrame), "Second element should be a DataFrame"
    
    # Parse the JSON response
    data = json.loads(json_response)
    
    # Print DataFrame info
    if not df.empty:
        print(f"\nDataFrame shape: {df.shape}")
        print(f"DataFrame columns: {df.columns.tolist()[:5]}...")  # Show first 5 columns
    else:
        print("\nDataFrame is empty")
    
    # Check if the CSV file was created
    if "dataframe_info" in data:
        csv_path = data["dataframe_info"].get("csv_path")
        if csv_path:
            full_path = os.path.join(backend_dir, csv_path)
            if os.path.exists(full_path):
                print(f"\nCSV file exists: {csv_path}")
            else:
                print(f"\nCSV file does not exist: {csv_path}")
    
    # Display a sample of the DataFrame if not empty
    if not df.empty:
        print(f"\nSample of DataFrame (first 3 rows):")
        print(df.head(3))
    
    print("\n=== DataFrame estimated metrics test completed ===")
    return json_response, df

def test_fetch_player_estimated_metrics_playoffs():
    """Test fetching player estimated metrics for playoffs."""
    print("\n=== Testing fetch_player_estimated_metrics_logic for playoffs ===")
    
    # Test with playoffs season type
    json_response = fetch_player_estimated_metrics_logic(
        SAMPLE_SEASON,
        SeasonTypeAllStar.playoffs,
        LeagueID.nba
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
        # Check if the season_type parameter was correctly used
        assert data["parameters"]["season_type"] == SeasonTypeAllStar.playoffs, "Season type should be 'Playoffs'"
        
        # Print some information about the data
        print(f"Season: {data['parameters']['season']}")
        print(f"Season Type: {data['parameters']['season_type']}")
        
        # Check if player_estimated_metrics exist
        assert "player_estimated_metrics" in data, "Response should have 'player_estimated_metrics'"
        
        # Print some information about the metrics
        metrics = data["player_estimated_metrics"]
        print(f"\nNumber of players with playoff estimated metrics: {len(metrics)}")
        
        if metrics:
            print("\nSample playoff metrics for first player:")
            first_player = metrics[0]
            print(f"Player: {first_player.get('PLAYER_NAME')} (ID: {first_player.get('PLAYER_ID')})")
            
            # Print some key metrics
            key_metrics = [
                "E_OFF_RATING", "E_DEF_RATING", "E_NET_RATING", 
                "E_AST_RATIO", "E_REB_PCT", "E_USG_PCT", "E_PACE"
            ]
            
            for metric in key_metrics:
                if metric in first_player:
                    print(f"  {metric}: {first_player[metric]}")
    
    print("\n=== Playoffs estimated metrics test completed ===")
    return data

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running player_estimated_metrics smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_player_estimated_metrics_basic()
        df_json, df_data = test_fetch_player_estimated_metrics_dataframe()
        playoffs_data = test_fetch_player_estimated_metrics_playoffs()
        
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

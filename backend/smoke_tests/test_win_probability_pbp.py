"""
Smoke test for the win_probability_pbp module.
Tests the functionality of fetching win probability play-by-play data for NBA games.
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

from api_tools.win_probability_pbp import (
    fetch_win_probability_pbp_logic,
    _get_csv_path_for_win_probability_pbp,
    WIN_PROBABILITY_PBP_CSV_DIR
)
from nba_api.stats.library.parameters import RunType

# Sample game ID for testing (2023-24 regular season game)
SAMPLE_GAME_ID = "0022300061"  # Lakers vs Nuggets game from the documentation
SAMPLE_GAME_ID_2 = "0022300001"  # Alternative game ID for testing
DEFAULT_RUN_TYPE = RunType.default

def _verify_csv_exists(expected_path: str):
    """Verify that a CSV file exists at the expected path."""
    assert os.path.exists(expected_path), f"CSV file not found at {expected_path}"
    print(f"Verified CSV file exists: {expected_path}")

def test_fetch_win_probability_pbp_basic():
    """Test fetching win probability PBP with basic parameters."""
    print(f"\n=== Testing fetch_win_probability_pbp_logic for game {SAMPLE_GAME_ID} ===")

    # Test JSON output with default parameters
    json_response_only = fetch_win_probability_pbp_logic(
        SAMPLE_GAME_ID,
        run_type=DEFAULT_RUN_TYPE
    )
    data_only = json.loads(json_response_only)
    assert isinstance(data_only, dict), "JSON only response should be a dictionary"
    
    if "error" in data_only:
        print(f"API (JSON only) returned an error: {data_only['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
    else:
        assert "game_id" in data_only
        assert data_only["game_id"] == SAMPLE_GAME_ID
        assert "run_type" in data_only
        assert data_only["run_type"] == DEFAULT_RUN_TYPE
        print(f"Win probability PBP (JSON only) fetched for game {data_only.get('game_id')}")
        print(f"Data sets available: {data_only.get('data_sets', [])}")
        print(f"Total records: {data_only.get('total_records', 0)}")
        
        # Check if we have win probability data
        if "win_prob_pbp" in data_only:
            win_prob_data = data_only["win_prob_pbp"]
            if win_prob_data:
                print(f"Number of win probability events: {len(win_prob_data)}")
                # Show first few events
                print("\nFirst 3 win probability events:")
                for i, event in enumerate(win_prob_data[:3]):
                    print(f"  Event {i+1}: Home {event.get('HOME_PCT', 'N/A')}%, "
                          f"Visitor {event.get('VISITOR_PCT', 'N/A')}%, "
                          f"Period {event.get('PERIOD', 'N/A')}, "
                          f"Time {event.get('SECONDS_REMAINING', 'N/A')}s")

    print("\n=== Basic test completed ===")
    return data_only

def test_fetch_win_probability_pbp_all_run_types():
    """Test fetching win probability PBP with different run types."""
    print(f"\n=== Testing different run types ===")
    
    # Get all available run types
    run_types = []
    for attr in dir(RunType):
        if not attr.startswith('_'):
            value = getattr(RunType, attr)
            if isinstance(value, str):
                run_types.append(value)
    
    print(f"Available run types: {run_types}")
    
    results = {}
    
    for run_type in run_types:
        print(f"\nTesting with run_type: {run_type}")
        json_response = fetch_win_probability_pbp_logic(
            SAMPLE_GAME_ID,
            run_type=run_type
        )
        data = json.loads(json_response)
        
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            results[run_type] = "error"
        else:
            total_records = data.get("total_records", 0)
            print(f"Total records: {total_records}")
            results[run_type] = total_records
    
    print(f"\nRun type results: {results}")
    print("\n=== Run type tests completed ===")
    return results

def test_fetch_win_probability_pbp_dataframe():
    """Test fetching win probability PBP with DataFrame output."""
    print(f"\n=== Testing DataFrame output ===")
    
    # Test with return_dataframe=True
    result = fetch_win_probability_pbp_logic(
        SAMPLE_GAME_ID,
        run_type=DEFAULT_RUN_TYPE,
        return_dataframe=True
    )
    
    assert isinstance(result, tuple), "Result should be a tuple when return_dataframe=True"
    assert len(result) == 2, "Result tuple should have 2 elements"
    
    json_response, dataframes = result
    
    # Check if the first element is a JSON string
    assert isinstance(json_response, str), "First element should be a JSON string"
    
    # Check if the second element is a dictionary of DataFrames
    assert isinstance(dataframes, dict), "Second element should be a dictionary of DataFrames"
    
    data = json.loads(json_response)
    
    if "error" in data:
        print(f"API returned an error: {data['error']}")
    else:
        print(f"DataFrames returned: {list(dataframes.keys())}")
        
        expected_dfs = ["win_prob_pbp", "game_info"]
        for key in expected_dfs:
            if key in dataframes:
                df = dataframes[key]
                print(f"\nDataFrame '{key}' shape: {df.shape}")
                print(f"DataFrame '{key}' columns: {df.columns.tolist()}")
                
                if not df.empty:
                    print(f"Sample data from '{key}':")
                    print(df.head(3))
                    
                    # Verify CSV was created for main DataFrame
                    if key == "win_prob_pbp":
                        csv_path = _get_csv_path_for_win_probability_pbp(
                            SAMPLE_GAME_ID, DEFAULT_RUN_TYPE
                        )
                        _verify_csv_exists(csv_path)
                else:
                    print(f"DataFrame '{key}' is empty.")
    
    print("\n=== DataFrame test completed ===")
    return json_response, dataframes

def test_fetch_win_probability_pbp_different_games():
    """Test fetching win probability PBP for different games."""
    print(f"\n=== Testing different games ===")
    
    game_ids = [SAMPLE_GAME_ID, SAMPLE_GAME_ID_2]
    results = {}
    
    for game_id in game_ids:
        print(f"\nTesting with game_id: {game_id}")
        json_response = fetch_win_probability_pbp_logic(
            game_id,
            run_type=DEFAULT_RUN_TYPE
        )
        data = json.loads(json_response)
        
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            results[game_id] = "error"
        else:
            total_records = data.get("total_records", 0)
            print(f"Total records: {total_records}")
            results[game_id] = total_records
            
            # Show game info if available
            if "game_info" in data and data["game_info"]:
                game_info = data["game_info"][0] if data["game_info"] else {}
                print(f"Game: {game_info.get('VISITOR_TEAM_ABR', 'N/A')} @ "
                      f"{game_info.get('HOME_TEAM_ABR', 'N/A')} on "
                      f"{game_info.get('GAME_DATE', 'N/A')}")
    
    print(f"\nGame results: {results}")
    print("\n=== Different games tests completed ===")
    return results

def test_fetch_win_probability_pbp_with_run_type_and_dataframe():
    """Test fetching win probability PBP with specific run type and DataFrame output."""
    print(f"\n=== Testing specific run type with DataFrame output ===")
    
    # Try different run types if available
    test_run_types = []
    for attr in dir(RunType):
        if not attr.startswith('_'):
            value = getattr(RunType, attr)
            if isinstance(value, str):
                test_run_types.append(value)
                if len(test_run_types) >= 2:  # Test first 2 available
                    break
    
    for run_type in test_run_types:
        print(f"\nTesting run_type: {run_type} with DataFrame output")
        
        result = fetch_win_probability_pbp_logic(
            SAMPLE_GAME_ID,
            run_type=run_type,
            return_dataframe=True
        )
        
        json_response, dataframes = result
        data = json.loads(json_response)
        
        if "error" in data:
            print(f"API returned an error: {data['error']}")
        else:
            print(f"Run type in response: {data.get('run_type')}")
            
            # Print DataFrame info
            for key, df in dataframes.items():
                if not df.empty:
                    print(f"DataFrame '{key}' with run_type='{run_type}' shape: {df.shape}")
                    
                    # Show sample data for win probability
                    if key == "win_prob_pbp" and len(df) > 0:
                        print("\nSample win probability data:")
                        sample_cols = ['GAME_ID', 'EVENT_NUM', 'HOME_PCT', 'VISITOR_PCT', 'PERIOD', 'SECONDS_REMAINING']
                        available_cols = [col for col in sample_cols if col in df.columns]
                        if available_cols:
                            print(df[available_cols].head(3))
    
    print("\n=== Run type with DataFrame test completed ===")

def test_fetch_win_probability_pbp_invalid_params():
    """Test fetching win probability PBP with invalid parameters."""
    print(f"\n=== Testing invalid parameters ===")
    
    # Test with invalid game ID
    json_response = fetch_win_probability_pbp_logic("")
    data = json.loads(json_response)
    assert "error" in data, "Should return error for empty game ID"
    print(f"Empty game ID test passed: {data['error']}")
    
    # Test with invalid run type (this might not fail if the API accepts any string)
    json_response = fetch_win_probability_pbp_logic(
        SAMPLE_GAME_ID, run_type="invalid_run_type"
    )
    data = json.loads(json_response)
    if "error" in data:
        print(f"Invalid run type test passed: {data['error']}")
    else:
        print("Invalid run type was accepted by API (this might be expected)")
    
    print("\n=== Invalid parameters tests completed ===")

def test_fetch_win_probability_pbp_data_analysis():
    """Test analyzing the structure and content of win probability data."""
    print(f"\n=== Testing data analysis ===")
    
    result = fetch_win_probability_pbp_logic(
        SAMPLE_GAME_ID,
        return_dataframe=True
    )
    
    json_response, dataframes = result
    data = json.loads(json_response)
    
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        return
    
    # Analyze win probability data
    if "win_prob_pbp" in dataframes:
        df = dataframes["win_prob_pbp"]
        if not df.empty:
            print(f"Win probability data analysis:")
            print(f"  Total events: {len(df)}")
            print(f"  Columns: {df.columns.tolist()}")
            
            # Check for key columns
            key_columns = ['HOME_PCT', 'VISITOR_PCT', 'PERIOD', 'SECONDS_REMAINING']
            available_key_cols = [col for col in key_columns if col in df.columns]
            print(f"  Key columns available: {available_key_cols}")
            
            if available_key_cols:
                # Show statistics
                for col in ['HOME_PCT', 'VISITOR_PCT']:
                    if col in df.columns:
                        print(f"  {col} range: {df[col].min():.3f} - {df[col].max():.3f}")
                
                if 'PERIOD' in df.columns:
                    print(f"  Periods covered: {sorted(df['PERIOD'].unique())}")
    
    # Analyze game info data
    if "game_info" in dataframes:
        df = dataframes["game_info"]
        if not df.empty:
            print(f"\nGame info analysis:")
            print(f"  Columns: {df.columns.tolist()}")
            if len(df) > 0:
                game_row = df.iloc[0]
                print(f"  Game: {game_row.get('VISITOR_TEAM_ABR', 'N/A')} @ {game_row.get('HOME_TEAM_ABR', 'N/A')}")
                print(f"  Date: {game_row.get('GAME_DATE', 'N/A')}")
                print(f"  Final Score: {game_row.get('VISITOR_TEAM_PTS', 'N/A')} - {game_row.get('HOME_TEAM_PTS', 'N/A')}")
    
    print("\n=== Data analysis completed ===")

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running win_probability_pbp smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        basic_data = test_fetch_win_probability_pbp_basic()
        run_type_results = test_fetch_win_probability_pbp_all_run_types()
        json_response, dataframes = test_fetch_win_probability_pbp_dataframe()
        game_results = test_fetch_win_probability_pbp_different_games()
        test_fetch_win_probability_pbp_with_run_type_and_dataframe()
        test_fetch_win_probability_pbp_invalid_params()
        test_fetch_win_probability_pbp_data_analysis()
        
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
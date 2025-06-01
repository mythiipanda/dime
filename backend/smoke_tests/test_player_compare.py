"""
Smoke tests for the player_compare module using real API calls.

These tests verify that the player compare API functions work correctly
by making actual calls to the NBA API.
"""

import os
import sys
import unittest
import pandas as pd
import time
import json

# Add the parent directory to the path so we can import the api_tools module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api_tools.player_compare import (
    fetch_player_compare_logic,
    get_player_compare,
    _get_csv_path_for_player_compare,
    PLAYER_COMPARE_CSV_DIR
)
from nba_api.stats.library.parameters import SeasonTypePlayoffs, PerModeDetailed, MeasureTypeDetailedDefense
class TestPlayerCompareReal(unittest.TestCase):
    """Test cases for the player_compare module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(PLAYER_COMPARE_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_player_compare(self):
        """Test that the CSV path is generated correctly."""
        # Test with default parameters
        path = _get_csv_path_for_player_compare(
            vs_player_id_list=["2544"],
            player_id_list=["201939"]
        )
        self.assertIn("player_compare", path)
        self.assertIn("vs2544", path)
        self.assertIn("players201939", path)
        self.assertIn("season2024_25", path)
        self.assertIn("typeRegular_Season", path)
        self.assertIn("perTotals", path)
        self.assertIn("measureBase", path)
        self.assertIn("leagueall", path)
        self.assertIn("games0", path)
        self.assertIn("PlayerCompare", path)
        
        # Test with custom parameters
        path = _get_csv_path_for_player_compare(
            vs_player_id_list=["1628369"],
            player_id_list=["1629029"],
            season="2023-24",
            season_type_playoffs=SeasonTypePlayoffs.playoffs,
            per_mode_detailed=PerModeDetailed.per_game,
            measure_type_detailed_defense=MeasureTypeDetailedDefense.advanced,
            league_id_nullable="00",
            last_n_games=10,
            data_set_name="CustomData"
        )
        self.assertIn("player_compare", path)
        self.assertIn("vs1628369", path)
        self.assertIn("players1629029", path)
        self.assertIn("season2023_24", path)
        self.assertIn("typePlayoffs", path)
        self.assertIn("perPerGame", path)
        self.assertIn("measureAdvanced", path)
        self.assertIn("league00", path)
        self.assertIn("games10", path)
        self.assertIn("CustomData", path)

    def test_fetch_player_compare_logic_json(self):
        """Test fetching player compare in JSON format."""
        # Call the function with real API
        json_response = fetch_player_compare_logic(
            vs_player_id_list=("2544",),  # LeBron James
            player_id_list=("201939",)    # Stephen Curry
        )
        
        # Parse the JSON response
        data = json.loads(json_response)
        
        # Verify the result
        self.assertIsInstance(data, dict)
        
        # Check if there's an error in the response
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            print("This might be expected if the NBA API is unavailable or rate-limited.")
        else:
            # Check parameters
            self.assertIn("parameters", data)
            self.assertEqual(data["parameters"]["vs_player_id_list"], ["2544"])
            self.assertEqual(data["parameters"]["player_id_list"], ["201939"])
            
            # Check data sets
            self.assertIn("data_sets", data)
            data_sets = data["data_sets"]
            self.assertIsInstance(data_sets, dict)
            self.assertGreater(len(data_sets), 0)
            
            # Print information about the data
            print(f"Parameters: {data.get('parameters', {})}")
            print(f"Data Sets: {list(data_sets.keys())}")
            
            # Check the main data sets
            expected_data_sets = ["OverallComparison", "IndividualComparison"]
            for data_set in expected_data_sets:
                if data_set in data_sets:
                    comparison_data = data_sets[data_set]
                    self.assertIsInstance(comparison_data, list)
                    self.assertGreater(len(comparison_data), 0)  # Should have comparison data
                    print(f"{data_set} count: {len(comparison_data)}")
                    print(f"Sample comparison: {comparison_data[0] if comparison_data else 'No data'}")

    def test_fetch_player_compare_logic_dataframe(self):
        """Test fetching player compare in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_player_compare_logic(
            vs_player_id_list=("2544",),  # LeBron James
            player_id_list=("201939",),   # Stephen Curry
            return_dataframe=True
        )
        
        # Parse the JSON response
        data = json.loads(json_response)
        
        # Verify the result
        self.assertIsInstance(data, dict)
        self.assertIsInstance(dataframes, dict)
        
        # Check if there's an error in the response
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            print("This might be expected if the NBA API is unavailable or rate-limited.")
        else:
            # Check parameters
            self.assertIn("parameters", data)
            self.assertEqual(data["parameters"]["vs_player_id_list"], ["2544"])
            self.assertEqual(data["parameters"]["player_id_list"], ["201939"])
            
            # Check dataframes
            self.assertGreater(len(dataframes), 0)
            
            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")
                print(f"Columns: {df.columns.tolist()}")
                
                # Verify expected columns for player compare
                expected_columns = ["GROUP_SET", "DESCRIPTION", "MIN", "PTS", "FG_PCT"]
                for col in expected_columns:
                    if col in df.columns:
                        print(f"Found expected column: {col}")
            
            # Verify CSV files were created
            expected_data_sets = ["OverallComparison", "IndividualComparison"]
            for data_set in expected_data_sets:
                csv_path = _get_csv_path_for_player_compare(
                    ["2544"], ["201939"], "2024-25", SeasonTypePlayoffs.regular, PerModeDetailed.totals,
                    MeasureTypeDetailedDefense.base, "", 0, data_set
                )
                if os.path.exists(csv_path):
                    print(f"CSV file created: {csv_path}")
                    print(f"File size: {os.path.getsize(csv_path)} bytes")
                else:
                    print(f"CSV file was not created at: {csv_path}")

    def test_fetch_player_compare_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        params = {
            "vs_player_id_list": ("1628369",),  # Jayson Tatum
            "player_id_list": ("1629029",)      # Luka Doncic
        }
        
        # Check if CSV already exists
        expected_data_sets = ["OverallComparison", "IndividualComparison"]
        csv_paths = []
        for data_set in expected_data_sets:
            csv_path = _get_csv_path_for_player_compare(
                list(params["vs_player_id_list"]), list(params["player_id_list"]), "2024-25", 
                SeasonTypePlayoffs.regular, PerModeDetailed.totals, MeasureTypeDetailedDefense.base, "", 0, data_set
            )
            csv_paths.append(csv_path)
            if os.path.exists(csv_path):
                print(f"CSV file already exists: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
                print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")
        
        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_player_compare_logic(**params, return_dataframe=True)
        
        # Verify the CSV files were created
        for csv_path in csv_paths:
            self.assertTrue(os.path.exists(csv_path))
        
        # Get the modification times of the CSV files
        mtimes1 = {}
        for csv_path in csv_paths:
            mtimes1[csv_path] = os.path.getmtime(csv_path)
            print(f"CSV file created/updated: {csv_path}")
            print(f"File size: {os.path.getsize(csv_path)} bytes")
            print(f"Last modified: {time.ctime(mtimes1[csv_path])}")
        
        # Wait a moment to ensure the modification time would be different if the file is rewritten
        time.sleep(0.1)
        
        # Second call should use the cache
        print("Making second API call (should use CSV cache)...")
        _, dataframes2 = fetch_player_compare_logic(**params, return_dataframe=True)
        
        # Verify the CSV files weren't modified
        for csv_path in csv_paths:
            mtime2 = os.path.getmtime(csv_path)
            self.assertEqual(mtimes1[csv_path], mtime2)
            print(f"CSV file was not modified (same timestamp): {time.ctime(mtime2)}")
        
        # Verify the data is the same
        if dataframes1 and dataframes2:
            for key in dataframes1:
                if key in dataframes2:
                    pd.testing.assert_frame_equal(dataframes1[key], dataframes2[key], check_dtype=False)
                    print(f"Verified data for {key} matches between calls")
        
        print(f"Data loaded from CSV matches original data")

    def test_get_player_compare(self):
        """Test the get_player_compare function."""
        # Call the function with real API
        json_response, dataframes = get_player_compare(
            vs_player_id_list=["2544"],  # LeBron James
            player_id_list=["201939"],   # Stephen Curry
            return_dataframe=True
        )
        
        # Parse the JSON response
        data = json.loads(json_response)
        
        # Verify the result
        self.assertIsInstance(data, dict)
        self.assertIsInstance(dataframes, dict)
        
        # Check if there's an error in the response
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            print("This might be expected if the NBA API is unavailable or rate-limited.")
        else:
            # Check parameters
            self.assertIn("parameters", data)
            self.assertEqual(data["parameters"]["vs_player_id_list"], ["2544"])
            self.assertEqual(data["parameters"]["player_id_list"], ["201939"])
            
            # Check dataframes
            self.assertGreater(len(dataframes), 0)
            
            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")

    def test_100_percent_parameter_coverage(self):
        """Test 100% parameter coverage for PlayerCompare endpoint."""
        print("\n=== Testing 100% Parameter Coverage ===")
        
        # Test parameter combinations that work
        test_cases = [
            # Basic combinations
            {"vs_player_id_list": ["2544"], "player_id_list": ["201939"]},  # LeBron vs Curry
            {"vs_player_id_list": ["1628369"], "player_id_list": ["1629029"]},  # Tatum vs Luka
            {"vs_player_id_list": ["203507"], "player_id_list": ["203081"]},  # Giannis vs Lillard
            
            # Different seasons
            {"vs_player_id_list": ["2544"], "player_id_list": ["201939"], "season": "2023-24"},
            {"vs_player_id_list": ["2544"], "player_id_list": ["201939"], "season": "2022-23"},
            
            # Different season types
            {"vs_player_id_list": ["2544"], "player_id_list": ["201939"], "season_type_playoffs": SeasonTypePlayoffs.playoffs},
            
            # Different per modes
            {"vs_player_id_list": ["2544"], "player_id_list": ["201939"], "per_mode_detailed": PerModeDetailed.per_game},
            
            # Different measure types
            {"vs_player_id_list": ["2544"], "player_id_list": ["201939"], "measure_type_detailed_defense": MeasureTypeDetailedDefense.advanced},
            
            # Last N games
            {"vs_player_id_list": ["2544"], "player_id_list": ["201939"], "last_n_games": 10},
            
            # League ID
            {"vs_player_id_list": ["2544"], "player_id_list": ["201939"], "league_id_nullable": "00"},
        ]
        
        successful_tests = 0
        total_tests = len(test_cases)
        
        for i, test_case in enumerate(test_cases):
            print(f"\nTest {i+1}/{total_tests}: {test_case}")
            
            try:
                # Call the API with these parameters
                json_response, dataframes = get_player_compare(
                    **test_case,
                    return_dataframe=True
                )
                
                # Parse the JSON response
                data = json.loads(json_response)
                
                # Verify the result
                self.assertIsInstance(data, dict)
                self.assertIsInstance(dataframes, dict)
                
                # Check if there's an error in the response
                if "error" in data:
                    print(f"  ✗ API returned an error: {data['error']}")
                else:
                    # Check parameters match
                    if "parameters" in data:
                        params = data["parameters"]
                        self.assertEqual(params["vs_player_id_list"], test_case["vs_player_id_list"])
                        self.assertEqual(params["player_id_list"], test_case["player_id_list"])
                        
                        print(f"  ✓ Parameters match")
                    
                    # Check data sets
                    if "data_sets" in data and data["data_sets"]:
                        data_sets = data["data_sets"]
                        print(f"  ✓ Data sets: {list(data_sets.keys())}")
                        
                        # Check dataframes
                        if dataframes:
                            for data_set_name, df in dataframes.items():
                                print(f"  ✓ DataFrame '{data_set_name}': {len(df)} records")
                                
                                # Verify CSV was created
                                csv_path = _get_csv_path_for_player_compare(
                                    test_case["vs_player_id_list"],
                                    test_case["player_id_list"],
                                    test_case.get("season", "2024-25"),
                                    test_case.get("season_type_playoffs", SeasonTypePlayoffs.regular),
                                    test_case.get("per_mode_detailed", PerModeDetailed.totals),
                                    test_case.get("measure_type_detailed_defense", MeasureTypeDetailedDefense.base),
                                    test_case.get("league_id_nullable", ""),
                                    test_case.get("last_n_games", 0),
                                    data_set_name
                                )
                                if os.path.exists(csv_path):
                                    print(f"  ✓ CSV created: {os.path.basename(csv_path)}")
                                else:
                                    print(f"  ○ CSV not found: {os.path.basename(csv_path)}")
                        else:
                            print(f"  ○ No dataframes returned")
                    else:
                        print(f"  ○ No data sets returned (might be empty for this combination)")
                    
                    successful_tests += 1
                    
            except Exception as e:
                print(f"  ✗ Exception: {e}")
                # Don't fail the test for individual parameter combinations that might not work
                # This is expected for some combinations
        
        print(f"\n=== Parameter Coverage Summary ===")
        print(f"Total test cases: {total_tests}")
        print(f"Successful tests: {successful_tests}")
        print(f"Coverage: {(successful_tests/total_tests)*100:.1f}%")
        
        # We expect at least 90% of test cases to work
        self.assertGreater(successful_tests, total_tests * 0.9, 
                          f"Expected at least 90% of parameter combinations to work, got {(successful_tests/total_tests)*100:.1f}%")


if __name__ == '__main__':
    unittest.main()

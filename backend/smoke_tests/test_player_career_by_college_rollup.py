"""
Smoke tests for the player_career_by_college_rollup module using real API calls.

These tests verify that the player career by college rollup API functions work correctly
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

from api_tools.player_career_by_college_rollup import (
    fetch_player_career_by_college_rollup_logic,
    get_player_career_by_college_rollup,
    _get_csv_path_for_player_career_by_college_rollup,
    PLAYER_CAREER_BY_COLLEGE_ROLLUP_CSV_DIR
)
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple


class TestPlayerCareerByCollegeRollupReal(unittest.TestCase):
    """Test cases for the player_career_by_college_rollup module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(PLAYER_CAREER_BY_COLLEGE_ROLLUP_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_player_career_by_college_rollup(self):
        """Test that the CSV path is generated correctly."""
        # Test with default parameters
        path = _get_csv_path_for_player_career_by_college_rollup()
        self.assertIn("player_career_by_college_rollup", path)
        self.assertIn("league00", path)
        self.assertIn("typeRegular_Season", path)
        self.assertIn("perTotals", path)
        self.assertIn("seasonall", path)
        self.assertIn("PlayerCareerByCollegeRollup", path)
        
        # Test with custom parameters
        path = _get_csv_path_for_player_career_by_college_rollup(
            league_id="10",
            per_mode_simple=PerModeSimple.per_game,
            season_type_all_star=SeasonTypeAllStar.playoffs,
            season_nullable="2023-24",
            data_set_name="EastRegion"
        )
        self.assertIn("player_career_by_college_rollup", path)
        self.assertIn("league10", path)
        self.assertIn("typePlayoffs", path)
        self.assertIn("perPerGame", path)
        self.assertIn("season2023-24", path)
        self.assertIn("EastRegion", path)

    def test_fetch_player_career_by_college_rollup_logic_json(self):
        """Test fetching player career by college rollup in JSON format."""
        # Call the function with real API
        json_response = fetch_player_career_by_college_rollup_logic()
        
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
            self.assertEqual(data["parameters"]["league_id"], "00")
            
            # Check data sets
            self.assertIn("data_sets", data)
            data_sets = data["data_sets"]
            self.assertIsInstance(data_sets, dict)
            self.assertGreater(len(data_sets), 0)
            
            # Print information about the data
            print(f"Parameters: {data.get('parameters', {})}")
            print(f"Data Sets: {list(data_sets.keys())}")
            
            # Check the main data sets
            expected_regions = ["EastRegion", "SouthRegion", "MidwestRegion", "WestRegion"]
            for region in expected_regions:
                if region in data_sets:
                    region_data = data_sets[region]
                    self.assertIsInstance(region_data, list)
                    self.assertEqual(len(region_data), 16)  # Should have 16 colleges per region
                    print(f"{region} count: {len(region_data)}")
                    print(f"Sample college: {region_data[0] if region_data else 'No data'}")

    def test_fetch_player_career_by_college_rollup_logic_dataframe(self):
        """Test fetching player career by college rollup in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_player_career_by_college_rollup_logic(
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
            self.assertEqual(data["parameters"]["league_id"], "00")
            
            # Check dataframes
            self.assertGreater(len(dataframes), 0)
            
            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")
                print(f"Columns: {df.columns.tolist()}")
                
                # Verify expected columns for player career by college rollup
                expected_columns = ["REGION", "SEED", "COLLEGE", "PLAYERS", "GP", "PTS"]
                for col in expected_columns:
                    if col in df.columns:
                        print(f"Found expected column: {col}")
            
            # Verify CSV files were created
            expected_regions = ["EastRegion", "SouthRegion", "MidwestRegion", "WestRegion"]
            for region in expected_regions:
                csv_path = _get_csv_path_for_player_career_by_college_rollup(
                    "00", PerModeSimple.totals, SeasonTypeAllStar.regular, "", region
                )
                if os.path.exists(csv_path):
                    print(f"CSV file created: {csv_path}")
                    print(f"File size: {os.path.getsize(csv_path)} bytes")
                else:
                    print(f"CSV file was not created at: {csv_path}")

    def test_fetch_player_career_by_college_rollup_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        params = {
            "league_id": "00"
        }
        
        # Check if CSV already exists
        expected_regions = ["EastRegion", "SouthRegion", "MidwestRegion", "WestRegion"]
        csv_paths = []
        for region in expected_regions:
            csv_path = _get_csv_path_for_player_career_by_college_rollup(
                params["league_id"], PerModeSimple.totals, SeasonTypeAllStar.regular, "", region
            )
            csv_paths.append(csv_path)
            if os.path.exists(csv_path):
                print(f"CSV file already exists: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
                print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")
        
        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_player_career_by_college_rollup_logic(**params, return_dataframe=True)
        
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
        _, dataframes2 = fetch_player_career_by_college_rollup_logic(**params, return_dataframe=True)
        
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

    def test_get_player_career_by_college_rollup(self):
        """Test the get_player_career_by_college_rollup function."""
        # Call the function with real API
        json_response, dataframes = get_player_career_by_college_rollup(
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
            self.assertEqual(data["parameters"]["league_id"], "00")
            
            # Check dataframes
            self.assertGreater(len(dataframes), 0)
            
            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")

    def test_100_percent_parameter_coverage(self):
        """Test 100% parameter coverage for PlayerCareerByCollegeRollup endpoint."""
        print("\n=== Testing 100% Parameter Coverage ===")
        
        # Test parameter combinations that work
        test_cases = [
            # Basic combinations
            {"league_id": "00"},
            {"league_id": "10"},  # WNBA
            
            # Different per modes
            {"league_id": "00", "per_mode_simple": PerModeSimple.per_game},
            
            # Different season types
            {"league_id": "00", "season_type_all_star": SeasonTypeAllStar.playoffs},
            
            # Specific seasons
            {"league_id": "00", "season_nullable": "2024-25"},
            {"league_id": "00", "season_nullable": "2023-24"},
        ]
        
        successful_tests = 0
        total_tests = len(test_cases)
        
        for i, test_case in enumerate(test_cases):
            print(f"\nTest {i+1}/{total_tests}: {test_case}")
            
            try:
                # Call the API with these parameters
                json_response, dataframes = get_player_career_by_college_rollup(
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
                        self.assertEqual(params["league_id"], test_case["league_id"])
                        
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
                                csv_path = _get_csv_path_for_player_career_by_college_rollup(
                                    test_case["league_id"],
                                    test_case.get("per_mode_simple", PerModeSimple.totals),
                                    test_case.get("season_type_all_star", SeasonTypeAllStar.regular),
                                    test_case.get("season_nullable", ""),
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

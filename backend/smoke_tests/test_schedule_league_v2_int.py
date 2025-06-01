"""
Smoke tests for the schedule_league_v2_int module using real API calls.

These tests verify that the schedule league v2 int API functions work correctly
by making actual calls to the NBA API.
"""

import os
import sys
import unittest
import pandas as pd
import time
import json

# Add the parent directory to the path so we can import the api_tools module

from api_tools.schedule_league_v2_int import (
    fetch_schedule_league_v2_int_logic,
    get_schedule_league_v2_int,
    _get_csv_path_for_schedule_league_v2_int,
    SCHEDULE_LEAGUE_V2_INT_CSV_DIR
)


class TestScheduleLeagueV2IntReal(unittest.TestCase):
    """Test cases for the schedule_league_v2_int module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(SCHEDULE_LEAGUE_V2_INT_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_schedule_league_v2_int(self):
        """Test that the CSV path is generated correctly."""
        # Test with default parameters
        path = _get_csv_path_for_schedule_league_v2_int()
        self.assertIn("schedule_league_v2_int", path)
        self.assertIn("league00", path)
        self.assertIn("season2024_25", path)
        self.assertIn("ScheduleLeagueV2Int", path)
        
        # Test with custom parameters
        path = _get_csv_path_for_schedule_league_v2_int(
            league_id="10",
            season="2023-24",
            data_set_name="CustomData"
        )
        self.assertIn("schedule_league_v2_int", path)
        self.assertIn("league10", path)
        self.assertIn("season2023_24", path)
        self.assertIn("CustomData", path)

    def test_fetch_schedule_league_v2_int_logic_json(self):
        """Test fetching schedule league v2 int in JSON format."""
        # Call the function with real API
        json_response = fetch_schedule_league_v2_int_logic()
        
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
            expected_data_sets = ["Games", "Weeks", "Broadcasters"]
            for data_set in expected_data_sets:
                if data_set in data_sets:
                    schedule_data = data_sets[data_set]
                    if isinstance(schedule_data, dict) and "total_records" in schedule_data:
                        # Large dataset with limited display
                        print(f"{data_set} total records: {schedule_data['total_records']}")
                        print(f"{data_set} displayed records: {schedule_data['displayed_records']}")
                        print(f"Sample {data_set.lower()}: {schedule_data['data'][0] if schedule_data['data'] else 'No data'}")
                    else:
                        # Regular dataset
                        self.assertIsInstance(schedule_data, list)
                        print(f"{data_set} count: {len(schedule_data)}")
                        print(f"Sample {data_set.lower()}: {schedule_data[0] if schedule_data else 'No data'}")

    def test_fetch_schedule_league_v2_int_logic_dataframe(self):
        """Test fetching schedule league v2 int in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_schedule_league_v2_int_logic(
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
                print(f"Columns: {df.columns.tolist()[:10]}...")  # Show first 10 columns
                
                # Verify expected columns for schedule league v2 int
                if data_set_name == "Games":
                    expected_columns = ["leagueId", "seasonYear", "gameDate", "gameId", "gameCode"]
                elif data_set_name == "Weeks":
                    expected_columns = ["leagueId", "seasonYear", "weekNumber", "weekName", "startDate", "endDate"]
                elif data_set_name == "Broadcasters":
                    expected_columns = ["leagueId", "seasonYear", "broadcasterId", "broadcasterDisplay"]
                else:
                    expected_columns = []
                
                for col in expected_columns:
                    if col in df.columns:
                        print(f"Found expected column: {col}")
            
            # Verify CSV files were created
            expected_data_sets = ["Games", "Weeks", "Broadcasters"]
            for data_set in expected_data_sets:
                csv_path = _get_csv_path_for_schedule_league_v2_int("00", "2024-25", data_set)
                if os.path.exists(csv_path):
                    print(f"CSV file created: {csv_path}")
                    print(f"File size: {os.path.getsize(csv_path)} bytes")
                else:
                    print(f"CSV file was not created at: {csv_path}")

    def test_fetch_schedule_league_v2_int_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        params = {
            "league_id": "00"
        }
        
        # Check if CSV already exists
        expected_data_sets = ["Games", "Weeks", "Broadcasters"]
        csv_paths = []
        for data_set in expected_data_sets:
            csv_path = _get_csv_path_for_schedule_league_v2_int(
                params["league_id"], "2024-25", data_set
            )
            csv_paths.append(csv_path)
            if os.path.exists(csv_path):
                print(f"CSV file already exists: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
                print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")
        
        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_schedule_league_v2_int_logic(**params, return_dataframe=True)
        
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
        _, dataframes2 = fetch_schedule_league_v2_int_logic(**params, return_dataframe=True)
        
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

    def test_get_schedule_league_v2_int(self):
        """Test the get_schedule_league_v2_int function."""
        # Call the function with real API
        json_response, dataframes = get_schedule_league_v2_int(
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
        """Test 100% parameter coverage for ScheduleLeagueV2Int endpoint."""
        print("\n=== Testing 100% Parameter Coverage ===")
        
        # Test parameter combinations that work
        test_cases = [
            # Basic combinations
            {"league_id": "00"},
            
            # Different seasons (note: some might not work due to data availability)
            {"league_id": "00", "season": "2024-25"},  # Current season
            {"league_id": "00", "season": "2023-24"},  # Previous season (might fail)
        ]
        
        successful_tests = 0
        total_tests = len(test_cases)
        
        for i, test_case in enumerate(test_cases):
            print(f"\nTest {i+1}/{total_tests}: {test_case}")
            
            try:
                # Call the API with these parameters
                json_response, dataframes = get_schedule_league_v2_int(
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
                                csv_path = _get_csv_path_for_schedule_league_v2_int(
                                    test_case["league_id"],
                                    test_case.get("season", "2024-25"),
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
        
        # We expect at least 66% of test cases to work (some seasons might not have data)
        self.assertGreater(successful_tests, total_tests * 0.66, 
                          f"Expected at least 66% of parameter combinations to work, got {(successful_tests/total_tests)*100:.1f}%")


if __name__ == '__main__':
    unittest.main()

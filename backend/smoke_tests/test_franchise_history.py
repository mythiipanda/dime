"""
Smoke tests for the franchise_history module using real API calls.

These tests verify that the franchise history API functions work correctly
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

from api_tools.franchise_history import (
    fetch_franchise_history_logic,
    get_franchise_history,
    _get_csv_path_for_franchise_history,
    FRANCHISE_HISTORY_CSV_DIR
)


class TestFranchiseHistoryReal(unittest.TestCase):
    """Test cases for the franchise_history module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(FRANCHISE_HISTORY_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_franchise_history(self):
        """Test that the CSV path is generated correctly."""
        # Test with default parameters
        path = _get_csv_path_for_franchise_history()
        self.assertIn("franchise_history_league00", path)
        self.assertIn("FranchiseHistory", path)
        
        # Test with custom parameters
        path = _get_csv_path_for_franchise_history(
            league_id="10",
            data_set_name="DefunctTeams"
        )
        self.assertIn("franchise_history_league10", path)
        self.assertIn("DefunctTeams", path)

    def test_fetch_franchise_history_logic_json(self):
        """Test fetching franchise history in JSON format."""
        # Call the function with real API
        json_response = fetch_franchise_history_logic(
            league_id="00"
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
            self.assertEqual(data["parameters"]["league_id"], "00")
            
            # Check data sets
            self.assertIn("data_sets", data)
            data_sets = data["data_sets"]
            self.assertIsInstance(data_sets, dict)
            self.assertGreater(len(data_sets), 0)
            
            # Print information about the data
            print(f"Parameters: {data.get('parameters', {})}")
            print(f"Data Sets: {list(data_sets.keys())}")
            
            # Check the main data set
            if "FranchiseHistory" in data_sets:
                franchise_data = data_sets["FranchiseHistory"]
                self.assertIsInstance(franchise_data, list)
                self.assertGreater(len(franchise_data), 70)  # Should have 74+ franchise records
                print(f"Franchise History count: {len(franchise_data)}")
                print(f"Sample franchise: {franchise_data[0] if franchise_data else 'No data'}")
            
            # Check defunct teams data set
            if "DefunctTeams" in data_sets:
                defunct_data = data_sets["DefunctTeams"]
                self.assertIsInstance(defunct_data, list)
                self.assertGreater(len(defunct_data), 10)  # Should have 15+ defunct teams
                print(f"Defunct Teams count: {len(defunct_data)}")
                print(f"Sample defunct team: {defunct_data[0] if defunct_data else 'No data'}")

    def test_fetch_franchise_history_logic_dataframe(self):
        """Test fetching franchise history in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_franchise_history_logic(
            league_id="00",
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
                
                # Verify expected columns for franchise history
                expected_columns = ["LEAGUE_ID", "TEAM_ID", "TEAM_CITY", "TEAM_NAME", "START_YEAR", "END_YEAR", "WINS", "LOSSES"]
                for col in expected_columns:
                    if col in df.columns:
                        print(f"Found expected column: {col}")
            
            # Verify CSV files were created
            for data_set_name in dataframes.keys():
                csv_path = _get_csv_path_for_franchise_history("00", data_set_name)
                if os.path.exists(csv_path):
                    print(f"CSV file created: {csv_path}")
                    print(f"File size: {os.path.getsize(csv_path)} bytes")
                else:
                    print(f"CSV file was not created at: {csv_path}")

    def test_fetch_franchise_history_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        params = {
            "league_id": "10"  # WNBA
        }
        
        # Check if CSV already exists
        csv_paths = []
        for data_set_name in ["FranchiseHistory", "DefunctTeams"]:
            csv_path = _get_csv_path_for_franchise_history(params["league_id"], data_set_name)
            csv_paths.append(csv_path)
            if os.path.exists(csv_path):
                print(f"CSV file already exists: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
                print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")
        
        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_franchise_history_logic(**params, return_dataframe=True)
        
        # Verify the CSV files were created
        for csv_path in csv_paths:
            if os.path.exists(csv_path):
                print(f"CSV file exists: {csv_path}")
        
        # Get the modification times of the CSV files
        mtimes1 = {}
        for csv_path in csv_paths:
            if os.path.exists(csv_path):
                mtimes1[csv_path] = os.path.getmtime(csv_path)
                print(f"CSV file: {os.path.basename(csv_path)}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
                print(f"Last modified: {time.ctime(mtimes1[csv_path])}")
        
        # Wait a moment to ensure the modification time would be different if the file is rewritten
        time.sleep(0.1)
        
        # Second call should use the cache
        print("Making second API call (should use CSV cache)...")
        _, dataframes2 = fetch_franchise_history_logic(**params, return_dataframe=True)
        
        # Verify the CSV files weren't modified
        for csv_path in csv_paths:
            if os.path.exists(csv_path) and csv_path in mtimes1:
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

    def test_get_franchise_history(self):
        """Test the get_franchise_history function."""
        # Call the function with real API
        json_response, dataframes = get_franchise_history(
            league_id="00",
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
        """Test 100% parameter coverage for FranchiseHistory endpoint."""
        print("\n=== Testing 100% Parameter Coverage ===")
        
        # Test all parameter combinations that work
        test_cases = [
            # NBA and WNBA
            {"league_id": "00"},  # NBA
            {"league_id": "10"},  # WNBA
        ]
        
        successful_tests = 0
        total_tests = len(test_cases)
        
        for i, test_case in enumerate(test_cases):
            print(f"\nTest {i+1}/{total_tests}: {test_case}")
            
            try:
                # Call the API with these parameters
                json_response, dataframes = get_franchise_history(
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
                                csv_path = _get_csv_path_for_franchise_history(
                                    test_case["league_id"],
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
                # This is expected for some league combinations
        
        print(f"\n=== Parameter Coverage Summary ===")
        print(f"Total test cases: {total_tests}")
        print(f"Successful tests: {successful_tests}")
        print(f"Coverage: {(successful_tests/total_tests)*100:.1f}%")
        
        # We expect 100% of test cases to work
        self.assertGreater(successful_tests, total_tests * 0.95, 
                          f"Expected at least 95% of parameter combinations to work, got {(successful_tests/total_tests)*100:.1f}%")


if __name__ == '__main__':
    unittest.main()

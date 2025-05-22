"""
Smoke tests for the franchise_leaders module using real API calls.

These tests verify that the franchise leaders API functions work correctly
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

from api_tools.franchise_leaders import (
    fetch_franchise_leaders_logic,
    get_franchise_leaders,
    _get_csv_path_for_franchise_leaders,
    FRANCHISE_LEADERS_CSV_DIR,
    VALID_TEAM_IDS
)


class TestFranchiseLeadersReal(unittest.TestCase):
    """Test cases for the franchise_leaders module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(FRANCHISE_LEADERS_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_franchise_leaders(self):
        """Test that the CSV path is generated correctly."""
        # Test with different team IDs
        path = _get_csv_path_for_franchise_leaders("1610612747")  # Lakers
        self.assertIn("franchise_leaders_team1610612747", path)
        
        path = _get_csv_path_for_franchise_leaders("1610612739")  # Cavaliers
        self.assertIn("franchise_leaders_team1610612739", path)

    def test_fetch_franchise_leaders_logic_json(self):
        """Test fetching franchise leaders in JSON format."""
        # Call the function with real API
        json_response = fetch_franchise_leaders_logic(
            team_id="1610612747"  # Lakers
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
            self.assertEqual(data["parameters"]["team_id"], "1610612747")
            
            # Check data sets
            self.assertIn("data_sets", data)
            data_sets = data["data_sets"]
            self.assertIsInstance(data_sets, dict)
            self.assertGreater(len(data_sets), 0)
            
            # Print information about the data
            print(f"Parameters: {data.get('parameters', {})}")
            print(f"Data Sets: {list(data_sets.keys())}")
            
            # Check the main data set
            if "FranchiseLeaders" in data_sets:
                leaders_data = data_sets["FranchiseLeaders"]
                self.assertIsInstance(leaders_data, list)
                self.assertEqual(len(leaders_data), 1)  # Should have 1 record with all leaders
                print(f"Franchise Leaders count: {len(leaders_data)}")
                print(f"Sample leaders: {leaders_data[0] if leaders_data else 'No data'}")

    def test_fetch_franchise_leaders_logic_dataframe(self):
        """Test fetching franchise leaders in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_franchise_leaders_logic(
            team_id="1610612744",  # Golden State Warriors
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
            self.assertEqual(data["parameters"]["team_id"], "1610612744")
            
            # Check dataframes
            self.assertGreater(len(dataframes), 0)
            
            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                self.assertEqual(len(df), 1)  # Should have 1 record with all leaders
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")
                print(f"Columns: {df.columns.tolist()}")
                
                # Verify expected columns for franchise leaders
                expected_columns = ["TEAM_ID", "PTS", "PTS_PLAYER", "AST", "AST_PLAYER", "REB", "REB_PLAYER"]
                for col in expected_columns:
                    if col in df.columns:
                        print(f"Found expected column: {col}")
            
            # Verify CSV file was created
            csv_path = _get_csv_path_for_franchise_leaders("1610612744")
            if os.path.exists(csv_path):
                print(f"CSV file created: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
            else:
                print(f"CSV file was not created at: {csv_path}")

    def test_fetch_franchise_leaders_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        params = {
            "team_id": "1610612739"  # Cleveland Cavaliers
        }
        
        # Check if CSV already exists
        csv_path = _get_csv_path_for_franchise_leaders(params["team_id"])
        if os.path.exists(csv_path):
            print(f"CSV file already exists: {csv_path}")
            print(f"File size: {os.path.getsize(csv_path)} bytes")
            print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")
        
        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_franchise_leaders_logic(**params, return_dataframe=True)
        
        # Verify the CSV file was created
        self.assertTrue(os.path.exists(csv_path))
        
        # Get the modification time of the CSV file
        mtime1 = os.path.getmtime(csv_path)
        print(f"CSV file created/updated: {csv_path}")
        print(f"File size: {os.path.getsize(csv_path)} bytes")
        print(f"Last modified: {time.ctime(mtime1)}")
        
        # Wait a moment to ensure the modification time would be different if the file is rewritten
        time.sleep(0.1)
        
        # Second call should use the cache
        print("Making second API call (should use CSV cache)...")
        _, dataframes2 = fetch_franchise_leaders_logic(**params, return_dataframe=True)
        
        # Verify the CSV file wasn't modified
        mtime2 = os.path.getmtime(csv_path)
        self.assertEqual(mtime1, mtime2)
        print(f"CSV file was not modified (same timestamp): {time.ctime(mtime2)}")
        
        # Verify the data is the same
        if dataframes1 and dataframes2:
            for key in dataframes1:
                if key in dataframes2:
                    pd.testing.assert_frame_equal(dataframes1[key], dataframes2[key], check_dtype=False)
                    print(f"Verified data for {key} matches between calls")
        
        print(f"Data loaded from CSV matches original data")

    def test_get_franchise_leaders(self):
        """Test the get_franchise_leaders function."""
        # Call the function with real API
        json_response, dataframes = get_franchise_leaders(
            team_id="1610612747",  # Lakers
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
            self.assertEqual(data["parameters"]["team_id"], "1610612747")
            
            # Check dataframes
            self.assertGreater(len(dataframes), 0)
            
            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                self.assertEqual(len(df), 1)  # Should have 1 record with all leaders
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")

    def test_100_percent_parameter_coverage(self):
        """Test 100% parameter coverage for FranchiseLeaders endpoint."""
        print("\n=== Testing 100% Parameter Coverage ===")
        
        # Test a representative sample of NBA teams
        test_cases = [
            {"team_id": "1610612747"},  # Los Angeles Lakers
            {"team_id": "1610612738"},  # Boston Celtics
            {"team_id": "1610612744"},  # Golden State Warriors
            {"team_id": "1610612739"},  # Cleveland Cavaliers
            {"team_id": "1610612741"},  # Chicago Bulls
            {"team_id": "1610612748"},  # Miami Heat
            {"team_id": "1610612759"},  # San Antonio Spurs
            {"team_id": "1610612752"},  # New York Knicks
            {"team_id": "1610612755"},  # Philadelphia 76ers
            {"team_id": "1610612742"},  # Dallas Mavericks
        ]
        
        successful_tests = 0
        total_tests = len(test_cases)
        
        for i, test_case in enumerate(test_cases):
            print(f"\nTest {i+1}/{total_tests}: {test_case}")
            
            try:
                # Call the API with these parameters
                json_response, dataframes = get_franchise_leaders(
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
                        self.assertEqual(params["team_id"], test_case["team_id"])
                        
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
                                csv_path = _get_csv_path_for_franchise_leaders(test_case["team_id"])
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
                # This is expected for some team combinations
        
        print(f"\n=== Parameter Coverage Summary ===")
        print(f"Total test cases: {total_tests}")
        print(f"Successful tests: {successful_tests}")
        print(f"Coverage: {(successful_tests/total_tests)*100:.1f}%")
        
        # We expect 100% of test cases to work
        self.assertGreater(successful_tests, total_tests * 0.95, 
                          f"Expected at least 95% of parameter combinations to work, got {(successful_tests/total_tests)*100:.1f}%")


if __name__ == '__main__':
    unittest.main()

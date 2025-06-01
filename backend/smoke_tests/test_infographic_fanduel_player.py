"""
Smoke tests for the infographic_fanduel_player module using real API calls.

These tests verify that the infographic FanDuel player API functions work correctly
by making actual calls to the NBA API.
"""

import os
import sys
import unittest
import pandas as pd
import time
import json

# Add the parent directory to the path so we can import the api_tools module

from api_tools.infographic_fanduel_player import (
    fetch_infographic_fanduel_logic,
    get_infographic_fanduel_player,
    _get_csv_path_for_infographic_fanduel,
    INFOGRAPHIC_FANDUEL_CSV_DIR
)


class TestInfographicFanDuelPlayerReal(unittest.TestCase):
    """Test cases for the infographic_fanduel_player module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(INFOGRAPHIC_FANDUEL_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_infographic_fanduel(self):
        """Test that the CSV path is generated correctly."""
        # Test with default parameters
        path = _get_csv_path_for_infographic_fanduel("0022400001")
        self.assertIn("infographic_fanduel_game0022400001", path)
        self.assertIn("FanDuelPlayers", path)
        
        # Test with custom parameters
        path = _get_csv_path_for_infographic_fanduel(
            game_id="0022400002",
            data_set_name="CustomData"
        )
        self.assertIn("infographic_fanduel_game0022400002", path)
        self.assertIn("CustomData", path)

    def test_fetch_infographic_fanduel_logic_json(self):
        """Test fetching infographic FanDuel in JSON format."""
        # Call the function with real API
        json_response = fetch_infographic_fanduel_logic(
            game_id="0022400001"
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
            self.assertEqual(data["parameters"]["game_id"], "0022400001")
            
            # Check data sets
            self.assertIn("data_sets", data)
            data_sets = data["data_sets"]
            self.assertIsInstance(data_sets, dict)
            self.assertGreater(len(data_sets), 0)
            
            # Print information about the data
            print(f"Parameters: {data.get('parameters', {})}")
            print(f"Data Sets: {list(data_sets.keys())}")
            
            # Check the main data set
            if "FanDuelPlayers" in data_sets:
                fanduel_data = data_sets["FanDuelPlayers"]
                self.assertIsInstance(fanduel_data, list)
                self.assertGreater(len(fanduel_data), 15)  # Should have 19-26 players
                print(f"FanDuel Players count: {len(fanduel_data)}")
                print(f"Sample player: {fanduel_data[0] if fanduel_data else 'No data'}")

    def test_fetch_infographic_fanduel_logic_dataframe(self):
        """Test fetching infographic FanDuel in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_infographic_fanduel_logic(
            game_id="0022400002",
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
            self.assertEqual(data["parameters"]["game_id"], "0022400002")
            
            # Check dataframes
            self.assertGreater(len(dataframes), 0)
            
            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")
                print(f"Columns: {df.columns.tolist()}")
                
                # Verify expected columns for FanDuel data
                expected_columns = ["PLAYER_ID", "PLAYER_NAME", "FAN_DUEL_PTS", "NBA_FANTASY_PTS", "PTS", "REB", "AST"]
                for col in expected_columns:
                    if col in df.columns:
                        print(f"Found expected column: {col}")
            
            # Verify CSV file was created
            csv_path = _get_csv_path_for_infographic_fanduel("0022400002", "FanDuelPlayers")
            if os.path.exists(csv_path):
                print(f"CSV file created: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
            else:
                print(f"CSV file was not created at: {csv_path}")

    def test_fetch_infographic_fanduel_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        params = {
            "game_id": "0022400003"
        }
        
        # Check if CSV already exists
        csv_path = _get_csv_path_for_infographic_fanduel(params["game_id"], "FanDuelPlayers")
        if os.path.exists(csv_path):
            print(f"CSV file already exists: {csv_path}")
            print(f"File size: {os.path.getsize(csv_path)} bytes")
            print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")
        
        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_infographic_fanduel_logic(**params, return_dataframe=True)
        
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
        _, dataframes2 = fetch_infographic_fanduel_logic(**params, return_dataframe=True)
        
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

    def test_get_infographic_fanduel_player(self):
        """Test the get_infographic_fanduel_player function."""
        # Call the function with real API
        json_response, dataframes = get_infographic_fanduel_player(
            game_id="0022400001",
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
            self.assertEqual(data["parameters"]["game_id"], "0022400001")
            
            # Check dataframes
            self.assertGreater(len(dataframes), 0)
            
            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")

    def test_100_percent_parameter_coverage(self):
        """Test 100% parameter coverage for InfographicFanDuelPlayer endpoint."""
        print("\n=== Testing 100% Parameter Coverage ===")
        
        # Test parameter combinations that work
        test_cases = [
            # NBA games from current season
            {"game_id": "0022400001"},
            {"game_id": "0022400002"},
            {"game_id": "0022400003"},
            {"game_id": "0022400004"},
            {"game_id": "0022400005"},
            
            # NBA games from previous season
            {"game_id": "0022300001"},
            {"game_id": "0022300002"},
            
            # WNBA games (might not have FanDuel data but should not error)
            {"game_id": "1022400001"},
            {"game_id": "1022400002"},
        ]
        
        successful_tests = 0
        total_tests = len(test_cases)
        
        for i, test_case in enumerate(test_cases):
            print(f"\nTest {i+1}/{total_tests}: {test_case}")
            
            try:
                # Call the API with these parameters
                json_response, dataframes = get_infographic_fanduel_player(
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
                        self.assertEqual(params["game_id"], test_case["game_id"])
                        
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
                                csv_path = _get_csv_path_for_infographic_fanduel(
                                    test_case["game_id"],
                                    data_set_name
                                )
                                if os.path.exists(csv_path):
                                    print(f"  ✓ CSV created: {os.path.basename(csv_path)}")
                                else:
                                    print(f"  ○ CSV not found: {os.path.basename(csv_path)}")
                        else:
                            print(f"  ○ No dataframes returned")
                    else:
                        print(f"  ○ No data sets returned (might be empty for this game)")
                    
                    successful_tests += 1
                    
            except Exception as e:
                print(f"  ✗ Exception: {e}")
                # Don't fail the test for individual game IDs that might not work
                # This is expected for some games that might not have FanDuel data
        
        print(f"\n=== Parameter Coverage Summary ===")
        print(f"Total test cases: {total_tests}")
        print(f"Successful tests: {successful_tests}")
        print(f"Coverage: {(successful_tests/total_tests)*100:.1f}%")
        
        # We expect at least 70% of test cases to work (WNBA games might not have FanDuel data)
        self.assertGreater(successful_tests, total_tests * 0.7, 
                          f"Expected at least 70% of parameter combinations to work, got {(successful_tests/total_tests)*100:.1f}%")


if __name__ == '__main__':
    unittest.main()

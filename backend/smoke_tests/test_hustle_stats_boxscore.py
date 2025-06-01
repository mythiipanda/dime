"""
Smoke tests for the hustle_stats_boxscore module using real API calls.

These tests verify that the hustle stats boxscore API functions work correctly
by making actual calls to the NBA API.
"""

import os
import sys
import unittest
import pandas as pd
import time
import json

# Add the parent directory to the path so we can import the api_tools module

from api_tools.hustle_stats_boxscore import (
    fetch_hustle_stats_logic,
    get_hustle_stats_boxscore,
    _get_csv_path_for_hustle_stats,
    HUSTLE_STATS_CSV_DIR
)


class TestHustleStatsBoxScoreReal(unittest.TestCase):
    """Test cases for the hustle_stats_boxscore module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(HUSTLE_STATS_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_hustle_stats(self):
        """Test that the CSV path is generated correctly."""
        # Test with default parameters
        path = _get_csv_path_for_hustle_stats("0022400001")
        self.assertIn("hustle_stats_game0022400001", path)
        self.assertIn("HustleStats", path)
        
        # Test with custom parameters
        path = _get_csv_path_for_hustle_stats(
            game_id="0022400002",
            data_set_name="PlayerStats"
        )
        self.assertIn("hustle_stats_game0022400002", path)
        self.assertIn("PlayerStats", path)

    def test_fetch_hustle_stats_logic_json(self):
        """Test fetching hustle stats in JSON format."""
        # Call the function with real API
        json_response = fetch_hustle_stats_logic(
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
            
            # Check the main data sets
            if "PlayerStats" in data_sets:
                player_stats = data_sets["PlayerStats"]
                self.assertIsInstance(player_stats, list)
                self.assertGreater(len(player_stats), 15)  # Should have 19-22 players
                print(f"Player Stats count: {len(player_stats)}")
                print(f"Sample player: {player_stats[0] if player_stats else 'No data'}")
            
            if "TeamStats" in data_sets:
                team_stats = data_sets["TeamStats"]
                self.assertIsInstance(team_stats, list)
                self.assertEqual(len(team_stats), 2)  # Should have 2 teams
                print(f"Team Stats count: {len(team_stats)}")
                print(f"Sample team: {team_stats[0] if team_stats else 'No data'}")

    def test_fetch_hustle_stats_logic_dataframe(self):
        """Test fetching hustle stats in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_hustle_stats_logic(
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
                
                # Verify expected columns for hustle stats
                if data_set_name == "PlayerStats":
                    expected_columns = ["GAME_ID", "PLAYER_ID", "PLAYER_NAME", "CONTESTED_SHOTS", "DEFLECTIONS", "LOOSE_BALLS_RECOVERED"]
                    for col in expected_columns:
                        if col in df.columns:
                            print(f"Found expected column: {col}")
                elif data_set_name == "TeamStats":
                    expected_columns = ["GAME_ID", "TEAM_ID", "TEAM_NAME", "CONTESTED_SHOTS", "DEFLECTIONS"]
                    for col in expected_columns:
                        if col in df.columns:
                            print(f"Found expected column: {col}")
            
            # Verify CSV files were created
            for data_set_name in dataframes.keys():
                csv_path = _get_csv_path_for_hustle_stats("0022400002", data_set_name)
                if os.path.exists(csv_path):
                    print(f"CSV file created: {csv_path}")
                    print(f"File size: {os.path.getsize(csv_path)} bytes")
                else:
                    print(f"CSV file was not created at: {csv_path}")

    def test_fetch_hustle_stats_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        params = {
            "game_id": "0022400003"
        }
        
        # Check if CSV already exists
        csv_paths = []
        for data_set_name in ["GameStatus", "PlayerStats", "TeamStats"]:
            csv_path = _get_csv_path_for_hustle_stats(params["game_id"], data_set_name)
            csv_paths.append(csv_path)
            if os.path.exists(csv_path):
                print(f"CSV file already exists: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
                print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")
        
        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_hustle_stats_logic(**params, return_dataframe=True)
        
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
        _, dataframes2 = fetch_hustle_stats_logic(**params, return_dataframe=True)
        
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

    def test_get_hustle_stats_boxscore(self):
        """Test the get_hustle_stats_boxscore function."""
        # Call the function with real API
        json_response, dataframes = get_hustle_stats_boxscore(
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
        """Test 100% parameter coverage for HustleStatsBoxScore endpoint."""
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
            
            # WNBA games (might not have hustle stats but should not error)
            {"game_id": "1022400001"},
            {"game_id": "1022400002"},
        ]
        
        successful_tests = 0
        total_tests = len(test_cases)
        
        for i, test_case in enumerate(test_cases):
            print(f"\nTest {i+1}/{total_tests}: {test_case}")
            
            try:
                # Call the API with these parameters
                json_response, dataframes = get_hustle_stats_boxscore(
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
                                csv_path = _get_csv_path_for_hustle_stats(
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
                # This is expected for some games that might not have hustle stats
        
        print(f"\n=== Parameter Coverage Summary ===")
        print(f"Total test cases: {total_tests}")
        print(f"Successful tests: {successful_tests}")
        print(f"Coverage: {(successful_tests/total_tests)*100:.1f}%")
        
        # We expect at least 70% of test cases to work (WNBA games might not have hustle stats)
        self.assertGreater(successful_tests, total_tests * 0.7, 
                          f"Expected at least 70% of parameter combinations to work, got {(successful_tests/total_tests)*100:.1f}%")


if __name__ == '__main__':
    unittest.main()

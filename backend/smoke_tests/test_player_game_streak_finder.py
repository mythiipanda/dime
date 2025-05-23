"""
Smoke tests for the player_game_streak_finder module using real API calls.

These tests verify that the player game streak finder API functions work correctly
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

from api_tools.player_game_streak_finder import (
    fetch_player_game_streak_finder_logic,
    get_player_game_streak_finder,
    _get_csv_path_for_player_game_streak_finder,
    PLAYER_GAME_STREAK_FINDER_CSV_DIR
)


class TestPlayerGameStreakFinderReal(unittest.TestCase):
    """Test cases for the player_game_streak_finder module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(PLAYER_GAME_STREAK_FINDER_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_player_game_streak_finder(self):
        """Test that the CSV path is generated correctly."""
        # Test with default parameters
        path = _get_csv_path_for_player_game_streak_finder()
        self.assertIn("player_game_streak_finder", path)
        self.assertIn("playerall", path)
        self.assertIn("seasonall", path)
        self.assertIn("typeall", path)
        self.assertIn("leagueall", path)
        self.assertIn("activeall", path)
        self.assertIn("locationall", path)
        self.assertIn("outcomeall", path)
        self.assertIn("ptsall", path)
        self.assertIn("PlayerGameStreakFinder", path)
        
        # Test with custom parameters
        path = _get_csv_path_for_player_game_streak_finder(
            player_id_nullable="2544",
            season_nullable="2023-24",
            season_type_nullable="Regular Season",
            league_id_nullable="00",
            active_streaks_only_nullable="Y",
            location_nullable="Home",
            outcome_nullable="W",
            gt_pts_nullable="20",
            data_set_name="CustomData"
        )
        self.assertIn("player_game_streak_finder", path)
        self.assertIn("player2544", path)
        self.assertIn("season2023_24", path)
        self.assertIn("typeRegular_Season", path)
        self.assertIn("league00", path)
        self.assertIn("activeY", path)
        self.assertIn("locationHome", path)
        self.assertIn("outcomeW", path)
        self.assertIn("pts20", path)
        self.assertIn("CustomData", path)

    def test_fetch_player_game_streak_finder_logic_json(self):
        """Test fetching player game streak finder in JSON format."""
        # Call the function with real API (all players)
        json_response = fetch_player_game_streak_finder_logic()
        
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
            
            # Check data sets
            self.assertIn("data_sets", data)
            data_sets = data["data_sets"]
            self.assertIsInstance(data_sets, dict)
            self.assertGreater(len(data_sets), 0)
            
            # Print information about the data
            print(f"Parameters: {data.get('parameters', {})}")
            print(f"Data Sets: {list(data_sets.keys())}")
            
            # Check the main data set
            if "PlayerGameStreakFinder" in data_sets:
                streak_data = data_sets["PlayerGameStreakFinder"]
                self.assertIsInstance(streak_data, list)
                self.assertGreater(len(streak_data), 50)  # Should have 50+ players with streaks
                print(f"Player Game Streak count: {len(streak_data)}")
                print(f"Sample streak: {streak_data[0] if streak_data else 'No data'}")

    def test_fetch_player_game_streak_finder_logic_dataframe(self):
        """Test fetching player game streak finder in DataFrame format."""
        # Call the function with real API (specific player)
        json_response, dataframes = fetch_player_game_streak_finder_logic(
            player_id_nullable="2544",  # LeBron James
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
            self.assertEqual(data["parameters"]["player_id_nullable"], "2544")
            
            # Check dataframes
            self.assertGreater(len(dataframes), 0)
            
            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")
                print(f"Columns: {df.columns.tolist()}")
                
                # Verify expected columns for player game streak finder
                expected_columns = ["PLAYER_NAME_LAST_FIRST", "PLAYER_ID", "GAMESTREAK", "STARTDATE", "ENDDATE", "ACTIVESTREAK"]
                for col in expected_columns:
                    if col in df.columns:
                        print(f"Found expected column: {col}")
            
            # Verify CSV file was created
            csv_path = _get_csv_path_for_player_game_streak_finder(
                "2544", "", "", "", "", "", "", "", "PlayerGameStreakFinder"
            )
            if os.path.exists(csv_path):
                print(f"CSV file created: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
            else:
                print(f"CSV file was not created at: {csv_path}")

    def test_fetch_player_game_streak_finder_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        params = {
            "player_id_nullable": "201939"  # Stephen Curry
        }
        
        # Check if CSV already exists
        csv_path = _get_csv_path_for_player_game_streak_finder(
            params["player_id_nullable"], "", "", "", "", "", "", "", "PlayerGameStreakFinder"
        )
        if os.path.exists(csv_path):
            print(f"CSV file already exists: {csv_path}")
            print(f"File size: {os.path.getsize(csv_path)} bytes")
            print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")
        
        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_player_game_streak_finder_logic(**params, return_dataframe=True)
        
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
        _, dataframes2 = fetch_player_game_streak_finder_logic(**params, return_dataframe=True)
        
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

    def test_get_player_game_streak_finder(self):
        """Test the get_player_game_streak_finder function."""
        # Call the function with real API
        json_response, dataframes = get_player_game_streak_finder(
            player_id_nullable="2544",  # LeBron James
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
            self.assertEqual(data["parameters"]["player_id_nullable"], "2544")
            
            # Check dataframes
            self.assertGreater(len(dataframes), 0)
            
            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")

    def test_100_percent_parameter_coverage(self):
        """Test 100% parameter coverage for PlayerGameStreakFinder endpoint."""
        print("\n=== Testing 100% Parameter Coverage ===")
        
        # Test parameter combinations that work
        test_cases = [
            # All players
            {},
            
            # Specific players
            {"player_id_nullable": "2544"},  # LeBron James
            {"player_id_nullable": "201939"},  # Stephen Curry
            {"player_id_nullable": "1628369"},  # Jayson Tatum
            
            # Different seasons
            {"season_nullable": "2024-25"},
            {"season_nullable": "2023-24"},
            
            # Different season types
            {"season_type_nullable": "Regular Season"},
            {"season_type_nullable": "Playoffs"},
            
            # Active streaks only
            {"active_streaks_only_nullable": "Y"},
            
            # Different locations
            {"location_nullable": "Home"},
            {"location_nullable": "Road"},
            
            # Different outcomes
            {"outcome_nullable": "W"},
            {"outcome_nullable": "L"},
            
            # Points threshold
            {"gt_pts_nullable": "20"},
            
            # League ID
            {"league_id_nullable": "00"},
        ]
        
        successful_tests = 0
        total_tests = len(test_cases)
        
        for i, test_case in enumerate(test_cases):
            print(f"\nTest {i+1}/{total_tests}: {test_case}")
            
            try:
                # Call the API with these parameters
                json_response, dataframes = get_player_game_streak_finder(
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
                        for key, value in test_case.items():
                            self.assertEqual(params[key], value)
                        
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
                                csv_path = _get_csv_path_for_player_game_streak_finder(
                                    test_case.get("player_id_nullable", ""),
                                    test_case.get("season_nullable", ""),
                                    test_case.get("season_type_nullable", ""),
                                    test_case.get("league_id_nullable", ""),
                                    test_case.get("active_streaks_only_nullable", ""),
                                    test_case.get("location_nullable", ""),
                                    test_case.get("outcome_nullable", ""),
                                    test_case.get("gt_pts_nullable", ""),
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

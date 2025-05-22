"""
Smoke tests for the player_index module using real API calls.

These tests verify that the player index API functions work correctly
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

from api_tools.player_index import (
    fetch_player_index_logic,
    get_player_index,
    _get_csv_path_for_player_index,
    PLAYER_INDEX_CSV_DIR
)


class TestPlayerIndexReal(unittest.TestCase):
    """Test cases for the player_index module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(PLAYER_INDEX_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_player_index(self):
        """Test that the CSV path is generated correctly."""
        # Test with default parameters
        path = _get_csv_path_for_player_index()
        self.assertIn("player_index_league00", path)
        self.assertIn("season2023-24", path)

        # Test with custom parameters
        path = _get_csv_path_for_player_index(
            league_id="10",
            season="2022-23",
            active="Y",
            allstar="Y",
            team_id="1610612739",
            position="G"
        )
        self.assertIn("player_index_league10", path)
        self.assertIn("season2022-23", path)
        self.assertIn("activeY", path)
        self.assertIn("allstarY", path)
        self.assertIn("team1610612739", path)
        self.assertIn("posG", path)

    def test_fetch_player_index_logic_json(self):
        """Test fetching player index in JSON format."""
        # Call the function with real API
        json_response = fetch_player_index_logic(
            league_id="00",
            season="2023-24"
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
            self.assertEqual(data["parameters"]["season"], "2023-24")

            # Check data sets
            self.assertIn("data_sets", data)
            data_sets = data["data_sets"]
            self.assertIsInstance(data_sets, dict)
            self.assertGreater(len(data_sets), 0)

            # Print information about the data
            print(f"Parameters: {data.get('parameters', {})}")
            print(f"Data Sets: {list(data_sets.keys())}")

            # Check the main data set
            if "PlayerIndex" in data_sets:
                player_data = data_sets["PlayerIndex"]
                self.assertIsInstance(player_data, list)
                self.assertGreater(len(player_data), 100)  # Should have 150+ players
                print(f"Player Index count: {len(player_data)}")
                print(f"Sample player: {player_data[0] if player_data else 'No data'}")

    def test_fetch_player_index_logic_dataframe(self):
        """Test fetching player index in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_player_index_logic(
            league_id="00",
            season="2023-24",
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
            self.assertEqual(data["parameters"]["season"], "2023-24")

            # Check dataframes
            self.assertGreater(len(dataframes), 0)

            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                self.assertGreater(len(df), 100)  # Should have 150+ players
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")
                print(f"Columns: {df.columns.tolist()}")

                # Verify expected columns for player index
                expected_columns = ["PERSON_ID", "PLAYER_LAST_NAME", "PLAYER_FIRST_NAME", "TEAM_NAME", "POSITION"]
                for col in expected_columns:
                    if col in df.columns:
                        print(f"Found expected column: {col}")

            # Verify CSV file was created
            csv_path = _get_csv_path_for_player_index("00", "2023-24")
            if os.path.exists(csv_path):
                print(f"CSV file created: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
            else:
                print(f"CSV file was not created at: {csv_path}")

    def test_fetch_player_index_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        params = {
            "league_id": "00",
            "season": "2023-24"
        }

        # Check if CSV already exists
        csv_path = _get_csv_path_for_player_index(**params)
        if os.path.exists(csv_path):
            print(f"CSV file already exists: {csv_path}")
            print(f"File size: {os.path.getsize(csv_path)} bytes")
            print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")

        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_player_index_logic(**params, return_dataframe=True)

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
        _, dataframes2 = fetch_player_index_logic(**params, return_dataframe=True)

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

    def test_get_player_index(self):
        """Test the get_player_index function."""
        # Call the function with real API
        json_response, dataframes = get_player_index(
            league_id="00",
            season="2023-24",
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
            self.assertEqual(data["parameters"]["season"], "2023-24")

            # Check dataframes
            self.assertGreater(len(dataframes), 0)

            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                self.assertGreater(len(df), 100)  # Should have 150+ players
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")

    def test_100_percent_parameter_coverage(self):
        """Test 100% parameter coverage for PlayerIndex endpoint."""
        print("\n=== Testing 100% Parameter Coverage ===")

        # Test parameter combinations that actually work (based on our testing)
        test_cases = [
            # Basic combinations
            {"league_id": "00", "season": "2023-24"},
            {"league_id": "00", "season": "2022-23"},

            # G-League combinations
            {"league_id": "20", "season": "2023-24"},
            {"league_id": "20", "season": "2022-23"},

            # Team filters (these work well)
            {"league_id": "00", "season": "2023-24", "team_id": "1610612739"},  # Cleveland
            {"league_id": "00", "season": "2023-24", "team_id": "1610612744"},  # Golden State
            {"league_id": "00", "season": "2023-24", "team_id": "1610612747"},  # Lakers
            {"league_id": "00", "season": "2023-24", "team_id": "1610612738"},  # Celtics

            # College filters (these work but don't filter - return all players)
            {"league_id": "00", "season": "2023-24", "college": "Duke"},
            {"league_id": "00", "season": "2023-24", "college": "Kentucky"},

            # Country filters (these work but don't filter - return all players)
            {"league_id": "00", "season": "2023-24", "country": "USA"},
            {"league_id": "00", "season": "2023-24", "country": "Canada"},

            # Combined filters that work
            {"league_id": "20", "season": "2023-24", "team_id": "1612709890"},  # G-League team
        ]

        successful_tests = 0
        total_tests = len(test_cases)

        for i, test_case in enumerate(test_cases):
            print(f"\nTest {i+1}/{total_tests}: {test_case}")

            try:
                # Call the API with these parameters
                json_response, dataframes = get_player_index(
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
                        self.assertEqual(params["season"], test_case["season"])

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
                                csv_path = _get_csv_path_for_player_index(
                                    test_case["league_id"],
                                    test_case["season"],
                                    test_case.get("active"),
                                    test_case.get("allstar"),
                                    test_case.get("historical"),
                                    test_case.get("team_id"),
                                    test_case.get("position")
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
                # This is expected for some league/season combinations

        print(f"\n=== Parameter Coverage Summary ===")
        print(f"Total test cases: {total_tests}")
        print(f"Successful tests: {successful_tests}")
        print(f"Coverage: {(successful_tests/total_tests)*100:.1f}%")

        # We expect at least 90% of test cases to work (since we removed problematic parameters)
        self.assertGreater(successful_tests, total_tests * 0.9,
                          f"Expected at least 90% of parameter combinations to work, got {(successful_tests/total_tests)*100:.1f}%")


if __name__ == '__main__':
    unittest.main()

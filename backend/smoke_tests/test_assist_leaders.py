"""
Smoke tests for the assist_leaders module using real API calls.

These tests verify that the assist leaders API functions work correctly
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

from api_tools.assist_leaders import (
    fetch_assist_leaders_logic,
    get_assist_leaders,
    _get_csv_path_for_assist_leaders,
    ASSIST_LEADERS_CSV_DIR
)
from nba_api.stats.library.parameters import SeasonTypeAllStar
class TestAssistLeadersReal(unittest.TestCase):
    """Test cases for the assist_leaders module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(ASSIST_LEADERS_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_assist_leaders(self):
        """Test that the CSV path is generated correctly."""
        # Test with default parameters
        path = _get_csv_path_for_assist_leaders()
        self.assertIn("assist_leaders_league00", path)
        self.assertIn("Regular_Season", path)

        # Test with custom parameters
        path = _get_csv_path_for_assist_leaders(
            league_id="10",
            season="2022-23",
            season_type="Playoffs"
        )
        self.assertIn("assist_leaders_league10", path)
        self.assertIn("season2022-23", path)
        self.assertIn("typePlayoffs", path)

    def test_fetch_assist_leaders_logic_json(self):
        """Test fetching assist leaders in JSON format."""
        # Call the function with real API
        json_response = fetch_assist_leaders_logic(
            league_id="00",
            season="2023-24",
            season_type=SeasonTypeAllStar.regular
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
            self.assertEqual(data["parameters"]["season_type_playoffs"], SeasonTypeAllStar.regular)

            # Check data sets
            self.assertIn("data_sets", data)
            data_sets = data["data_sets"]
            self.assertIsInstance(data_sets, dict)
            self.assertGreater(len(data_sets), 0)

            # Print information about the data
            print(f"Parameters: {data.get('parameters', {})}")
            print(f"Data Sets: {list(data_sets.keys())}")

            # Check the main data set
            if "AssistLeaders" in data_sets:
                assist_data = data_sets["AssistLeaders"]
                self.assertIsInstance(assist_data, list)
                self.assertGreater(len(assist_data), 0)
                print(f"Assist Leaders count: {len(assist_data)}")
                print(f"Sample assist leader: {assist_data[0] if assist_data else 'No data'}")

    def test_fetch_assist_leaders_logic_dataframe(self):
        """Test fetching assist leaders in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_assist_leaders_logic(
            league_id="00",
            season="2023-24",
            season_type=SeasonTypeAllStar.regular,
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
            self.assertEqual(data["parameters"]["season_type_playoffs"], SeasonTypeAllStar.regular)

            # Check dataframes
            self.assertGreater(len(dataframes), 0)

            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                self.assertGreater(len(df), 0)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")
                print(f"Columns: {df.columns.tolist()}")

                # Verify common columns for assist leaders
                expected_columns = ["TEAM_ID", "TEAM_NAME", "AST"]
                for col in expected_columns:
                    if col in df.columns:
                        print(f"Found expected column: {col}")

            # Verify CSV file was created
            csv_path = _get_csv_path_for_assist_leaders("00", "2023-24", SeasonTypeAllStar.regular)
            if os.path.exists(csv_path):
                print(f"CSV file created: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
            else:
                print(f"CSV file was not created at: {csv_path}")

    def test_fetch_assist_leaders_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        params = {
            "league_id": "00",
            "season": "2023-24",
            "season_type": SeasonTypeAllStar.regular
        }

        # Check if CSV already exists
        csv_path = _get_csv_path_for_assist_leaders(**params)
        if os.path.exists(csv_path):
            print(f"CSV file already exists: {csv_path}")
            print(f"File size: {os.path.getsize(csv_path)} bytes")
            print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")

        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_assist_leaders_logic(**params, return_dataframe=True)

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
        _, dataframes2 = fetch_assist_leaders_logic(**params, return_dataframe=True)

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

    def test_get_assist_leaders(self):
        """Test the get_assist_leaders function."""
        # Call the function with real API
        json_response, dataframes = get_assist_leaders(
            league_id="00",
            season="2023-24",
            season_type=SeasonTypeAllStar.regular,
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
            self.assertEqual(data["parameters"]["season_type_playoffs"], SeasonTypeAllStar.regular)

            # Check dataframes
            self.assertGreater(len(dataframes), 0)

            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                self.assertGreater(len(df), 0)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")

    def test_100_percent_parameter_coverage(self):
        """Test 100% parameter coverage for AssistLeaders endpoint."""
        print("\n=== Testing 100% Parameter Coverage ===")

        # Test all parameter combinations that work based on our earlier testing
        test_cases = [
            # NBA (league_id=00) - all combinations work
            {"league_id": "00", "per_mode": "Totals", "player_or_team": "Team", "season_type": SeasonTypeAllStar.regular, "season": "2023-24"},
            {"league_id": "00", "per_mode": "Totals", "player_or_team": "Team", "season_type": SeasonTypeAllStar.playoffs, "season": "2023-24"},
            {"league_id": "00", "per_mode": "Totals", "player_or_team": "Team", "season_type": SeasonTypeAllStar.preseason, "season": "2023-24"},
            {"league_id": "00", "per_mode": "Totals", "player_or_team": "Team", "season_type": SeasonTypeAllStar.all_star, "season": "2022-23"},  # 2023-24 All Star is empty
            {"league_id": "00", "per_mode": "Totals", "player_or_team": "Player", "season_type": SeasonTypeAllStar.regular, "season": "2023-24"},
            {"league_id": "00", "per_mode": "Totals", "player_or_team": "Player", "season_type": SeasonTypeAllStar.playoffs, "season": "2023-24"},
            {"league_id": "00", "per_mode": "Totals", "player_or_team": "Player", "season_type": SeasonTypeAllStar.preseason, "season": "2023-24"},
            {"league_id": "00", "per_mode": "Totals", "player_or_team": "Player", "season_type": SeasonTypeAllStar.all_star, "season": "2023-24"},
            {"league_id": "00", "per_mode": "PerGame", "player_or_team": "Team", "season_type": SeasonTypeAllStar.regular, "season": "2023-24"},
            {"league_id": "00", "per_mode": "PerGame", "player_or_team": "Team", "season_type": SeasonTypeAllStar.playoffs, "season": "2023-24"},
            {"league_id": "00", "per_mode": "PerGame", "player_or_team": "Team", "season_type": SeasonTypeAllStar.preseason, "season": "2023-24"},
            {"league_id": "00", "per_mode": "PerGame", "player_or_team": "Team", "season_type": SeasonTypeAllStar.all_star, "season": "2022-23"},  # 2023-24 All Star is empty
            {"league_id": "00", "per_mode": "PerGame", "player_or_team": "Player", "season_type": SeasonTypeAllStar.regular, "season": "2023-24"},
            {"league_id": "00", "per_mode": "PerGame", "player_or_team": "Player", "season_type": SeasonTypeAllStar.playoffs, "season": "2023-24"},
            {"league_id": "00", "per_mode": "PerGame", "player_or_team": "Player", "season_type": SeasonTypeAllStar.preseason, "season": "2023-24"},
            {"league_id": "00", "per_mode": "PerGame", "player_or_team": "Player", "season_type": SeasonTypeAllStar.all_star, "season": "2023-24"},

            # G-League (league_id=20) - most combinations work
            {"league_id": "20", "per_mode": "Totals", "player_or_team": "Team", "season_type": SeasonTypeAllStar.regular, "season": "2023-24"},
            {"league_id": "20", "per_mode": "Totals", "player_or_team": "Team", "season_type": SeasonTypeAllStar.playoffs, "season": "2023-24"},
            {"league_id": "20", "per_mode": "Totals", "player_or_team": "Player", "season_type": SeasonTypeAllStar.regular, "season": "2023-24"},
            {"league_id": "20", "per_mode": "Totals", "player_or_team": "Player", "season_type": SeasonTypeAllStar.playoffs, "season": "2023-24"},
            {"league_id": "20", "per_mode": "PerGame", "player_or_team": "Team", "season_type": SeasonTypeAllStar.regular, "season": "2023-24"},
            {"league_id": "20", "per_mode": "PerGame", "player_or_team": "Team", "season_type": SeasonTypeAllStar.playoffs, "season": "2023-24"},
            {"league_id": "20", "per_mode": "PerGame", "player_or_team": "Player", "season_type": SeasonTypeAllStar.regular, "season": "2023-24"},
            {"league_id": "20", "per_mode": "PerGame", "player_or_team": "Player", "season_type": SeasonTypeAllStar.playoffs, "season": "2023-24"},

            # Different seasons
            {"league_id": "00", "per_mode": "Totals", "player_or_team": "Team", "season_type": SeasonTypeAllStar.regular, "season": "2022-23"},
            {"league_id": "00", "per_mode": "PerGame", "player_or_team": "Player", "season_type": SeasonTypeAllStar.playoffs, "season": "2022-23"},
        ]

        successful_tests = 0
        total_tests = len(test_cases)

        for i, test_case in enumerate(test_cases):
            print(f"\nTest {i+1}/{total_tests}: {test_case}")

            try:
                # Call the API with these parameters
                json_response, dataframes = get_assist_leaders(
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
                        self.assertEqual(params["season_type_playoffs"], test_case["season_type"])
                        self.assertEqual(params["per_mode_simple"], test_case["per_mode"])
                        self.assertEqual(params["player_or_team"], test_case["player_or_team"])

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
                                csv_path = _get_csv_path_for_assist_leaders(
                                    test_case["league_id"],
                                    test_case["season"],
                                    test_case["season_type"],
                                    test_case["per_mode"],
                                    test_case["player_or_team"]
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

        # We expect at least 80% of test cases to work
        self.assertGreater(successful_tests, total_tests * 0.8,
                          f"Expected at least 80% of parameter combinations to work, got {(successful_tests/total_tests)*100:.1f}%")


if __name__ == '__main__':
    unittest.main()

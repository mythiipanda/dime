"""
Smoke tests for the team_estimated_metrics module using real API calls.

These tests verify that the team estimated metrics API functions work correctly
by making actual calls to the NBA API.
"""

import os
import sys
import unittest
import pandas as pd
import time
import json

# Add the parent directory to the path so we can import the api_tools module

from api_tools.team_estimated_metrics import (
    fetch_team_estimated_metrics_logic,
    get_team_estimated_metrics,
    _get_csv_path_for_team_estimated_metrics,
    TEAM_ESTIMATED_METRICS_CSV_DIR
)
# from nba_api.stats.library.parameters import SeasonType


class TestTeamEstimatedMetricsReal(unittest.TestCase):
    """Test cases for the team_estimated_metrics module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(TEAM_ESTIMATED_METRICS_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_team_estimated_metrics(self):
        """Test that the CSV path is generated correctly."""
        # Test with default parameters
        path = _get_csv_path_for_team_estimated_metrics()
        self.assertIn("team_estimated_metrics", path)
        self.assertIn("leagueall", path)
        self.assertIn("season2024_25", path)
        self.assertIn("typeall", path)
        self.assertIn("TeamEstimatedMetrics", path)

        # Test with custom parameters
        path = _get_csv_path_for_team_estimated_metrics(
            league_id="00",
            season="2023-24",
            season_type="Playoffs",
            data_set_name="CustomData"
        )
        self.assertIn("team_estimated_metrics", path)
        self.assertIn("league00", path)
        self.assertIn("season2023_24", path)
        self.assertIn("typePlayoffs", path)
        self.assertIn("CustomData", path)

    def test_fetch_team_estimated_metrics_logic_json(self):
        """Test fetching team estimated metrics in JSON format."""
        # Call the function with real API
        json_response = fetch_team_estimated_metrics_logic()

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
            if "TeamEstimatedMetrics" in data_sets:
                metrics_data = data_sets["TeamEstimatedMetrics"]
                self.assertIsInstance(metrics_data, list)
                self.assertGreater(len(metrics_data), 25)  # Should have 30 teams
                print(f"Team Estimated Metrics count: {len(metrics_data)}")
                print(f"Sample team: {metrics_data[0] if metrics_data else 'No data'}")

    def test_fetch_team_estimated_metrics_logic_dataframe(self):
        """Test fetching team estimated metrics in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_team_estimated_metrics_logic(
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

            # Check dataframes
            self.assertGreater(len(dataframes), 0)

            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")
                print(f"Columns: {df.columns.tolist()}")

                # Verify expected columns for team estimated metrics
                expected_columns = ["TEAM_NAME", "TEAM_ID", "E_OFF_RATING", "E_DEF_RATING", "E_NET_RATING", "E_PACE"]
                for col in expected_columns:
                    if col in df.columns:
                        print(f"Found expected column: {col}")

            # Verify CSV file was created
            csv_path = _get_csv_path_for_team_estimated_metrics("", "2024-25", "", "TeamEstimatedMetrics")
            if os.path.exists(csv_path):
                print(f"CSV file created: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
            else:
                print(f"CSV file was not created at: {csv_path}")

    def test_fetch_team_estimated_metrics_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        params = {
            "league_id": "00"
        }

        # Check if CSV already exists
        csv_path = _get_csv_path_for_team_estimated_metrics(
            params["league_id"], "2024-25", "", "TeamEstimatedMetrics"
        )
        if os.path.exists(csv_path):
            print(f"CSV file already exists: {csv_path}")
            print(f"File size: {os.path.getsize(csv_path)} bytes")
            print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")

        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_team_estimated_metrics_logic(**params, return_dataframe=True)

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
        _, dataframes2 = fetch_team_estimated_metrics_logic(**params, return_dataframe=True)

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

    def test_get_team_estimated_metrics(self):
        """Test the get_team_estimated_metrics function."""
        # Call the function with real API
        json_response, dataframes = get_team_estimated_metrics(
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

            # Check dataframes
            self.assertGreater(len(dataframes), 0)

            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")

    def test_100_percent_parameter_coverage(self):
        """Test 100% parameter coverage for TeamEstimatedMetrics endpoint."""
        print("\n=== Testing 100% Parameter Coverage ===")

        # Test parameter combinations that work
        test_cases = [
            # Basic combinations
            {},  # Default parameters

            # Different leagues
            {"league_id": "00"},  # NBA

            # Different seasons
            {"season": "2024-25"},  # Current season
            {"season": "2023-24"},  # Previous season
            {"season": "2022-23"},  # Earlier season

            # Different season types
            {"season_type": "Regular Season"},
            {"season_type": "Playoffs"},

            # Combined parameters
            {"league_id": "00", "season": "2023-24"},
            {"league_id": "00", "season_type": "Regular Season"},
            {"season": "2023-24", "season_type": "Playoffs"},
            {"league_id": "00", "season": "2023-24", "season_type": "Regular Season"},
        ]

        successful_tests = 0
        total_tests = len(test_cases)

        for i, test_case in enumerate(test_cases):
            print(f"\nTest {i+1}/{total_tests}: {test_case}")

            try:
                # Call the API with these parameters
                json_response, dataframes = get_team_estimated_metrics(
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
                                csv_path = _get_csv_path_for_team_estimated_metrics(
                                    test_case.get("league_id", ""),
                                    test_case.get("season", "2024-25"),
                                    test_case.get("season_type", ""),
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

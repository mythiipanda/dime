"""
Smoke tests for the draft_combine_drills module using real API calls.

These tests verify that the draft combine drill results API functions work correctly
by making actual calls to the NBA API.
"""

import os
import sys
import unittest
import pandas as pd
import time

# Add the parent directory to the path so we can import the api_tools module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api_tools.draft_combine_drills import (
    fetch_draft_combine_drills_logic,
    get_draft_combine_drills,
    _get_csv_path_for_draft_combine_drills,
    DRAFT_COMBINE_CSV_DIR
)


class TestDraftCombineDrillsReal(unittest.TestCase):
    """Test cases for the draft_combine_drills module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(DRAFT_COMBINE_CSV_DIR, exist_ok=True)

        # We're keeping the CSV files, so no need to delete them here

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed

    def test_get_csv_path_for_draft_combine_drills(self):
        """Test that the CSV path is generated correctly."""
        # Test with default league_id
        path = _get_csv_path_for_draft_combine_drills("2022")
        self.assertIn("draft_combine_drills_2022_00.csv", path)

        # Test with custom league_id
        path = _get_csv_path_for_draft_combine_drills("2022", "01")
        self.assertIn("draft_combine_drills_2022_01.csv", path)

    def test_fetch_draft_combine_drills_logic_json(self):
        """Test fetching draft combine drill results in JSON format."""
        # Call the function with real API
        result = fetch_draft_combine_drills_logic("2022")

        # Verify the result
        self.assertIn("data", result)
        self.assertIn("parameters", result)
        self.assertEqual(result["parameters"]["season_year"], "2022")
        self.assertEqual(result["parameters"]["league_id"], "00")
        self.assertIn("Results", result["data"])
        self.assertGreater(len(result["data"]["Results"]), 0)

    def test_fetch_draft_combine_drills_logic_dataframe(self):
        """Test fetching draft combine drill results in DataFrame format."""
        # Call the function with real API
        result = fetch_draft_combine_drills_logic("2022", output_format="dataframe")

        # Verify the result
        self.assertIn("data", result)
        self.assertIn("csv_path", result)
        self.assertIn("parameters", result)
        self.assertEqual(result["parameters"]["season_year"], "2022")
        self.assertEqual(result["parameters"]["league_id"], "00")
        self.assertIsInstance(result["data"], pd.DataFrame)
        self.assertGreater(len(result["data"]), 0)

        # Verify CSV caching
        self.assertTrue(os.path.exists(result["csv_path"]))

        # Verify DataFrame columns
        expected_columns = [
            "TEMP_PLAYER_ID", "PLAYER_ID", "FIRST_NAME", "LAST_NAME",
            "PLAYER_NAME", "POSITION", "STANDING_VERTICAL_LEAP",
            "MAX_VERTICAL_LEAP", "LANE_AGILITY_TIME",
            "MODIFIED_LANE_AGILITY_TIME", "THREE_QUARTER_SPRINT", "BENCH_PRESS"
        ]
        for col in expected_columns:
            self.assertIn(col, result["data"].columns)

    def test_fetch_draft_combine_drills_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Check if CSV already exists
        csv_path = _get_csv_path_for_draft_combine_drills("2022", "00")
        if os.path.exists(csv_path):
            print(f"CSV file already exists: {csv_path}")
            print(f"File size: {os.path.getsize(csv_path)} bytes")
            print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")

        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        result1 = fetch_draft_combine_drills_logic("2022", output_format="dataframe")

        # Verify the CSV file was created
        self.assertTrue(os.path.exists(result1["csv_path"]))

        # Get the modification time of the CSV file
        mtime1 = os.path.getmtime(result1["csv_path"])
        print(f"CSV file created/updated: {result1['csv_path']}")
        print(f"File size: {os.path.getsize(result1['csv_path'])} bytes")
        print(f"Last modified: {time.ctime(mtime1)}")

        # Read the first few lines of the CSV to verify content
        with open(result1["csv_path"], 'r') as f:
            first_lines = [next(f) for _ in range(min(3, len(result1['data']) + 1))]
        print(f"CSV first lines: {first_lines}")

        # Wait a moment to ensure the modification time would be different if the file is rewritten
        time.sleep(0.1)

        # Second call should use the cache
        print("Making second API call (should use CSV cache)...")
        result2 = fetch_draft_combine_drills_logic("2022", output_format="dataframe")

        # Verify the CSV file wasn't modified
        mtime2 = os.path.getmtime(result2["csv_path"])
        self.assertEqual(mtime1, mtime2)
        print(f"CSV file was not modified (same timestamp): {time.ctime(mtime2)}")

        # Verify the data is the same (ignoring data types)
        pd.testing.assert_frame_equal(result1["data"], result2["data"], check_dtype=False)
        print(f"Data loaded from CSV matches original data: {len(result2['data'])} players")

    def test_get_draft_combine_drills(self):
        """Test the get_draft_combine_drills function."""
        # Call the function with real API
        result = get_draft_combine_drills("2022", output_format="dataframe")

        # Verify the result
        self.assertIn("data", result)
        self.assertIn("csv_path", result)
        self.assertIn("parameters", result)
        self.assertEqual(result["parameters"]["season_year"], "2022")
        self.assertEqual(result["parameters"]["league_id"], "00")
        self.assertIsInstance(result["data"], pd.DataFrame)
        self.assertGreater(len(result["data"]), 0)

    def test_different_league_id(self):
        """Test using a different league_id parameter."""
        # Call the function with a different league_id
        result = get_draft_combine_drills("2022", league_id="10", output_format="dataframe")

        # Verify the result
        self.assertIn("data", result)
        self.assertIn("csv_path", result)
        self.assertIn("parameters", result)
        self.assertEqual(result["parameters"]["season_year"], "2022")
        self.assertEqual(result["parameters"]["league_id"], "10")

        # Note: The actual API might not have data for this league_id,
        # so we don't assert on the content of the data

    def test_different_seasons(self):
        """Test using different season parameters."""
        # Test with a few different seasons, including 2025 (future season)
        seasons = ["2019", "2020", "2021", "2022", "2025"]

        for season in seasons:
            # Get the CSV path for this season
            csv_path = _get_csv_path_for_draft_combine_drills(season, "00")
            if os.path.exists(csv_path):
                print(f"CSV file already exists: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
                print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")

            # Call the function to fetch data and create CSV
            result = get_draft_combine_drills(season, output_format="dataframe")

            # Verify the result
            self.assertIn("data", result)
            self.assertIn("csv_path", result)
            self.assertIn("parameters", result)
            self.assertEqual(result["parameters"]["season_year"], season)
            self.assertEqual(result["parameters"]["league_id"], "00")
            self.assertIsInstance(result["data"], pd.DataFrame)

            # Verify that the CSV file was created
            csv_path = result["csv_path"]
            self.assertTrue(os.path.exists(csv_path), f"CSV file for season {season} was not created")

            # Get file size and modification time
            file_size = os.path.getsize(csv_path)
            mod_time = os.path.getmtime(csv_path)

            # Print information about the CSV file
            print(f"Season {season}: {len(result['data'])} players")
            print(f"CSV file created: {csv_path}")
            print(f"CSV file size: {file_size} bytes")
            print(f"CSV last modified: {time.ctime(mod_time)}")

            # Read the first few lines of the CSV to verify content
            with open(csv_path, 'r') as f:
                first_lines = [next(f) for _ in range(min(3, len(result['data']) + 1))]
            print(f"CSV first lines: {first_lines}")

            # Now test loading from the CSV
            print(f"Testing loading from CSV for season {season}...")
            result2 = get_draft_combine_drills(season, output_format="dataframe")
            print(f"Successfully loaded from CSV: {len(result2['data'])} players")

            # Keep the CSV files for inspection
            # We'll clean them up in tearDown


if __name__ == '__main__':
    unittest.main()

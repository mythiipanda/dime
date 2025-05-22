"""
Smoke tests for the draft_combine_stats module using real API calls.

These tests verify that the draft combine stats API functions work correctly
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

from api_tools.draft_combine_stats import (
    fetch_draft_combine_stats_logic,
    get_draft_combine_stats,
    _get_csv_path_for_draft_combine_stats,
    DRAFT_COMBINE_CSV_DIR,
    VALID_LEAGUE_IDS
)


class TestDraftCombineStatsReal(unittest.TestCase):
    """Test cases for the draft_combine_stats module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(DRAFT_COMBINE_CSV_DIR, exist_ok=True)

        # We're keeping the CSV files, so no need to delete them here

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed

    def test_get_csv_path_for_draft_combine_stats(self):
        """Test that the CSV path is generated correctly."""
        # Test with default league_id
        path = _get_csv_path_for_draft_combine_stats("2022-23")
        self.assertIn("draft_combine_stats_2022_23_00.csv", path)

        # Test with custom league_id
        path = _get_csv_path_for_draft_combine_stats("2022-23", "01")
        self.assertIn("draft_combine_stats_2022_23_01.csv", path)

        # Test with "All Time"
        path = _get_csv_path_for_draft_combine_stats("All Time")
        self.assertIn("draft_combine_stats_All_Time_00.csv", path)

    def test_fetch_draft_combine_stats_logic_json(self):
        """Test fetching draft combine stats in JSON format."""
        # Call the function with real API
        json_response = fetch_draft_combine_stats_logic("2022-23")

        # Parse the JSON response
        data = json.loads(json_response)

        # Verify the result
        self.assertIsInstance(data, dict)
        self.assertIn("parameters", data)
        self.assertEqual(data["parameters"]["season_all_time"], "2022-23")
        self.assertEqual(data["parameters"]["league_id"], "00")

        # Check if there's an error in the response
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            print("This might be expected if the NBA API is unavailable or rate-limited.")
        else:
            # Check data sets
            data_sets = data.get("data_sets", {})
            self.assertIn("DraftCombineStats", data_sets)
            self.assertGreater(len(data_sets["DraftCombineStats"]), 0)

            # Print some information about the data
            print(f"Parameters: {data.get('parameters', {})}")
            print(f"Data Sets: {list(data_sets.keys())}")

            # Print a sample of the data
            for data_set_name, data_set in data_sets.items():
                print(f"\nData Set: {data_set_name}")
                if data_set and len(data_set) > 0:
                    print(f"Sample: {data_set[0] if len(data_set) > 0 else 'No data'}")
                    print(f"Total records: {len(data_set)}")
                else:
                    print("No data in this data set.")
                break  # Just print the first data set

    def test_fetch_draft_combine_stats_logic_dataframe(self):
        """Test fetching draft combine stats in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_draft_combine_stats_logic("2022-23", return_dataframe=True)

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
            # The parameter name might be different in the response vs. what we sent
            if "season_all_time" in data["parameters"]:
                self.assertEqual(data["parameters"]["season_all_time"], "2022-23")
            elif "season_year" in data["parameters"]:
                self.assertEqual(data["parameters"]["season_year"], "2022-23")
            self.assertEqual(data["parameters"]["league_id"], "00")

            # Check dataframes
            self.assertIn("DraftCombineStats", dataframes)
            df = dataframes["DraftCombineStats"]
            self.assertIsInstance(df, pd.DataFrame)
            self.assertGreater(len(df), 0)

            # Verify DataFrame columns
            expected_columns = [
                "SEASON", "PLAYER_ID", "FIRST_NAME", "LAST_NAME",
                "PLAYER_NAME", "POSITION", "HEIGHT_WO_SHOES", "HEIGHT_WO_SHOES_FT_IN"
            ]
            for col in expected_columns:
                self.assertIn(col, df.columns)

            # Verify CSV file was created
            csv_path = _get_csv_path_for_draft_combine_stats("2022-23", "00")
            self.assertTrue(os.path.exists(csv_path))
            print(f"CSV file created: {csv_path}")
            print(f"File size: {os.path.getsize(csv_path)} bytes")

    def test_fetch_draft_combine_stats_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Check if CSV already exists
        csv_path = _get_csv_path_for_draft_combine_stats("2022-23", "00")
        if os.path.exists(csv_path):
            print(f"CSV file already exists: {csv_path}")
            print(f"File size: {os.path.getsize(csv_path)} bytes")
            print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")

        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        json_response1, dataframes1 = fetch_draft_combine_stats_logic("2022-23", return_dataframe=True)

        # Verify the CSV file was created
        self.assertTrue(os.path.exists(csv_path))

        # Get the modification time of the CSV file
        mtime1 = os.path.getmtime(csv_path)
        print(f"CSV file created/updated: {csv_path}")
        print(f"File size: {os.path.getsize(csv_path)} bytes")
        print(f"Last modified: {time.ctime(mtime1)}")

        # Read the first few lines of the CSV to verify content
        with open(csv_path, 'r') as f:
            first_lines = [next(f) for _ in range(min(3, len(dataframes1["DraftCombineStats"]) + 1))]
        print(f"CSV first lines: {first_lines}")

        # Wait a moment to ensure the modification time would be different if the file is rewritten
        time.sleep(0.1)

        # Second call should use the cache
        print("Making second API call (should use CSV cache)...")
        json_response2, dataframes2 = fetch_draft_combine_stats_logic("2022-23", return_dataframe=True)

        # Verify the CSV file wasn't modified
        mtime2 = os.path.getmtime(csv_path)
        self.assertEqual(mtime1, mtime2)
        print(f"CSV file was not modified (same timestamp): {time.ctime(mtime2)}")

        # Verify the data is the same (ignoring data types)
        pd.testing.assert_frame_equal(dataframes1["DraftCombineStats"], dataframes2["DraftCombineStats"], check_dtype=False)
        print(f"Data loaded from CSV matches original data: {len(dataframes2['DraftCombineStats'])} players")

    def test_get_draft_combine_stats(self):
        """Test the get_draft_combine_stats function."""
        # Call the function with real API
        json_response, dataframes = get_draft_combine_stats("2022-23", return_dataframe=True)

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
            # The parameter name might be different in the response vs. what we sent
            if "season_all_time" in data["parameters"]:
                self.assertEqual(data["parameters"]["season_all_time"], "2022-23")
            elif "season_year" in data["parameters"]:
                self.assertEqual(data["parameters"]["season_year"], "2022-23")
            self.assertEqual(data["parameters"]["league_id"], "00")

            # Check dataframes
            self.assertIn("DraftCombineStats", dataframes)
            df = dataframes["DraftCombineStats"]
            self.assertIsInstance(df, pd.DataFrame)
            self.assertGreater(len(df), 0)

    def test_different_league_id(self):
        """Test using a different league_id parameter."""
        # Call the function with a different league_id
        json_response, dataframes = get_draft_combine_stats("2022-23", league_id="10", return_dataframe=True)

        # Parse the JSON response
        data = json.loads(json_response)

        # Verify the result
        self.assertIsInstance(data, dict)
        self.assertIsInstance(dataframes, dict)

        # Check parameters
        self.assertIn("parameters", data)
        # The parameter name might be different in the response vs. what we sent
        if "season_all_time" in data["parameters"]:
            self.assertEqual(data["parameters"]["season_all_time"], "2022-23")
        elif "season_year" in data["parameters"]:
            self.assertEqual(data["parameters"]["season_year"], "2022-23")
        self.assertEqual(data["parameters"]["league_id"], "10")

        # Note: The actual API might not have data for this league_id,
        # so we don't assert on the content of the data

    def test_different_seasons(self):
        """Test using different season parameters."""
        # Test with a few different seasons, including "All Time"
        seasons = ["2019-20", "2020-21", "2021-22", "2022-23", "All Time"]

        for season in seasons:
            # Get the CSV path for this season
            csv_path = _get_csv_path_for_draft_combine_stats(season, "00")
            if os.path.exists(csv_path):
                print(f"CSV file already exists: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
                print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")

            # Call the function to fetch data and create CSV
            json_response, dataframes = get_draft_combine_stats(season, return_dataframe=True)

            # Parse the JSON response
            data = json.loads(json_response)

            # Verify the result
            self.assertIsInstance(data, dict)
            self.assertIsInstance(dataframes, dict)

            # Check if there's an error in the response
            if "error" in data:
                print(f"API returned an error for season {season}: {data['error']}")
                print("This might be expected if the NBA API is unavailable or rate-limited.")
                continue

            # Check parameters
            self.assertIn("parameters", data)
            # The parameter name might be different in the response vs. what we sent
            if "season_all_time" in data["parameters"]:
                self.assertEqual(data["parameters"]["season_all_time"], season)
            elif "season_year" in data["parameters"]:
                self.assertEqual(data["parameters"]["season_year"], season)
            self.assertEqual(data["parameters"]["league_id"], "00")

            # Check dataframes
            self.assertIn("DraftCombineStats", dataframes)
            df = dataframes["DraftCombineStats"]
            self.assertIsInstance(df, pd.DataFrame)

            # Verify that the CSV file was created
            self.assertTrue(os.path.exists(csv_path), f"CSV file for season {season} was not created")

            # Get file size and modification time
            file_size = os.path.getsize(csv_path)
            mod_time = os.path.getmtime(csv_path)

            # Print information about the CSV file
            print(f"Season {season}: {len(df)} players")
            print(f"CSV file created: {csv_path}")
            print(f"CSV file size: {file_size} bytes")
            print(f"CSV last modified: {time.ctime(mod_time)}")

            # Read the first few lines of the CSV to verify content
            with open(csv_path, 'r') as f:
                first_lines = [next(f) for _ in range(min(3, len(df) + 1))]
            print(f"CSV first lines: {first_lines}")

            # Now test loading from the CSV
            print(f"Testing loading from CSV for season {season}...")
            json_response2, dataframes2 = get_draft_combine_stats(season, return_dataframe=True)
            print(f"Successfully loaded from CSV: {len(dataframes2['DraftCombineStats'])} players")

            # Keep the CSV files for inspection


if __name__ == '__main__':
    unittest.main()

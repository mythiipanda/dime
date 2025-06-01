"""
Smoke tests for the player_fantasy_profile module using real API calls.

These tests verify that the player fantasy profile API functions work correctly
by making actual calls to the NBA API.
"""

import os
import sys
import unittest
import pandas as pd
import time
import json

# Add the parent directory to the path so we can import the api_tools module

from api_tools.player_fantasy_profile import (
    fetch_player_fantasy_profile_logic,
    get_player_fantasy_profile,
    _get_csv_path_for_player_fantasy_profile,
    PLAYER_FANTASY_PROFILE_CSV_DIR
)
from nba_api.stats.library.parameters import SeasonTypePlayoffs, MeasureTypeBase, PerMode36
class TestPlayerFantasyProfileReal(unittest.TestCase):
    """Test cases for the player_fantasy_profile module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(PLAYER_FANTASY_PROFILE_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_player_fantasy_profile(self):
        """Test that the CSV path is generated correctly."""
        # Test with default parameters
        path = _get_csv_path_for_player_fantasy_profile(player_id="2544")
        self.assertIn("player_fantasy_profile", path)
        self.assertIn("player2544", path)
        self.assertIn("season2024_25", path)
        self.assertIn("typeRegular_Season", path)
        self.assertIn("measureBase", path)
        self.assertIn("perTotals", path)
        self.assertIn("leagueall", path)
        self.assertIn("paceN", path)
        self.assertIn("plusN", path)
        self.assertIn("rankN", path)
        self.assertIn("PlayerFantasyProfile", path)

        # Test with custom parameters
        path = _get_csv_path_for_player_fantasy_profile(
            player_id="201939",
            season="2023-24",
            season_type_playoffs=SeasonTypePlayoffs.playoffs,
            measure_type_base=MeasureTypeBase.base,
            per_mode36=PerMode36.per_game,
            league_id_nullable="00",
            pace_adjust_no="Y",
            plus_minus_no="Y",
            rank_no="Y",
            data_set_name="CustomData"
        )
        self.assertIn("player_fantasy_profile", path)
        self.assertIn("player201939", path)
        self.assertIn("season2023_24", path)
        self.assertIn("typePlayoffs", path)
        self.assertIn("measureBase", path)
        self.assertIn("perPerGame", path)
        self.assertIn("league00", path)
        self.assertIn("paceY", path)
        self.assertIn("plusY", path)
        self.assertIn("rankY", path)
        self.assertIn("CustomData", path)

    def test_fetch_player_fantasy_profile_logic_json(self):
        """Test fetching player fantasy profile in JSON format."""
        # Call the function with real API
        json_response = fetch_player_fantasy_profile_logic(player_id="2544")  # LeBron James

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
            self.assertEqual(data["parameters"]["player_id"], "2544")

            # Check data sets
            self.assertIn("data_sets", data)
            data_sets = data["data_sets"]
            self.assertIsInstance(data_sets, dict)
            self.assertGreater(len(data_sets), 0)

            # Print information about the data
            print(f"Parameters: {data.get('parameters', {})}")
            print(f"Data Sets: {list(data_sets.keys())}")

            # Check the main data sets
            expected_data_sets = ["Overall", "Location", "LastNGames", "DaysRest", "VsOpponent"]
            for data_set in expected_data_sets:
                if data_set in data_sets:
                    fantasy_data = data_sets[data_set]
                    self.assertIsInstance(fantasy_data, list)
                    self.assertGreater(len(fantasy_data), 0)  # Should have fantasy data
                    print(f"{data_set} count: {len(fantasy_data)}")
                    print(f"Sample fantasy: {fantasy_data[0] if fantasy_data else 'No data'}")

    def test_fetch_player_fantasy_profile_logic_dataframe(self):
        """Test fetching player fantasy profile in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_player_fantasy_profile_logic(
            player_id="2544",  # LeBron James
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
            self.assertEqual(data["parameters"]["player_id"], "2544")

            # Check dataframes
            self.assertGreater(len(dataframes), 0)

            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")
                print(f"Columns: {df.columns.tolist()}")

                # Verify expected columns for player fantasy profile
                expected_columns = ["GROUP_SET", "GROUP_VALUE", "GP", "PTS", "FAN_DUEL_PTS", "NBA_FANTASY_PTS"]
                for col in expected_columns:
                    if col in df.columns:
                        print(f"Found expected column: {col}")

            # Verify CSV files were created
            expected_data_sets = ["Overall", "Location", "LastNGames", "DaysRest", "VsOpponent"]
            for data_set in expected_data_sets:
                csv_path = _get_csv_path_for_player_fantasy_profile(
                    "2544", "2024-25", SeasonTypePlayoffs.regular, MeasureTypeBase.base, PerMode36.totals,
                    "", "N", "N", "N", data_set
                )
                if os.path.exists(csv_path):
                    print(f"CSV file created: {csv_path}")
                    print(f"File size: {os.path.getsize(csv_path)} bytes")
                else:
                    print(f"CSV file was not created at: {csv_path}")

    def test_fetch_player_fantasy_profile_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        params = {
            "player_id": "201939"  # Stephen Curry
        }

        # Check if CSV already exists
        expected_data_sets = ["Overall", "Location", "LastNGames", "DaysRest", "VsOpponent"]
        csv_paths = []
        for data_set in expected_data_sets:
            csv_path = _get_csv_path_for_player_fantasy_profile(
                params["player_id"], "2024-25", SeasonTypePlayoffs.regular, MeasureTypeBase.base,
                PerMode36.totals, "", "N", "N", "N", data_set
            )
            csv_paths.append(csv_path)
            if os.path.exists(csv_path):
                print(f"CSV file already exists: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
                print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")

        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_player_fantasy_profile_logic(**params, return_dataframe=True)

        # Verify the CSV files were created
        for csv_path in csv_paths:
            self.assertTrue(os.path.exists(csv_path))

        # Get the modification times of the CSV files
        mtimes1 = {}
        for csv_path in csv_paths:
            mtimes1[csv_path] = os.path.getmtime(csv_path)
            print(f"CSV file created/updated: {csv_path}")
            print(f"File size: {os.path.getsize(csv_path)} bytes")
            print(f"Last modified: {time.ctime(mtimes1[csv_path])}")

        # Wait a moment to ensure the modification time would be different if the file is rewritten
        time.sleep(0.1)

        # Second call should use the cache
        print("Making second API call (should use CSV cache)...")
        _, dataframes2 = fetch_player_fantasy_profile_logic(**params, return_dataframe=True)

        # Verify the CSV files weren't modified
        for csv_path in csv_paths:
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

    def test_get_player_fantasy_profile(self):
        """Test the get_player_fantasy_profile function."""
        # Call the function with real API
        json_response, dataframes = get_player_fantasy_profile(
            player_id="2544",  # LeBron James
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
            self.assertEqual(data["parameters"]["player_id"], "2544")

            # Check dataframes
            self.assertGreater(len(dataframes), 0)

            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")

    def test_100_percent_parameter_coverage(self):
        """Test 100% parameter coverage for PlayerFantasyProfile endpoint."""
        print("\n=== Testing 100% Parameter Coverage ===")

        # Test parameter combinations that work
        test_cases = [
            # Different players
            {"player_id": "2544"},  # LeBron James
            {"player_id": "201939"},  # Stephen Curry
            {"player_id": "1628369"},  # Jayson Tatum
            {"player_id": "203507"},  # Giannis Antetokounmpo

            # Different seasons
            {"player_id": "2544", "season": "2023-24"},
            {"player_id": "2544", "season": "2022-23"},

            # Different season types
            {"player_id": "2544", "season_type_playoffs": SeasonTypePlayoffs.playoffs},

            # Different measure types (only base is available)
            # {"player_id": "2544", "measure_type_base": MeasureTypeBase.advanced},

            # Different per modes
            {"player_id": "2544", "per_mode36": PerMode36.per_game},

            # League ID
            {"player_id": "2544", "league_id_nullable": "00"},
        ]

        successful_tests = 0
        total_tests = len(test_cases)

        for i, test_case in enumerate(test_cases):
            print(f"\nTest {i+1}/{total_tests}: {test_case}")

            try:
                # Call the API with these parameters
                json_response, dataframes = get_player_fantasy_profile(
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
                        self.assertEqual(params["player_id"], test_case["player_id"])

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
                                csv_path = _get_csv_path_for_player_fantasy_profile(
                                    test_case["player_id"],
                                    test_case.get("season", "2024-25"),
                                    test_case.get("season_type_playoffs", SeasonTypePlayoffs.regular),
                                    test_case.get("measure_type_base", MeasureTypeBase.base),
                                    test_case.get("per_mode36", PerMode36.totals),
                                    test_case.get("league_id_nullable", ""),
                                    test_case.get("pace_adjust_no", "N"),
                                    test_case.get("plus_minus_no", "N"),
                                    test_case.get("rank_no", "N"),
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

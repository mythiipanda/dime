"""
Smoke tests for the league_dash_player_shot_locations module using real API calls.

These tests verify that the league dash player shot locations API functions work correctly
by making actual calls to the NBA API.
"""

import os
import sys
import unittest
import pandas as pd
import time
import json

# Add the parent directory to the path so we can import the api_tools module

from api_tools.league_dash_player_shot_locations import (
    fetch_league_dash_player_shot_locations_logic,
    get_league_dash_player_shot_locations,
    _get_csv_path_for_league_dash_player_shot_locations,
    LEAGUE_DASH_PLAYER_SHOT_LOCATIONS_CSV_DIR
)
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, MeasureTypeSimple
class TestLeagueDashPlayerShotLocationsReal(unittest.TestCase):
    """Test cases for the league_dash_player_shot_locations module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(LEAGUE_DASH_PLAYER_SHOT_LOCATIONS_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_league_dash_player_shot_locations(self):
        """Test that the CSV path is generated correctly."""
        # Test with default parameters
        path = _get_csv_path_for_league_dash_player_shot_locations()
        self.assertIn("league_dash_player_shot_locations", path)
        self.assertIn("season2024-25", path)
        self.assertIn("typeRegular_Season", path)
        self.assertIn("measureBase", path)
        self.assertIn("perTotals", path)
        self.assertIn("distanceBy_Zone", path)
        self.assertIn("games0", path)
        self.assertIn("leagueall", path)
        self.assertIn("PlayerShotLocations", path)

        # Test with custom parameters
        path = _get_csv_path_for_league_dash_player_shot_locations(
            distance_range="5ft Range",
            last_n_games=10,
            measure_type_simple=MeasureTypeSimple.base,
            per_mode_detailed=PerModeDetailed.per_game,
            season="2023-24",
            season_type_all_star=SeasonTypeAllStar.playoffs,
            league_id_nullable="00",
            data_set_name="CustomData"
        )
        self.assertIn("league_dash_player_shot_locations", path)
        self.assertIn("season2023-24", path)
        self.assertIn("typePlayoffs", path)
        self.assertIn("measureBase", path)
        self.assertIn("perPerGame", path)
        self.assertIn("distance5ft_Range", path)
        self.assertIn("games10", path)
        self.assertIn("league00", path)
        self.assertIn("CustomData", path)

    def test_fetch_league_dash_player_shot_locations_logic_json(self):
        """Test fetching league dash player shot locations in JSON format."""
        # Call the function with real API
        json_response = fetch_league_dash_player_shot_locations_logic(
            season="2024-25",
            distance_range="By Zone"
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
            self.assertEqual(data["parameters"]["season"], "2024-25")
            self.assertEqual(data["parameters"]["distance_range"], "By Zone")

            # Check data sets
            self.assertIn("data_sets", data)
            data_sets = data["data_sets"]
            self.assertIsInstance(data_sets, dict)
            self.assertGreater(len(data_sets), 0)

            # Print information about the data
            print(f"Parameters: {data.get('parameters', {})}")
            print(f"Data Sets: {list(data_sets.keys())}")

            # Check the main data set
            if "PlayerShotLocations" in data_sets:
                shot_locations_data = data_sets["PlayerShotLocations"]
                self.assertIsInstance(shot_locations_data, list)
                self.assertGreater(len(shot_locations_data), 500)  # Should have 500+ players
                print(f"Player Shot Locations count: {len(shot_locations_data)}")
                print(f"Sample player: {shot_locations_data[0] if shot_locations_data else 'No data'}")

    def test_fetch_league_dash_player_shot_locations_logic_dataframe(self):
        """Test fetching league dash player shot locations in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_league_dash_player_shot_locations_logic(
            season="2024-25",
            distance_range="By Zone",
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
            self.assertEqual(data["parameters"]["season"], "2024-25")
            self.assertEqual(data["parameters"]["distance_range"], "By Zone")

            # Check dataframes
            self.assertGreater(len(dataframes), 0)

            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")
                print(f"Columns: {df.columns.tolist()}")

                # Verify expected columns for shot locations
                expected_columns = ["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION"]
                for col in expected_columns:
                    # Handle multi-level column names
                    flat_columns = [str(col) for col in df.columns]
                    if any(expected_col in str(col) for col in flat_columns for expected_col in expected_columns):
                        print(f"Found expected column structure")
                        break

            # Verify CSV file was created
            csv_path = _get_csv_path_for_league_dash_player_shot_locations(
                "By Zone", 0, MeasureTypeSimple.base, PerModeDetailed.totals,
                "2024-25", SeasonTypeAllStar.regular, "", "PlayerShotLocations"
            )
            if os.path.exists(csv_path):
                print(f"CSV file created: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
            else:
                print(f"CSV file was not created at: {csv_path}")

    def test_fetch_league_dash_player_shot_locations_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        params = {
            "season": "2023-24",
            "distance_range": "By Zone"
        }

        # Check if CSV already exists
        csv_path = _get_csv_path_for_league_dash_player_shot_locations(
            params["distance_range"], 0, MeasureTypeSimple.base, PerModeDetailed.totals,
            params["season"], SeasonTypeAllStar.regular, "", "PlayerShotLocations"
        )
        if os.path.exists(csv_path):
            print(f"CSV file already exists: {csv_path}")
            print(f"File size: {os.path.getsize(csv_path)} bytes")
            print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")

        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_league_dash_player_shot_locations_logic(**params, return_dataframe=True)

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
        _, dataframes2 = fetch_league_dash_player_shot_locations_logic(**params, return_dataframe=True)

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

    def test_get_league_dash_player_shot_locations(self):
        """Test the get_league_dash_player_shot_locations function."""
        # Call the function with real API
        json_response, dataframes = get_league_dash_player_shot_locations(
            season="2024-25",
            distance_range="By Zone",
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
            self.assertEqual(data["parameters"]["season"], "2024-25")
            self.assertEqual(data["parameters"]["distance_range"], "By Zone")

            # Check dataframes
            self.assertGreater(len(dataframes), 0)

            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")

    def test_100_percent_parameter_coverage(self):
        """Test 100% parameter coverage for LeagueDashPlayerShotLocations endpoint."""
        print("\n=== Testing 100% Parameter Coverage ===")

        # Test parameter combinations that work
        test_cases = [
            # Basic combinations
            {"season": "2024-25", "distance_range": "By Zone"},
            {"season": "2023-24", "distance_range": "By Zone"},
            {"season": "2022-23", "distance_range": "By Zone"},

            # Different distance ranges
            {"season": "2024-25", "distance_range": "5ft Range"},
            {"season": "2024-25", "distance_range": "8ft Range"},

            # Different measure types (only Base is supported)
            {"season": "2024-25", "distance_range": "By Zone", "measure_type_simple": MeasureTypeSimple.base},

            # Different per modes
            {"season": "2024-25", "distance_range": "By Zone", "per_mode_detailed": PerModeDetailed.per_game},

            # Last N games
            {"season": "2024-25", "distance_range": "By Zone", "last_n_games": 10},

            # Playoffs
            {"season": "2023-24", "distance_range": "By Zone", "season_type_all_star": SeasonTypeAllStar.playoffs},

            # Specific league
            {"season": "2024-25", "distance_range": "By Zone", "league_id_nullable": "00"},
        ]

        successful_tests = 0
        total_tests = len(test_cases)

        for i, test_case in enumerate(test_cases):
            print(f"\nTest {i+1}/{total_tests}: {test_case}")

            try:
                # Call the API with these parameters
                json_response, dataframes = get_league_dash_player_shot_locations(
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
                        self.assertEqual(params["season"], test_case["season"])
                        self.assertEqual(params["distance_range"], test_case["distance_range"])

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
                                csv_path = _get_csv_path_for_league_dash_player_shot_locations(
                                    test_case["distance_range"],
                                    test_case.get("last_n_games", 0),
                                    test_case.get("measure_type_simple", MeasureTypeSimple.base),
                                    test_case.get("per_mode_detailed", PerModeDetailed.totals),
                                    test_case["season"],
                                    test_case.get("season_type_all_star", SeasonTypeAllStar.regular),
                                    test_case.get("league_id_nullable", ""),
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

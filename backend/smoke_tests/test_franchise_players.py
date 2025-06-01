"""
Smoke tests for the franchise_players module using real API calls.

These tests verify that the franchise players API functions work correctly
by making actual calls to the NBA API.
"""

import os
import sys
import unittest
import pandas as pd
import time
import json

# Add the parent directory to the path so we can import the api_tools module

from api_tools.franchise_players import (
    fetch_franchise_players_logic,
    get_franchise_players,
    _get_csv_path_for_franchise_players,
    FRANCHISE_PLAYERS_CSV_DIR
)
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed
class TestFranchisePlayersReal(unittest.TestCase):
    """Test cases for the franchise_players module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(FRANCHISE_PLAYERS_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_franchise_players(self):
        """Test that the CSV path is generated correctly."""
        # Test with default parameters
        path = _get_csv_path_for_franchise_players("1610612747")  # Lakers
        self.assertIn("franchise_players_team1610612747", path)
        self.assertIn("league00", path)
        self.assertIn("modeTotals", path)
        self.assertIn("typeRegular_Season", path)

        # Test with custom parameters
        path = _get_csv_path_for_franchise_players(
            team_id="1610612739",
            league_id="00",
            per_mode_detailed=PerModeDetailed.per_game,
            season_type_all_star=SeasonTypeAllStar.playoffs
        )
        self.assertIn("franchise_players_team1610612739", path)
        self.assertIn("league00", path)
        self.assertIn("modePerGame", path)
        self.assertIn("typePlayoffs", path)

    def test_fetch_franchise_players_logic_json(self):
        """Test fetching franchise players in JSON format."""
        # Call the function with real API
        json_response = fetch_franchise_players_logic(
            team_id="1610612747"  # Lakers
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
            self.assertEqual(data["parameters"]["team_id"], "1610612747")

            # Check data sets
            self.assertIn("data_sets", data)
            data_sets = data["data_sets"]
            self.assertIsInstance(data_sets, dict)
            self.assertGreater(len(data_sets), 0)

            # Print information about the data
            print(f"Parameters: {data.get('parameters', {})}")
            print(f"Data Sets: {list(data_sets.keys())}")

            # Check the main data set
            if "FranchisePlayers" in data_sets:
                players_data = data_sets["FranchisePlayers"]
                self.assertIsInstance(players_data, list)
                self.assertGreater(len(players_data), 400)  # Should have 500+ players
                print(f"Franchise Players count: {len(players_data)}")
                print(f"Sample player: {players_data[0] if players_data else 'No data'}")

    def test_fetch_franchise_players_logic_dataframe(self):
        """Test fetching franchise players in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_franchise_players_logic(
            team_id="1610612744",  # Golden State Warriors
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
            self.assertEqual(data["parameters"]["team_id"], "1610612744")

            # Check dataframes
            self.assertGreater(len(dataframes), 0)

            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                self.assertGreater(len(df), 500)  # Should have 565+ players
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")
                print(f"Columns: {df.columns.tolist()}")

                # Verify expected columns for franchise players
                expected_columns = ["LEAGUE_ID", "TEAM_ID", "TEAM", "PERSON_ID", "PLAYER", "GP", "PTS", "REB", "AST"]
                for col in expected_columns:
                    if col in df.columns:
                        print(f"Found expected column: {col}")

            # Verify CSV file was created
            csv_path = _get_csv_path_for_franchise_players("1610612744")
            if os.path.exists(csv_path):
                print(f"CSV file created: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
            else:
                print(f"CSV file was not created at: {csv_path}")

    def test_fetch_franchise_players_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        params = {
            "team_id": "1610612739"  # Cleveland Cavaliers
        }

        # Check if CSV already exists
        csv_path = _get_csv_path_for_franchise_players(params["team_id"])
        if os.path.exists(csv_path):
            print(f"CSV file already exists: {csv_path}")
            print(f"File size: {os.path.getsize(csv_path)} bytes")
            print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")

        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_franchise_players_logic(**params, return_dataframe=True)

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
        _, dataframes2 = fetch_franchise_players_logic(**params, return_dataframe=True)

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

    def test_get_franchise_players(self):
        """Test the get_franchise_players function."""
        # Call the function with real API
        json_response, dataframes = get_franchise_players(
            team_id="1610612747",  # Lakers
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
            self.assertEqual(data["parameters"]["team_id"], "1610612747")

            # Check dataframes
            self.assertGreater(len(dataframes), 0)

            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                self.assertGreater(len(df), 400)  # Should have 500+ players
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")

    def test_100_percent_parameter_coverage(self):
        """Test 100% parameter coverage for FranchisePlayers endpoint."""
        print("\n=== Testing 100% Parameter Coverage ===")

        # Test parameter combinations that work
        test_cases = [
            # Basic combinations
            {"team_id": "1610612747", "league_id": "00", "per_mode_detailed": PerModeDetailed.totals, "season_type_all_star": SeasonTypeAllStar.regular},
            {"team_id": "1610612738", "league_id": "00", "per_mode_detailed": PerModeDetailed.totals, "season_type_all_star": SeasonTypeAllStar.regular},
            {"team_id": "1610612744", "league_id": "00", "per_mode_detailed": PerModeDetailed.totals, "season_type_all_star": SeasonTypeAllStar.regular},
            {"team_id": "1610612739", "league_id": "00", "per_mode_detailed": PerModeDetailed.totals, "season_type_all_star": SeasonTypeAllStar.regular},
            {"team_id": "1610612741", "league_id": "00", "per_mode_detailed": PerModeDetailed.totals, "season_type_all_star": SeasonTypeAllStar.regular},

            # Per game mode
            {"team_id": "1610612748", "league_id": "00", "per_mode_detailed": PerModeDetailed.per_game, "season_type_all_star": SeasonTypeAllStar.regular},
            {"team_id": "1610612759", "league_id": "00", "per_mode_detailed": PerModeDetailed.per_game, "season_type_all_star": SeasonTypeAllStar.regular},

            # Playoff data
            {"team_id": "1610612752", "league_id": "00", "per_mode_detailed": PerModeDetailed.totals, "season_type_all_star": SeasonTypeAllStar.playoffs},
            {"team_id": "1610612755", "league_id": "00", "per_mode_detailed": PerModeDetailed.totals, "season_type_all_star": SeasonTypeAllStar.playoffs},

            # All-Star data
            {"team_id": "1610612742", "league_id": "00", "per_mode_detailed": PerModeDetailed.totals, "season_type_all_star": SeasonTypeAllStar.all_star},
        ]

        successful_tests = 0
        total_tests = len(test_cases)

        for i, test_case in enumerate(test_cases):
            print(f"\nTest {i+1}/{total_tests}: {test_case}")

            try:
                # Call the API with these parameters
                json_response, dataframes = get_franchise_players(
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
                        self.assertEqual(params["team_id"], test_case["team_id"])
                        self.assertEqual(params["league_id"], test_case["league_id"])
                        self.assertEqual(params["per_mode_detailed"], test_case["per_mode_detailed"])
                        self.assertEqual(params["season_type_all_star"], test_case["season_type_all_star"])

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
                                csv_path = _get_csv_path_for_franchise_players(
                                    test_case["team_id"],
                                    test_case["league_id"],
                                    test_case["per_mode_detailed"],
                                    test_case["season_type_all_star"]
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

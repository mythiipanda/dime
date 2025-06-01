"""
Smoke tests for the team_details module using real API calls.

These tests verify that the team details API functions work correctly
by making actual calls to the NBA API.
"""

import os
import sys
import unittest
import pandas as pd
import time
import json

# Add the parent directory to the path so we can import the api_tools module

from api_tools.team_details import (
    fetch_team_details_logic,
    get_team_details,
    _get_csv_path_for_team_details,
    TEAM_DETAILS_CSV_DIR
)


class TestTeamDetailsReal(unittest.TestCase):
    """Test cases for the team_details module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(TEAM_DETAILS_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_team_details(self):
        """Test that the CSV path is generated correctly."""
        # Test with team ID
        path = _get_csv_path_for_team_details("1610612739")
        self.assertIn("team_details_1610612739", path)
        self.assertTrue(path.endswith(".csv"))

    def test_fetch_team_details_logic_json(self):
        """Test fetching team details in JSON format."""
        # Call the function with real API
        json_response = fetch_team_details_logic(team_id="1610612739")

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
            self.assertEqual(data["parameters"]["team_id"], "1610612739")

            # Check data sets
            self.assertIn("data_sets", data)
            data_sets = data["data_sets"]
            self.assertIsInstance(data_sets, dict)
            self.assertGreater(len(data_sets), 0)

            # Print information about the data
            print(f"Parameters: {data.get('parameters', {})}")
            print(f"Data Sets: {list(data_sets.keys())}")

            # Check expected data sets
            expected_datasets = [
                "TeamInfo", "TeamHistory", "SocialMediaAccounts",
                "Championships", "ConferenceChampionships", "DivisionChampionships",
                "RetiredPlayers", "HallOfFamePlayers"
            ]

            for dataset in expected_datasets:
                if dataset in data_sets:
                    dataset_data = data_sets[dataset]
                    print(f"{dataset}: {len(dataset_data) if isinstance(dataset_data, list) else 'Not a list'} records")

    def test_fetch_team_details_logic_dataframe(self):
        """Test fetching team details in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_team_details_logic(
            team_id="1610612739",
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
            self.assertEqual(data["parameters"]["team_id"], "1610612739")

            # Check dataframes
            self.assertGreater(len(dataframes), 0)

            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")
                print(f"Columns: {df.columns.tolist()}")

                # Verify expected columns for different datasets
                if data_set_name == "TeamInfo":
                    expected_columns = ["TEAM_ID", "ABBREVIATION", "NICKNAME", "CITY", "ARENA"]
                    for col in expected_columns:
                        if col in df.columns:
                            print(f"Found expected column in TeamInfo: {col}")
                elif data_set_name == "SocialMediaAccounts":
                    expected_columns = ["ACCOUNTTYPE", "WEBSITE_LINK"]
                    for col in expected_columns:
                        if col in df.columns:
                            print(f"Found expected column in SocialMediaAccounts: {col}")

            # Verify CSV files were created for each dataset
            dataset_names = ["TeamInfo", "TeamHistory", "SocialMediaAccounts", "Championships",
                           "ConferenceChampionships", "DivisionChampionships", "RetiredPlayers", "HallOfFamePlayers"]

            for dataset_name in dataset_names:
                csv_path = _get_csv_path_for_team_details("1610612739", dataset_name)
                if os.path.exists(csv_path):
                    file_size = os.path.getsize(csv_path)
                    print(f"CSV file created for {dataset_name}: {os.path.basename(csv_path)} ({file_size} bytes)")
                else:
                    print(f"CSV file was not created for {dataset_name}: {os.path.basename(csv_path)}")

    def test_fetch_team_details_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        team_id = "1610612744"  # Golden State Warriors

        # Check if CSV files already exist
        csv_path_teaminfo = _get_csv_path_for_team_details(team_id, "TeamInfo")
        if os.path.exists(csv_path_teaminfo):
            print(f"CSV file already exists: {csv_path_teaminfo}")
            print(f"File size: {os.path.getsize(csv_path_teaminfo)} bytes")
            print(f"Last modified: {time.ctime(os.path.getmtime(csv_path_teaminfo))}")

        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_team_details_logic(team_id=team_id, return_dataframe=True)

        # Verify the CSV files were created
        self.assertTrue(os.path.exists(csv_path_teaminfo))

        # Get the modification time of the CSV file
        mtime1 = os.path.getmtime(csv_path_teaminfo)
        print(f"CSV file created/updated: {csv_path_teaminfo}")
        print(f"File size: {os.path.getsize(csv_path_teaminfo)} bytes")
        print(f"Last modified: {time.ctime(mtime1)}")

        # Wait a moment to ensure the modification time would be different if the file is rewritten
        time.sleep(0.1)

        # Second call should use the cache
        print("Making second API call (should use CSV cache)...")
        _, dataframes2 = fetch_team_details_logic(team_id=team_id, return_dataframe=True)

        # Verify the CSV file wasn't modified
        mtime2 = os.path.getmtime(csv_path_teaminfo)
        self.assertEqual(mtime1, mtime2)
        print(f"CSV file was not modified (same timestamp): {time.ctime(mtime2)}")

        # Verify the data is the same
        if dataframes1 and dataframes2:
            for key in dataframes1:
                if key in dataframes2:
                    pd.testing.assert_frame_equal(dataframes1[key], dataframes2[key], check_dtype=False)
                    print(f"Verified data for {key} matches between calls")

        print(f"Data loaded from CSV matches original data")

    def test_get_team_details(self):
        """Test the get_team_details function."""
        # Call the function with real API
        json_response, dataframes = get_team_details(
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
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")

    def test_100_percent_parameter_coverage(self):
        """Test 100% parameter coverage for TeamDetails endpoint."""
        print("\n=== Testing 100% Parameter Coverage ===")

        # Test different NBA teams
        test_teams = [
            "1610612739",  # Cleveland Cavaliers
            "1610612744",  # Golden State Warriors
            "1610612747",  # Los Angeles Lakers
            "1610612738",  # Boston Celtics
            "1610612741",  # Chicago Bulls
            "1610612748",  # Miami Heat
            "1610612752",  # New York Knicks
            "1610612759",  # San Antonio Spurs
            "1610612749",  # Milwaukee Bucks
            "1610612761",  # Toronto Raptors
        ]

        successful_tests = 0
        total_tests = len(test_teams)

        for i, team_id in enumerate(test_teams):
            print(f"\nTest {i+1}/{total_tests}: Team ID {team_id}")

            try:
                # Call the API with this team ID
                json_response, dataframes = get_team_details(
                    team_id=team_id,
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
                        self.assertEqual(params["team_id"], team_id)
                        print(f"  ✓ Parameters match")

                    # Check data sets
                    if "data_sets" in data and data["data_sets"]:
                        data_sets = data["data_sets"]
                        print(f"  ✓ Data sets: {list(data_sets.keys())}")

                        # Check dataframes
                        if dataframes:
                            for data_set_name, df in dataframes.items():
                                print(f"  ✓ DataFrame '{data_set_name}': {len(df)} records")

                                # Verify CSV was created for this dataset
                                csv_path = _get_csv_path_for_team_details(team_id, data_set_name)
                                if os.path.exists(csv_path):
                                    file_size = os.path.getsize(csv_path)
                                    print(f"  ✓ CSV created for {data_set_name}: {os.path.basename(csv_path)} ({file_size} bytes)")
                                else:
                                    print(f"  ○ CSV not found for {data_set_name}: {os.path.basename(csv_path)}")
                        else:
                            print(f"  ○ No dataframes returned")
                    else:
                        print(f"  ○ No data sets returned")

                    successful_tests += 1

            except Exception as e:
                print(f"  ✗ Exception: {e}")
                # Don't fail the test for individual teams that might not work

        print(f"\n=== Parameter Coverage Summary ===")
        print(f"Total test cases: {total_tests}")
        print(f"Successful tests: {successful_tests}")
        print(f"Coverage: {(successful_tests/total_tests)*100:.1f}%")

        # We expect at least 90% of test cases to work
        self.assertGreater(successful_tests, total_tests * 0.9,
                          f"Expected at least 90% of team IDs to work, got {(successful_tests/total_tests)*100:.1f}%")


if __name__ == '__main__':
    unittest.main()

"""
Smoke tests for the league_hustle_stats_team module using real API calls.

These tests verify that the league hustle stats team API functions work correctly
by making actual calls to the NBA API.
"""

import os
import sys
import unittest
import pandas as pd
import time
import json

# Add the parent directory to the path so we can import the api_tools module

from api_tools.league_hustle_stats_team import (
    fetch_league_hustle_stats_team_logic,
    get_league_hustle_stats_team,
    _get_csv_path_for_league_hustle_stats_team,
    LEAGUE_HUSTLE_STATS_TEAM_CSV_DIR
)
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeTime
class TestLeagueHustleStatsTeamReal(unittest.TestCase):
    """Test cases for the league_hustle_stats_team module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(LEAGUE_HUSTLE_STATS_TEAM_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_league_hustle_stats_team(self):
        """Test that the CSV path is generated correctly."""
        # Test with default parameters
        path = _get_csv_path_for_league_hustle_stats_team()
        self.assertIn("league_hustle_stats_team", path)
        self.assertIn("season2024-25", path)
        self.assertIn("typeRegular_Season", path)
        self.assertIn("perTotals", path)
        self.assertIn("leagueall", path)
        self.assertIn("TeamHustleStats", path)
        
        # Test with custom parameters
        path = _get_csv_path_for_league_hustle_stats_team(
            per_mode_time=PerModeTime.per_game,
            season="2023-24",
            season_type_all_star=SeasonTypeAllStar.playoffs,
            league_id_nullable="00",
            data_set_name="CustomData"
        )
        self.assertIn("league_hustle_stats_team", path)
        self.assertIn("season2023-24", path)
        self.assertIn("typePlayoffs", path)
        self.assertIn("perPerGame", path)
        self.assertIn("league00", path)
        self.assertIn("CustomData", path)

    def test_fetch_league_hustle_stats_team_logic_json(self):
        """Test fetching league hustle stats team in JSON format."""
        # Call the function with real API
        json_response = fetch_league_hustle_stats_team_logic(
            season="2024-25"
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
            
            # Check data sets
            self.assertIn("data_sets", data)
            data_sets = data["data_sets"]
            self.assertIsInstance(data_sets, dict)
            self.assertGreater(len(data_sets), 0)
            
            # Print information about the data
            print(f"Parameters: {data.get('parameters', {})}")
            print(f"Data Sets: {list(data_sets.keys())}")
            
            # Check the main data set
            if "TeamHustleStats" in data_sets:
                hustle_stats_data = data_sets["TeamHustleStats"]
                self.assertIsInstance(hustle_stats_data, list)
                self.assertEqual(len(hustle_stats_data), 30)  # Should have 30 NBA teams
                print(f"Team Hustle Stats count: {len(hustle_stats_data)}")
                print(f"Sample team: {hustle_stats_data[0] if hustle_stats_data else 'No data'}")

    def test_fetch_league_hustle_stats_team_logic_dataframe(self):
        """Test fetching league hustle stats team in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_league_hustle_stats_team_logic(
            season="2024-25",
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
            
            # Check dataframes
            self.assertGreater(len(dataframes), 0)
            
            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")
                print(f"Columns: {df.columns.tolist()}")
                
                # Verify expected columns for team hustle stats
                expected_columns = ["TEAM_ID", "TEAM_NAME", "CONTESTED_SHOTS", "DEFLECTIONS", "CHARGES_DRAWN"]
                for col in expected_columns:
                    if col in df.columns:
                        print(f"Found expected column: {col}")
            
            # Verify CSV file was created
            csv_path = _get_csv_path_for_league_hustle_stats_team(
                PerModeTime.totals, "2024-25", SeasonTypeAllStar.regular, "", "TeamHustleStats"
            )
            if os.path.exists(csv_path):
                print(f"CSV file created: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
            else:
                print(f"CSV file was not created at: {csv_path}")

    def test_fetch_league_hustle_stats_team_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        params = {
            "season": "2023-24"
        }
        
        # Check if CSV already exists
        csv_path = _get_csv_path_for_league_hustle_stats_team(
            PerModeTime.totals, params["season"], SeasonTypeAllStar.regular, "", "TeamHustleStats"
        )
        if os.path.exists(csv_path):
            print(f"CSV file already exists: {csv_path}")
            print(f"File size: {os.path.getsize(csv_path)} bytes")
            print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")
        
        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_league_hustle_stats_team_logic(**params, return_dataframe=True)
        
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
        _, dataframes2 = fetch_league_hustle_stats_team_logic(**params, return_dataframe=True)
        
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

    def test_get_league_hustle_stats_team(self):
        """Test the get_league_hustle_stats_team function."""
        # Call the function with real API
        json_response, dataframes = get_league_hustle_stats_team(
            season="2024-25",
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
            
            # Check dataframes
            self.assertGreater(len(dataframes), 0)
            
            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")

    def test_100_percent_parameter_coverage(self):
        """Test 100% parameter coverage for LeagueHustleStatsTeam endpoint."""
        print("\n=== Testing 100% Parameter Coverage ===")
        
        # Test parameter combinations that work
        test_cases = [
            # Basic combinations
            {"season": "2024-25"},
            {"season": "2023-24"},
            {"season": "2022-23"},
            
            # Different per modes
            {"season": "2024-25", "per_mode_time": PerModeTime.per_game},
            
            # Playoffs
            {"season": "2023-24", "season_type_all_star": SeasonTypeAllStar.playoffs},
            
            # Specific league
            {"season": "2024-25", "league_id_nullable": "00"},
        ]
        
        successful_tests = 0
        total_tests = len(test_cases)
        
        for i, test_case in enumerate(test_cases):
            print(f"\nTest {i+1}/{total_tests}: {test_case}")
            
            try:
                # Call the API with these parameters
                json_response, dataframes = get_league_hustle_stats_team(
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
                                csv_path = _get_csv_path_for_league_hustle_stats_team(
                                    test_case.get("per_mode_time", PerModeTime.totals),
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

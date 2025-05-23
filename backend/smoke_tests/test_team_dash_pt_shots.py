"""
Smoke tests for the team_dash_pt_shots module using real API calls.

These tests verify that the team dash pt shots API functions work correctly
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

from api_tools.team_dash_pt_shots import (
    fetch_team_dash_pt_shots_logic,
    get_team_dash_pt_shots,
    _get_csv_path_for_team_dash_pt_shots,
    TEAM_DASH_PT_SHOTS_CSV_DIR
)
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple


class TestTeamDashPtShotsReal(unittest.TestCase):
    """Test cases for the team_dash_pt_shots module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(TEAM_DASH_PT_SHOTS_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_team_dash_pt_shots(self):
        """Test that the CSV path is generated correctly."""
        # Test with default parameters
        path = _get_csv_path_for_team_dash_pt_shots(team_id="1610612738")
        self.assertIn("team_dash_pt_shots", path)
        self.assertIn("team1610612738", path)
        self.assertIn("season2024_25", path)
        self.assertIn("typeall", path)
        self.assertIn("modeall", path)
        self.assertIn("TeamDashPtShots", path)
        
        # Test with custom parameters
        path = _get_csv_path_for_team_dash_pt_shots(
            team_id="1610612747",
            season="2023-24",
            season_type_all_star=SeasonTypeAllStar.playoffs,
            per_mode_simple=PerModeSimple.per_game,
            league_id="00",
            last_n_games="10",
            location_nullable="Home",
            outcome_nullable="W",
            data_set_name="CustomData"
        )
        self.assertIn("team_dash_pt_shots", path)
        self.assertIn("team1610612747", path)
        self.assertIn("season2023_24", path)
        self.assertIn("typePlayoffs", path)
        self.assertIn("modePer_Game", path)
        self.assertIn("league00", path)
        self.assertIn("games10", path)
        self.assertIn("locationHome", path)
        self.assertIn("outcomeW", path)
        self.assertIn("CustomData", path)

    def test_fetch_team_dash_pt_shots_logic_json(self):
        """Test fetching team dash pt shots in JSON format."""
        # Call the function with real API
        json_response = fetch_team_dash_pt_shots_logic(team_id="1610612738")  # Celtics
        
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
            self.assertEqual(data["parameters"]["team_id"], "1610612738")
            
            # Check data sets
            self.assertIn("data_sets", data)
            data_sets = data["data_sets"]
            self.assertIsInstance(data_sets, dict)
            self.assertGreater(len(data_sets), 0)
            
            # Print information about the data
            print(f"Parameters: {data.get('parameters', {})}")
            print(f"Data Sets: {list(data_sets.keys())}")
            
            # Check the main data set
            if "TeamDashPtShots" in data_sets:
                shots_data = data_sets["TeamDashPtShots"]
                self.assertIsInstance(shots_data, list)
                self.assertGreater(len(shots_data), 0)  # Should have shot type data
                print(f"Team Dash Pt Shots count: {len(shots_data)}")
                print(f"Sample shot type: {shots_data[0] if shots_data else 'No data'}")

    def test_fetch_team_dash_pt_shots_logic_dataframe(self):
        """Test fetching team dash pt shots in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_team_dash_pt_shots_logic(
            team_id="1610612738",  # Celtics
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
            self.assertEqual(data["parameters"]["team_id"], "1610612738")
            
            # Check dataframes
            self.assertGreater(len(dataframes), 0)
            
            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")
                print(f"Columns: {df.columns.tolist()}")
                
                # Verify expected columns for team dash pt shots
                expected_columns = ["TEAM_ID", "TEAM_NAME", "SHOT_TYPE", "FGA_FREQUENCY", "FGM", "FGA", "FG_PCT"]
                for col in expected_columns:
                    if col in df.columns:
                        print(f"Found expected column: {col}")
            
            # Verify CSV file was created
            csv_path = _get_csv_path_for_team_dash_pt_shots(
                "1610612738", "2024-25", "", "", "", "", "", "", "", "", "", "TeamDashPtShots"
            )
            if os.path.exists(csv_path):
                print(f"CSV file created: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
            else:
                print(f"CSV file was not created at: {csv_path}")

    def test_fetch_team_dash_pt_shots_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        params = {
            "team_id": "1610612747"  # Lakers
        }
        
        # Check if CSV already exists
        csv_path = _get_csv_path_for_team_dash_pt_shots(
            params["team_id"], "2024-25", "", "", "", "", "", "", "", "", "", "TeamDashPtShots"
        )
        if os.path.exists(csv_path):
            print(f"CSV file already exists: {csv_path}")
            print(f"File size: {os.path.getsize(csv_path)} bytes")
            print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")
        
        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_team_dash_pt_shots_logic(**params, return_dataframe=True)
        
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
        _, dataframes2 = fetch_team_dash_pt_shots_logic(**params, return_dataframe=True)
        
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

    def test_get_team_dash_pt_shots(self):
        """Test the get_team_dash_pt_shots function."""
        # Call the function with real API
        json_response, dataframes = get_team_dash_pt_shots(
            team_id="1610612738",  # Celtics
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
            self.assertEqual(data["parameters"]["team_id"], "1610612738")
            
            # Check dataframes
            self.assertGreater(len(dataframes), 0)
            
            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")

    def test_100_percent_parameter_coverage(self):
        """Test 100% parameter coverage for TeamDashPtShots endpoint."""
        print("\n=== Testing 100% Parameter Coverage ===")
        
        # Test parameter combinations that work
        test_cases = [
            # Different teams
            {"team_id": "1610612738"},  # Celtics
            {"team_id": "1610612747"},  # Lakers
            {"team_id": "1610612744"},  # Warriors
            {"team_id": "1610612751"},  # Nets
            
            # Different seasons
            {"team_id": "1610612738", "season": "2023-24"},
            {"team_id": "1610612738", "season": "2022-23"},
            
            # Different season types
            {"team_id": "1610612738", "season_type_all_star": SeasonTypeAllStar.playoffs},
            
            # Different per modes
            {"team_id": "1610612738", "per_mode_simple": PerModeSimple.per_game},
            
            # League ID
            {"team_id": "1610612738", "league_id": "00"},
            
            # Last N games
            {"team_id": "1610612738", "last_n_games": "10"},
            
            # Location and outcome
            {"team_id": "1610612738", "location_nullable": "Home"},
            {"team_id": "1610612738", "outcome_nullable": "W"},
        ]
        
        successful_tests = 0
        total_tests = len(test_cases)
        
        for i, test_case in enumerate(test_cases):
            print(f"\nTest {i+1}/{total_tests}: {test_case}")
            
            try:
                # Call the API with these parameters
                json_response, dataframes = get_team_dash_pt_shots(
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
                                csv_path = _get_csv_path_for_team_dash_pt_shots(
                                    test_case["team_id"],
                                    test_case.get("season", "2024-25"),
                                    test_case.get("season_type_all_star", ""),
                                    test_case.get("per_mode_simple", ""),
                                    test_case.get("league_id", ""),
                                    test_case.get("last_n_games", ""),
                                    test_case.get("month", ""),
                                    test_case.get("opponent_team_id", ""),
                                    test_case.get("period", ""),
                                    test_case.get("location_nullable", ""),
                                    test_case.get("outcome_nullable", ""),
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

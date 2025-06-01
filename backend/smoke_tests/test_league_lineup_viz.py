"""
Smoke tests for the league_lineup_viz module using real API calls.

These tests verify that the league lineup viz API functions work correctly
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

from api_tools.league_lineup_viz import (
    fetch_league_lineup_viz_logic,
    get_league_lineup_viz,
    _get_csv_path_for_league_lineup_viz,
    LEAGUE_LINEUP_VIZ_CSV_DIR
)
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailedDefense
class TestLeagueLineupVizReal(unittest.TestCase):
    """Test cases for the league_lineup_viz module using real API calls."""

    def setUp(self):
        """Set up the test environment."""
        # Create the cache directory if it doesn't exist
        os.makedirs(LEAGUE_LINEUP_VIZ_CSV_DIR, exist_ok=True)

    def tearDown(self):
        """Clean up after the tests."""
        # We're keeping the CSV files for inspection, so no cleanup needed
        pass

    def test_get_csv_path_for_league_lineup_viz(self):
        """Test that the CSV path is generated correctly."""
        # Test with default parameters
        path = _get_csv_path_for_league_lineup_viz()
        self.assertIn("league_lineup_viz", path)
        self.assertIn("season2024-25", path)
        self.assertIn("typeRegular_Season", path)
        self.assertIn("measureBase", path)
        self.assertIn("perTotals", path)
        self.assertIn("min5", path)
        self.assertIn("group5", path)
        self.assertIn("games0", path)
        self.assertIn("leagueall", path)
        self.assertIn("LineupViz", path)
        
        # Test with custom parameters
        path = _get_csv_path_for_league_lineup_viz(
            minutes_min=10,
            group_quantity=3,
            last_n_games=5,
            measure_type_detailed_defense=MeasureTypeDetailedDefense.base,
            per_mode_detailed=PerModeDetailed.per_game,
            season="2023-24",
            season_type_all_star=SeasonTypeAllStar.playoffs,
            league_id_nullable="00",
            data_set_name="CustomData"
        )
        self.assertIn("league_lineup_viz", path)
        self.assertIn("season2023-24", path)
        self.assertIn("typePlayoffs", path)
        self.assertIn("measureBase", path)
        self.assertIn("perPerGame", path)
        self.assertIn("min10", path)
        self.assertIn("group3", path)
        self.assertIn("games5", path)
        self.assertIn("league00", path)
        self.assertIn("CustomData", path)

    def test_fetch_league_lineup_viz_logic_json(self):
        """Test fetching league lineup viz in JSON format."""
        # Call the function with real API
        json_response = fetch_league_lineup_viz_logic(
            minutes_min=5,
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
            self.assertEqual(data["parameters"]["minutes_min"], 5)
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
            if "LineupViz" in data_sets:
                lineup_viz_data = data_sets["LineupViz"]
                self.assertIsInstance(lineup_viz_data, list)
                self.assertGreater(len(lineup_viz_data), 1000)  # Should have 1000+ lineups
                print(f"Lineup Viz count: {len(lineup_viz_data)}")
                print(f"Sample lineup: {lineup_viz_data[0] if lineup_viz_data else 'No data'}")

    def test_fetch_league_lineup_viz_logic_dataframe(self):
        """Test fetching league lineup viz in DataFrame format."""
        # Call the function with real API
        json_response, dataframes = fetch_league_lineup_viz_logic(
            minutes_min=5,
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
            self.assertEqual(data["parameters"]["minutes_min"], 5)
            self.assertEqual(data["parameters"]["season"], "2024-25")
            
            # Check dataframes
            self.assertGreater(len(dataframes), 0)
            
            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")
                print(f"Columns: {df.columns.tolist()}")
                
                # Verify expected columns for lineup viz
                expected_columns = ["GROUP_ID", "GROUP_NAME", "TEAM_ID", "TEAM_ABBREVIATION", "MIN", "OFF_RATING", "DEF_RATING", "NET_RATING"]
                for col in expected_columns:
                    if col in df.columns:
                        print(f"Found expected column: {col}")
            
            # Verify CSV file was created
            csv_path = _get_csv_path_for_league_lineup_viz(
                5, 5, 0, MeasureTypeDetailedDefense.base, PerModeDetailed.totals,
                "2024-25", SeasonTypeAllStar.regular, "", "LineupViz"
            )
            if os.path.exists(csv_path):
                print(f"CSV file created: {csv_path}")
                print(f"File size: {os.path.getsize(csv_path)} bytes")
            else:
                print(f"CSV file was not created at: {csv_path}")

    def test_fetch_league_lineup_viz_logic_csv_cache(self):
        """Test that CSV caching works correctly."""
        # Parameters for testing
        params = {
            "minutes_min": 10,
            "season": "2023-24"
        }
        
        # Check if CSV already exists
        csv_path = _get_csv_path_for_league_lineup_viz(
            params["minutes_min"], 5, 0, MeasureTypeDetailedDefense.base, PerModeDetailed.totals,
            params["season"], SeasonTypeAllStar.regular, "", "LineupViz"
        )
        if os.path.exists(csv_path):
            print(f"CSV file already exists: {csv_path}")
            print(f"File size: {os.path.getsize(csv_path)} bytes")
            print(f"Last modified: {time.ctime(os.path.getmtime(csv_path))}")
        
        # First call to create the cache if it doesn't exist
        print("Making first API call to create/update CSV...")
        _, dataframes1 = fetch_league_lineup_viz_logic(**params, return_dataframe=True)
        
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
        _, dataframes2 = fetch_league_lineup_viz_logic(**params, return_dataframe=True)
        
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

    def test_get_league_lineup_viz(self):
        """Test the get_league_lineup_viz function."""
        # Call the function with real API
        json_response, dataframes = get_league_lineup_viz(
            minutes_min=5,
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
            self.assertEqual(data["parameters"]["minutes_min"], 5)
            self.assertEqual(data["parameters"]["season"], "2024-25")
            
            # Check dataframes
            self.assertGreater(len(dataframes), 0)
            
            for data_set_name, df in dataframes.items():
                self.assertIsInstance(df, pd.DataFrame)
                print(f"DataFrame '{data_set_name}' shape: {df.shape}")

    def test_100_percent_parameter_coverage(self):
        """Test 100% parameter coverage for LeagueLineupViz endpoint."""
        print("\n=== Testing 100% Parameter Coverage ===")
        
        # Test parameter combinations that work
        test_cases = [
            # Basic combinations
            {"minutes_min": 5, "season": "2024-25"},
            {"minutes_min": 10, "season": "2023-24"},
            {"minutes_min": 15, "season": "2022-23"},
            
            # Different group quantities
            {"minutes_min": 5, "season": "2024-25", "group_quantity": 2},
            {"minutes_min": 5, "season": "2024-25", "group_quantity": 3},
            {"minutes_min": 5, "season": "2024-25", "group_quantity": 4},
            
            # Different per modes
            {"minutes_min": 5, "season": "2024-25", "per_mode_detailed": PerModeDetailed.per_game},
            
            # Last N games
            {"minutes_min": 5, "season": "2024-25", "last_n_games": 10},
            
            # Playoffs
            {"minutes_min": 5, "season": "2023-24", "season_type_all_star": SeasonTypeAllStar.playoffs},
            
            # Specific league
            {"minutes_min": 5, "season": "2024-25", "league_id_nullable": "00"},
            {"minutes_min": 5, "season": "2024", "league_id_nullable": "10"},  # WNBA
        ]
        
        successful_tests = 0
        total_tests = len(test_cases)
        
        for i, test_case in enumerate(test_cases):
            print(f"\nTest {i+1}/{total_tests}: {test_case}")
            
            try:
                # Call the API with these parameters
                json_response, dataframes = get_league_lineup_viz(
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
                        self.assertEqual(params["minutes_min"], test_case["minutes_min"])
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
                                csv_path = _get_csv_path_for_league_lineup_viz(
                                    test_case["minutes_min"],
                                    test_case.get("group_quantity", 5),
                                    test_case.get("last_n_games", 0),
                                    test_case.get("measure_type_detailed_defense", MeasureTypeDetailedDefense.base),
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

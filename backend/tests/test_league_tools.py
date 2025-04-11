import unittest
import json
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime
from backend.api_tools.league_tools import (
    fetch_league_standings_logic,
    fetch_draft_history_logic,
    fetch_league_leaders_logic,
    fetch_league_lineups_logic
)
from nba_api.stats.library.parameters import SeasonTypeAllStar, MeasureTypeDetailedDefense, PerMode36

class TestLeagueTools(unittest.TestCase):
    def setUp(self):
        # Common test data
        self.valid_season = "2023-24"
        self.invalid_season = "invalid"
        self.valid_season_type = SeasonTypeAllStar.regular
        self.invalid_season_type = "Invalid"
        self.valid_per_mode = PerMode36.per_game
        self.invalid_per_mode = "Invalid"
        self.valid_stat_category = "PTS"
        self.invalid_stat_category = "Invalid"
        self.valid_measure_type = MeasureTypeDetailedDefense.base

    @patch('backend.api_tools.league_tools.leaguestandingsv3.LeagueStandingsV3')
    def test_fetch_league_standings_logic(self, mock_standings):
        # Test valid request
        mock_standings_df = pd.DataFrame({
            'TeamID': ['1610612737', '1610612738'],
            'TeamName': ['Hawks', 'Celtics'],
            'Conference': ['East', 'East'],
            'WinPCT': [0.600, 0.700],
            'L': [10, 8],
            'W': [15, 20],
            'GB': [0.0, 2.0],
            'LastTenWin': [7, 8],
            'LastTenLoss': [3, 2]
        })
        mock_standings.return_value.standings.get_data_frame.return_value = mock_standings_df
        
        result = json.loads(fetch_league_standings_logic(self.valid_season))
        self.assertIn('standings', result)
        self.assertEqual(len(result['standings']), 2)
        self.assertIn('teamid', result['standings'][0])
        self.assertIn('winpct', result['standings'][0])
        
        # Test invalid season
        mock_standings.side_effect = Exception("Invalid season")
        result = json.loads(fetch_league_standings_logic(self.invalid_season))
        self.assertIn('error', result)
        
        # Test missing data
        mock_standings.side_effect = None
        mock_standings.return_value.standings.get_data_frame.return_value = pd.DataFrame()
        result = json.loads(fetch_league_standings_logic(self.valid_season))
        self.assertIn('standings', result)
        self.assertEqual(len(result['standings']), 0)

    @patch('backend.api_tools.league_tools.drafthistory.DraftHistory')
    def test_fetch_draft_history_logic(self, mock_draft):
        # Test valid request
        mock_draft_df = pd.DataFrame({
            'PERSON_ID': ['1234567', '1234568'],
            'PLAYER_NAME': ['Player1', 'Player2'],
            'TEAM_ID': ['1610612737', '1610612738'],
            'TEAM_CITY': ['Atlanta', 'Boston'],
            'TEAM_NAME': ['Hawks', 'Celtics'],
            'ROUND_NUMBER': [1, 1],
            'ROUND_PICK': [1, 2],
            'OVERALL_PICK': [1, 2],
            'DRAFT_YEAR': ['2023', '2023']
        })
        mock_draft.return_value.draft_history.get_data_frame.return_value = mock_draft_df
        
        # Test with specific year
        result = json.loads(fetch_draft_history_logic("2023"))
        self.assertIn('draft_picks', result)
        self.assertEqual(len(result['draft_picks']), 2)
        self.assertEqual(result['season_year_requested'], "2023")
        
        # Test without year (all history)
        result = json.loads(fetch_draft_history_logic())
        self.assertIn('draft_picks', result)
        self.assertEqual(result['season_year_requested'], "All")
        
        # Test missing data
        mock_draft.return_value.draft_history.get_data_frame.return_value = pd.DataFrame()
        result = json.loads(fetch_draft_history_logic("2023"))
        self.assertIn('draft_picks', result)
        self.assertEqual(len(result['draft_picks']), 0)

    @patch('backend.api_tools.league_tools.leagueleaders.LeagueLeaders')
    def test_fetch_league_leaders_logic(self, mock_leaders):
        # Test valid request
        mock_leaders_df = pd.DataFrame({
            'PLAYER_ID': ['203999', '1629029'],
            'PLAYER_NAME': ['Player1', 'Player2'],
            'TEAM_ID': ['1610612737', '1610612738'],
            'GP': [20, 22],
            'PTS': [30.5, 29.8],
            'RANK': [1, 2]
        })
        mock_leaders.return_value.league_leaders.get_data_frame.return_value = mock_leaders_df
        
        result = json.loads(fetch_league_leaders_logic(
            season=self.valid_season,
            stat_category=self.valid_stat_category,
            season_type=self.valid_season_type,
            per_mode=self.valid_per_mode
        ))
        self.assertIn('leaders', result)
        self.assertEqual(len(result['leaders']), 2)
        self.assertIn('player_id', result['leaders'][0])
        self.assertIn('rank', result['leaders'][0])
        
        # Test invalid season
        mock_leaders.side_effect = Exception("Invalid season")
        result = json.loads(fetch_league_leaders_logic(
            season=self.invalid_season,
            stat_category=self.valid_stat_category
        ))
        self.assertIn('error', result)
        
        # Test missing data
        mock_leaders.side_effect = None
        mock_leaders.return_value.league_leaders.get_data_frame.return_value = pd.DataFrame()
        result = json.loads(fetch_league_leaders_logic(
            season=self.valid_season,
            stat_category=self.valid_stat_category
        ))
        self.assertIn('leaders', result)
        self.assertEqual(len(result['leaders']), 0)

    @patch('backend.api_tools.league_tools.leaguedashlineups.LeagueDashLineups')
    def test_fetch_league_lineups_logic(self, mock_lineups):
        # Test valid request
        mock_lineups_df = pd.DataFrame({
            'GROUP_ID': ['1234567', '1234568'],
            'GROUP_NAME': ['Player1-Player2-Player3', 'Player4-Player5-Player6'],
            'TEAM_ID': ['1610612737', '1610612738'],
            'TEAM_ABBREVIATION': ['ATL', 'BOS'],
            'GP': [20, 22],
            'MIN': [150.5, 160.8],
            'PLUS_MINUS': [5.5, 6.2]
        })
        mock_lineups.return_value.league_dash_lineups.get_data_frame.return_value = mock_lineups_df
        
        result = json.loads(fetch_league_lineups_logic(
            season=self.valid_season,
            season_type=self.valid_season_type,
            measure_type=self.valid_measure_type,
            per_mode=self.valid_per_mode
        ))
        self.assertIn('lineups', result)
        self.assertEqual(len(result['lineups']), 2)
        self.assertIn('group_id', result['lineups'][0])
        self.assertIn('plus_minus', result['lineups'][0])
        
        # Test invalid season
        mock_lineups.side_effect = Exception("Invalid season")
        result = json.loads(fetch_league_lineups_logic(
            season=self.invalid_season
        ))
        self.assertIn('error', result)
        
        # Test missing data
        mock_lineups.side_effect = None
        mock_lineups.return_value.league_dash_lineups.get_data_frame.return_value = pd.DataFrame()
        result = json.loads(fetch_league_lineups_logic(
            season=self.valid_season
        ))
        self.assertIn('lineups', result)
        self.assertEqual(len(result['lineups']), 0)

if __name__ == '__main__':
    unittest.main() 
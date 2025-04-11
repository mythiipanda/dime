import unittest
import json
from unittest.mock import patch, MagicMock
import pandas as pd
from backend.api_tools.game_tools import (
    fetch_game_boxscore_logic,
    fetch_game_shotchart_logic,
    fetch_game_hustle_stats_logic,
    fetch_game_playbyplay_logic
)

class TestGameTools(unittest.TestCase):
    def setUp(self):
        # Common test data
        self.valid_game_id = "0022300001"
        self.invalid_game_id = "invalid123"
        self.empty_game_id = ""
        self.valid_team_id = "1610612737"
        self.invalid_team_id = "invalid"

    @patch('backend.api_tools.game_tools.boxscoretraditionalv3.BoxScoreTraditionalV3')
    def test_fetch_game_boxscore_logic(self, mock_boxscore):
        # Test valid game_id
        mock_player_df = pd.DataFrame({
            'TEAM_ID': ['1610612737', '1610612737', '1610612738', '1610612738'],
            'PLAYER_NAME': ['Player1', 'Player2', 'Player3', 'Player4'],
            'MINUTES': ['20:00', '25:00', '22:00', '18:00']
        })
        mock_team_df = pd.DataFrame({
            'TEAM_ID': ['1610612737', '1610612738'],
            'TEAM_NAME': ['Team1', 'Team2']
        })
        
        mock_boxscore.return_value.player_stats.get_data_frame.return_value = mock_player_df
        mock_boxscore.return_value.team_stats.get_data_frame.return_value = mock_team_df
        
        result = json.loads(fetch_game_boxscore_logic(self.valid_game_id))
        self.assertIn('home_team', result)
        self.assertIn('away_team', result)
        self.assertIn('players', result['home_team'])
        self.assertIn('players', result['away_team'])
        self.assertEqual(len(result['home_team']['players']), 2)
        self.assertEqual(len(result['away_team']['players']), 2)
        
        # Test empty game_id
        result = json.loads(fetch_game_boxscore_logic(self.empty_game_id))
        self.assertIn('error', result)
        self.assertEqual(result['error'], 'Game ID cannot be empty.')
        
        # Test invalid game_id format
        result = json.loads(fetch_game_boxscore_logic(self.invalid_game_id))
        self.assertIn('error', result)
        self.assertEqual(result['error'], f'Invalid Game ID format: {self.invalid_game_id}. Expected 10 digits.')
        
        # Test missing TEAM_ID in player stats
        mock_player_df = pd.DataFrame({
            'PLAYER_NAME': ['Player1', 'Player2'],
            'MINUTES': ['20:00', '25:00']
        })
        mock_boxscore.return_value.player_stats.get_data_frame.return_value = mock_player_df
        result = json.loads(fetch_game_boxscore_logic(self.valid_game_id))
        self.assertIn('error', result)
        self.assertEqual(result['error'], f'Invalid boxscore data format for game {self.valid_game_id}')
        
        # Test missing TEAM_ID in team stats
        mock_player_df = pd.DataFrame({
            'TEAM_ID': ['1610612737', '1610612738'],
            'PLAYER_NAME': ['Player1', 'Player2'],
            'MINUTES': ['20:00', '25:00']
        })
        mock_team_df = pd.DataFrame({
            'TEAM_NAME': ['Team1', 'Team2']
        })
        mock_boxscore.return_value.player_stats.get_data_frame.return_value = mock_player_df
        mock_boxscore.return_value.team_stats.get_data_frame.return_value = mock_team_df
        result = json.loads(fetch_game_boxscore_logic(self.valid_game_id))
        self.assertIn('error', result)
        self.assertEqual(result['error'], f'Invalid boxscore data format for game {self.valid_game_id}')
        
        # Test API timeout scenario
        mock_boxscore.return_value.player_stats.get_data_frame.side_effect = Exception('API timeout')
        result = json.loads(fetch_game_boxscore_logic(self.valid_game_id))
        self.assertIn('error', result)
        self.assertEqual(result['error'], f'Failed to retrieve boxscore data for game {self.valid_game_id}: API timeout')
        
        # Test empty dataframes
        # Reset side effect from previous test
        mock_boxscore.return_value.player_stats.get_data_frame.side_effect = None
        mock_boxscore.return_value.player_stats.get_data_frame.return_value = pd.DataFrame()
        mock_boxscore.return_value.team_stats.get_data_frame.return_value = pd.DataFrame()
        result = json.loads(fetch_game_boxscore_logic(self.valid_game_id))
        self.assertIn('error', result)
        self.assertEqual(result['error'], f'No boxscore data found for game {self.valid_game_id}')

    @patch('backend.api_tools.game_tools.shotchartdetail.ShotChartDetail')
    def test_fetch_game_shotchart_logic(self, mock_shotchart):
        # Test valid game_id
        mock_shots_df = pd.DataFrame({
            'GAME_ID': [self.valid_game_id],
            'TEAM_ID': [self.valid_team_id],
            'PLAYER_NAME': ['Player1'],
            'LOC_X': [100.0],
            'LOC_Y': [100.0],
            'SHOT_MADE_FLAG': [1]
        })
        mock_shotchart.return_value.get_data_frames.return_value = [mock_shots_df]
        
        # Test with valid data
        result = json.loads(fetch_game_shotchart_logic(self.valid_game_id))
        self.assertIn('shots', result)
        self.assertGreater(len(result['shots']), 0)
        
        # Test with team_id filter
        result = json.loads(fetch_game_shotchart_logic(self.valid_game_id, self.valid_team_id))
        self.assertIn('shots', result)
        
        # Test invalid game_id
        result = json.loads(fetch_game_shotchart_logic(self.invalid_game_id))
        self.assertIn('error', result)
        
        # Test invalid team_id
        result = json.loads(fetch_game_shotchart_logic(self.valid_game_id, self.invalid_team_id))
        self.assertIn('error', result)
        
        # Test missing required columns
        mock_shots_df = pd.DataFrame({'GAME_ID': [self.valid_game_id]})
        mock_shotchart.return_value.get_data_frames.return_value = [mock_shots_df]
        result = json.loads(fetch_game_shotchart_logic(self.valid_game_id))
        self.assertIn('error', result)

    @patch('backend.api_tools.game_tools.hustlestatsboxscore.HustleStatsBoxScore')
    def test_fetch_game_hustle_stats_logic(self, mock_hustle):
        # Test valid game_id
        mock_player_df = pd.DataFrame({
            'GAME_ID': [self.valid_game_id],
            'TEAM_ID': [self.valid_team_id],
            'PLAYER_NAME': ['Player1'],
            'MINUTES': ['20:00']
        })
        mock_team_df = pd.DataFrame({
            'GAME_ID': [self.valid_game_id, self.valid_game_id],
            'TEAM_ID': [self.valid_team_id, '1610612738'],
            'TEAM_NAME': ['Team1', 'Team2']
        })
        
        mock_hustle.return_value.hustle_stats_player_box_score.get_data_frame.return_value = mock_player_df
        mock_hustle.return_value.hustle_stats_team_box_score.get_data_frame.return_value = mock_team_df
        
        # Test with valid data
        result = json.loads(fetch_game_hustle_stats_logic(self.valid_game_id))
        self.assertIn('home_team', result)
        self.assertIn('away_team', result)
        
        # Test invalid game_id
        result = json.loads(fetch_game_hustle_stats_logic(self.invalid_game_id))
        self.assertIn('error', result)
        
        # Test missing required columns
        mock_player_df = pd.DataFrame({'GAME_ID': [self.valid_game_id]})
        mock_hustle.return_value.hustle_stats_player_box_score.get_data_frame.return_value = mock_player_df
        result = json.loads(fetch_game_hustle_stats_logic(self.valid_game_id))
        self.assertIn('error', result)

    @patch('backend.api_tools.game_tools.playbyplayv3.PlayByPlayV3')
    def test_fetch_game_playbyplay_logic(self, mock_pbp):
        # Test valid game_id
        mock_pbp_df = pd.DataFrame({
            'PERIOD': [1, 1],
            'PCTIMESTRING': ['12:00', '11:45'],
            'SCORE': ['0-0', '2-0'],
            'SCOREMARGIN': ['0', '2'],
            'EVENTMSGTYPE': [1, 2],
            'HOMEDESCRIPTION': ['Shot made', 'Rebound'],
            'PLAYER1_NAME': ['Player1', 'Player2']
        })
        mock_pbp.return_value.play_by_play.get_data_frame.return_value = mock_pbp_df
        
        # Test with valid data
        result = json.loads(fetch_game_playbyplay_logic(self.valid_game_id))
        self.assertIn('plays', result)
        self.assertGreater(len(result['plays']), 0)
        
        # Test with period filter
        result = json.loads(fetch_game_playbyplay_logic(self.valid_game_id, period=1))
        self.assertIn('plays', result)
        self.assertEqual(result['period'], 1)
        
        # Test invalid game_id
        result = json.loads(fetch_game_playbyplay_logic(self.invalid_game_id))
        self.assertIn('error', result)
        
        # Test invalid period
        result = json.loads(fetch_game_playbyplay_logic(self.valid_game_id, period='invalid'))
        self.assertIn('error', result)
        
        # Test missing required columns
        mock_pbp_df = pd.DataFrame({'PERIOD': [1]})
        mock_pbp.return_value.play_by_play.get_data_frame.return_value = mock_pbp_df
        result = json.loads(fetch_game_playbyplay_logic(self.valid_game_id))
        self.assertIn('error', result)

if __name__ == '__main__':
    unittest.main() 
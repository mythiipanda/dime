import sys
import os
import pytest
from unittest.mock import patch, MagicMock
import json
import pandas as pd

# Add the backend directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

from api_tools.player_tools import (
    find_player_by_name,
    _find_player_id,
    fetch_player_stats_logic,
    fetch_player_clutch_stats_logic
)

@patch('api_tools.player_tools.players.find_players_by_full_name')
def test_find_player_by_name(mock_find_players):
    # Mock data
    mock_player = {
        "id": "2544",
        "full_name": "LeBron James",
        "first_name": "LeBron",
        "last_name": "James",
        "is_active": True
    }
    
    # Test with a valid player name
    mock_find_players.return_value = [mock_player]
    result = find_player_by_name("LeBron James")
    assert result is not None
    assert "id" in result
    assert "full_name" in result
    assert result["full_name"] == "LeBron James"
    mock_find_players.assert_called_once_with("LeBron James")

    # Test with an invalid player name
    mock_find_players.reset_mock()
    mock_find_players.return_value = []
    result = find_player_by_name("NonexistentPlayer123")
    assert result is None
    mock_find_players.assert_called_once_with("NonexistentPlayer123")

    # Test with None
    mock_find_players.reset_mock()
    result = find_player_by_name(None)
    assert result is None
    mock_find_players.assert_not_called()

    # Test with empty string
    mock_find_players.reset_mock()
    result = find_player_by_name("")
    assert result is None
    mock_find_players.assert_not_called()

    # Test API error handling
    mock_find_players.reset_mock()
    mock_find_players.side_effect = Exception("API Error")
    result = find_player_by_name("LeBron James")
    assert result is None
    mock_find_players.assert_called_once_with("LeBron James")

@patch('api_tools.player_tools.players.find_players_by_full_name')
def test_find_player_id(mock_find_players):
    # Mock data
    mock_player = {
        "id": "2544",
        "full_name": "LeBron James",
        "first_name": "LeBron",
        "last_name": "James",
        "is_active": True
    }
    
    # Test with a valid player name
    mock_find_players.return_value = [mock_player]
    player_id, full_name = _find_player_id("LeBron James")
    assert player_id == "2544"
    assert full_name == "LeBron James"
    mock_find_players.assert_called_once_with("LeBron James")

    # Test with an invalid player name
    mock_find_players.reset_mock()
    mock_find_players.return_value = []
    player_id, full_name = _find_player_id("NonexistentPlayer123")
    assert player_id is None
    assert full_name is None
    mock_find_players.assert_called_once_with("NonexistentPlayer123")

    # Test with None
    mock_find_players.reset_mock()
    player_id, full_name = _find_player_id(None)
    assert player_id is None
    assert full_name is None
    mock_find_players.assert_not_called()

    # Test with empty string
    mock_find_players.reset_mock()
    player_id, full_name = _find_player_id("")
    assert player_id is None
    assert full_name is None
    mock_find_players.assert_not_called()

    # Test API error handling
    mock_find_players.reset_mock()
    mock_find_players.side_effect = Exception("API Error")
    player_id, full_name = _find_player_id("LeBron James")
    assert player_id is None
    assert full_name is None
    mock_find_players.assert_called_once_with("LeBron James")

@patch('api_tools.player_tools.commonplayerinfo.CommonPlayerInfo')
@patch('api_tools.player_tools.playercareerstats.PlayerCareerStats')
@patch('api_tools.player_tools._find_player_id')
def test_fetch_player_stats_logic(mock_find_player_id, mock_career_stats, mock_player_info):
    # Mock data
    mock_player_id = "2544"
    mock_player_name = "LeBron James"
    
    # Mock player info DataFrame
    mock_info_df = pd.DataFrame({
        'PERSON_ID': [mock_player_id],
        'FIRST_NAME': ['LeBron'],
        'LAST_NAME': ['James'],
        'BIRTHDATE': ['1984-12-30'],
        'COUNTRY': ['USA'],
        'HEIGHT': ['6-9'],
        'WEIGHT': ['250'],
        'SEASON_EXP': [19],
        'JERSEY': ['23'],
        'POSITION': ['F'],
        'TEAM_ID': ['1610612747'],
        'TEAM_NAME': ['Los Angeles Lakers']
    })
    
    # Mock career stats DataFrames
    mock_season_totals_df = pd.DataFrame({
        'PLAYER_ID': [mock_player_id],
        'SEASON_ID': ['2022-23'],
        'TEAM_ID': ['1610612747'],
        'TEAM_ABBREVIATION': ['LAL'],
        'GP': [55],
        'GS': [54],
        'MIN': [1850],
        'PTS': [1500],
        'AST': [400],
        'REB': [500]
    })
    
    mock_career_totals_df = pd.DataFrame({
        'PLAYER_ID': [mock_player_id],
        'GP': [1421],
        'GS': [1420],
        'MIN': [54000],
        'PTS': [39000],
        'AST': [10500],
        'REB': [11000]
    })
    
    # Set up mocks
    mock_find_player_id.return_value = (mock_player_id, mock_player_name)
    mock_player_info.return_value.common_player_info.get_data_frame.return_value = mock_info_df
    mock_career_stats.return_value.season_totals_regular_season.get_data_frame.return_value = mock_season_totals_df
    mock_career_stats.return_value.career_totals_regular_season.get_data_frame.return_value = mock_career_totals_df
    
    # Test with valid inputs
    result = fetch_player_stats_logic("LeBron James", "2022-23")
    result_dict = json.loads(result)
    assert result_dict is not None
    assert result_dict["player_name"] == mock_player_name
    assert result_dict["player_id"] == mock_player_id
    assert "info" in result_dict
    assert "career_stats" in result_dict
    assert "season_stats" in result_dict
    
    # Test with invalid player
    mock_find_player_id.return_value = (None, None)
    result = fetch_player_stats_logic("NonexistentPlayer123", "2022-23")
    result_dict = json.loads(result)
    assert "error" in result_dict
    assert "Player not found" in result_dict["error"]
    
    # Test with API error in player info
    mock_find_player_id.return_value = (mock_player_id, mock_player_name)
    mock_player_info.return_value.common_player_info.get_data_frame.side_effect = Exception("API Error")
    result = fetch_player_stats_logic("LeBron James", "2022-23")
    result_dict = json.loads(result)
    assert "error" in result_dict
    
    # Test with API error in career stats
    mock_player_info.return_value.common_player_info.get_data_frame.side_effect = None
    mock_career_stats.return_value.season_totals_regular_season.get_data_frame.side_effect = Exception("API Error")
    result = fetch_player_stats_logic("LeBron James", "2022-23")
    result_dict = json.loads(result)
    assert "error" in result_dict

@patch('api_tools.player_tools.playerdashboardbyclutch.PlayerDashboardByClutch')
@patch('api_tools.player_tools._find_player_id')
def test_fetch_player_clutch_stats_logic(mock_find_player_id, mock_clutch_stats):
    # Mock data
    mock_player_id = "2544"
    mock_player_name = "LeBron James"
    
    # Mock clutch stats DataFrame
    mock_clutch_df = pd.DataFrame({
        'GROUP_SET': ['Overall', 'Last 5 Min'],
        'GP': [55, 30],
        'W': [30, 15],
        'L': [25, 15],
        'MIN': [1850, 150],
        'PTS': [1500, 200],
        'AST': [400, 50],
        'REB': [500, 60],
        'FG_PCT': [0.500, 0.480],
        'FG3_PCT': [0.350, 0.330],
        'FT_PCT': [0.750, 0.800]
    })
    
    # Set up mocks
    mock_find_player_id.return_value = (mock_player_id, mock_player_name)
    mock_clutch_stats.return_value.overall_clutch_dashboard.get_data_frame.return_value = mock_clutch_df
    mock_clutch_stats.return_value.last5min_clutch_dashboard.get_data_frame.return_value = mock_clutch_df
    
    # Test with valid inputs
    result = fetch_player_clutch_stats_logic("LeBron James", "2022-23")
    result_dict = json.loads(result)
    assert result_dict is not None
    assert result_dict["player_name"] == mock_player_name
    assert result_dict["player_id"] == mock_player_id
    assert "overall_clutch" in result_dict
    assert "last5min_clutch" in result_dict
    
    # Test with invalid player
    mock_find_player_id.return_value = (None, None)
    result = fetch_player_clutch_stats_logic("NonexistentPlayer123", "2022-23")
    result_dict = json.loads(result)
    assert "error" in result_dict
    assert "Player not found" in result_dict["error"]
    
    # Test with API error in clutch stats
    mock_find_player_id.return_value = (mock_player_id, mock_player_name)
    mock_clutch_stats.return_value.overall_clutch_dashboard.get_data_frame.side_effect = Exception("API Error")
    result = fetch_player_clutch_stats_logic("LeBron James", "2022-23")
    result_dict = json.loads(result)
    assert "error" in result_dict
    
    # Test with empty data
    mock_clutch_stats.return_value.overall_clutch_dashboard.get_data_frame.side_effect = None
    mock_clutch_stats.return_value.overall_clutch_dashboard.get_data_frame.return_value = pd.DataFrame()
    result = fetch_player_clutch_stats_logic("LeBron James", "2022-23")
    result_dict = json.loads(result)
    assert "error" in result_dict 
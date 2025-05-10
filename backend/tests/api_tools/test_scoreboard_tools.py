import pytest
import json
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime, date

# Modules to test
from backend.api_tools.scoreboard import scoreboard_tools
from backend.config import Errors, DEFAULT_TIMEOUT
from nba_api.stats.library.parameters import LeagueID

# Mock data for Live Scoreboard (reuse from live_game_tools tests)
MOCK_LIVE_GAME_1 = {
    "gameId": "0022300100", "gameStatus": 2, "gameStatusText": "Q2 5:00", "period": 2, "gameClock": "5:00",
    "homeTeam": {"teamId": 101, "teamTricode": "AAA", "score": 55, "wins": 10, "losses": 5},
    "awayTeam": {"teamId": 102, "teamTricode": "BBB", "score": 50, "wins": 8, "losses": 7},
    "gameTimeUTC": "2023-11-10T19:00:00Z"
}
MOCK_LIVE_SCOREBOARD_RAW = {
    "scoreboard": {
        "gameDate": datetime.now().strftime("%Y-%m-%d"),
        "games": [MOCK_LIVE_GAME_1]
    }
}
MOCK_FORMATTED_LIVE_GAME_1 = { # Expected format from scoreboard_tools logic
    "gameId": "0022300100", "gameStatus": 2, "gameStatusText": "Q2 5:00", "period": 2, "gameClock": "5:00",
    "homeTeam": {"teamId": 101, "teamTricode": "AAA", "score": 55, "wins": 10, "losses": 5},
    "awayTeam": {"teamId": 102, "teamTricode": "BBB", "score": 50, "wins": 8, "losses": 7},
    "gameEt": "2023-11-10T19:00:00Z"
}

# Mock data for Static ScoreboardV2
MOCK_STATIC_GAME_DATE = "2023-11-09"
MOCK_STATIC_GAME_HEADER_DATA = [
    {"GAME_ID": "0022300090", "GAME_DATE_EST": MOCK_STATIC_GAME_DATE, "GAME_STATUS_ID": 3, "GAME_STATUS_TEXT": "Final", "HOME_TEAM_ID": 103, "VISITOR_TEAM_ID": 104, "LIVE_PERIOD": 4, "LIVE_PC_TIME": ""},
]
MOCK_STATIC_LINE_SCORE_DATA = [
    {"GAME_ID": "0022300090", "TEAM_ID": 103, "TEAM_ABBREVIATION": "CCC", "TEAM_WINS_LOSSES": "9-6", "PTS": 115},
    {"GAME_ID": "0022300090", "TEAM_ID": 104, "TEAM_ABBREVIATION": "DDD", "TEAM_WINS_LOSSES": "7-8", "PTS": 110}
]
MOCK_STATIC_SCOREBOARD_PROCESSED = { # Data structure returned by get_cached_static_scoreboard_data
    "game_header": MOCK_STATIC_GAME_HEADER_DATA,
    "line_score": MOCK_STATIC_LINE_SCORE_DATA
}
MOCK_FORMATTED_STATIC_GAME = { # Expected format from scoreboard_tools logic
    "gameId": "0022300090", "gameStatus": 3, "gameStatusText": "Final", "period": 4, "gameClock": "",
    "homeTeam": {"teamId": 103, "teamTricode": "CCC", "score": 115, "wins": 9, "losses": 6},
    "awayTeam": {"teamId": 104, "teamTricode": "DDD", "score": 110, "wins": 7, "losses": 8},
    "gameEt": MOCK_STATIC_GAME_DATE
}

# --- Tests for fetch_scoreboard_data_logic ---

@patch('backend.api_tools.scoreboard.scoreboard_tools.get_cached_live_scoreboard_data')
@patch('backend.api_tools.scoreboard.scoreboard_tools.date') # Mock date to control 'is_today'
def test_fetch_scoreboard_live_success_cached(mock_date, mock_get_live_cached):
    """Test successful fetching of live scoreboard data from cache."""
    # Arrange
    today_str = "2023-11-10"
    mock_date.today.return_value.strftime.return_value = today_str
    mock_get_live_cached.return_value = MOCK_LIVE_SCOREBOARD_RAW
    expected_result_data = {"gameDate": today_str, "games": [MOCK_FORMATTED_LIVE_GAME_1]}

    # Act
    result_str = scoreboard_tools.fetch_scoreboard_data_logic(game_date=today_str)
    result = json.loads(result_str)

    # Assert
    mock_get_live_cached.assert_called_once()
    assert "error" not in result
    assert result == expected_result_data

@patch('backend.api_tools.scoreboard.scoreboard_tools.LiveScoreBoard')
@patch('backend.api_tools.scoreboard.scoreboard_tools.date')
def test_fetch_scoreboard_live_success_no_cache(mock_date, mock_live_endpoint):
    """Test successful fetching of live scoreboard data bypassing cache."""
    # Arrange
    today_str = "2023-11-10"
    mock_date.today.return_value.strftime.return_value = today_str
    mock_live_instance = MagicMock()
    mock_live_instance.get_dict.return_value = MOCK_LIVE_SCOREBOARD_RAW
    mock_live_endpoint.return_value = mock_live_instance
    expected_result_data = {"gameDate": today_str, "games": [MOCK_FORMATTED_LIVE_GAME_1]}

    # Act
    result_str = scoreboard_tools.fetch_scoreboard_data_logic(game_date=today_str, bypass_cache=True)
    result = json.loads(result_str)

    # Assert
    mock_live_endpoint.assert_called_once()
    assert "error" not in result
    assert result == expected_result_data

@patch('backend.api_tools.scoreboard.scoreboard_tools.get_cached_static_scoreboard_data')
@patch('backend.api_tools.scoreboard.scoreboard_tools.date')
def test_fetch_scoreboard_static_success_cached(mock_date, mock_get_static_cached):
    """Test successful fetching of static scoreboard data from cache."""
    # Arrange
    mock_date.today.return_value.strftime.return_value = "2023-11-10" # Today is different
    mock_get_static_cached.return_value = MOCK_STATIC_SCOREBOARD_PROCESSED
    expected_result_data = {"gameDate": MOCK_STATIC_GAME_DATE, "games": [MOCK_FORMATTED_STATIC_GAME]}

    # Act
    result_str = scoreboard_tools.fetch_scoreboard_data_logic(game_date=MOCK_STATIC_GAME_DATE)
    result = json.loads(result_str)

    # Assert
    mock_get_static_cached.assert_called_once()
    assert "error" not in result
    assert result == expected_result_data

@patch('backend.api_tools.scoreboard.scoreboard_tools.scoreboardv2.ScoreboardV2')
@patch('backend.api_tools.scoreboard.scoreboard_tools._process_dataframe')
@patch('backend.api_tools.scoreboard.scoreboard_tools.date')
def test_fetch_scoreboard_static_success_no_cache(mock_date, mock_process_df, mock_static_endpoint):
    """Test successful fetching of static scoreboard data bypassing cache."""
    # Arrange
    mock_date.today.return_value.strftime.return_value = "2023-11-10" # Today is different
    mock_static_instance = MagicMock()
    mock_static_instance.game_header.get_data_frame.return_value = pd.DataFrame(MOCK_STATIC_GAME_HEADER_DATA)
    mock_static_instance.line_score.get_data_frame.return_value = pd.DataFrame(MOCK_STATIC_LINE_SCORE_DATA)
    mock_static_endpoint.return_value = mock_static_instance

    # Mock _process_dataframe used within the static fetch logic simulation
    mock_process_df.side_effect = [
        MOCK_STATIC_GAME_HEADER_DATA, # game_header
        MOCK_STATIC_LINE_SCORE_DATA   # line_score
    ]
    expected_result_data = {"gameDate": MOCK_STATIC_GAME_DATE, "games": [MOCK_FORMATTED_STATIC_GAME]}

    # Act
    result_str = scoreboard_tools.fetch_scoreboard_data_logic(game_date=MOCK_STATIC_GAME_DATE, bypass_cache=True)
    result = json.loads(result_str)

    # Assert
    mock_static_endpoint.assert_called_once()
    # Note: _process_dataframe is called inside the *simulated* static fetch logic now
    # We can't directly assert its call count here easily without more complex mocking
    assert "error" not in result
    assert result == expected_result_data

def test_fetch_scoreboard_invalid_date():
    """Test scoreboard fetch with invalid date format."""
    # Arrange
    invalid_date = "11-10-2023"
    expected_error = Errors.INVALID_DATE_FORMAT.format(date=invalid_date)

    # Act
    result_str = scoreboard_tools.fetch_scoreboard_data_logic(game_date=invalid_date)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.scoreboard.scoreboard_tools.get_cached_live_scoreboard_data')
@patch('backend.api_tools.scoreboard.scoreboard_tools.date')
def test_fetch_scoreboard_live_api_error(mock_date, mock_get_live_cached):
    """Test live scoreboard fetch with API error."""
    # Arrange
    today_str = "2023-11-10"
    mock_date.today.return_value.strftime.return_value = today_str
    api_error_message = "Live API timeout"
    mock_get_live_cached.side_effect = Exception(api_error_message)
    expected_error = Errors.LEAGUE_SCOREBOARD_UNEXPECTED.format(game_date=today_str, error=api_error_message)

    # Act
    result_str = scoreboard_tools.fetch_scoreboard_data_logic(game_date=today_str)
    result = json.loads(result_str)

    # Assert
    mock_get_live_cached.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.scoreboard.scoreboard_tools.get_cached_static_scoreboard_data')
@patch('backend.api_tools.scoreboard.scoreboard_tools.date')
def test_fetch_scoreboard_static_api_error(mock_date, mock_get_static_cached):
    """Test static scoreboard fetch with API error."""
    # Arrange
    mock_date.today.return_value.strftime.return_value = "2023-11-10" # Today is different
    api_error_message = "Static API timeout"
    mock_get_static_cached.side_effect = Exception(api_error_message)
    expected_error = Errors.LEAGUE_SCOREBOARD_UNEXPECTED.format(game_date=MOCK_STATIC_GAME_DATE, error=api_error_message)

    # Act
    result_str = scoreboard_tools.fetch_scoreboard_data_logic(game_date=MOCK_STATIC_GAME_DATE)
    result = json.loads(result_str)

    # Assert
    mock_get_static_cached.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error
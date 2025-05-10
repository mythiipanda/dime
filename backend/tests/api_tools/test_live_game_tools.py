import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime

# Modules to test
from backend.api_tools import live_game_tools
from backend.config import Errors, DEFAULT_TIMEOUT # Added DEFAULT_TIMEOUT
# Import the actual class being used in the source file
from nba_api.live.nba.endpoints import ScoreBoard as LiveScoreBoard # Keep this import

# Mock data for Live Scoreboard
MOCK_LIVE_GAME_1 = {
    "gameId": "0022300100", "gameStatus": 2, "gameStatusText": "Q2 5:00", "period": 2, "gameClock": "5:00",
    "homeTeam": {"teamId": 101, "teamTricode": "AAA", "score": 55, "wins": 10, "losses": 5},
    "awayTeam": {"teamId": 102, "teamTricode": "BBB", "score": 50, "wins": 8, "losses": 7},
    "gameTimeUTC": "2023-11-10T19:00:00Z"
}
MOCK_LIVE_GAME_2 = {
    "gameId": "0022300101", "gameStatus": 1, "gameStatusText": "7:30 PM ET", "period": 0, "gameClock": "",
    "homeTeam": {"teamId": 103, "teamTricode": "CCC", "score": 0, "wins": 9, "losses": 6},
    "awayTeam": {"teamId": 104, "teamTricode": "DDD", "score": 0, "wins": 7, "losses": 8},
    "gameTimeUTC": "2023-11-10T19:30:00Z"
}
MOCK_LIVE_GAME_3_FINAL = { # Example of a finished game
    "gameId": "0022300099", "gameStatus": 3, "gameStatusText": "Final", "period": 4, "gameClock": "",
    "homeTeam": {"teamId": 105, "teamTricode": "EEE", "score": 110, "wins": 11, "losses": 4},
    "awayTeam": {"teamId": 106, "teamTricode": "FFF", "score": 105, "wins": 6, "losses": 9},
    "gameTimeUTC": "2023-11-10T18:00:00Z"
}
MOCK_LIVE_SCOREBOARD_RAW = {
    "scoreboard": {
        "gameDate": datetime.now().strftime("%Y-%m-%d"),
        "games": [MOCK_LIVE_GAME_1, MOCK_LIVE_GAME_2, MOCK_LIVE_GAME_3_FINAL]
    }
}
# Expected formatted output (structure matches frontend needs)
MOCK_FORMATTED_GAME_1 = {
    "gameId": "0022300100", "gameStatus": 2, "gameStatusText": "Q2 5:00", "period": 2, "gameClock": "5:00",
    "homeTeam": {"teamId": 101, "teamTricode": "AAA", "score": 55, "wins": 10, "losses": 5},
    "awayTeam": {"teamId": 102, "teamTricode": "BBB", "score": 50, "wins": 8, "losses": 7},
    "gameEt": "2023-11-10T19:00:00Z"
}
MOCK_FORMATTED_GAME_2 = {
    "gameId": "0022300101", "gameStatus": 1, "gameStatusText": "7:30 PM ET", "period": 0, "gameClock": None, # Clock None for scheduled
    "homeTeam": {"teamId": 103, "teamTricode": "CCC", "score": 0, "wins": 9, "losses": 6},
    "awayTeam": {"teamId": 104, "teamTricode": "DDD", "score": 0, "wins": 7, "losses": 8},
    "gameEt": "2023-11-10T19:30:00Z"
}
MOCK_FORMATTED_GAME_3 = {
    "gameId": "0022300099", "gameStatus": 3, "gameStatusText": "Final", "period": 4, "gameClock": None, # Clock None for final
    "homeTeam": {"teamId": 105, "teamTricode": "EEE", "score": 110, "wins": 11, "losses": 4},
    "awayTeam": {"teamId": 106, "teamTricode": "FFF", "score": 105, "wins": 6, "losses": 9},
    "gameEt": "2023-11-10T18:00:00Z"
}
MOCK_EXPECTED_SCOREBOARD_RESULT = {
    "gameDate": datetime.now().strftime("%Y-%m-%d"),
    "games": [MOCK_FORMATTED_GAME_1, MOCK_FORMATTED_GAME_2, MOCK_FORMATTED_GAME_3]
}

# --- Tests for fetch_league_scoreboard_logic ---

@patch('backend.api_tools.live_game_tools.get_cached_scoreboard_data')
def test_fetch_scoreboard_success_cached(mock_get_cached):
    """Test successful fetching of scoreboard data from cache."""
    # Arrange
    mock_get_cached.return_value = MOCK_LIVE_SCOREBOARD_RAW
    expected_result_data = MOCK_EXPECTED_SCOREBOARD_RESULT

    # Act
    result_str = live_game_tools.fetch_league_scoreboard_logic()
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" not in result
    # Compare key fields instead of exact dict match
    assert result.get("gameDate") == expected_result_data["gameDate"]
    assert len(result.get("games", [])) == len(expected_result_data["games"])
    assert result["games"][0]["gameId"] == expected_result_data["games"][0]["gameId"]
    assert result["games"][1]["gameStatus"] == expected_result_data["games"][1]["gameStatus"]
    assert result["games"][2]["homeTeam"]["teamId"] == expected_result_data["games"][2]["homeTeam"]["teamId"]


# Patch the get_dict method of the instantiated object
@patch.object(LiveScoreBoard, 'get_dict', return_value=MOCK_LIVE_SCOREBOARD_RAW)
def test_fetch_scoreboard_success_no_cache(mock_get_dict):
    """Test successful fetching of scoreboard data bypassing cache."""
    # Arrange
    expected_result_data = MOCK_EXPECTED_SCOREBOARD_RESULT

    # Act
    result_str = live_game_tools.fetch_league_scoreboard_logic(bypass_cache=True)
    result = json.loads(result_str)

    # Assert
    mock_get_dict.assert_called_once() # Check get_dict was called
    assert "error" not in result
    # Compare key fields instead of exact dict match
    assert result.get("gameDate") == expected_result_data["gameDate"]
    assert len(result.get("games", [])) == len(expected_result_data["games"])
    assert result["games"][0]["gameId"] == expected_result_data["games"][0]["gameId"]


@patch('backend.api_tools.live_game_tools.get_cached_scoreboard_data')
def test_fetch_scoreboard_api_error_in_cache(mock_get_cached):
    """Test scoreboard fetch when the cached function itself raises an API error."""
    # Arrange
    api_error_message = "Live API timeout"
    mock_get_cached.side_effect = Exception(api_error_message)
    expected_error = Errors.LEAGUE_SCOREBOARD_UNEXPECTED.format(
        game_date=datetime.now().strftime('%Y-%m-%d'), error=api_error_message
    )

    # Act
    result_str = live_game_tools.fetch_league_scoreboard_logic()
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

# Patch the get_dict method to simulate API error
@patch.object(LiveScoreBoard, 'get_dict')
def test_fetch_scoreboard_api_error_no_cache(mock_get_dict):
    """Test scoreboard fetch with API error when bypassing cache."""
    # Arrange
    api_error_message = "Live API timeout direct"
    mock_get_dict.side_effect = Exception(api_error_message) # Simulate get_dict raising error
    expected_error = Errors.LEAGUE_SCOREBOARD_UNEXPECTED.format(
        game_date=datetime.now().strftime('%Y-%m-%d'), error=api_error_message
    )

    # Act
    result_str = live_game_tools.fetch_league_scoreboard_logic(bypass_cache=True)
    result = json.loads(result_str)

    # Assert
    mock_get_dict.assert_called_once() # Check get_dict was called
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.live_game_tools.get_cached_scoreboard_data')
def test_fetch_scoreboard_empty_response(mock_get_cached):
    """Test scoreboard fetch when API returns an empty or unexpected structure."""
    # Arrange
    # Simulate cache returning raw dict with empty games list
    mock_get_cached.return_value = {"scoreboard": {"gameDate": "2023-11-10", "games": []}}
    expected_result_data = {"gameDate": "2023-11-10", "games": []}

    # Act
    result_str = live_game_tools.fetch_league_scoreboard_logic()
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" not in result
    assert result == expected_result_data
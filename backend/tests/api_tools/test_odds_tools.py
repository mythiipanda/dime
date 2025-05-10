import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime

# Modules to test
from backend.api_tools import odds_tools
from backend.config import Errors

# Mock data for Odds
MOCK_ODDS_GAME_DATA = [
    {"gameId": "0022300100", "awayTeam": {"teamId": 1, "teamName": "Team A"}, "homeTeam": {"teamId": 2, "teamName": "Team B"}, "odds": [{"provider": "ProviderX", "details": "Spread -5.5"}]},
    {"gameId": "0022300101", "awayTeam": {"teamId": 3, "teamName": "Team C"}, "homeTeam": {"teamId": 4, "teamName": "Team D"}, "odds": [{"provider": "ProviderY", "details": "Total 220.5"}]}
]
MOCK_ODDS_RESPONSE_DICT = {"games": MOCK_ODDS_GAME_DATA}
MOCK_ODDS_EXPECTED_RESULT = {"games": MOCK_ODDS_GAME_DATA} # Logic currently just wraps this

# --- Tests for fetch_odds_data_logic ---

@patch('backend.api_tools.odds_tools.get_cached_odds_data')
def test_fetch_odds_data_success_cached(mock_get_cached):
    """Test successful fetching of odds data from cache."""
    # Arrange
    mock_get_cached.return_value = MOCK_ODDS_RESPONSE_DICT
    expected_result_data = MOCK_ODDS_EXPECTED_RESULT

    # Act
    result_str = odds_tools.fetch_odds_data_logic()
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" not in result
    assert "games" in result
    assert result == expected_result_data

@patch('backend.api_tools.odds_tools.NBALiveHTTP') # Patch the HTTP client directly for bypass
def test_fetch_odds_data_success_no_cache(mock_live_http):
    """Test successful fetching of odds data bypassing cache."""
    # Arrange
    mock_http_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.get_dict.return_value = MOCK_ODDS_RESPONSE_DICT
    mock_http_instance.send_api_request.return_value = mock_response
    mock_live_http.return_value = mock_http_instance

    expected_result_data = MOCK_ODDS_EXPECTED_RESULT

    # Act
    result_str = odds_tools.fetch_odds_data_logic(bypass_cache=True)
    result = json.loads(result_str)

    # Assert
    mock_live_http.assert_called_once()
    mock_http_instance.send_api_request.assert_called_once()
    assert "error" not in result
    assert "games" in result
    assert result == expected_result_data

@patch('backend.api_tools.odds_tools.get_cached_odds_data')
def test_fetch_odds_data_api_error_in_cache(mock_get_cached):
    """Test odds fetch when the cached function itself raises an API error."""
    # Arrange
    api_error_message = "Live API timeout"
    mock_get_cached.side_effect = Exception(api_error_message)
    expected_error = Errors.ODDS_API_UNEXPECTED.format(error=api_error_message)

    # Act
    result_str = odds_tools.fetch_odds_data_logic()
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.odds_tools.NBALiveHTTP')
def test_fetch_odds_data_api_error_no_cache(mock_live_http):
    """Test odds fetch with API error when bypassing cache."""
    # Arrange
    api_error_message = "Live API timeout direct"
    mock_http_instance = MagicMock()
    mock_http_instance.send_api_request.side_effect = Exception(api_error_message)
    mock_live_http.return_value = mock_http_instance
    expected_error = Errors.ODDS_API_UNEXPECTED.format(error=api_error_message)

    # Act
    result_str = odds_tools.fetch_odds_data_logic(bypass_cache=True)
    result = json.loads(result_str)

    # Assert
    mock_live_http.assert_called_once()
    mock_http_instance.send_api_request.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.odds_tools.get_cached_odds_data')
def test_fetch_odds_data_empty_response(mock_get_cached):
    """Test odds fetch when API returns an empty or unexpected structure."""
    # Arrange
    mock_get_cached.return_value = {"unexpected_key": "value"} # Simulate missing 'games'
    expected_result_data = {"games": []} # Expect empty games list

    # Act
    result_str = odds_tools.fetch_odds_data_logic()
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" not in result
    assert "games" in result
    assert result == expected_result_data
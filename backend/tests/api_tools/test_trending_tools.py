import pytest
import json
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime

# Modules to test
from backend.api_tools import trending_tools
from backend.config import Errors, CURRENT_SEASON
from nba_api.stats.library.parameters import SeasonTypeAllStar, StatCategoryAbbreviation

# Mock data for League Leaders (used by trending tools)
MOCK_LEADERS_DATA = [
    {"PLAYER_ID": 1, "RANK": 1, "PLAYER": "Player One", "TEAM": "AAA", "PTS": 30.0},
    {"PLAYER_ID": 2, "RANK": 2, "PLAYER": "Player Two", "TEAM": "BBB", "PTS": 29.5},
    {"PLAYER_ID": 3, "RANK": 3, "PLAYER": "Player Three", "TEAM": "CCC", "PTS": 29.0},
    {"PLAYER_ID": 4, "RANK": 4, "PLAYER": "Player Four", "TEAM": "DDD", "PTS": 28.5},
    {"PLAYER_ID": 5, "RANK": 5, "PLAYER": "Player Five", "TEAM": "EEE", "PTS": 28.0},
    {"PLAYER_ID": 6, "RANK": 6, "PLAYER": "Player Six", "TEAM": "FFF", "PTS": 27.5}
]
MOCK_LEADERS_RESPONSE = {
    "season": CURRENT_SEASON,
    "stat_category": StatCategoryAbbreviation.pts,
    "season_type": SeasonTypeAllStar.regular,
    "leaders": MOCK_LEADERS_DATA
}
MOCK_LEADERS_JSON_STR = json.dumps(MOCK_LEADERS_RESPONSE)
MOCK_LEADERS_ERROR_JSON_STR = json.dumps({"error": "Failed to fetch leaders"})

# --- Tests for fetch_top_performers_logic ---

@patch('backend.api_tools.trending_tools.get_cached_league_leaders')
@patch('backend.api_tools.trending_tools._validate_season_format', return_value=True)
def test_fetch_top_performers_success_cached(mock_validate, mock_get_cached):
    """Test successful fetching of top performers from cache."""
    # Arrange
    mock_get_cached.return_value = MOCK_LEADERS_JSON_STR
    top_n = 3
    expected_top_performers = MOCK_LEADERS_DATA[:top_n]

    # Act
    result_str = trending_tools.fetch_top_performers_logic(top_n=top_n)
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" not in result
    assert "top_performers" in result
    assert len(result["top_performers"]) == top_n
    assert result["top_performers"] == expected_top_performers

@patch('backend.api_tools.trending_tools.fetch_league_leaders_logic') # Patch the direct call for bypass
@patch('backend.api_tools.trending_tools._validate_season_format', return_value=True)
def test_fetch_top_performers_success_no_cache(mock_validate, mock_fetch_leaders):
    """Test successful fetching of top performers bypassing cache."""
    # Arrange
    mock_fetch_leaders.return_value = MOCK_LEADERS_JSON_STR
    top_n = 2
    expected_top_performers = MOCK_LEADERS_DATA[:top_n]

    # Act
    result_str = trending_tools.fetch_top_performers_logic(top_n=top_n, bypass_cache=True)
    result = json.loads(result_str)

    # Assert
    mock_fetch_leaders.assert_called_once()
    assert "error" not in result
    assert "top_performers" in result
    assert len(result["top_performers"]) == top_n
    assert result["top_performers"] == expected_top_performers

def test_fetch_top_performers_invalid_season():
    """Test top performers fetch with invalid season."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = trending_tools.fetch_top_performers_logic(season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_top_performers_invalid_top_n():
    """Test top performers fetch with invalid top_n."""
    # Arrange
    invalid_top_n = 0
    expected_error = Errors.INVALID_TOP_N.format(value=invalid_top_n)

    # Act
    result_str = trending_tools.fetch_top_performers_logic(top_n=invalid_top_n)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.trending_tools.get_cached_league_leaders')
@patch('backend.api_tools.trending_tools._validate_season_format', return_value=True)
def test_fetch_top_performers_leader_fetch_error(mock_validate, mock_get_cached):
    """Test top performers fetch when underlying leader fetch returns an error."""
    # Arrange
    mock_get_cached.return_value = MOCK_LEADERS_ERROR_JSON_STR
    expected_error_data = json.loads(MOCK_LEADERS_ERROR_JSON_STR)

    # Act
    result_str = trending_tools.fetch_top_performers_logic()
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" in result
    assert result == expected_error_data # Should propagate the error dict

@patch('backend.api_tools.trending_tools.get_cached_league_leaders')
@patch('backend.api_tools.trending_tools._validate_season_format', return_value=True)
def test_fetch_top_performers_leader_fetch_invalid_json(mock_validate, mock_get_cached):
    """Test top performers fetch when underlying leader fetch returns invalid JSON."""
    # Arrange
    mock_get_cached.return_value = "invalid json"
    expected_error = Errors.PROCESSING_ERROR.format(error="invalid format from league leaders data")

    # Act
    result_str = trending_tools.fetch_top_performers_logic()
    result = json.loads(result_str)

    # Assert
    mock_validate.assert_called_once() # Ensure validation was called
    mock_get_cached.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

# Test unexpected error during processing *after* successful fetch/cache retrieval
@patch('backend.api_tools.trending_tools.get_cached_league_leaders')
@patch('backend.api_tools.trending_tools._validate_season_format', return_value=True)
def test_fetch_top_performers_unexpected_processing_error(mock_validate, mock_get_cached):
    """Test top performers fetch with unexpected error during JSON processing."""
    # Arrange
    mock_get_cached.return_value = MOCK_LEADERS_JSON_STR # Simulate successful fetch
    processing_error_msg = "Unexpected processing issue"
    expected_error = Errors.TRENDING_UNEXPECTED.format(error=processing_error_msg)

    # Patch json.loads specifically for this test's scope
    with patch('backend.api_tools.trending_tools.json.loads', side_effect=Exception(processing_error_msg)):
        # Act
        result_str = trending_tools.fetch_top_performers_logic()
        # The result_str itself will contain the formatted error JSON
        # result = json.loads(result_str) # Don't load the error string

    # Assert
    mock_validate.assert_called_once()
    mock_get_cached.assert_called_once()
    # Check that the returned string contains the expected error message
    assert "error" in result_str
    assert expected_error in result_str
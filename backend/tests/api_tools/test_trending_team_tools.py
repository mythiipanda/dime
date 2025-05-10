import pytest
import json
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime

# Modules to test
from backend.api_tools import trending_team_tools
from backend.config import Errors, CURRENT_SEASON
from nba_api.stats.library.parameters import SeasonTypeAllStar

# Mock data for Standings (used by trending team tools)
# Reusing MOCK_STANDINGS_DATA structure from league_tools tests
MOCK_STANDINGS_DATA = [
    {'TeamID': 101, 'TeamCity': 'Team', 'TeamName': 'AAA', 'Conference': 'East', 'PlayoffRank': 1, 'WinPct': 0.700, 'WINS': 50, 'LOSSES': 22},
    {'TeamID': 102, 'TeamCity': 'Team', 'TeamName': 'BBB', 'Conference': 'West', 'PlayoffRank': 1, 'WinPct': 0.680, 'WINS': 49, 'LOSSES': 23},
    {'TeamID': 103, 'TeamCity': 'Team', 'TeamName': 'CCC', 'Conference': 'East', 'PlayoffRank': 2, 'WinPct': 0.650, 'WINS': 47, 'LOSSES': 25},
    {'TeamID': 104, 'TeamCity': 'Team', 'TeamName': 'DDD', 'Conference': 'West', 'PlayoffRank': 2, 'WinPct': 0.660, 'WINS': 48, 'LOSSES': 24}
]
MOCK_STANDINGS_RESPONSE = {"standings": MOCK_STANDINGS_DATA}
MOCK_STANDINGS_JSON_STR = json.dumps(MOCK_STANDINGS_RESPONSE)
MOCK_STANDINGS_ERROR_JSON_STR = json.dumps({"error": "Failed to fetch standings"})

# --- Tests for fetch_top_teams_logic ---

@patch('backend.api_tools.trending_team_tools.get_cached_standings_for_trending')
@patch('backend.api_tools.trending_team_tools._validate_season_format', return_value=True)
def test_fetch_top_teams_success_cached(mock_validate, mock_get_cached):
    """Test successful fetching of top teams from cache."""
    # Arrange
    mock_get_cached.return_value = MOCK_STANDINGS_JSON_STR
    top_n = 2
    # Expected result after sorting by WinPct and selecting top N + essential fields
    expected_top_teams = [
        {'TeamID': 101, 'TeamName': 'AAA', 'Conference': 'East', 'PlayoffRank': 1, 'WinPct': 0.700, 'WINS': 50, 'LOSSES': 22},
        {'TeamID': 102, 'TeamName': 'BBB', 'Conference': 'West', 'PlayoffRank': 1, 'WinPct': 0.680, 'WINS': 49, 'LOSSES': 23}
    ]

    # Act
    result_str = trending_team_tools.fetch_top_teams_logic(top_n=top_n)
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" not in result
    assert "top_teams" in result
    assert len(result["top_teams"]) == top_n
    # Compare essential fields
    for i in range(top_n):
        assert result["top_teams"][i]["TeamID"] == expected_top_teams[i]["TeamID"]
        assert result["top_teams"][i]["WinPct"] == expected_top_teams[i]["WinPct"]

@patch('backend.api_tools.trending_team_tools.fetch_league_standings_logic') # Patch direct call for bypass
@patch('backend.api_tools.trending_team_tools._validate_season_format', return_value=True)
def test_fetch_top_teams_success_no_cache(mock_validate, mock_fetch_standings):
    """Test successful fetching of top teams bypassing cache."""
    # Arrange
    mock_fetch_standings.return_value = MOCK_STANDINGS_JSON_STR
    top_n = 1
    expected_top_teams = [
        {'TeamID': 101, 'TeamName': 'AAA', 'Conference': 'East', 'PlayoffRank': 1, 'WinPct': 0.700, 'WINS': 50, 'LOSSES': 22}
    ]

    # Act
    result_str = trending_team_tools.fetch_top_teams_logic(top_n=top_n, bypass_cache=True)
    result = json.loads(result_str)

    # Assert
    mock_fetch_standings.assert_called_once()
    assert "error" not in result
    assert "top_teams" in result
    assert len(result["top_teams"]) == top_n
    assert result["top_teams"][0]["TeamID"] == expected_top_teams[0]["TeamID"]

def test_fetch_top_teams_invalid_season():
    """Test top teams fetch with invalid season."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = trending_team_tools.fetch_top_teams_logic(season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_top_teams_invalid_top_n():
    """Test top teams fetch with invalid top_n."""
    # Arrange
    invalid_top_n = 0
    expected_error = Errors.INVALID_TOP_N.format(value=invalid_top_n)

    # Act
    result_str = trending_team_tools.fetch_top_teams_logic(top_n=invalid_top_n)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.trending_team_tools.get_cached_standings_for_trending')
@patch('backend.api_tools.trending_team_tools._validate_season_format', return_value=True)
def test_fetch_top_teams_standings_fetch_error(mock_validate, mock_get_cached):
    """Test top teams fetch when underlying standings fetch returns an error."""
    # Arrange
    mock_get_cached.return_value = MOCK_STANDINGS_ERROR_JSON_STR
    expected_error_data = json.loads(MOCK_STANDINGS_ERROR_JSON_STR)

    # Act
    result_str = trending_team_tools.fetch_top_teams_logic()
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" in result
    assert result == expected_error_data # Propagate error

@patch('backend.api_tools.trending_team_tools.get_cached_standings_for_trending')
@patch('backend.api_tools.trending_team_tools._validate_season_format', return_value=True)
def test_fetch_top_teams_standings_invalid_json(mock_validate, mock_get_cached):
    """Test top teams fetch when underlying standings fetch returns invalid JSON."""
    # Arrange
    mock_get_cached.return_value = "invalid json"
    expected_error = Errors.PROCESSING_ERROR.format(error="invalid format from standings data")

    # Act
    result_str = trending_team_tools.fetch_top_teams_logic()
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.trending_team_tools.get_cached_standings_for_trending', side_effect=Exception("Cache function error"))
@patch('backend.api_tools.trending_team_tools._validate_season_format', return_value=True)
def test_fetch_top_teams_unexpected_error(mock_validate, mock_get_cached):
    """Test top teams fetch with unexpected error."""
    # Arrange
    error_message = "Cache function error"
    expected_error = Errors.TRENDING_TEAMS_UNEXPECTED.format(error=error_message)

    # Act
    result_str = trending_team_tools.fetch_top_teams_logic()
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.trending_team_tools.get_cached_standings_for_trending')
@patch('backend.api_tools.trending_team_tools._validate_season_format', return_value=True)
def test_fetch_top_teams_sorting_error(mock_validate, mock_get_cached):
    """Test top teams fetch when sorting fails (e.g., invalid WinPct)."""
    # Arrange
    # Simulate standings data with a non-numeric WinPct
    bad_standings_data = [
        {'TeamID': 101, 'TeamName': 'AAA', 'WinPct': 0.7},
        {'TeamID': 102, 'TeamName': 'BBB', 'WinPct': "bad_value"}, # Invalid value
        {'TeamID': 103, 'TeamName': 'CCC', 'WinPct': 0.6}
    ]
    mock_get_cached.return_value = json.dumps({"standings": bad_standings_data})
    top_n = 2

    # Act
    result_str = trending_team_tools.fetch_top_teams_logic(top_n=top_n)
    result = json.loads(result_str)

    # Assert
    # Expect it to return the top N unsorted items due to the warning log
    mock_get_cached.assert_called_once()
    assert "error" not in result
    assert "top_teams" in result
    assert len(result["top_teams"]) == top_n
    # Check if the first two (unsorted) items are returned
    assert result["top_teams"][0]["TeamID"] == 101
    assert result["top_teams"][1]["TeamID"] == 102
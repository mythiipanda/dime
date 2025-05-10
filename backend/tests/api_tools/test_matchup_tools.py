import pytest
import json
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime

# Modules to test
from backend.api_tools import matchup_tools
from backend.config import Errors, CURRENT_SEASON
from nba_api.stats.library.parameters import SeasonTypeAllStar

# Mock data
MOCK_DEF_PLAYER_ID = "201939" # Stephen Curry
MOCK_OFF_PLAYER_ID = "2544"   # LeBron James
MOCK_SEASON = "2022-23" # Use a historical season for cache testing

# Mock data for LeagueSeasonMatchups
MOCK_SEASON_MATCHUPS_ROWSET = [
    ["0022200001", "GSW vs. LAL", MOCK_OFF_PLAYER_ID, "LeBron James", MOCK_DEF_PLAYER_ID, "Stephen Curry", 10.5, 5, 2, 4, 0, 1, "5:00", 1, 3, 0, 1, 1, 0, 0, 0],
    ["0022200100", "LAL @ GSW", MOCK_OFF_PLAYER_ID, "LeBron James", MOCK_DEF_PLAYER_ID, "Stephen Curry", 12.0, 7, 3, 5, 1, 2, "6:30", 2, 4, 1, 1, 0, 1, 1, 1]
]
MOCK_SEASON_MATCHUPS_HEADERS = [
    'GAME_ID', 'MATCHUP', 'OFF_PLAYER_ID', 'OFF_PLAYER_NAME', 'DEF_PLAYER_ID', 'DEF_PLAYER_NAME',
    'PARTIAL_POSS', 'PLAYER_PTS', 'PLAYER_FGM', 'PLAYER_FGA', 'PLAYER_FG3M',
    'PLAYER_FG3A', 'MATCHUP_MIN', 'MATCHUP_FGM', 'MATCHUP_FGA', 'MATCHUP_FG3M',
    'MATCHUP_FG3A', 'MATCHUP_TOV', 'HELP_BLK', 'HELP_FGM', 'HELP_FGA' # Simplified headers
]
MOCK_SEASON_MATCHUPS_RESULT_SET = {"name": "SeasonMatchups", "headers": MOCK_SEASON_MATCHUPS_HEADERS, "rowSet": MOCK_SEASON_MATCHUPS_ROWSET}
MOCK_SEASON_MATCHUPS_RESPONSE_DICT = {"resultSets": [MOCK_SEASON_MATCHUPS_RESULT_SET]}
MOCK_PROCESSED_SEASON_MATCHUPS = [dict(zip(MOCK_SEASON_MATCHUPS_HEADERS, row)) for row in MOCK_SEASON_MATCHUPS_ROWSET]

# Mock data for MatchupsRollup
MOCK_ROLLUP_ROWSET = [
    [MOCK_OFF_PLAYER_ID, "LeBron James", 5, "15:30", 25.0, 12, 5, 10, 1, 3, 3, 7, 1, 2, 2, 1],
    [201935, "James Harden", 4, "12:00", 20.0, 10, 4, 8, 2, 5, 2, 5, 1, 3, 1, 0]
]
MOCK_ROLLUP_HEADERS = [
    'OFF_PLAYER_ID', 'OFF_PLAYER_NAME', 'GP', 'MATCHUP_MIN',
    'PARTIAL_POSS', 'PLAYER_PTS', 'PLAYER_FGM', 'PLAYER_FGA',
    'PLAYER_FG3M', 'PLAYER_FG3A', 'MATCHUP_FGM', 'MATCHUP_FGA',
    'MATCHUP_FG3M', 'MATCHUP_FG3A', 'MATCHUP_TOV', 'MATCHUP_HELP_BLK'
]
MOCK_ROLLUP_RESULT_SET = {"name": "MatchupsRollup", "headers": MOCK_ROLLUP_HEADERS, "rowSet": MOCK_ROLLUP_ROWSET}
MOCK_ROLLUP_RESPONSE_DICT = {"resultSets": [MOCK_ROLLUP_RESULT_SET]}
MOCK_PROCESSED_ROLLUP = [dict(zip(MOCK_ROLLUP_HEADERS, row)) for row in MOCK_ROLLUP_ROWSET]

# --- Tests for fetch_league_season_matchups_logic ---

@patch('backend.api_tools.matchup_tools.get_cached_matchups')
@patch('backend.api_tools.matchup_tools._validate_season_format', return_value=True)
def test_fetch_season_matchups_success_cached(mock_validate, mock_get_cached):
    """Test successful fetching of season matchups from cache."""
    # Arrange
    mock_get_cached.return_value = MOCK_SEASON_MATCHUPS_RESPONSE_DICT
    expected_result_data = {"def_player_id": MOCK_DEF_PLAYER_ID, "off_player_id": MOCK_OFF_PLAYER_ID, "matchups": MOCK_PROCESSED_SEASON_MATCHUPS}

    # Act
    result_str = matchup_tools.fetch_league_season_matchups_logic(
        def_player_id=MOCK_DEF_PLAYER_ID, off_player_id=MOCK_OFF_PLAYER_ID, season=MOCK_SEASON
    )
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" not in result
    assert result == expected_result_data

@patch('backend.api_tools.matchup_tools.LeagueSeasonMatchups')
@patch('backend.api_tools.matchup_tools._validate_season_format', return_value=True)
def test_fetch_season_matchups_success_no_cache(mock_validate, mock_endpoint):
    """Test successful fetching of season matchups bypassing cache."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.get_dict.return_value = MOCK_SEASON_MATCHUPS_RESPONSE_DICT
    mock_endpoint.return_value = mock_endpoint_instance
    expected_result_data = {"def_player_id": MOCK_DEF_PLAYER_ID, "off_player_id": MOCK_OFF_PLAYER_ID, "matchups": MOCK_PROCESSED_SEASON_MATCHUPS}

    # Act
    result_str = matchup_tools.fetch_league_season_matchups_logic(
        def_player_id=MOCK_DEF_PLAYER_ID, off_player_id=MOCK_OFF_PLAYER_ID, season=MOCK_SEASON, bypass_cache=True
    )
    result = json.loads(result_str)

    # Assert
    mock_endpoint.assert_called_once()
    assert "error" not in result
    assert result == expected_result_data

def test_fetch_season_matchups_missing_id():
    """Test season matchups fetch with missing player ID."""
    # Arrange
    expected_error = Errors.MISSING_PLAYER_ID

    # Act
    result_str = matchup_tools.fetch_league_season_matchups_logic(def_player_id="", off_player_id=MOCK_OFF_PLAYER_ID, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_season_matchups_invalid_season():
    """Test season matchups fetch with invalid season."""
    # Arrange
    invalid_season = "abc"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = matchup_tools.fetch_league_season_matchups_logic(
        def_player_id=MOCK_DEF_PLAYER_ID, off_player_id=MOCK_OFF_PLAYER_ID, season=invalid_season
    )
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.matchup_tools.get_cached_matchups')
@patch('backend.api_tools.matchup_tools._validate_season_format', return_value=True)
def test_fetch_season_matchups_api_error(mock_validate, mock_get_cached):
    """Test season matchups fetch with API error."""
    # Arrange
    api_error_message = "NBA API timeout"
    mock_get_cached.side_effect = Exception(api_error_message)
    expected_error = Errors.MATCHUPS_API.format(error=api_error_message)

    # Act
    result_str = matchup_tools.fetch_league_season_matchups_logic(
        def_player_id=MOCK_DEF_PLAYER_ID, off_player_id=MOCK_OFF_PLAYER_ID, season=MOCK_SEASON
    )
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

# --- Tests for fetch_matchups_rollup_logic ---

@patch('backend.api_tools.matchup_tools.get_cached_matchups')
@patch('backend.api_tools.matchup_tools._validate_season_format', return_value=True)
def test_fetch_rollup_success_cached(mock_validate, mock_get_cached):
    """Test successful fetching of matchup rollup from cache."""
    # Arrange
    mock_get_cached.return_value = MOCK_ROLLUP_RESPONSE_DICT
    expected_result_data = {"def_player_id": MOCK_DEF_PLAYER_ID, "rollup": MOCK_PROCESSED_ROLLUP}

    # Act
    result_str = matchup_tools.fetch_matchups_rollup_logic(def_player_id=MOCK_DEF_PLAYER_ID, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" not in result
    assert result == expected_result_data

@patch('backend.api_tools.matchup_tools.MatchupsRollup')
@patch('backend.api_tools.matchup_tools._validate_season_format', return_value=True)
def test_fetch_rollup_success_no_cache(mock_validate, mock_endpoint):
    """Test successful fetching of matchup rollup bypassing cache."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.get_dict.return_value = MOCK_ROLLUP_RESPONSE_DICT
    mock_endpoint.return_value = mock_endpoint_instance
    expected_result_data = {"def_player_id": MOCK_DEF_PLAYER_ID, "rollup": MOCK_PROCESSED_ROLLUP}

    # Act
    result_str = matchup_tools.fetch_matchups_rollup_logic(def_player_id=MOCK_DEF_PLAYER_ID, season=MOCK_SEASON, bypass_cache=True)
    result = json.loads(result_str)

    # Assert
    mock_endpoint.assert_called_once()
    assert "error" not in result
    assert result == expected_result_data

def test_fetch_rollup_missing_id():
    """Test matchup rollup fetch with missing player ID."""
    # Arrange
    expected_error = Errors.MISSING_PLAYER_ID

    # Act
    result_str = matchup_tools.fetch_matchups_rollup_logic(def_player_id="", season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_rollup_invalid_season():
    """Test matchup rollup fetch with invalid season."""
    # Arrange
    invalid_season = "abc"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = matchup_tools.fetch_matchups_rollup_logic(def_player_id=MOCK_DEF_PLAYER_ID, season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.matchup_tools.get_cached_matchups')
@patch('backend.api_tools.matchup_tools._validate_season_format', return_value=True)
def test_fetch_rollup_api_error(mock_validate, mock_get_cached):
    """Test matchup rollup fetch with API error."""
    # Arrange
    api_error_message = "NBA API timeout"
    mock_get_cached.side_effect = Exception(api_error_message)
    expected_error = Errors.MATCHUPS_ROLLUP_API.format(error=api_error_message)

    # Act
    result_str = matchup_tools.fetch_matchups_rollup_logic(def_player_id=MOCK_DEF_PLAYER_ID, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error
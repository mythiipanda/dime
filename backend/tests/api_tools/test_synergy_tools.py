import pytest
import json
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime

# Modules to test
from backend.api_tools import synergy_tools
from backend.config import Errors, CURRENT_SEASON
from nba_api.stats.library.parameters import (
    LeagueID, PerModeSimple, PlayerOrTeamAbbreviation, SeasonTypeAllStar,
    PlayTypeNullable, TypeGroupingNullable
)

# Mock data for SynergyPlayTypes
MOCK_SYNERGY_ROWSET = [
    [1610612738, "BOS", "Boston Celtics", "Isolation", "Offensive", 1, 82, 10.0, 0.95, 0.450, 0.500, 0.600, 0.100, 100, 95],
    [1610612738, "BOS", "Boston Celtics", "Transition", "Offensive", 2, 82, 15.0, 1.10, 0.550, 0.620, 0.650, 0.080, 150, 165]
    # Add more rows if needed
]
MOCK_SYNERGY_HEADERS = [
    "TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME", "PLAY_TYPE", "TYPE_GROUPING",
    "PERCENTILE", "GP", "POSS_PCT", "PPP", "FG_PCT", "EFG_PCT", "SCORE_POSS_PCT",
    "TOV_POSS_PCT", "POSS", "PTS"
]
MOCK_SYNERGY_RESULT_SET = {
    "name": "SynergyPlayType",
    "headers": MOCK_SYNERGY_HEADERS,
    "rowSet": MOCK_SYNERGY_ROWSET
}
MOCK_SYNERGY_RESPONSE_DICT = {"resultSets": [MOCK_SYNERGY_RESULT_SET]}

# Expected processed data (list of dicts)
MOCK_PROCESSED_SYNERGY_DATA = [
    dict(zip(MOCK_SYNERGY_HEADERS, row)) for row in MOCK_SYNERGY_ROWSET
]

# --- Tests for fetch_synergy_play_types_logic ---

@patch('backend.api_tools.synergy_tools.get_cached_synergy_data')
@patch('backend.api_tools.synergy_tools._validate_season_format', return_value=True)
def test_fetch_synergy_success_cached(mock_validate, mock_get_cached):
    """Test successful fetching of synergy data from cache."""
    # Arrange
    # Simulate cached function returning the raw API dict
    mock_get_cached.return_value = MOCK_SYNERGY_RESPONSE_DICT
    expected_result_data = {"synergy_stats": MOCK_PROCESSED_SYNERGY_DATA}

    # Act
    result_str = synergy_tools.fetch_synergy_play_types_logic(season=CURRENT_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" not in result
    assert "synergy_stats" in result
    # Compare the processed data part
    assert result["synergy_stats"] == expected_result_data["synergy_stats"]

@patch('backend.api_tools.synergy_tools.SynergyPlayTypes')
@patch('backend.api_tools.synergy_tools._validate_season_format', return_value=True)
def test_fetch_synergy_success_no_cache(mock_validate, mock_synergy_endpoint):
    """Test successful fetching of synergy data without cache."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.get_dict.return_value = MOCK_SYNERGY_RESPONSE_DICT
    mock_synergy_endpoint.return_value = mock_endpoint_instance
    expected_result_data = {"synergy_stats": MOCK_PROCESSED_SYNERGY_DATA}

    # Act
    # Bypass cache explicitly, also test passing a specific play type
    result_str = synergy_tools.fetch_synergy_play_types_logic(
        season=CURRENT_SEASON, play_type="Isolation", bypass_cache=True
    )
    result = json.loads(result_str)

    # Assert
    mock_synergy_endpoint.assert_called_once()
    # Check specific args passed due to bypass_cache=True
    call_args, call_kwargs = mock_synergy_endpoint.call_args
    assert call_kwargs.get('play_type_nullable') == "Isolation"
    assert call_kwargs.get('season') == CURRENT_SEASON

    assert "error" not in result
    assert "synergy_stats" in result
    assert result["synergy_stats"] == expected_result_data["synergy_stats"]

def test_fetch_synergy_invalid_season():
    """Test synergy fetch with invalid season format."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = synergy_tools.fetch_synergy_play_types_logic(season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_synergy_invalid_play_type():
    """Test synergy fetch with invalid play type."""
    # Arrange
    invalid_play_type = "InvalidPlay"
    expected_error = Errors.INVALID_PLAY_TYPE.format(play_type=invalid_play_type)

    # Act
    result_str = synergy_tools.fetch_synergy_play_types_logic(play_type=invalid_play_type)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_synergy_invalid_type_grouping():
    """Test synergy fetch with invalid type grouping."""
    # Arrange
    invalid_grouping = "neither"
    expected_error = Errors.INVALID_TYPE_GROUPING.format(type_grouping=invalid_grouping)

    # Act
    result_str = synergy_tools.fetch_synergy_play_types_logic(type_grouping=invalid_grouping)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.synergy_tools.get_cached_synergy_data')
@patch('backend.api_tools.synergy_tools._validate_season_format', return_value=True)
def test_fetch_synergy_api_error(mock_validate, mock_get_cached):
    """Test synergy fetch with API error during cache fetch."""
    # Arrange
    api_error_message = "NBA API timeout"
    mock_get_cached.side_effect = Exception(api_error_message)
    expected_error = Errors.SYNERGY_API.format(error=api_error_message)

    # Act
    result_str = synergy_tools.fetch_synergy_play_types_logic(season=CURRENT_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.synergy_tools.get_cached_synergy_data')
@patch('backend.api_tools.synergy_tools._validate_season_format', return_value=True)
def test_fetch_synergy_processing_error(mock_validate, mock_get_cached):
    """Test synergy fetch with processing error (e.g., unexpected response structure)."""
    # Arrange
    # Simulate cached function returning dict without 'resultSets'
    mock_get_cached.return_value = {"some_other_key": []}
    # The function should return an empty list in this case now, not an error
    # expected_error = Errors.SYNERGY_PROCESSING

    # Act
    result_str = synergy_tools.fetch_synergy_play_types_logic(season=CURRENT_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" not in result
    assert "synergy_stats" in result
    assert result["synergy_stats"] == [] # Expect empty list due to processing fallback

@patch('backend.api_tools.synergy_tools.get_cached_synergy_data')
@patch('backend.api_tools.synergy_tools._validate_season_format', return_value=True)
def test_fetch_synergy_unexpected_error(mock_validate, mock_get_cached):
    """Test synergy fetch with unexpected error during processing."""
    # Arrange
    mock_get_cached.return_value = MOCK_SYNERGY_RESPONSE_DICT
    processing_error_msg = "Something broke during processing"
    # Patch json.dumps within the function's scope to raise error after processing
    with patch('backend.api_tools.synergy_tools.pd.DataFrame', side_effect=Exception(processing_error_msg)):
         expected_error = Errors.SYNERGY_UNEXPECTED.format(error=processing_error_msg)

         # Act
         result_str = synergy_tools.fetch_synergy_play_types_logic(season=CURRENT_SEASON)
         result = json.loads(result_str)

    # Assert
    mock_get_cached.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error
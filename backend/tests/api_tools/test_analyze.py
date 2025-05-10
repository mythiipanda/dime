import pytest
import json
from unittest.mock import patch, MagicMock
import pandas as pd

# Modules to test
from backend.api_tools import analyze
from backend.api_tools.utils import PlayerNotFoundError, format_response # Import format_response if needed by logic
from backend.config import Errors, CURRENT_SEASON, DEFAULT_TIMEOUT # Added DEFAULT_TIMEOUT
from backend.config import Errors, CURRENT_SEASON
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, LeagueID

# Mock data
MOCK_PLAYER_ID = 2544 # LeBron James example
MOCK_PLAYER_NAME = "LeBron James"
MOCK_SEASON = CURRENT_SEASON
MOCK_OVERALL_DASHBOARD_DATA = [ # Data structure from OverallPlayerDashboard in the endpoint
    {"GROUP_SET": "Overall", "PLAYER_ID": MOCK_PLAYER_ID, "PLAYER_NAME": MOCK_PLAYER_NAME, "GP": 71, "W": 40, "L": 31, "W_PCT": 0.563, "MIN": 35.3, "PTS": 25.7} # Simplified
]
mock_overall_dashboard_df = pd.DataFrame(MOCK_OVERALL_DASHBOARD_DATA)

# --- Tests for analyze_player_stats_logic ---

@patch('backend.api_tools.analyze.find_player_id_or_error')
@patch('backend.api_tools.analyze.playerdashboardbyyearoveryear.PlayerDashboardByYearOverYear') # Corrected endpoint name
@patch('backend.api_tools.analyze._process_dataframe')
@patch('backend.api_tools.analyze._validate_season_format', return_value=True)
def test_analyze_player_stats_success(mock_validate, mock_process_df, mock_dashboard_endpoint, mock_find_player):
    """Test successful fetching of player analysis (overall dashboard) stats."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)

    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.overall_player_dashboard.get_data_frame.return_value = mock_overall_dashboard_df
    mock_dashboard_endpoint.return_value = mock_endpoint_instance

    # Mock _process_dataframe return value for the overall dashboard
    mock_process_df.return_value = MOCK_OVERALL_DASHBOARD_DATA[0] # single_row=True

    # Act
    result_str = analyze.analyze_player_stats_logic(MOCK_PLAYER_NAME, season=MOCK_SEASON)
    result = json.loads(result_str) # The function returns JSON string

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_dashboard_endpoint.assert_called_once_with(
        player_id=MOCK_PLAYER_ID, season=MOCK_SEASON, season_type_playoffs=SeasonTypeAllStar.regular,
        per_mode_detailed=PerModeDetailed.per_game, league_id_nullable=LeagueID.nba, timeout=DEFAULT_TIMEOUT
    )
    mock_process_df.assert_called_once()
    assert "error" not in result
    assert result.get("player_id") == MOCK_PLAYER_ID
    assert result.get("player_name") == MOCK_PLAYER_NAME
    assert "overall_dashboard_stats" in result
    assert result["overall_dashboard_stats"] == MOCK_OVERALL_DASHBOARD_DATA[0]

@patch('backend.api_tools.analyze.find_player_id_or_error')
def test_analyze_player_stats_player_not_found(mock_find_player):
    """Test player analysis fetch when player is not found."""
    # Arrange
    identifier = "Unknown Player"
    mock_find_player.side_effect = PlayerNotFoundError(identifier)
    expected_error = Errors.PLAYER_NOT_FOUND.format(name=identifier)

    # Act
    result_str = analyze.analyze_player_stats_logic(identifier, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(identifier)
    assert "error" in result
    assert result["error"] == expected_error

def test_analyze_player_stats_invalid_season():
    """Test player analysis fetch with invalid season."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = analyze.analyze_player_stats_logic(MOCK_PLAYER_NAME, season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.analyze.find_player_id_or_error')
@patch('backend.api_tools.analyze.playerdashboardbyyearoveryear.PlayerDashboardByYearOverYear') # Corrected endpoint name
@patch('backend.api_tools.analyze._validate_season_format', return_value=True)
def test_analyze_player_stats_api_error(mock_validate, mock_dashboard_endpoint, mock_find_player):
    """Test player analysis fetch with API error."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    api_error_message = "NBA API timeout"
    mock_dashboard_endpoint.side_effect = Exception(api_error_message)
    expected_error = Errors.PLAYER_ANALYSIS_API.format(name=MOCK_PLAYER_NAME, error=api_error_message)

    # Act
    result_str = analyze.analyze_player_stats_logic(MOCK_PLAYER_NAME, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once()
    mock_dashboard_endpoint.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.analyze.find_player_id_or_error')
@patch('backend.api_tools.analyze.playerdashboardbyyearoveryear.PlayerDashboardByYearOverYear') # Corrected endpoint name
@patch('backend.api_tools.analyze._process_dataframe')
@patch('backend.api_tools.analyze._validate_season_format', return_value=True)
def test_analyze_player_stats_processing_error(mock_validate, mock_process_df, mock_dashboard_endpoint, mock_find_player):
    """Test player analysis fetch with processing error."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.overall_player_dashboard.get_data_frame.return_value = mock_overall_dashboard_df # Non-empty
    mock_dashboard_endpoint.return_value = mock_endpoint_instance

    mock_process_df.return_value = None # Simulate processing error
    expected_error = Errors.PLAYER_ANALYSIS_PROCESSING.format(name=MOCK_PLAYER_NAME)

    # Act
    result_str = analyze.analyze_player_stats_logic(MOCK_PLAYER_NAME, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once()
    mock_dashboard_endpoint.assert_called_once()
    mock_process_df.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.analyze.find_player_id_or_error')
@patch('backend.api_tools.analyze.playerdashboardbyyearoveryear.PlayerDashboardByYearOverYear') # Corrected endpoint name
@patch('backend.api_tools.analyze._process_dataframe')
@patch('backend.api_tools.analyze._validate_season_format', return_value=True)
def test_analyze_player_stats_empty_df(mock_validate, mock_process_df, mock_dashboard_endpoint, mock_find_player):
    """Test player analysis fetch with empty DataFrame response."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.overall_player_dashboard.get_data_frame.return_value = pd.DataFrame() # Empty DF
    mock_dashboard_endpoint.return_value = mock_endpoint_instance

    mock_process_df.return_value = {} # Processing empty DF (single row) returns empty dict

    # Act
    result_str = analyze.analyze_player_stats_logic(MOCK_PLAYER_NAME, season=MOCK_SEASON)
    result = json.loads(result_str) # Expecting empty data, not error

    # Assert
    mock_find_player.assert_called_once()
    mock_dashboard_endpoint.assert_called_once()
    mock_process_df.assert_called_once()
    assert "error" not in result
    assert "overall_dashboard_stats" in result
    assert result["overall_dashboard_stats"] == {}
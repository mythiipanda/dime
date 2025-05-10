import pytest
import json
from unittest.mock import patch, MagicMock
import pandas as pd

# Modules to test
from backend.api_tools import team_tracking
from backend.api_tools.utils import TeamNotFoundError # Import custom exception
from backend.config import Errors, CURRENT_SEASON
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed

# Mock data - Reuse team info from team_tools tests if possible
MOCK_TEAM_ID = 1610612738 # Boston Celtics example
MOCK_TEAM_NAME = "Boston Celtics"
MOCK_TEAM_IDENTIFIER = "Celtics" # Example identifier
MOCK_SEASON = CURRENT_SEASON

# Mock data for TeamDashPtReb
MOCK_TEAM_REB_OVERALL_DATA = [{"TEAM_ID": MOCK_TEAM_ID, "TEAM_NAME": MOCK_TEAM_NAME, "GP": 70, "REB": 45.0, "OREB": 10.0, "DREB": 35.0, "C_REB": 15.0, "UC_REB": 30.0, "REB_PCT": 0.520, "C_REB_PCT": 0.333}]
MOCK_TEAM_REB_SHOT_TYPE_DATA = [{"TEAM_ID": MOCK_TEAM_ID, "SHOT_TYPE": "2PT", "REB": 30.0}, {"TEAM_ID": MOCK_TEAM_ID, "SHOT_TYPE": "3PT", "REB": 15.0}]
MOCK_TEAM_REB_CONTESTED_DATA = [{"TEAM_ID": MOCK_TEAM_ID, "CONTEST_TYPE": "Contested", "REB": 15.0}, {"TEAM_ID": MOCK_TEAM_ID, "CONTEST_TYPE": "Uncontested", "REB": 30.0}]
MOCK_TEAM_REB_SHOT_DIST_DATA = [{"TEAM_ID": MOCK_TEAM_ID, "SHOT_DISTANCE_RANGE": "0-5 ft", "REB": 25.0}]
MOCK_TEAM_REB_REB_DIST_DATA = [{"TEAM_ID": MOCK_TEAM_ID, "REB_DISTANCE_RANGE": "0-3 ft", "REB": 20.0}]

mock_team_reb_overall_df = pd.DataFrame(MOCK_TEAM_REB_OVERALL_DATA)
mock_team_reb_shot_type_df = pd.DataFrame(MOCK_TEAM_REB_SHOT_TYPE_DATA)
mock_team_reb_contested_df = pd.DataFrame(MOCK_TEAM_REB_CONTESTED_DATA)
mock_team_reb_shot_dist_df = pd.DataFrame(MOCK_TEAM_REB_SHOT_DIST_DATA)
mock_team_reb_reb_dist_df = pd.DataFrame(MOCK_TEAM_REB_REB_DIST_DATA)

# --- Tests for fetch_team_rebounding_stats_logic ---

@patch('backend.api_tools.team_tracking.find_team_id_or_error')
@patch('backend.api_tools.team_tracking.teamdashptreb.TeamDashPtReb')
@patch('backend.api_tools.team_tracking._process_dataframe')
@patch('backend.api_tools.team_tracking._validate_season_format', return_value=True)
@patch('backend.api_tools.team_tracking.validate_date_format', return_value=True) # Assume dates valid if passed
def test_fetch_team_rebounding_stats_success(mock_validate_date, mock_validate_season, mock_process_df, mock_reb_endpoint, mock_find_team):
    """Test successful fetching of team rebounding stats."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)

    mock_reb_instance = MagicMock()
    mock_reb_instance.overall_rebounding.get_data_frame.return_value = mock_team_reb_overall_df
    mock_reb_instance.shot_type_rebounding.get_data_frame.return_value = mock_team_reb_shot_type_df
    mock_reb_instance.num_contested_rebounding.get_data_frame.return_value = mock_team_reb_contested_df
    mock_reb_instance.shot_distance_rebounding.get_data_frame.return_value = mock_team_reb_shot_dist_df
    mock_reb_instance.reb_distance_rebounding.get_data_frame.return_value = mock_team_reb_reb_dist_df
    mock_reb_endpoint.return_value = mock_reb_instance

    # Mock _process_dataframe return values
    mock_process_df.side_effect = [
        MOCK_TEAM_REB_OVERALL_DATA[0],   # overall
        MOCK_TEAM_REB_SHOT_TYPE_DATA,    # shot_type
        MOCK_TEAM_REB_CONTESTED_DATA,    # contested
        MOCK_TEAM_REB_SHOT_DIST_DATA,    # distances
        MOCK_TEAM_REB_REB_DIST_DATA      # reb_dist
    ]

    # Act
    result_str = team_tracking.fetch_team_rebounding_stats_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once_with(MOCK_TEAM_IDENTIFIER)
    mock_reb_endpoint.assert_called_once()
    assert mock_process_df.call_count == 5 # 5 reb DFs
    assert "error" not in result
    assert result.get("team_id") == MOCK_TEAM_ID
    assert result.get("team_name") == MOCK_TEAM_NAME
    assert "overall" in result
    assert "by_shot_type" in result
    assert result["overall"] == MOCK_TEAM_REB_OVERALL_DATA[0]
    assert result["by_shot_type"] == MOCK_TEAM_REB_SHOT_TYPE_DATA

@patch('backend.api_tools.team_tracking.find_team_id_or_error')
def test_fetch_team_rebounding_stats_team_not_found(mock_find_team):
    """Test team rebounding fetch when team is not found."""
    # Arrange
    identifier = "Unknown Team"
    mock_find_team.side_effect = TeamNotFoundError(identifier)
    expected_error = Errors.TEAM_NOT_FOUND.format(identifier=identifier)

    # Act
    result_str = team_tracking.fetch_team_rebounding_stats_logic(identifier, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once_with(identifier)
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_team_rebounding_stats_invalid_season():
    """Test team rebounding fetch with invalid season."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = team_tracking.fetch_team_rebounding_stats_logic(MOCK_TEAM_IDENTIFIER, season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.team_tracking.find_team_id_or_error')
@patch('backend.api_tools.team_tracking.teamdashptreb.TeamDashPtReb')
@patch('backend.api_tools.team_tracking._validate_season_format', return_value=True)
def test_fetch_team_rebounding_stats_api_error(mock_validate, mock_reb_endpoint, mock_find_team):
    """Test team rebounding fetch with API error."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)
    api_error_message = "NBA API timeout"
    mock_reb_endpoint.side_effect = Exception(api_error_message)
    expected_error = Errors.TEAM_REBOUNDING_UNEXPECTED.format(identifier=MOCK_TEAM_IDENTIFIER, error=api_error_message)

    # Act
    result_str = team_tracking.fetch_team_rebounding_stats_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once()
    mock_reb_endpoint.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.team_tracking.find_team_id_or_error')
@patch('backend.api_tools.team_tracking.teamdashptreb.TeamDashPtReb')
@patch('backend.api_tools.team_tracking._process_dataframe')
@patch('backend.api_tools.team_tracking._validate_season_format', return_value=True)
def test_fetch_team_rebounding_stats_processing_error(mock_validate, mock_process_df, mock_reb_endpoint, mock_find_team):
    """Test team rebounding fetch with processing error."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)
    mock_reb_instance = MagicMock()
    mock_reb_instance.overall_rebounding.get_data_frame.return_value = mock_team_reb_overall_df # Non-empty
    mock_reb_endpoint.return_value = mock_reb_instance

    # Simulate _process_dataframe returning None for overall stats
    mock_process_df.side_effect = [None, [], [], [], []]
    expected_error = Errors.TEAM_REBOUNDING_PROCESSING.format(identifier=MOCK_TEAM_ID)

    # Act
    result_str = team_tracking.fetch_team_rebounding_stats_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count > 0 # Called for overall
    assert "error" in result
    assert result["error"] == expected_error

# --- Add tests for fetch_team_passing_stats_logic ---
# --- Add tests for fetch_team_shooting_stats_logic ---
# Mock data for Team Passing Stats
MOCK_TEAM_PASSES_MADE_DATA = [
    {"PASS_FROM": "Player A", "PASS_TO": "Player B", "FREQUENCY": 0.25, "PASS": 50, "AST": 10, "FGM": 8, "FGA": 15, "FG_PCT": 0.533},
    {"PASS_FROM": "Player C", "PASS_TO": "Player A", "FREQUENCY": 0.15, "PASS": 30, "AST": 5, "FGM": 4, "FGA": 8, "FG_PCT": 0.500}
]
MOCK_TEAM_PASSES_RECEIVED_DATA = [
    {"PASS_FROM": "Player B", "PASS_TO": "Player A", "FREQUENCY": 0.20, "PASS": 40, "AST": 2, "FGM": 6, "FGA": 10, "FG_PCT": 0.600},
    {"PASS_FROM": "Player A", "PASS_TO": "Player C", "FREQUENCY": 0.18, "PASS": 35, "AST": 6, "FGM": 5, "FGA": 9, "FG_PCT": 0.556}
]
mock_team_passes_made_df = pd.DataFrame(MOCK_TEAM_PASSES_MADE_DATA)
mock_team_passes_received_df = pd.DataFrame(MOCK_TEAM_PASSES_RECEIVED_DATA)

# --- Tests for fetch_team_passing_stats_logic ---

@patch('backend.api_tools.team_tracking.find_team_id_or_error')
@patch('backend.api_tools.team_tracking.teamdashptpass.TeamDashPtPass')
@patch('backend.api_tools.team_tracking._process_dataframe')
@patch('backend.api_tools.team_tracking._validate_season_format', return_value=True)
def test_fetch_team_passing_stats_success(mock_validate, mock_process_df, mock_pass_endpoint, mock_find_team):
    """Test successful fetching of team passing stats."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)

    mock_pass_instance = MagicMock()
    mock_pass_instance.passes_made.get_data_frame.return_value = mock_team_passes_made_df
    mock_pass_instance.passes_received.get_data_frame.return_value = mock_team_passes_received_df
    mock_pass_endpoint.return_value = mock_pass_instance

    mock_process_df.side_effect = [
        MOCK_TEAM_PASSES_MADE_DATA,     # passes_made
        MOCK_TEAM_PASSES_RECEIVED_DATA  # passes_received
    ]

    # Act
    result_str = team_tracking.fetch_team_passing_stats_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once_with(MOCK_TEAM_IDENTIFIER)
    mock_pass_endpoint.assert_called_once()
    assert mock_process_df.call_count == 2
    assert "error" not in result
    assert result.get("team_id") == MOCK_TEAM_ID
    assert result.get("team_name") == MOCK_TEAM_NAME
    assert "passes_made" in result
    assert "passes_received" in result
    assert result["passes_made"] == MOCK_TEAM_PASSES_MADE_DATA
    assert result["passes_received"] == MOCK_TEAM_PASSES_RECEIVED_DATA

@patch('backend.api_tools.team_tracking.find_team_id_or_error')
def test_fetch_team_passing_stats_team_not_found(mock_find_team):
    """Test team passing stats fetch when team is not found."""
    # Arrange
    identifier = "Unknown Team"
    mock_find_team.side_effect = TeamNotFoundError(identifier)
    expected_error = Errors.TEAM_NOT_FOUND.format(identifier=identifier)

    # Act
    result_str = team_tracking.fetch_team_passing_stats_logic(identifier, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once_with(identifier)
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_team_passing_stats_invalid_season():
    """Test team passing stats fetch with invalid season."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = team_tracking.fetch_team_passing_stats_logic(MOCK_TEAM_IDENTIFIER, season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.team_tracking.find_team_id_or_error')
@patch('backend.api_tools.team_tracking.teamdashptpass.TeamDashPtPass')
@patch('backend.api_tools.team_tracking._validate_season_format', return_value=True)
def test_fetch_team_passing_stats_api_error(mock_validate, mock_pass_endpoint, mock_find_team):
    """Test team passing stats fetch with API error."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)
    api_error_message = "NBA API timeout"
    mock_pass_endpoint.side_effect = Exception(api_error_message)
    expected_error = Errors.TEAM_PASSING_UNEXPECTED.format(identifier=MOCK_TEAM_IDENTIFIER, error=api_error_message)

    # Act
    result_str = team_tracking.fetch_team_passing_stats_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once()
    mock_pass_endpoint.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.team_tracking.find_team_id_or_error')
@patch('backend.api_tools.team_tracking.teamdashptpass.TeamDashPtPass')
@patch('backend.api_tools.team_tracking._process_dataframe')
@patch('backend.api_tools.team_tracking._validate_season_format', return_value=True)
def test_fetch_team_passing_stats_processing_error(mock_validate, mock_process_df, mock_pass_endpoint, mock_find_team):
    """Test team passing stats fetch with processing error."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)
    mock_pass_instance = MagicMock()
    mock_pass_instance.passes_made.get_data_frame.return_value = mock_team_passes_made_df # Non-empty
    mock_pass_instance.passes_received.get_data_frame.return_value = mock_team_passes_received_df
    mock_pass_endpoint.return_value = mock_pass_instance

    mock_process_df.return_value = None # Simulate processing error
    expected_error = Errors.TEAM_PASSING_PROCESSING.format(identifier=MOCK_TEAM_ID)

    # Act
    result_str = team_tracking.fetch_team_passing_stats_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count > 0
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.team_tracking.find_team_id_or_error')
@patch('backend.api_tools.team_tracking.teamdashptpass.TeamDashPtPass')
@patch('backend.api_tools.team_tracking._process_dataframe')
@patch('backend.api_tools.team_tracking._validate_season_format', return_value=True)
def test_fetch_team_passing_stats_empty_df(mock_validate, mock_process_df, mock_pass_endpoint, mock_find_team):
    """Test team passing stats fetch with empty DataFrame response."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)
    mock_pass_instance = MagicMock()
    mock_pass_instance.passes_made.get_data_frame.return_value = pd.DataFrame() # Empty
    mock_pass_instance.passes_received.get_data_frame.return_value = pd.DataFrame() # Empty
    mock_pass_endpoint.return_value = mock_pass_instance

    mock_process_df.side_effect = [[], []] # Processing empty DFs

    # Act
    result_str = team_tracking.fetch_team_passing_stats_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count == 2
    assert "error" not in result
    assert "passes_made" in result
    assert result["passes_made"] == []
    assert "passes_received" in result
    assert result["passes_received"] == []
# Mock data for Team Shooting Stats (TeamDashPtShots)
MOCK_TEAM_SHOTS_GENERAL_DATA = [{"TEAM_ID": MOCK_TEAM_ID, "TEAM_NAME": MOCK_TEAM_NAME, "SHOT_TYPE": "Overall", "FGM": 42.0, "FGA": 88.0, "FG_PCT": 0.477, "EFG_PCT": 0.550}] # Simplified overall
MOCK_TEAM_SHOTS_GENERAL_SPLITS_DATA = [{"TEAM_ID": MOCK_TEAM_ID, "TEAM_NAME": MOCK_TEAM_NAME, "SHOT_TYPE": "Catch and Shoot", "FGM": 15.0, "FGA": 35.0, "FG_PCT": 0.429}] # Example split
MOCK_TEAM_SHOTS_SHOT_CLOCK_DATA = [{"TEAM_ID": MOCK_TEAM_ID, "SHOT_CLOCK_RANGE": "15-7 Sec.", "FGM": 18.0, "FGA": 38.0, "FG_PCT": 0.474}]
MOCK_TEAM_SHOTS_DRIBBLE_DATA = [{"TEAM_ID": MOCK_TEAM_ID, "DRIBBLE_RANGE": "0 Dribbles", "FGM": 20.0, "FGA": 40.0, "FG_PCT": 0.500}]
MOCK_TEAM_SHOTS_TOUCH_TIME_DATA = [{"TEAM_ID": MOCK_TEAM_ID, "TOUCH_TIME_RANGE": "Touch < 2 Seconds", "FGM": 25.0, "FGA": 50.0, "FG_PCT": 0.500}]
MOCK_TEAM_SHOTS_DEFENDER_DIST_DATA = [{"TEAM_ID": MOCK_TEAM_ID, "CLOSE_DEF_DIST_RANGE": "4-6 Feet - Open", "FGM": 22.0, "FGA": 45.0, "FG_PCT": 0.489}]

mock_team_shots_general_df = pd.DataFrame(MOCK_TEAM_SHOTS_GENERAL_DATA + MOCK_TEAM_SHOTS_GENERAL_SPLITS_DATA) # Combine for endpoint mock
mock_team_shots_shot_clock_df = pd.DataFrame(MOCK_TEAM_SHOTS_SHOT_CLOCK_DATA)
mock_team_shots_dribble_df = pd.DataFrame(MOCK_TEAM_SHOTS_DRIBBLE_DATA)
mock_team_shots_touch_time_df = pd.DataFrame(MOCK_TEAM_SHOTS_TOUCH_TIME_DATA)
mock_team_shots_defender_dist_df = pd.DataFrame(MOCK_TEAM_SHOTS_DEFENDER_DIST_DATA)

# --- Tests for fetch_team_shooting_stats_logic ---

@patch('backend.api_tools.team_tracking.find_team_id_or_error')
@patch('backend.api_tools.team_tracking.teamdashptshots.TeamDashPtShots')
@patch('backend.api_tools.team_tracking._process_dataframe')
@patch('backend.api_tools.team_tracking._validate_season_format', return_value=True)
@patch('backend.api_tools.team_tracking.validate_date_format', return_value=True)
def test_fetch_team_shooting_stats_success(mock_validate_date, mock_validate_season, mock_process_df, mock_shots_endpoint, mock_find_team):
    """Test successful fetching of team shooting stats."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)

    mock_shots_instance = MagicMock()
    mock_shots_instance.general_shooting.get_data_frame.return_value = mock_team_shots_general_df
    mock_shots_instance.shot_clock_shooting.get_data_frame.return_value = mock_team_shots_shot_clock_df
    mock_shots_instance.dribble_shooting.get_data_frame.return_value = mock_team_shots_dribble_df
    mock_shots_instance.closest_defender_shooting.get_data_frame.return_value = mock_team_shots_defender_dist_df
    mock_shots_instance.touch_time_shooting.get_data_frame.return_value = mock_team_shots_touch_time_df
    mock_shots_endpoint.return_value = mock_shots_instance

    # Mock _process_dataframe return values
    mock_process_df.side_effect = [
        MOCK_TEAM_SHOTS_GENERAL_DATA[0],        # overall_shooting (single row)
        MOCK_TEAM_SHOTS_GENERAL_SPLITS_DATA,    # general_shooting_splits
        MOCK_TEAM_SHOTS_SHOT_CLOCK_DATA,        # shot_clock
        MOCK_TEAM_SHOTS_DRIBBLE_DATA,           # dribbles
        MOCK_TEAM_SHOTS_DEFENDER_DIST_DATA,     # defender
        MOCK_TEAM_SHOTS_TOUCH_TIME_DATA         # touch_time
    ]

    # Act
    result_str = team_tracking.fetch_team_shooting_stats_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once_with(MOCK_TEAM_IDENTIFIER)
    mock_shots_endpoint.assert_called_once()
    assert mock_process_df.call_count == 6 # overall + 5 splits
    assert "error" not in result
    assert result.get("team_id") == MOCK_TEAM_ID
    assert result.get("team_name") == MOCK_TEAM_NAME
    assert "overall_shooting" in result
    assert "general_shooting_splits" in result
    assert "by_shot_clock" in result
    assert result["overall_shooting"] == MOCK_TEAM_SHOTS_GENERAL_DATA[0]
    assert result["by_shot_clock"] == MOCK_TEAM_SHOTS_SHOT_CLOCK_DATA

@patch('backend.api_tools.team_tracking.find_team_id_or_error')
def test_fetch_team_shooting_stats_team_not_found(mock_find_team):
    """Test team shooting stats fetch when team is not found."""
    # Arrange
    identifier = "Unknown Team"
    mock_find_team.side_effect = TeamNotFoundError(identifier)
    expected_error = Errors.TEAM_NOT_FOUND.format(identifier=identifier)

    # Act
    result_str = team_tracking.fetch_team_shooting_stats_logic(identifier, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once_with(identifier)
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_team_shooting_stats_invalid_season():
    """Test team shooting stats fetch with invalid season."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = team_tracking.fetch_team_shooting_stats_logic(MOCK_TEAM_IDENTIFIER, season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.team_tracking.find_team_id_or_error')
@patch('backend.api_tools.team_tracking.teamdashptshots.TeamDashPtShots')
@patch('backend.api_tools.team_tracking._validate_season_format', return_value=True)
def test_fetch_team_shooting_stats_api_error(mock_validate, mock_shots_endpoint, mock_find_team):
    """Test team shooting stats fetch with API error."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)
    api_error_message = "NBA API timeout"
    mock_shots_endpoint.side_effect = Exception(api_error_message)
    expected_error = Errors.TEAM_SHOOTING_UNEXPECTED.format(identifier=MOCK_TEAM_IDENTIFIER, error=api_error_message)

    # Act
    result_str = team_tracking.fetch_team_shooting_stats_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once()
    mock_shots_endpoint.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.team_tracking.find_team_id_or_error')
@patch('backend.api_tools.team_tracking.teamdashptshots.TeamDashPtShots')
@patch('backend.api_tools.team_tracking._process_dataframe')
@patch('backend.api_tools.team_tracking._validate_season_format', return_value=True)
def test_fetch_team_shooting_stats_processing_error(mock_validate, mock_process_df, mock_shots_endpoint, mock_find_team):
    """Test team shooting stats fetch with processing error."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)
    mock_shots_instance = MagicMock()
    mock_shots_instance.general_shooting.get_data_frame.return_value = mock_team_shots_general_df # Non-empty
    mock_shots_endpoint.return_value = mock_shots_instance

    # Simulate _process_dataframe returning None for overall stats
    mock_process_df.side_effect = [None, [], [], [], [], []]
    expected_error = Errors.TEAM_SHOOTING_PROCESSING.format(identifier=MOCK_TEAM_ID)

    # Act
    result_str = team_tracking.fetch_team_shooting_stats_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count > 0 # Called for overall
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.team_tracking.find_team_id_or_error')
@patch('backend.api_tools.team_tracking.teamdashptshots.TeamDashPtShots')
@patch('backend.api_tools.team_tracking._process_dataframe')
@patch('backend.api_tools.team_tracking._validate_season_format', return_value=True)
def test_fetch_team_shooting_stats_empty_df(mock_validate, mock_process_df, mock_shots_endpoint, mock_find_team):
    """Test team shooting stats fetch with empty DataFrame response."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)
    mock_shots_instance = MagicMock()
    mock_shots_instance.general_shooting.get_data_frame.return_value = pd.DataFrame() # Empty
    # Mock other DFs as empty too
    mock_shots_instance.shot_clock_shooting.get_data_frame.return_value = pd.DataFrame()
    mock_shots_instance.dribble_shooting.get_data_frame.return_value = pd.DataFrame()
    mock_shots_instance.closest_defender_shooting.get_data_frame.return_value = pd.DataFrame()
    mock_shots_instance.touch_time_shooting.get_data_frame.return_value = pd.DataFrame()
    mock_shots_endpoint.return_value = mock_shots_instance

    mock_process_df.side_effect = [{}, [], [], [], [], []] # Processing empty DFs

    # Act
    result_str = team_tracking.fetch_team_shooting_stats_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count == 6
    assert "error" not in result
    assert "overall_shooting" in result
    assert result["overall_shooting"] == {}
    assert "by_shot_clock" in result
    assert result["by_shot_clock"] == []
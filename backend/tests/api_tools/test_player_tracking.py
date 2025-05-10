import pytest
import json
from unittest.mock import patch, MagicMock
import pandas as pd

# Modules to test
from backend.api_tools import player_tracking
from backend.api_tools.utils import PlayerNotFoundError
from backend.config import Errors, CURRENT_SEASON, DEFAULT_TIMEOUT # Added DEFAULT_TIMEOUT
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed

# Mock data - Reuse player info from player_tools tests if possible
MOCK_PLAYER_ID = 2544 # LeBron James example
MOCK_PLAYER_NAME = "LeBron James"
MOCK_TEAM_ID = 1610612747 # LAL
MOCK_SEASON = CURRENT_SEASON
MOCK_COMMON_PLAYER_INFO_DATA = { # Simplified for this test
    "PERSON_ID": MOCK_PLAYER_ID, "DISPLAY_FIRST_LAST": MOCK_PLAYER_NAME, "TEAM_ID": MOCK_TEAM_ID
}
# Note: _process_dataframe(single_row=True) returns a dict, not list[dict]
mock_common_player_info_df = pd.DataFrame([MOCK_COMMON_PLAYER_INFO_DATA]) # Need list for DataFrame constructor

# Mock data for PlayerDashPtReb
MOCK_REB_OVERALL_DATA = {"PLAYER_ID": MOCK_PLAYER_ID, "PLAYER_NAME": MOCK_PLAYER_NAME, "TEAM_ABBREVIATION": "LAL", "GP": 70, "REB": 8.0, "OREB": 1.0, "DREB": 7.0, "C_REB": 2.0, "UC_REB": 6.0, "REB_PCT": 0.12, "C_REB_PCT": 0.25, "UC_REB_PCT": 0.75}
MOCK_REB_SHOT_TYPE_DATA = [{"PLAYER_ID": MOCK_PLAYER_ID, "SHOT_TYPE": "2PT", "REB": 6.0}, {"PLAYER_ID": MOCK_PLAYER_ID, "SHOT_TYPE": "3PT", "REB": 2.0}]
MOCK_REB_CONTESTED_DATA = [{"PLAYER_ID": MOCK_PLAYER_ID, "CONTEST_TYPE": "Contested", "REB": 2.0}, {"PLAYER_ID": MOCK_PLAYER_ID, "CONTEST_TYPE": "Uncontested", "REB": 6.0}]
MOCK_REB_SHOT_DIST_DATA = [{"PLAYER_ID": MOCK_PLAYER_ID, "SHOT_DISTANCE_RANGE": "0-5 ft", "REB": 5.0}]
MOCK_REB_REB_DIST_DATA = [{"PLAYER_ID": MOCK_PLAYER_ID, "REB_DISTANCE_RANGE": "0-3 ft", "REB": 4.0}]

mock_reb_overall_df = pd.DataFrame([MOCK_REB_OVERALL_DATA]) # Need list for DataFrame constructor
mock_reb_shot_type_df = pd.DataFrame(MOCK_REB_SHOT_TYPE_DATA)
mock_reb_contested_df = pd.DataFrame(MOCK_REB_CONTESTED_DATA)
mock_reb_shot_dist_df = pd.DataFrame(MOCK_REB_SHOT_DIST_DATA)
mock_reb_reb_dist_df = pd.DataFrame(MOCK_REB_REB_DIST_DATA)

# Mock data for Player Passing Stats
MOCK_PLAYER_PASSES_MADE_DATA = [
    {"PASS_TO": "Anthony Davis", "FREQUENCY": 0.3, "PASS": 20, "AST": 5, "FGM": 8, "FGA": 12, "FG_PCT": 0.667},
    {"PASS_TO": "Austin Reaves", "FREQUENCY": 0.2, "PASS": 15, "AST": 4, "FGM": 5, "FGA": 10, "FG_PCT": 0.500}
]
MOCK_PLAYER_PASSES_RECEIVED_DATA = [
    {"PASS_FROM": "D'Angelo Russell", "FREQUENCY": 0.25, "PASS": 18, "AST": 2, "FGM": 6, "FGA": 10, "FG_PCT": 0.600},
    {"PASS_FROM": "Austin Reaves", "FREQUENCY": 0.15, "PASS": 12, "AST": 1, "FGM": 4, "FGA": 8, "FG_PCT": 0.500}
]
mock_player_passes_made_df = pd.DataFrame(MOCK_PLAYER_PASSES_MADE_DATA)
mock_player_passes_received_df = pd.DataFrame(MOCK_PLAYER_PASSES_RECEIVED_DATA)

# Mock data for Player Shooting Stats (PlayerDashPtShots)
MOCK_SHOTS_GENERAL_DATA = {"PLAYER_ID": MOCK_PLAYER_ID, "PLAYER_NAME": MOCK_PLAYER_NAME, "SHOT_TYPE": "Overall", "FGM": 10.0, "FGA": 20.0, "FG_PCT": 0.500, "EFG_PCT": 0.550, "FG2_PCT": 0.520, "FG3_PCT": 0.400} # Simplified overall
MOCK_SHOTS_GENERAL_SPLITS_DATA = [{"PLAYER_ID": MOCK_PLAYER_ID, "PLAYER_NAME": MOCK_PLAYER_NAME, "SHOT_TYPE": "Catch and Shoot", "FGM": 5.0, "FGA": 10.0, "FG_PCT": 0.500}] # Example split
MOCK_SHOTS_SHOT_CLOCK_DATA = [{"PLAYER_ID": MOCK_PLAYER_ID, "SHOT_CLOCK_RANGE": "15-7 Sec.", "FGM": 4.0, "FGA": 8.0, "FG_PCT": 0.500}]
MOCK_SHOTS_DRIBBLE_DATA = [{"PLAYER_ID": MOCK_PLAYER_ID, "DRIBBLE_RANGE": "0 Dribbles", "FGM": 3.0, "FGA": 5.0, "FG_PCT": 0.600}]
MOCK_SHOTS_TOUCH_TIME_DATA = [{"PLAYER_ID": MOCK_PLAYER_ID, "TOUCH_TIME_RANGE": "Touch < 2 Seconds", "FGM": 6.0, "FGA": 10.0, "FG_PCT": 0.600}]
MOCK_SHOTS_DEFENDER_DIST_DATA = [{"PLAYER_ID": MOCK_PLAYER_ID, "CLOSE_DEF_DIST_RANGE": "4-6 Feet - Open", "FGM": 5.0, "FGA": 9.0, "FG_PCT": 0.556}]
MOCK_SHOTS_DEFENDER_DIST_10FT_DATA = [{"PLAYER_ID": MOCK_PLAYER_ID, "CLOSE_DEF_DIST_RANGE": "10+ Feet - Wide Open", "FGM": 2.0, "FGA": 3.0, "FG_PCT": 0.667}] # Example

mock_shots_general_df = pd.DataFrame([MOCK_SHOTS_GENERAL_DATA] + MOCK_SHOTS_GENERAL_SPLITS_DATA) # Combine for endpoint mock
mock_shots_shot_clock_df = pd.DataFrame(MOCK_SHOTS_SHOT_CLOCK_DATA)
mock_shots_dribble_df = pd.DataFrame(MOCK_SHOTS_DRIBBLE_DATA)
mock_shots_touch_time_df = pd.DataFrame(MOCK_SHOTS_TOUCH_TIME_DATA)
mock_shots_defender_dist_df = pd.DataFrame(MOCK_SHOTS_DEFENDER_DIST_DATA)
mock_shots_defender_dist_10ft_df = pd.DataFrame(MOCK_SHOTS_DEFENDER_DIST_10FT_DATA)

# Mock data for Player Clutch Stats
MOCK_PLAYER_CLUTCH_DATA = { # Example structure, adjust based on actual API response
    "resultSets": [ # Simulate the structure returned by get_dict()
        {
            "name": "OverallPlayerDashboard", # Example dataset name
            "headers": ["GROUP_SET", "PLAYER_ID", "PLAYER_NAME", "GP", "W", "L", "W_PCT", "MIN", "PTS", "FGM", "FGA", "FG_PCT"],
            "rowSet": [
                ["Overall", MOCK_PLAYER_ID, MOCK_PLAYER_NAME, 20, 15, 5, 0.750, 5.0, 8.0, 3.0, 5.0, 0.600]
            ]
        },
        {
            "name": "Last5Min5PointPlayerDashboard", # Assuming this is the target dataset
            "headers": ["GROUP_SET", "PLAYER_ID", "PLAYER_NAME", "GP", "W", "L", "W_PCT", "MIN", "PTS", "FGM", "FGA", "FG_PCT"],
            "rowSet": [
                ["Last 5 Minutes, 5 Point Differential", MOCK_PLAYER_ID, MOCK_PLAYER_NAME, 10, 7, 3, 0.700, 4.5, 6.0, 2.0, 4.0, 0.500]
            ]
        }
    ]
}
# Expected processed data for the target dataset
MOCK_PROCESSED_CLUTCH_DATA = [{"GROUP_SET": "Last 5 Minutes, 5 Point Differential", "PLAYER_ID": MOCK_PLAYER_ID, "PLAYER_NAME": MOCK_PLAYER_NAME, "GP": 10, "W": 7, "L": 3, "W_PCT": 0.700, "MIN": 4.5, "PTS": 6.0, "FGM": 2.0, "FGA": 4.0, "FG_PCT": 0.500}]


# --- Tests for fetch_player_rebounding_stats_logic ---

@patch('backend.api_tools.player_tracking.find_player_id_or_error')
@patch('backend.api_tools.player_tracking.commonplayerinfo.CommonPlayerInfo')
@patch('backend.api_tools.player_tracking.playerdashptreb.PlayerDashPtReb')
@patch('backend.api_tools.player_tracking._process_dataframe')
@patch('backend.api_tools.player_tracking._validate_season_format', return_value=True)
def test_fetch_player_rebounding_stats_success(mock_validate, mock_process_df, mock_reb_endpoint, mock_info_endpoint, mock_find_player):
    """Test successful fetching of player rebounding stats."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)

    # Mock commonplayerinfo for team_id lookup
    mock_info_instance = MagicMock()
    mock_info_instance.common_player_info.get_data_frame.return_value = mock_common_player_info_df
    mock_info_endpoint.return_value = mock_info_instance

    # Mock playerdashptreb endpoint
    mock_reb_instance = MagicMock()
    mock_reb_instance.overall_rebounding.get_data_frame.return_value = mock_reb_overall_df
    mock_reb_instance.shot_type_rebounding.get_data_frame.return_value = mock_reb_shot_type_df
    mock_reb_instance.num_contested_rebounding.get_data_frame.return_value = mock_reb_contested_df
    mock_reb_instance.shot_distance_rebounding.get_data_frame.return_value = mock_reb_shot_dist_df
    mock_reb_instance.reb_distance_rebounding.get_data_frame.return_value = mock_reb_reb_dist_df
    mock_reb_endpoint.return_value = mock_reb_instance

    # Mock _process_dataframe return values
    mock_process_df.side_effect = [
        MOCK_COMMON_PLAYER_INFO_DATA,    # For info_dict (Corrected: return dict)
        MOCK_REB_OVERALL_DATA,           # overall (Corrected: return dict)
        MOCK_REB_SHOT_TYPE_DATA,         # shot_type
        MOCK_REB_CONTESTED_DATA,         # contested
        MOCK_REB_SHOT_DIST_DATA,         # distances
        MOCK_REB_REB_DIST_DATA           # reb_dist
    ]

    # Act
    result_str = player_tracking.fetch_player_rebounding_stats_logic(MOCK_PLAYER_NAME, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_info_endpoint.assert_called_once_with(player_id=MOCK_PLAYER_ID, timeout=DEFAULT_TIMEOUT)
    mock_reb_endpoint.assert_called_once()
    assert mock_process_df.call_count == 6 # info + 5 reb DFs
    assert "error" not in result
    assert result.get("player_id") == MOCK_PLAYER_ID
    assert result.get("player_name") == MOCK_PLAYER_NAME
    assert "overall" in result
    assert "by_shot_type" in result
    assert result["overall"] == MOCK_REB_OVERALL_DATA # Corrected: Compare dict
    assert result["by_shot_type"] == MOCK_REB_SHOT_TYPE_DATA

@patch('backend.api_tools.player_tracking.find_player_id_or_error')
def test_fetch_player_rebounding_stats_player_not_found(mock_find_player):
    """Test player rebounding fetch when player is not found."""
    # Arrange
    identifier = "Unknown Player"
    mock_find_player.side_effect = PlayerNotFoundError(identifier)
    expected_error = Errors.PLAYER_NOT_FOUND.format(name=identifier)

    # Act
    result_str = player_tracking.fetch_player_rebounding_stats_logic(identifier, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(identifier)
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_player_rebounding_stats_invalid_season():
    """Test player rebounding fetch with invalid season."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = player_tracking.fetch_player_rebounding_stats_logic(MOCK_PLAYER_NAME, season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tracking.find_player_id_or_error')
@patch('backend.api_tools.player_tracking.commonplayerinfo.CommonPlayerInfo')
@patch('backend.api_tools.player_tracking.playerdashptreb.PlayerDashPtReb')
@patch('backend.api_tools.player_tracking._validate_season_format', return_value=True)
def test_fetch_player_rebounding_stats_api_error(mock_validate, mock_reb_endpoint, mock_info_endpoint, mock_find_player):
    """Test player rebounding fetch with API error."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    # Mock commonplayerinfo success
    mock_info_instance = MagicMock()
    mock_info_instance.common_player_info.get_data_frame.return_value = mock_common_player_info_df
    mock_info_endpoint.return_value = mock_info_instance
    # Mock playerdashptreb failure
    api_error_message = "NBA API timeout"
    mock_reb_endpoint.side_effect = Exception(api_error_message)
    expected_error = Errors.PLAYER_REBOUNDING_UNEXPECTED.format(name=MOCK_PLAYER_NAME, error=api_error_message)

    # Act
    result_str = player_tracking.fetch_player_rebounding_stats_logic(MOCK_PLAYER_NAME, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once()
    mock_info_endpoint.assert_called_once()
    mock_reb_endpoint.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tracking.find_player_id_or_error')
@patch('backend.api_tools.player_tracking.commonplayerinfo.CommonPlayerInfo')
@patch('backend.api_tools.player_tracking.playerdashptreb.PlayerDashPtReb')
@patch('backend.api_tools.player_tracking._process_dataframe')
@patch('backend.api_tools.player_tracking._validate_season_format', return_value=True)
def test_fetch_player_rebounding_stats_processing_error(mock_validate, mock_process_df, mock_reb_endpoint, mock_info_endpoint, mock_find_player):
    """Test player rebounding fetch with processing error."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    mock_info_instance = MagicMock()
    mock_info_instance.common_player_info.get_data_frame.return_value = mock_common_player_info_df
    mock_info_endpoint.return_value = mock_info_instance
    mock_reb_instance = MagicMock()
    mock_reb_instance.overall_rebounding.get_data_frame.return_value = mock_reb_overall_df # Non-empty DF
    mock_reb_endpoint.return_value = mock_reb_instance

    # Simulate _process_dataframe returning None for overall stats
    mock_process_df.side_effect = [MOCK_COMMON_PLAYER_INFO_DATA, None, [], [], [], []] # Corrected info mock
    expected_error = Errors.PLAYER_REBOUNDING_PROCESSING.format(name=MOCK_PLAYER_NAME)

    # Act
    result_str = player_tracking.fetch_player_rebounding_stats_logic(MOCK_PLAYER_NAME, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count > 1 # Called for info and overall
    assert "error" in result
    assert result["error"] == expected_error

# --- Tests for fetch_player_passing_stats_logic ---

@patch('backend.api_tools.player_tracking.find_player_id_or_error')
@patch('backend.api_tools.player_tracking.commonplayerinfo.CommonPlayerInfo')
@patch('backend.api_tools.player_tracking.playerdashptpass.PlayerDashPtPass')
@patch('backend.api_tools.player_tracking._process_dataframe')
@patch('backend.api_tools.player_tracking._validate_season_format', return_value=True)
def test_fetch_player_passing_stats_success(mock_validate, mock_process_df, mock_pass_endpoint, mock_info_endpoint, mock_find_player):
    """Test successful fetching of player passing stats."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    mock_info_instance = MagicMock()
    mock_info_instance.common_player_info.get_data_frame.return_value = mock_common_player_info_df
    mock_info_endpoint.return_value = mock_info_instance

    mock_pass_instance = MagicMock()
    mock_pass_instance.passes_made.get_data_frame.return_value = mock_player_passes_made_df
    mock_pass_instance.passes_received.get_data_frame.return_value = mock_player_passes_received_df
    mock_pass_endpoint.return_value = mock_pass_instance

    mock_process_df.side_effect = [
        MOCK_COMMON_PLAYER_INFO_DATA,    # info_dict (Corrected: return dict)
        MOCK_PLAYER_PASSES_MADE_DATA,    # made
        MOCK_PLAYER_PASSES_RECEIVED_DATA # received
    ]

    # Act
    result_str = player_tracking.fetch_player_passing_stats_logic(MOCK_PLAYER_NAME, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_info_endpoint.assert_called_once()
    mock_pass_endpoint.assert_called_once()
    assert mock_process_df.call_count == 3 # info + made + received
    assert "error" not in result
    assert result.get("player_id") == MOCK_PLAYER_ID
    assert result.get("player_name") == MOCK_PLAYER_NAME
    assert "passes_made" in result
    assert "passes_received" in result
    assert result["passes_made"] == MOCK_PLAYER_PASSES_MADE_DATA
    assert result["passes_received"] == MOCK_PLAYER_PASSES_RECEIVED_DATA

@patch('backend.api_tools.player_tracking.find_player_id_or_error')
def test_fetch_player_passing_stats_player_not_found(mock_find_player):
    """Test player passing fetch when player is not found."""
    # Arrange
    identifier = "Unknown Player"
    mock_find_player.side_effect = PlayerNotFoundError(identifier)
    expected_error = Errors.PLAYER_NOT_FOUND.format(name=identifier)

    # Act
    result_str = player_tracking.fetch_player_passing_stats_logic(identifier, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(identifier)
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_player_passing_stats_invalid_season():
    """Test player passing fetch with invalid season."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = player_tracking.fetch_player_passing_stats_logic(MOCK_PLAYER_NAME, season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tracking.find_player_id_or_error')
@patch('backend.api_tools.player_tracking.commonplayerinfo.CommonPlayerInfo')
@patch('backend.api_tools.player_tracking.playerdashptpass.PlayerDashPtPass')
@patch('backend.api_tools.player_tracking._validate_season_format', return_value=True)
def test_fetch_player_passing_stats_api_error(mock_validate, mock_pass_endpoint, mock_info_endpoint, mock_find_player):
    """Test player passing fetch with API error."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    mock_info_instance = MagicMock()
    mock_info_instance.common_player_info.get_data_frame.return_value = mock_common_player_info_df
    mock_info_endpoint.return_value = mock_info_instance

    api_error_message = "NBA API timeout"
    mock_pass_endpoint.side_effect = Exception(api_error_message)
    expected_error = Errors.PLAYER_PASSING_UNEXPECTED.format(name=MOCK_PLAYER_NAME, error=api_error_message)

    # Act
    result_str = player_tracking.fetch_player_passing_stats_logic(MOCK_PLAYER_NAME, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once()
    mock_info_endpoint.assert_called_once()
    mock_pass_endpoint.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tracking.find_player_id_or_error')
@patch('backend.api_tools.player_tracking.commonplayerinfo.CommonPlayerInfo')
@patch('backend.api_tools.player_tracking.playerdashptpass.PlayerDashPtPass')
@patch('backend.api_tools.player_tracking._process_dataframe')
@patch('backend.api_tools.player_tracking._validate_season_format', return_value=True)
def test_fetch_player_passing_stats_processing_error(mock_validate, mock_process_df, mock_pass_endpoint, mock_info_endpoint, mock_find_player):
    """Test player passing fetch with processing error."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    mock_info_instance = MagicMock()
    mock_info_instance.common_player_info.get_data_frame.return_value = mock_common_player_info_df
    mock_info_endpoint.return_value = mock_info_instance

    mock_pass_instance = MagicMock()
    mock_pass_instance.passes_made.get_data_frame.return_value = mock_player_passes_made_df
    mock_pass_instance.passes_received.get_data_frame.return_value = mock_player_passes_received_df
    mock_pass_endpoint.return_value = mock_pass_instance

    # Simulate _process_dataframe returning None for passes_made
    mock_process_df.side_effect = [MOCK_COMMON_PLAYER_INFO_DATA, None, MOCK_PLAYER_PASSES_RECEIVED_DATA] # Corrected info mock
    expected_error = Errors.PLAYER_PASSING_PROCESSING.format(name=MOCK_PLAYER_NAME)

    # Act
    result_str = player_tracking.fetch_player_passing_stats_logic(MOCK_PLAYER_NAME, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count > 1 # Called for info and passes_made
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tracking.find_player_id_or_error')
@patch('backend.api_tools.player_tracking.commonplayerinfo.CommonPlayerInfo')
@patch('backend.api_tools.player_tracking.playerdashptpass.PlayerDashPtPass')
@patch('backend.api_tools.player_tracking._process_dataframe')
@patch('backend.api_tools.player_tracking._validate_season_format', return_value=True)
def test_fetch_player_passing_stats_empty_df(mock_validate, mock_process_df, mock_pass_endpoint, mock_info_endpoint, mock_find_player):
    """Test player passing fetch with empty DataFrame response."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    mock_info_instance = MagicMock()
    mock_info_instance.common_player_info.get_data_frame.return_value = mock_common_player_info_df
    mock_info_endpoint.return_value = mock_info_instance

    mock_pass_instance = MagicMock()
    mock_pass_instance.passes_made.get_data_frame.return_value = pd.DataFrame() # Empty DF
    mock_pass_instance.passes_received.get_data_frame.return_value = pd.DataFrame() # Empty DF
    mock_pass_endpoint.return_value = mock_pass_instance

    mock_process_df.side_effect = [MOCK_COMMON_PLAYER_INFO_DATA, [], []] # Corrected info mock, Processing empty DFs

    # Act
    result_str = player_tracking.fetch_player_passing_stats_logic(MOCK_PLAYER_NAME, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count == 3
    assert "error" not in result
    assert "passes_made" in result
    assert result["passes_made"] == []
    assert "passes_received" in result
    assert result["passes_received"] == []

# --- Tests for fetch_player_shots_tracking_logic ---

@patch('backend.api_tools.player_tracking.commonplayerinfo.CommonPlayerInfo')
@patch('backend.api_tools.player_tracking.playerdashptshots.PlayerDashPtShots')
@patch('backend.api_tools.player_tracking._process_dataframe')
@patch('backend.api_tools.player_tracking._validate_season_format', return_value=True)
@patch('backend.api_tools.player_tracking.validate_date_format', return_value=True)
def test_fetch_player_shots_tracking_success(mock_validate_date, mock_validate_season, mock_process_df, mock_shots_endpoint, mock_info_endpoint):
    """Test successful fetching of player shots tracking stats."""
    # Arrange
    # Mock commonplayerinfo for team_id lookup
    mock_info_instance = MagicMock()
    mock_info_instance.common_player_info.get_data_frame.return_value = mock_common_player_info_df
    mock_info_endpoint.return_value = mock_info_instance

    # Mock playerdashptshots endpoint
    mock_shots_instance = MagicMock()
    mock_shots_instance.general_shooting.get_data_frame.return_value = mock_shots_general_df
    mock_shots_instance.shot_clock_shooting.get_data_frame.return_value = mock_shots_shot_clock_df
    mock_shots_instance.dribble_shooting.get_data_frame.return_value = mock_shots_dribble_df
    mock_shots_instance.closest_defender_shooting.get_data_frame.return_value = mock_shots_defender_dist_df
    mock_shots_instance.closest_defender10ft_plus_shooting.get_data_frame.return_value = mock_shots_defender_dist_10ft_df
    mock_shots_instance.touch_time_shooting.get_data_frame.return_value = mock_shots_touch_time_df
    mock_shots_endpoint.return_value = mock_shots_instance

    # Mock _process_dataframe return values
    # Corrected: general should be a list containing the overall dict and the splits list
    mock_process_df.side_effect = [
        MOCK_COMMON_PLAYER_INFO_DATA,           # info_dict (Corrected: return dict)
        [MOCK_SHOTS_GENERAL_DATA] + MOCK_SHOTS_GENERAL_SPLITS_DATA, # general (list)
        MOCK_SHOTS_SHOT_CLOCK_DATA,             # shot_clock
        MOCK_SHOTS_DRIBBLE_DATA,                # dribbles
        MOCK_SHOTS_TOUCH_TIME_DATA,             # touch_time
        MOCK_SHOTS_DEFENDER_DIST_DATA,          # defender_dist
        MOCK_SHOTS_DEFENDER_DIST_10FT_DATA      # defender_dist_10ft
    ]

    # Act
    result_str = player_tracking.fetch_player_shots_tracking_logic(str(MOCK_PLAYER_ID), season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_info_endpoint.assert_called_once_with(player_id=MOCK_PLAYER_ID, timeout=DEFAULT_TIMEOUT)
    mock_shots_endpoint.assert_called_once()
    # Expect 1 call for info + 6 for shot DFs
    assert mock_process_df.call_count == 7
    assert "error" not in result
    assert result.get("player_id") == MOCK_PLAYER_ID
    assert result.get("player_name") == MOCK_PLAYER_NAME
    assert "general_shooting" in result
    assert "by_shot_clock" in result
    assert "by_dribble_count" in result
    assert "by_touch_time" in result
    assert "by_defender_distance" in result
    assert "by_defender_distance_10ft_plus" in result
    # Check one of the processed lists
    assert result["by_shot_clock"] == MOCK_SHOTS_SHOT_CLOCK_DATA
    # Check the general shooting list structure
    assert result["general_shooting"] == [MOCK_SHOTS_GENERAL_DATA] + MOCK_SHOTS_GENERAL_SPLITS_DATA

def test_fetch_player_shots_tracking_empty_player_id():
    """Test player shots tracking fetch with empty player ID."""
    # Arrange
    expected_error = Errors.PLAYER_ID_EMPTY

    # Act
    result_str = player_tracking.fetch_player_shots_tracking_logic("", season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_player_shots_tracking_invalid_player_id():
    """Test player shots tracking fetch with invalid player ID format."""
    # Arrange
    invalid_id = "abc"
    expected_error = Errors.INVALID_PLAYER_ID_FORMAT.format(player_id=invalid_id)

    # Act
    result_str = player_tracking.fetch_player_shots_tracking_logic(invalid_id, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_player_shots_tracking_invalid_season():
    """Test player shots tracking fetch with invalid season."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = player_tracking.fetch_player_shots_tracking_logic(str(MOCK_PLAYER_ID), season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tracking.commonplayerinfo.CommonPlayerInfo')
@patch('backend.api_tools.player_tracking.playerdashptshots.PlayerDashPtShots')
@patch('backend.api_tools.player_tracking._validate_season_format', return_value=True)
def test_fetch_player_shots_tracking_api_error(mock_validate, mock_shots_endpoint, mock_info_endpoint):
    """Test player shots tracking fetch with API error."""
    # Arrange
    # Mock commonplayerinfo success
    mock_info_instance = MagicMock()
    mock_info_instance.common_player_info.get_data_frame.return_value = mock_common_player_info_df
    mock_info_endpoint.return_value = mock_info_instance
    # Mock playerdashptshots failure
    api_error_message = "NBA API timeout"
    mock_shots_endpoint.side_effect = Exception(api_error_message)
    expected_error = Errors.PLAYER_SHOTS_TRACKING_UNEXPECTED.format(player_id=MOCK_PLAYER_ID, error=api_error_message)

    # Act
    result_str = player_tracking.fetch_player_shots_tracking_logic(str(MOCK_PLAYER_ID), season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_info_endpoint.assert_called_once()
    mock_shots_endpoint.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tracking.commonplayerinfo.CommonPlayerInfo')
@patch('backend.api_tools.player_tracking.playerdashptshots.PlayerDashPtShots')
@patch('backend.api_tools.player_tracking._process_dataframe')
@patch('backend.api_tools.player_tracking._validate_season_format', return_value=True)
def test_fetch_player_shots_tracking_processing_error(mock_validate, mock_process_df, mock_shots_endpoint, mock_info_endpoint):
    """Test player shots tracking fetch with processing error."""
    # Arrange
    mock_info_instance = MagicMock()
    mock_info_instance.common_player_info.get_data_frame.return_value = mock_common_player_info_df
    mock_info_endpoint.return_value = mock_info_instance

    mock_shots_instance = MagicMock()
    mock_shots_instance.general_shooting.get_data_frame.return_value = mock_shots_general_df # Non-empty
    mock_shots_endpoint.return_value = mock_shots_instance

    # Simulate _process_dataframe returning None for general stats
    mock_process_df.side_effect = [MOCK_COMMON_PLAYER_INFO_DATA, None, [], [], [], [], []] # Corrected info mock
    expected_error = Errors.PLAYER_SHOTS_TRACKING_PROCESSING.format(player_id=MOCK_PLAYER_ID)

    # Act
    result_str = player_tracking.fetch_player_shots_tracking_logic(str(MOCK_PLAYER_ID), season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count > 1 # Called for info and general
    assert "error" in result
    assert result["error"] == expected_error

# --- Tests for fetch_player_clutch_stats_logic ---

@patch('backend.api_tools.player_tracking.find_player_id_or_error')
@patch('backend.api_tools.player_tracking.playerdashboardbyclutch.PlayerDashboardByClutch')
@patch('backend.api_tools.player_tracking._process_dataframe') # Need to mock this as it's used in the refactored version
@patch('backend.api_tools.player_tracking._validate_season_format', return_value=True)
def test_fetch_player_clutch_stats_success(mock_validate, mock_process_df, mock_clutch_endpoint, mock_find_player):
    """Test successful fetching of player clutch stats."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)

    mock_endpoint_instance = MagicMock()
    # Simulate get_data_frames() returning a list containing the target DataFrame
    mock_clutch_df = pd.DataFrame(MOCK_PROCESSED_CLUTCH_DATA) # Use processed data for simplicity
    mock_endpoint_instance.get_data_frames.return_value = [mock_clutch_df]
    mock_clutch_endpoint.return_value = mock_endpoint_instance

    # Mock _process_dataframe to return the list of dicts
    mock_process_df.return_value = MOCK_PROCESSED_CLUTCH_DATA

    # Expected result structure after adding player info
    expected_result_data = {
        "player_name": MOCK_PLAYER_NAME,
        "player_id": MOCK_PLAYER_ID,
        "parameters": { # Check default parameters are included
             "season": MOCK_SEASON, "season_type": SeasonTypeAllStar.regular, "measure_type": "Base",
             "per_mode": "Totals", "plus_minus": "N", "pace_adjust": "N",
             "rank": "N", "shot_clock_range": None, "game_segment": None,
             "period": 0, "last_n_games": 0, "month": 0,
             "opponent_team_id": 0, "location": None, "outcome": None,
             "vs_conference": None, "vs_division": None,
             "season_segment": None, "date_from": None, "date_to": None
        },
        "clutch_stats": MOCK_PROCESSED_CLUTCH_DATA
    }


    # Act
    result_str = player_tracking.fetch_player_clutch_stats_logic(MOCK_PLAYER_NAME, season=MOCK_SEASON)
    result = json.loads(result_str) # The function returns JSON string

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_clutch_endpoint.assert_called_once()
    mock_process_df.assert_called_once() # Called once on the first DataFrame
    assert "error" not in result
    # Compare the structured data
    assert result == expected_result_data


@patch('backend.api_tools.player_tracking.find_player_id_or_error')
def test_fetch_player_clutch_stats_player_not_found(mock_find_player):
    """Test player clutch fetch when player is not found."""
    # Arrange
    identifier = "Unknown Player"
    mock_find_player.side_effect = PlayerNotFoundError(identifier)
    expected_error = Errors.PLAYER_NOT_FOUND.format(name=identifier)

    # Act
    result_str = player_tracking.fetch_player_clutch_stats_logic(identifier, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(identifier)
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_player_clutch_stats_invalid_season():
    """Test player clutch fetch with invalid season."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = player_tracking.fetch_player_clutch_stats_logic(MOCK_PLAYER_NAME, season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tracking.find_player_id_or_error')
@patch('backend.api_tools.player_tracking.playerdashboardbyclutch.PlayerDashboardByClutch')
@patch('backend.api_tools.player_tracking._validate_season_format', return_value=True)
def test_fetch_player_clutch_stats_api_error(mock_validate, mock_clutch_endpoint, mock_find_player):
    """Test player clutch fetch with API error."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    api_error_message = "NBA API timeout"
    mock_clutch_endpoint.side_effect = Exception(api_error_message)
    expected_error = Errors.PLAYER_CLUTCH_STATS_UNEXPECTED.format(name=MOCK_PLAYER_NAME, season=MOCK_SEASON, error=api_error_message)

    # Act
    result_str = player_tracking.fetch_player_clutch_stats_logic(MOCK_PLAYER_NAME, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once()
    mock_clutch_endpoint.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tracking.find_player_id_or_error')
@patch('backend.api_tools.player_tracking.playerdashboardbyclutch.PlayerDashboardByClutch')
@patch('backend.api_tools.player_tracking._process_dataframe')
@patch('backend.api_tools.player_tracking._validate_season_format', return_value=True)
def test_fetch_player_clutch_stats_processing_error(mock_validate, mock_process_df, mock_clutch_endpoint, mock_find_player):
    """Test player clutch fetch with processing error."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    mock_endpoint_instance = MagicMock()
    mock_clutch_df = pd.DataFrame(MOCK_PROCESSED_CLUTCH_DATA)
    mock_endpoint_instance.get_data_frames.return_value = [mock_clutch_df] # Non-empty DF
    mock_clutch_endpoint.return_value = mock_endpoint_instance

    mock_process_df.return_value = None # Simulate processing error
    expected_error = Errors.PLAYER_CLUTCH_PROCESSING.format(name=MOCK_PLAYER_NAME)

    # Act
    result_str = player_tracking.fetch_player_clutch_stats_logic(MOCK_PLAYER_NAME, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once()
    mock_clutch_endpoint.assert_called_once()
    mock_process_df.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error


@patch('backend.api_tools.player_tracking.find_player_id_or_error')
@patch('backend.api_tools.player_tracking.playerdashboardbyclutch.PlayerDashboardByClutch')
@patch('backend.api_tools.player_tracking._process_dataframe')
@patch('backend.api_tools.player_tracking._validate_season_format', return_value=True)
def test_fetch_player_clutch_stats_no_data(mock_validate, mock_process_df, mock_clutch_endpoint, mock_find_player):
    """Test player clutch fetch when no relevant data is found in the response."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    mock_endpoint_instance = MagicMock()
    # Simulate response with empty dataframe
    mock_endpoint_instance.get_data_frames.return_value = [pd.DataFrame()]
    mock_clutch_endpoint.return_value = mock_endpoint_instance

    mock_process_df.return_value = [] # Processing empty returns empty list

    # Act
    result_str = player_tracking.fetch_player_clutch_stats_logic(MOCK_PLAYER_NAME, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert "error" not in result
    # Check that the main data payload is empty list
    assert result.get("clutch_stats") == []
    assert result.get("player_name") == MOCK_PLAYER_NAME # Should still include identifiers
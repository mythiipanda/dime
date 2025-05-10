import pytest
import json
from unittest.mock import patch, MagicMock
import pandas as pd

# Modules to test
from backend.api_tools import team_tools
from backend.api_tools.utils import TeamNotFoundError # Import custom exception
from backend.config import Errors, CURRENT_SEASON, DEFAULT_TIMEOUT # Added DEFAULT_TIMEOUT
from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID, PerModeDetailed # Added PerModeDetailed

# Mock data
MOCK_TEAM_ID = 1610612738 # Boston Celtics example
MOCK_TEAM_NAME = "Boston Celtics"
MOCK_TEAM_IDENTIFIER = "Celtics" # Example identifier
MOCK_SEASON = CURRENT_SEASON

MOCK_TEAM_INFO_COMMON_DATA = { # Data for a single row
    "TEAM_ID": MOCK_TEAM_ID, "SEASON_YEAR": MOCK_SEASON, "TEAM_CITY": "Boston",
    "TEAM_NAME": "Celtics", "TEAM_ABBREVIATION": "BOS", "TEAM_CONFERENCE": "East",
    "TEAM_DIVISION": "Atlantic", "W": 50, "L": 20, "PCT": 0.714, "CONF_RANK": 1, "DIV_RANK": 1
}
MOCK_TEAM_SEASON_RANKS_DATA = { # Data for a single row
    "TEAM_ID": MOCK_TEAM_ID, "SEASON_ID": f"{MOCK_SEASON[:4]}-{MOCK_SEASON[-2:]}", "PTS_RANK": 1, "REB_RANK": 5, "AST_RANK": 3, "STL_RANK": 10, "BLK_RANK": 2
}
MOCK_TEAM_ROSTER_DATA = [
    {"TeamID": MOCK_TEAM_ID, "SEASON": MOCK_SEASON, "LeagueID": "00", "PLAYER": "Jayson Tatum", "PLAYER_ID": 1628369, "NUM": "0", "POSITION": "F", "HEIGHT": "6-8", "WEIGHT": "210", "AGE": 26.0, "EXP": "7", "SCHOOL": "Duke", "BIRTH_DATE": "MAR 03, 1998"},
    {"TeamID": MOCK_TEAM_ID, "SEASON": MOCK_SEASON, "LeagueID": "00", "PLAYER": "Jaylen Brown", "PLAYER_ID": 1627759, "NUM": "7", "POSITION": "G-F", "HEIGHT": "6-6", "WEIGHT": "223", "AGE": 27.0, "EXP": "8", "SCHOOL": "California", "BIRTH_DATE": "OCT 24, 1996"}
]
MOCK_TEAM_COACHES_DATA = [
    {"TEAM_ID": MOCK_TEAM_ID, "SEASON": MOCK_SEASON, "COACH_ID": "MAZ273465", "FIRST_NAME": "Joe", "LAST_NAME": "Mazzulla", "COACH_NAME": "Joe Mazzulla", "COACH_CODE": "joe_mazzulla", "IS_ASSISTANT": 1.0, "COACH_TYPE": "Head Coach", "SCHOOL": "College - West Virginia", "SORT_SEQUENCE": 0.0}
]

# Need list for DataFrame constructor even for single row data
mock_team_info_df = pd.DataFrame([MOCK_TEAM_INFO_COMMON_DATA])
mock_team_ranks_df = pd.DataFrame([MOCK_TEAM_SEASON_RANKS_DATA])
mock_roster_df = pd.DataFrame(MOCK_TEAM_ROSTER_DATA)
mock_coaches_df = pd.DataFrame(MOCK_TEAM_COACHES_DATA)

# Mock data for Team Stats
MOCK_TEAM_DASHBOARD_DATA = { # Data for a single row
    "TEAM_ID": MOCK_TEAM_ID, "TEAM_NAME": MOCK_TEAM_NAME, "GP": 70, "W": 50, "L": 20, "W_PCT": 0.714, "MIN": 48.0, "PTS": 115.0, "FGM": 42.0, "FGA": 88.0, "FG_PCT": 0.477, "FG3M": 15.0, "FG3A": 40.0, "FG3_PCT": 0.375, "FTM": 16.0, "FTA": 20.0, "FT_PCT": 0.800, "OREB": 10.0, "DREB": 35.0, "REB": 45.0, "AST": 25.0, "TOV": 13.0, "STL": 8.0, "BLK": 5.0, "PF": 19.0, "PLUS_MINUS": 5.0
}
MOCK_TEAM_HISTORICAL_DATA = [
    {"TEAM_ID": MOCK_TEAM_ID, "YEAR": "2022-23", "GP": 82, "WINS": 57, "LOSSES": 25, "WIN_PCT": 0.695, "PTS": 117.9},
    {"TEAM_ID": MOCK_TEAM_ID, "YEAR": "2021-22", "GP": 82, "WINS": 51, "LOSSES": 31, "WIN_PCT": 0.622, "PTS": 111.8}
]
mock_team_dashboard_df = pd.DataFrame([MOCK_TEAM_DASHBOARD_DATA]) # Need list for DataFrame constructor
mock_team_historical_df = pd.DataFrame(MOCK_TEAM_HISTORICAL_DATA)

# Mock data for Team Passing Stats
MOCK_TEAM_PASSES_MADE_DATA = [
    {"PASS_FROM": "Player One", "PASS_TO": "Player Two", "FREQUENCY": 0.2, "PASS": 10, "AST": 3, "FGM": 2, "FGA": 4, "FG_PCT": 0.500},
    {"PASS_FROM": "Player Two", "PASS_TO": "Player One", "FREQUENCY": 0.15, "PASS": 8, "AST": 2, "FGM": 1, "FGA": 3, "FG_PCT": 0.333}
]
MOCK_TEAM_PASSES_RECEIVED_DATA = [
    {"PASS_FROM": "Player Two", "PASS_TO": "Player One", "FREQUENCY": 0.18, "PASS": 9, "AST": 1, "FGM": 3, "FGA": 5, "FG_PCT": 0.600},
    {"PASS_FROM": "Player One", "PASS_TO": "Player Two", "FREQUENCY": 0.22, "PASS": 11, "AST": 4, "FGM": 3, "FGA": 6, "FG_PCT": 0.500}
]
mock_team_passes_made_df = pd.DataFrame(MOCK_TEAM_PASSES_MADE_DATA)
mock_team_passes_received_df = pd.DataFrame(MOCK_TEAM_PASSES_RECEIVED_DATA)


# --- Tests for fetch_team_info_and_roster_logic ---

@patch('backend.api_tools.team_tools.find_team_id_or_error')
@patch('backend.api_tools.team_tools.teaminfocommon.TeamInfoCommon')
@patch('backend.api_tools.team_tools.commonteamroster.CommonTeamRoster')
@patch('backend.api_tools.team_tools._process_dataframe')
def test_fetch_team_info_roster_success(mock_process_df, mock_roster_endpoint, mock_info_endpoint, mock_find_team):
    """Test successful fetching of team info, ranks, roster, and coaches."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)

    # Mock TeamInfoCommon endpoint
    mock_info_instance = MagicMock()
    mock_info_instance.team_info_common.get_data_frame.return_value = mock_team_info_df
    mock_info_instance.team_season_ranks.get_data_frame.return_value = mock_team_ranks_df
    mock_info_endpoint.return_value = mock_info_instance

    # Mock CommonTeamRoster endpoint
    mock_roster_instance = MagicMock()
    mock_roster_instance.common_team_roster.get_data_frame.return_value = mock_roster_df
    mock_roster_instance.coaches.get_data_frame.return_value = mock_coaches_df
    mock_roster_endpoint.return_value = mock_roster_instance

    # Mock _process_dataframe return values
    mock_process_df.side_effect = [
        MOCK_TEAM_INFO_COMMON_DATA,    # team_info_dict (Corrected: return dict)
        MOCK_TEAM_SEASON_RANKS_DATA,   # team_ranks_dict (Corrected: return dict)
        MOCK_TEAM_ROSTER_DATA,         # roster_list
        MOCK_TEAM_COACHES_DATA         # coaches_list
    ]

    # Act
    result_str = team_tools.fetch_team_info_and_roster_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once_with(MOCK_TEAM_IDENTIFIER)
    mock_info_endpoint.assert_called_once()
    mock_roster_endpoint.assert_called_once()
    assert mock_process_df.call_count == 4
    assert "error" not in result
    assert "partial_errors" not in result # Expect no partial errors on full success
    assert result.get("team_id") == MOCK_TEAM_ID
    assert result.get("team_name") == MOCK_TEAM_NAME
    assert "info" in result
    assert "ranks" in result
    assert "roster" in result
    assert "coaches" in result
    assert result["info"] == MOCK_TEAM_INFO_COMMON_DATA # Corrected: Compare dict
    assert result["ranks"] == MOCK_TEAM_SEASON_RANKS_DATA # Corrected: Compare dict
    assert result["roster"] == MOCK_TEAM_ROSTER_DATA # _process_dataframe returns list directly
    assert result["coaches"] == MOCK_TEAM_COACHES_DATA

@patch('backend.api_tools.team_tools.find_team_id_or_error')
def test_fetch_team_info_roster_team_not_found(mock_find_team):
    """Test team info/roster fetch when team is not found."""
    # Arrange
    identifier = "Unknown Team"
    mock_find_team.side_effect = TeamNotFoundError(identifier)
    expected_error = Errors.TEAM_NOT_FOUND.format(identifier=identifier)

    # Act
    result_str = team_tools.fetch_team_info_and_roster_logic(identifier, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once_with(identifier)
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_team_info_roster_empty_identifier():
    """Test team info/roster fetch with empty identifier."""
    # Arrange
    expected_error = Errors.TEAM_IDENTIFIER_EMPTY

    # Act
    result_str = team_tools.fetch_team_info_and_roster_logic("", season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_team_info_roster_invalid_season():
    """Test team info/roster fetch with invalid season."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = team_tools.fetch_team_info_and_roster_logic(MOCK_TEAM_IDENTIFIER, season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.team_tools.find_team_id_or_error')
@patch('backend.api_tools.team_tools.teaminfocommon.TeamInfoCommon')
@patch('backend.api_tools.team_tools.commonteamroster.CommonTeamRoster')
@patch('backend.api_tools.team_tools._process_dataframe') # Patch process_dataframe
def test_fetch_team_info_roster_api_error(mock_process_df, mock_roster_endpoint, mock_info_endpoint, mock_find_team):
    """Test team info/roster fetch with an API error in one of the calls."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)
    api_error_message = "NBA API timeout"
    mock_info_endpoint.side_effect = Exception(api_error_message) # Simulate info API failure

    # Mock roster success
    mock_roster_instance = MagicMock()
    mock_roster_instance.common_team_roster.get_data_frame.return_value = mock_roster_df
    mock_roster_instance.coaches.get_data_frame.return_value = mock_coaches_df
    mock_roster_endpoint.return_value = mock_roster_instance

    # Mock _process_dataframe for the successful roster/coaches calls
    # Only these calls should happen if the first API call fails
    mock_process_df.side_effect = [
        MOCK_TEAM_ROSTER_DATA,     # roster_list (success)
        MOCK_TEAM_COACHES_DATA     # coaches_list (success)
    ]

    # Act
    result_str = team_tools.fetch_team_info_and_roster_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert "error" not in result # Corrected Assertion: Should return partial data
    assert "partial_errors" in result
    assert result["partial_errors"] == ["team info/ranks API"] # Corrected Assertion: Check specific error
    assert mock_process_df.call_count == 2 # Should only be called for roster and coaches
    assert "roster" in result # Check that roster data still exists
    assert result["roster"] == MOCK_TEAM_ROSTER_DATA # Check successful part
    assert result["coaches"] == MOCK_TEAM_COACHES_DATA
    assert result["info"] == {} # Should be empty dict
    assert result["ranks"] == {} # Should be empty dict

@patch('backend.api_tools.team_tools.find_team_id_or_error')
@patch('backend.api_tools.team_tools.teaminfocommon.TeamInfoCommon')
@patch('backend.api_tools.team_tools.commonteamroster.CommonTeamRoster')
def test_fetch_team_info_roster_all_api_fail(mock_roster_endpoint, mock_info_endpoint, mock_find_team):
    """Test team info/roster fetch when all API calls fail."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)
    api_error_message = "NBA API timeout"
    mock_info_endpoint.side_effect = Exception(api_error_message)
    mock_roster_endpoint.side_effect = Exception(api_error_message)
    expected_error = Errors.TEAM_ALL_FAILED.format(
        identifier=MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON, errors='team info/ranks API, roster/coaches API'
    )

    # Act
    result_str = team_tools.fetch_team_info_and_roster_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

# --- Tests for fetch_team_stats_logic ---

@patch('backend.api_tools.team_tools.find_team_id_or_error')
@patch('backend.api_tools.team_tools.teamdashboardbygeneralsplits.TeamDashboardByGeneralSplits')
@patch('backend.api_tools.team_tools.teamyearbyyearstats.TeamYearByYearStats')
@patch('backend.api_tools.team_tools._process_dataframe')
@patch('backend.api_tools.team_tools._validate_season_format', return_value=True)
@patch('backend.api_tools.team_tools.validate_date_format', return_value=True)
def test_fetch_team_stats_success(mock_validate_date, mock_validate_season, mock_process_df, mock_historical_endpoint, mock_dashboard_endpoint, mock_find_team):
    """Test successful fetching of team dashboard and historical stats."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)

    # Mock Dashboard endpoint
    mock_dashboard_instance = MagicMock()
    mock_dashboard_instance.overall_team_dashboard.get_data_frame.return_value = mock_team_dashboard_df
    mock_dashboard_endpoint.return_value = mock_dashboard_instance

    # Mock Historical endpoint
    mock_historical_instance = MagicMock()
    mock_historical_instance.get_data_frames.return_value = [mock_team_historical_df] # Endpoint returns list
    mock_historical_endpoint.return_value = mock_historical_instance

    # Mock _process_dataframe return values
    mock_process_df.side_effect = [
        MOCK_TEAM_DASHBOARD_DATA,    # overall_stats (Corrected: return dict)
        MOCK_TEAM_HISTORICAL_DATA    # historical_stats
    ]

    # Act
    result_str = team_tools.fetch_team_stats_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once_with(MOCK_TEAM_IDENTIFIER)
    mock_dashboard_endpoint.assert_called_once()
    mock_historical_endpoint.assert_called_once()
    assert mock_process_df.call_count == 2
    assert "error" not in result
    assert "partial_errors" not in result
    assert result.get("team_id") == MOCK_TEAM_ID
    assert result.get("team_name") == MOCK_TEAM_NAME
    assert "current_stats" in result
    assert "historical_stats" in result
    assert result["current_stats"] == MOCK_TEAM_DASHBOARD_DATA # Corrected: Compare dict
    assert result["historical_stats"] == MOCK_TEAM_HISTORICAL_DATA

@patch('backend.api_tools.team_tools.find_team_id_or_error')
def test_fetch_team_stats_team_not_found(mock_find_team):
    """Test team stats fetch when team is not found."""
    # Arrange
    identifier = "Unknown Team"
    mock_find_team.side_effect = TeamNotFoundError(identifier)
    expected_error = Errors.TEAM_NOT_FOUND.format(identifier=identifier)

    # Act
    result_str = team_tools.fetch_team_stats_logic(identifier, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once_with(identifier)
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_team_stats_invalid_season():
    """Test team stats fetch with invalid season."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = team_tools.fetch_team_stats_logic(MOCK_TEAM_IDENTIFIER, season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.team_tools.find_team_id_or_error')
@patch('backend.api_tools.team_tools.teamdashboardbygeneralsplits.TeamDashboardByGeneralSplits')
@patch('backend.api_tools.team_tools.teamyearbyyearstats.TeamYearByYearStats')
@patch('backend.api_tools.team_tools._validate_season_format', return_value=True)
def test_fetch_team_stats_partial_error(mock_validate_season, mock_historical_endpoint, mock_dashboard_endpoint, mock_find_team):
    """Test team stats fetch when one API call fails but the other succeeds."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)
    dashboard_error_msg = "Dashboard API timeout"
    mock_dashboard_endpoint.side_effect = Exception(dashboard_error_msg) # Simulate dashboard failure

    # Mock Historical success
    mock_historical_instance = MagicMock()
    mock_historical_instance.get_data_frames.return_value = [mock_team_historical_df]
    mock_historical_endpoint.return_value = mock_historical_instance

    # Mock _process_dataframe for the successful historical call
    with patch('backend.api_tools.team_tools._process_dataframe', return_value=MOCK_TEAM_HISTORICAL_DATA) as mock_process_df_hist:
        # Act
        result_str = team_tools.fetch_team_stats_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
        result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once_with(MOCK_TEAM_IDENTIFIER)
    mock_dashboard_endpoint.assert_called_once()
    mock_historical_endpoint.assert_called_once()
    mock_process_df_hist.assert_called_once() # Only called for historical
    assert "error" not in result # Should not have top-level error
    assert "partial_errors" in result
    assert len(result["partial_errors"]) == 1
    assert Errors.TEAM_API.format(data_type="team dashboard", identifier=MOCK_TEAM_ID, error=dashboard_error_msg) in result["partial_errors"][0]
    assert "current_stats" in result
    assert result["current_stats"] == {} # Should be empty as it failed
    assert "historical_stats" in result
    assert result["historical_stats"] == MOCK_TEAM_HISTORICAL_DATA # Historical should be present

# --- Tests for fetch_team_passing_stats_logic ---

@patch('backend.api_tools.team_tools.find_team_id_or_error')
@patch('backend.api_tools.team_tools.teamdashptpass.TeamDashPtPass')
@patch('backend.api_tools.team_tools._process_dataframe')
@patch('backend.api_tools.team_tools._validate_season_format', return_value=True)
def test_fetch_team_passing_stats_success(mock_validate_season, mock_process_df, mock_pass_endpoint, mock_find_team):
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
    result_str = team_tools.fetch_team_passing_stats_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
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

@patch('backend.api_tools.team_tools.find_team_id_or_error')
def test_fetch_team_passing_stats_team_not_found(mock_find_team):
    """Test team passing stats fetch when team is not found."""
    # Arrange
    identifier = "Unknown Team"
    mock_find_team.side_effect = TeamNotFoundError(identifier)
    expected_error = Errors.TEAM_NOT_FOUND.format(identifier=identifier)

    # Act
    result_str = team_tools.fetch_team_passing_stats_logic(identifier, season=MOCK_SEASON)
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
    result_str = team_tools.fetch_team_passing_stats_logic(MOCK_TEAM_IDENTIFIER, season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.team_tools.find_team_id_or_error')
@patch('backend.api_tools.team_tools.teamdashptpass.TeamDashPtPass')
@patch('backend.api_tools.team_tools._validate_season_format', return_value=True)
def test_fetch_team_passing_stats_api_error(mock_validate_season, mock_pass_endpoint, mock_find_team):
    """Test team passing stats fetch with API error."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)
    api_error_message = "NBA API timeout"
    mock_pass_endpoint.side_effect = Exception(api_error_message)
    # Corrected: Expect TEAM_PASSING_API error here
    expected_error = Errors.TEAM_PASSING_API.format(identifier=MOCK_TEAM_ID, error=api_error_message)

    # Act
    result_str = team_tools.fetch_team_passing_stats_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once()
    mock_pass_endpoint.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error # Corrected Assertion

@patch('backend.api_tools.team_tools.find_team_id_or_error')
@patch('backend.api_tools.team_tools.teamdashptpass.TeamDashPtPass')
@patch('backend.api_tools.team_tools._process_dataframe')
@patch('backend.api_tools.team_tools._validate_season_format', return_value=True)
def test_fetch_team_passing_stats_processing_error(mock_validate_season, mock_process_df, mock_pass_endpoint, mock_find_team):
    """Test team passing stats fetch with processing error."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)
    mock_pass_instance = MagicMock()
    mock_pass_instance.passes_made.get_data_frame.return_value = mock_team_passes_made_df # Non-empty
    mock_pass_instance.passes_received.get_data_frame.return_value = mock_team_passes_received_df
    mock_pass_endpoint.return_value = mock_pass_instance

    mock_process_df.return_value = None # Simulate processing error
    # Corrected: Expect TEAM_PASSING_UNEXPECTED because the error happens in the inner processing block
    expected_error_base = Errors.TEAM_PASSING_PROCESSING.format(identifier=MOCK_TEAM_ID)
    expected_error = Errors.TEAM_PASSING_UNEXPECTED.format(identifier=MOCK_TEAM_IDENTIFIER, error=f"ValueError: {expected_error_base}")


    # Act
    result_str = team_tools.fetch_team_passing_stats_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count > 0
    assert "error" in result
    # Check if the error message contains the expected processing error part
    assert Errors.TEAM_PASSING_PROCESSING.format(identifier=MOCK_TEAM_ID) in result["error"]


@patch('backend.api_tools.team_tools.find_team_id_or_error')
@patch('backend.api_tools.team_tools.teamdashptpass.TeamDashPtPass')
@patch('backend.api_tools.team_tools._process_dataframe')
@patch('backend.api_tools.team_tools._validate_season_format', return_value=True)
def test_fetch_team_passing_stats_empty_df(mock_validate_season, mock_process_df, mock_pass_endpoint, mock_find_team):
    """Test team passing stats fetch with empty DataFrame response."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)
    mock_pass_instance = MagicMock()
    mock_pass_instance.passes_made.get_data_frame.return_value = pd.DataFrame() # Empty
    mock_pass_instance.passes_received.get_data_frame.return_value = pd.DataFrame() # Empty
    mock_pass_endpoint.return_value = mock_pass_instance

    mock_process_df.side_effect = [[], []] # Processing empty DFs

    # Act
    result_str = team_tools.fetch_team_passing_stats_logic(MOCK_TEAM_IDENTIFIER, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count == 2
    assert "error" not in result
    assert "passes_made" in result
    assert result["passes_made"] == []
    assert "passes_received" in result
    assert result["passes_received"] == []
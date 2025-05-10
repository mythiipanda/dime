import pytest
import json
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime

# Modules to test
from backend.api_tools import league_tools
from backend.config import Errors, CURRENT_SEASON, DEFAULT_TIMEOUT # Added DEFAULT_TIMEOUT
from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID, PerMode48, Scope, StatCategoryAbbreviation

# Mock data for Standings
MOCK_STANDINGS_DATA = [
    {'TeamID': 101, 'TeamCity': 'Team', 'TeamName': 'AAA', 'Conference': 'East', 'PlayoffRank': 1, 'WinPCT': 0.700, 'ConferenceGamesBack': 0.0, 'L10': '8-2', 'strCurrentStreak': 'W4', 'WINS': 50, 'LOSSES': 22, 'HOME': '28-8', 'ROAD': '22-14', 'Division': 'Atlantic', 'ClinchIndicator': '- e', 'DivisionRank': 1, 'ConferenceRecord': '30-15', 'DivisionRecord': '10-4'},
    {'TeamID': 102, 'TeamCity': 'Team', 'TeamName': 'BBB', 'Conference': 'West', 'PlayoffRank': 1, 'WinPCT': 0.680, 'ConferenceGamesBack': 0.0, 'L10': '7-3', 'strCurrentStreak': 'W1', 'WINS': 49, 'LOSSES': 23, 'HOME': '27-9', 'ROAD': '22-14', 'Division': 'Pacific', 'ClinchIndicator': '- w', 'DivisionRank': 1, 'ConferenceRecord': '32-12', 'DivisionRecord': '9-3'},
    {'TeamID': 103, 'TeamCity': 'Team', 'TeamName': 'CCC', 'Conference': 'East', 'PlayoffRank': 2, 'WinPCT': 0.650, 'ConferenceGamesBack': 2.0, 'L10': '6-4', 'strCurrentStreak': 'L1', 'WINS': 47, 'LOSSES': 25, 'HOME': '25-11', 'ROAD': '22-14', 'Division': 'Atlantic', 'ClinchIndicator': '- x', 'DivisionRank': 2, 'ConferenceRecord': '28-17', 'DivisionRecord': '8-6'}
]
mock_standings_df = pd.DataFrame(MOCK_STANDINGS_DATA)

# Mock data for DraftHistory
MOCK_DRAFT_YEAR = "2023"
MOCK_DRAFT_DATA = [
    {"PERSON_ID": 1629627, "PLAYER_NAME": "Zion Williamson", "ROUND_NUMBER": 1, "ROUND_PICK": 1, "OVERALL_PICK": 1, "TEAM_ID": 1610612740, "TEAM_CITY": "New Orleans", "TEAM_NAME": "Pelicans", "TEAM_ABBREVIATION": "NOP", "ORGANIZATION": "Duke"},
    {"PERSON_ID": 1629628, "PLAYER_NAME": "Ja Morant", "ROUND_NUMBER": 1, "ROUND_PICK": 2, "OVERALL_PICK": 2, "TEAM_ID": 1610612763, "TEAM_CITY": "Memphis", "TEAM_NAME": "Grizzlies", "TEAM_ABBREVIATION": "MEM", "ORGANIZATION": "Murray State"}
]
mock_draft_df = pd.DataFrame(MOCK_DRAFT_DATA)

# Mock data for LeagueLeaders
MOCK_LEADERS_DATA = [
    {"PLAYER_ID": 1, "RANK": 1, "PLAYER": "Player One", "TEAM_ID": 101, "TEAM": "AAA", "GP": 70, "MIN": 35.0, "FGM": 10.0, "FGA": 20.0, "FG_PCT": 0.500, "FG3M": 2.0, "FG3A": 5.0, "FG3_PCT": 0.400, "FTM": 5.0, "FTA": 6.0, "FT_PCT": 0.833, "OREB": 1.0, "DREB": 6.0, "REB": 7.0, "AST": 5.0, "STL": 1.5, "BLK": 0.5, "TOV": 2.5, "PTS": 27.0, "EFF": 25.0},
    {"PLAYER_ID": 2, "RANK": 2, "PLAYER": "Player Two", "TEAM_ID": 102, "TEAM": "BBB", "GP": 72, "MIN": 34.0, "FGM": 9.5, "FGA": 19.0, "FG_PCT": 0.500, "FG3M": 1.5, "FG3A": 4.0, "FG3_PCT": 0.375, "FTM": 6.0, "FTA": 7.0, "FT_PCT": 0.857, "OREB": 1.2, "DREB": 5.8, "REB": 7.0, "AST": 6.0, "STL": 1.2, "BLK": 0.6, "TOV": 2.8, "PTS": 26.5, "EFF": 24.5}
]
mock_leaders_df = pd.DataFrame(MOCK_LEADERS_DATA)


# --- Tests for fetch_league_standings_logic ---

@patch('backend.api_tools.league_tools.get_cached_standings')
@patch('backend.api_tools.league_tools._process_dataframe')
@patch('backend.api_tools.league_tools._validate_season_format', return_value=True)
def test_fetch_league_standings_success(mock_validate, mock_process_df, mock_get_cached):
    """Test successful fetching of league standings."""
    # Arrange
    mock_get_cached.return_value = mock_standings_df
    # Simulate processing *before* sorting
    mock_process_df.return_value = MOCK_STANDINGS_DATA
    # Expected data after sorting by Conf/Rank
    expected_sorted_data = [
        {'TeamID': 101, 'TeamCity': 'Team', 'TeamName': 'AAA', 'Conference': 'East', 'PlayoffRank': 1, 'WinPCT': 0.700, 'ConferenceGamesBack': 0.0, 'L10': '8-2', 'strCurrentStreak': 'W4', 'WINS': 50, 'LOSSES': 22, 'HOME': '28-8', 'ROAD': '22-14', 'Division': 'Atlantic', 'ClinchIndicator': '- e', 'DivisionRank': 1, 'ConferenceRecord': '30-15', 'DivisionRecord': '10-4'},
        {'TeamID': 103, 'TeamCity': 'Team', 'TeamName': 'CCC', 'Conference': 'East', 'PlayoffRank': 2, 'WinPCT': 0.650, 'ConferenceGamesBack': 2.0, 'L10': '6-4', 'strCurrentStreak': 'L1', 'WINS': 47, 'LOSSES': 25, 'HOME': '25-11', 'ROAD': '22-14', 'Division': 'Atlantic', 'ClinchIndicator': '- x', 'DivisionRank': 2, 'ConferenceRecord': '28-17', 'DivisionRecord': '8-6'},
        {'TeamID': 102, 'TeamCity': 'Team', 'TeamName': 'BBB', 'Conference': 'West', 'PlayoffRank': 1, 'WinPCT': 0.680, 'ConferenceGamesBack': 0.0, 'L10': '7-3', 'strCurrentStreak': 'W1', 'WINS': 49, 'LOSSES': 23, 'HOME': '27-9', 'ROAD': '22-14', 'Division': 'Pacific', 'ClinchIndicator': '- w', 'DivisionRank': 1, 'ConferenceRecord': '32-12', 'DivisionRecord': '9-3'}
    ]


    # Act
    result_str = league_tools.fetch_league_standings_logic(season=CURRENT_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_validate.assert_called_once_with(CURRENT_SEASON)
    mock_get_cached.assert_called_once()
    mock_process_df.assert_called_once()
    assert "error" not in result
    assert "standings" in result
    # Assert the final sorted list
    assert result["standings"] == expected_sorted_data

def test_fetch_league_standings_invalid_season():
    """Test league standings fetch with invalid season format."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = league_tools.fetch_league_standings_logic(season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.league_tools.get_cached_standings')
@patch('backend.api_tools.league_tools._validate_season_format', return_value=True)
def test_fetch_league_standings_api_error_in_cache(mock_validate, mock_get_cached):
    """Test league standings fetch when the cached function itself raises an API error."""
    # Arrange
    api_error_message = "NBA API timeout in cache"
    # Simulate the cached function raising an error (which propagates)
    mock_get_cached.side_effect = Exception(api_error_message)
    expected_error = Errors.LEAGUE_STANDINGS_UNEXPECTED.format(season=CURRENT_SEASON, error=api_error_message)

    # Act
    result_str = league_tools.fetch_league_standings_logic(season=CURRENT_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_validate.assert_called_once_with(CURRENT_SEASON)
    mock_get_cached.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.league_tools.get_cached_standings')
@patch('backend.api_tools.league_tools._process_dataframe')
@patch('backend.api_tools.league_tools._validate_season_format', return_value=True)
def test_fetch_league_standings_processing_error(mock_validate, mock_process_df, mock_get_cached):
    """Test league standings fetch with processing error."""
    # Arrange
    mock_get_cached.return_value = mock_standings_df
    mock_process_df.return_value = None # Simulate processing error
    expected_error = Errors.LEAGUE_STANDINGS_PROCESSING.format(season=CURRENT_SEASON)

    # Act
    result_str = league_tools.fetch_league_standings_logic(season=CURRENT_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_validate.assert_called_once_with(CURRENT_SEASON)
    mock_get_cached.assert_called_once()
    mock_process_df.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.league_tools.get_cached_standings')
@patch('backend.api_tools.league_tools._validate_season_format', return_value=True)
def test_fetch_league_standings_empty_df(mock_validate, mock_get_cached):
    """Test league standings fetch with empty DataFrame response from cache."""
    # Arrange
    mock_get_cached.return_value = pd.DataFrame() # Empty DF

    # Mock the secondary check within the logic to also return empty
    with patch('backend.api_tools.league_tools.leaguestandingsv3.LeagueStandingsV3') as mock_secondary_call:
        mock_secondary_instance = MagicMock()
        mock_secondary_instance.standings.get_data_frame.return_value = pd.DataFrame()
        mock_secondary_call.return_value = mock_secondary_instance

        # Act
        result_str = league_tools.fetch_league_standings_logic(season=CURRENT_SEASON)
        result = json.loads(result_str)

    # Assert
    mock_validate.assert_called_once_with(CURRENT_SEASON)
    mock_get_cached.assert_called_once()
    mock_secondary_call.assert_called_once() # Ensure the check was made
    assert "error" not in result
    assert "standings" in result
    assert result["standings"] == [] # Expect empty list

# --- Tests for fetch_draft_history_logic ---

@patch('backend.api_tools.league_tools.drafthistory.DraftHistory')
@patch('backend.api_tools.league_tools._process_dataframe')
def test_fetch_draft_history_success(mock_process_df, mock_draft_endpoint):
    """Test successful fetching of draft history for a specific year."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.draft_history.get_data_frame.return_value = mock_draft_df
    mock_draft_endpoint.return_value = mock_endpoint_instance

    mock_process_df.return_value = MOCK_DRAFT_DATA

    # Act
    result_str = league_tools.fetch_draft_history_logic(season_year=MOCK_DRAFT_YEAR)
    result = json.loads(result_str)

    # Assert
    mock_draft_endpoint.assert_called_once_with(
        league_id=LeagueID.nba, season_year_nullable=MOCK_DRAFT_YEAR, timeout=DEFAULT_TIMEOUT
    )
    mock_process_df.assert_called_once()
    assert "error" not in result
    assert result.get("season_year_requested") == MOCK_DRAFT_YEAR
    assert "draft_picks" in result
    assert result["draft_picks"] == MOCK_DRAFT_DATA

@patch('backend.api_tools.league_tools.drafthistory.DraftHistory')
@patch('backend.api_tools.league_tools._process_dataframe')
def test_fetch_draft_history_all_years_success(mock_process_df, mock_draft_endpoint):
    """Test successful fetching of draft history for all years."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.draft_history.get_data_frame.return_value = mock_draft_df # Use same mock data
    mock_draft_endpoint.return_value = mock_endpoint_instance

    mock_process_df.return_value = MOCK_DRAFT_DATA

    # Act
    result_str = league_tools.fetch_draft_history_logic(season_year=None) # No year specified
    result = json.loads(result_str)

    # Assert
    mock_draft_endpoint.assert_called_once_with(
        league_id=LeagueID.nba, season_year_nullable=None, timeout=DEFAULT_TIMEOUT
    )
    mock_process_df.assert_called_once()
    assert "error" not in result
    assert result.get("season_year_requested") == "All"
    assert "draft_picks" in result
    assert result["draft_picks"] == MOCK_DRAFT_DATA

def test_fetch_draft_history_invalid_year_format():
    """Test draft history fetch with invalid year format."""
    # Arrange
    invalid_year = "23-24"
    expected_error = Errors.INVALID_DRAFT_YEAR_FORMAT.format(year=invalid_year)

    # Act
    result_str = league_tools.fetch_draft_history_logic(season_year=invalid_year)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.league_tools.drafthistory.DraftHistory')
def test_fetch_draft_history_api_error(mock_draft_endpoint):
    """Test draft history fetch with API error."""
    # Arrange
    api_error_message = "NBA API timeout"
    mock_draft_endpoint.side_effect = Exception(api_error_message)
    # Corrected expected error to match the except block in the source code
    expected_error = Errors.DRAFT_HISTORY_UNEXPECTED.format(year=MOCK_DRAFT_YEAR, error=api_error_message)

    # Act
    result_str = league_tools.fetch_draft_history_logic(season_year=MOCK_DRAFT_YEAR)
    result = json.loads(result_str)

    # Assert
    mock_draft_endpoint.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.league_tools.drafthistory.DraftHistory')
@patch('backend.api_tools.league_tools._process_dataframe')
def test_fetch_draft_history_processing_error(mock_process_df, mock_draft_endpoint):
    """Test draft history fetch with processing error."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.draft_history.get_data_frame.return_value = mock_draft_df
    mock_draft_endpoint.return_value = mock_endpoint_instance

    mock_process_df.return_value = None # Simulate processing error
    expected_error = Errors.DRAFT_HISTORY_PROCESSING.format(year=MOCK_DRAFT_YEAR)

    # Act
    result_str = league_tools.fetch_draft_history_logic(season_year=MOCK_DRAFT_YEAR)
    result = json.loads(result_str)

    # Assert
    mock_draft_endpoint.assert_called_once()
    mock_process_df.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.league_tools.drafthistory.DraftHistory')
@patch('backend.api_tools.league_tools._process_dataframe')
def test_fetch_draft_history_empty_df(mock_process_df, mock_draft_endpoint):
    """Test draft history fetch with empty DataFrame response."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.draft_history.get_data_frame.return_value = pd.DataFrame() # Empty DF
    mock_draft_endpoint.return_value = mock_endpoint_instance

    mock_process_df.return_value = [] # Processing empty DF returns empty list

    # Act
    result_str = league_tools.fetch_draft_history_logic(season_year=MOCK_DRAFT_YEAR)
    result = json.loads(result_str)

    # Assert
    mock_draft_endpoint.assert_called_once()
    mock_process_df.assert_called_once()
    assert "error" not in result
    assert "draft_picks" in result
    assert result["draft_picks"] == []

# --- Tests for fetch_league_leaders_logic ---

@patch('backend.api_tools.league_tools.leagueleaders.LeagueLeaders')
@patch('backend.api_tools.league_tools._process_dataframe')
@patch('backend.api_tools.league_tools._validate_season_format', return_value=True)
def test_fetch_league_leaders_success(mock_validate, mock_process_df, mock_leaders_endpoint):
    """Test successful fetching of league leaders."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.league_leaders.get_data_frame.return_value = mock_leaders_df
    mock_leaders_endpoint.return_value = mock_endpoint_instance

    # Corrected: Mock _process_dataframe to return the sliced data
    top_n = 1
    mock_process_df.return_value = MOCK_LEADERS_DATA[:top_n]

    # Act
    result_str = league_tools.fetch_league_leaders_logic(season=CURRENT_SEASON, top_n=top_n, stat_category=StatCategoryAbbreviation.pts) # Corrected: Use .pts
    result = json.loads(result_str)

    # Assert
    mock_leaders_endpoint.assert_called_once_with(
        season=CURRENT_SEASON, stat_category_abbreviation=StatCategoryAbbreviation.pts, # Corrected: Use .pts
        season_type_all_star=SeasonTypeAllStar.regular, per_mode48=PerMode48.per_game,
        league_id=LeagueID.nba, scope=Scope.s, timeout=DEFAULT_TIMEOUT
    )
    # Corrected: _process_dataframe is called with the sliced DataFrame
    mock_process_df.assert_called_once()
    # Check the argument passed to _process_dataframe
    call_args, _ = mock_process_df.call_args
    processed_df = call_args[0]
    assert isinstance(processed_df, pd.DataFrame)
    assert len(processed_df) == top_n # Ensure the sliced DF was passed

    assert "error" not in result
    assert "leaders" in result
    assert len(result["leaders"]) == top_n # Check that top_n was applied in the final result
    assert result["leaders"][0]["PLAYER_ID"] == 1

@patch('backend.api_tools.league_tools.leagueleaders.LeagueLeaders')
@patch('backend.api_tools.league_tools._process_dataframe')
@patch('backend.api_tools.league_tools._validate_season_format', return_value=True)
def test_fetch_league_leaders_success_all(mock_validate, mock_process_df, mock_leaders_endpoint):
    """Test successful fetching of league leaders with top_n=0 (all)."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.league_leaders.get_data_frame.return_value = mock_leaders_df
    mock_leaders_endpoint.return_value = mock_endpoint_instance
    mock_process_df.return_value = MOCK_LEADERS_DATA

    # Act
    result_str = league_tools.fetch_league_leaders_logic(season=CURRENT_SEASON, top_n=0, stat_category=StatCategoryAbbreviation.pts) # Corrected: Use .pts
    result = json.loads(result_str)

    # Assert
    assert "error" not in result
    assert "leaders" in result
    assert len(result["leaders"]) == len(MOCK_LEADERS_DATA) # Check all are returned

def test_fetch_league_leaders_invalid_season():
    """Test league leaders fetch with invalid season format."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = league_tools.fetch_league_leaders_logic(season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.league_tools.leagueleaders.LeagueLeaders')
@patch('backend.api_tools.league_tools._validate_season_format', return_value=True)
def test_fetch_league_leaders_api_error(mock_validate, mock_leaders_endpoint):
    """Test league leaders fetch with API error."""
    # Arrange
    api_error_message = "NBA API timeout"
    mock_leaders_endpoint.side_effect = Exception(api_error_message)
    expected_error = Errors.LEAGUE_LEADERS_UNEXPECTED.format(stat=StatCategoryAbbreviation.pts, season=CURRENT_SEASON, error=api_error_message) # Corrected: Use .pts

    # Act
    result_str = league_tools.fetch_league_leaders_logic(season=CURRENT_SEASON, stat_category=StatCategoryAbbreviation.pts) # Corrected: Use .pts
    result = json.loads(result_str)

    # Assert
    mock_leaders_endpoint.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.league_tools.leagueleaders.LeagueLeaders')
@patch('backend.api_tools.league_tools._process_dataframe')
@patch('backend.api_tools.league_tools._validate_season_format', return_value=True)
def test_fetch_league_leaders_processing_error(mock_validate, mock_process_df, mock_leaders_endpoint):
    """Test league leaders fetch with processing error."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.league_leaders.get_data_frame.return_value = mock_leaders_df
    mock_leaders_endpoint.return_value = mock_endpoint_instance

    mock_process_df.return_value = None # Simulate processing error
    expected_error = Errors.PROCESSING_ERROR.format(error=f"league leaders data for {CURRENT_SEASON}, {StatCategoryAbbreviation.pts}") # Corrected: Use .pts

    # Act
    result_str = league_tools.fetch_league_leaders_logic(season=CURRENT_SEASON, stat_category=StatCategoryAbbreviation.pts) # Corrected: Use .pts
    result = json.loads(result_str)

    # Assert
    mock_leaders_endpoint.assert_called_once()
    mock_process_df.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.league_tools.leagueleaders.LeagueLeaders')
@patch('backend.api_tools.league_tools._process_dataframe')
@patch('backend.api_tools.league_tools._validate_season_format', return_value=True)
def test_fetch_league_leaders_empty_df(mock_validate, mock_process_df, mock_leaders_endpoint):
    """Test league leaders fetch with empty DataFrame response."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.league_leaders.get_data_frame.return_value = pd.DataFrame() # Empty DF
    mock_leaders_endpoint.return_value = mock_endpoint_instance

    # Act
    result_str = league_tools.fetch_league_leaders_logic(season=CURRENT_SEASON, stat_category=StatCategoryAbbreviation.pts) # Corrected: Use .pts
    result = json.loads(result_str)

    # Assert
    mock_leaders_endpoint.assert_called_once()
    mock_process_df.assert_not_called() # Should return before processing
    assert "error" not in result
    assert "leaders" in result
    assert result["leaders"] == [] # Expect empty list
import pytest
import json
from unittest.mock import patch, MagicMock
import pandas as pd

# Modules to test
from backend.api_tools import search
from backend.api_tools.utils import TeamNotFoundError, format_response # Import format_response if needed
from backend.config import Errors, CURRENT_SEASON, MIN_PLAYER_SEARCH_LENGTH, MAX_SEARCH_RESULTS, DEFAULT_TIMEOUT # Added DEFAULT_TIMEOUT
from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID # Added LeagueID

# Mock data - Define constants used across tests
MOCK_SEASON = CURRENT_SEASON
MOCK_TEAM_ID = 1610612747 # LAL example
MOCK_TEAM_NAME = "Los Angeles Lakers"

# Mock data for static lists
MOCK_STATIC_PLAYERS = [
    {'id': 2544, 'full_name': 'LeBron James', 'is_active': True},
    {'id': 201939, 'full_name': 'Stephen Curry', 'is_active': True},
    {'id': 1628369, 'full_name': 'Jayson Tatum', 'is_active': True},
    {'id': 1629027, 'full_name': 'Trae Young', 'is_active': True},
    {'id': 101108, 'full_name': 'Chris Paul', 'is_active': True},
    {'id': 201566, 'full_name': 'Russell Westbrook', 'is_active': True} # Example inactive player (for testing)
]
MOCK_STATIC_TEAMS = [
    {'id': 1610612738, 'full_name': 'Boston Celtics', 'abbreviation': 'BOS', 'nickname': 'Celtics', 'city': 'Boston', 'state': 'Massachusetts', 'year_founded': 1946},
    {'id': 1610612747, 'full_name': 'Los Angeles Lakers', 'abbreviation': 'LAL', 'nickname': 'Lakers', 'city': 'Los Angeles', 'state': 'California', 'year_founded': 1947},
    {'id': 1610612744, 'full_name': 'Golden State Warriors', 'abbreviation': 'GSW', 'nickname': 'Warriors', 'city': 'Golden State', 'state': 'California', 'year_founded': 1946}
]
MOCK_GAME_SEARCH_DATA = [ # Simplified game data
    {'GAME_ID': '0022300100', 'GAME_DATE': '2023-11-10', 'MATCHUP': 'LAL vs. PHX', 'WL': 'W'},
    {'GAME_ID': '0022300200', 'GAME_DATE': '2023-11-25', 'MATCHUP': 'LAL @ CLE', 'WL': 'L'},
    {'GAME_ID': '0022300300', 'GAME_DATE': '2023-12-05', 'MATCHUP': 'BOS vs. LAL', 'WL': 'W'} # Example H2H
]
mock_game_search_df = pd.DataFrame(MOCK_GAME_SEARCH_DATA)

# --- Tests for search_players_logic ---

@patch('backend.api_tools.search._get_cached_player_list')
def test_search_players_success(mock_get_players):
    """Test successful player search."""
    # Arrange
    mock_get_players.return_value = MOCK_STATIC_PLAYERS
    query = "James"
    expected_players = [{'id': 2544, 'full_name': 'LeBron James', 'is_active': True}]

    # Act
    result_str = search.search_players_logic(query)
    result = json.loads(result_str)

    # Assert
    mock_get_players.assert_called_once()
    assert "error" not in result
    assert "players" in result
    # Compare based on id and name, ignore is_active for simplicity if needed
    assert result["players"] == expected_players

@patch('backend.api_tools.search._get_cached_player_list')
def test_search_players_no_match(mock_get_players):
    """Test player search with no matching results."""
    # Arrange
    mock_get_players.return_value = MOCK_STATIC_PLAYERS
    query = "NonExistent"

    # Act
    result_str = search.search_players_logic(query)
    result = json.loads(result_str)

    # Assert
    assert "error" not in result
    assert "players" in result
    assert result["players"] == []

def test_search_players_empty_query():
    """Test player search with empty query."""
    # Arrange
    expected_error = Errors.EMPTY_SEARCH_QUERY

    # Act
    result_str = search.search_players_logic("")
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_search_players_query_too_short():
    """Test player search with query too short."""
    # Arrange
    query = "Le"
    expected_error = Errors.SEARCH_QUERY_TOO_SHORT.format(min_length=MIN_PLAYER_SEARCH_LENGTH)

    # Act
    result_str = search.search_players_logic(query)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.search._get_cached_player_list', side_effect=Exception("Cache fetch failed"))
def test_search_players_exception(mock_get_players):
    """Test player search with an unexpected exception."""
    # Arrange
    query = "James"
    expected_error = Errors.PLAYER_SEARCH_UNEXPECTED.format(error="Cache fetch failed")

    # Act
    result_str = search.search_players_logic(query)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

# --- Tests for search_teams_logic ---

@patch('backend.api_tools.search.teams.get_teams')
def test_search_teams_success(mock_get_teams):
    """Test successful team search."""
    # Arrange
    mock_get_teams.return_value = MOCK_STATIC_TEAMS
    query = "Lakers"
    expected_teams = [MOCK_STATIC_TEAMS[1]] # Los Angeles Lakers

    # Act
    result_str = search.search_teams_logic(query)
    result = json.loads(result_str)

    # Assert
    mock_get_teams.assert_called_once()
    assert "error" not in result
    assert "teams" in result
    assert result["teams"] == expected_teams

@patch('backend.api_tools.search.teams.get_teams')
def test_search_teams_no_match(mock_get_teams):
    """Test team search with no matching results."""
    # Arrange
    mock_get_teams.return_value = MOCK_STATIC_TEAMS
    query = "NonExistent"

    # Act
    result_str = search.search_teams_logic(query)
    result = json.loads(result_str)

    # Assert
    assert "error" not in result
    assert "teams" in result
    assert result["teams"] == []

def test_search_teams_empty_query():
    """Test team search with empty query."""
    # Arrange
    expected_error = Errors.EMPTY_SEARCH_QUERY

    # Act
    result_str = search.search_teams_logic("")
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.search.teams.get_teams', side_effect=Exception("Static list failed"))
def test_search_teams_exception(mock_get_teams):
    """Test team search with an unexpected exception."""
    # Arrange
    query = "Celtics"
    expected_error = Errors.TEAM_SEARCH_UNEXPECTED.format(error="Static list failed")

    # Act
    result_str = search.search_teams_logic(query)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

# --- Tests for search_games_logic ---

@patch('backend.api_tools.search.find_team_id_or_error')
@patch('backend.api_tools.search.leaguegamefinder.LeagueGameFinder')
@patch('backend.api_tools.search._process_dataframe')
@patch('backend.api_tools.search._validate_season_format', return_value=True)
def test_search_games_single_team_success(mock_validate, mock_process, mock_finder, mock_find_team):
    """Test successful game search for a single team."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME) # Mock finding Lakers
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.league_game_finder_results.get_data_frame.return_value = mock_game_search_df
    mock_finder.return_value = mock_endpoint_instance
    mock_process.return_value = MOCK_GAME_SEARCH_DATA # Assume processing returns all games initially

    # Act
    result_str = search.search_games_logic("Lakers", season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once_with("Lakers")
    mock_finder.assert_called_once()
    mock_process.assert_called_once()
    assert "error" not in result
    assert "games" in result
    assert len(result["games"]) > 0 # Should find games involving Lakers

@patch('backend.api_tools.search.find_team_id_or_error')
@patch('backend.api_tools.search.leaguegamefinder.LeagueGameFinder')
@patch('backend.api_tools.search._process_dataframe')
@patch('backend.api_tools.search._validate_season_format', return_value=True)
@patch('backend.api_tools.search.teams') # Mock the static teams module used for abbr lookup
def test_search_games_two_teams_success(mock_static_teams, mock_validate, mock_process, mock_finder, mock_find_team):
    """Test successful game search for a head-to-head matchup."""
    # Arrange
    # Simulate finding both teams
    mock_find_team.side_effect = [
        (1610612738, "Boston Celtics"), # BOS
        (1610612747, "Los Angeles Lakers")  # LAL
    ]
    # Mock the abbreviation lookup
    mock_static_teams.find_team_name_by_id.side_effect = [
        {'abbreviation': 'BOS'},
        {'abbreviation': 'LAL'}
    ]
    mock_endpoint_instance = MagicMock()
    # Return all mock games initially, filtering happens later in the source code
    mock_endpoint_instance.league_game_finder_results.get_data_frame.return_value = mock_game_search_df
    mock_finder.return_value = mock_endpoint_instance
    # Mock _process_dataframe to return its input (the filtered DataFrame converted to dict)
    mock_process.side_effect = lambda df, single_row: df.to_dict(orient='records')

    # Act
    result_str = search.search_games_logic("BOS vs LAL", season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert mock_find_team.call_count == 2
    mock_finder.assert_called_once()
    # Check that _process_dataframe was called with the filtered DataFrame
    mock_process.assert_called_once()
    call_args, _ = mock_process.call_args
    processed_df_arg = call_args[0]
    assert isinstance(processed_df_arg, pd.DataFrame)
    assert len(processed_df_arg) == 1 # Should have been filtered to 1 game before processing
    assert processed_df_arg.iloc[0]['GAME_ID'] == '0022300300'

    assert "error" not in result
    assert "games" in result
    assert len(result["games"]) == 1
    assert result["games"][0]['GAME_ID'] == '0022300300' # Final assertion on processed result

@patch('backend.api_tools.search.find_team_id_or_error', side_effect=TeamNotFoundError("query"))
@patch('backend.api_tools.search._validate_season_format', return_value=True)
def test_search_games_team_not_found(mock_validate, mock_find_team):
    """Test game search when the team query doesn't match any team."""
    # Arrange
    query = "NonExistent Team"

    # Act
    result_str = search.search_games_logic(query, season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once_with(query)
    assert "error" not in result # Should return empty list, not error
    assert "games" in result
    assert result["games"] == []

def test_search_games_invalid_season():
    """Test game search with invalid season."""
    # Arrange
    invalid_season = "abc"
    expected_error = Errors.INVALID_SEASON # Assuming this constant exists

    # Act
    result_str = search.search_games_logic("Lakers", season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.search.find_team_id_or_error')
@patch('backend.api_tools.search.leaguegamefinder.LeagueGameFinder')
@patch('backend.api_tools.search._validate_season_format', return_value=True)
def test_search_games_api_error(mock_validate, mock_finder, mock_find_team):
    """Test game search with API error."""
    # Arrange
    mock_find_team.return_value = (MOCK_TEAM_ID, MOCK_TEAM_NAME)
    api_error_message = "NBA API timeout"
    mock_finder.side_effect = Exception(api_error_message)
    expected_error = Errors.GAME_SEARCH_UNEXPECTED.format(error=api_error_message)

    # Act
    result_str = search.search_games_logic("Lakers", season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_team.assert_called_once()
    mock_finder.assert_called_once() # Corrected: Should be called now
    assert "error" in result
    assert result["error"] == expected_error
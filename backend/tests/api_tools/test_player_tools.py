import pytest
import json
from unittest.mock import patch, MagicMock
import pandas as pd

from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed
# Modules to test
from backend.api_tools import player_tools
from backend.api_tools.utils import PlayerNotFoundError
from backend.config import Errors

# Mock data for nba_api responses
MOCK_PLAYER_ID = 2544 # LeBron James example
MOCK_PLAYER_NAME = "LeBron James"
MOCK_COMMON_PLAYER_INFO_DATA = {
    'PERSON_ID': [MOCK_PLAYER_ID],
    'FIRST_NAME': ['LeBron'],
    'LAST_NAME': ['James'],
    'DISPLAY_FIRST_LAST': [MOCK_PLAYER_NAME],
    'BIRTHDATE': ['1984-12-30T00:00:00'],
    'SCHOOL': ['St. Vincent-St. Mary HS (OH)'],
    'COUNTRY': ['USA'],
    'HEIGHT': ['6-9'],
    'WEIGHT': ['250'],
    'SEASON_EXP': [21],
    'JERSEY': ['23'],
    'POSITION': ['Forward'],
    'ROSTERSTATUS': ['Active'],
    'TEAM_ID': [1610612747],
    'TEAM_NAME': ['Lakers'],
    'TEAM_ABBREVIATION': ['LAL'],
    'TEAM_CODE': ['lakers'],
    'FROM_YEAR': [2003],
    'TO_YEAR': [2023], # Example data
    'DLEAGUE_FLAG': ['N'],
    'NBA_FLAG': ['Y'],
    'GAMES_PLAYED_FLAG': ['Y'],
    'DRAFT_YEAR': ['2003'],
    'DRAFT_ROUND': ['1'],
    'DRAFT_NUMBER': ['1'],
    'PTS': [25.0], # Example data
    'AST': [7.0],  # Example data
    'REB': [7.0]   # Example data
}
MOCK_HEADLINE_STATS_DATA = {
    'PLAYER_ID': [MOCK_PLAYER_ID],
    'PLAYER_NAME': [MOCK_PLAYER_NAME],
    'TimeFrame': ['Career'],
    'PTS': [27.1],
    'AST': [7.4],
    'REB': [7.5],
    'PIE': [0.18] # Example data
}

# Create mock DataFrames
mock_common_player_info_df = pd.DataFrame(MOCK_COMMON_PLAYER_INFO_DATA)
mock_headline_stats_df = pd.DataFrame(MOCK_HEADLINE_STATS_DATA)

# --- Tests for fetch_player_info_logic ---

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.commonplayerinfo.CommonPlayerInfo')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_info_success(mock_process_df, mock_common_info, mock_find_player):
    """Test successful fetching of player info."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    
    # Mock the endpoint instance and its methods to return mock DataFrames
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.common_player_info.get_data_frame.return_value = mock_common_player_info_df
    mock_endpoint_instance.player_headline_stats.get_data_frame.return_value = mock_headline_stats_df
    mock_common_info.return_value = mock_endpoint_instance

    # Mock _process_dataframe return values
    mock_process_df.side_effect = [
        MOCK_COMMON_PLAYER_INFO_DATA, # First call for common_player_info
        MOCK_HEADLINE_STATS_DATA      # Second call for player_headline_stats
    ]

    # Act
    result_str = player_tools.fetch_player_info_logic(MOCK_PLAYER_NAME)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_common_info.assert_called_once_with(player_id=MOCK_PLAYER_ID, timeout=player_tools.DEFAULT_TIMEOUT)
    assert mock_process_df.call_count == 2
    assert "error" not in result
    assert "player_info" in result
    assert "headline_stats" in result
    assert result["player_info"] == MOCK_COMMON_PLAYER_INFO_DATA
    assert result["headline_stats"] == MOCK_HEADLINE_STATS_DATA

@patch('backend.api_tools.player_tools.find_player_id_or_error')
def test_fetch_player_info_player_not_found(mock_find_player):
    """Test player not found scenario."""
    # Arrange
    player_name = "Unknown Player"
    mock_find_player.side_effect = PlayerNotFoundError(player_name)
    expected_error = Errors.PLAYER_NOT_FOUND.format(name=player_name)

    # Act
    result_str = player_tools.fetch_player_info_logic(player_name)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(player_name)
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_player_info_empty_name():
    """Test empty player name scenario."""
    # Arrange
    player_name = ""
    expected_error = Errors.PLAYER_NAME_EMPTY

    # Act
    result_str = player_tools.fetch_player_info_logic(player_name)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.commonplayerinfo.CommonPlayerInfo')
def test_fetch_player_info_api_error(mock_common_info, mock_find_player):
    """Test scenario where the nba_api call fails."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    api_error_message = "NBA API timeout"
    mock_common_info.side_effect = Exception(api_error_message) # Simulate API call failure
    expected_error = Errors.PLAYER_INFO_API.format(name=MOCK_PLAYER_NAME, error=api_error_message)

    # Act
    result_str = player_tools.fetch_player_info_logic(MOCK_PLAYER_NAME)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_common_info.assert_called_once_with(player_id=MOCK_PLAYER_ID, timeout=player_tools.DEFAULT_TIMEOUT)
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.commonplayerinfo.CommonPlayerInfo')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_info_processing_error(mock_process_df, mock_common_info, mock_find_player):
    """Test scenario where DataFrame processing fails."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.common_player_info.get_data_frame.return_value = mock_common_player_info_df
    mock_endpoint_instance.player_headline_stats.get_data_frame.return_value = mock_headline_stats_df
    mock_common_info.return_value = mock_endpoint_instance

    # Simulate _process_dataframe returning None (indicating processing error)
    mock_process_df.return_value = None 
    expected_error = Errors.PLAYER_INFO_PROCESSING.format(name=MOCK_PLAYER_NAME)

    # Act
    result_str = player_tools.fetch_player_info_logic(MOCK_PLAYER_NAME)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_common_info.assert_called_once_with(player_id=MOCK_PLAYER_ID, timeout=player_tools.DEFAULT_TIMEOUT)
    assert mock_process_df.call_count > 0 # It should be called at least once
    assert "error" in result
    assert result["error"] == expected_error

# --- Add tests for other functions (gamelog, career_stats, awards, etc.) below ---
# Mock data for gamelog tests
MOCK_SEASON = "2023-24"
MOCK_GAMELOG_DATA = [
    {
        'GAME_ID': '0022300001', 'GAME_DATE': '2023-10-24', 'MATCHUP': 'LAL @ DEN', 'WL': 'L', 'MIN': 30, 'FGM': 8, 'FGA': 15, 'FG_PCT': 0.533,
        'FG3M': 1, 'FG3A': 3, 'FG3_PCT': 0.333, 'FTM': 2, 'FTA': 2, 'FT_PCT': 1.0, 'OREB': 1, 'DREB': 5,
        'REB': 6, 'AST': 4, 'STL': 1, 'BLK': 0, 'TOV': 3, 'PF': 2, 'PTS': 19, 'PLUS_MINUS': -5
    },
    {
        'GAME_ID': '0022300002', 'GAME_DATE': '2023-10-26', 'MATCHUP': 'LAL vs. PHX', 'WL': 'W', 'MIN': 35, 'FGM': 10, 'FGA': 20, 'FG_PCT': 0.500,
        'FG3M': 2, 'FG3A': 5, 'FG3_PCT': 0.400, 'FTM': 5, 'FTA': 6, 'FT_PCT': 0.833, 'OREB': 2, 'DREB': 8,
        'REB': 10, 'AST': 9, 'STL': 2, 'BLK': 1, 'TOV': 4, 'PF': 3, 'PTS': 27, 'PLUS_MINUS': 10
    }
]
mock_gamelog_df = pd.DataFrame(MOCK_GAMELOG_DATA)

# --- Tests for fetch_player_gamelog_logic ---

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.playergamelog.PlayerGameLog')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_gamelog_success(mock_process_df, mock_gamelog, mock_find_player):
    """Test successful fetching of player gamelog."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    
    mock_endpoint_instance = MagicMock()
    # IMPORTANT: get_data_frames() returns a LIST of dataframes
    mock_endpoint_instance.get_data_frames.return_value = [mock_gamelog_df] 
    mock_gamelog.return_value = mock_endpoint_instance

    mock_process_df.return_value = MOCK_GAMELOG_DATA # Simulate successful processing

    # Act
    result_str = player_tools.fetch_player_gamelog_logic(MOCK_PLAYER_NAME, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_gamelog.assert_called_once_with(
        player_id=MOCK_PLAYER_ID, 
        season=MOCK_SEASON, 
        season_type_all_star=SeasonTypeAllStar.regular, # Default season type
        timeout=player_tools.DEFAULT_TIMEOUT
    )
    mock_process_df.assert_called_once() # Check it was called
    assert "error" not in result
    assert result.get("player_name") == MOCK_PLAYER_NAME
    assert result.get("player_id") == MOCK_PLAYER_ID
    assert result.get("season") == MOCK_SEASON
    assert "gamelog" in result
    assert result["gamelog"] == MOCK_GAMELOG_DATA

@patch('backend.api_tools.player_tools.find_player_id_or_error')
def test_fetch_player_gamelog_player_not_found(mock_find_player):
    """Test player not found scenario for gamelog."""
    # Arrange
    player_name = "Unknown Player"
    mock_find_player.side_effect = PlayerNotFoundError(player_name)
    expected_error = Errors.PLAYER_NOT_FOUND.format(name=player_name)

    # Act
    result_str = player_tools.fetch_player_gamelog_logic(player_name, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(player_name)
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_player_gamelog_invalid_season():
    """Test invalid season format for gamelog."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = player_tools.fetch_player_gamelog_logic(MOCK_PLAYER_NAME, invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.playergamelog.PlayerGameLog')
def test_fetch_player_gamelog_api_error(mock_gamelog, mock_find_player):
    """Test scenario where the gamelog API call fails."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    api_error_message = "NBA API timeout"
    mock_gamelog.side_effect = Exception(api_error_message)
    expected_error = Errors.PLAYER_GAMELOG_API.format(name=MOCK_PLAYER_NAME, season=MOCK_SEASON, error=api_error_message)

    # Act
    result_str = player_tools.fetch_player_gamelog_logic(MOCK_PLAYER_NAME, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_gamelog.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.playergamelog.PlayerGameLog')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_gamelog_processing_error(mock_process_df, mock_gamelog, mock_find_player):
    """Test scenario where gamelog DataFrame processing fails."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.get_data_frames.return_value = [mock_gamelog_df] 
    mock_gamelog.return_value = mock_endpoint_instance

    mock_process_df.return_value = None # Simulate processing error
    expected_error = Errors.PLAYER_GAMELOG_PROCESSING.format(name=MOCK_PLAYER_NAME, season=MOCK_SEASON)

    # Act
    result_str = player_tools.fetch_player_gamelog_logic(MOCK_PLAYER_NAME, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_gamelog.assert_called_once()
    mock_process_df.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.playergamelog.PlayerGameLog')
@patch('backend.api_tools.player_tools._process_dataframe') # Need to mock this even if not used directly in assert
def test_fetch_player_gamelog_empty_df(mock_process_df, mock_gamelog, mock_find_player):
    """Test scenario where API returns an empty DataFrame."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.get_data_frames.return_value = [pd.DataFrame()] # Empty DF
    mock_gamelog.return_value = mock_endpoint_instance

    # Act
    result_str = player_tools.fetch_player_gamelog_logic(MOCK_PLAYER_NAME, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_gamelog.assert_called_once()
    mock_process_df.assert_not_called() # Should not be called if DF is empty
    assert "error" not in result
    assert "gamelog" in result
    assert result["gamelog"] == [] # Expect empty list
# Mock data for career stats tests
MOCK_CAREER_SEASON_TOTALS_DATA = [
    {'SEASON_ID': '2022-23', 'TEAM_ABBREVIATION': 'LAL', 'PLAYER_AGE': 38.0, 'GP': 55, 'GS': 54, 'MIN': 1953.0, 'FGM': 573, 'FGA': 1145, 'FG_PCT': 0.5, 'FG3M': 121, 'FG3A': 377, 'FG3_PCT': 0.321, 'FTM': 296, 'FTA': 386, 'FT_PCT': 0.767, 'OREB': 58, 'DREB': 398, 'REB': 456, 'AST': 375, 'STL': 50, 'BLK': 32, 'TOV': 178, 'PF': 93, 'PTS': 1590},
    {'SEASON_ID': '2023-24', 'TEAM_ABBREVIATION': 'LAL', 'PLAYER_AGE': 39.0, 'GP': 71, 'GS': 71, 'MIN': 2504.0, 'FGM': 670, 'FGA': 1245, 'FG_PCT': 0.538, 'FG3M': 148, 'FG3A': 361, 'FG3_PCT': 0.41, 'FTM': 310, 'FTA': 428, 'FT_PCT': 0.724, 'OREB': 75, 'DREB': 445, 'REB': 520, 'AST': 589, 'STL': 89, 'BLK': 37, 'TOV': 241, 'PF': 78, 'PTS': 1798}
]
MOCK_CAREER_TOTALS_DATA = {
    'PLAYER_ID': MOCK_PLAYER_ID, 'LEAGUE_ID': '00', 'Team_ID': 0, 'GP': 1492, 'GS': 1490, 'MIN': 56417.0, 'FGM': 14843, 'FGA': 29379, 'FG_PCT': 0.505, 'FG3M': 2419, 'FG3A': 6941, 'FG3_PCT': 0.348, 'FTM': 8327, 'FTA': 11349, 'FT_PCT': 0.734, 'OREB': 1664, 'DREB': 9678, 'REB': 11342, 'AST': 11009, 'STL': 2275, 'BLK': 1110, 'TOV': 5000, 'PF': 2698, 'PTS': 40474
}
mock_career_season_totals_df = pd.DataFrame(MOCK_CAREER_SEASON_TOTALS_DATA)
mock_career_totals_df = pd.DataFrame([MOCK_CAREER_TOTALS_DATA]) # Needs to be a list for DataFrame constructor

# --- Tests for fetch_player_career_stats_logic ---

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.playercareerstats.PlayerCareerStats')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_career_stats_success(mock_process_df, mock_career_stats, mock_find_player):
    """Test successful fetching of player career stats."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.season_totals_regular_season.get_data_frame.return_value = mock_career_season_totals_df
    mock_endpoint_instance.career_totals_regular_season.get_data_frame.return_value = mock_career_totals_df
    mock_career_stats.return_value = mock_endpoint_instance

    # Mock _process_dataframe return values
    mock_process_df.side_effect = [
        MOCK_CAREER_SEASON_TOTALS_DATA, # First call for season_totals
        MOCK_CAREER_TOTALS_DATA         # Second call for career_totals
    ]

    # Act
    result_str = player_tools.fetch_player_career_stats_logic(MOCK_PLAYER_NAME)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_career_stats.assert_called_once_with(
        player_id=MOCK_PLAYER_ID, 
        per_mode_detailed=PerModeDetailed.per_game, # Default per_mode
        timeout=player_tools.DEFAULT_TIMEOUT
    )
    assert mock_process_df.call_count == 2
    assert "error" not in result
    assert result.get("player_name") == MOCK_PLAYER_NAME
    assert result.get("player_id") == MOCK_PLAYER_ID
    assert "season_totals_regular_season" in result
    assert "career_totals_regular_season" in result
    assert result["season_totals_regular_season"] == MOCK_CAREER_SEASON_TOTALS_DATA
    assert result["career_totals_regular_season"] == MOCK_CAREER_TOTALS_DATA

@patch('backend.api_tools.player_tools.find_player_id_or_error')
def test_fetch_player_career_stats_player_not_found(mock_find_player):
    """Test player not found scenario for career stats."""
    # Arrange
    player_name = "Unknown Player"
    mock_find_player.side_effect = PlayerNotFoundError(player_name)
    expected_error = Errors.PLAYER_NOT_FOUND.format(name=player_name)

    # Act
    result_str = player_tools.fetch_player_career_stats_logic(player_name)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(player_name)
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.playercareerstats.PlayerCareerStats')
def test_fetch_player_career_stats_api_error(mock_career_stats, mock_find_player):
    """Test scenario where the career stats API call fails."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    api_error_message = "NBA API timeout"
    mock_career_stats.side_effect = Exception(api_error_message)
    expected_error = Errors.PLAYER_CAREER_STATS_API.format(name=MOCK_PLAYER_NAME, error=api_error_message)

    # Act
    result_str = player_tools.fetch_player_career_stats_logic(MOCK_PLAYER_NAME)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_career_stats.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.playercareerstats.PlayerCareerStats')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_career_stats_processing_error(mock_process_df, mock_career_stats, mock_find_player):
    """Test scenario where career stats DataFrame processing fails."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.season_totals_regular_season.get_data_frame.return_value = mock_career_season_totals_df
    mock_endpoint_instance.career_totals_regular_season.get_data_frame.return_value = mock_career_totals_df
    mock_career_stats.return_value = mock_endpoint_instance

    mock_process_df.return_value = None # Simulate processing error
    expected_error = Errors.PLAYER_CAREER_STATS_PROCESSING.format(name=MOCK_PLAYER_NAME)

    # Act
    result_str = player_tools.fetch_player_career_stats_logic(MOCK_PLAYER_NAME)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_career_stats.assert_called_once()
    assert mock_process_df.call_count > 0
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.playercareerstats.PlayerCareerStats')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_career_stats_invalid_per_mode(mock_process_df, mock_career_stats, mock_find_player):
    """Test that an invalid per_mode defaults to PerGame and succeeds."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.season_totals_regular_season.get_data_frame.return_value = mock_career_season_totals_df
    mock_endpoint_instance.career_totals_regular_season.get_data_frame.return_value = mock_career_totals_df
    mock_career_stats.return_value = mock_endpoint_instance

    mock_process_df.side_effect = [ MOCK_CAREER_SEASON_TOTALS_DATA, MOCK_CAREER_TOTALS_DATA ]
    invalid_per_mode = "InvalidMode"

    # Act
    result_str = player_tools.fetch_player_career_stats_logic(MOCK_PLAYER_NAME, per_mode=invalid_per_mode)
    result = json.loads(result_str)

    # Assert
    # Check that the API was called with the *default* PerGame mode
    mock_career_stats.assert_called_once_with(
        player_id=MOCK_PLAYER_ID, 
        per_mode_detailed=PerModeDetailed.per_game, # Should default
        timeout=player_tools.DEFAULT_TIMEOUT
    )
    assert "error" not in result
    assert result.get("per_mode_requested") == invalid_per_mode # Should report the original invalid request
    assert result.get("data_retrieved_mode") == PerModeDetailed.per_game # Should report the default used
    assert result["season_totals_regular_season"] == MOCK_CAREER_SEASON_TOTALS_DATA
    assert result["career_totals_regular_season"] == MOCK_CAREER_TOTALS_DATA
# Mock data for awards tests
MOCK_AWARDS_DATA = [
    {'DESCRIPTION': 'All-NBA', 'ALL_NBA_TEAM_NUMBER': '1st Team', 'SEASON': '2022-23', 'MONTH': None, 'WEEK': None, 'CONFERENCE': None, 'TYPE': 'Award', 'SUBTYPE1': None, 'SUBTYPE2': None, 'SUBTYPE3': None},
    {'DESCRIPTION': 'NBA Player of the Week', 'ALL_NBA_TEAM_NUMBER': None, 'SEASON': '2022-23', 'MONTH': None, 'WEEK': 15, 'CONFERENCE': 'West', 'TYPE': 'Award', 'SUBTYPE1': None, 'SUBTYPE2': None, 'SUBTYPE3': None},
    {'DESCRIPTION': 'NBA All-Star', 'ALL_NBA_TEAM_NUMBER': None, 'SEASON': '2022-23', 'MONTH': None, 'WEEK': None, 'CONFERENCE': 'West', 'TYPE': 'All-Star', 'SUBTYPE1': None, 'SUBTYPE2': None, 'SUBTYPE3': None}
]
mock_awards_df = pd.DataFrame(MOCK_AWARDS_DATA)

# --- Tests for fetch_player_awards_logic ---

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.playerawards.PlayerAwards')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_awards_success(mock_process_df, mock_awards, mock_find_player):
    """Test successful fetching of player awards."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.player_awards.get_data_frame.return_value = mock_awards_df
    mock_awards.return_value = mock_endpoint_instance

    mock_process_df.return_value = MOCK_AWARDS_DATA

    # Act
    result_str = player_tools.fetch_player_awards_logic(MOCK_PLAYER_NAME)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_awards.assert_called_once_with(player_id=MOCK_PLAYER_ID, timeout=player_tools.DEFAULT_TIMEOUT)
    mock_process_df.assert_called_once()
    assert "error" not in result
    assert result.get("player_name") == MOCK_PLAYER_NAME
    assert result.get("player_id") == MOCK_PLAYER_ID
    assert "awards" in result
    assert result["awards"] == MOCK_AWARDS_DATA

@patch('backend.api_tools.player_tools.find_player_id_or_error')
def test_fetch_player_awards_player_not_found(mock_find_player):
    """Test player not found scenario for awards."""
    # Arrange
    player_name = "Unknown Player"
    mock_find_player.side_effect = PlayerNotFoundError(player_name)
    expected_error = Errors.PLAYER_NOT_FOUND.format(name=player_name)

    # Act
    result_str = player_tools.fetch_player_awards_logic(player_name)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(player_name)
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.playerawards.PlayerAwards')
def test_fetch_player_awards_api_error(mock_awards, mock_find_player):
    """Test scenario where the awards API call fails."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    api_error_message = "NBA API timeout"
    mock_awards.side_effect = Exception(api_error_message)
    expected_error = Errors.PLAYER_AWARDS_API.format(name=MOCK_PLAYER_NAME, error=api_error_message)

    # Act
    result_str = player_tools.fetch_player_awards_logic(MOCK_PLAYER_NAME)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_awards.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.playerawards.PlayerAwards')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_awards_processing_error(mock_process_df, mock_awards, mock_find_player):
    """Test scenario where awards DataFrame processing fails."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.player_awards.get_data_frame.return_value = mock_awards_df
    mock_awards.return_value = mock_endpoint_instance

    mock_process_df.return_value = None # Simulate processing error
    expected_error = Errors.PLAYER_AWARDS_PROCESSING.format(name=MOCK_PLAYER_NAME)

    # Act
    result_str = player_tools.fetch_player_awards_logic(MOCK_PLAYER_NAME)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_awards.assert_called_once()
    mock_process_df.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.playerawards.PlayerAwards')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_awards_empty_df(mock_process_df, mock_awards, mock_find_player):
    """Test scenario where API returns an empty DataFrame for awards."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.player_awards.get_data_frame.return_value = pd.DataFrame() # Empty DF
    mock_awards.return_value = mock_endpoint_instance

    mock_process_df.return_value = [] # Processing empty DF returns empty list

    # Act
    result_str = player_tools.fetch_player_awards_logic(MOCK_PLAYER_NAME)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_awards.assert_called_once()
    mock_process_df.assert_called_once() 
    assert "error" not in result
    assert "awards" in result
    assert result["awards"] == [] # Expect empty list
# --- Tests for fetch_player_stats_logic (Aggregator) ---

# Mock data for aggregated stats tests
MOCK_INFO_RESULT = json.dumps({
    "player_info": MOCK_COMMON_PLAYER_INFO_DATA,
    "headline_stats": MOCK_HEADLINE_STATS_DATA
})
MOCK_CAREER_RESULT = json.dumps({
    "player_name": MOCK_PLAYER_NAME, "player_id": MOCK_PLAYER_ID,
    "season_totals_regular_season": MOCK_CAREER_SEASON_TOTALS_DATA,
    "career_totals_regular_season": MOCK_CAREER_TOTALS_DATA
})
MOCK_GAMELOG_RESULT = json.dumps({
    "player_name": MOCK_PLAYER_NAME, "player_id": MOCK_PLAYER_ID,
    "season": MOCK_SEASON, "season_type": SeasonTypeAllStar.regular,
    "gamelog": MOCK_GAMELOG_DATA
})
MOCK_AWARDS_RESULT = json.dumps({
    "player_name": MOCK_PLAYER_NAME, "player_id": MOCK_PLAYER_ID,
    "awards": MOCK_AWARDS_DATA
})

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.fetch_player_info_logic')
@patch('backend.api_tools.player_tools.fetch_player_career_stats_logic')
@patch('backend.api_tools.player_tools.fetch_player_gamelog_logic')
@patch('backend.api_tools.player_tools.fetch_player_awards_logic')
def test_fetch_player_stats_success(mock_awards_logic, mock_gamelog_logic, mock_career_logic, mock_info_logic, mock_find_player):
    """Test successful aggregation of player stats."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    mock_info_logic.return_value = MOCK_INFO_RESULT
    mock_career_logic.return_value = MOCK_CAREER_RESULT
    mock_gamelog_logic.return_value = MOCK_GAMELOG_RESULT
    mock_awards_logic.return_value = MOCK_AWARDS_RESULT

    # Act
    result_str = player_tools.fetch_player_stats_logic(MOCK_PLAYER_NAME, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    # Check that sub-functions were called with the *actual* name found
    mock_info_logic.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_career_logic.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_gamelog_logic.assert_called_once_with(MOCK_PLAYER_NAME, MOCK_SEASON, SeasonTypeAllStar.regular)
    mock_awards_logic.assert_called_once_with(MOCK_PLAYER_NAME)

    assert "error" not in result
    assert result.get("player_name") == MOCK_PLAYER_NAME
    assert result.get("player_id") == MOCK_PLAYER_ID
    assert result.get("season_requested") == MOCK_SEASON
    assert "info" in result
    assert "headline_stats" in result
    assert "career_stats" in result
    assert "season_gamelog" in result
    assert "awards" in result
    assert result["info"] == MOCK_COMMON_PLAYER_INFO_DATA
    assert result["headline_stats"] == MOCK_HEADLINE_STATS_DATA
    assert result["career_stats"]["season_totals"] == MOCK_CAREER_SEASON_TOTALS_DATA
    assert result["career_stats"]["career_totals"] == MOCK_CAREER_TOTALS_DATA
    assert result["season_gamelog"] == MOCK_GAMELOG_DATA
    assert result["awards"] == MOCK_AWARDS_DATA

@patch('backend.api_tools.player_tools.find_player_id_or_error')
def test_fetch_player_stats_player_not_found(mock_find_player):
    """Test player not found scenario for aggregated stats."""
    # Arrange
    player_name = "Unknown Player"
    mock_find_player.side_effect = PlayerNotFoundError(player_name)
    expected_error = Errors.PLAYER_NOT_FOUND.format(name=player_name)

    # Act
    result_str = player_tools.fetch_player_stats_logic(player_name, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(player_name)
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_player_stats_invalid_season():
    """Test invalid season format for aggregated stats."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = player_tools.fetch_player_stats_logic(MOCK_PLAYER_NAME, invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.fetch_player_info_logic')
@patch('backend.api_tools.player_tools.fetch_player_career_stats_logic')
@patch('backend.api_tools.player_tools.fetch_player_gamelog_logic')
@patch('backend.api_tools.player_tools.fetch_player_awards_logic')
def test_fetch_player_stats_sub_logic_error(mock_awards_logic, mock_gamelog_logic, mock_career_logic, mock_info_logic, mock_find_player):
    """Test error propagation when a sub-logic function returns an error."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    mock_info_logic.return_value = MOCK_INFO_RESULT
    mock_career_logic.return_value = MOCK_CAREER_RESULT
    # Simulate gamelog logic returning an error
    gamelog_error_msg = "API error during gamelog fetch"
    mock_gamelog_logic.return_value = json.dumps({"error": gamelog_error_msg}) 
    mock_awards_logic.return_value = MOCK_AWARDS_RESULT

    # Act
    result_str = player_tools.fetch_player_stats_logic(MOCK_PLAYER_NAME, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_info_logic.assert_called_once()
    mock_career_logic.assert_called_once()
    mock_gamelog_logic.assert_called_once() 
    mock_awards_logic.assert_not_called() # Should stop after first error

    assert "error" in result
    assert result["error"] == gamelog_error_msg # Ensure the specific error is propagated

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.fetch_player_info_logic')
def test_fetch_player_stats_sub_logic_json_error(mock_info_logic, mock_find_player):
    """Test error handling when a sub-logic function returns invalid JSON."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    mock_info_logic.return_value = "This is not JSON" # Invalid JSON
    expected_error = "Failed to process internal info results."

    # Act
    result_str = player_tools.fetch_player_stats_logic(MOCK_PLAYER_NAME, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_info_logic.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error
# Mock data for shotchart tests
MOCK_SHOT_DATA = [
    {'LOC_X': 10, 'LOC_Y': 50, 'SHOT_MADE_FLAG': 1, 'SHOT_ZONE_BASIC': 'Mid-Range', 'SHOT_DISTANCE': 15},
    {'LOC_X': -240, 'LOC_Y': 70, 'SHOT_MADE_FLAG': 0, 'SHOT_ZONE_BASIC': 'Left Corner 3', 'SHOT_DISTANCE': 24},
    {'LOC_X': 0, 'LOC_Y': 10, 'SHOT_MADE_FLAG': 1, 'SHOT_ZONE_BASIC': 'Restricted Area', 'SHOT_DISTANCE': 1},
]
MOCK_LEAGUE_AVG_DATA = [
    {'SHOT_ZONE_BASIC': 'Mid-Range', 'FGA': 1000, 'FGM': 450, 'FG_PCT': 0.450},
    {'SHOT_ZONE_BASIC': 'Left Corner 3', 'FGA': 800, 'FGM': 300, 'FG_PCT': 0.375},
    {'SHOT_ZONE_BASIC': 'Restricted Area', 'FGA': 2000, 'FGM': 1300, 'FG_PCT': 0.650},
]
mock_shots_df = pd.DataFrame(MOCK_SHOT_DATA)
mock_league_avg_df = pd.DataFrame(MOCK_LEAGUE_AVG_DATA)
MOCK_VIZ_PATH = "/path/to/output/shotchart_LeBron_James_2023-24.png"

# --- Tests for fetch_player_shotchart_logic ---

@patch('backend.api_tools.player_tools.os.makedirs')
@patch('backend.api_tools.player_tools.create_shotchart')
@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.shotchartdetail.ShotChartDetail')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_shotchart_success(mock_process_df, mock_shotchart, mock_find_player, mock_create_viz, mock_makedirs):
    """Test successful fetching and processing of shotchart data."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.get_data_frames.return_value = [mock_shots_df, mock_league_avg_df]
    mock_shotchart.return_value = mock_endpoint_instance

    mock_process_df.side_effect = [MOCK_SHOT_DATA, MOCK_LEAGUE_AVG_DATA]
    mock_create_viz.return_value = MOCK_VIZ_PATH

    # Act
    result_str = player_tools.fetch_player_shotchart_logic(MOCK_PLAYER_NAME, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_shotchart.assert_called_once()
    assert mock_process_df.call_count == 2
    mock_makedirs.assert_called_once() # Check if directory creation was attempted
    mock_create_viz.assert_called_once() # Check if viz creation was attempted
    
    assert "error" not in result
    assert result.get("player_name") == MOCK_PLAYER_NAME
    assert result.get("season") == MOCK_SEASON
    assert "overall_stats" in result
    assert "zone_breakdown" in result
    assert result.get("visualization_path") == MOCK_VIZ_PATH
    assert result.get("visualization_error") is None
    # Check zone summary calculation (basic check)
    assert "Mid-Range" in result["zone_breakdown"]
    assert result["zone_breakdown"]["Mid-Range"]["attempts"] == 1
    assert result["zone_breakdown"]["Mid-Range"]["made"] == 1
    assert result["zone_breakdown"]["Mid-Range"]["percentage"] == 100.0

@patch('backend.api_tools.player_tools.os.makedirs')
@patch('backend.api_tools.player_tools.create_shotchart')
@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.shotchartdetail.ShotChartDetail')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_shotchart_viz_error(mock_process_df, mock_shotchart, mock_find_player, mock_create_viz, mock_makedirs):
    """Test shotchart data fetch success but visualization error."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.get_data_frames.return_value = [mock_shots_df, mock_league_avg_df]
    mock_shotchart.return_value = mock_endpoint_instance
    mock_process_df.side_effect = [MOCK_SHOT_DATA, MOCK_LEAGUE_AVG_DATA]
    viz_error_msg = "Matplotlib error"
    mock_create_viz.side_effect = Exception(viz_error_msg)

    # Act
    result_str = player_tools.fetch_player_shotchart_logic(MOCK_PLAYER_NAME, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert "error" not in result # Function itself doesn't error, includes viz error in response
    assert result.get("visualization_path") is None
    assert result.get("visualization_error") == viz_error_msg

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.shotchartdetail.ShotChartDetail')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_shotchart_no_data(mock_process_df, mock_shotchart, mock_find_player):
    """Test scenario where API returns no shot data."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.get_data_frames.return_value = [pd.DataFrame(), mock_league_avg_df] # Empty shots DF
    mock_shotchart.return_value = mock_endpoint_instance
    mock_process_df.side_effect = [[], MOCK_LEAGUE_AVG_DATA] # Processing empty DF returns empty list

    # Act
    result_str = player_tools.fetch_player_shotchart_logic(MOCK_PLAYER_NAME, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert "error" not in result
    assert "message" in result
    assert result["message"] == "No shot data found for the specified criteria."
    assert result["overall_stats"]["total_shots"] == 0

@patch('backend.api_tools.player_tools.find_player_id_or_error')
def test_fetch_player_shotchart_player_not_found(mock_find_player):
    """Test player not found scenario for shotchart."""
    # Arrange
    player_name = "Unknown Player"
    mock_find_player.side_effect = PlayerNotFoundError(player_name)
    expected_error = Errors.PLAYER_NOT_FOUND.format(name=player_name)

    # Act
    result_str = player_tools.fetch_player_shotchart_logic(player_name, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_player_shotchart_invalid_season():
    """Test invalid season format for shotchart."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = player_tools.fetch_player_shotchart_logic(MOCK_PLAYER_NAME, invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.shotchartdetail.ShotChartDetail')
def test_fetch_player_shotchart_api_error(mock_shotchart, mock_find_player):
    """Test scenario where the shotchart API call fails."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    api_error_message = "NBA API timeout"
    mock_shotchart.side_effect = Exception(api_error_message)
    expected_error = Errors.PLAYER_SHOTCHART_API.format(name=MOCK_PLAYER_NAME, season=MOCK_SEASON, error=api_error_message)

    # Act
    result_str = player_tools.fetch_player_shotchart_logic(MOCK_PLAYER_NAME, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.shotchartdetail.ShotChartDetail')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_shotchart_processing_error(mock_process_df, mock_shotchart, mock_find_player):
    """Test scenario where shotchart DataFrame processing fails."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.get_data_frames.return_value = [mock_shots_df, mock_league_avg_df]
    mock_shotchart.return_value = mock_endpoint_instance
    mock_process_df.return_value = None # Simulate processing error
    expected_error = Errors.PLAYER_SHOTCHART_PROCESSING.format(name=MOCK_PLAYER_NAME)

    # Act
    result_str = player_tools.fetch_player_shotchart_logic(MOCK_PLAYER_NAME, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error
# Mock data for defense tests
MOCK_DEFENSE_DATA = [
    {'DEFENSE_CATEGORY': 'Overall', 'GP': 70, 'FREQ': 1.0, 'D_FG_PCT': 0.450, 'NORMAL_FG_PCT': 0.470, 'PCT_PLUSMINUS': -0.020},
    {'DEFENSE_CATEGORY': '3 Pointers', 'GP': 70, 'FREQ': 0.4, 'D_FG_PCT': 0.350, 'NORMAL_FG_PCT': 0.360, 'PCT_PLUSMINUS': -0.010},
    {'DEFENSE_CATEGORY': '2 Pointers', 'GP': 70, 'FREQ': 0.6, 'D_FG_PCT': 0.500, 'NORMAL_FG_PCT': 0.520, 'PCT_PLUSMINUS': -0.020},
    {'DEFENSE_CATEGORY': 'Less Than 6Ft', 'GP': 70, 'FREQ': 0.3, 'D_FG_PCT': 0.600, 'NORMAL_FG_PCT': 0.620, 'PCT_PLUSMINUS': -0.020},
    {'DEFENSE_CATEGORY': 'Greater Than 15Ft', 'GP': 70, 'FREQ': 0.2, 'D_FG_PCT': 0.400, 'NORMAL_FG_PCT': 0.410, 'PCT_PLUSMINUS': -0.010},
]
mock_defense_df = pd.DataFrame(MOCK_DEFENSE_DATA)

# --- Tests for fetch_player_defense_logic ---

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.playerdashptshotdefend.PlayerDashPtShotDefend')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_defense_success(mock_process_df, mock_defense_endpoint, mock_find_player):
    """Test successful fetching of player defense stats."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.get_data_frames.return_value = [mock_defense_df]
    mock_defense_endpoint.return_value = mock_endpoint_instance

    mock_process_df.return_value = MOCK_DEFENSE_DATA

    # Act
    result_str = player_tools.fetch_player_defense_logic(MOCK_PLAYER_NAME, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_defense_endpoint.assert_called_once()
    mock_process_df.assert_called_once()
    assert "error" not in result
    assert result.get("player_name") == MOCK_PLAYER_NAME
    assert "parameters" in result
    assert "summary" in result
    assert "overall_defense" in result["summary"]
    assert "three_point_defense" in result["summary"]
    assert result["summary"]["overall_defense"]["field_goal_percentage_allowed"] == 0.450

@patch('backend.api_tools.player_tools.find_player_id_or_error')
def test_fetch_player_defense_player_not_found(mock_find_player):
    """Test player not found scenario for defense stats."""
    # Arrange
    player_name = "Unknown Player"
    mock_find_player.side_effect = PlayerNotFoundError(player_name)
    expected_error = Errors.PLAYER_NOT_FOUND.format(name=player_name)

    # Act
    result_str = player_tools.fetch_player_defense_logic(player_name, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_player_defense_invalid_season():
    """Test invalid season format for defense stats."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = player_tools.fetch_player_defense_logic(MOCK_PLAYER_NAME, invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_player_defense_invalid_date():
    """Test invalid date format for defense stats."""
    # Arrange
    invalid_date = "10-25-2023"
    expected_error = Errors.INVALID_DATE_FORMAT.format(date=invalid_date) # Use the constant from config.py

    # Act
    result_str = player_tools.fetch_player_defense_logic(MOCK_PLAYER_NAME, MOCK_SEASON, date_from=invalid_date)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.playerdashptshotdefend.PlayerDashPtShotDefend')
def test_fetch_player_defense_api_error(mock_defense_endpoint, mock_find_player):
    """Test scenario where the defense API call fails."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    api_error_message = "NBA API timeout"
    mock_defense_endpoint.side_effect = Exception(api_error_message)
    expected_error = Errors.PLAYER_DEFENSE_API.format(name=MOCK_PLAYER_NAME, error=api_error_message)

    # Act
    result_str = player_tools.fetch_player_defense_logic(MOCK_PLAYER_NAME, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.playerdashptshotdefend.PlayerDashPtShotDefend')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_defense_processing_error(mock_process_df, mock_defense_endpoint, mock_find_player):
    """Test scenario where defense DataFrame processing fails."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.get_data_frames.return_value = [mock_defense_df]
    mock_defense_endpoint.return_value = mock_endpoint_instance
    mock_process_df.return_value = None # Simulate processing error
    expected_error = Errors.PLAYER_DEFENSE_PROCESSING.format(name=MOCK_PLAYER_NAME)

    # Act
    result_str = player_tools.fetch_player_defense_logic(MOCK_PLAYER_NAME, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.playerdashptshotdefend.PlayerDashPtShotDefend')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_defense_no_data(mock_process_df, mock_defense_endpoint, mock_find_player):
    """Test scenario where API returns no defense data."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.get_data_frames.return_value = [pd.DataFrame()] # Empty DF
    mock_defense_endpoint.return_value = mock_endpoint_instance
    mock_process_df.return_value = [] # Processing empty DF returns empty list

    # Act
    result_str = player_tools.fetch_player_defense_logic(MOCK_PLAYER_NAME, MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    assert "error" not in result
    assert "message" in result
    assert result["message"] == "No defense stats found for the specified criteria."
    assert result["summary"] == {}
# Mock data for hustle stats tests
MOCK_HUSTLE_DATA = [
    {'PLAYER_ID': MOCK_PLAYER_ID, 'PLAYER_NAME': MOCK_PLAYER_NAME, 'TEAM_ABBREVIATION': 'LAL', 'G': 70, 'MIN': 35.0, 'CHARGES_DRAWN': 0.1, 'CONTESTED_SHOTS': 5.0, 'CONTESTED_SHOTS_3PT': 2.0, 'CONTESTED_SHOTS_2PT': 3.0, 'DEFLECTIONS': 2.5, 'LOOSE_BALLS_RECOVERED': 1.0, 'LOOSE_BALLS_RECOVERED_OFF': 0.3, 'LOOSE_BALLS_RECOVERED_DEF': 0.7, 'SCREEN_ASSISTS': 1.5, 'SCREEN_AST_PTS': 3.5, 'BOX_OUTS': 4.0, 'BOX_OUTS_OFF': 0.5, 'BOX_OUTS_DEF': 3.5},
    {'PLAYER_ID': 201939, 'PLAYER_NAME': 'Stephen Curry', 'TEAM_ABBREVIATION': 'GSW', 'G': 65, 'MIN': 34.0, 'CHARGES_DRAWN': 0.0, 'CONTESTED_SHOTS': 3.0, 'CONTESTED_SHOTS_3PT': 1.5, 'CONTESTED_SHOTS_2PT': 1.5, 'DEFLECTIONS': 1.8, 'LOOSE_BALLS_RECOVERED': 0.8, 'LOOSE_BALLS_RECOVERED_OFF': 0.2, 'LOOSE_BALLS_RECOVERED_DEF': 0.6, 'SCREEN_ASSISTS': 0.5, 'SCREEN_AST_PTS': 1.2, 'BOX_OUTS': 1.0, 'BOX_OUTS_OFF': 0.1, 'BOX_OUTS_DEF': 0.9},
]
mock_hustle_df = pd.DataFrame(MOCK_HUSTLE_DATA)

# --- Tests for fetch_player_hustle_stats_logic ---

@patch('backend.api_tools.player_tools.find_player_id_or_error') # Mock even if not always called
@patch('backend.api_tools.player_tools.leaguehustlestatsplayer.LeagueHustleStatsPlayer')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_hustle_stats_success_player(mock_process_df, mock_hustle_endpoint, mock_find_player):
    """Test successful fetching of hustle stats for a specific player."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    
    mock_endpoint_instance = MagicMock()
    # Simulate API returning data for multiple players initially
    mock_endpoint_instance.get_data_frames.return_value = [mock_hustle_df] 
    mock_hustle_endpoint.return_value = mock_endpoint_instance

    # Simulate processing the filtered DataFrame (only LeBron's data)
    filtered_data = [MOCK_HUSTLE_DATA[0]]
    mock_process_df.return_value = filtered_data 

    # Act
    result_str = player_tools.fetch_player_hustle_stats_logic(season=MOCK_SEASON, player_name=MOCK_PLAYER_NAME)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_hustle_endpoint.assert_called_once()
    mock_process_df.assert_called_once() 
    assert "error" not in result
    assert "parameters" in result
    assert result["parameters"]["player_name"] == MOCK_PLAYER_NAME
    assert "hustle_stats" in result
    assert len(result["hustle_stats"]) == 1
    assert result["hustle_stats"][0]["PLAYER_ID"] == MOCK_PLAYER_ID # Corrected key access

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.leaguehustlestatsplayer.LeagueHustleStatsPlayer')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_hustle_stats_success_league(mock_process_df, mock_hustle_endpoint, mock_find_player):
    """Test successful fetching of league-wide hustle stats."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.get_data_frames.return_value = [mock_hustle_df] 
    mock_hustle_endpoint.return_value = mock_endpoint_instance
    mock_process_df.return_value = MOCK_HUSTLE_DATA # Processed full data

    # Act
    result_str = player_tools.fetch_player_hustle_stats_logic(season=MOCK_SEASON) # No player or team
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_not_called() # Should not be called
    mock_hustle_endpoint.assert_called_once()
    mock_process_df.assert_called_once()
    assert "error" not in result
    assert result["parameters"]["player_name"] is None
    assert result["parameters"]["team_id"] is None
    assert "hustle_stats" in result
    assert len(result["hustle_stats"]) == len(MOCK_HUSTLE_DATA) # Assuming limit wasn't hit

@patch('backend.api_tools.player_tools.find_player_id_or_error')
def test_fetch_player_hustle_stats_player_not_found(mock_find_player):
    """Test player not found scenario for hustle stats."""
    # Arrange
    player_name = "Unknown Player"
    mock_find_player.side_effect = PlayerNotFoundError(player_name)
    expected_error = Errors.PLAYER_NOT_FOUND.format(name=player_name)

    # Act
    result_str = player_tools.fetch_player_hustle_stats_logic(season=MOCK_SEASON, player_name=player_name)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(player_name)
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_player_hustle_stats_invalid_season():
    """Test invalid season format for hustle stats."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = player_tools.fetch_player_hustle_stats_logic(season=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.leaguehustlestatsplayer.LeagueHustleStatsPlayer')
def test_fetch_player_hustle_stats_api_error(mock_hustle_endpoint):
    """Test scenario where the hustle stats API call fails."""
    # Arrange
    api_error_message = "NBA API timeout"
    mock_hustle_endpoint.side_effect = Exception(api_error_message)
    expected_error = Errors.PLAYER_HUSTLE_API.format(error=api_error_message)

    # Act
    result_str = player_tools.fetch_player_hustle_stats_logic(season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_hustle_endpoint.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.leaguehustlestatsplayer.LeagueHustleStatsPlayer')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_hustle_stats_processing_error(mock_process_df, mock_hustle_endpoint):
    """Test scenario where hustle stats DataFrame processing fails."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.get_data_frames.return_value = [mock_hustle_df] 
    mock_hustle_endpoint.return_value = mock_endpoint_instance
    mock_process_df.return_value = None # Simulate processing error
    expected_error = Errors.PLAYER_HUSTLE_PROCESSING.format()

    # Act
    result_str = player_tools.fetch_player_hustle_stats_logic(season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_hustle_endpoint.assert_called_once()
    mock_process_df.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.leaguehustlestatsplayer.LeagueHustleStatsPlayer')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_hustle_stats_empty_df(mock_process_df, mock_hustle_endpoint):
    """Test scenario where API returns an empty DataFrame for hustle stats."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.get_data_frames.return_value = [pd.DataFrame()] # Empty DF
    mock_hustle_endpoint.return_value = mock_endpoint_instance

    # Act
    result_str = player_tools.fetch_player_hustle_stats_logic(season=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_hustle_endpoint.assert_called_once()
    mock_process_df.assert_not_called() # Should not be called if DF is empty
    assert "error" not in result
    assert "hustle_stats" in result
    assert result["hustle_stats"] == [] # Expect empty list
    assert "message" in result
# Mock data for profile tests
# Re-use MOCK_COMMON_PLAYER_INFO_DATA and mock_common_player_info_df
MOCK_PROFILE_CAREER_TOTALS_DATA = {'PLAYER_ID': MOCK_PLAYER_ID, 'GP': 1492, 'PTS': 27.1} # Simplified
MOCK_PROFILE_SEASON_TOTALS_DATA = [{'SEASON_ID': '2023-24', 'GP': 71, 'PTS': 25.3}] # Simplified
MOCK_PROFILE_SEASON_HIGHS_DATA = {'PLAYER_ID': MOCK_PLAYER_ID, 'SEASON_ID': '2023-24', 'PTS': 50} # Simplified
MOCK_PROFILE_CAREER_HIGHS_DATA = {'PLAYER_ID': MOCK_PLAYER_ID, 'PTS': 61} # Simplified
MOCK_PROFILE_NEXT_GAME_DATA = {'GAME_ID': '0022400001', 'GAME_DATE': '2024-10-22', 'HOME_TEAM_ABBREVIATION': 'LAL', 'VISITOR_TEAM_ABBREVIATION': 'DEN'} # Simplified

mock_profile_career_totals_df = pd.DataFrame([MOCK_PROFILE_CAREER_TOTALS_DATA])
mock_profile_season_totals_df = pd.DataFrame(MOCK_PROFILE_SEASON_TOTALS_DATA)
mock_profile_season_highs_df = pd.DataFrame([MOCK_PROFILE_SEASON_HIGHS_DATA])
mock_profile_career_highs_df = pd.DataFrame([MOCK_PROFILE_CAREER_HIGHS_DATA])
mock_profile_next_game_df = pd.DataFrame([MOCK_PROFILE_NEXT_GAME_DATA])

# --- Tests for fetch_player_profile_logic ---

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.commonplayerinfo.CommonPlayerInfo')
@patch('backend.api_tools.player_tools.playerprofilev2.PlayerProfileV2')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_profile_success(mock_process_df, mock_profile_endpoint, mock_info_endpoint, mock_find_player):
    """Test successful fetching of player profile data."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)

    # Mock CommonPlayerInfo
    mock_info_instance = MagicMock()
    mock_info_instance.common_player_info.get_data_frame.return_value = mock_common_player_info_df
    mock_info_endpoint.return_value = mock_info_instance

    # Mock PlayerProfileV2
    mock_profile_instance = MagicMock()
    mock_profile_instance.career_totals_regular_season.get_data_frame.return_value = mock_profile_career_totals_df
    mock_profile_instance.season_totals_regular_season.get_data_frame.return_value = mock_profile_season_totals_df
    mock_profile_instance.season_highs.get_data_frame.return_value = mock_profile_season_highs_df
    mock_profile_instance.career_highs.get_data_frame.return_value = mock_profile_career_highs_df
    mock_profile_instance.next_game.get_data_frame.return_value = mock_profile_next_game_df
    mock_profile_endpoint.return_value = mock_profile_instance

    # Mock _process_dataframe calls
    mock_process_df.side_effect = [
        MOCK_COMMON_PLAYER_INFO_DATA, # For commonplayerinfo call
        MOCK_PROFILE_CAREER_TOTALS_DATA,
        MOCK_PROFILE_SEASON_TOTALS_DATA,
        MOCK_PROFILE_SEASON_HIGHS_DATA,
        MOCK_PROFILE_CAREER_HIGHS_DATA,
        MOCK_PROFILE_NEXT_GAME_DATA
    ]

    # Act
    result_str = player_tools.fetch_player_profile_logic(MOCK_PLAYER_NAME)
    result = json.loads(result_str)

    # Assert
    mock_find_player.assert_called_once_with(MOCK_PLAYER_NAME)
    mock_info_endpoint.assert_called_once_with(player_id=MOCK_PLAYER_ID, timeout=player_tools.DEFAULT_TIMEOUT)
    mock_profile_endpoint.assert_called_once_with(player_id=MOCK_PLAYER_ID, per_mode36=PerModeDetailed.per_game, timeout=player_tools.DEFAULT_TIMEOUT)
    assert mock_process_df.call_count == 6 # 1 for info + 5 for profile parts
    assert "error" not in result
    assert result.get("player_name") == MOCK_PLAYER_NAME
    assert "player_info" in result
    assert "career_highs" in result
    assert "season_highs" in result
    assert "next_game" in result
    assert "career_totals" in result
    assert "season_totals" in result
    assert result["player_info"] == MOCK_COMMON_PLAYER_INFO_DATA
    assert result["career_highs"] == MOCK_PROFILE_CAREER_HIGHS_DATA

@patch('backend.api_tools.player_tools.find_player_id_or_error')
def test_fetch_player_profile_player_not_found(mock_find_player):
    """Test player not found scenario for profile."""
    # Arrange
    player_name = "Unknown Player"
    mock_find_player.side_effect = PlayerNotFoundError(player_name)
    expected_error = Errors.PLAYER_NOT_FOUND.format(name=player_name)

    # Act
    result_str = player_tools.fetch_player_profile_logic(player_name)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.commonplayerinfo.CommonPlayerInfo')
@patch('backend.api_tools.player_tools.playerprofilev2.PlayerProfileV2')
def test_fetch_player_profile_api_error(mock_profile_endpoint, mock_info_endpoint, mock_find_player):
    """Test scenario where one of the profile API calls fails."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    # Mock CommonPlayerInfo success
    mock_info_instance = MagicMock()
    mock_info_instance.common_player_info.get_data_frame.return_value = mock_common_player_info_df
    mock_info_endpoint.return_value = mock_info_instance
    # Mock PlayerProfileV2 failure
    api_error_message = "NBA API timeout on profile"
    mock_profile_endpoint.side_effect = Exception(api_error_message)
    expected_error = Errors.PLAYER_PROFILE_API.format(name=MOCK_PLAYER_NAME, error=api_error_message)

    # Act
    result_str = player_tools.fetch_player_profile_logic(MOCK_PLAYER_NAME)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.player_tools.find_player_id_or_error')
@patch('backend.api_tools.player_tools.commonplayerinfo.CommonPlayerInfo')
@patch('backend.api_tools.player_tools.playerprofilev2.PlayerProfileV2')
@patch('backend.api_tools.player_tools._process_dataframe')
def test_fetch_player_profile_processing_error(mock_process_df, mock_profile_endpoint, mock_info_endpoint, mock_find_player):
    """Test scenario where essential profile DataFrame processing fails."""
    # Arrange
    mock_find_player.return_value = (MOCK_PLAYER_ID, MOCK_PLAYER_NAME)
    # Mock API calls success
    mock_info_instance = MagicMock()
    mock_info_instance.common_player_info.get_data_frame.return_value = mock_common_player_info_df
    mock_info_endpoint.return_value = mock_info_instance
    mock_profile_instance = MagicMock()
    mock_profile_instance.career_totals_regular_season.get_data_frame.return_value = mock_profile_career_totals_df
    mock_profile_instance.season_totals_regular_season.get_data_frame.return_value = mock_profile_season_totals_df
    # ... mock other profile DFs ...
    mock_profile_endpoint.return_value = mock_profile_instance

    # Simulate processing failure for an essential part (e.g., career totals)
    mock_process_df.side_effect = [
        MOCK_COMMON_PLAYER_INFO_DATA, 
        None, # Simulate career_totals processing failure
        MOCK_PROFILE_SEASON_TOTALS_DATA, 
        MOCK_PROFILE_SEASON_HIGHS_DATA, 
        MOCK_PROFILE_CAREER_HIGHS_DATA, 
        MOCK_PROFILE_NEXT_GAME_DATA
    ]
    expected_error = Errors.PLAYER_PROFILE_PROCESSING.format(name=MOCK_PLAYER_NAME)

    # Act
    result_str = player_tools.fetch_player_profile_logic(MOCK_PLAYER_NAME)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error
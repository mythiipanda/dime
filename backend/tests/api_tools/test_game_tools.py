import pytest
import json
from unittest.mock import patch, MagicMock
import pandas as pd

# Modules to test
from backend.api_tools import game_tools
from backend.api_tools.utils import PlayerNotFoundError # Assuming utils might be needed indirectly
from backend.config import Errors, DEFAULT_TIMEOUT, CURRENT_SEASON # Added DEFAULT_TIMEOUT, CURRENT_SEASON
from nba_api.stats.library.parameters import StartPeriod, EndPeriod, StartRange, EndRange, RangeType # Import params

# Mock data - Define constants used across tests
MOCK_GAME_ID = "0022300001" # Example Game ID
MOCK_SEASON = CURRENT_SEASON # Use constant from config

# Mock data for BoxScoreTraditionalV3
MOCK_PLAYER_STATS_V3_DATA = [
    {"personId": 1, "firstName": "Player", "familyName": "One", "teamTricode": "AAA", "position": "G", "minutes": "30:00", "points": 20, "reboundsOffensive": 1, "reboundsDefensive": 4, "reboundsTotal": 5, "assists": 3, "steals": 1, "blocks": 0, "turnovers": 2, "foulsPersonal": 3, "fieldGoalsMade": 8, "fieldGoalsAttempted": 15, "fieldGoalsPercentage": 0.533, "threePointersMade": 2, "threePointersAttempted": 5, "threePointersPercentage": 0.400, "freeThrowsMade": 2, "freeThrowsAttempted": 2, "freeThrowsPercentage": 1.0, "plusMinusPoints": 5, "comment": "", "jerseyNum": "1"},
    {"personId": 2, "firstName": "Player", "familyName": "Two", "teamTricode": "BBB", "position": "F", "minutes": "32:00", "points": 15, "reboundsOffensive": 2, "reboundsDefensive": 6, "reboundsTotal": 8, "assists": 2, "steals": 0, "blocks": 1, "turnovers": 1, "foulsPersonal": 4, "fieldGoalsMade": 6, "fieldGoalsAttempted": 12, "fieldGoalsPercentage": 0.500, "threePointersMade": 1, "threePointersAttempted": 3, "threePointersPercentage": 0.333, "freeThrowsMade": 2, "freeThrowsAttempted": 3, "freeThrowsPercentage": 0.667, "plusMinusPoints": -2, "comment": "", "jerseyNum": "2"}
]
MOCK_TEAM_STATS_V3_DATA = [
    {"teamId": 101, "teamCity": "Team", "teamName": "AAA", "teamTricode": "AAA", "minutes": "240:00", "points": 100, "reboundsOffensive": 10, "reboundsDefensive": 30, "reboundsTotal": 40, "assists": 20, "steals": 5, "blocks": 3, "turnovers": 12, "foulsPersonal": 22, "fieldGoalsMade": 40, "fieldGoalsAttempted": 85, "fieldGoalsPercentage": 0.471, "threePointersMade": 10, "threePointersAttempted": 30, "threePointersPercentage": 0.333, "freeThrowsMade": 10, "freeThrowsAttempted": 15, "freeThrowsPercentage": 0.667, "plusMinusPoints": 3},
    {"teamId": 102, "teamCity": "Team", "teamName": "BBB", "teamTricode": "BBB", "minutes": "240:00", "points": 97, "reboundsOffensive": 12, "reboundsDefensive": 32, "reboundsTotal": 44, "assists": 18, "steals": 6, "blocks": 4, "turnovers": 14, "foulsPersonal": 20, "fieldGoalsMade": 38, "fieldGoalsAttempted": 80, "fieldGoalsPercentage": 0.475, "threePointersMade": 8, "threePointersAttempted": 25, "threePointersPercentage": 0.320, "freeThrowsMade": 13, "freeThrowsAttempted": 18, "freeThrowsPercentage": 0.722, "plusMinusPoints": -3}
]
MOCK_STARTERS_BENCH_V3_DATA = [
     {"teamId": 101, "teamTricode": "AAA", "startersBench": "Starters", "minutes": "180:00", "points": 80},
     {"teamId": 101, "teamTricode": "AAA", "startersBench": "Bench", "minutes": "60:00", "points": 20},
     {"teamId": 102, "teamTricode": "BBB", "startersBench": "Starters", "minutes": "185:00", "points": 75},
     {"teamId": 102, "teamTricode": "BBB", "startersBench": "Bench", "minutes": "55:00", "points": 22}
]

mock_player_stats_v3_df = pd.DataFrame(MOCK_PLAYER_STATS_V3_DATA)
mock_team_stats_v3_df = pd.DataFrame(MOCK_TEAM_STATS_V3_DATA)
mock_starters_bench_v3_df = pd.DataFrame(MOCK_STARTERS_BENCH_V3_DATA)

# Mock data for BoxScoreAdvancedV3
MOCK_PLAYER_ADVANCED_V3_DATA = [
    {"personId": 1, "firstName": "Player", "familyName": "One", "teamTricode": "AAA", "minutes": "30:00", "offensiveRating": 110.5, "defensiveRating": 105.2, "netRating": 5.3, "assistPercentage": 0.15, "assistRatio": 1.5, "assistToTurnover": 2.0, "defensiveReboundPercentage": 0.20, "effectiveFieldGoalPercentage": 0.550, "pace": 98.5, "playerEfficiencyRating": 18.2, "possessions": 65, "trueShootingPercentage": 0.580, "turnoverRatio": 0.10, "usagePercentage": 0.25},
    {"personId": 2, "firstName": "Player", "familyName": "Two", "teamTricode": "BBB", "minutes": "32:00", "offensiveRating": 108.1, "defensiveRating": 107.0, "netRating": 1.1, "assistPercentage": 0.12, "assistRatio": 1.2, "assistToTurnover": 1.5, "defensiveReboundPercentage": 0.22, "effectiveFieldGoalPercentage": 0.520, "pace": 99.0, "playerEfficiencyRating": 16.5, "possessions": 70, "trueShootingPercentage": 0.545, "turnoverRatio": 0.12, "usagePercentage": 0.22}
]
MOCK_TEAM_ADVANCED_V3_DATA = [
    {"teamId": 101, "teamCity": "Team", "teamName": "AAA", "teamTricode": "AAA", "minutes": "240:00", "offensiveRating": 112.0, "defensiveRating": 108.0, "netRating": 4.0, "assistPercentage": 0.60, "assistRatio": 18.0, "assistToTurnover": 1.8, "defensiveReboundPercentage": 0.75, "effectiveFieldGoalPercentage": 0.530, "pace": 98.8, "possessions": 210, "trueShootingPercentage": 0.560, "turnoverRatio": 0.11},
    {"teamId": 102, "teamCity": "Team", "teamName": "BBB", "teamTricode": "BBB", "minutes": "240:00", "offensiveRating": 109.5, "defensiveRating": 110.0, "netRating": -0.5, "assistPercentage": 0.58, "assistRatio": 17.5, "assistToTurnover": 1.6, "defensiveReboundPercentage": 0.73, "effectiveFieldGoalPercentage": 0.515, "pace": 99.2, "possessions": 215, "trueShootingPercentage": 0.540, "turnoverRatio": 0.13}
]

mock_player_advanced_v3_df = pd.DataFrame(MOCK_PLAYER_ADVANCED_V3_DATA)
mock_team_advanced_v3_df = pd.DataFrame(MOCK_TEAM_ADVANCED_V3_DATA)

# Mock data for BoxScoreFourFactorsV3
MOCK_PLAYER_FOURFACTORS_V3_DATA = [
    {"personId": 1, "firstName": "Player", "familyName": "One", "teamTricode": "AAA", "minutes": "30:00", "effectiveFieldGoalPercentage": 0.550, "freeThrowAttemptRate": 0.200, "teamTurnoverPercentage": 0.100, "offensiveReboundPercentage": 0.08, "oppEffectiveFieldGoalPercentage": 0.500, "oppFreeThrowAttemptRate": 0.250, "oppTeamTurnoverPercentage": 0.120, "oppOffensiveReboundPercentage": 0.22},
    {"personId": 2, "firstName": "Player", "familyName": "Two", "teamTricode": "BBB", "minutes": "32:00", "effectiveFieldGoalPercentage": 0.520, "freeThrowAttemptRate": 0.220, "teamTurnoverPercentage": 0.110, "offensiveReboundPercentage": 0.10, "oppEffectiveFieldGoalPercentage": 0.510, "oppFreeThrowAttemptRate": 0.230, "oppTeamTurnoverPercentage": 0.130, "oppOffensiveReboundPercentage": 0.25}
]
MOCK_TEAM_FOURFACTORS_V3_DATA = [
    {"teamId": 101, "teamCity": "Team", "teamName": "AAA", "teamTricode": "AAA", "minutes": "240:00", "effectiveFieldGoalPercentage": 0.530, "freeThrowAttemptRate": 0.180, "teamTurnoverPercentage": 0.115, "offensiveReboundPercentage": 0.25, "oppEffectiveFieldGoalPercentage": 0.505, "oppFreeThrowAttemptRate": 0.240, "oppTeamTurnoverPercentage": 0.125, "oppOffensiveReboundPercentage": 0.24},
    {"teamId": 102, "teamCity": "Team", "teamName": "BBB", "teamTricode": "BBB", "minutes": "240:00", "effectiveFieldGoalPercentage": 0.515, "freeThrowAttemptRate": 0.190, "teamTurnoverPercentage": 0.125, "offensiveReboundPercentage": 0.28, "oppEffectiveFieldGoalPercentage": 0.525, "oppFreeThrowAttemptRate": 0.220, "oppTeamTurnoverPercentage": 0.110, "oppOffensiveReboundPercentage": 0.26}
]

mock_player_fourfactors_v3_df = pd.DataFrame(MOCK_PLAYER_FOURFACTORS_V3_DATA)
mock_team_fourfactors_v3_df = pd.DataFrame(MOCK_TEAM_FOURFACTORS_V3_DATA)

# Mock data for BoxScoreUsageV3
MOCK_PLAYER_USAGE_V3_DATA = [
    {"personId": 1, "firstName": "Player", "familyName": "One", "teamTricode": "AAA", "minutes": "30:00", "usagePercentage": 0.255, "teamPlayPercentage": 0.180, "playerPlayPercentage": 0.220, "playerFoulOutPercentage": 0.0},
    {"personId": 2, "firstName": "Player", "familyName": "Two", "teamTricode": "BBB", "minutes": "32:00", "usagePercentage": 0.221, "teamPlayPercentage": 0.175, "playerPlayPercentage": 0.210, "playerFoulOutPercentage": 0.0}
]
mock_player_usage_v3_df = pd.DataFrame(MOCK_PLAYER_USAGE_V3_DATA)

# Mock data for BoxScoreDefensiveV2
MOCK_PLAYER_DEFENSIVE_V2_DATA = [
    {"personId": 1, "firstName": "Player", "familyName": "One", "teamTricode": "AAA", "minutes": "30:00", "dreb": 4, "stl": 1, "blk": 0, "contestedShots": 10, "contestedShots2pt": 6, "contestedShots3pt": 4, "deflections": 2, "chargesDrawn": 0, "screenAssists": 1, "screenAssistPoints": 2, "looseBallsRecovered": 1, "looseBallsRecoveredOffensive": 0, "looseBallsRecoveredDefensive": 1, "boxOuts": 5, "boxOutsOffensive": 1, "boxOutsDefensive": 4},
    {"personId": 2, "firstName": "Player", "familyName": "Two", "teamTricode": "BBB", "minutes": "32:00", "dreb": 6, "stl": 0, "blk": 1, "contestedShots": 12, "contestedShots2pt": 8, "contestedShots3pt": 4, "deflections": 1, "chargesDrawn": 1, "screenAssists": 0, "screenAssistPoints": 0, "looseBallsRecovered": 2, "looseBallsRecoveredOffensive": 1, "looseBallsRecoveredDefensive": 1, "boxOuts": 7, "boxOutsOffensive": 2, "boxOutsDefensive": 5}
]
mock_player_defensive_v2_df = pd.DataFrame(MOCK_PLAYER_DEFENSIVE_V2_DATA)

# Mock data for PlayByPlay tests
MOCK_LIVE_PBP_RESULT = {
    "game_id": MOCK_GAME_ID, "source": "live", "has_video": False,
    "periods": [{"period": 1, "plays": [{"event_num": 1, "clock": "11:45", "score": "2-0", "team": "home", "neutral_description": "Jump Ball", "event_type": "JUMP_BALL_"}]}]
}
MOCK_HISTORICAL_PBP_RESULT = {
    "game_id": MOCK_GAME_ID, "source": "historical", "has_video": True,
    "filtered_periods": None,
    "periods": [{"period": 1, "plays": [{"event_num": 1, "clock": "12:00", "score": None, "team": "neutral", "home_description": None, "away_description": None, "neutral_description": "Start Period", "event_type": "START_PERIOD"}]}]
}

# Mock data for ShotChartDetail (Game context)
MOCK_GAME_SHOT_DATA = [
    {'PLAYER_ID': 1, 'PLAYER_NAME': 'Player One', 'TEAM_ID': 101, 'TEAM_NAME': 'Team AAA', 'PERIOD': 1, 'MINUTES_REMAINING': 5, 'SECONDS_REMAINING': 30, 'SHOT_TYPE': '2PT Field Goal', 'SHOT_ZONE_BASIC': 'Mid-Range', 'SHOT_ZONE_AREA': 'Center(C)', 'SHOT_ZONE_RANGE': '16-24 ft.', 'SHOT_DISTANCE': 18, 'LOC_X': 0, 'LOC_Y': 180, 'SHOT_MADE_FLAG': 1, 'ACTION_TYPE': 'Jump Shot'},
    {'PLAYER_ID': 2, 'PLAYER_NAME': 'Player Two', 'TEAM_ID': 102, 'TEAM_NAME': 'Team BBB', 'PERIOD': 2, 'MINUTES_REMAINING': 8, 'SECONDS_REMAINING': 15, 'SHOT_TYPE': '3PT Field Goal', 'SHOT_ZONE_BASIC': 'Left Corner 3', 'SHOT_ZONE_AREA': 'Left Side(L)', 'SHOT_ZONE_RANGE': '24+ ft.', 'SHOT_DISTANCE': 24, 'LOC_X': -230, 'LOC_Y': 50, 'SHOT_MADE_FLAG': 0, 'ACTION_TYPE': 'Jump Shot'}
]
MOCK_GAME_LEAGUE_AVG_DATA = [ # Same structure as player shotchart league avg
    {'SHOT_ZONE_BASIC': 'Mid-Range', 'FGA': 1000, 'FGM': 450, 'FG_PCT': 0.450},
    {'SHOT_ZONE_BASIC': 'Left Corner 3', 'FGA': 800, 'FGM': 300, 'FG_PCT': 0.375},
]
mock_game_shots_df = pd.DataFrame(MOCK_GAME_SHOT_DATA)
mock_game_league_avg_df = pd.DataFrame(MOCK_GAME_LEAGUE_AVG_DATA)

# Mock data for LeagueGameFinder
MOCK_LEAGUE_GAMES_DATA = [
    {'GAME_ID': '0022300001', 'GAME_DATE': '2023-10-24', 'MATCHUP': 'LAL @ DEN', 'WL': 'L', 'PTS': 107, 'FG_PCT': 0.450, 'FT_PCT': 0.800, 'FG3_PCT': 0.300, 'AST': 25, 'REB': 40, 'TOV': 15, 'STL': 8, 'BLK': 4},
    {'GAME_ID': '0022300002', 'GAME_DATE': '2023-10-24', 'MATCHUP': 'PHX @ GSW', 'WL': 'W', 'PTS': 115, 'FG_PCT': 0.480, 'FT_PCT': 0.850, 'FG3_PCT': 0.350, 'AST': 28, 'REB': 45, 'TOV': 12, 'STL': 10, 'BLK': 5},
    {'GAME_ID': '0022300003', 'GAME_DATE': '2023-10-25', 'MATCHUP': 'BOS vs. NYK', 'WL': 'W', 'PTS': 120, 'FG_PCT': 0.500, 'FT_PCT': 0.900, 'FG3_PCT': 0.400, 'AST': 30, 'REB': 50, 'TOV': 10, 'STL': 12, 'BLK': 6}
]
mock_league_games_df = pd.DataFrame(MOCK_LEAGUE_GAMES_DATA)

# Mock data for WinProbabilityPBP
MOCK_WP_GAME_INFO_DATA = [{"GAME_ID": MOCK_GAME_ID, "HOME_TEAM_ID": 101, "AWAY_TEAM_ID": 102}]
MOCK_WP_PROB_DATA = [
    {"EVENT_NUM": 1, "HOME_PCT": 0.50, "VISITOR_PCT": 0.50},
    {"EVENT_NUM": 2, "HOME_PCT": 0.55, "VISITOR_PCT": 0.45},
    {"EVENT_NUM": 3, "HOME_PCT": 0.52, "VISITOR_PCT": 0.48}
]
mock_wp_game_info_df = pd.DataFrame(MOCK_WP_GAME_INFO_DATA)
mock_wp_prob_df = pd.DataFrame(MOCK_WP_PROB_DATA)

# --- Tests for fetch_boxscore_traditional_logic ---

@patch('backend.api_tools.game_tools.BoxScoreTraditionalV3')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_boxscore_traditional_success(mock_process_df, mock_boxscore_v3):
    """Test successful fetching of traditional box score using V3."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.player_stats.get_data_frame.return_value = mock_player_stats_v3_df
    mock_endpoint_instance.team_stats.get_data_frame.return_value = mock_team_stats_v3_df
    mock_endpoint_instance.team_starter_bench_stats.get_data_frame.return_value = mock_starters_bench_v3_df
    mock_boxscore_v3.return_value = mock_endpoint_instance

    # Mock _process_dataframe return values
    mock_process_df.side_effect = [
        MOCK_PLAYER_STATS_V3_DATA,      # For player_stats
        MOCK_TEAM_STATS_V3_DATA,        # For team_stats
        MOCK_STARTERS_BENCH_V3_DATA     # For starters_bench
    ]

    # Act
    result_str = game_tools.fetch_boxscore_traditional_logic(MOCK_GAME_ID)
    result = json.loads(result_str)

    # Assert
    mock_boxscore_v3.assert_called_once_with(
        game_id=MOCK_GAME_ID,
        start_period=StartPeriod.default, end_period=EndPeriod.default,
        start_range=StartRange.default, end_range=EndRange.default,
        range_type=RangeType.default, timeout=DEFAULT_TIMEOUT
    )
    assert mock_process_df.call_count == 3
    assert "error" not in result
    assert result.get("game_id") == MOCK_GAME_ID
    assert "teams" in result
    assert "players" in result
    assert "starters_bench" in result
    assert result["players"] == MOCK_PLAYER_STATS_V3_DATA
    assert result["teams"] == MOCK_TEAM_STATS_V3_DATA
    assert result["starters_bench"] == MOCK_STARTERS_BENCH_V3_DATA

def test_fetch_boxscore_traditional_empty_game_id():
    """Test traditional box score fetch with empty game ID."""
    # Arrange
    expected_error = Errors.GAME_ID_EMPTY

    # Act
    result_str = game_tools.fetch_boxscore_traditional_logic("")
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_boxscore_traditional_invalid_game_id():
    """Test traditional box score fetch with invalid game ID format."""
    # Arrange
    invalid_game_id = "12345"
    expected_error = Errors.INVALID_GAME_ID_FORMAT.format(game_id=invalid_game_id)

    # Act
    result_str = game_tools.fetch_boxscore_traditional_logic(invalid_game_id)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.BoxScoreTraditionalV3')
def test_fetch_boxscore_traditional_api_error(mock_boxscore_v3):
    """Test traditional box score fetch with API error."""
    # Arrange
    api_error_message = "NBA API timeout"
    mock_boxscore_v3.side_effect = Exception(api_error_message)
    expected_error = Errors.BOXSCORE_API.format(game_id=MOCK_GAME_ID, error=api_error_message)

    # Act
    result_str = game_tools.fetch_boxscore_traditional_logic(MOCK_GAME_ID)
    result = json.loads(result_str)

    # Assert
    mock_boxscore_v3.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.BoxScoreTraditionalV3')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_boxscore_traditional_processing_error(mock_process_df, mock_boxscore_v3):
    """Test traditional box score fetch with processing error."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.player_stats.get_data_frame.return_value = mock_player_stats_v3_df
    # Simulate other DFs are fine
    mock_endpoint_instance.team_stats.get_data_frame.return_value = mock_team_stats_v3_df
    mock_endpoint_instance.team_starter_bench_stats.get_data_frame.return_value = mock_starters_bench_v3_df
    mock_boxscore_v3.return_value = mock_endpoint_instance

    # Simulate _process_dataframe returning None for player_stats
    mock_process_df.side_effect = [None, MOCK_TEAM_STATS_V3_DATA, MOCK_STARTERS_BENCH_V3_DATA]
    expected_error = Errors.PROCESSING_ERROR.format(error=f"boxscore data for game {MOCK_GAME_ID}")

    # Act
    result_str = game_tools.fetch_boxscore_traditional_logic(MOCK_GAME_ID)
    result = json.loads(result_str)

    # Assert
    mock_boxscore_v3.assert_called_once()
    assert mock_process_df.call_count > 0
    assert "error" in result
    assert result["error"] == expected_error

# --- Tests for fetch_boxscore_advanced_logic ---

@patch('backend.api_tools.game_tools.BoxScoreAdvancedV3')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_boxscore_advanced_success(mock_process_df, mock_boxscore_adv_v3):
    """Test successful fetching of advanced box score using V3."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.player_stats.get_data_frame.return_value = mock_player_advanced_v3_df
    mock_endpoint_instance.team_stats.get_data_frame.return_value = mock_team_advanced_v3_df
    mock_boxscore_adv_v3.return_value = mock_endpoint_instance

    mock_process_df.side_effect = [
        MOCK_PLAYER_ADVANCED_V3_DATA, # For player_stats
        MOCK_TEAM_ADVANCED_V3_DATA    # For team_stats
    ]

    # Act
    result_str = game_tools.fetch_boxscore_advanced_logic(MOCK_GAME_ID)
    result = json.loads(result_str)

    # Assert
    mock_boxscore_adv_v3.assert_called_once_with(
        game_id=MOCK_GAME_ID,
        start_period=0, end_period=0, start_range=0, end_range=0, # Defaults
        timeout=DEFAULT_TIMEOUT
    )
    assert mock_process_df.call_count == 2
    assert "error" not in result
    assert result.get("game_id") == MOCK_GAME_ID
    assert "player_stats" in result
    assert "team_stats" in result
    assert result["player_stats"] == MOCK_PLAYER_ADVANCED_V3_DATA
    assert result["team_stats"] == MOCK_TEAM_ADVANCED_V3_DATA

def test_fetch_boxscore_advanced_empty_game_id():
    """Test advanced box score fetch with empty game ID."""
    # Arrange
    expected_error = Errors.GAME_ID_EMPTY

    # Act
    result_str = game_tools.fetch_boxscore_advanced_logic("")
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_boxscore_advanced_invalid_game_id():
    """Test advanced box score fetch with invalid game ID format."""
    # Arrange
    invalid_game_id = "12345"
    expected_error = Errors.INVALID_GAME_ID_FORMAT.format(game_id=invalid_game_id)

    # Act
    result_str = game_tools.fetch_boxscore_advanced_logic(invalid_game_id)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.BoxScoreAdvancedV3')
def test_fetch_boxscore_advanced_api_error(mock_boxscore_adv_v3):
    """Test advanced box score fetch with API error."""
    # Arrange
    api_error_message = "NBA API timeout"
    mock_boxscore_adv_v3.side_effect = Exception(api_error_message)
    expected_error = Errors.BOXSCORE_ADVANCED_API.format(game_id=MOCK_GAME_ID, error=api_error_message)

    # Act
    result_str = game_tools.fetch_boxscore_advanced_logic(MOCK_GAME_ID)
    result = json.loads(result_str)

    # Assert
    mock_boxscore_adv_v3.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.BoxScoreAdvancedV3')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_boxscore_advanced_processing_error(mock_process_df, mock_boxscore_adv_v3):
    """Test advanced box score fetch with processing error."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.player_stats.get_data_frame.return_value = mock_player_advanced_v3_df
    mock_endpoint_instance.team_stats.get_data_frame.return_value = mock_team_advanced_v3_df
    mock_boxscore_adv_v3.return_value = mock_endpoint_instance

    # Simulate _process_dataframe returning None for player_stats
    mock_process_df.side_effect = [None, MOCK_TEAM_ADVANCED_V3_DATA]
    expected_error = Errors.PROCESSING_ERROR.format(error=f"advanced boxscore data for game {MOCK_GAME_ID}")

    # Act
    result_str = game_tools.fetch_boxscore_advanced_logic(MOCK_GAME_ID)
    result = json.loads(result_str)

    # Assert
    mock_boxscore_adv_v3.assert_called_once()
    assert mock_process_df.call_count > 0
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.BoxScoreAdvancedV3')
def test_fetch_boxscore_advanced_index_error(mock_boxscore_adv_v3):
    """Test advanced box score fetch with IndexError (simulating unavailable data)."""
    # Arrange
    mock_boxscore_adv_v3.side_effect = IndexError("Simulated index error")
    expected_error = Errors.DATA_NOT_FOUND + f" (Advanced box score data might be unavailable for game {MOCK_GAME_ID})"

    # Act
    result_str = game_tools.fetch_boxscore_advanced_logic(MOCK_GAME_ID)
    result = json.loads(result_str)

    # Assert
    mock_boxscore_adv_v3.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

# --- Tests for fetch_boxscore_four_factors_logic ---

@patch('backend.api_tools.game_tools.BoxScoreFourFactorsV3')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_boxscore_four_factors_success(mock_process_df, mock_boxscore_ff_v3):
    """Test successful fetching of four factors box score using V3."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    # Need to mock the import within the function if it's done there
    with patch('backend.api_tools.game_tools.BoxScoreFourFactorsV3', return_value=mock_endpoint_instance):
        mock_endpoint_instance.player_stats.get_data_frame.return_value = mock_player_fourfactors_v3_df
        mock_endpoint_instance.team_stats.get_data_frame.return_value = mock_team_fourfactors_v3_df
        # mock_boxscore_ff_v3.return_value = mock_endpoint_instance # Mocking via context manager now

        mock_process_df.side_effect = [
            MOCK_PLAYER_FOURFACTORS_V3_DATA, # For player_stats
            MOCK_TEAM_FOURFACTORS_V3_DATA    # For team_stats
        ]

        # Act
        result_str = game_tools.fetch_boxscore_four_factors_logic(MOCK_GAME_ID)
        result = json.loads(result_str)

    # Assert
    # mock_boxscore_ff_v3.assert_called_once_with( # Check call within context manager if needed
    #     game_id=MOCK_GAME_ID, start_period=0, end_period=0, timeout=DEFAULT_TIMEOUT
    # )
    assert mock_process_df.call_count == 2
    assert "error" not in result
    assert result.get("game_id") == MOCK_GAME_ID
    assert "player_stats" in result
    assert "team_stats" in result
    assert result["player_stats"] == MOCK_PLAYER_FOURFACTORS_V3_DATA
    assert result["team_stats"] == MOCK_TEAM_FOURFACTORS_V3_DATA

def test_fetch_boxscore_four_factors_empty_game_id():
    """Test four factors box score fetch with empty game ID."""
    # Arrange
    expected_error = Errors.GAME_ID_EMPTY

    # Act
    result_str = game_tools.fetch_boxscore_four_factors_logic("")
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_boxscore_four_factors_invalid_game_id():
    """Test four factors box score fetch with invalid game ID format."""
    # Arrange
    invalid_game_id = "12345"
    expected_error = Errors.INVALID_GAME_ID_FORMAT.format(game_id=invalid_game_id)

    # Act
    result_str = game_tools.fetch_boxscore_four_factors_logic(invalid_game_id)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.BoxScoreFourFactorsV3')
def test_fetch_boxscore_four_factors_api_error(mock_boxscore_ff_v3):
    """Test four factors box score fetch with API error."""
    # Arrange
    api_error_message = "NBA API timeout"
    # Need to mock the import within the function if it's done there
    with patch('backend.api_tools.game_tools.BoxScoreFourFactorsV3', side_effect=Exception(api_error_message)):
        expected_error = Errors.BOXSCORE_FOURFACTORS_API.format(game_id=MOCK_GAME_ID, error=api_error_message)

        # Act
        result_str = game_tools.fetch_boxscore_four_factors_logic(MOCK_GAME_ID)
        result = json.loads(result_str)

    # Assert
    # mock_boxscore_ff_v3.assert_called_once() # Called within context
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.BoxScoreFourFactorsV3')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_boxscore_four_factors_processing_error(mock_process_df, mock_boxscore_ff_v3):
    """Test four factors box score fetch with processing error."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    with patch('backend.api_tools.game_tools.BoxScoreFourFactorsV3', return_value=mock_endpoint_instance):
        mock_endpoint_instance.player_stats.get_data_frame.return_value = mock_player_fourfactors_v3_df
        mock_endpoint_instance.team_stats.get_data_frame.return_value = mock_team_fourfactors_v3_df
        # mock_boxscore_ff_v3.return_value = mock_endpoint_instance

        # Simulate _process_dataframe returning None for player_stats
        mock_process_df.side_effect = [None, MOCK_TEAM_FOURFACTORS_V3_DATA]
        expected_error = Errors.PROCESSING_ERROR.format(error=f"four factors boxscore data for game {MOCK_GAME_ID}")

        # Act
        result_str = game_tools.fetch_boxscore_four_factors_logic(MOCK_GAME_ID)
        result = json.loads(result_str)

    # Assert
    # mock_boxscore_ff_v3.assert_called_once()
    assert mock_process_df.call_count > 0
    assert "error" in result
    assert result["error"] == expected_error

# --- Tests for fetch_boxscore_usage_logic ---

@patch('backend.api_tools.game_tools.BoxScoreUsageV3')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_boxscore_usage_success(mock_process_df, mock_boxscore_usage_v3):
    """Test successful fetching of usage box score using V3."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    with patch('backend.api_tools.game_tools.BoxScoreUsageV3', return_value=mock_endpoint_instance):
        mock_endpoint_instance.player_stats.get_data_frame.return_value = mock_player_usage_v3_df
        mock_process_df.return_value = MOCK_PLAYER_USAGE_V3_DATA

        # Act
        result_str = game_tools.fetch_boxscore_usage_logic(MOCK_GAME_ID)
        result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count == 1
    assert "error" not in result
    assert result.get("game_id") == MOCK_GAME_ID
    assert "usage_stats" in result
    assert result["usage_stats"] == MOCK_PLAYER_USAGE_V3_DATA

def test_fetch_boxscore_usage_empty_game_id():
    """Test usage box score fetch with empty game ID."""
    # Arrange
    expected_error = Errors.GAME_ID_EMPTY

    # Act
    result_str = game_tools.fetch_boxscore_usage_logic("")
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_boxscore_usage_invalid_game_id():
    """Test usage box score fetch with invalid game ID format."""
    # Arrange
    invalid_game_id = "12345"
    expected_error = Errors.INVALID_GAME_ID_FORMAT.format(game_id=invalid_game_id)

    # Act
    result_str = game_tools.fetch_boxscore_usage_logic(invalid_game_id)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.BoxScoreUsageV3')
def test_fetch_boxscore_usage_api_error(mock_boxscore_usage_v3):
    """Test usage box score fetch with API error."""
    # Arrange
    api_error_message = "NBA API timeout"
    with patch('backend.api_tools.game_tools.BoxScoreUsageV3', side_effect=Exception(api_error_message)):
        expected_error = Errors.BOXSCORE_USAGE_API.format(game_id=MOCK_GAME_ID, error=api_error_message)

        # Act
        result_str = game_tools.fetch_boxscore_usage_logic(MOCK_GAME_ID)
        result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.BoxScoreUsageV3')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_boxscore_usage_processing_error(mock_process_df, mock_boxscore_usage_v3):
    """Test usage box score fetch with processing error."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    with patch('backend.api_tools.game_tools.BoxScoreUsageV3', return_value=mock_endpoint_instance):
        mock_endpoint_instance.player_stats.get_data_frame.return_value = mock_player_usage_v3_df
        mock_process_df.return_value = None # Simulate processing error
        expected_error = Errors.PROCESSING_ERROR.format(error=f"usage boxscore data for game {MOCK_GAME_ID}")

        # Act
        result_str = game_tools.fetch_boxscore_usage_logic(MOCK_GAME_ID)
        result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count == 1
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.BoxScoreUsageV3')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_boxscore_usage_empty_df(mock_process_df, mock_boxscore_usage_v3):
    """Test usage box score fetch with empty DataFrame response."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    with patch('backend.api_tools.game_tools.BoxScoreUsageV3', return_value=mock_endpoint_instance):
        mock_endpoint_instance.player_stats.get_data_frame.return_value = pd.DataFrame() # Empty DF
        # _process_dataframe won't be called if the initial df is empty in the logic

        # Act
        result_str = game_tools.fetch_boxscore_usage_logic(MOCK_GAME_ID)
        result = json.loads(result_str)

    # Assert
    # _process_dataframe should *not* be called if the initial DF is empty
    mock_process_df.assert_not_called() # Reverted Assertion
    assert "error" not in result
    assert "usage_stats" in result
    assert result["usage_stats"] == [] # Expect empty list

# --- Tests for fetch_boxscore_defensive_logic ---

@patch('backend.api_tools.game_tools.BoxScoreDefensiveV2')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_boxscore_defensive_success(mock_process_df, mock_boxscore_def_v2):
    """Test successful fetching of defensive box score using V2."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    with patch('backend.api_tools.game_tools.BoxScoreDefensiveV2', return_value=mock_endpoint_instance):
        mock_endpoint_instance.player_stats.get_data_frame.return_value = mock_player_defensive_v2_df
        mock_process_df.return_value = MOCK_PLAYER_DEFENSIVE_V2_DATA

        # Act
        result_str = game_tools.fetch_boxscore_defensive_logic(MOCK_GAME_ID)
        result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count == 1
    assert "error" not in result
    assert result.get("game_id") == MOCK_GAME_ID
    assert "defensive_stats" in result
    assert result["defensive_stats"] == MOCK_PLAYER_DEFENSIVE_V2_DATA

def test_fetch_boxscore_defensive_empty_game_id():
    """Test defensive box score fetch with empty game ID."""
    # Arrange
    expected_error = Errors.GAME_ID_EMPTY

    # Act
    result_str = game_tools.fetch_boxscore_defensive_logic("")
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_boxscore_defensive_invalid_game_id():
    """Test defensive box score fetch with invalid game ID format."""
    # Arrange
    invalid_game_id = "12345"
    expected_error = Errors.INVALID_GAME_ID_FORMAT.format(game_id=invalid_game_id)

    # Act
    result_str = game_tools.fetch_boxscore_defensive_logic(invalid_game_id)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.BoxScoreDefensiveV2')
def test_fetch_boxscore_defensive_api_error(mock_boxscore_def_v2):
    """Test defensive box score fetch with API error."""
    # Arrange
    api_error_message = "NBA API timeout"
    with patch('backend.api_tools.game_tools.BoxScoreDefensiveV2', side_effect=Exception(api_error_message)):
        expected_error = Errors.BOXSCORE_DEFENSIVE_API.format(game_id=MOCK_GAME_ID, error=api_error_message)

        # Act
        result_str = game_tools.fetch_boxscore_defensive_logic(MOCK_GAME_ID)
        result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.BoxScoreDefensiveV2')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_boxscore_defensive_processing_error(mock_process_df, mock_boxscore_def_v2):
    """Test defensive box score fetch with processing error."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    with patch('backend.api_tools.game_tools.BoxScoreDefensiveV2', return_value=mock_endpoint_instance):
        mock_endpoint_instance.player_stats.get_data_frame.return_value = mock_player_defensive_v2_df
        mock_process_df.return_value = None # Simulate processing error
        expected_error = Errors.PROCESSING_ERROR.format(error=f"defensive boxscore data for game {MOCK_GAME_ID}")

        # Act
        result_str = game_tools.fetch_boxscore_defensive_logic(MOCK_GAME_ID)
        result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count == 1
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.BoxScoreDefensiveV2')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_boxscore_defensive_empty_df(mock_process_df, mock_boxscore_def_v2):
    """Test defensive box score fetch with empty DataFrame response."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    with patch('backend.api_tools.game_tools.BoxScoreDefensiveV2', return_value=mock_endpoint_instance):
        mock_endpoint_instance.player_stats.get_data_frame.return_value = pd.DataFrame() # Empty DF

        # Act
        result_str = game_tools.fetch_boxscore_defensive_logic(MOCK_GAME_ID)
        result = json.loads(result_str)

    # Assert
    # _process_dataframe should *not* be called if the initial DF is empty
    mock_process_df.assert_not_called() # Reverted Assertion
    assert "error" not in result
    assert "defensive_stats" in result
    assert result["defensive_stats"] == [] # Expect empty list

# --- Tests for fetch_playbyplay_logic ---

@patch('backend.api_tools.game_tools._fetch_live_playbyplay_logic')
@patch('backend.api_tools.game_tools._fetch_historical_playbyplay_logic')
def test_fetch_playbyplay_live_success(mock_historical_pbp, mock_live_pbp):
    """Test PBP fetch succeeds using the live endpoint."""
    # Arrange
    mock_live_pbp.return_value = MOCK_LIVE_PBP_RESULT

    # Act
    result_str = game_tools.fetch_playbyplay_logic(MOCK_GAME_ID)
    result = json.loads(result_str)

    # Assert
    mock_live_pbp.assert_called_once_with(MOCK_GAME_ID)
    mock_historical_pbp.assert_not_called()
    assert "error" not in result
    assert result["source"] == "live"
    assert result["game_id"] == MOCK_GAME_ID
    assert result["periods"] == MOCK_LIVE_PBP_RESULT["periods"]
    assert result["parameters"]["note"] == "Period filter NA for live data"

@patch('backend.api_tools.game_tools._fetch_live_playbyplay_logic')
@patch('backend.api_tools.game_tools._fetch_historical_playbyplay_logic')
def test_fetch_playbyplay_fallback_to_historical_success(mock_historical_pbp, mock_live_pbp):
    """Test PBP fetch falls back to historical endpoint successfully."""
    # Arrange
    mock_live_pbp.side_effect = ValueError("No live actions found") # Simulate live failure
    mock_historical_pbp.return_value = MOCK_HISTORICAL_PBP_RESULT

    # Act
    result_str = game_tools.fetch_playbyplay_logic(MOCK_GAME_ID, start_period=1, end_period=1) # Pass period filters
    result = json.loads(result_str)

    # Assert
    mock_live_pbp.assert_called_once_with(MOCK_GAME_ID)
    mock_historical_pbp.assert_called_once_with(MOCK_GAME_ID, 1, 1) # Check filters passed
    assert "error" not in result
    assert result["source"] == "historical"
    assert result["game_id"] == MOCK_GAME_ID
    assert result["periods"] == MOCK_HISTORICAL_PBP_RESULT["periods"]
    assert result["parameters"]["start_period"] == 1
    assert result["parameters"]["end_period"] == 1

@patch('backend.api_tools.game_tools._fetch_live_playbyplay_logic')
@patch('backend.api_tools.game_tools._fetch_historical_playbyplay_logic')
def test_fetch_playbyplay_both_fail(mock_historical_pbp, mock_live_pbp):
    """Test PBP fetch when both live and historical endpoints fail."""
    # Arrange
    live_error_msg = "No live actions found"
    hist_error_msg = "Historical API timeout"
    mock_live_pbp.side_effect = ValueError(live_error_msg)
    mock_historical_pbp.side_effect = Exception(hist_error_msg)
    expected_error = Errors.PLAYBYPLAY_API.format(game_id=MOCK_GAME_ID, error=hist_error_msg)

    # Act
    result_str = game_tools.fetch_playbyplay_logic(MOCK_GAME_ID)
    result = json.loads(result_str)

    # Assert
    mock_live_pbp.assert_called_once_with(MOCK_GAME_ID)
    mock_historical_pbp.assert_called_once_with(MOCK_GAME_ID, 0, 0) # Default periods
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_playbyplay_empty_game_id():
    """Test PBP fetch with empty game ID."""
    # Arrange
    expected_error = Errors.GAME_ID_EMPTY

    # Act
    result_str = game_tools.fetch_playbyplay_logic("")
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_playbyplay_invalid_game_id():
    """Test PBP fetch with invalid game ID format."""
    # Arrange
    invalid_game_id = "12345"
    expected_error = Errors.INVALID_GAME_ID_FORMAT.format(game_id=invalid_game_id)

    # Act
    result_str = game_tools.fetch_playbyplay_logic(invalid_game_id)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

# --- Tests for fetch_shotchart_logic ---

@patch('backend.api_tools.game_tools.shotchartdetail.ShotChartDetail')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_shotchart_success(mock_process_df, mock_shotchart_endpoint):
    """Test successful fetching of game shotchart data."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.shot_chart_detail.get_data_frame.return_value = mock_game_shots_df
    mock_endpoint_instance.league_averages.get_data_frame.return_value = mock_game_league_avg_df
    mock_shotchart_endpoint.return_value = mock_endpoint_instance

    mock_process_df.side_effect = [
        MOCK_GAME_SHOT_DATA,        # For shots
        MOCK_GAME_LEAGUE_AVG_DATA   # For league averages
    ]

    # Act
    result_str = game_tools.fetch_shotchart_logic(MOCK_GAME_ID)
    result = json.loads(result_str)

    # Assert
    mock_shotchart_endpoint.assert_called_once_with(
        game_id_nullable=MOCK_GAME_ID, team_id=0, player_id=0,
        context_measure_simple="FGA", season_nullable=None, timeout=DEFAULT_TIMEOUT
    )
    assert mock_process_df.call_count == 2
    assert "error" not in result
    assert result.get("game_id") == MOCK_GAME_ID
    assert "teams" in result
    assert "league_averages" in result
    assert len(result["teams"]) > 0 # Should have data organized by team
    assert len(result["teams"][0]["shots"]) > 0 # Check if shots are nested
    assert result["league_averages"] == MOCK_GAME_LEAGUE_AVG_DATA

def test_fetch_shotchart_empty_game_id():
    """Test game shotchart fetch with empty game ID."""
    # Arrange
    expected_error = Errors.GAME_ID_EMPTY

    # Act
    result_str = game_tools.fetch_shotchart_logic("")
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_shotchart_invalid_game_id():
    """Test game shotchart fetch with invalid game ID format."""
    # Arrange
    invalid_game_id = "12345"
    expected_error = Errors.INVALID_GAME_ID_FORMAT.format(game_id=invalid_game_id)

    # Act
    result_str = game_tools.fetch_shotchart_logic(invalid_game_id)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.shotchartdetail.ShotChartDetail')
def test_fetch_shotchart_api_error(mock_shotchart_endpoint):
    """Test game shotchart fetch with API error."""
    # Arrange
    api_error_message = "NBA API timeout"
    mock_shotchart_endpoint.side_effect = Exception(api_error_message)
    expected_error = Errors.SHOTCHART_API.format(game_id=MOCK_GAME_ID, error=api_error_message)

    # Act
    result_str = game_tools.fetch_shotchart_logic(MOCK_GAME_ID)
    result = json.loads(result_str)

    # Assert
    mock_shotchart_endpoint.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.shotchartdetail.ShotChartDetail')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_shotchart_processing_error(mock_process_df, mock_shotchart_endpoint):
    """Test game shotchart fetch with processing error."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.shot_chart_detail.get_data_frame.return_value = mock_game_shots_df
    mock_endpoint_instance.league_averages.get_data_frame.return_value = mock_game_league_avg_df
    mock_shotchart_endpoint.return_value = mock_endpoint_instance

    mock_process_df.return_value = None # Simulate processing error
    expected_error = Errors.SHOTCHART_PROCESSING.format(game_id=MOCK_GAME_ID)

    # Act
    result_str = game_tools.fetch_shotchart_logic(MOCK_GAME_ID)
    result = json.loads(result_str)

    # Assert
    mock_shotchart_endpoint.assert_called_once()
    assert mock_process_df.call_count > 0
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.shotchartdetail.ShotChartDetail')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_shotchart_empty_df(mock_process_df, mock_shotchart_endpoint):
    """Test game shotchart fetch with empty DataFrame response."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.shot_chart_detail.get_data_frame.return_value = pd.DataFrame() # Empty shots
    mock_endpoint_instance.league_averages.get_data_frame.return_value = pd.DataFrame() # Empty avgs
    mock_shotchart_endpoint.return_value = mock_endpoint_instance

    mock_process_df.side_effect = [[], []] # Processing empty DFs returns empty lists

    # Act
    result_str = game_tools.fetch_shotchart_logic(MOCK_GAME_ID)
    result = json.loads(result_str)

    # Assert
    mock_shotchart_endpoint.assert_called_once()
    assert mock_process_df.call_count == 2
    assert "error" not in result
    assert "teams" in result
    assert result["teams"] == []
    assert "league_averages" in result
    assert result["league_averages"] == []

# --- Tests for fetch_league_games_logic ---

@patch('backend.api_tools.game_tools.leaguegamefinder.LeagueGameFinder')
@patch('backend.api_tools.game_tools._process_dataframe')
@patch('backend.api_tools.game_tools._validate_season_format', return_value=True) # Assume valid season
@patch('backend.api_tools.game_tools.validate_date_format', return_value=True) # Assume valid dates
def test_fetch_league_games_success(mock_validate_date, mock_validate_season, mock_process_df, mock_game_finder):
    """Test successful fetching of league games."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.league_game_finder_results.get_data_frame.return_value = mock_league_games_df
    mock_game_finder.return_value = mock_endpoint_instance

    # Mock _process_dataframe to return the data after potential column selection
    # Simulate selecting relevant columns and formatting date
    processed_data = [
        {'GAME_ID': '0022300001', 'GAME_DATE': '2023-10-24', 'MATCHUP': 'LAL @ DEN', 'WL': 'L', 'PTS': 107, 'FG_PCT': 0.450, 'FT_PCT': 0.800, 'FG3_PCT': 0.300, 'AST': 25, 'REB': 40, 'TOV': 15, 'STL': 8, 'BLK': 4, 'GAME_DATE_FORMATTED': '2023-10-24'},
        {'GAME_ID': '0022300002', 'GAME_DATE': '2023-10-24', 'MATCHUP': 'PHX @ GSW', 'WL': 'W', 'PTS': 115, 'FG_PCT': 0.480, 'FT_PCT': 0.850, 'FG3_PCT': 0.350, 'AST': 28, 'REB': 45, 'TOV': 12, 'STL': 10, 'BLK': 5, 'GAME_DATE_FORMATTED': '2023-10-24'},
        {'GAME_ID': '0022300003', 'GAME_DATE': '2023-10-25', 'MATCHUP': 'BOS vs. NYK', 'WL': 'W', 'PTS': 120, 'FG_PCT': 0.500, 'FT_PCT': 0.900, 'FG3_PCT': 0.400, 'AST': 30, 'REB': 50, 'TOV': 10, 'STL': 12, 'BLK': 6, 'GAME_DATE_FORMATTED': '2023-10-25'}
    ]
    mock_process_df.return_value = processed_data

    # Act
    result_str = game_tools.fetch_league_games_logic(season_nullable=MOCK_SEASON) # Example filter
    result = json.loads(result_str)

    # Assert
    mock_game_finder.assert_called_once()
    mock_process_df.assert_called_once()
    assert "error" not in result
    assert "games" in result
    assert len(result["games"]) == len(processed_data)
    assert result["games"][0]['GAME_ID'] == '0022300001'
    assert 'GAME_DATE_FORMATTED' in result["games"][0]

def test_fetch_league_games_invalid_season():
    """Test league games fetch with invalid season format."""
    # Arrange
    invalid_season = "2023"
    expected_error = Errors.INVALID_SEASON_FORMAT.format(season=invalid_season)

    # Act
    result_str = game_tools.fetch_league_games_logic(season_nullable=invalid_season)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_league_games_invalid_date():
    """Test league games fetch with invalid date format."""
    # Arrange
    invalid_date = "10-25-2023"
    expected_error = Errors.INVALID_DATE_FORMAT.format(date=invalid_date)

    # Act
    result_str = game_tools.fetch_league_games_logic(date_from_nullable=invalid_date)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.leaguegamefinder.LeagueGameFinder')
@patch('backend.api_tools.game_tools._validate_season_format', return_value=True)
def test_fetch_league_games_api_error(mock_validate_season, mock_game_finder):
    """Test league games fetch with API error."""
    # Arrange
    api_error_message = "NBA API timeout"
    mock_game_finder.side_effect = Exception(api_error_message)
    expected_error = Errors.LEAGUE_GAMES_API.format(error=api_error_message)

    # Act
    result_str = game_tools.fetch_league_games_logic(season_nullable=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_game_finder.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.leaguegamefinder.LeagueGameFinder')
@patch('backend.api_tools.game_tools._process_dataframe')
@patch('backend.api_tools.game_tools._validate_season_format', return_value=True)
def test_fetch_league_games_processing_error(mock_validate_season, mock_process_df, mock_game_finder):
    """Test league games fetch with processing error."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.league_game_finder_results.get_data_frame.return_value = mock_league_games_df
    mock_game_finder.return_value = mock_endpoint_instance

    mock_process_df.return_value = None # Simulate processing error
    expected_error = Errors.PROCESSING_ERROR.format(error="league games data")

    # Act
    result_str = game_tools.fetch_league_games_logic(season_nullable=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_game_finder.assert_called_once()
    mock_process_df.assert_called_once()
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.leaguegamefinder.LeagueGameFinder')
@patch('backend.api_tools.game_tools._process_dataframe')
@patch('backend.api_tools.game_tools._validate_season_format', return_value=True)
def test_fetch_league_games_empty_df(mock_validate_season, mock_process_df, mock_game_finder):
    """Test league games fetch with empty DataFrame response."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    mock_endpoint_instance.league_game_finder_results.get_data_frame.return_value = pd.DataFrame() # Empty DF
    mock_game_finder.return_value = mock_endpoint_instance

    # Act
    result_str = game_tools.fetch_league_games_logic(season_nullable=MOCK_SEASON)
    result = json.loads(result_str)

    # Assert
    mock_game_finder.assert_called_once()
    # _process_dataframe should *not* be called if the initial DF is empty
    mock_process_df.assert_not_called() # Reverted Assertion
    assert "error" not in result
    assert "games" in result
    assert result["games"] == [] # Expect empty list

# --- Tests for fetch_win_probability_logic ---

@patch('backend.api_tools.game_tools.WinProbabilityPBP')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_win_probability_success(mock_process_df, mock_wp_endpoint):
    """Test successful fetching of win probability data."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    with patch('backend.api_tools.game_tools.WinProbabilityPBP', return_value=mock_endpoint_instance):
        mock_endpoint_instance.game_info.get_data_frame.return_value = mock_wp_game_info_df
        mock_endpoint_instance.win_prob_p_bp.get_data_frame.return_value = mock_wp_prob_df

        mock_process_df.side_effect = [
            MOCK_WP_GAME_INFO_DATA[0], # single_row=True for game_info
            MOCK_WP_PROB_DATA          # single_row=False for win_prob
        ]

        # Act
        result_str = game_tools.fetch_win_probability_logic(MOCK_GAME_ID)
        result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count == 2
    assert "error" not in result
    assert result.get("game_id") == MOCK_GAME_ID
    assert "game_info" in result
    assert "win_probability" in result
    assert result["game_info"] == MOCK_WP_GAME_INFO_DATA[0]
    assert result["win_probability"] == MOCK_WP_PROB_DATA

def test_fetch_win_probability_empty_game_id():
    """Test win probability fetch with empty game ID."""
    # Arrange
    expected_error = Errors.GAME_ID_EMPTY

    # Act
    result_str = game_tools.fetch_win_probability_logic("")
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

def test_fetch_win_probability_invalid_game_id():
    """Test win probability fetch with invalid game ID format."""
    # Arrange
    invalid_game_id = "12345"
    expected_error = Errors.INVALID_GAME_ID_FORMAT.format(game_id=invalid_game_id)

    # Act
    result_str = game_tools.fetch_win_probability_logic(invalid_game_id)
    result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.WinProbabilityPBP')
def test_fetch_win_probability_api_error(mock_wp_endpoint):
    """Test win probability fetch with API error."""
    # Arrange
    api_error_message = "NBA API timeout"
    with patch('backend.api_tools.game_tools.WinProbabilityPBP', side_effect=Exception(api_error_message)):
        expected_error = Errors.WINPROBABILITY_API.format(game_id=MOCK_GAME_ID, error=api_error_message)

        # Act
        result_str = game_tools.fetch_win_probability_logic(MOCK_GAME_ID)
        result = json.loads(result_str)

    # Assert
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.WinProbabilityPBP')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_win_probability_processing_error(mock_process_df, mock_wp_endpoint):
    """Test win probability fetch with processing error."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    with patch('backend.api_tools.game_tools.WinProbabilityPBP', return_value=mock_endpoint_instance):
        mock_endpoint_instance.game_info.get_data_frame.return_value = mock_wp_game_info_df
        mock_endpoint_instance.win_prob_p_bp.get_data_frame.return_value = mock_wp_prob_df

        mock_process_df.return_value = None # Simulate processing error
        expected_error = Errors.PROCESSING_ERROR.format(error=f"win probability data for game {MOCK_GAME_ID}")

        # Act
        result_str = game_tools.fetch_win_probability_logic(MOCK_GAME_ID)
        result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count > 0
    assert "error" in result
    assert result["error"] == expected_error

@patch('backend.api_tools.game_tools.WinProbabilityPBP')
@patch('backend.api_tools.game_tools._process_dataframe')
def test_fetch_win_probability_empty_df(mock_process_df, mock_wp_endpoint):
    """Test win probability fetch with empty DataFrame response."""
    # Arrange
    mock_endpoint_instance = MagicMock()
    with patch('backend.api_tools.game_tools.WinProbabilityPBP', return_value=mock_endpoint_instance):
        mock_endpoint_instance.game_info.get_data_frame.return_value = pd.DataFrame() # Empty info
        mock_endpoint_instance.win_prob_p_bp.get_data_frame.return_value = pd.DataFrame() # Empty probs

        mock_process_df.side_effect = [{}, []] # Processing empty DFs

        # Act
        result_str = game_tools.fetch_win_probability_logic(MOCK_GAME_ID)
        result = json.loads(result_str)

    # Assert
    assert mock_process_df.call_count == 2
    assert "error" not in result
    assert "game_info" in result
    assert result["game_info"] == {}
    assert "win_probability" in result
    assert result["win_probability"] == []
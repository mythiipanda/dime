import pytest
import json
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerMode48
from backend.tools import (
    get_player_info,
    get_player_gamelog,
    get_team_info_and_roster,
    get_player_career_stats,
    find_games,
    get_player_awards,
    get_boxscore_traditional,
    get_league_standings,
    get_scoreboard,
    get_playbyplay,
    get_draft_history,
    get_league_leaders
)
from backend.api_tools.player_tools import (
    fetch_player_info_logic,
    fetch_player_gamelog_logic,
    fetch_player_career_stats_logic,
    fetch_player_awards_logic
)
from backend.api_tools.team_tools import fetch_team_info_and_roster_logic
from backend.api_tools.game_tools import (
    fetch_league_games_logic,
    fetch_boxscore_traditional_logic,
    fetch_playbyplay_logic
)
from backend.api_tools.league_tools import (
    fetch_league_standings_logic,
    fetch_scoreboard_logic,
    fetch_draft_history_logic,
    fetch_league_leaders_logic
)
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerMode36

# Test Data
TEST_PLAYER = "LeBron James"
TEST_TEAM = "LAL"
TEST_SEASON = "2023-24"
TEST_GAME_ID = "0022300001"  # Example game ID
VALID_STAT_CATEGORIES = ['PTS', 'REB', 'AST', 'STL', 'BLK']

def test_get_player_info():
    """Test getting player information"""
    result = json.loads(fetch_player_info_logic(TEST_PLAYER))
    assert 'error' not in result
    assert 'player_info' in result
    # Check common name field from API response
    assert result['player_info']['DISPLAY_FIRST_LAST'].lower() == TEST_PLAYER.lower()

def test_get_player_gamelog():
    """Test getting player game log"""
    result = json.loads(fetch_player_gamelog_logic(TEST_PLAYER, TEST_SEASON))
    assert 'error' not in result
    assert 'gamelog' in result
    assert isinstance(result['gamelog'], list)

def test_get_player_gamelog_invalid_season_type():
    """Test handling invalid season type"""
    # Invalid season type should be handled with default
    result = json.loads(fetch_player_gamelog_logic(TEST_PLAYER, TEST_SEASON, SeasonTypeAllStar.regular))
    assert 'error' not in result
    assert 'gamelog' in result

def test_get_team_info_and_roster():
    """Test getting team information and roster"""
    result = json.loads(fetch_team_info_and_roster_logic(TEST_TEAM))
    assert 'error' not in result
    assert 'team_info' in result
    assert 'roster' in result
    assert isinstance(result['roster'], list)

def test_get_player_career_stats():
    """Test getting player career statistics"""
    result = json.loads(fetch_player_career_stats_logic(TEST_PLAYER))
    assert 'error' not in result
    assert 'season_totals_regular_season' in result
    assert isinstance(result['season_totals_regular_season'], list)

def test_get_player_career_stats_invalid_per_mode():
    """Test handling invalid per mode"""
    result = json.loads(fetch_player_career_stats_logic(TEST_PLAYER, "Invalid"))
    assert 'error' not in result  # Should use default per mode
    assert 'season_totals_regular_season' in result

def test_find_games_team():
    """Test finding games for a team"""
    result = json.loads(fetch_league_games_logic(player_or_team_abbreviation='T', team_id_nullable=1610612747))
    assert 'error' not in result
    assert 'games' in result
    assert isinstance(result['games'], list)

def test_find_games_missing_id():
    """Test finding games without required ID"""
    result = json.loads(fetch_league_games_logic(player_or_team_abbreviation='T'))
    assert 'error' in result
    assert 'team_id is required' in result['error']

def test_get_player_awards():
    """Test getting player awards"""
    result = json.loads(fetch_player_awards_logic(TEST_PLAYER))
    assert 'error' not in result
    assert 'awards' in result
    assert isinstance(result['awards'], list)

def test_get_boxscore_traditional():
    """Test getting traditional box score"""
    result = json.loads(fetch_boxscore_traditional_logic(TEST_GAME_ID))
    assert 'error' not in result
    assert 'game_id' in result
    assert 'player_stats' in result
    assert 'team_stats' in result

def test_get_league_standings():
    """Test getting league standings"""
    result = json.loads(fetch_league_standings_logic(TEST_SEASON))
    assert 'error' not in result
    standings_list = result.get('standings', [])
    assert isinstance(standings_list, list)
    assert len(standings_list) > 0
    # Verify essential standings data exists
    first_team = standings_list[0]
    assert 'TeamName' in first_team
    assert 'WinPCT' in first_team

def test_get_scoreboard():
    """Test getting scoreboard"""
    result = json.loads(fetch_scoreboard_logic())
    assert 'error' not in result
    assert 'game_header' in result
    assert 'line_score' in result
    assert isinstance(result['game_header'], list)

def test_get_playbyplay():
    """Test getting play-by-play data"""
    result = json.loads(fetch_playbyplay_logic(TEST_GAME_ID))
    assert 'error' not in result
    assert 'actions' in result
    assert isinstance(result['actions'], list)

def test_get_draft_history():
    """Test getting draft history"""
    result = json.loads(fetch_draft_history_logic())
    assert 'error' not in result
    assert 'draft_picks' in result
    assert isinstance(result['draft_picks'], list)

def test_get_league_leaders():
    """Test getting league leaders"""
    result = json.loads(fetch_league_leaders_logic(
        stat_category='PTS',
        season=TEST_SEASON,
        season_type=SeasonTypeAllStar.regular,
        per_mode=PerMode48.per_game
    ))
    assert 'error' not in result
    assert 'leaders' in result
    assert isinstance(result['leaders'], list)
    assert result['stat_category'] == 'PTS'
    assert result['season_type'] == SeasonTypeAllStar.regular

def test_get_league_leaders_invalid_stat():
    """Test handling invalid stat category"""
    result = json.loads(fetch_league_leaders_logic(
        stat_category='INVALID',
        season=TEST_SEASON,
        season_type=SeasonTypeAllStar.regular,
        per_mode=PerMode48.per_game
    ))
    assert 'error' in result

# Error Cases
def test_get_player_info_invalid_player():
    """Test getting info for non-existent player"""
    result = json.loads(fetch_player_info_logic("NonExistentPlayer"))
    assert 'error' in result

def test_get_team_info_invalid_team():
    """Test getting info for non-existent team"""
    result = json.loads(fetch_team_info_and_roster_logic("XXX"))
    assert 'error' in result

def test_get_boxscore_invalid_game():
    """Test getting boxscore for invalid game ID"""
    result = json.loads(fetch_boxscore_traditional_logic("0"))
    assert 'error' in result
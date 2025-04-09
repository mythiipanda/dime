import pytest
import json
from ..api_tools.league_tools import (
    fetch_league_standings_logic,
    fetch_league_leaders_logic,
    fetch_league_lineups_logic,
    fetch_league_hustle_stats_logic
)
from nba_api.stats.library.parameters import SeasonTypeAllStar

# Test data
TEST_SEASON = "2022-23"
INVALID_SEASON = "9999-00"

def test_fetch_league_standings():
    """Test fetching league standings for regular season."""
    result = fetch_league_standings_logic(TEST_SEASON)
    data = json.loads(result)
    
    assert "error" not in data
    assert data["season"] == TEST_SEASON
    assert "standings" in data
    assert isinstance(data["standings"], list)
    assert len(data["standings"]) > 0
    
    # Verify standings structure
    first_team = data["standings"][0]
    required_fields = ["team_id", "team_name", "conference", "wins", "losses", "win_pct"]
    for field in required_fields:
        assert field in first_team

def test_fetch_league_standings_invalid_season():
    """Test fetching league standings with invalid season."""
    result = fetch_league_standings_logic(INVALID_SEASON)
    data = json.loads(result)
    
    assert "standings" in data
    assert len(data["standings"]) == 0

@pytest.mark.parametrize("season_type", [
    SeasonTypeAllStar.regular,
    pytest.param(SeasonTypeAllStar.preseason, marks=pytest.mark.skip(reason="Preseason data may be unavailable")),
    SeasonTypeAllStar.playoffs
])
def test_fetch_league_standings_season_types(season_type):
    """Test fetching league standings for different season types."""
    result = fetch_league_standings_logic(TEST_SEASON, season_type=season_type)
    data = json.loads(result)
    
    if "error" in data and "timeout" in data["error"].lower():
        pytest.skip(f"Skipping due to timeout: {data['error']}")
    
    assert "error" not in data
    assert data["season_type"] == season_type
    assert "standings" in data

def test_fetch_league_leaders():
    """Test fetching league leaders."""
    result = fetch_league_leaders_logic(TEST_SEASON)
    data = json.loads(result)
    
    assert "error" not in data
    assert data["season"] == TEST_SEASON
    assert "leaders" in data
    assert isinstance(data["leaders"], list)
    assert len(data["leaders"]) > 0
    
    # Verify leaders structure
    first_leader = data["leaders"][0]
    required_fields = ["player_id", "player_name", "team_id", "team_abbreviation", "stat_value"]
    for field in required_fields:
        assert field in first_leader

def test_fetch_league_leaders_invalid_season():
    """Test fetching league leaders with invalid season."""
    result = fetch_league_leaders_logic(INVALID_SEASON)
    data = json.loads(result)
    
    assert "leaders" in data
    assert len(data["leaders"]) == 0

def test_fetch_league_lineups():
    """Test fetching league lineups."""
    result = fetch_league_lineups_logic(TEST_SEASON)
    data = json.loads(result)
    
    assert "error" not in data
    assert data["season"] == TEST_SEASON
    assert "lineups" in data
    assert isinstance(data["lineups"], list)
    assert len(data["lineups"]) > 0
    
    # Verify lineup structure
    first_lineup = data["lineups"][0]
    required_fields = ["group_id", "players", "minutes", "plus_minus"]
    for field in required_fields:
        assert field in first_lineup

def test_fetch_league_lineups_invalid_season():
    """Test fetching league lineups with invalid season."""
    result = fetch_league_lineups_logic(INVALID_SEASON)
    data = json.loads(result)
    
    assert "lineups" in data
    assert len(data["lineups"]) == 0

def test_fetch_league_hustle_stats():
    """Test fetching league hustle stats."""
    result = fetch_league_hustle_stats_logic(TEST_SEASON)
    data = json.loads(result)
    
    assert "error" not in data
    assert data["season"] == TEST_SEASON
    assert "hustle_stats" in data
    assert isinstance(data["hustle_stats"], list)
    assert len(data["hustle_stats"]) > 0
    
    # Verify hustle stats structure
    first_stat = data["hustle_stats"][0]
    required_fields = ["player_id", "player_name", "team_id", "deflections", "loose_balls_recovered"]
    for field in required_fields:
        assert field in first_stat

def test_fetch_league_hustle_stats_invalid_season():
    """Test fetching league hustle stats with invalid season."""
    result = fetch_league_hustle_stats_logic(INVALID_SEASON)
    data = json.loads(result)
    
    assert "hustle_stats" in data
    assert len(data["hustle_stats"]) == 0 
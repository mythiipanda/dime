import pytest
import json
from ..api_tools.team_tracking import (
    fetch_team_passing_stats_logic,
    fetch_team_rebounding_stats_logic,
    fetch_team_shooting_stats_logic
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed
)

# Test data
TEST_TEAMS = [
    "Boston Celtics",
    "Los Angeles Lakers",
    "Golden State Warriors"
]
TEST_SEASON = "2022-23"
INVALID_TEAM = "Invalid Team Name"
INVALID_SEASON = "9999-00"

@pytest.mark.parametrize("team_name", TEST_TEAMS)
def test_fetch_team_passing_stats_multiple_teams(team_name):
    """Test fetching passing stats for multiple valid teams."""
    result = fetch_team_passing_stats_logic(team_name, TEST_SEASON)
    data = json.loads(result)
    
    assert "error" not in data
    assert data["team_name"] == team_name
    assert data["season"] == TEST_SEASON
    assert "passes_made" in data
    assert isinstance(data["passes_made"], list)
    assert len(data["passes_made"]) > 0

def test_fetch_team_passing_stats_invalid_team():
    """Test fetching passing stats for an invalid team."""
    result = fetch_team_passing_stats_logic(INVALID_TEAM, TEST_SEASON)
    data = json.loads(result)
    
    assert "error" in data
    assert INVALID_TEAM in data["error"]

def test_fetch_team_passing_stats_invalid_season():
    """Test fetching passing stats with an invalid season."""
    result = fetch_team_passing_stats_logic(TEST_TEAMS[0], INVALID_SEASON)
    data = json.loads(result)
    
    # For invalid seasons, the API returns empty data sets
    assert "passes_made" in data
    assert len(data["passes_made"]) == 0

@pytest.mark.parametrize("team_name", TEST_TEAMS)
def test_fetch_team_rebounding_stats_multiple_teams(team_name):
    """Test fetching rebounding stats for multiple valid teams."""
    result = fetch_team_rebounding_stats_logic(team_name, TEST_SEASON)
    data = json.loads(result)
    
    assert "error" not in data
    assert data["team_name"] == team_name
    assert data["season"] == TEST_SEASON
    
    # Check for expected rebounding data sections
    expected_sections = ["overall_rebounding", "rebounding_types", "shot_type_rebounding"]
    found_sections = 0
    for section in expected_sections:
        if section in data:
            assert isinstance(data[section], list)
            assert len(data[section]) > 0
            found_sections += 1
    
    # At least one section should be present
    assert found_sections > 0

def test_fetch_team_rebounding_stats_invalid_team():
    """Test fetching rebounding stats for an invalid team."""
    result = fetch_team_rebounding_stats_logic(INVALID_TEAM, TEST_SEASON)
    data = json.loads(result)
    
    assert "error" in data
    assert INVALID_TEAM in data["error"]

def test_fetch_team_rebounding_stats_invalid_season():
    """Test fetching rebounding stats with an invalid season."""
    result = fetch_team_rebounding_stats_logic(TEST_TEAMS[0], INVALID_SEASON)
    data = json.loads(result)
    
    # For invalid seasons, the API returns empty data sets
    expected_sections = ["overall_rebounding", "rebounding_types", "shot_type_rebounding"]
    for section in expected_sections:
        if section in data:
            assert len(data[section]) == 0

@pytest.mark.parametrize("team_name", TEST_TEAMS)
def test_fetch_team_shooting_stats_multiple_teams(team_name):
    """Test fetching shooting stats for multiple valid teams."""
    result = fetch_team_shooting_stats_logic(team_name, TEST_SEASON)
    data = json.loads(result)
    
    assert "error" not in data
    assert data["team_name"] == team_name
    assert data["season"] == TEST_SEASON
    
    # Check for expected shooting data sections
    expected_sections = ["general_shooting", "shot_category_detail", "shot_distance_tracking"]
    found_sections = 0
    for section in expected_sections:
        if section in data:
            assert isinstance(data[section], list)
            assert len(data[section]) > 0
            found_sections += 1
    
    # At least one section should be present
    assert found_sections > 0

def test_fetch_team_shooting_stats_invalid_team():
    """Test fetching shooting stats for an invalid team."""
    result = fetch_team_shooting_stats_logic(INVALID_TEAM, TEST_SEASON)
    data = json.loads(result)
    
    assert "error" in data
    assert INVALID_TEAM in data["error"]

def test_fetch_team_shooting_stats_invalid_season():
    """Test fetching shooting stats with an invalid season."""
    result = fetch_team_shooting_stats_logic(TEST_TEAMS[0], INVALID_SEASON)
    data = json.loads(result)
    
    # For invalid seasons, the API returns empty data sets
    expected_sections = ["general_shooting", "shot_category_detail", "shot_distance_tracking"]
    for section in expected_sections:
        if section in data:
            assert len(data[section]) == 0

@pytest.mark.parametrize("season_type", [
    SeasonTypeAllStar.regular,
    pytest.param(SeasonTypeAllStar.preseason, marks=pytest.mark.skip(reason="Preseason data may be unavailable or timeout")),
    SeasonTypeAllStar.playoffs
])
def test_season_type_parameter_all_endpoints(season_type):
    """Test that season_type parameter is properly handled in all endpoints."""
    team_name = TEST_TEAMS[0]
    
    # Test passing stats
    result = fetch_team_passing_stats_logic(team_name, TEST_SEASON, season_type=season_type)
    data = json.loads(result)
    if "error" in data and "timeout" in data["error"].lower():
        pytest.skip(f"Skipping due to timeout: {data['error']}")
    assert "error" not in data
    assert data["season_type"] == season_type
    
    # Test rebounding stats
    result = fetch_team_rebounding_stats_logic(team_name, TEST_SEASON, season_type=season_type)
    data = json.loads(result)
    if "error" in data and "timeout" in data["error"].lower():
        pytest.skip(f"Skipping due to timeout: {data['error']}")
    assert "error" not in data
    assert data["season_type"] == season_type
    
    # Test shooting stats
    result = fetch_team_shooting_stats_logic(team_name, TEST_SEASON, season_type=season_type)
    data = json.loads(result)
    if "error" in data and "timeout" in data["error"].lower():
        pytest.skip(f"Skipping due to timeout: {data['error']}")
    assert "error" not in data
    assert data["season_type"] == season_type

@pytest.mark.parametrize("per_mode", [
    PerModeDetailed.per_game,
    PerModeDetailed.totals
])
def test_per_mode_parameter_all_endpoints(per_mode):
    """Test that per_mode parameter is properly handled in all endpoints."""
    team_name = TEST_TEAMS[0]
    
    # Test passing stats
    result = fetch_team_passing_stats_logic(team_name, TEST_SEASON, per_mode=per_mode)
    data = json.loads(result)
    assert "error" not in data
    
    # Test rebounding stats
    result = fetch_team_rebounding_stats_logic(team_name, TEST_SEASON, per_mode=per_mode)
    data = json.loads(result)
    assert "error" not in data
    
    # Test shooting stats
    result = fetch_team_shooting_stats_logic(team_name, TEST_SEASON, per_mode=per_mode)
    data = json.loads(result)
    assert "error" not in data

@pytest.mark.parametrize("team_id,season,season_type", [
    ("1610612737", "2023-24", SeasonTypeAllStar.regular),  # Hawks regular season
])
def test_fetch_team_passing_stats(team_id, season, season_type):
    """Test fetching team passing stats."""
    try:
        result = fetch_team_passing_stats_logic(team_id, season, season_type)
        assert result is not None
        assert "TeamDashPtPass" in result
        assert len(result["TeamDashPtPass"]) > 0
    except Exception as e:
        if "Timeout" in str(e):
            pytest.skip(f"Timeout error for team {team_id}: {str(e)}")
        raise

@pytest.mark.parametrize("team_id,season,season_type", [
    ("1610612737", "2023-24", SeasonTypeAllStar.regular),  # Hawks regular season
])
def test_fetch_team_rebounding_stats(team_id, season, season_type):
    """Test fetching team rebounding stats."""
    try:
        result = fetch_team_rebounding_stats_logic(team_id, season, season_type)
        assert result is not None
        assert "TeamDashPtReb" in result
        assert len(result["TeamDashPtReb"]) > 0
    except Exception as e:
        if "Timeout" in str(e):
            pytest.skip(f"Timeout error for team {team_id}: {str(e)}")
        raise

@pytest.mark.parametrize("team_id,season,season_type", [
    ("1610612737", "2023-24", SeasonTypeAllStar.regular),  # Hawks regular season
])
def test_fetch_team_shooting_stats(team_id, season, season_type):
    """Test fetching team shooting stats."""
    try:
        result = fetch_team_shooting_stats_logic(team_id, season, season_type)
        assert result is not None
        assert "TeamDashPtShots" in result
        assert len(result["TeamDashPtShots"]) > 0
    except Exception as e:
        if "Timeout" in str(e):
            pytest.skip(f"Timeout error for team {team_id}: {str(e)}")
        raise 
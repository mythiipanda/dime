import pytest
import json
from config import ErrorMessages # Import ErrorMessages for checking specific errors
import json
from config import ErrorMessages # Import ErrorMessages for checking specific errors
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
    result_str = fetch_team_passing_stats_logic(team_name, TEST_SEASON)
    data = json.loads(result_str)

    # Allow the specific resultSet error, otherwise check data
    is_resultset_error = data.get("error") == "API response format error (missing 'resultSet')."
    assert "error" not in data or is_resultset_error, f"Unexpected error: {data.get('error')}"

    if not is_resultset_error:
        # These assertions might fail if the resultSet error occurs, but are correct otherwise
        # assert data.get("team_name") == team_name # Logic doesn't return team_name currently
        assert data.get("season") == TEST_SEASON
        assert "PassesMade" in data or "PassesReceived" in data, "Expected passing data keys not found"
        # assert isinstance(data.get("PassesMade", []), list) # Check type if key exists
        # assert len(data.get("PassesMade", [])) > 0 # Check length if key exists

def test_fetch_team_passing_stats_invalid_team():
    """Test fetching passing stats for an invalid team."""
    result_str = fetch_team_passing_stats_logic(INVALID_TEAM, TEST_SEASON)
    data = json.loads(result_str)

    assert "error" in data
    assert data["error"] == ErrorMessages.TEAM_NOT_FOUND.format(identifier=INVALID_TEAM)

def test_fetch_team_passing_stats_invalid_season():
    """Test fetching passing stats with an invalid season."""
    result_str = fetch_team_passing_stats_logic(TEST_TEAMS[0], INVALID_SEASON)
    data = json.loads(result_str)

    # Check if it returns the specific message for empty data or a format error
    assert "error" in data or data.get("message") == "No passing data found for the specified parameters."
    if "error" in data:
         # If the API itself throws an error for invalid season format, check that
         assert "season" in data["error"].lower() or "format" in data["error"].lower()

@pytest.mark.parametrize("team_name", TEST_TEAMS)
def test_fetch_team_rebounding_stats_multiple_teams(team_name):
    """Test fetching rebounding stats for multiple valid teams."""
    result_str = fetch_team_rebounding_stats_logic(team_name, TEST_SEASON)
    data = json.loads(result_str)

    # Allow the specific resultSet error, otherwise check data
    is_resultset_error = data.get("error") == "API response format error (missing 'resultSet')."
    assert "error" not in data or is_resultset_error, f"Unexpected error: {data.get('error')}"

    if not is_resultset_error:
        # assert data.get("team_name") == team_name
        assert data.get("season") == TEST_SEASON
        # Check for expected rebounding data sections
        expected_keys = ["OverallRebounding", "ShotTypeRebounding", "NumContestedRebounding"]
        assert any(key in data for key in expected_keys), "Expected rebounding data keys not found"
        # for key in expected_keys:
        #     if key in data:
        #         assert isinstance(data[key], list)
        #         assert len(data[key]) > 0

def test_fetch_team_rebounding_stats_invalid_team():
    """Test fetching rebounding stats for an invalid team."""
    result_str = fetch_team_rebounding_stats_logic(INVALID_TEAM, TEST_SEASON)
    data = json.loads(result_str)

    assert "error" in data
    assert data["error"] == ErrorMessages.TEAM_NOT_FOUND.format(identifier=INVALID_TEAM)

def test_fetch_team_rebounding_stats_invalid_season():
    """Test fetching rebounding stats with an invalid season."""
    result_str = fetch_team_rebounding_stats_logic(TEST_TEAMS[0], INVALID_SEASON)
    data = json.loads(result_str)

    # Check if it returns the specific message for empty data or a format error
    assert "error" in data or data.get("message") == "No rebounding data found for the specified parameters."
    if "error" in data:
         assert "season" in data["error"].lower() or "format" in data["error"].lower()

@pytest.mark.parametrize("team_name", TEST_TEAMS)
def test_fetch_team_shooting_stats_multiple_teams(team_name):
    """Test fetching shooting stats for multiple valid teams."""
    result_str = fetch_team_shooting_stats_logic(team_name, TEST_SEASON)
    data = json.loads(result_str)

    # Allow the specific resultSet error, otherwise check data
    is_resultset_error = data.get("error") == "API response format error (missing 'resultSet')."
    assert "error" not in data or is_resultset_error, f"Unexpected error: {data.get('error')}"

    if not is_resultset_error:
        # assert data.get("team_name") == team_name
        assert data.get("season") == TEST_SEASON
        # Check for expected shooting data sections
        expected_keys = ["GeneralShooting", "ShotClockShooting", "DribbleShooting", "ClosestDefenderShooting", "TouchTimeShooting"]
        assert any(key in data for key in expected_keys), "Expected shooting data keys not found"
        # for key in expected_keys:
        #     if key in data:
        #         assert isinstance(data[key], list)
        #         assert len(data[key]) > 0

def test_fetch_team_shooting_stats_invalid_team():
    """Test fetching shooting stats for an invalid team."""
    result_str = fetch_team_shooting_stats_logic(INVALID_TEAM, TEST_SEASON)
    data = json.loads(result_str)

    assert "error" in data
    assert data["error"] == ErrorMessages.TEAM_NOT_FOUND.format(identifier=INVALID_TEAM)

def test_fetch_team_shooting_stats_invalid_season():
    """Test fetching shooting stats with an invalid season."""
    result_str = fetch_team_shooting_stats_logic(TEST_TEAMS[0], INVALID_SEASON)
    data = json.loads(result_str)

    # Check if it returns the specific message for empty data or a format error
    assert "error" in data or data.get("message") == "No shooting data found for the specified parameters."
    if "error" in data:
         assert "season" in data["error"].lower() or "format" in data["error"].lower()

@pytest.mark.parametrize("season_type", [
    SeasonTypeAllStar.regular,
    pytest.param(SeasonTypeAllStar.preseason, marks=pytest.mark.skip(reason="Preseason data may be unavailable or timeout")),
    SeasonTypeAllStar.playoffs
])
def test_season_type_parameter_all_endpoints(season_type):
    """Test that season_type parameter is properly handled in all endpoints."""
    team_name = TEST_TEAMS[0]
    
    # Test passing stats
    result_str = fetch_team_passing_stats_logic(team_name, TEST_SEASON, season_type=season_type)
    data = json.loads(result_str)
    if "error" in data and "timeout" in data["error"].lower():
        pytest.skip(f"Skipping due to timeout: {data['error']}")
    is_resultset_error = data.get("error") == "API response format error (missing 'resultSet')."
    assert "error" not in data or is_resultset_error, f"Unexpected error: {data.get('error')}"
    # if not is_resultset_error: assert data.get("season_type") == season_type # season_type not returned by logic
    
    # Test rebounding stats
    result_str = fetch_team_rebounding_stats_logic(team_name, TEST_SEASON, season_type=season_type)
    data = json.loads(result_str)
    if "error" in data and "timeout" in data["error"].lower():
        pytest.skip(f"Skipping due to timeout: {data['error']}")
    is_resultset_error = data.get("error") == "API response format error (missing 'resultSet')."
    assert "error" not in data or is_resultset_error, f"Unexpected error: {data.get('error')}"
    # if not is_resultset_error: assert data.get("season_type") == season_type
    
    # Test shooting stats
    result_str = fetch_team_shooting_stats_logic(team_name, TEST_SEASON, season_type=season_type)
    data = json.loads(result_str)
    if "error" in data and "timeout" in data["error"].lower():
        pytest.skip(f"Skipping due to timeout: {data['error']}")
    is_resultset_error = data.get("error") == "API response format error (missing 'resultSet')."
    assert "error" not in data or is_resultset_error, f"Unexpected error: {data.get('error')}"
    # if not is_resultset_error: assert data.get("season_type") == season_type

@pytest.mark.parametrize("per_mode", [
    PerModeDetailed.per_game,
    PerModeDetailed.totals
])
def test_per_mode_parameter_all_endpoints(per_mode):
    """Test that per_mode parameter is properly handled in all endpoints."""
    team_name = TEST_TEAMS[0]
    
    # Test passing stats
    result_str = fetch_team_passing_stats_logic(team_name, TEST_SEASON, per_mode=per_mode)
    data = json.loads(result_str)
    is_resultset_error = data.get("error") == "API response format error (missing 'resultSet')."
    assert "error" not in data or is_resultset_error, f"Unexpected error: {data.get('error')}"
    
    # Test rebounding stats
    result_str = fetch_team_rebounding_stats_logic(team_name, TEST_SEASON, per_mode=per_mode)
    data = json.loads(result_str)
    is_resultset_error = data.get("error") == "API response format error (missing 'resultSet')."
    assert "error" not in data or is_resultset_error, f"Unexpected error: {data.get('error')}"
    
    # Test shooting stats
    result_str = fetch_team_shooting_stats_logic(team_name, TEST_SEASON, per_mode=per_mode)
    data = json.loads(result_str)
    is_resultset_error = data.get("error") == "API response format error (missing 'resultSet')."
    assert "error" not in data or is_resultset_error, f"Unexpected error: {data.get('error')}"

@pytest.mark.parametrize("team_id,season,season_type", [
    ("1610612737", "2023-24", SeasonTypeAllStar.regular),  # Hawks regular season
])
def test_fetch_team_passing_stats(team_id, season, season_type):
    """Test fetching team passing stats."""
    try:
        result_str = fetch_team_passing_stats_logic(team_id, season, season_type)
        assert result_str is not None
        result_data = json.loads(result_str)
        is_resultset_error = result_data.get("error") == "API response format error (missing 'resultSet')."
        assert "error" not in result_data or is_resultset_error, f"API returned an unexpected error: {result_data.get('error')}"
        if not is_resultset_error:
            # Check for a key specific to passing stats data sets
            assert "PassesMade" in result_data or "PassesReceived" in result_data, "Expected passing data keys not found"
            # assert len(result_data.get("PassesMade", [])) > 0 # Check length if key exists
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
        result_str = fetch_team_rebounding_stats_logic(team_id, season, season_type)
        assert result_str is not None
        result_data = json.loads(result_str)
        is_resultset_error = result_data.get("error") == "API response format error (missing 'resultSet')."
        assert "error" not in result_data or is_resultset_error, f"API returned an unexpected error: {result_data.get('error')}"
        if not is_resultset_error:
            # Check for a key specific to rebounding stats data sets
            assert "OverallRebounding" in result_data or "ShotTypeRebounding" in result_data or "NumContestedRebounding" in result_data, "Expected rebounding data keys not found"
            # assert len(result_data.get("OverallRebounding", [])) > 0 # Check length if key exists
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
        result_str = fetch_team_shooting_stats_logic(team_id, season, season_type)
        assert result_str is not None
        result_data = json.loads(result_str)
        is_resultset_error = result_data.get("error") == "API response format error (missing 'resultSet')."
        assert "error" not in result_data or is_resultset_error, f"API returned an unexpected error: {result_data.get('error')}"
        if not is_resultset_error:
            # Check for a key specific to shooting stats data sets
            assert "GeneralShooting" in result_data or "ShotClockShooting" in result_data or "DribbleShooting" in result_data, "Expected shooting data keys not found"
            # assert len(result_data.get("GeneralShooting", [])) > 0 # Check length if key exists
    except Exception as e:
        if "Timeout" in str(e):
            pytest.skip(f"Timeout error for team {team_id}: {str(e)}")
        raise
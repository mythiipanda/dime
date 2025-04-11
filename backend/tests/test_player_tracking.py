import sys
import os
import json
import pytest

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.api_tools.player_tracking import (
    fetch_player_passing_stats_logic,
    fetch_player_rebounding_stats_logic,
    fetch_player_shots_tracking_logic,
    fetch_player_clutch_stats_logic
)

# Test parameters
PLAYER_NAME = "LeBron James"
SEASON = "2022-23"
NONEXISTENT_PLAYER = "NonexistentPlayer123"

def test_fetch_player_shots_tracking():
    """Test fetching player shot tracking stats."""
    result = fetch_player_shots_tracking_logic(PLAYER_NAME, SEASON)
    result_dict = json.loads(result)

    # Check basic structure
    assert "error" not in result_dict
    assert "player_name" in result_dict
    assert "player_id" in result_dict
    assert "season" in result_dict

    # Check shot categories
    assert "general_shooting" in result_dict
    assert "shot_clock_shooting" in result_dict
    assert "dribble_shooting" in result_dict
    assert "closest_defender_shooting" in result_dict
    assert "touch_time_shooting" in result_dict

def test_fetch_player_shots_tracking_invalid_player():
    """Test fetching shot tracking stats for invalid player."""
    result = fetch_player_shots_tracking_logic(NONEXISTENT_PLAYER, SEASON)
    result_dict = json.loads(result)

    assert "error" in result_dict
    assert "not found" in result_dict["error"].lower()

def test_fetch_player_rebounding_stats():
    """Test fetching player rebounding stats."""
    result = fetch_player_rebounding_stats_logic(PLAYER_NAME, SEASON)
    result_dict = json.loads(result)

    # Check basic structure
    assert "error" not in result_dict
    assert isinstance(result_dict, dict)

    # Check for rebounding data
    assert any(key for key in result_dict.keys() if "reb" in key.lower())

def test_fetch_player_rebounding_stats_invalid_player():
    """Test fetching rebounding stats for invalid player."""
    result = fetch_player_rebounding_stats_logic(NONEXISTENT_PLAYER, SEASON)
    result_dict = json.loads(result)

    assert "error" in result_dict
    assert "not found" in result_dict["error"].lower()

def test_fetch_player_passing_stats():
    """Test fetching player passing stats."""
    result = fetch_player_passing_stats_logic(PLAYER_NAME, SEASON)
    result_dict = json.loads(result)

    # Check basic structure
    assert "error" not in result_dict
    assert isinstance(result_dict, dict)

    # Check for passing data
    assert any(key for key in result_dict.keys() if "pass" in key.lower())

def test_fetch_player_passing_stats_invalid_player():
    """Test fetching passing stats for invalid player."""
    result = fetch_player_passing_stats_logic(NONEXISTENT_PLAYER, SEASON)
    result_dict = json.loads(result)

    assert "error" in result_dict
    assert "not found" in result_dict["error"].lower()

def test_fetch_player_clutch_stats():
    """Test fetching player clutch stats."""
    result = fetch_player_clutch_stats_logic(PLAYER_NAME, SEASON)
    result_dict = json.loads(result)

    # Check basic structure
    assert "error" not in result_dict
    assert isinstance(result_dict, dict)

    # Check for clutch data (adjust keys based on actual API response if needed)
    # Example check: Look for common clutch stat categories
    assert any(key for key in result_dict.keys() if "clutch" in key.lower() or "last" in key.lower() or "min" in key.lower())

def test_fetch_player_clutch_stats_invalid_player():
    """Test fetching clutch stats for invalid player."""
    result = fetch_player_clutch_stats_logic(NONEXISTENT_PLAYER, SEASON)
    result_dict = json.loads(result)

    assert "error" in result_dict
    assert "not found" in result_dict["error"].lower()

@pytest.mark.parametrize("player_name,season,expected_error", [
    (PLAYER_NAME, "invalid-season", "error"),
    ("", SEASON, "error"),
    (None, SEASON, "error"),
    (PLAYER_NAME, None, "error"),
])
def test_invalid_inputs(player_name, season, expected_error):
    """Test handling of invalid inputs for all tracking functions."""
    # Test shots tracking
    result_shots = fetch_player_shots_tracking_logic(player_name, season)
    result_shots_dict = json.loads(result_shots)
    assert expected_error in result_shots_dict or "error" in result_shots_dict # Allow generic error key

    # Test rebounding stats
    result_reb = fetch_player_rebounding_stats_logic(player_name, season)
    result_reb_dict = json.loads(result_reb)
    assert expected_error in result_reb_dict or "error" in result_reb_dict

    # Test passing stats
    result_pass = fetch_player_passing_stats_logic(player_name, season)
    result_pass_dict = json.loads(result_pass)
    assert expected_error in result_pass_dict or "error" in result_pass_dict

    # Test clutch stats
    result_clutch = fetch_player_clutch_stats_logic(player_name, season)
    result_clutch_dict = json.loads(result_clutch)
    assert expected_error in result_clutch_dict or "error" in result_clutch_dict
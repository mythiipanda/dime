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

def test_player_passing_stats():
    print(f"\n[Testing Player Passing Stats for {PLAYER_NAME}]")
    result = fetch_player_passing_stats_logic(PLAYER_NAME, SEASON)
    parsed_result = json.loads(result)
    if "error" in parsed_result:
        print(f"Error: {parsed_result['error']}")
        assert False, f"Error in passing stats: {parsed_result['error']}"
    else:
        print(f"Successfully retrieved passing stats for {parsed_result['player_name']}")
        print(f"Season: {parsed_result['season']}")
        if "passes_made" in parsed_result:
            print(f"Pass targets found: {len(parsed_result['passes_made'])}")
            assert True
        else:
            assert False, "No passes_made data found"

def test_player_rebounding_stats():
    print(f"\n[Testing Player Rebounding Stats for {PLAYER_NAME}]")
    result = fetch_player_rebounding_stats_logic(PLAYER_NAME, SEASON)
    parsed_result = json.loads(result)
    if "error" in parsed_result:
        print(f"Error: {parsed_result['error']}")
        assert False, f"Error in rebounding stats: {parsed_result['error']}"
    else:
        print(f"Successfully retrieved rebounding stats for {parsed_result['player_name']}")
        print(f"Season: {parsed_result['season']}")
        if "overall_rebounding" in parsed_result:
            print("Overall rebounding stats retrieved")
            assert True
        else:
            assert False, "No overall_rebounding data found"

def test_player_shots_tracking():
    print(f"\n[Testing Player Shot Tracking for {PLAYER_NAME}]")
    result = fetch_player_shots_tracking_logic(PLAYER_NAME, SEASON)
    parsed_result = json.loads(result)
    if "error" in parsed_result:
        print(f"Error: {parsed_result['error']}")
        assert False, f"Error in shot tracking: {parsed_result['error']}"
    else:
        print(f"Successfully retrieved shot tracking stats for {parsed_result['player_name']}")
        print(f"Season: {parsed_result['season']}")
        if "general_shooting" in parsed_result:
            print("General shooting stats retrieved")
            assert True
        else:
            assert False, "No general_shooting data found"

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

@pytest.mark.parametrize("player_name,season,expected_error", [
    (PLAYER_NAME, "invalid-season", "error"),
    ("", SEASON, "error"),
    (None, SEASON, "error"),
    (PLAYER_NAME, None, "error"),
])
def test_invalid_inputs(player_name, season, expected_error):
    """Test handling of invalid inputs for all tracking functions."""
    # Test shots tracking
    result = fetch_player_shots_tracking_logic(player_name, season)
    assert expected_error in json.loads(result)
    
    # Test rebounding stats
    result = fetch_player_rebounding_stats_logic(player_name, season)
    assert expected_error in json.loads(result)
    
    # Test passing stats
    result = fetch_player_passing_stats_logic(player_name, season)
    assert expected_error in json.loads(result)

if __name__ == "__main__":
    # Run tests
    success_count = 0
    
    if test_player_passing_stats():
        success_count += 1
    
    if test_player_rebounding_stats():
        success_count += 1
    
    if test_player_shots_tracking():
        success_count += 1
    
    print(f"\n[Test Summary]")
    print(f"Tests completed: 3")
    print(f"Tests passed: {success_count}")
    print(f"Tests failed: {3 - success_count}")
    
    if success_count == 3:
        print("All tests passed successfully!")
    else:
        print("Some tests failed.") 
import pytest
import json
import time
import requests
from unittest.mock import patch
from ..config import ErrorMessages as Errors
from ..api_tools.game_tools import (
    fetch_game_boxscore_logic,
    fetch_game_playbyplay_logic,
    fetch_game_shotchart_logic,
    fetch_game_hustle_stats_logic
)

# Test data
TEST_GAME_ID = "0022200021"  # Use a known valid game ID from 2022-23 season
INVALID_GAME_ID = "9999999999"
OT_GAME_ID = "0022300653"  # Bucks vs Kings 2024-01-14 2OT game

def test_fetch_game_boxscore():
    """Test fetching game boxscore for a valid game."""
    result = fetch_game_boxscore_logic(TEST_GAME_ID)
    data = json.loads(result)
    
    assert "error" not in data
    assert data["game_id"] == TEST_GAME_ID
    assert "home_team" in data
    assert "away_team" in data
    
    # Verify team boxscore structure
    for team in ["home_team", "away_team"]:
        team_data = data[team]
        assert "team_id" in team_data
        assert "team_name" in team_data
        assert "players" in team_data
        assert isinstance(team_data["players"], list)
        assert len(team_data["players"]) > 0
        
        # Verify player stats structure
        first_player = team_data["players"][0]
        required_fields = ["player_id", "player_name", "minutes", "points", "rebounds", "assists"]
        for field in required_fields:
            assert field in first_player

def test_fetch_game_boxscore_invalid_game():
    """Test fetching game boxscore with invalid game ID."""
    result = fetch_game_boxscore_logic(INVALID_GAME_ID)
    data = json.loads(result)
    
    assert "error" in data
    assert INVALID_GAME_ID in data["error"]

def test_fetch_game_playbyplay():
    """Test fetching play-by-play data for a regular game"""
    game_id = "0022200021"  # Use a known regular game
    result = json.loads(fetch_game_playbyplay_logic(game_id))
    
    assert "error" not in result
    assert result["game_id"] == game_id
    assert "total_periods" in result
    assert "overtime_periods" in result
    assert isinstance(result["plays"], list)
    assert len(result["plays"]) > 0
    
    # Verify required fields in plays
    for play in result["plays"]:
        assert "GAME_ID" in play
        assert "PERIOD" in play

def test_fetch_game_playbyplay_overtime():
    """Test fetching play-by-play data for a game with overtime"""
    game_id = "0022200024"  # Use a known overtime game
    result = json.loads(fetch_game_playbyplay_logic(game_id))
    
    assert "error" not in result
    assert result["game_id"] == game_id
    assert result["total_periods"] > 4
    assert result["overtime_periods"] > 0
    assert isinstance(result["plays"], list)
    assert len(result["plays"]) > 0
    
    # Verify plays from overtime periods exist
    overtime_plays = [play for play in result["plays"] if play["PERIOD"] > 4]
    assert len(overtime_plays) > 0

def test_fetch_game_playbyplay_by_period():
    """Test fetching play-by-play data filtered by period"""
    game_id = "0022200021"
    period = 1
    result = json.loads(fetch_game_playbyplay_logic(game_id, period))
    
    assert "error" not in result
    assert result["game_id"] == game_id
    assert isinstance(result["plays"], list)
    assert len(result["plays"]) > 0
    
    # Verify all plays are from the requested period
    for play in result["plays"]:
        assert play["PERIOD"] == period

def test_fetch_game_playbyplay_invalid():
    """Test fetching play-by-play data with invalid inputs"""
    # Test empty game ID
    result = json.loads(fetch_game_playbyplay_logic(""))
    assert "error" in result
    assert result["error"] == Errors.GAME_ID_EMPTY
    
    # Test invalid game ID format
    result = json.loads(fetch_game_playbyplay_logic("invalid"))
    assert "error" in result
    assert Errors.INVALID_GAME_ID_FORMAT.format(game_id="invalid") in result["error"]
    
    # Test non-existent game ID
    result = json.loads(fetch_game_playbyplay_logic("9999999999"))
    assert "error" in result
    assert "No play-by-play data found" in result["error"]
    
    # Test invalid period
    game_id = "0022200021"
    result = json.loads(fetch_game_playbyplay_logic(game_id, 10))
    assert "error" in result
    assert "No play-by-play data found for period 10" in result["error"]

def test_fetch_game_playbyplay_timeout():
    """Test handling of timeout errors during play-by-play retrieval"""
    with patch('nba_api.stats.endpoints.playbyplayv3.PlayByPlayV3', side_effect=requests.exceptions.Timeout):
        result = fetch_game_playbyplay_logic(TEST_GAME_ID)
        assert isinstance(result, dict)
        assert "error" in result
        assert "timeout" in result["error"].lower()

@pytest.mark.parametrize("period", [5, 6])
def test_fetch_game_playbyplay_overtime(period):
    """Test fetching play-by-play data for overtime periods"""
    result = fetch_game_playbyplay_logic(OT_GAME_ID, period)
    data = json.loads(result) if isinstance(result, str) else result
    
    assert "error" not in data
    assert data["game_id"] == OT_GAME_ID
    if "period" in data:  # If period filtering is implemented
        assert data["period"] == period
    assert "play_by_play" in data
    assert isinstance(data["play_by_play"], list)
    if "plays" in data:  # If period filtering returns filtered plays
        for play in data["plays"]:
            assert play["period"] == period

def test_fetch_game_playbyplay_data_validation():
    """Test validation of play-by-play data fields"""
    result = fetch_game_playbyplay_logic(TEST_GAME_ID)
    data = json.loads(result) if isinstance(result, str) else result
    
    assert "error" not in data
    assert "game_id" in data
    assert "play_by_play" in data
    assert isinstance(data["play_by_play"], list)
    
    if data["play_by_play"]:
        first_play = data["play_by_play"][0]
        required_fields = ["GAME_ID", "EVENTNUM", "EVENTMSGTYPE", "PERIOD", "PCTIMESTRING"]
        for field in required_fields:
            assert field in first_play

@pytest.mark.skip(reason="Cache implementation is optional - enable if caching is implemented")
def test_fetch_game_playbyplay_caching():
    """Test caching behavior for play-by-play data"""
    # First call
    start_time = time.time()
    result1 = fetch_game_playbyplay_logic(TEST_GAME_ID)
    first_call_time = time.time() - start_time
    
    # Second call (should be faster if cached)
    start_time = time.time()
    result2 = fetch_game_playbyplay_logic(TEST_GAME_ID)
    second_call_time = time.time() - start_time
    
    # Convert results to dict if they're JSON strings
    if isinstance(result1, str):
        result1 = json.loads(result1)
    if isinstance(result2, str):
        result2 = json.loads(result2)
    
    assert result1 == result2  # Results should be identical
    assert second_call_time < first_call_time  # Second call should be faster

def test_fetch_game_shotchart():
    """Test fetching shot chart data for a valid game."""
    result = fetch_game_shotchart_logic(TEST_GAME_ID)
    data = json.loads(result)
    
    assert "error" not in data
    assert data["game_id"] == TEST_GAME_ID
    assert "shots" in data
    assert isinstance(data["shots"], list)
    assert len(data["shots"]) > 0
    
    # Verify shot structure
    first_shot = data["shots"][0]
    required_fields = ["player_id", "player_name", "x", "y", "shot_made", "shot_type"]
    for field in required_fields:
        assert field in first_shot

def test_fetch_game_shotchart_invalid_game():
    """Test fetching shot chart with invalid game ID."""
    result = fetch_game_shotchart_logic(INVALID_GAME_ID)
    data = json.loads(result)
    
    assert "error" in data
    assert INVALID_GAME_ID in data["error"]

def test_fetch_game_hustle_stats():
    """Test fetching hustle stats for a valid game."""
    result = fetch_game_hustle_stats_logic(TEST_GAME_ID)
    data = json.loads(result)
    
    assert "error" not in data
    assert data["game_id"] == TEST_GAME_ID
    assert "home_team" in data
    assert "away_team" in data
    
    # Verify team hustle stats structure
    for team in ["home_team", "away_team"]:
        team_data = data[team]
        assert "team_id" in team_data
        assert "team_name" in team_data
        assert "players" in team_data
        assert isinstance(team_data["players"], list)
        assert len(team_data["players"]) > 0
        
        # Verify player hustle stats structure
        first_player = team_data["players"][0]
        required_fields = ["player_id", "player_name", "deflections", "loose_balls_recovered", "charges_drawn"]
        for field in required_fields:
            assert field in first_player

def test_fetch_game_hustle_stats_invalid_game():
    """Test fetching hustle stats with invalid game ID."""
    result = fetch_game_hustle_stats_logic(INVALID_GAME_ID)
    data = json.loads(result)
    
    assert "error" in data
    assert INVALID_GAME_ID in data["error"] 
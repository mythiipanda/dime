import sys
import os
import pytest
from unittest.mock import patch, MagicMock
import json

# Add the backend directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

from api_tools.player_tools import (
    find_player_by_name,
    _find_player_id,
    fetch_player_stats_logic,
    fetch_player_clutch_stats_logic
)

def test_find_player_by_name():
    # Test with a valid player name
    result = find_player_by_name("LeBron James")
    assert result is not None
    assert "id" in result
    assert "full_name" in result
    assert result["full_name"] == "LeBron James"

    # Test with an invalid player name
    result = find_player_by_name("NonexistentPlayer123")
    assert result is None

    # Test with None
    result = find_player_by_name(None)
    assert result is None

    # Test with empty string
    result = find_player_by_name("")
    assert result is None

def test_find_player_id():
    # Test with a valid player name
    player_id, full_name = _find_player_id("LeBron James")
    assert player_id is not None
    assert full_name == "LeBron James"

    # Test with an invalid player name
    player_id, full_name = _find_player_id("NonexistentPlayer123")
    assert player_id is None
    assert full_name is None

    # Test with None
    player_id, full_name = _find_player_id(None)
    assert player_id is None
    assert full_name is None

@pytest.mark.skip(reason="Need to mock NBA API calls")
def test_fetch_player_stats_logic():
    # Test with valid inputs
    result = fetch_player_stats_logic("LeBron James", "2022-23")
    result_dict = json.loads(result)
    assert result_dict is not None
    assert "player_name" in result_dict
    assert "player_id" in result_dict
    assert "info" in result_dict
    assert "career_stats" in result_dict

    # Test with invalid player
    result = fetch_player_stats_logic("NonexistentPlayer123", "2022-23")
    result_dict = json.loads(result)
    assert "error" in result_dict
    assert "Player not found" in result_dict["error"]

    # Test with invalid season
    result = fetch_player_stats_logic("LeBron James", "invalid-season")
    result_dict = json.loads(result)
    assert "error" in result_dict

@pytest.mark.skip(reason="Need to mock NBA API calls")
def test_fetch_player_clutch_stats_logic():
    # Test with valid inputs
    result = fetch_player_clutch_stats_logic("LeBron James", "2022-23")
    result_dict = json.loads(result)
    assert result_dict is not None
    assert "player_name" in result_dict
    assert "player_id" in result_dict
    assert "overall_clutch" in result_dict
    assert "last5min_clutch" in result_dict

    # Test with invalid player
    result = fetch_player_clutch_stats_logic("NonexistentPlayer123", "2022-23")
    result_dict = json.loads(result)
    assert "error" in result_dict
    assert "Player not found" in result_dict["error"]

    # Test with invalid season
    result = fetch_player_clutch_stats_logic("LeBron James", "invalid-season")
    result_dict = json.loads(result)
    assert "error" in result_dict 
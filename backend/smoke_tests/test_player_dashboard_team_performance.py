import sys
import os
import pytest
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from backend.api_tools.player_dashboard_team_performance import fetch_player_dashboard_by_team_performance_logic

@pytest.mark.parametrize("player_name,season,expected_key", [
    ("LeBron James", "2023-24", "team_performance_dashboards"),
    ("Stephen Curry", "2023-24", "team_performance_dashboards"),
])
def test_fetch_player_dashboard_by_team_performance_success(player_name, season, expected_key):
    result = fetch_player_dashboard_by_team_performance_logic(player_name=player_name, season=season)
    data = json.loads(result)
    assert expected_key in data
    assert "overall_player_dashboard" in data[expected_key]
    assert isinstance(data[expected_key]["overall_player_dashboard"], list)

def test_fetch_player_dashboard_by_team_performance_invalid_player():
    result = fetch_player_dashboard_by_team_performance_logic(player_name="NotARealPlayer", season="2023-24")
    data = json.loads(result)
    assert "error" in data
    assert "not found" in data["error"].lower()

def test_fetch_player_dashboard_by_team_performance_invalid_season():
    result = fetch_player_dashboard_by_team_performance_logic(player_name="LeBron James", season="20XX-YY")
    data = json.loads(result)
    assert "error" in data
    assert "season" in data["error"].lower()

def test_fetch_player_dashboard_by_team_performance_invalid_per_mode():
    result = fetch_player_dashboard_by_team_performance_logic(player_name="LeBron James", season="2023-24", per_mode="InvalidMode")
    data = json.loads(result)
    assert "error" in data
    assert "per_mode" in data["error"].lower()

def test_fetch_player_dashboard_by_team_performance_edge_case():
    # Edge: Valid player, but likely no games (e.g., LastNGames very high)
    result = fetch_player_dashboard_by_team_performance_logic(player_name="LeBron James", season="2023-24", last_n_games=999)
    data = json.loads(result)
    assert "team_performance_dashboards" in data
    # Should still return dashboard keys, possibly empty lists
    for key in ["overall_player_dashboard", "points_scored_player_dashboard", "ponts_against_player_dashboard", "score_differential_player_dashboard"]:
        assert key in data["team_performance_dashboards"]
        assert isinstance(data["team_performance_dashboards"][key], list)
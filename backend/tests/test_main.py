import pytest
from fastapi.testclient import TestClient
from main import app # Import the FastAPI app instance
import json
from nba_api.stats.library.parameters import PerMode36 # For test values

# Create a synchronous test client
client = TestClient(app)

# --- Test Root Endpoint ---
def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "NBA Analytics Backend using Agno"}

# --- Test Analyze Endpoint ---
def test_analyze_endpoint():
    """Test the /analyze endpoint with mock data."""
    payload = {
        "query": "Summarize performance",
        "data": {"player_name": "Test Player", "PTS": 25, "AST": 5, "REB": 10}
    }
    response = client.post("/analyze", json=payload)
    # Expecting 200 even if agent response needs work, as endpoint handles it
    assert response.status_code == 200
    assert "analysis" in response.json()

# --- Tests for Fetch Data Endpoint (Direct Logic Call) ---

def test_fetch_data_endpoint_success():
    """
    Test the /fetch_data endpoint for a valid player.
    Expects a 200 OK with player_info and headline_stats.
    """
    # Now requires target/params, not prompt
    payload = {
        "target": "player_info",
        "params": {"player_name": "LeBron James"}
    }
    response = client.post("/fetch_data", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "player_info" in data and data["player_info"]["DISPLAY_FIRST_LAST"] == "LeBron James"
    assert "headline_stats" in data

def test_fetch_data_endpoint_not_found():
    """
    Test the /fetch_data endpoint for a player that doesn't exist.
    Expects a 404 Not Found error.
    """
    payload = {
        "target": "player_info",
        "params": {"player_name": "Non Existent Player XYZ"}
    }
    response = client.post("/fetch_data", json=payload)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_fetch_data_endpoint_bad_request():
    """
    Test the /fetch_data endpoint with an unsupported target or missing params.
    Expects a 400 Bad Request error.
    """
    # Missing player_name for player_info target
    payload_missing_param = {
        "target": "player_info",
        "params": {}
    }
    response_missing = client.post("/fetch_data", json=payload_missing_param)
    assert response_missing.status_code == 400
    assert "missing 'player_name'" in response_missing.json()["detail"].lower()

    # Unsupported target
    payload_bad_target = {
        "target": "invalid_target",
        "params": {"player_name": "LeBron James"}
    }
    response_bad_target = client.post("/fetch_data", json=payload_bad_target)
    assert response_bad_target.status_code == 400
    assert "unsupported target" in response_bad_target.json()["detail"].lower()

def test_fetch_player_career_success():
    """Test fetching player career stats successfully."""
    payload = {
        "target": "player_career_stats",
        "params": {"player_name": "Kevin Durant"}
    }
    response = client.post("/fetch_data", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "player_name" in data and data["player_name"] == "Kevin Durant"
    assert "season_totals_regular_season" in data and isinstance(data["season_totals_regular_season"], list)
    assert "career_totals_regular_season" in data and isinstance(data["career_totals_regular_season"], dict)
    assert data.get("per_mode_requested") == "PerGame"

def test_fetch_player_career_totals_mode():
    """Test fetching player career stats with Totals per_mode."""
    payload = {
        "target": "player_career_stats",
        "params": {"player_name": "Kevin Durant", "per_mode36": PerMode36.totals}
    }
    response = client.post("/fetch_data", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data.get("per_mode_requested") == "Totals"

def test_fetch_player_career_not_found():
    """Test fetching career stats for a non-existent player."""
    payload = {
        "target": "player_career_stats",
        "params": {"player_name": "Non Existent Player XYZ"}
    }
    response = client.post("/fetch_data", json=payload)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_fetch_player_career_invalid_per_mode():
    """Test fetching career stats with an invalid per_mode."""
    payload = {
        "target": "player_career_stats",
        "params": {"player_name": "Kevin Durant", "per_mode36": "InvalidMode"}
    }
    response = client.post("/fetch_data", json=payload)
    # Expect 200 as tool logic defaults invalid mode
    assert response.status_code == 200
    data = response.json()
    assert data.get("per_mode_requested") == "InvalidMode" # Check the original invalid requested mode
    assert data.get("data_retrieved_mode") == "Default (PerMode parameter ignored)"

# --- Tests for Find Games ---

def test_fetch_find_games_team_success():
    """Test finding games for a team successfully."""
    payload = {
        "target": "find_games",
        "params": {"player_or_team": "T", "team_id": 1610612747}
    }
    response = client.post("/fetch_data", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "games" in data and isinstance(data["games"], list)
    assert len(data["games"]) > 0 and len(data["games"]) <= 20 # Check limit
    assert "GAME_ID" in data["games"][0]
    assert "TEAM_ID" in data["games"][0] and data["games"][0]["TEAM_ID"] == 1610612747

def test_fetch_find_games_player_success():
    """Test finding games for a player successfully."""
    payload = {
        "target": "find_games",
        "params": {"player_or_team": "P", "player_id": 2544}
    }
    response = client.post("/fetch_data", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "games" in data and isinstance(data["games"], list)
    assert len(data["games"]) > 0 and len(data["games"]) <= 20 # Check limit
    assert "GAME_ID" in data["games"][0]
    assert "PLAYER_ID" in data["games"][0] and data["games"][0]["PLAYER_ID"] == 2544

def test_fetch_find_games_missing_id():
    """Test finding games with missing required ID."""
    payload_team = {
        "target": "find_games",
        "params": {"player_or_team": "T"} # Missing team_id
    }
    response_team = client.post("/fetch_data", json=payload_team)
    assert response_team.status_code == 400 # Logic should raise 400 now
    assert "missing 'team_id'" in response_team.json()["detail"].lower()

    payload_player = {
        "target": "find_games",
        "params": {"player_or_team": "P"} # Missing player_id
    }
    response_player = client.post("/fetch_data", json=payload_player)
    assert response_player.status_code == 400 # Logic should raise 400 now
    assert "missing 'player_id'" in response_player.json()["detail"].lower()

# --- Test Normalize Endpoint (Commented Out) ---
# def test_normalize_data_endpoint():
#     """Test the /normalize_data endpoint (placeholder)."""
#     payload = {"raw_data": {"some_key": "some_value"}}
#     response = client.post("/normalize_data", json=payload)
#     # Expecting 501 Not Implemented now
#     assert response.status_code == 501
#     # assert "normalized_data_simulation_result" in response.json()
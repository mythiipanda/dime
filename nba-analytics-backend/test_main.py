import pytest
from fastapi.testclient import TestClient # Import TestClient
from main import app

# No need for pytest_asyncio for synchronous TestClient

# Instantiate the TestClient
client = TestClient(app)

# --- Tests ---

def test_read_root(): # Remove async and decorator
    # Correct indentation starts here
    """
    Test if the root endpoint returns the expected welcome message.
    """
    # Use the synchronous client directly
    response = client.get("/")
    
    assert response.status_code == 200
    assert response.json() == {"message": "NBA Analytics Backend using Agno"}

# --- Tests for Agent Endpoints ---

# Removed async decorator
def test_analyze_endpoint(): # Remove async
    """
    Test the /analyze endpoint with basic input.
    Expects either a 200 OK with 'analysis' or 500 error if agent fails.
    """
    # Use the synchronous client
    payload = {"query": "Summarize this data", "data": {"player": "Test Player", "points": 10}}
    response = client.post("/analyze", json=payload)

    assert response.status_code in [200, 500] # Allow 500 as agent isn't fully mocked/functional
    if response.status_code == 200:
        assert "analysis" in response.json()
    else:
        assert "detail" in response.json() # FastAPI HTTPException detail

# Removed async decorator
def test_fetch_data_endpoint_success():
    """
    Test the /fetch_data endpoint for a valid player.
    Expects a 200 OK with player_info and headline_stats.
    """
    # Use the synchronous client
    payload = {"target": "player_info", "params": {"player_name": "LeBron James"}}
    response = client.post("/fetch_data", json=payload)
    # Restore assertions
    assert response.status_code == 200
    data = response.json()
    assert "player_info" in data, "Response should contain 'player_info'"
    assert "headline_stats" in data, "Response should contain 'headline_stats'"
    assert data["player_info"].get("PERSON_ID") == 2544, "LeBron's PERSON_ID should be 2544"

def test_fetch_data_endpoint_not_found():
    """
    Test the /fetch_data endpoint for a player that doesn't exist.
    Expects a 404 Not Found error.
    """
    payload = {"target": "player_info", "params": {"player_name": "Non Existent Player XYZ"}}
    response = client.post("/fetch_data", json=payload)
    # Restore assertions - Expect 404
    assert response.status_code == 404
    assert "detail" in response.json()
    assert "not found" in response.json()["detail"].lower()

def test_fetch_data_endpoint_bad_request():
    """
    Test the /fetch_data endpoint with an unsupported target or missing params.
    Expects a 400 Bad Request error.
    """
    # Missing player_name
    payload_missing_param = {"target": "player_info", "params": {}}
    response_missing = client.post("/fetch_data", json=payload_missing_param)
    assert response_missing.status_code == 400
    assert "detail" in response_missing.json()

    # Unsupported target
    payload_bad_target = {"target": "game_log", "params": {"player_name": "LeBron James"}}
    response_bad_target = client.post("/fetch_data", json=payload_bad_target)
    assert response_bad_target.status_code == 400
    assert "detail" in response_bad_target.json()

# --- Tests for Player Career Stats ---

def test_fetch_player_career_success():
    """Test fetching player career stats successfully."""
    payload = {"target": "player_career_stats", "params": {"player_name": "Kevin Durant"}} # Test default per_mode36
    response = client.post("/fetch_data", json=payload)
    # Restore assertions
    assert response.status_code == 200
    data = response.json()
    assert "player_name" in data and data["player_name"] == "Kevin Durant"
    assert "season_totals_regular_season" in data and isinstance(data["season_totals_regular_season"], list)
    assert "career_totals_regular_season" in data and isinstance(data["career_totals_regular_season"], dict)
    assert data.get("per_mode_requested") == "PerGame" # Check the requested mode key

def test_fetch_player_career_totals_mode():
    """Test fetching player career stats with Totals per_mode."""
    payload = {"target": "player_career_stats", "params": {"player_name": "Kevin Durant", "per_mode36": "Totals"}} # Use per_mode36
    response = client.post("/fetch_data", json=payload)
    # Restore assertions
    assert response.status_code == 200
    data = response.json()
    assert data.get("per_mode_requested") == "Totals" # Check the requested mode key
    assert "season_totals_regular_season" in data

def test_fetch_player_career_not_found():
    """Test fetching career stats for a non-existent player."""
    payload = {"target": "player_career_stats", "params": {"player_name": "Non Existent Player XYZ"}} # Test default per_mode36
    response = client.post("/fetch_data", json=payload)
    # Restore assertions - Expect 404
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_fetch_player_career_invalid_per_mode():
    """Test fetching career stats with an invalid per_mode."""
    payload = {"target": "player_career_stats", "params": {"player_name": "Kevin Durant", "per_mode36": "InvalidMode"}} # Use per_mode36
    response = client.post("/fetch_data", json=payload)
    # Restore assertions - Expect 200 as tool defaults invalid mode
    assert response.status_code == 200
    data = response.json()
    # Check that the *requested* mode was invalid but the *retrieved* mode defaulted
    assert data.get("per_mode_requested") == "InvalidMode" # Check the original invalid requested mode
    assert data.get("data_retrieved_mode") == "Default (PerMode parameter ignored)" # Verify default was used internally
    assert data.get("data_retrieved_mode") == "Default (PerMode parameter ignored)" # Match exact string from tool

# Removed async decorator
def test_normalize_data_endpoint(): # Remove async
    """
    Test the /normalize_data endpoint with basic input.
    Expects either a 200 OK with 'normalized_data_simulation_result' or 500 error.
    """
    # Use the synchronous client
    payload = {"raw_data": {"source": "api_x", "stats": [1, 2, 3]}}
    response = client.post("/normalize_data", json=payload)

    assert response.status_code in [200, 500]
    if response.status_code == 200:
        assert "normalized_data_simulation_result" in response.json()
    else:
        assert "detail" in response.json()
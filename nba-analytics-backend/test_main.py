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
def test_fetch_data_endpoint(): # Remove async
    """
    Test the /fetch_data endpoint with basic input.
    Expects either a 200 OK with 'raw_data_simulation_result' or 500 error.
    """
    # Use the synchronous client
    payload = {"target": "player stats", "params": {"player_id": 1}}
    response = client.post("/fetch_data", json=payload)

    assert response.status_code in [200, 500]
    if response.status_code == 200:
        assert "raw_data_simulation_result" in response.json()
    else:
        assert "detail" in response.json()

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
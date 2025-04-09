import os
import sys
import pytest
import logging
import time
from api_tools.http_client import configure_nba_api_client

# Get the absolute path of the backend directory
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add the backend directory to the Python path
sys.path.insert(0, backend_dir)

@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment."""
    # Configure NBA API client with increased timeout
    configure_nba_api_client(timeout=60)
    
    # Add delay between tests to avoid rate limiting
    yield
    time.sleep(1)

@pytest.fixture
def valid_team():
    """Return a valid team name for testing."""
    return "Boston Celtics"

@pytest.fixture
def invalid_team():
    """Return an invalid team name for testing."""
    return "Invalid Team Name"

@pytest.fixture
def test_season():
    """Return a test season for testing."""
    return "2022-23"

@pytest.fixture(autouse=True)
def setup_logging():
    """Set up logging for tests."""
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger(__name__) 
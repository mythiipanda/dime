from nba_api.stats.static import players
from nba_api.stats import endpoints
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
from nba_api.stats.library.http import NBAStatsHTTP
from config import settings
from typing import Optional

logger = logging.getLogger(__name__)

# Constants for HTTP client configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 1
RETRY_STATUS_CODES = [500, 502, 503, 504]
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

def configure_nba_api_client(timeout: Optional[int] = None):
    """Configure the NBA API client with custom settings for better reliability.

    Args:
        timeout (Optional[int]): Timeout in seconds for API requests. Defaults to settings.DEFAULT_TIMEOUT_SECONDS.
    """
    try:
        session = requests.Session()
        retries = Retry(
            total=DEFAULT_MAX_RETRIES,
            backoff_factor=DEFAULT_BACKOFF_FACTOR,
            status_forcelist=RETRY_STATUS_CODES,
        )

        # Mount the retry adapter to both HTTP and HTTPS requests
        adapter = HTTPAdapter(max_retries=retries)
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        # Create NBA stats client
        nba_session = NBAStatsHTTP()

        # Configure the session
        nba_session.session = session
        nba_session.timeout = timeout or settings.DEFAULT_TIMEOUT_SECONDS
        nba_session.headers = {
            'User-Agent': DEFAULT_USER_AGENT
        }

        logger.info(f"NBA API client configured successfully with timeout {nba_session.timeout}s")
        return nba_session

    except Exception as e:
        logger.error(f"Failed to configure NBA API client: {str(e)}")
        raise

# Configure the NBA API client
nba_session = configure_nba_api_client()

# Patch the NBA API's internal requests session
players.requests = nba_session
endpoints.requests = nba_session
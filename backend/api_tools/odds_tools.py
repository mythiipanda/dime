import logging
from typing import Any, Dict
from nba_api.live.nba.library.http import NBALiveHTTP
from backend.config import DEFAULT_TIMEOUT
from backend.api_tools.utils import format_response

logger = logging.getLogger(__name__)

def fetch_odds_data_logic() -> Dict[str, Any]:
    """
    Fetches live betting odds for NBA games via NBALiveHTTP.
    Returns a dict with a "games" key or an "error" message.
    """
    logger.info("Executing fetch_odds_data_logic")
    try:
        http = NBALiveHTTP()
        response = http.send_api_request(
            endpoint="odds/odds_todaysGames.json",
            parameters={},
            proxy=None,
            headers=None,
            timeout=DEFAULT_TIMEOUT
        )
        data = response.get_dict()
        return {"games": data.get("games", [])}
    except Exception as e:
        logger.exception(f"Error fetching odds data: {e}")
        return {"error": f"Failed to fetch odds data: {str(e)}"}

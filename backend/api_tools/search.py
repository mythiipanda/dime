import logging
from typing import List, Dict
from nba_api.stats.static import players
from ..config import DEFAULT_PLAYER_SEARCH_LIMIT, MIN_PLAYER_SEARCH_LENGTH

logger = logging.getLogger(__name__)

# Cache for player list to avoid repeated calls to get_players()
_player_list_cache = None

def _get_cached_player_list() -> List[Dict]:
    """Gets the full player list, caching it after the first call."""
    global _player_list_cache
    if _player_list_cache is None:
        logger.info("Fetching and caching full player list...")
        try:
            _player_list_cache = players.get_players()
            logger.info(f"Successfully cached {len(_player_list_cache)} players.")
        except Exception as e:
            logger.error(f"Failed to fetch and cache player list: {e}", exc_info=True)
            _player_list_cache = [] # Set to empty list on error to avoid retrying constantly
    return _player_list_cache

def find_players_by_name_fragment(name_fragment: str, limit: int = DEFAULT_PLAYER_SEARCH_LIMIT) -> List[Dict]:
    """
    Finds players whose full name contains the given fragment (case-insensitive).
    Args:
        name_fragment (str): The partial name to search for.
        limit (int): The maximum number of results to return.
    Returns:
        List[Dict]: A list of matching players [{'id': player_id, 'full_name': player_name}, ...].
    """
    if not name_fragment or len(name_fragment) < MIN_PLAYER_SEARCH_LENGTH:
        return []

    all_players = _get_cached_player_list()
    if not all_players:
        return []

    name_fragment_lower = name_fragment.lower()
    matching_players = []

    try:
        for player in all_players:
            if name_fragment_lower in player['full_name'].lower():
                matching_players.append({
                    'id': player['id'],
                    'full_name': player['full_name']
                })
                if len(matching_players) >= limit:
                    break
    except Exception as e:
        logger.error(f"Error filtering player list for fragment '{name_fragment}': {e}", exc_info=True)
        return []

    logger.info(f"Found {len(matching_players)} players matching fragment '{name_fragment}' (limit {limit}).")
    return matching_players

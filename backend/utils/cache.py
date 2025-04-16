import time
import logging
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)

# Simple in-memory cache implementation
_cache: Dict[str, Dict[str, Any]] = {}

def cache_data(key: str, data: Any, ttl: int = 3600):
    """Stores data in the in-memory cache with a time-to-live (TTL).

    Args:
        key (str): The cache key.
        data (Any): The data to store (should be JSON serializable if persisted).
        ttl (int): Time-to-live in seconds. Defaults to 3600 (1 hour).
    """
    expires_at = time.time() + ttl
    _cache[key] = {"data": data, "expires_at": expires_at}
    logger.debug(f"Cached data for key '{key}' with TTL {ttl}s.")

def get_cached_data(key: str) -> Optional[Any]:
    """Retrieves data from the in-memory cache if it exists and hasn't expired.

    Args:
        key (str): The cache key.

    Returns:
        Optional[Any]: The cached data, or None if not found or expired.
    """
    cached_item = _cache.get(key)
    if cached_item:
        if time.time() < cached_item["expires_at"]:
            logger.debug(f"Cache hit for key '{key}'.")
            return cached_item["data"]
        else:
            logger.debug(f"Cache expired for key '{key}'.")
            # Remove expired item
            del _cache[key]
    else:
        logger.debug(f"Cache miss for key '{key}'.")
    return None

def clear_cache():
    """Clears the entire in-memory cache."""
    global _cache
    _cache = {}
    logger.info("In-memory cache cleared.") 
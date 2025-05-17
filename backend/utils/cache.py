"""
Provides a simple in-memory caching utility with Time-To-Live (TTL) support.
This can be used to temporarily store results of expensive operations.
"""
import time
import logging
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)

# --- Module-Level Constants and Variables ---
DEFAULT_CACHE_TTL_SECONDS: int = 3600  # Default TTL: 1 hour

# Simple in-memory cache storage
_cache: Dict[str, Dict[str, Any]] = {} # Structure: {key: {"data": ..., "expires_at": ...}}

# --- Cache Control ---
CACHE_ENABLED: bool = True # Global flag to enable/disable caching behavior

def cache_data(key: str, data: Any, ttl: int = DEFAULT_CACHE_TTL_SECONDS) -> None:
    """
    Stores data in the in-memory cache with a specified time-to-live (TTL).

    Args:
        key (str): The unique key under which to store the data.
        data (Any): The data to be cached.
        ttl (int, optional): Time-to-live for the cached item in seconds.
                             Defaults to `DEFAULT_CACHE_TTL_SECONDS`.
    """
    if not CACHE_ENABLED:
        logger.debug(f"Caching is disabled. Skipping cache_data for key '{key}'.")
        return

    expires_at = time.time() + ttl
    _cache[key] = {"data": data, "expires_at": expires_at}
    logger.debug(f"Cached data for key '{key}' with TTL {ttl}s. Expires at: {time.ctime(expires_at)}.")

def get_cached_data(key: str) -> Optional[Any]:
    """Retrieves data from the in-memory cache if it exists and hasn't expired."""
    if not CACHE_ENABLED:
        logger.debug(f"Caching disabled. Skipping get_cached_data for key '{key}'")
        return None
        
    cached_item = _cache.get(key)
    if cached_item:
        if time.time() < cached_item["expires_at"]:
            logger.debug(f"Cache hit for key '{key}'")
            return cached_item["data"]
        else:
            logger.debug(f"Cache expired for key '{key}'")
            del _cache[key] # Remove expired item
    logger.debug(f"Cache miss for key '{key}'")
    return None

def clear_cache():
    """Clears the entire in-memory cache."""
    global _cache
    _cache = {}
    logger.info("In-memory cache cleared.")
import time
import logging
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)

# Simple in-memory cache implementation
_cache: Dict[str, Dict[str, Any]] = {}

# --- Caching Disabled Temporarily ---
CACHE_ENABLED = True # Set back to True to enable caching

def cache_data(key: str, data: Any, ttl: int = 3600):
    """Stores data in the in-memory cache with a time-to-live (TTL)."""
    if not CACHE_ENABLED:
        logger.debug(f"Caching disabled. Skipping cache_data for key '{key}'")
        return
        
    expires_at = time.time() + ttl
    _cache[key] = {"data": data, "expires_at": expires_at}
    logger.debug(f"Cached data for key '{key}' with TTL {ttl}s.")

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
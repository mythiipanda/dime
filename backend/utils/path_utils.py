"""
Utility functions for handling paths in a consistent way across the codebase.
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Get the absolute path to the backend directory
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Cache directory is inside the backend directory
CACHE_DIR = os.path.join(BACKEND_DIR, "cache")

def ensure_dir_exists(directory_path: str) -> None:
    """
    Ensures that the specified directory exists, creating it if necessary.
    
    Args:
        directory_path: Path to the directory to ensure exists
    """
    try:
        os.makedirs(directory_path, exist_ok=True)
        # logger.debug(f"Ensured directory exists: {directory_path}")
    except Exception as e:
        logger.error(f"Error creating directory {directory_path}: {e}", exc_info=True)
        raise

def get_cache_dir(subdirectory: Optional[str] = None) -> str:
    """
    Gets the path to the cache directory or a subdirectory within it.
    
    Args:
        subdirectory: Optional subdirectory within the cache directory
        
    Returns:
        Path to the cache directory or subdirectory
    """
    if subdirectory:
        cache_subdir = os.path.join(CACHE_DIR, subdirectory)
        ensure_dir_exists(cache_subdir)
        return cache_subdir
    
    ensure_dir_exists(CACHE_DIR)
    return CACHE_DIR

def get_cache_file_path(filename: str, subdirectory: Optional[str] = None) -> str:
    """
    Gets the path to a file within the cache directory or a subdirectory.
    
    Args:
        filename: Name of the file
        subdirectory: Optional subdirectory within the cache directory
        
    Returns:
        Path to the file within the cache directory or subdirectory
    """
    cache_dir = get_cache_dir(subdirectory)
    return os.path.join(cache_dir, filename)

def get_relative_cache_path(filename: str, subdirectory: Optional[str] = None) -> str:
    """
    Gets the relative path to a file within the cache directory or a subdirectory,
    relative to the backend directory.
    
    Args:
        filename: Name of the file
        subdirectory: Optional subdirectory within the cache directory
        
    Returns:
        Relative path to the file within the cache directory or subdirectory
    """
    if subdirectory:
        return os.path.join("cache", subdirectory, filename)
    return os.path.join("cache", filename)

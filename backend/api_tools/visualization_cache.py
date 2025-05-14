"""
Caching module for visualizations to improve performance.
"""

import os
import json
import hashlib
import logging
import time
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Cache directory
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache", "visualizations")
# Cache expiration time (24 hours in seconds)
CACHE_EXPIRATION = 24 * 60 * 60

class VisualizationCache:
    """
    Cache for visualizations to improve performance.
    Uses a file-based cache with JSON metadata and image files.
    """
    
    @staticmethod
    def _ensure_cache_dir() -> None:
        """Ensure the cache directory exists."""
        os.makedirs(CACHE_DIR, exist_ok=True)
    
    @staticmethod
    def _generate_cache_key(params: Dict[str, Any]) -> str:
        """
        Generate a cache key from the parameters.
        
        Args:
            params: Dictionary of parameters
            
        Returns:
            Cache key string
        """
        # Convert params to a sorted string representation for consistent hashing
        param_str = json.dumps(params, sort_keys=True)
        # Generate MD5 hash
        return hashlib.md5(param_str.encode()).hexdigest()
    
    @staticmethod
    def _get_cache_metadata_path(cache_key: str) -> str:
        """Get the path to the cache metadata file."""
        return os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    @staticmethod
    def _get_cache_file_path(cache_key: str, file_ext: str) -> str:
        """Get the path to the cached file."""
        return os.path.join(CACHE_DIR, f"{cache_key}.{file_ext}")
    
    @classmethod
    def get(cls, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get a cached visualization if it exists and is not expired.
        
        Args:
            params: Dictionary of parameters
            
        Returns:
            Cached visualization data or None if not found or expired
        """
        cls._ensure_cache_dir()
        cache_key = cls._generate_cache_key(params)
        metadata_path = cls._get_cache_metadata_path(cache_key)
        
        # Check if metadata file exists
        if not os.path.exists(metadata_path):
            return None
        
        try:
            # Load metadata
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Check if cache is expired
            if time.time() - metadata.get('timestamp', 0) > CACHE_EXPIRATION:
                logger.info(f"Cache expired for key: {cache_key}")
                return None
            
            # Check if cached file exists
            file_path = metadata.get('file_path')
            if not file_path or not os.path.exists(file_path):
                logger.warning(f"Cached file not found: {file_path}")
                return None
            
            # For base64 data, load it from the metadata
            if 'image_data' in metadata or 'animation_data' in metadata:
                return metadata
            
            # For file paths, return the metadata
            return metadata
            
        except Exception as e:
            logger.error(f"Error reading cache: {e}")
            return None
    
    @classmethod
    def set(cls, params: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Cache a visualization.
        
        Args:
            params: Dictionary of parameters
            result: Visualization result to cache
        """
        cls._ensure_cache_dir()
        cache_key = cls._generate_cache_key(params)
        metadata_path = cls._get_cache_metadata_path(cache_key)
        
        try:
            # Create metadata
            metadata = {
                'params': params,
                'timestamp': time.time(),
                'chart_type': result.get('chart_type', 'unknown')
            }
            
            # Handle different result types
            if 'image_data' in result:
                metadata['image_data'] = result['image_data']
            elif 'animation_data' in result:
                metadata['animation_data'] = result['animation_data']
            elif 'file_path' in result:
                # For file paths, store the path and copy the file to the cache
                src_path = result['file_path']
                file_ext = os.path.splitext(src_path)[1][1:]  # Get extension without dot
                dst_path = cls._get_cache_file_path(cache_key, file_ext)
                
                # Copy file if it exists
                if os.path.exists(src_path):
                    import shutil
                    shutil.copy2(src_path, dst_path)
                    metadata['file_path'] = dst_path
            
            # Save metadata
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f)
                
            logger.info(f"Cached visualization with key: {cache_key}")
            
        except Exception as e:
            logger.error(f"Error caching visualization: {e}")
    
    @classmethod
    def clear_expired(cls) -> int:
        """
        Clear expired cache entries.
        
        Returns:
            Number of entries cleared
        """
        cls._ensure_cache_dir()
        cleared_count = 0
        
        try:
            # Get all metadata files
            metadata_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
            
            for metadata_file in metadata_files:
                metadata_path = os.path.join(CACHE_DIR, metadata_file)
                
                try:
                    # Load metadata
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    
                    # Check if cache is expired
                    if time.time() - metadata.get('timestamp', 0) > CACHE_EXPIRATION:
                        # Remove file if it exists
                        file_path = metadata.get('file_path')
                        if file_path and os.path.exists(file_path):
                            os.remove(file_path)
                        
                        # Remove metadata file
                        os.remove(metadata_path)
                        cleared_count += 1
                        
                except Exception as e:
                    logger.error(f"Error clearing cache entry {metadata_file}: {e}")
            
            logger.info(f"Cleared {cleared_count} expired cache entries")
            return cleared_count
            
        except Exception as e:
            logger.error(f"Error clearing expired cache: {e}")
            return 0

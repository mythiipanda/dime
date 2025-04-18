import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
import json
from backend.api_tools.player_tracking import (
    fetch_player_clutch_stats_logic,
    fetch_player_shots_tracking_logic,
    fetch_player_rebounding_stats_logic,
    fetch_player_passing_stats_logic
)
from backend.utils.cache import cache_data, get_cached_data
try:
    from backend.tools import generate_cache_key 
except ImportError:
    # Fallback definition
    def generate_cache_key(func_name: str, *args, **kwargs) -> str:
        key_parts = [func_name]
        key_parts.extend(map(str, args))
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return "_".join(key_parts)
    logging.warning("Could not import generate_cache_key from backend.tools, using fallback definition.")

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/tracking/stats")
async def fetch_player_tracking_stats(
    player_name: str = Query(...), 
    season: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Get comprehensive player tracking statistics (clutch, shots, rebounding, passing).
    Caches the combined result.
    
    Args:
        player_name (str): The name of the player to fetch tracking stats for
        season (Optional[str]): The season to fetch stats for (e.g., '2023-24')
    """
    cache_key = generate_cache_key("fetch_player_tracking_stats_endpoint", player_name, season=season)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for combined tracking stats endpoint: {cache_key}")
        try:
            return json.loads(cached_result)
        except json.JSONDecodeError:
             logger.warning(f"Failed to parse cached JSON for {cache_key}. Fetching fresh.")
             # Fall through

    logger.info(f"Cache miss for combined tracking stats. Received GET /player/tracking/stats request for player: '{player_name}', season: {season}")
    try:
        # --- Fetch individual stats (these calls might hit their own cache layers) --- 
        # Assume logic functions return JSON strings from cached tools
        
        clutch_json = fetch_player_clutch_stats_logic(player_name, season) if season else fetch_player_clutch_stats_logic(player_name)
        shots_json = fetch_player_shots_tracking_logic(player_name, season) if season else fetch_player_shots_tracking_logic(player_name)
        rebounding_json = fetch_player_rebounding_stats_logic(player_name, season) if season else fetch_player_rebounding_stats_logic(player_name)
        passing_json = fetch_player_passing_stats_logic(player_name, season) if season else fetch_player_passing_stats_logic(player_name)
        
        # --- Parse and check errors --- 
        try: clutch_result = json.loads(clutch_json)
        except json.JSONDecodeError: raise HTTPException(status_code=500, detail="Error decoding clutch stats data.")
        if isinstance(clutch_result, dict) and 'error' in clutch_result: raise HTTPException(status_code=500, detail=f"Clutch Stats Error: {clutch_result['error']}")

        try: shots_result = json.loads(shots_json)
        except json.JSONDecodeError: raise HTTPException(status_code=500, detail="Error decoding shots tracking data.")
        if isinstance(shots_result, dict) and 'error' in shots_result: raise HTTPException(status_code=500, detail=f"Shots Tracking Error: {shots_result['error']}")

        try: rebounding_result = json.loads(rebounding_json)
        except json.JSONDecodeError: raise HTTPException(status_code=500, detail="Error decoding rebounding stats data.")
        if isinstance(rebounding_result, dict) and 'error' in rebounding_result: raise HTTPException(status_code=500, detail=f"Rebounding Stats Error: {rebounding_result['error']}")

        try: passing_result = json.loads(passing_json)
        except json.JSONDecodeError: raise HTTPException(status_code=500, detail="Error decoding passing stats data.")
        if isinstance(passing_result, dict) and 'error' in passing_result: raise HTTPException(status_code=500, detail=f"Passing Stats Error: {passing_result['error']}")
            
        # --- Combine successful results --- 
        # Extract the actual stats data, handling potential missing 'stats' keys gracefully
        combined_result = {
            "player_name": player_name,
            "season": season,
            "clutch_stats": clutch_result.get("stats", clutch_result), # Fallback to full dict if 'stats' key missing
            "shots_tracking": shots_result.get("stats", shots_result),
            "rebounding_stats": rebounding_result.get("stats", rebounding_result),
            "passing_stats": passing_result.get("stats", passing_result)
        }
        
        # Cache the combined dictionary as a JSON string
        cache_data(cache_key, json.dumps(combined_result, default=str))
        return combined_result
        
    except HTTPException as http_exc:
        # Log and re-raise HTTP exceptions from parsing/error checks
        logger.error(f"HTTP error during combined tracking stats fetch: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        # Catch-all for other unexpected errors
        logger.error(f"Error fetching combined player tracking stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/tracking/clutch")
async def fetch_player_clutch_stats(
    player_name: str = Query(...),
    season: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get player clutch statistics. Caches results."""
    cache_key = generate_cache_key("fetch_player_clutch_stats_endpoint", player_name, season=season)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for clutch stats endpoint: {cache_key}")
        try: return json.loads(cached_result)
        except json.JSONDecodeError: logger.warning(f"Failed cache parse {cache_key}")
        
    logger.info(f"Cache miss GET /player/tracking/clutch for: '{player_name}', season: {season}")
    try:
        result_json_string = fetch_player_clutch_stats_logic(player_name, season) if season else fetch_player_clutch_stats_logic(player_name)
        # Validate and parse
        try: result_data = json.loads(result_json_string)
        except json.JSONDecodeError: raise HTTPException(status_code=500, detail="Invalid data from clutch service.")
        if isinstance(result_data, dict) and 'error' in result_data: raise HTTPException(status_code=500, detail=result_data['error'])
        cache_data(cache_key, result_json_string)
        return result_data
    except HTTPException as http_exc: raise http_exc
    except Exception as e:
        logger.error(f"Error fetching player clutch stats endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tracking/shots")
async def fetch_player_shots_tracking(
    player_name: str = Query(...),
    season: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get player shots tracking statistics. Caches results."""
    cache_key = generate_cache_key("fetch_player_shots_tracking_endpoint", player_name, season=season)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for shots tracking endpoint: {cache_key}")
        try: return json.loads(cached_result)
        except json.JSONDecodeError: logger.warning(f"Failed cache parse {cache_key}")

    logger.info(f"Cache miss GET /player/tracking/shots for: '{player_name}', season: {season}")
    try:
        result_json_string = fetch_player_shots_tracking_logic(player_name, season) if season else fetch_player_shots_tracking_logic(player_name)
        # Validate and parse
        try: result_data = json.loads(result_json_string)
        except json.JSONDecodeError: raise HTTPException(status_code=500, detail="Invalid data from shots service.")
        if isinstance(result_data, dict) and 'error' in result_data: raise HTTPException(status_code=500, detail=result_data['error'])
        cache_data(cache_key, result_json_string)
        return result_data
    except HTTPException as http_exc: raise http_exc
    except Exception as e:
        logger.error(f"Error fetching player shots tracking endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tracking/rebounding")
async def fetch_player_rebounding_stats(
    player_name: str = Query(...),
    season: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get player rebounding statistics. Caches results."""
    cache_key = generate_cache_key("fetch_player_rebounding_stats_endpoint", player_name, season=season)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for rebounding stats endpoint: {cache_key}")
        try: return json.loads(cached_result)
        except json.JSONDecodeError: logger.warning(f"Failed cache parse {cache_key}")

    logger.info(f"Cache miss GET /player/tracking/rebounding for: '{player_name}', season: {season}")
    try:
        result_json_string = fetch_player_rebounding_stats_logic(player_name, season) if season else fetch_player_rebounding_stats_logic(player_name)
        # Validate and parse
        try: result_data = json.loads(result_json_string)
        except json.JSONDecodeError: raise HTTPException(status_code=500, detail="Invalid data from rebounding service.")
        if isinstance(result_data, dict) and 'error' in result_data: raise HTTPException(status_code=500, detail=result_data['error'])
        cache_data(cache_key, result_json_string)
        return result_data
    except HTTPException as http_exc: raise http_exc
    except Exception as e:
        logger.error(f"Error fetching player rebounding stats endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tracking/passing")
async def fetch_player_passing_stats(
    player_name: str = Query(...),
    season: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get player passing statistics. Caches results."""
    cache_key = generate_cache_key("fetch_player_passing_stats_endpoint", player_name, season=season)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for passing stats endpoint: {cache_key}")
        try: return json.loads(cached_result)
        except json.JSONDecodeError: logger.warning(f"Failed cache parse {cache_key}")

    logger.info(f"Cache miss GET /player/tracking/passing for: '{player_name}', season: {season}")
    try:
        result_json_string = fetch_player_passing_stats_logic(player_name, season) if season else fetch_player_passing_stats_logic(player_name)
        # Validate and parse
        try: result_data = json.loads(result_json_string)
        except json.JSONDecodeError: raise HTTPException(status_code=500, detail="Invalid data from passing service.")
        if isinstance(result_data, dict) and 'error' in result_data: raise HTTPException(status_code=500, detail=result_data['error'])
        cache_data(cache_key, result_json_string)
        return result_data
    except HTTPException as http_exc: raise http_exc
    except Exception as e:
        logger.error(f"Error fetching player passing stats endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 
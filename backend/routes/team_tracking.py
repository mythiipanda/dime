import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
import json
from backend.api_tools.team_tracking import (
    fetch_team_passing_stats_logic,
    fetch_team_rebounding_stats_logic,
    fetch_team_shooting_stats_logic
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
async def fetch_team_tracking_stats(
    team_name: str = Query(...),
    season: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Get comprehensive team tracking statistics (passing, rebounding, shooting).
    Caches the combined result.
    
    Args:
        team_name (str): The name of the team to fetch tracking stats for
        season (Optional[str]): The season to fetch stats for (e.g., '2023-24')
    """
    cache_key = generate_cache_key("fetch_team_tracking_stats_endpoint", team_name, season=season)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for combined team tracking stats endpoint: {cache_key}")
        try:
            return json.loads(cached_result)
        except json.JSONDecodeError:
             logger.warning(f"Failed to parse cached JSON for {cache_key}. Fetching fresh.")
             # Fall through

    logger.info(f"Cache miss for combined team tracking stats. Received GET /team/tracking/stats request for team: '{team_name}', season: {season}")
    try:
        # Get passing stats
        passing_result = json.loads(fetch_team_passing_stats_logic(team_name, season) if season else fetch_team_passing_stats_logic(team_name))
        if "error" in passing_result:
            return {"error": passing_result["error"]}
            
        # Get rebounding stats
        rebounding_result = json.loads(fetch_team_rebounding_stats_logic(team_name, season) if season else fetch_team_rebounding_stats_logic(team_name))
        if "error" in rebounding_result:
            return {"error": rebounding_result["error"]}
            
        # Get shooting stats
        shooting_result = json.loads(fetch_team_shooting_stats_logic(team_name, season) if season else fetch_team_shooting_stats_logic(team_name))
        if "error" in shooting_result:
            return {"error": shooting_result["error"]}
            
        # Combine all results
        result = {
            "team_name": team_name,
            "season": season,
            "passing_stats": passing_result.get("stats", {}),
            "rebounding_stats": rebounding_result.get("stats", {}),
            "shooting_stats": shooting_result.get("stats", {})
        }
        
        # Cache the combined dictionary as a JSON string
        cache_data(cache_key, json.dumps(result, default=str))
        return result
    except Exception as e:
        logger.error(f"Error fetching team tracking stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tracking/passing")
async def fetch_team_passing_stats(
    team_name: str = Query(...),
    season: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get team passing statistics. Caches results."""
    cache_key = generate_cache_key("fetch_team_passing_stats_endpoint", team_name, season=season)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for team passing stats endpoint: {cache_key}")
        try: return json.loads(cached_result)
        except json.JSONDecodeError: logger.warning(f"Failed cache parse {cache_key}")
        
    logger.info(f"Cache miss GET /team/tracking/passing for: '{team_name}', season: {season}")
    try:
        result = fetch_team_passing_stats_logic(team_name, season) if season else fetch_team_passing_stats_logic(team_name)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error fetching team passing stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tracking/rebounding")
async def fetch_team_rebounding_stats(
    team_name: str = Query(...),
    season: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get team rebounding statistics. Caches results."""
    cache_key = generate_cache_key("fetch_team_rebounding_stats_endpoint", team_name, season=season)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for team rebounding stats endpoint: {cache_key}")
        try: return json.loads(cached_result)
        except json.JSONDecodeError: logger.warning(f"Failed cache parse {cache_key}")

    logger.info(f"Cache miss GET /team/tracking/rebounding for: '{team_name}', season: {season}")
    try:
        result = fetch_team_rebounding_stats_logic(team_name, season) if season else fetch_team_rebounding_stats_logic(team_name)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error fetching team rebounding stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tracking/shooting")
async def fetch_team_shooting_stats(
    team_name: str = Query(...),
    season: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get team shooting statistics. Caches results."""
    cache_key = generate_cache_key("fetch_team_shooting_stats_endpoint", team_name, season=season)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for team shooting stats endpoint: {cache_key}")
        try: return json.loads(cached_result)
        except json.JSONDecodeError: logger.warning(f"Failed cache parse {cache_key}")

    logger.info(f"Cache miss GET /team/tracking/shooting for: '{team_name}', season: {season}")
    try:
        result = fetch_team_shooting_stats_logic(team_name, season) if season else fetch_team_shooting_stats_logic(team_name)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error fetching team shooting stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 
import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
import json
from backend.api_tools.player_tools import (
    get_player_headshot_url,
    fetch_player_stats_logic,
    fetch_player_profile_logic,
)
from backend.api_tools.search import find_players_by_name_fragment
from backend.utils.cache import cache_data, get_cached_data

try:
    from backend.tools import generate_cache_key 
except ImportError:
    def generate_cache_key(func_name: str, *args, **kwargs) -> str:
        key_parts = [func_name]
        key_parts.extend(map(str, args))
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return "_".join(key_parts)
    logging.warning("Could not import generate_cache_key from backend.tools, using fallback definition.")

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/player/{player_id}/headshot")
async def get_player_headshot_by_id(player_id: int):
    cache_key = generate_cache_key("get_player_headshot_by_id", player_id)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for headshot endpoint: {cache_key}")
        try:
            return json.loads(cached_result) 
        except json.JSONDecodeError:
             logger.warning(f"Failed to parse cached JSON for {cache_key}. Fetching fresh.")
             # Fall through to fetch fresh data

    logger.info(f"Cache miss for headshot endpoint. Received GET /player/{player_id}/headshot request.")
    if player_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid player_id provided.")
    try:
        headshot_url = get_player_headshot_url(player_id)
        result = {"player_id": player_id, "headshot_url": headshot_url}
        cache_data(cache_key, json.dumps(result)) 
        return result
    except Exception as e:
        logger.exception(f"Unexpected error fetching headshot for player ID {player_id}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/search", response_model=List[Dict[str, Any]])
async def search_players_by_name(
    q: Optional[str] = Query(None, description="Search query for player name"), 
    limit: int = Query(10, description="Maximum number of results to return")
):
    if not q or len(q) < 2:
        return []

    cache_key = generate_cache_key("search_players_by_name", q=q, limit=limit)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for search endpoint: {cache_key}")
        try:
            return json.loads(cached_result)
        except json.JSONDecodeError:
             logger.warning(f"Failed to parse cached JSON for {cache_key}. Fetching fresh.")
             # Fall through

    logger.info(f"Cache miss for search endpoint. Received GET /search request with query: '{q}', limit: {limit}")
    try:
        results = find_players_by_name_fragment(q, limit=limit)
        logger.info(f"Returning {len(results)} players for search query '{q}'")
        cache_data(cache_key, json.dumps(results))
        return results
    except Exception as e:
        logger.exception(f"Unexpected error during player search for query '{q}'")
        raise HTTPException(status_code=500, detail=f"Internal server error during player search: {str(e)}")

@router.get("/stats")
async def fetch_player_stats_endpoint(player_name: str, season: Optional[str] = None) -> Dict[str, Any]:
    cache_key = generate_cache_key("fetch_player_stats_endpoint", player_name, season=season)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for stats endpoint: {cache_key}")
        try:
            return json.loads(cached_result)
        except json.JSONDecodeError:
             logger.warning(f"Failed to parse cached JSON for {cache_key}. Fetching fresh.")
             # Fall through

    logger.info(f"Cache miss for stats endpoint. Received GET /stats request for player: '{player_name}', season: {season}")
    try:
        result_json_string = fetch_player_stats_logic(player_name, season) if season else fetch_player_stats_logic(player_name)
        
        try:
            result_data = json.loads(result_json_string)
        except json.JSONDecodeError:
             logger.error(f"Failed to parse JSON from fetch_player_stats_logic for {player_name}, season {season}. Response: {result_json_string}")
             raise HTTPException(status_code=500, detail="Internal server error: Invalid data format from service.")

        if isinstance(result_data, dict) and 'error' in result_data:
             logger.error(f"Error from fetch_player_stats_logic: {result_data['error']}")
             status_code = 404 if "not found" in result_data['error'].lower() else 500
             raise HTTPException(status_code=status_code, detail=result_data['error'])

        cache_data(cache_key, result_json_string) 
        return result_data
        
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error fetching player stats endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/profile")
async def fetch_player_profile_endpoint(player_name: str) -> Dict[str, Any]:
    cache_key = generate_cache_key("fetch_player_profile_endpoint", player_name)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for profile endpoint: {cache_key}")
        try:
            return json.loads(cached_result)
        except json.JSONDecodeError:
             logger.warning(f"Failed to parse cached JSON for {cache_key}. Fetching fresh.")
             # Fall through

    logger.info(f"Cache miss for profile endpoint. Received GET /profile request for player: '{player_name}'")
    try:
        result_json_string = fetch_player_profile_logic(player_name)
        
        try:
            result_data = json.loads(result_json_string)
        except json.JSONDecodeError as json_err:
            logger.error(f"Failed to parse JSON response from fetch_player_profile_logic: {json_err}. Response: {result_json_string}")
            raise HTTPException(status_code=500, detail="Internal server error: Invalid data format from service.")
        
        if isinstance(result_data, dict) and 'error' in result_data:
            logger.error(f"Error fetching player profile from logic: {result_data['error']}")
            status_code = 404 if "not found" in result_data['error'].lower() else 500
            raise HTTPException(status_code=status_code, detail=result_data['error'])
            
        cache_data(cache_key, result_json_string)
        return result_data
        
    except HTTPException as http_exc:
         raise http_exc
    except Exception as e:
        logger.error(f"Error fetching player profile endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
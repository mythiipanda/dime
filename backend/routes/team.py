import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import json # Import json for serialization/deserialization
from fastapi import Query  # Import Query for GET parameters
from backend.api_tools.team_tools import (
    fetch_team_info_and_roster_logic,
    fetch_team_stats_logic
)
from backend.api_tools.team_tracking import (
    fetch_team_passing_stats_logic,
    fetch_team_rebounding_stats_logic,
    fetch_team_shooting_stats_logic
)
from backend.config import DEFAULT_TIMEOUT, CURRENT_SEASON, Errors
# Import cache utilities and generate_cache_key helper function
from backend.utils.cache import cache_data, get_cached_data
try:
    from backend.tools import generate_cache_key 
except ImportError:
    # Fallback definition if import fails (adjust if needed)
    def generate_cache_key(func_name: str, *args, **kwargs) -> str:
        key_parts = [func_name]
        key_parts.extend(map(str, args))
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return "_".join(key_parts)
    logging.warning("Could not import generate_cache_key from backend.tools, using fallback definition.")


router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/stats")
async def fetch_team_stats(team_name: str, season: Optional[str] = None) -> Dict[str, Any]:
    """
    Get comprehensive team statistics. Caches results based on team name and season.
    
    Args:
        team_name (str): The name of the team to fetch stats for
        season (Optional[str]): The season to fetch stats for (e.g., '2023-24')
    """
    cache_key = generate_cache_key("fetch_team_stats_endpoint", team_name, season=season)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for team stats endpoint: {cache_key}")
        try:
            return json.loads(cached_result)
        except json.JSONDecodeError:
             logger.warning(f"Failed to parse cached JSON for {cache_key}. Fetching fresh.")
             # Fall through

    logger.info(f"Cache miss for team stats endpoint. Received GET /stats request for team: '{team_name}', season: {season}")
    try:
        # Assuming fetch_team_stats_logic returns a JSON string (as it calls a cached tool)
        result_json_string = fetch_team_stats_logic(team_name=team_name, season=season)
        
        # Validate and parse before caching
        try:
            result_data = json.loads(result_json_string)
        except json.JSONDecodeError:
             logger.error(f"Failed to parse JSON from fetch_team_stats_logic for {team_name}, season {season}. Response: {result_json_string}")
             raise HTTPException(status_code=500, detail="Internal server error: Invalid data format from service.")

        # Check for errors returned by the logic function
        if isinstance(result_data, dict) and 'error' in result_data:
            logger.error(f"Error from fetch_team_stats_logic: {result_data['error']}")
            status_code = 404 if "not found" in result_data['error'].lower() else 500
            raise HTTPException(status_code=status_code, detail=result_data['error'])

        # Cache the valid JSON string result
        cache_data(cache_key, result_json_string)
        return result_data # Return the parsed dictionary

    except HTTPException as http_exc:
        raise http_exc # Re-raise HTTPExceptions
    except Exception as e:
        logger.error(f"Error fetching team stats endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/info")
async def fetch_team_info(team_name: str, season: Optional[str] = None) -> Dict[str, Any]:
    """
    Get team information and roster. Caches results based on team name and season.
    
    Args:
        team_name (str): The name of the team to fetch info for
        season (Optional[str]): The season to fetch info for (e.g., '2023-24')
    """
    cache_key = generate_cache_key("fetch_team_info_endpoint", team_name, season=season)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for team info endpoint: {cache_key}")
        try:
            return json.loads(cached_result)
        except json.JSONDecodeError:
             logger.warning(f"Failed to parse cached JSON for {cache_key}. Fetching fresh.")
             # Fall through

    logger.info(f"Cache miss for team info endpoint. Received GET /info request for team: '{team_name}', season: {season}")
    try:
        # Assuming fetch_team_info_and_roster_logic returns a JSON string
        result_json_string = fetch_team_info_and_roster_logic(team_name=team_name, season=season)
        
        # Validate and parse
        try:
            result_data = json.loads(result_json_string)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from fetch_team_info_and_roster_logic for {team_name}, season {season}. Response: {result_json_string}")
            raise HTTPException(status_code=500, detail="Internal server error: Invalid data format from service.")

        if isinstance(result_data, dict) and 'error' in result_data:
            logger.error(f"Error from fetch_team_info_and_roster_logic: {result_data['error']}")
            status_code = 404 if "not found" in result_data['error'].lower() else 500
            raise HTTPException(status_code=status_code, detail=result_data['error'])

        cache_data(cache_key, result_json_string)
        return result_data

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error fetching team info endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/passing")
async def get_team_passing_stats(
    team_name: str = Query(...),
    season: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Get team passing statistics. Caches results based on team name and season.
    """
    cache_key = generate_cache_key("get_team_passing_stats_endpoint", team_name, season=season)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for team passing stats endpoint: {cache_key}")
        try:
            return json.loads(cached_result)
        except json.JSONDecodeError:
             logger.warning(f"Failed to parse cached JSON for {cache_key}. Fetching fresh.")
             # Fall through

    logger.info(f"Cache miss for team passing stats. Received GET /passing request for team: '{team_name}', season: {season}")
    try:
        # Assuming logic returns JSON string
        result_json_string = fetch_team_passing_stats_logic(team_name=team_name, season=season)
        
        # Validate and parse
        try:
             result_data = json.loads(result_json_string)
        except json.JSONDecodeError:
             logger.error(f"Failed to parse JSON from fetch_team_passing_stats_logic for {team_name}, season {season}. Response: {result_json_string}")
             raise HTTPException(status_code=500, detail="Internal server error: Invalid data format from service.")

        if isinstance(result_data, dict) and 'error' in result_data:
            logger.error(f"Error from fetch_team_passing_stats_logic: {result_data['error']}")
            status_code = 404 if "not found" in result_data['error'].lower() else 500
            raise HTTPException(status_code=status_code, detail=result_data['error'])

        cache_data(cache_key, result_json_string)
        return result_data
        
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error getting team passing stats endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/rebounding")
async def get_team_rebounding_stats(
    team_name: str = Query(...),
    season: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Get team rebounding statistics. Caches results based on team name and season.
    """
    cache_key = generate_cache_key("get_team_rebounding_stats_endpoint", team_name, season=season)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for team rebounding stats endpoint: {cache_key}")
        try:
            return json.loads(cached_result)
        except json.JSONDecodeError:
             logger.warning(f"Failed to parse cached JSON for {cache_key}. Fetching fresh.")
             # Fall through

    logger.info(f"Cache miss for team rebounding stats. Received GET /rebounding request for team: '{team_name}', season: {season}")
    try:
        # Assuming logic returns JSON string
        result_json_string = fetch_team_rebounding_stats_logic(team_name=team_name, season=season)
        
        # Validate and parse
        try:
             result_data = json.loads(result_json_string)
        except json.JSONDecodeError:
             logger.error(f"Failed to parse JSON from fetch_team_rebounding_stats_logic for {team_name}, season {season}. Response: {result_json_string}")
             raise HTTPException(status_code=500, detail="Internal server error: Invalid data format from service.")

        if isinstance(result_data, dict) and 'error' in result_data:
            logger.error(f"Error from fetch_team_rebounding_stats_logic: {result_data['error']}")
            status_code = 404 if "not found" in result_data['error'].lower() else 500
            raise HTTPException(status_code=status_code, detail=result_data['error'])

        cache_data(cache_key, result_json_string)
        return result_data

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error getting team rebounding stats endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/shooting")
async def get_team_shooting_stats(
    team_name: str = Query(...),
    season: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Get team shooting statistics. Caches results based on team name and season.
    """
    cache_key = generate_cache_key("get_team_shooting_stats_endpoint", team_name, season=season)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for team shooting stats endpoint: {cache_key}")
        try:
            return json.loads(cached_result)
        except json.JSONDecodeError:
             logger.warning(f"Failed to parse cached JSON for {cache_key}. Fetching fresh.")
             # Fall through

    logger.info(f"Cache miss for team shooting stats. Received GET /shooting request for team: '{team_name}', season: {season}")
    try:
        # Assuming logic returns JSON string
        result_json_string = fetch_team_shooting_stats_logic(team_name=team_name, season=season)
        
        # Validate and parse
        try:
             result_data = json.loads(result_json_string)
        except json.JSONDecodeError:
             logger.error(f"Failed to parse JSON from fetch_team_shooting_stats_logic for {team_name}, season {season}. Response: {result_json_string}")
             raise HTTPException(status_code=500, detail="Internal server error: Invalid data format from service.")

        if isinstance(result_data, dict) and 'error' in result_data:
            logger.error(f"Error from fetch_team_shooting_stats_logic: {result_data['error']}")
            status_code = 404 if "not found" in result_data['error'].lower() else 500
            raise HTTPException(status_code=status_code, detail=result_data['error'])

        cache_data(cache_key, result_json_string)
        return result_data

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error getting team shooting stats endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") 
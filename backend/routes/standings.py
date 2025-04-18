from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
import json
from nba_api.stats.library.parameters import SeasonType
from backend.api_tools.league_tools import fetch_league_standings_logic
import logging
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

@router.get("/standings")
async def get_standings(
    season: Optional[str] = Query(None, description="Season in YYYY-YY format (e.g., \"2023-24\")"), 
    season_type: str = Query(SeasonType.regular, description="Season type (e.g., Regular Season, Playoffs)")
) -> Dict[str, Any]:
    """
    Get NBA league standings. Caches results based on season and season type.

    Args:
        season: Optional season in YYYY-YY format (e.g., "2023-24")
        season_type: Season type (default: Regular Season)
    """
    cache_key = generate_cache_key("get_standings_endpoint", season=season, season_type=season_type)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for standings endpoint: {cache_key}")
        try:
            return json.loads(cached_result)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse cached JSON for {cache_key}. Fetching fresh.")
            # Fall through

    logger.info(f"Cache miss for standings endpoint. Fetching standings for season: {season}, type: {season_type}")
    try:
        # Assuming logic returns JSON string
        result_json_string = fetch_league_standings_logic(season=season, season_type=season_type)
        
        # Validate and parse
        try:
            result_data = json.loads(result_json_string)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from fetch_league_standings_logic for season {season}, type {season_type}. Response: {result_json_string}")
            raise HTTPException(status_code=500, detail="Internal server error: Invalid data format from standings service.")

        # Check for errors from logic
        if isinstance(result_data, dict) and 'error' in result_data:
            logger.error(f"Error from fetch_league_standings_logic: {result_data['error']}")
            # Standings errors are less likely to be 404s unless season is invalid
            raise HTTPException(status_code=500, detail=result_data['error'])
        
        # Cache the valid result
        cache_data(cache_key, result_json_string)
        return result_data

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error fetching standings endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
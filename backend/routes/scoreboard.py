from fastapi import APIRouter, Query, HTTPException, status
import logging
from typing import Any, Dict, Optional
from datetime import date
import json # Import json

# Import the unified logic function
from backend.api_tools.scoreboard.scoreboard_tools import fetch_scoreboard_data_logic
from backend.api_tools.utils import validate_date_format # For validation if needed here
# Import cache utilities and key generator
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


logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", 
            summary="Get Scoreboard by Date", 
            description="Fetches NBA scoreboard data for a specific date (YYYY-MM-DD). Defaults to today if no date is provided. Results are cached.",
            response_description="A dictionary containing the game date and a list of games.",
            tags=["Scoreboard"])
async def get_scoreboard_endpoint(
    game_date: Optional[str] = Query(default=None, description="Date in YYYY-MM-DD format. Defaults to today.")
) -> Dict[str, Any]:
    """
    API endpoint to retrieve scoreboard data for a given date. Caches results.
    """
    # Determine the effective date for logging and cache key
    effective_game_date = game_date or date.today().strftime('%Y-%m-%d')
    
    cache_key = generate_cache_key("get_scoreboard_endpoint", game_date=effective_game_date)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for scoreboard endpoint: {cache_key}")
        try:
            return json.loads(cached_result)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse cached JSON for {cache_key}. Fetching fresh.")
            # Fall through

    logger.info(f"Cache miss for scoreboard endpoint. Received request for scoreboard data for date: {effective_game_date}.")
    
    # Basic validation can happen here, or rely on the logic function
    if game_date and not validate_date_format(game_date):
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST, 
             detail=f"Invalid date format: {game_date}. Use YYYY-MM-DD."
         )

    try:
        # Pass the original date (or None) to the logic function
        # Assuming the logic function returns a dictionary
        result_dict = fetch_scoreboard_data_logic(game_date=game_date) 
        
        # Check for errors before caching
        if isinstance(result_dict, dict) and 'error' in result_dict:
            logger.error(f"Error fetching scoreboard from logic: {result_dict['error']}")
            status_code = status.HTTP_502_BAD_GATEWAY if "Failed to fetch" in result_dict['error'] else status.HTTP_500_INTERNAL_SERVER_ERROR
            if "Invalid date format" in result_dict['error']:
                status_code = status.HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=status_code, detail=result_dict['error'])
        
        logger.info(f"Successfully retrieved scoreboard data for {result_dict.get('gameDate', effective_game_date)}.")
        
        # Cache the successful result dictionary as a JSON string
        cache_data(cache_key, json.dumps(result_dict, default=str))
        return result_dict

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception("Unhandled exception in scoreboard endpoint", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                            detail=f"An unexpected error occurred: {str(e)}") 
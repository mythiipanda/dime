import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
from backend.api_tools.game_tools import (
    fetch_boxscore_traditional_logic as fetch_game_boxscore_logic,
    fetch_playbyplay_logic as fetch_game_playbyplay_logic,
    fetch_shotchart_logic as fetch_game_shotchart_logic,
)
from backend.api_tools.league_tools import fetch_scoreboard_logic # Import correct scoreboard logic
import json
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

@router.get("/boxscore/{game_id}")
async def get_game_boxscore(game_id: str) -> Dict[str, Any]:
    """
    Get game boxscore. Caches results based on game_id.
    """
    cache_key = generate_cache_key("get_game_boxscore_endpoint", game_id)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for boxscore endpoint: {cache_key}")
        try:
            return json.loads(cached_result)
        except json.JSONDecodeError:
             logger.warning(f"Failed to parse cached JSON for {cache_key}. Fetching fresh.")
             # Fall through

    logger.info(f"Cache miss for boxscore endpoint. Received GET /boxscore/{game_id} request.")
    if not game_id or len(game_id) != 10: # Basic validation for game_id format
         raise HTTPException(status_code=400, detail="Valid 10-digit game_id path parameter is required")
         
    try:
        # Assuming logic returns dict, needs dump to JSON string for caching
        result_dict = fetch_game_boxscore_logic(game_id)

        # Check for errors returned by the logic function
        if isinstance(result_dict, dict) and 'error' in result_dict:
            logger.error(f"Error from fetch_game_boxscore_logic: {result_dict['error']}")
            # Use 404 if game not found, otherwise 500
            status_code = 404 if "not found" in result_dict['error'].lower() else 500
            raise HTTPException(status_code=status_code, detail=result_dict['error'])
        
        # Convert dict to JSON string for caching
        result_json_string = json.dumps(result_dict, default=str) 
        cache_data(cache_key, result_json_string)
        return result_dict # Return the original dictionary

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error getting game boxscore endpoint for {game_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/playbyplay/{game_id}")
async def get_game_playbyplay(
    game_id: str, 
    start_period: int = Query(0, description="Optional start period filter (1-based)"),
    end_period: int = Query(0, description="Optional end period filter (1-based)")
) -> Dict[str, Any]:
    """
    Get game play-by-play data. Caches results only if data is historical (game finished).
    """
    cache_key = generate_cache_key("get_game_playbyplay_endpoint", game_id, start_period=start_period, end_period=end_period)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        # Only return cached if it was confirmed historical previously
        try:
            cached_data = json.loads(cached_result)
            if cached_data.get("source") == "historical":
                 logger.debug(f"Cache hit for historical PBP endpoint: {cache_key}")
                 return cached_data
            else:
                 logger.debug(f"Cache hit for PBP {cache_key}, but wasn't historical. Fetching fresh.")
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse cached PBP JSON for {cache_key}. Fetching fresh.")
            # Fall through
            
    logger.info(f"Cache miss or non-historical hit for PBP endpoint. Received GET /playbyplay/{game_id} request.")
    if not game_id or len(game_id) != 10:
         raise HTTPException(status_code=400, detail="Valid 10-digit game_id path parameter is required")

    try:
        # Logic function returns a JSON string
        result_json_string = fetch_game_playbyplay_logic(game_id=game_id, start_period=start_period, end_period=end_period)
        
        # Parse and validate
        try:
            result_data = json.loads(result_json_string)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from fetch_game_playbyplay_logic for {game_id}. Response: {result_json_string}")
            raise HTTPException(status_code=500, detail="Internal server error: Invalid data format from PBP service.")

        # Check for errors from logic
        if isinstance(result_data, dict) and "error" in result_data:
             logger.error(f"Play-by-play logic failed for game {game_id}: {result_data['error']}")
             status_code = 404 if "not found" in result_data['error'].lower() else 500
             raise HTTPException(status_code=status_code, detail=result_data['error'])

        # Cache ONLY if the source was historical
        if result_data.get("source") == "historical":
            logger.debug(f"Caching historical PBP result for {cache_key}")
            cache_data(cache_key, result_json_string)
        else:
            logger.debug(f"Not caching non-historical PBP for game {game_id}")
            
        return result_data # Return the parsed dictionary
            
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error getting PBP endpoint for {game_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/shotchart/{game_id}")
async def get_game_shotchart(
    game_id: str,
    team_id: Optional[int] = Query(None, description="Optional team ID filter"), # Add query params
    player_id: Optional[int] = Query(None, description="Optional player ID filter") # Add query params
) -> Dict[str, Any]:
    """
    Get game shot chart data. Caches results based on game_id and optional filters.
    Note: team_id and player_id filters are not yet implemented in the underlying logic.
    """
    cache_key = generate_cache_key("get_game_shotchart_endpoint", game_id, team_id=team_id, player_id=player_id)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for shotchart endpoint: {cache_key}")
        try:
            return json.loads(cached_result)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse cached JSON for {cache_key}. Fetching fresh.")
            # Fall through
            
    logger.info(f"Cache miss for shotchart endpoint. Received GET /shotchart/{game_id} request.")
    if not game_id or len(game_id) != 10:
         raise HTTPException(status_code=400, detail="Valid 10-digit game_id path parameter is required")

    # Log warning if filters are used but not implemented yet
    if team_id or player_id:
        logger.warning(f"Team/Player filters provided for {game_id} shotchart, but not yet implemented in logic.")
        
    try:
        # Assuming logic returns JSON string
        # TODO: Update logic function to accept team_id/player_id when implemented
        result_json_string = fetch_game_shotchart_logic(game_id)
        
        # Validate and parse
        try:
            result_data = json.loads(result_json_string)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from fetch_game_shotchart_logic for {game_id}. Response: {result_json_string}")
            raise HTTPException(status_code=500, detail="Internal server error: Invalid data format from shotchart service.")

        if isinstance(result_data, dict) and 'error' in result_data:
            logger.error(f"Error from fetch_game_shotchart_logic: {result_data['error']}")
            status_code = 404 if "not found" in result_data['error'].lower() else 500
            raise HTTPException(status_code=status_code, detail=result_data['error'])

        cache_data(cache_key, result_json_string)
        return result_data

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error getting game shot chart endpoint for {game_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/league/scoreboard")
async def get_league_scoreboard(
    game_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format. Defaults to today."),
    day_offset: int = Query(0, description="Day offset from game_date. Defaults to 0.")
) -> Dict[str, Any]:
    """
    Get league scoreboard for a specific date. Caches results based on date and offset.
    """
    # Note: The underlying logic function `fetch_scoreboard_logic` handles the default game_date if None
    # We need the actual date used for the cache key.
    import datetime
    final_game_date = game_date or datetime.date.today().strftime('%Y-%m-%d')
    
    cache_key = generate_cache_key("get_league_scoreboard_endpoint", game_date=final_game_date, day_offset=day_offset)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for scoreboard endpoint: {cache_key}")
        try:
            return json.loads(cached_result)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse cached JSON for {cache_key}. Fetching fresh.")
            # Fall through
            
    logger.info(f"Cache miss for scoreboard endpoint. Received GET /league/scoreboard request for date {game_date}, offset {day_offset}.")
    try:
        # Assuming logic returns JSON string
        result_json_string = fetch_scoreboard_logic(game_date=game_date, day_offset=day_offset)
        
        # Validate and parse
        try:
            result_data = json.loads(result_json_string)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from fetch_scoreboard_logic for date {game_date}, offset {day_offset}. Response: {result_json_string}")
            raise HTTPException(status_code=500, detail="Internal server error: Invalid data format from scoreboard service.")

        if isinstance(result_data, dict) and 'error' in result_data:
            logger.error(f"Error from fetch_scoreboard_logic: {result_data['error']}")
            # Scoreboard errors are less likely to be 404s
            raise HTTPException(status_code=500, detail=result_data['error'])

        cache_data(cache_key, result_json_string)
        return result_data

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error getting league scoreboard endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
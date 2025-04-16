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

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/player/{player_id}/headshot")
async def get_player_headshot_by_id(player_id: int):
    logger.info(f"Received GET /player/{player_id}/headshot request.")
    if player_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid player_id provided.")
    try:
        headshot_url = get_player_headshot_url(player_id)
        return {"player_id": player_id, "headshot_url": headshot_url}
    except Exception as e:
        logger.exception(f"Unexpected error fetching headshot for player ID {player_id}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/search", response_model=List[Dict[str, Any]])
async def search_players_by_name(
    q: Optional[str] = Query(None, description="Search query for player name"), 
    limit: int = Query(10, description="Maximum number of results to return")
):
    logger.info(f"Received GET /search request with query: '{q}', limit: {limit}")
    if not q or len(q) < 2:
        return []
    try:
        results = find_players_by_name_fragment(q, limit=limit)
        logger.info(f"Returning {len(results)} players for search query '{q}'")
        return results
    except Exception as e:
        logger.exception(f"Unexpected error during player search for query '{q}'")
        raise HTTPException(status_code=500, detail=f"Internal server error during player search: {str(e)}")

@router.get("/stats")
async def fetch_player_stats_endpoint(player_name: str, season: Optional[str] = None) -> Dict[str, Any]:
    """
    Get comprehensive player statistics.
    
    Args:
        player_name (str): The name of the player to fetch stats for
        season (Optional[str]): The season to fetch stats for (e.g., '2023-24')
    """
    logger.info(f"Received GET /stats request for player: '{player_name}', season: {season}")
    try:
        result = fetch_player_stats_logic(player_name, season) if season else fetch_player_stats_logic(player_name)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error fetching player stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/profile")
async def fetch_player_profile_endpoint(player_name: str) -> Dict[str, Any]:
    """
    Get comprehensive player profile including career totals, season totals, highs etc.
    
    Args:
        player_name (str): The name of the player to fetch profile for
    """
    logger.info(f"Received GET /profile request for player: '{player_name}'")
    try:
        result_json_string = fetch_player_profile_logic(player_name)
        result_data = json.loads(result_json_string)
        
        if isinstance(result_data, dict) and 'error' in result_data:
            logger.error(f"Error fetching player profile from logic: {result_data['error']}")
            status_code = 404 if "not found" in result_data['error'].lower() else 500
            raise HTTPException(status_code=status_code, detail=result_data['error'])
            
        return result_data 
        
    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to parse JSON response from fetch_player_profile_logic: {json_err}")
        raise HTTPException(status_code=500, detail="Internal server error: Invalid data format from service.")
    except Exception as e:
        logger.error(f"Error fetching player profile: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
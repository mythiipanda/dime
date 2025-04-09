import logging
from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any
import json
from api_tools.player_tools import (
    get_player_headshot_url, 
    find_players_by_name_fragment,
    fetch_player_stats_logic,
    fetch_player_info_logic
)
from api_tools.player_tracking import (
    fetch_player_clutch_stats_logic,
    fetch_player_shots_tracking_logic,
    fetch_player_rebounding_stats_logic,
    fetch_player_passing_stats_logic
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/headshot")
async def get_player_headshot(player_id: str):
    """Get the URL for a player's headshot."""
    try:
        url = get_player_headshot_url(player_id)
        return {"url": url}
    except Exception as e:
        logger.error(f"Error getting player headshot: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search")
async def search_players(query: str, limit: Optional[int] = 10) -> Dict[str, Any]:
    """Search for players by name fragment."""
    try:
        players = find_players_by_name_fragment(query, limit)
        return {"players": players}
    except Exception as e:
        logger.error(f"Error searching players: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/player/{player_id}/headshot")
async def get_player_headshot(player_id: int):
    logger.info(f"Received GET /player/{player_id}/headshot request.")
    if player_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid player_id provided.")
    try:
        headshot_url = get_player_headshot_url(player_id)
        return {"player_id": player_id, "headshot_url": headshot_url}
    except Exception as e:
        logger.exception(f"Unexpected error fetching headshot for player ID {player_id}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    except Exception as e:
        logger.exception(f"Unexpected error fetching headshot for player ID {player_id}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/players/search", response_model=List[Dict[str, Any]])
async def search_players(q: str | None = None, limit: int = 10):
    logger.info(f"Received GET /players/search request with query: '{q}', limit: {limit}")
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
async def fetch_player_stats(player_name: str, season: Optional[str] = None) -> Dict[str, Any]:
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

@router.get("/info")
async def fetch_player_info(player_name: str) -> Dict[str, Any]:
    """
    Get player information.
    
    Args:
        player_name (str): The name of the player to fetch info for
    """
    logger.info(f"Received GET /info request for player: '{player_name}'")
    try:
        result = fetch_player_info_logic(player_name)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error fetching player info: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
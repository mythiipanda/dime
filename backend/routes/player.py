from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import logging

from api_tools.player_tools import get_player_headshot_url, find_players_by_name_fragment

logger = logging.getLogger(__name__)

router = APIRouter()

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
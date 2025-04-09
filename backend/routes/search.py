from fastapi import APIRouter, HTTPException
import logging

from schemas import SearchRequest
from api_tools.search import search_players_logic, search_teams_logic, search_games_logic
from config import SUPPORTED_SEARCH_TARGETS

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/search")
async def search_data(request: SearchRequest):
    """
    Search for players, teams, or games based on the provided query.
    """
    try:
        if request.target not in SUPPORTED_SEARCH_TARGETS:
            raise HTTPException(status_code=400, detail=f"Unsupported search target: {request.target}")

        if request.target == "players":
            return search_players_logic(request.query, request.limit)
        elif request.target == "teams":
            return search_teams_logic(request.query, request.limit)
        elif request.target == "games":
            return search_games_logic(request.query, request.season, request.season_type, request.limit)
        
    except Exception as e:
        logger.error(f"Error in search_data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
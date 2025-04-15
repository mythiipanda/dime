import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from backend.routes.schemas import FetchRequest
from backend.api_tools.game_tools import (
    fetch_boxscore_traditional_logic as fetch_game_boxscore_logic,
    fetch_playbyplay_logic as fetch_game_playbyplay_logic,
    fetch_shotchart_logic as fetch_game_shotchart_logic,
    fetch_league_games_logic as fetch_league_scoreboard_logic
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/boxscore")
async def get_game_boxscore(request: FetchRequest) -> Dict[str, Any]:
    """
    Get game boxscore.
    """
    try:
        game_id = request.params.get("game_id")
        if not game_id:
            raise HTTPException(status_code=400, detail="game_id is required")
        result = fetch_game_boxscore_logic(game_id)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error getting game boxscore: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/playbyplay")
async def get_game_playbyplay(request: FetchRequest) -> Dict[str, Any]:
    """
    Get game play-by-play data.
    """
    try:
        game_id = request.params.get("game_id")
        if not game_id:
            raise HTTPException(status_code=400, detail="game_id is required")
        result = fetch_game_playbyplay_logic(game_id)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error getting game play-by-play: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/shotchart")
async def get_game_shotchart(request: FetchRequest) -> Dict[str, Any]:
    """
    Get game shot chart data.
    """
    try:
        game_id = request.params.get("game_id")
        if not game_id:
            raise HTTPException(status_code=400, detail="game_id is required")
        result = fetch_game_shotchart_logic(game_id)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error getting game shot chart: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/league/scoreboard")
async def get_league_scoreboard(request: FetchRequest) -> Dict[str, Any]:
    """
    Get league scoreboard for a specific date.
    """
    try:
        # Although FetchRequest is used, this endpoint might not need specific params
        # depending on fetch_league_scoreboard_logic implementation.
        # If it needs a date, it should be passed in request.params
        # game_date = request.params.get("game_date") # Example if date is needed
        # if not game_date:
        #     raise HTTPException(status_code=400, detail="game_date is required")

        result = fetch_league_scoreboard_logic() # Pass params if needed, e.g., fetch_league_scoreboard_logic(game_date)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error getting league scoreboard: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
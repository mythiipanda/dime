import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from backend.routes.schemas import FetchRequest
from backend.api_tools.game_tools import (
    fetch_boxscore_traditional_logic as fetch_game_boxscore_logic,
    fetch_playbyplay_logic as fetch_game_playbyplay_logic,
    fetch_shotchart_logic as fetch_game_shotchart_logic,
)
from backend.api_tools.league_tools import fetch_scoreboard_logic # Import correct scoreboard logic

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
        # Extract potential parameters for scoreboard logic
        game_date = request.params.get("game_date") # Expects YYYY-MM-DD or None for today
        day_offset_str = request.params.get("day_offset", "0")
        try:
            day_offset = int(day_offset_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="day_offset must be an integer")

        # Call the correct scoreboard logic function
        result = fetch_scoreboard_logic(game_date=game_date, day_offset=day_offset)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error getting league scoreboard: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
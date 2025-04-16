import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from backend.routes.schemas import TeamRequest
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

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/stats")
async def fetch_team_stats(team_name: str, season: Optional[str] = None) -> Dict[str, Any]:
    """
    Get comprehensive team statistics.
    
    Args:
        team_name (str): The name of the team to fetch stats for
        season (Optional[str]): The season to fetch stats for (e.g., '2023-24')
    """
    logger.info(f"Received GET /stats request for team: '{team_name}', season: {season}")
    try:
        result = fetch_team_stats_logic(team_name, season) if season else fetch_team_stats_logic(team_name)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error fetching team stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/info")
async def fetch_team_info(team_name: str, season: Optional[str] = None) -> Dict[str, Any]:
    """
    Get team information and roster.
    
    Args:
        team_name (str): The name of the team to fetch info for
        season (Optional[str]): The season to fetch info for (e.g., '2023-24')
    """
    logger.info(f"Received GET /info request for team: '{team_name}', season: {season}")
    try:
        result = fetch_team_info_and_roster_logic(team_name, season) if season else fetch_team_info_and_roster_logic(team_name)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error fetching team info: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/passing")
async def get_team_passing_stats(request: TeamRequest) -> Dict[str, Any]:
    """
    Get team passing statistics.
    """
    try:
        result = fetch_team_passing_stats_logic(request.team_name, request.season)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error getting team passing stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rebounding")
async def get_team_rebounding_stats(request: TeamRequest) -> Dict[str, Any]:
    """
    Get team rebounding statistics.
    """
    try:
        result = fetch_team_rebounding_stats_logic(request.team_name, request.season)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error getting team rebounding stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/shooting")
async def get_team_shooting_stats(request: TeamRequest) -> Dict[str, Any]:
    """
    Get team shooting statistics.
    """
    try:
        result = fetch_team_shooting_stats_logic(request.team_name, request.season)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error getting team shooting stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 
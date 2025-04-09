import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import json
from api_tools.team_tracking import (
    fetch_team_passing_stats_logic,
    fetch_team_rebounding_stats_logic,
    fetch_team_shooting_stats_logic
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/tracking/stats")
async def fetch_team_tracking_stats(team_name: str, season: Optional[str] = None) -> Dict[str, Any]:
    """
    Get comprehensive team tracking statistics.
    
    Args:
        team_name (str): The name of the team to fetch tracking stats for
        season (Optional[str]): The season to fetch stats for (e.g., '2023-24')
    """
    logger.info(f"Received GET /tracking/stats request for team: '{team_name}', season: {season}")
    try:
        # Get passing stats
        passing_result = json.loads(fetch_team_passing_stats_logic(team_name, season) if season else fetch_team_passing_stats_logic(team_name))
        if "error" in passing_result:
            return {"error": passing_result["error"]}
            
        # Get rebounding stats
        rebounding_result = json.loads(fetch_team_rebounding_stats_logic(team_name, season) if season else fetch_team_rebounding_stats_logic(team_name))
        if "error" in rebounding_result:
            return {"error": rebounding_result["error"]}
            
        # Get shooting stats
        shooting_result = json.loads(fetch_team_shooting_stats_logic(team_name, season) if season else fetch_team_shooting_stats_logic(team_name))
        if "error" in shooting_result:
            return {"error": shooting_result["error"]}
            
        # Combine all results
        result = {
            "team_name": team_name,
            "season": season,
            "passing_stats": passing_result.get("stats", {}),
            "rebounding_stats": rebounding_result.get("stats", {}),
            "shooting_stats": shooting_result.get("stats", {})
        }
        
        return {"result": json.dumps(result)}
    except Exception as e:
        logger.error(f"Error fetching team tracking stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tracking/passing")
async def fetch_team_passing_stats(team_name: str, season: Optional[str] = None) -> Dict[str, Any]:
    """Get team passing statistics."""
    logger.info(f"Received GET /tracking/passing request for team: '{team_name}', season: {season}")
    try:
        result = fetch_team_passing_stats_logic(team_name, season) if season else fetch_team_passing_stats_logic(team_name)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error fetching team passing stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tracking/rebounding")
async def fetch_team_rebounding_stats(team_name: str, season: Optional[str] = None) -> Dict[str, Any]:
    """Get team rebounding statistics."""
    logger.info(f"Received GET /tracking/rebounding request for team: '{team_name}', season: {season}")
    try:
        result = fetch_team_rebounding_stats_logic(team_name, season) if season else fetch_team_rebounding_stats_logic(team_name)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error fetching team rebounding stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tracking/shooting")
async def fetch_team_shooting_stats(team_name: str, season: Optional[str] = None) -> Dict[str, Any]:
    """Get team shooting statistics."""
    logger.info(f"Received GET /tracking/shooting request for team: '{team_name}', season: {season}")
    try:
        result = fetch_team_shooting_stats_logic(team_name, season) if season else fetch_team_shooting_stats_logic(team_name)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error fetching team shooting stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 
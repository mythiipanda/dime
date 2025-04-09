import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import json
from api_tools.player_tracking import (
    fetch_player_clutch_stats_logic,
    fetch_player_shots_tracking_logic,
    fetch_player_rebounding_stats_logic,
    fetch_player_passing_stats_logic
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/tracking/stats")
async def fetch_player_tracking_stats(player_name: str, season: Optional[str] = None) -> Dict[str, Any]:
    """
    Get comprehensive player tracking statistics.
    
    Args:
        player_name (str): The name of the player to fetch tracking stats for
        season (Optional[str]): The season to fetch stats for (e.g., '2023-24')
    """
    logger.info(f"Received GET /tracking/stats request for player: '{player_name}', season: {season}")
    try:
        # Get clutch stats
        clutch_result = json.loads(fetch_player_clutch_stats_logic(player_name, season) if season else fetch_player_clutch_stats_logic(player_name))
        if "error" in clutch_result:
            return {"error": clutch_result["error"]}
            
        # Get shots tracking
        shots_result = json.loads(fetch_player_shots_tracking_logic(player_name, season) if season else fetch_player_shots_tracking_logic(player_name))
        if "error" in shots_result:
            return {"error": shots_result["error"]}
            
        # Get rebounding stats
        rebounding_result = json.loads(fetch_player_rebounding_stats_logic(player_name, season) if season else fetch_player_rebounding_stats_logic(player_name))
        if "error" in rebounding_result:
            return {"error": rebounding_result["error"]}
            
        # Get passing stats
        passing_result = json.loads(fetch_player_passing_stats_logic(player_name, season) if season else fetch_player_passing_stats_logic(player_name))
        if "error" in passing_result:
            return {"error": passing_result["error"]}
            
        # Combine all results
        result = {
            "player_name": player_name,
            "season": season,
            "clutch_stats": clutch_result.get("stats", {}),
            "shots_tracking": shots_result.get("stats", {}),
            "rebounding_stats": rebounding_result.get("stats", {}),
            "passing_stats": passing_result.get("stats", {})
        }
        
        return {"result": json.dumps(result)}
    except Exception as e:
        logger.error(f"Error fetching player tracking stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tracking/clutch")
async def fetch_player_clutch_stats(player_name: str, season: Optional[str] = None) -> Dict[str, Any]:
    """Get player clutch statistics."""
    logger.info(f"Received GET /tracking/clutch request for player: '{player_name}', season: {season}")
    try:
        result = fetch_player_clutch_stats_logic(player_name, season) if season else fetch_player_clutch_stats_logic(player_name)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error fetching player clutch stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tracking/shots")
async def fetch_player_shots_tracking(player_name: str, season: Optional[str] = None) -> Dict[str, Any]:
    """Get player shots tracking statistics."""
    logger.info(f"Received GET /tracking/shots request for player: '{player_name}', season: {season}")
    try:
        result = fetch_player_shots_tracking_logic(player_name, season) if season else fetch_player_shots_tracking_logic(player_name)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error fetching player shots tracking: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tracking/rebounding")
async def fetch_player_rebounding_stats(player_name: str, season: Optional[str] = None) -> Dict[str, Any]:
    """Get player rebounding statistics."""
    logger.info(f"Received GET /tracking/rebounding request for player: '{player_name}', season: {season}")
    try:
        result = fetch_player_rebounding_stats_logic(player_name, season) if season else fetch_player_rebounding_stats_logic(player_name)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error fetching player rebounding stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tracking/passing")
async def fetch_player_passing_stats(player_name: str, season: Optional[str] = None) -> Dict[str, Any]:
    """Get player passing statistics."""
    logger.info(f"Received GET /tracking/passing request for player: '{player_name}', season: {season}")
    try:
        result = fetch_player_passing_stats_logic(player_name, season) if season else fetch_player_passing_stats_logic(player_name)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error fetching player passing stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 
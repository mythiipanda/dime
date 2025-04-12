from fastapi import APIRouter, HTTPException
from typing import Optional
import json
from nba_api.stats.library.parameters import SeasonType
from api_tools.league_tools import fetch_league_standings_logic
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/standings")
async def get_standings(season: Optional[str] = None, season_type: str = SeasonType.regular):
    """
    Get NBA league standings.

    Args:
        season: Optional season in YYYY-YY format (e.g., "2023-24")
        season_type: Season type (default: Regular Season)
    """
    try:
        standings_data = fetch_league_standings_logic(season=season, season_type=season_type)
        
        # Convert to JSON-serializable format
        return standings_data

    except Exception as e:
        logger.error(f"Error fetching standings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
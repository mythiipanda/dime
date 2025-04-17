import logging
import json
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, status
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerMode36
from backend.api_tools.league_tools import fetch_league_leaders_logic
from backend.api_tools.utils import validate_season_format
from backend.config import CURRENT_SEASON

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/leaders", summary="Get League Leaders", tags=["League Leaders"] )
async def get_league_leaders(
    season: Optional[str] = Query(None, description="Season YYYY-YY format"),
    stat_category: str = Query("PTS", description="Stat category abbreviation"),
    season_type: str = Query(SeasonTypeAllStar.regular, description="Season type"),
    per_mode: str = Query(PerMode36.per_game, description="Per mode (e.g. per game/per 36 mins)")
):
    """
    Retrieve top league leaders based on stat category.
    """
    logger.info(f"Request league leaders: season={season}, stat_category={stat_category}")
    if season and not validate_season_format(season):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid season format. Use YYYY-YY.")
    season_val = season or CURRENT_SEASON
    try:
        json_str = fetch_league_leaders_logic(
            season=season_val,
            stat_category=stat_category,
            season_type=season_type,
            per_mode=per_mode
        )
        data = json.loads(json_str)
        if "error" in data:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=data["error"])
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching league leaders: {e}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

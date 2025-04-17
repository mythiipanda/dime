import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from backend.api_tools.odds_tools import fetch_odds_data_logic

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/odds", summary="Get Live Betting Odds", tags=["Odds"])
async def get_live_odds() -> Dict[str, Any]:
    """
    Retrieve live betting odds for NBA games.
    """
    logger.info("Requesting live odds")
    try:
        result = fetch_odds_data_logic()
        if "error" in result:
            raise HTTPException(status_code=502, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_live_odds: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

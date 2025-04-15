import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from backend.schemas import AnalyzeRequest
from backend.api_tools.analyze import analyze_player_stats_logic
# Removed unused imports: nba_agent, json

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/player")
async def analyze_player_stats(request: AnalyzeRequest) -> Dict[str, Any]:
    """
    Analyze player statistics based on the provided request.
    """
    try:
        result = analyze_player_stats_logic(request.player_name, request.season)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error analyzing player stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Removed the /analyze endpoint as requested
from fastapi import APIRouter, Query, HTTPException, status
import logging
from typing import Any, Dict, Optional
from datetime import date

# Import the unified logic function
from backend.api_tools.scoreboard.scoreboard_tools import fetch_scoreboard_data_logic
from backend.api_tools.utils import validate_date_format # For validation if needed here

logger = logging.getLogger(__name__)
router = APIRouter()

# Renamed endpoint slightly to reflect it handles dates
@router.get("/", 
            summary="Get Scoreboard by Date", 
            description="Fetches NBA scoreboard data for a specific date (YYYY-MM-DD). Defaults to today if no date is provided.",
            response_description="A dictionary containing the game date and a list of games.",
            tags=["Scoreboard"])
async def get_scoreboard_endpoint(
    game_date: Optional[str] = Query(default=None, description="Date in YYYY-MM-DD format. Defaults to today.")
) -> Dict[str, Any]:
    """
    API endpoint to retrieve scoreboard data for a given date.
    """
    logger.info(f"Received request for scoreboard data for date: {game_date or 'today'}.")
    
    # Basic validation can happen here, or rely on the logic function
    if game_date and not validate_date_format(game_date):
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST, 
             detail=f"Invalid date format: {game_date}. Use YYYY-MM-DD."
         )

    try:
        # Pass the date (or None) to the logic function
        result = fetch_scoreboard_data_logic(game_date=game_date) 
        
        if isinstance(result, dict) and 'error' in result:
            logger.error(f"Error fetching scoreboard from logic: {result['error']}")
            status_code = status.HTTP_502_BAD_GATEWAY if "Failed to fetch" in result['error'] else status.HTTP_500_INTERNAL_SERVER_ERROR
            # Include specific date format error as 400 Bad Request
            if "Invalid date format" in result['error']:
                status_code = status.HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=status_code, detail=result['error'])
        
        logger.info(f"Successfully retrieved scoreboard data for {result.get('gameDate', game_date or 'today')}.")
        return result

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception("Unhandled exception in scoreboard endpoint", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                            detail=f"An unexpected error occurred: {str(e)}") 
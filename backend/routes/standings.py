from fastapi import APIRouter, HTTPException, Query, status
from typing import Optional, Dict, Any
import json
import asyncio
from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID
from backend.api_tools.league_standings import fetch_league_standings_logic
import logging
from backend.core.errors import Errors
from backend.config import settings
from backend.utils.validation import validate_date_format, validate_season_format

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/league",  # Standard prefix for league-related endpoints
    tags=["League"]    # Tag for OpenAPI documentation
)

async def _handle_league_route_logic_call(
    logic_function: callable, 
    endpoint_name: str,
    *args, 
    **kwargs
) -> Dict[str, Any]:
    """Helper to call league-related logic, parse JSON, and handle errors."""
    try:
        # Filter out None kwargs so logic functions can use their defaults
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        
        result_json_string = await asyncio.to_thread(logic_function, *args, **filtered_kwargs)
        result_data = json.loads(result_json_string)

        if isinstance(result_data, dict) and 'error' in result_data:
            error_detail = result_data['error']
            logger.error(f"Error from {logic_function.__name__} with args {args}, kwargs {filtered_kwargs}: {error_detail}")
            status_code_to_raise = status.HTTP_404_NOT_FOUND if "not found" in error_detail.lower() else \
                                   status.HTTP_400_BAD_REQUEST if "invalid" in error_detail.lower() else \
                                   status.HTTP_500_INTERNAL_SERVER_ERROR
            raise HTTPException(status_code=status_code_to_raise, detail=error_detail)
        return result_data
    except HTTPException as http_exc:
        raise http_exc
    except json.JSONDecodeError as json_err:
        func_name = logic_function.__name__
        logger.error(f"Failed to parse JSON response from {func_name} for args {args}, kwargs {filtered_kwargs}: {json_err}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=Errors.JSON_PROCESSING_ERROR)
    except Exception as e:
        func_name = logic_function.__name__
        logger.critical(f"Unexpected error in API route calling {func_name} for args {args}, kwargs {filtered_kwargs}: {str(e)}", exc_info=True)
        error_msg_template = getattr(Errors, 'UNEXPECTED_ERROR', "An unexpected server error occurred: {error}")
        detail_msg = error_msg_template.format(error=f"processing {endpoint_name.lower()}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail_msg)

@router.get(
    "/standings",
    summary="Get League Standings",
    description="Fetches NBA league standings. Can be filtered by season, season type, league, and a specific date. "
                "If `date` is provided, `season` and `season_type` are ignored by the underlying API for V2 standings.",
    response_model=Dict[str, Any]
)
async def get_league_standings_endpoint(
    league_id: Optional[str] = Query(LeagueID.nba, description="League ID (e.g., '00' for NBA, '10' for WNBA, '20' for G-League). Defaults to NBA."),
    season: Optional[str] = Query(None, description=f"Season in YYYY-YY format (e.g., '2023-24'). Defaults to {settings.CURRENT_NBA_SEASON} in logic if date is not set.", regex=r"^\d{4}-\d{2}$"), # Changed
    season_type: Optional[str] = Query(SeasonTypeAllStar.regular, description="Season type (e.g., 'Regular Season', 'Playoffs'). Defaults to Regular Season."),
    date: Optional[str] = Query(None, description="Specific date for standings in YYYY-MM-DD format. If provided, season/season_type might be ignored by API. Defaults to None.", regex=r"^\d{4}-\d{2}-\d{2}$")
) -> Dict[str, Any]:
    """
    Endpoint to get NBA league standings.
    Uses `fetch_league_standings_logic` from `league_tools.py`.

    Query Parameters:
    - **league_id** (str, optional): Defaults to "00" (NBA).
    - **season** (str, optional): YYYY-YY format. Defaults to current season in logic if `date` is not specified.
    - **season_type** (str, optional): e.g., "Regular Season", "Playoffs". Defaults to "Regular Season".
      Valid values are from `nba_api.stats.library.parameters.SeasonTypeAllStar`.
    - **date** (str, optional): YYYY-MM-DD format. If provided, fetches standings for this specific date.

    Successful Response (200 OK):
    Returns a dictionary containing parameters and a list of team standings.
    Example:
    ```json
    {
        "parameters": {
            "league_id": "00",
            "season": "2023-24",
            "season_type": "Regular Season",
            "date": null
        },
        "standings": [
            {
                "TeamID": 1610612738,
                "LeagueID": "00",
                "SeasonID": "22023",
                "TeamCity": "Boston",
                "TeamName": "Celtics",
                "Conference": "East",
                "PlayoffRank": 1,
                "WINS": 64,
                "LOSSES": 18,
                // ... many other fields like WinPct, Record, HomeRecord, RoadRecord, etc.
            },
            // ... more teams
        ]
    }
    ```
    If no standings are found for the criteria, `standings` will be an empty list.

    Error Responses:
    - 400 Bad Request: If query parameters are invalid (e.g., bad date/season format).
    - 500 Internal Server Error: For unexpected errors or issues fetching/processing data.
    """
    logger.info(f"Received GET /league/standings request. League: {league_id}, Season: {season}, Type: {season_type}, Date: {date}")

    # Validate date format if provided
    if date and not validate_date_format(date):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Errors.INVALID_DATE_FORMAT.format(date=date)
        )
    if season and not date and not validate_season_format(season):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Errors.INVALID_SEASON_FORMAT.format(season=season)
        )
    standings_kwargs_for_logic = {
        "season": season,
        "season_type": season_type,
        "date": date
    }
    
    return await _handle_league_route_logic_call(
        fetch_league_standings_logic, "league standings",
        **standings_kwargs_for_logic
    )
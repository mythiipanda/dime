import logging
import json
import asyncio
from typing import Optional, Dict, Any
from fastapi import APIRouter, Query, HTTPException, status

from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, 
    PerMode48, 
    LeagueID, 
    Scope,
    StatCategoryAbbreviation
)
from backend.api_tools.league_leaders_data import fetch_league_leaders_logic
from backend.utils.validation import validate_season_format
from backend.core.errors import Errors
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/league",  # Standard prefix for league-related endpoints
    tags=["League"]    # Consistent tag
)

async def _handle_league_route_logic_call(
    logic_function: callable, 
    endpoint_name: str,
    *args, 
    **kwargs
) -> Dict[str, Any]:
    """Helper to call league-related logic, parse JSON, and handle errors."""
    try:
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        result_json_string = await asyncio.to_thread(logic_function, *args, **filtered_kwargs)
        result_data = json.loads(result_json_string)

        if isinstance(result_data, dict) and 'error' in result_data:
            error_detail = result_data['error']
            logger.error(f"Error from {logic_function.__name__} with args {args}, kwargs {filtered_kwargs}: {error_detail}")
            status_code_to_raise = status.HTTP_404_NOT_FOUND if "not found" in error_detail.lower() else \
                                   status.HTTP_400_BAD_REQUEST if "invalid" in error_detail.lower() else \
                                   status.HTTP_500_INTERNAL_SERVER_ERROR # Default to 500, can be 502 if upstream API error
            if "nba api error" in error_detail.lower() or "external api" in error_detail.lower(): # Check for upstream API issues
                status_code_to_raise = status.HTTP_502_BAD_GATEWAY
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
    "/leaders", 
    summary="Get League Leaders by Statistical Category",
    description="Fetches a list of top NBA players based on a specified statistical category, season, and other criteria. "
                "Data is sourced from the NBA's official stats API.",
    response_model=Dict[str, Any]
)
async def get_league_leaders_endpoint(
    stat_category: str = Query(StatCategoryAbbreviation.pts, description="The statistical category to rank leaders by (e.g., 'PTS', 'REB', 'AST'). See `nba_api.stats.library.parameters.StatCategoryAbbreviation` for all valid options."),
    season: Optional[str] = Query(None, description=f"NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to {settings.CURRENT_NBA_SEASON} in logic if not provided.", regex=r"^\d{4}-\d{2}$"), # Changed
    season_type: str = Query(SeasonTypeAllStar.regular, description="Type of season (e.g., 'Regular Season', 'Playoffs'). See `nba_api.stats.library.parameters.SeasonTypeAllStar`."),
    per_mode: str = Query(PerMode48.per_game, description="Statistical mode (e.g., 'PerGame', 'Totals', 'Per36'). See `nba_api.stats.library.parameters.PerMode48`."),
    league_id: str = Query(LeagueID.nba, description="League ID. See `nba_api.stats.library.parameters.LeagueID` (e.g., '00' for NBA)."),
    scope: str = Query(Scope.s, description="Scope of the statistics (e.g., 'S' for Season, 'RS' for Regular Season, 'PO' for Playoffs). See `nba_api.stats.library.parameters.Scope`."),
    top_n: Optional[int] = Query(10, description="Number of top leaders to return. Logic layer defaults if not provided or invalid.", ge=1, le=200) # Added ge/le
) -> Dict[str, Any]:
    """
    Endpoint to retrieve top league leaders for a given statistical category.
    Uses `fetch_league_leaders_logic` from `league_tools.py`.

    Query Parameters:
    - **stat_category** (str, required): e.g., "PTS", "REB", "AST". Default: "PTS".
    - **season** (str, optional): YYYY-YY format. Defaults to current season in logic.
    - **season_type** (str, optional): e.g., "Regular Season". Default: "Regular Season".
    - **per_mode** (str, optional): e.g., "PerGame". Default: "PerGame".
    - **league_id** (str, optional): e.g., "00" for NBA. Default: "00".
    - **scope** (str, optional): e.g., "S" for Season. Default: "S".
    - **top_n** (int, optional): Number of leaders. Default: 10. Min:1, Max:200 (API might have its own limits).

    Successful Response (200 OK):
    Returns a dictionary containing parameters and a list of league leaders.
    Example:
    ```json
    {
        "parameters": {
            "stat_category": "PTS",
            "season": "2023-24",
            // ... other params
        },
        "leaders": [
            {
                "PLAYER_ID": 201939,
                "RANK": 1,
                "PLAYER": "Stephen Curry",
                "TEAM_ID": 1610612744,
                "TEAM": "GSW",
                "GP": 70,
                "MIN": 35.0,
                "PTS": 30.1, // Actual stat category value
                // ... other common stats like FGM, FGA, FG_PCT etc.
            },
            // ... more players
        ]
    }
    ```
    If no leaders are found, `leaders` will be an empty list.

    Error Responses:
    - 400 Bad Request: If query parameters are invalid (e.g., bad season format, invalid stat category).
    - 500 Internal Server Error / 502 Bad Gateway: For unexpected errors or issues fetching/processing data.
    """
    logger.info(f"Received GET /league/leaders request. Category: {stat_category}, Season: {season}, Type: {season_type}, PerMode: {per_mode}, League: {league_id}, Scope: {scope}, TopN: {top_n}")

    season_to_use = season or settings.CURRENT_NBA_SEASON # Changed
    if not validate_season_format(season_to_use):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=Errors.INVALID_SEASON_FORMAT.format(season=season_to_use))

    # Validate enum-like string parameters
    VALID_STAT_CATEGORIES = {getattr(StatCategoryAbbreviation, attr) for attr in dir(StatCategoryAbbreviation) if not attr.startswith('_')}
    if stat_category not in VALID_STAT_CATEGORIES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=Errors.INVALID_STAT_CATEGORY.format(value=stat_category, options=", ".join(list(VALID_STAT_CATEGORIES)[:5]))) # Show some options
    
    # Similar validation for season_type, per_mode, league_id, scope can be added here
    # For brevity, assuming logic layer or FastAPI's default Query validation (if enums were used) handles them.
    # Example for season_type:
    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_')}
    if season_type not in VALID_SEASON_TYPES:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5])))


    leaders_kwargs = {
        "season": season_to_use,
        "stat_category": stat_category,
        "season_type": season_type,
        "per_mode": per_mode,
        "league_id": league_id,
        "scope": scope,
        "top_n": top_n if top_n is not None else 10 # Logic layer handles default if None
    }

    return await _handle_league_route_logic_call(
        fetch_league_leaders_logic, "league leaders",
        **leaders_kwargs
    )

import logging
import asyncio
from fastapi import APIRouter, HTTPException, Query, Path
from typing import Dict, Any, Optional
import json

from backend.api_tools.team_info_roster import fetch_team_info_and_roster_logic
from backend.api_tools.team_general_stats import fetch_team_stats_logic

from backend.api_tools.team_passing_tracking import fetch_team_passing_stats_logic
from backend.api_tools.team_rebounding_tracking import fetch_team_rebounding_stats_logic
from backend.api_tools.team_shooting_tracking import fetch_team_shooting_stats_logic

from backend.core.errors import Errors
from config import settings

router = APIRouter(
    prefix="/team", # Add prefix for all team routes
    tags=["Teams"]  # Tag for OpenAPI documentation
)
logger = logging.getLogger(__name__)

async def _handle_team_route_logic_call(
    logic_function: callable,
    team_identifier: str, # All team routes will have this
    endpoint_name: str,
    *args, # Positional args for the logic function (e.g., season)
    **kwargs # Keyword args for the logic function
) -> Dict[str, Any]:
    """Helper to call team-related logic, parse JSON, and handle errors."""
    try:
        # Ensure all args are passed correctly; logic functions handle defaults for None
        all_logic_args = (team_identifier,) + args
        # Filter out None kwargs so logic functions can use their defaults
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}

        result_json_string = await asyncio.to_thread(logic_function, *all_logic_args, **filtered_kwargs)
        result_data = json.loads(result_json_string)

        if isinstance(result_data, dict) and 'error' in result_data:
            error_detail = result_data['error']
            logger.error(f"Error from {logic_function.__name__} for {team_identifier}: {error_detail}")
            status_code = 404 if "not found" in error_detail.lower() or "invalid team" in error_detail.lower() else \
                          400 if "invalid" in error_detail.lower() else 500
            raise HTTPException(status_code=status_code, detail=error_detail)
        return result_data
    except HTTPException as http_exc:
        raise http_exc
    except json.JSONDecodeError as json_err:
        func_name = logic_function.__name__
        logger.error(f"Failed to parse JSON response from {func_name} for {team_identifier}: {json_err}", exc_info=True)
        raise HTTPException(status_code=500, detail=Errors.JSON_PROCESSING_ERROR)
    except Exception as e:
        func_name = logic_function.__name__
        logger.critical(f"Unexpected error in API route calling {func_name} for '{team_identifier}': {str(e)}", exc_info=True)
        error_msg_template = getattr(Errors, 'UNEXPECTED_ERROR', "An unexpected server error occurred: {error}")
        detail_msg = error_msg_template.format(error=f"processing team data via {func_name}")
        raise HTTPException(status_code=500, detail=detail_msg)

@router.get(
    "/{team_identifier}/stats",
    summary="Get Comprehensive Team Statistics",
    description="Fetches comprehensive team statistics for a specified team and season. "
                "Includes current season dashboard stats (based on `measure_type`) and historical year-by-year performance.",
    response_model=Dict[str, Any]
)
async def get_team_stats_endpoint( # Renamed for clarity
    team_identifier: str = Path(..., description="Team name (e.g., 'Boston Celtics'), abbreviation (e.g., 'BOS'), or ID (e.g., '1610612738')."),
    season: Optional[str] = Query(None, description=f"NBA season in YYYY-YY format (e.g., '2023-24') for dashboard stats. Defaults to {settings.CURRENT_NBA_SEASON} in logic.", regex=r"^\d{4}-\d{2}$"), # Changed
    season_type: Optional[str] = Query(None, description="Type of season for dashboard stats (e.g., 'Regular Season', 'Playoffs'). Logic default: 'Regular Season'."),
    per_mode: Optional[str] = Query(None, description="Statistical mode for dashboard and historical stats (e.g., 'PerGame', 'Totals'). Logic default: 'PerGame'."),
    measure_type: Optional[str] = Query(None, description="Category of dashboard stats (e.g., 'Base', 'Advanced', 'Scoring'). Logic default: 'Base'."),
    opponent_team_id: Optional[int] = Query(0, description="Filter dashboard stats against a specific opponent team ID. Default: 0 (all).", ge=0),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD) for filtering dashboard games.", regex=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD) for filtering dashboard games.", regex=r"^\d{4}-\d{2}-\d{2}$"),
    league_id: Optional[str] = Query(None, description="League ID for historical stats (e.g., '00' for NBA). Logic default: '00'.")
) -> Dict[str, Any]:
    """
    Endpoint to get comprehensive team statistics.
    Uses `fetch_team_stats_logic` from `team_tools.py`.

    Path Parameters:
    - **team_identifier** (str, required): Team name, abbreviation, or ID.

    Query Parameters (all optional, logic functions use defaults):
    - **season**: For dashboard stats.
    - **season_type**: For dashboard stats.
    - **per_mode**: For dashboard and historical stats.
    - **measure_type**: For dashboard stats.
    - **opponent_team_id**: For dashboard stats.
    - **date_from**: For dashboard stats.
    - **date_to**: For dashboard stats.
    - **league_id**: For historical stats.

    Successful Response (200 OK):
    Returns a dictionary with team stats. Refer to `fetch_team_stats_logic` docstring in `team_tools.py`.
    Includes `current_stats` (dashboard) and `historical_stats`.

    Error Responses: 400, 404, 500.
    """
    logger.info(f"Received GET /team/{team_identifier}/stats request, Season: {season}, Measure: {measure_type}")
    return await _handle_team_route_logic_call(
        fetch_team_stats_logic, team_identifier, "team stats",
        season=season, season_type=season_type, per_mode=per_mode, measure_type=measure_type,
        opponent_team_id=opponent_team_id, date_from=date_from, date_to=date_to, league_id=league_id
    )

@router.get(
    "/{team_identifier}/info_roster",
    summary="Get Team Information and Roster",
    description="Fetches detailed team information, including conference/division ranks, current season roster, and coaching staff.",
    response_model=Dict[str, Any]
)
async def get_team_info_and_roster_endpoint(
    team_identifier: str = Path(..., description="Team name, abbreviation, or ID."),
    season: Optional[str] = Query(None, description=f"NBA season (YYYY-YY). Defaults to {settings.CURRENT_NBA_SEASON} in logic.", regex=r"^\d{4}-\d{2}$"), # Changed
    season_type: Optional[str] = Query(None, description="Season type. Logic default: 'Regular Season'."),
    league_id: Optional[str] = Query(None, description="League ID. Logic default: '00' (NBA).")
) -> Dict[str, Any]:
    """
    Endpoint to get team information and roster.
    Uses `fetch_team_info_and_roster_logic` from `team_tools.py`.

    Path Parameters:
    - **team_identifier** (str, required): Team name, abbreviation, or ID.

    Query Parameters (all optional, logic functions use defaults):
    - **season**
    - **season_type**
    - **league_id**

    Successful Response (200 OK):
    Returns a dictionary with team info and roster. Refer to `fetch_team_info_and_roster_logic` docstring.
    Includes `info`, `ranks`, `roster`, `coaches`.

    Error Responses: 400, 404, 500.
    """
    logger.info(f"Received GET /team/{team_identifier}/info_roster request, Season: {season}")
    return await _handle_team_route_logic_call(
        fetch_team_info_and_roster_logic, team_identifier, "team info/roster",
        season=season, season_type=season_type, league_id=league_id
    )

@router.get(
    "/{team_identifier}/tracking/passing",
    summary="Get Team Passing Statistics",
    description="Fetches team passing statistics, detailing passes made and received among players.",
    response_model=Dict[str, Any]
)
async def get_team_passing_stats_endpoint(
    team_identifier: str = Path(..., description="Team name, abbreviation, or ID."),
    season: Optional[str] = Query(None, description=f"Season (YYYY-YY). Defaults to {settings.CURRENT_NBA_SEASON} in logic.", regex=r"^\d{4}-\d{2}$"), # Changed
    season_type: Optional[str] = Query(None, description="Season type. Logic default: 'Regular Season'."),
    per_mode: Optional[str] = Query(None, description="Per mode (e.g., 'PerGame', 'Totals'). Logic default: 'PerGame'.")
) -> Dict[str, Any]:
    """
    Endpoint to get team passing statistics.
    Uses `fetch_team_passing_stats_logic` from `team_tracking.py`.

    Path Parameters:
    - **team_identifier** (str, required).

    Query Parameters (all optional, logic functions use defaults):
    - **season**
    - **season_type**
    - **per_mode**

    Successful Response (200 OK):
    Returns dict with `passes_made` and `passes_received`. Refer to `fetch_team_passing_stats_logic` docstring.

    Error Responses: 400, 404, 500.
    """
    logger.info(f"Received GET /team/{team_identifier}/tracking/passing request, Season: {season}")
    return await _handle_team_route_logic_call(
        fetch_team_passing_stats_logic, team_identifier, "team passing stats",
        season=season, season_type=season_type, per_mode=per_mode
    )

@router.get(
    "/{team_identifier}/tracking/rebounding",
    summary="Get Team Rebounding Statistics",
    description="Fetches team rebounding statistics, categorized by shot type, contest, and distances.",
    response_model=Dict[str, Any]
)
async def get_team_rebounding_stats_endpoint(
    team_identifier: str = Path(..., description="Team name, abbreviation, or ID."),
    season: Optional[str] = Query(None, description=f"Season (YYYY-YY). Defaults to {settings.CURRENT_NBA_SEASON} in logic.", regex=r"^\d{4}-\d{2}$"), # Changed
    season_type: Optional[str] = Query(None, description="Season type. Logic default: 'Regular Season'."),
    per_mode: Optional[str] = Query(None, description="Per mode. Logic default: 'PerGame'."),
    opponent_team_id: Optional[int] = Query(0, description="Filter by opponent team ID. Default: 0 (all).", ge=0),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD).", regex=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD).", regex=r"^\d{4}-\d{2}-\d{2}$")
) -> Dict[str, Any]:
    """
    Endpoint to get team rebounding statistics.
    Uses `fetch_team_rebounding_stats_logic` from `team_tracking.py`.

    Path Parameters:
    - **team_identifier** (str, required).

    Query Parameters (all optional, logic functions use defaults):
    - **season**, **season_type**, **per_mode**
    - **opponent_team_id**, **date_from**, **date_to**

    Successful Response (200 OK):
    Returns dict with rebounding splits. Refer to `fetch_team_rebounding_stats_logic` docstring.

    Error Responses: 400, 404, 500.
    """
    logger.info(f"Received GET /team/{team_identifier}/tracking/rebounding, Season: {season}")
    return await _handle_team_route_logic_call(
        fetch_team_rebounding_stats_logic, team_identifier, "team rebounding stats",
        season=season, season_type=season_type, per_mode=per_mode,
        opponent_team_id=opponent_team_id, date_from=date_from, date_to=date_to
    )

@router.get(
    "/{team_identifier}/tracking/shooting",
    summary="Get Team Shooting Statistics",
    description="Fetches team shooting statistics, categorized by shot clock, dribbles, defender distance, etc.",
    response_model=Dict[str, Any]
)
async def get_team_shooting_stats_endpoint(
    team_identifier: str = Path(..., description="Team name, abbreviation, or ID."),
    season: Optional[str] = Query(None, description=f"Season (YYYY-YY). Defaults to {settings.CURRENT_NBA_SEASON} in logic.", regex=r"^\d{4}-\d{2}$"), # Changed
    season_type: Optional[str] = Query(None, description="Season type. Logic default: 'Regular Season'."),
    per_mode: Optional[str] = Query(None, description="Per mode. Logic default: 'PerGame'."),
    opponent_team_id: Optional[int] = Query(0, description="Filter by opponent team ID. Default: 0 (all).", ge=0),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD).", regex=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD).", regex=r"^\d{4}-\d{2}-\d{2}$")
) -> Dict[str, Any]:
    """
    Endpoint to get team shooting statistics.
    Uses `fetch_team_shooting_stats_logic` from `team_tracking.py`.

    Path Parameters:
    - **team_identifier** (str, required).

    Query Parameters (all optional, logic functions use defaults):
    - **season**, **season_type**, **per_mode**
    - **opponent_team_id**, **date_from**, **date_to**

    Successful Response (200 OK):
    Returns dict with shooting splits. Refer to `fetch_team_shooting_stats_logic` docstring.

    Error Responses: 400, 404, 500.
    """
    logger.info(f"Received GET /team/{team_identifier}/tracking/shooting, Season: {season}")
    return await _handle_team_route_logic_call(
        fetch_team_shooting_stats_logic, team_identifier, "team shooting stats",
        season=season, season_type=season_type, per_mode=per_mode,
        opponent_team_id=opponent_team_id, date_from=date_from, date_to=date_to
    )
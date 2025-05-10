import logging
import asyncio
from fastapi import APIRouter, HTTPException, Query, Path
from typing import Dict, Any, Optional, List
import json

from backend.api_tools.team_tracking import (
    fetch_team_passing_stats_logic,
    fetch_team_rebounding_stats_logic,
    fetch_team_shooting_stats_logic
)
from backend.config import Errors, CURRENT_SEASON
# import backend.api_tools.utils as api_utils # Not directly used in the remaining endpoint

router = APIRouter(
    prefix="/team", 
    tags=["Team Tracking"]
)
logger = logging.getLogger(__name__)

async def _handle_team_tracking_logic_call(
    logic_function: callable,
    team_identifier: str,
    endpoint_name: str,
    *args,
    **kwargs
) -> Dict[str, Any]:
    """Helper to call team tracking logic, parse JSON, and handle errors."""
    try:
        all_logic_args = (team_identifier,) + args
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
        logger.critical(f"Unexpected error in {endpoint_name} for '{team_identifier}': {str(e)}", exc_info=True)
        error_msg_template = getattr(Errors, 'UNEXPECTED_ERROR', "An unexpected server error occurred: {error}")
        detail_msg = error_msg_template.format(error=f"processing {endpoint_name.lower()} for team '{team_identifier}'")
        raise HTTPException(status_code=500, detail=detail_msg)

@router.get(
    "/{team_identifier}/tracking/stats_all",
    summary="Get All Team Tracking Statistics (Combined)",
    description="Fetches a comprehensive set of team tracking statistics including passing, rebounding, "
                "and shooting data for a specified team and season. This endpoint makes multiple "
                "underlying API calls.",
    response_model=Dict[str, Any]
)
async def get_all_team_tracking_stats_endpoint(
    team_identifier: str = Path(..., description="Team name (e.g., 'Boston Celtics'), abbreviation (e.g., 'BOS'), or ID (e.g., '1610612738')."),
    season: Optional[str] = Query(None, description=f"NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to {CURRENT_SEASON} in logic.", regex=r"^\d{4}-\d{2}$"),
    season_type: Optional[str] = Query(None, description="Type of season (e.g., 'Regular Season', 'Playoffs'). Defaults to 'Regular Season' in logic."),
    per_mode: Optional[str] = Query(None, description="Per mode for all tracking types (e.g., 'PerGame', 'Totals'). Logic functions use their own defaults if not specified here."),
    opponent_team_id: Optional[int] = Query(0, description="Filter by opponent team ID for applicable tracking types (rebounding, shooting). Default 0 (all).", ge=0),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD) for applicable tracking types (rebounding, shooting).", regex=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD) for applicable tracking types (rebounding, shooting).", regex=r"^\d{4}-\d{2}-\d{2}$")
) -> Dict[str, Any]:
    """
    Endpoint to get a combined set of team tracking statistics.

    Path Parameters:
    - **team_identifier** (str, required): Team name, abbreviation, or ID.

    Query Parameters (all optional, logic functions use defaults):
    - **season**, **season_type**, **per_mode**
    - **opponent_team_id** (for rebounding, shooting)
    - **date_from** (for rebounding, shooting)
    - **date_to** (for rebounding, shooting)

    Successful Response (200 OK):
    Returns a dictionary containing all tracking stats. Structure:
    ```json
    {
        "team_identifier_requested": "Boston Celtics",
        "team_id_resolved": 1610612738, // Example
        "team_name_resolved": "Boston Celtics", // Example
        "season_requested": "2023-24", // Or null
        "passing_stats": { /* ... data from fetch_team_passing_stats_logic ... */ },
        "rebounding_stats": { /* ... data from fetch_team_rebounding_stats_logic ... */ },
        "shooting_stats": { /* ... data from fetch_team_shooting_stats_logic ... */ }
    }
    ```
    Error Responses: 400, 404, 500.
    """
    logger.info(f"Received GET /team/{team_identifier}/tracking/stats_all request, Season: {season}")

    common_kwargs = {"season": season, "season_type": season_type, "per_mode": per_mode}
    reb_shoot_kwargs = {**common_kwargs, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to}

    try:
        results = await asyncio.gather(
            _handle_team_tracking_logic_call(fetch_team_passing_stats_logic, team_identifier, "team passing stats", **common_kwargs),
            _handle_team_tracking_logic_call(fetch_team_rebounding_stats_logic, team_identifier, "team rebounding stats", **reb_shoot_kwargs),
            _handle_team_tracking_logic_call(fetch_team_shooting_stats_logic, team_identifier, "team shooting stats", **reb_shoot_kwargs),
            return_exceptions=False
        )
        passing_data, rebounding_data, shooting_data = results
        
        team_id_resolved = passing_data.get("team_id") or rebounding_data.get("team_id") or shooting_data.get("team_id")
        team_name_resolved = passing_data.get("team_name", team_identifier) 

        combined_result = {
            "team_identifier_requested": team_identifier,
            "team_id_resolved": team_id_resolved,
            "team_name_resolved": team_name_resolved,
            "season_requested": season,
            "passing_stats": passing_data,
            "rebounding_stats": rebounding_data,
            "shooting_stats": shooting_data
        }
        return combined_result
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.critical(f"Unexpected error in combined team tracking stats for {team_identifier}: {str(e)}", exc_info=True)
        error_msg = Errors.UNEXPECTED_ERROR.format(error=f"fetching combined tracking stats for team '{team_identifier}'")
        raise HTTPException(status_code=500, detail=error_msg)

# Deprecated individual tracking endpoints have been removed.
# The functionality is covered by the /team/{team_identifier}/tracking/* endpoints in backend/routes/team.py
# or by the combined /team/{team_identifier}/tracking/stats_all endpoint above.
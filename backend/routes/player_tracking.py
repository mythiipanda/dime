import logging
import asyncio
from fastapi import APIRouter, HTTPException, Query, Path
from typing import Dict, Any, Optional
import json
import re

from backend.api_tools.player_clutch import fetch_player_clutch_stats_logic
from backend.api_tools.player_shooting_tracking import fetch_player_shots_tracking_logic
from backend.api_tools.player_rebounding import fetch_player_rebounding_stats_logic
from backend.api_tools.player_passing import fetch_player_passing_stats_logic

from backend.core.errors import Errors
from backend.config import settings

router = APIRouter(
    prefix="/player", 
    tags=["Player Tracking"]
)
logger = logging.getLogger(__name__)

season_regex_pattern = r"(^\d{4}-\d{2}$)|(^" + re.escape(settings.CURRENT_NBA_SEASON) + r"$)"

async def _handle_tracking_logic_call(
    logic_function: callable,
    player_name: str,
    endpoint_name: str, 
    *args, 
    **kwargs
) -> Dict[str, Any]:
    """Helper to call player tracking logic, parse JSON, and handle errors."""
    try:
        all_logic_args = (player_name,) + args
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        
        result_json_string = await asyncio.to_thread(logic_function, *all_logic_args, **filtered_kwargs)
        result_data = json.loads(result_json_string)

        if isinstance(result_data, dict) and 'error' in result_data:
            error_detail = result_data['error']
            logger.error(f"Error from {logic_function.__name__} for {player_name}: {error_detail}")
            status_code = 404 if "not found" in error_detail.lower() or "invalid player" in error_detail.lower() else \
                          400 if "invalid" in error_detail.lower() else 500
            raise HTTPException(status_code=status_code, detail=error_detail)
        return result_data
    except HTTPException as http_exc:
        raise http_exc
    except json.JSONDecodeError as json_err:
        func_name = logic_function.__name__
        logger.error(f"Failed to parse JSON response from {func_name} for {player_name}: {json_err}", exc_info=True)
        raise HTTPException(status_code=500, detail=Errors.JSON_PROCESSING_ERROR)
    except Exception as e:
        func_name = logic_function.__name__
        log_args_repr = args[:1] 
        logger.critical(f"Unexpected error in API route calling {func_name} for '{player_name}' with args {log_args_repr} and kwargs {filtered_kwargs}: {str(e)}", exc_info=True)
        error_msg_template = getattr(Errors, 'UNEXPECTED_ERROR', "An unexpected server error occurred: {error}")
        detail_msg = error_msg_template.format(error=f"processing {endpoint_name.lower()} for player '{player_name}'")
        raise HTTPException(status_code=500, detail=detail_msg)

@router.get(
    "/{player_name}/tracking/stats",
    summary="Get All Player Tracking Statistics (Combined)",
    description="Fetches a comprehensive set of player tracking statistics including clutch performance, "
                "detailed shooting, rebounding, and passing data for a specified player and season. "
                "This endpoint makes multiple underlying API calls; individual data categories might "
                "return empty or error states if specific data is unavailable.",
    response_model=Dict[str, Any]
)
async def get_all_player_tracking_stats(
    player_name: str = Path(..., description="Full name of the player (e.g., 'LeBron James')."),
    season: Optional[str] = Query(None, description=f"NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to {settings.CURRENT_NBA_SEASON} in logic if not provided.", regex=r"^\d{4}-\d{2}$"), # Changed
    season_type: Optional[str] = Query(None, description="Type of season (e.g., 'Regular Season', 'Playoffs'). Defaults to 'Regular Season' in logic."),
    measure_type_clutch: Optional[str] = Query(None, description="Measure type for clutch stats (e.g., 'Base', 'Advanced')."),
    per_mode_clutch: Optional[str] = Query(None, description="Per mode for clutch stats (e.g., 'Totals', 'PerGame')."),
    opponent_team_id_shots: Optional[int] = Query(0, description="Opponent team ID for shots tracking. Default 0 (all).", ge=0),
    date_from_shots: Optional[str] = Query(None, description="Start date (YYYY-MM-DD) for shots tracking.", regex=r"^\d{4}-\d{2}-\d{2}$"),
    date_to_shots: Optional[str] = Query(None, description="End date (YYYY-MM-DD) for shots tracking.", regex=r"^\d{4}-\d{2}-\d{2}$"),
    per_mode_reb: Optional[str] = Query(None, description="Per mode for rebounding (e.g., 'PerGame', 'Totals')."),
    per_mode_pass: Optional[str] = Query(None, description="Per mode for passing (e.g., 'PerGame', 'Totals').")
) -> Dict[str, Any]:
    logger.info(f"Received GET /player/{player_name}/tracking/stats request, Season: {season}")

    clutch_kwargs = {"season": season, "season_type": season_type, "measure_type": measure_type_clutch, "per_mode": per_mode_clutch}
    shots_kwargs = {"season": season, "season_type": season_type, "opponent_team_id": opponent_team_id_shots, "date_from": date_from_shots, "date_to": date_to_shots}
    reb_kwargs = {"season": season, "season_type": season_type, "per_mode": per_mode_reb}
    pass_kwargs = {"season": season, "season_type": season_type, "per_mode": per_mode_pass}

    try:
        results = await asyncio.gather(
            _handle_tracking_logic_call(fetch_player_clutch_stats_logic, player_name, "clutch stats", **clutch_kwargs),
            _handle_tracking_logic_call(fetch_player_shots_tracking_logic, player_name, "shots tracking", **shots_kwargs),
            _handle_tracking_logic_call(fetch_player_rebounding_stats_logic, player_name, "rebounding stats", **reb_kwargs),
            _handle_tracking_logic_call(fetch_player_passing_stats_logic, player_name, "passing stats", **pass_kwargs),
            return_exceptions=False
        )
        clutch_data, shots_data, rebounding_data, passing_data = results
        
        player_id_resolved = clutch_data.get("player_id")
        player_name_resolved = clutch_data.get("player_name", player_name)

        combined_result = {
            "player_name": player_name_resolved,
            "player_id": player_id_resolved,
            "season_requested": season,
            "clutch_stats": clutch_data,
            "shots_tracking": shots_data,
            "rebounding_stats": rebounding_data,
            "passing_stats": passing_data
        }
        return combined_result
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.critical(f"Unexpected error in combined tracking stats for {player_name}: {str(e)}", exc_info=True)
        error_msg = Errors.UNEXPECTED_ERROR.format(error=f"fetching combined tracking stats for player '{player_name}'")
        raise HTTPException(status_code=500, detail=error_msg)

@router.get(
    "/{player_name}/tracking/clutch",
    summary="Get Player Clutch Statistics",
    description="Fetches player statistics in clutch situations (e.g., last 5 minutes of a close game). "
                "Allows filtering by various clutch parameters.",
    response_model=Dict[str, Any]
)
async def get_player_clutch_stats_endpoint(
    player_name: str = Path(..., description="Full name of the player."),
    season: Optional[str] = Query(None, description=f"Season (YYYY-YY or '{settings.CURRENT_NBA_SEASON}'). Defaults to {settings.CURRENT_NBA_SEASON} in logic.", regex=season_regex_pattern, example="2023-24"), # Changed
    season_type: Optional[str] = Query(None, description="Season type (e.g., 'Regular Season', 'Playoffs'). Logic default: 'Regular Season'."),
    measure_type: Optional[str] = Query(None, description="Measure type (e.g., 'Base', 'Advanced'). Logic default: 'Base'."),
    per_mode: Optional[str] = Query(None, description="Per mode (e.g., 'Totals', 'PerGame'). Logic default: 'Totals'."),
    clutch_time_nullable: Optional[str] = Query(None, description="Clutch time window (e.g., 'Last 5 Minutes', 'Last 1 Minute')."),
    ahead_behind_nullable: Optional[str] = Query(None, description="Score margin (e.g., 'Ahead or Behind', 'Tied', 'Behind by 1-3')."),
    point_diff_nullable: Optional[int] = Query(None, description="Maximum point differential for clutch definition (e.g., 5 for within 5 points).", ge=0),
    plus_minus: Optional[str] = Query(None, description="Include plus-minus stats ('Y' or 'N').", pattern=r"^[YN]$"), # Corrected regex
    pace_adjust: Optional[str] = Query(None, description="Adjust stats for pace ('Y' or 'N').", pattern=r"^[YN]$"), # Corrected regex
    rank: Optional[str] = Query(None, description="Include stat rankings ('Y' or 'N').", pattern=r"^[YN]$"), # Corrected regex
    opponent_team_id: Optional[int] = Query(0, description="Filter by opponent team ID. Default 0 (all).", ge=0)
) -> Dict[str, Any]:
    logger.info(f"Received GET /player/{player_name}/tracking/clutch with params: season={season}, measure_type={measure_type}, per_mode={per_mode}")
    clutch_kwargs = {
        "season": season, "season_type": season_type, "measure_type": measure_type, "per_mode": per_mode,
        "clutch_time_nullable": clutch_time_nullable, "ahead_behind_nullable": ahead_behind_nullable,
        "point_diff_nullable": point_diff_nullable, "plus_minus": plus_minus, "pace_adjust": pace_adjust,
        "rank": rank, "opponent_team_id": opponent_team_id
    }
    return await _handle_tracking_logic_call(fetch_player_clutch_stats_logic, player_name, "clutch stats", **clutch_kwargs)

@router.get(
    "/{player_name}/tracking/shots",
    summary="Get Player Shots Tracking Statistics",
    description="Fetches detailed player shooting statistics, categorized by factors like shot clock, dribbles, and defender distance.",
    response_model=Dict[str, Any]
)
async def get_player_shots_tracking_endpoint(
    player_name: str = Path(..., description="Full name of the player."),
    season: Optional[str] = Query(None, description=f"Season (YYYY-YY or '{settings.CURRENT_NBA_SEASON}'). Defaults to {settings.CURRENT_NBA_SEASON} in logic.", regex=season_regex_pattern, example="2023-24"), # Changed
    season_type: Optional[str] = Query(None, description="Season type. Logic default: 'Regular Season'."),
    opponent_team_id: Optional[int] = Query(0, description="Filter by opponent team ID. Default: 0 (all).", ge=0),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD).", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD).", pattern=r"^\d{4}-\d{2}-\d{2}$")
) -> Dict[str, Any]:
    logger.info(f"Received GET /player/{player_name}/tracking/shots, Season: {season}")
    shots_kwargs = {
        "season": season, "season_type": season_type,
        "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to
    }
    return await _handle_tracking_logic_call(fetch_player_shots_tracking_logic, player_name, "shots tracking", **shots_kwargs)

@router.get(
    "/{player_name}/tracking/rebounding",
    summary="Get Player Rebounding Statistics",
    description="Fetches detailed player rebounding statistics, categorized by shot type, contest, and distances.",
    response_model=Dict[str, Any]
)
async def get_player_rebounding_stats_endpoint(
    player_name: str = Path(..., description="Full name of the player."),
    season: Optional[str] = Query(None, description=f"Season (YYYY-YY or '{settings.CURRENT_NBA_SEASON}'). Defaults to {settings.CURRENT_NBA_SEASON} in logic.", regex=season_regex_pattern, example="2023-24"), # Changed
    season_type: Optional[str] = Query(None, description="Season type. Logic default: 'Regular Season'."),
    per_mode: Optional[str] = Query(None, description="Per mode (e.g., 'PerGame', 'Totals'). Logic default: 'PerGame'.")
) -> Dict[str, Any]:
    logger.info(f"Received GET /player/{player_name}/tracking/rebounding, Season: {season}")
    reb_kwargs = {"season": season, "season_type": season_type, "per_mode": per_mode}
    return await _handle_tracking_logic_call(fetch_player_rebounding_stats_logic, player_name, "rebounding stats", **reb_kwargs)

@router.get(
    "/{player_name}/tracking/passing",
    summary="Get Player Passing Statistics",
    description="Fetches detailed player passing statistics, including passes made to and received from teammates.",
    response_model=Dict[str, Any]
)
async def get_player_passing_stats_endpoint(
    player_name: str = Path(..., description="Full name of the player."),
    season: Optional[str] = Query(None, description=f"Season (YYYY-YY or '{settings.CURRENT_NBA_SEASON}'). Defaults to {settings.CURRENT_NBA_SEASON} in logic.", regex=season_regex_pattern, example="2023-24"), # Changed
    season_type: Optional[str] = Query(None, description="Season type. Logic default: 'Regular Season'."),
    per_mode: Optional[str] = Query(None, description="Per mode (e.g., 'PerGame', 'Totals'). Logic default: 'PerGame'.")
) -> Dict[str, Any]:
    logger.info(f"Received GET /player/{player_name}/tracking/passing, Season: {season}")
    pass_kwargs = {"season": season, "season_type": season_type, "per_mode": per_mode}
    return await _handle_tracking_logic_call(fetch_player_passing_stats_logic, player_name, "passing stats", **pass_kwargs)
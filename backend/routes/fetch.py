from fastapi import APIRouter, HTTPException, Body, status # Added Body, status
import json
import logging
import asyncio
from typing import Dict, Any # For response type hint

from backend.schemas import FetchRequest # Corrected import
from backend.api_tools.player_tools import ( # Corrected import
    fetch_player_info_logic, 
    fetch_player_gamelog_logic, 
    fetch_player_career_stats_logic
)
from backend.api_tools.team_tools import fetch_team_info_and_roster_logic # Corrected import
from backend.api_tools.game_tools import fetch_league_games_logic # Corrected import
from nba_api.stats.library.parameters import PerMode36, SeasonTypeAllStar # Used for defaults
from backend.config import SUPPORTED_FETCH_TARGETS, Errors # Corrected import

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/fetch", # Add prefix for this generic fetch route
    tags=["Generic Fetch"] # Tag for OpenAPI documentation
)

async def _handle_fetch_logic_call(
    logic_function: callable, 
    endpoint_name: str, # For logging/error context
    *args, 
    **kwargs
) -> Dict[str, Any]:
    """Helper to call underlying logic, parse JSON, and handle errors for /fetch routes."""
    try:
        # Filter out None kwargs so logic functions can use their defaults if they support it
        # However, for this generic fetch, params are explicitly passed based on target.
        
        result_json_string = await asyncio.to_thread(logic_function, *args, **kwargs)
        
        if not result_json_string: # Handle case where logic might return None or empty string
            logger.error(f"Logic function {logic_function.__name__} returned no data for {endpoint_name} with args {args}, kwargs {kwargs}.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No data returned from underlying service.")

        result_data = json.loads(result_json_string)

        if isinstance(result_data, dict) and 'error' in result_data:
            error_detail = result_data['error']
            logger.error(f"Error from {logic_function.__name__} for {endpoint_name} ({args}, {kwargs}): {error_detail}")
            
            status_code_to_raise = status.HTTP_500_INTERNAL_SERVER_ERROR # Default
            if "not found" in error_detail.lower():
                status_code_to_raise = status.HTTP_404_NOT_FOUND
            elif "invalid parameter" in error_detail.lower() or "missing" in error_detail.lower() or "invalid format" in error_detail.lower():
                status_code_to_raise = status.HTTP_400_BAD_REQUEST
            elif "nba api error" in error_detail.lower() or "external api" in error_detail.lower():
                status_code_to_raise = status.HTTP_502_BAD_GATEWAY
            
            raise HTTPException(status_code=status_code_to_raise, detail=error_detail)
        return result_data # Can be Dict or List (e.g. for gamelog)
    except HTTPException as http_exc:
        raise http_exc
    except json.JSONDecodeError as json_err:
        func_name = logic_function.__name__
        logger.error(f"Failed to parse JSON response from {func_name} for {endpoint_name} ({args}, {kwargs}): {json_err}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=Errors.JSON_PROCESSING_ERROR)
    except Exception as e:
        func_name = logic_function.__name__
        logger.critical(f"Unexpected error in API route calling {func_name} for {endpoint_name} ({args}, {kwargs}): {str(e)}", exc_info=True)
        error_msg_template = getattr(Errors, 'UNEXPECTED_ERROR', "An unexpected server error occurred: {error}")
        detail_msg = error_msg_template.format(error=f"processing fetch request for {endpoint_name}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail_msg)

@router.post(
    "/data", # Changed path from /fetch_data to /data under /fetch prefix
    summary="Generic Data Fetcher",
    description="A versatile endpoint to fetch various types of NBA data based on a specified `target` "
                "and target-specific `params`. Refer to the `FetchRequest` schema and the documentation "
                "for each target to understand required and optional parameters.",
    response_model=Dict[str, Any] # Response structure varies, Dict[str, Any] is a general placeholder
)
async def fetch_data_endpoint( # Renamed for clarity
    request: FetchRequest = Body(...)
) -> Dict[str, Any]:
    """
    Generic endpoint to fetch various NBA data.

    Request Body (`FetchRequest`):
    - **target** (str, required): Specifies the type of data to fetch. Supported values are defined in
      `SUPPORTED_FETCH_TARGETS` (e.g., "player_info", "player_gamelog", "team_info", 
      "player_career_stats", "find_games").
    - **params** (Dict[str, Any], required): A dictionary of parameters specific to the chosen `target`.

      **Parameter details by target:**
      - **target="player_info"**:
        - `params`: `{"player_name": str (required)}`
      - **target="player_gamelog"**:
        - `params`: `{"player_name": str (required), "season": str (required, YYYY-YY), "season_type"?: str (optional, defaults to Regular Season)}`
      - **target="team_info"**:
        - `params`: `{"team_identifier": str (required, name/abbr/ID), "season"?: str (optional, YYYY-YY, defaults to current)}`
      - **target="player_career_stats"**:
        - `params`: `{"player_name": str (required), "per_mode"?: str (optional, e.g., "PerGame", defaults to "PerGame")}`
          (Note: API uses `per_mode36` but common term is `per_mode`)
      - **target="find_games"**: (LeagueGameFinder)
        - `params`: `{
            "player_or_team_abbreviation": "P" | "T" (required),
            "player_id_nullable"?: int (optional, required if player_or_team_abbreviation='P'),
            "team_id_nullable"?: int (optional, required if player_or_team_abbreviation='T'),
            "season_nullable"?: str (optional, YYYY-YY),
            "season_type_nullable"?: str (optional),
            "league_id_nullable"?: str (optional, e.g., "00"),
            "date_from_nullable"?: str (optional, YYYY-MM-DD),
            "date_to_nullable"?: str (optional, YYYY-MM-DD)
          }`

    Successful Response (200 OK):
    Returns a dictionary containing the fetched data. The structure of this dictionary
    depends on the `target` and the data returned by the corresponding logic function.
    (e.g., for "player_info", it will be player details; for "player_gamelog", a list of games).

    Error Responses:
    - 400 Bad Request: If `target` is unsupported, or if required `params` for the target are missing/invalid.
    - 404 Not Found: If the requested resource (e.g., player, team) is not found by the logic layer.
    - 500 Internal Server Error: For unexpected errors or issues in the underlying service.
    - 502 Bad Gateway: If an external API call made by the logic layer fails.
    """
    target = request.target
    params = request.params if request.params is not None else {} # Ensure params is a dict
    logger.info(f"Received POST /fetch/data request for target: {target}, params: {params}")

    if target not in SUPPORTED_FETCH_TARGETS:
        logger.warning(f"Unsupported fetch target: {target}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=Errors.UNSUPPORTED_FETCH_TARGET.format(target=target, supported_targets=", ".join(SUPPORTED_FETCH_TARGETS))
        )

    if target == "player_info":
        player_name = params.get("player_name")
        if not player_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing 'player_name' in params for target 'player_info'.")
        return await _handle_fetch_logic_call(fetch_player_info_logic, "player_info", player_name)

    elif target == "player_gamelog":
        player_name = params.get("player_name")
        season = params.get("season")
        if not player_name or not season:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing 'player_name' or 'season' in params for target 'player_gamelog'.")
        season_type = params.get("season_type", SeasonTypeAllStar.regular) # Default here or in logic
        return await _handle_fetch_logic_call(fetch_player_gamelog_logic, "player_gamelog", player_name, season, season_type=season_type)

    elif target == "team_info":
        team_identifier = params.get("team_identifier")
        if not team_identifier:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing 'team_identifier' in params for target 'team_info'.")
        season = params.get("season") # Optional, logic handles default
        return await _handle_fetch_logic_call(fetch_team_info_and_roster_logic, "team_info", team_identifier, season=season)

    elif target == "player_career_stats":
        player_name = params.get("player_name")
        if not player_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing 'player_name' in params for target 'player_career_stats'.")
        # API uses per_mode36, but common term is per_mode. Logic function expects per_mode_param.
        per_mode_param = params.get("per_mode", PerMode36.per_game) # Default here or in logic
        return await _handle_fetch_logic_call(fetch_player_career_stats_logic, "player_career_stats", player_name, per_mode_param=per_mode_param)

    elif target == "find_games":
        # Extract all possible params for fetch_league_games_logic
        required_player_or_team = params.get("player_or_team_abbreviation")
        if not required_player_or_team or required_player_or_team not in ['P', 'T']:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing or invalid 'player_or_team_abbreviation' (must be 'P' or 'T') in params for target 'find_games'.")
        
        find_games_kwargs = {
            "player_or_team_abbreviation": required_player_or_team,
            "player_id_nullable": params.get("player_id_nullable"),
            "team_id_nullable": params.get("team_id_nullable"),
            "season_nullable": params.get("season_nullable"),
            "season_type_nullable": params.get("season_type_nullable"),
            "league_id_nullable": params.get("league_id_nullable"),
            "date_from_nullable": params.get("date_from_nullable"),
            "date_to_nullable": params.get("date_to_nullable")
        }
        if required_player_or_team == 'P' and find_games_kwargs["player_id_nullable"] is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing 'player_id_nullable' in params when player_or_team_abbreviation is 'P'.")
        if required_player_or_team == 'T' and find_games_kwargs["team_id_nullable"] is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing 'team_id_nullable' in params when player_or_team_abbreviation is 'T'.")
            
        return await _handle_fetch_logic_call(fetch_league_games_logic, "find_games", **find_games_kwargs)
    
    else:
        # Should be caught by SUPPORTED_FETCH_TARGETS check, but as a safeguard
        logger.error(f"Logic error: Reached else block for fetch target: {target}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error: Invalid fetch target processing.")
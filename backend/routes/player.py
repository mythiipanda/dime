import logging
import asyncio
from fastapi import APIRouter, HTTPException, Query, Path # Added Path
from typing import Optional, List, Dict, Any
import json

from backend.api_tools.player_common_info import get_player_headshot_url
from backend.api_tools.player_aggregate_stats import fetch_player_stats_logic
from backend.api_tools.player_dashboard_stats import fetch_player_profile_logic

from backend.api_tools.search import find_players_by_name_fragment
from backend.core.errors import Errors
from backend.utils.validation import _validate_season_format

router = APIRouter(
    prefix="/player", # Add prefix for all player routes
    tags=["Players"]  # Tag for OpenAPI documentation
)
logger = logging.getLogger(__name__)

async def _handle_player_route_logic_call(logic_function: callable, *args, **kwargs) -> Dict[str, Any]:
    """Helper to call player-related logic, parse JSON, and handle errors for player routes."""
    try:
        result_json_string = await asyncio.to_thread(logic_function, *args, **kwargs)
        result_data = json.loads(result_json_string)

        if isinstance(result_data, dict) and 'error' in result_data:
            error_detail = result_data['error']
            logger.error(f"Error from {logic_function.__name__}: {error_detail}")
            status_code = 404 if "not found" in error_detail.lower() or "invalid player" in error_detail.lower() else \
                          400 if "invalid" in error_detail.lower() else 500
            raise HTTPException(status_code=status_code, detail=error_detail)
        return result_data
    except HTTPException as http_exc:
        raise http_exc
    except json.JSONDecodeError as json_err:
        func_name = logic_function.__name__
        logger.error(f"Failed to parse JSON response from {func_name} for args {args}: {json_err}", exc_info=True)
        raise HTTPException(status_code=500, detail=Errors.JSON_PROCESSING_ERROR)
    except Exception as e:
        func_name = logic_function.__name__
        log_args = args[:1] # Log first arg (usually player identifier)
        logger.critical(f"Unexpected error in API route calling {func_name} with args {log_args}: {str(e)}", exc_info=True)
        error_msg_template = getattr(Errors, 'UNEXPECTED_ERROR', "An unexpected server error occurred: {error}")
        detail_msg = error_msg_template.format(error=f"processing player data via {func_name}")
        raise HTTPException(status_code=500, detail=detail_msg)


@router.get(
    "/{player_id}/headshot",
    summary="Get Player Headshot URL",
    description="Retrieves the URL for a player's official NBA headshot image based on their player ID.",
    response_model=Dict[str, Any]
)
async def get_player_headshot_by_id_endpoint( # Renamed for clarity
    player_id: int = Path(..., description="The unique 7-to-10 digit ID of the NBA player.", gt=0) # Added gt=0 validation
) -> Dict[str, Any]:
    """
    Endpoint to get a player's headshot URL by their ID.

    Path Parameters:
    - **player_id** (int, required): The unique ID of the player. Must be a positive integer.

    Successful Response (200 OK):
    ```json
    {
        "player_id": 2544,
        "headshot_url": "https://ak-static.cms.nba.com/wp-content/uploads/headshots/nba/latest/260x190/2544.png"
    }
    ```

    Error Responses:
    - 400 Bad Request: If `player_id` is invalid (e.g., not a positive integer).
    - 500 Internal Server Error: For unexpected errors.
    """
    logger.info(f"Received GET /player/{player_id}/headshot request.")
    try:
        headshot_url_str = await asyncio.to_thread(get_player_headshot_url, player_id)
        result = {"player_id": player_id, "headshot_url": headshot_url_str}
        return result
    except ValueError as ve: # Catch specific ValueError from get_player_headshot_url if player_id is invalid
        logger.warning(f"Invalid player_id for headshot: {player_id}. Error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.critical(f"Unexpected error fetching headshot for player ID {player_id}: {str(e)}", exc_info=True)
        error_msg = Errors.UNEXPECTED_ERROR.format(error=f"fetching headshot for player ID {player_id}")
        raise HTTPException(status_code=500, detail=error_msg)

@router.get(
    "/search",
    summary="Search for Players by Name Fragment",
    description="Searches for NBA players whose full names contain the provided query string. "
                "Returns a list of matching players with basic information.",
    response_model=List[Dict[str, Any]]
)
async def search_players_by_name_endpoint(
    q: str = Query(..., description="Search query string for player name. Minimum 2 characters.", min_length=2),
    limit: int = Query(10, description="Maximum number of search results to return.", ge=1, le=50)
) -> List[Dict[str, Any]]:
    """
    Endpoint to search for players by a name fragment.
    Uses `find_players_by_name_fragment` from `search.py`.

    Query Parameters:
    - **q** (str, required): The search query for the player's name. Minimum length is 2 characters.
    - **limit** (int, optional): Maximum number of results to return. Default: 10. Min: 1, Max: 50.

    Successful Response (200 OK):
    Returns a list of player objects. Each object contains:
    ```json
    [
        {
            "id": 2544,
            "full_name": "LeBron James",
            "first_name": "LeBron",
            "last_name": "James",
            "is_active": true
        },
        ...
    ]
    ```
    Returns an empty list if no players match or the query is too short.

    Error Responses:
    - 400 Bad Request: If query parameters are invalid (e.g., `q` too short, `limit` out of range - handled by FastAPI).
    - 500 Internal Server Error: For unexpected errors during the search.
    """
    logger.info(f"Received GET /player/search request with query: '{q}', limit: {limit}")
    try:
        results_list = await asyncio.to_thread(find_players_by_name_fragment, q, limit=limit)
        logger.info(f"Returning {len(results_list)} players for search query '{q}'")
        return results_list
    except Exception as e:
        logger.critical(f"Unexpected error during player search for query '{q}': {str(e)}", exc_info=True)
        error_msg = Errors.UNEXPECTED_ERROR.format(error=f"searching for player '{q}'")
        raise HTTPException(status_code=500, detail=error_msg)

@router.get(
    "/stats",
    summary="Get Aggregated Player Statistics",
    description="Fetches a comprehensive set of aggregated statistics for a player, "
                "including player info, headline stats, career totals, season game logs, and awards.",
    response_model=Dict[str, Any]
)
async def fetch_player_stats_endpoint(
    player_name: str = Query(..., description="Full name of the player (e.g., 'LeBron James')."),
    season: Optional[str] = Query(None, description="NBA season in YYYY-YY format (e.g., '2023-24') for game logs. Defaults to current season in logic.", regex=r"^\d{4}-\d{2}$")
) -> Dict[str, Any]:
    """
    Endpoint to get aggregated player statistics.
    Uses `fetch_player_stats_logic`.

    Query Parameters:
    - **player_name** (str, required): Full name of the player.
    - **season** (str, optional): Season for game logs (YYYY-YY). Defaults to current season in the logic layer.

    Successful Response (200 OK):
    Returns a dictionary with aggregated player stats.
    Refer to `fetch_player_stats_logic` in `player_tools.py` for detailed structure.
    Includes `info`, `headline_stats`, `career_stats`, `season_gamelog`, `awards`.

    Error Responses:
    - 400 Bad Request: If `player_name` is missing or `season` format is invalid.
    - 404 Not Found: If the player is not found.
    - 500 Internal Server Error: For other processing issues.
    """
    logger.info(f"Received GET /player/stats request for player: '{player_name}', season: {season}")
    if season and not _validate_season_format(season): # Use directly imported util
        raise HTTPException(status_code=400, detail=Errors.INVALID_SEASON_FORMAT.format(season=season))
    return await _handle_player_route_logic_call(fetch_player_stats_logic, player_name, season)

@router.get(
    "/profile",
    summary="Get Player Profile",
    description="Fetches a comprehensive player profile including biographical info, career/season highs, "
                "next game details, and career/season totals.",
    response_model=Dict[str, Any]
)
async def fetch_player_profile_endpoint(
    player_name: str = Query(..., description="Full name of the player (e.g., 'Stephen Curry')."),
    per_mode: Optional[str] = Query(None, description="Statistical mode for career/season totals (e.g., 'PerGame', 'Totals'). Defaults to 'PerGame' in logic.")
) -> Dict[str, Any]:
    """
    Endpoint to get a player's profile.
    Uses `fetch_player_profile_logic`.

    Query Parameters:
    - **player_name** (str, required): Full name of the player.
    - **per_mode** (str, optional): Statistical mode for totals. Defaults to 'PerGame' in logic layer.

    Successful Response (200 OK):
    Returns a dictionary with the player's profile.
    Refer to `fetch_player_profile_logic` in `player_tools.py` for detailed structure.
    Includes `player_info`, `career_highs`, `season_highs`, `next_game`, `career_totals`, `season_totals`.

    Error Responses:
    - 400 Bad Request: If `player_name` is missing or `per_mode` is invalid.
    - 404 Not Found: If the player is not found.
    - 500 Internal Server Error: For other processing issues.
    """
    logger.info(f"Received GET /player/profile request for player: '{player_name}', per_mode: {per_mode}")
    return await _handle_player_route_logic_call(fetch_player_profile_logic, player_name, per_mode)
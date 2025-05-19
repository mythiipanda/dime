from fastapi import APIRouter, HTTPException, Body, status # Added Body, status
import logging
import asyncio
import json
from typing import Any

from schemas import SearchRequest
from backend.api_tools.search import (
    search_players_logic, 
    search_teams_logic, 
    search_games_logic
)
from backend.core.constants import SUPPORTED_SEARCH_TARGETS
from backend.core.errors import Errors

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/search", # Add prefix for search routes
    tags=["Search"]   # Tag for OpenAPI documentation
)

async def _handle_search_logic_call(
    logic_function: callable, 
    endpoint_name: str,
    *args, 
    **kwargs
) -> Any:
    """Helper to call search logic, parse JSON, and handle errors."""
    try:
        # Filter out None kwargs so logic functions can use their defaults
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        
        result_json_string = await asyncio.to_thread(logic_function, *args, **filtered_kwargs)
        result_data = json.loads(result_json_string)

        if isinstance(result_data, dict) and 'error' in result_data:
            error_detail = result_data['error']
            logger.error(f"Error from {logic_function.__name__} for args {args}, kwargs {filtered_kwargs}: {error_detail}")
            # Determine status code based on error
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
        detail_msg = error_msg_template.format(error=f"processing search request via {func_name}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail_msg)

@router.post(
    "/",
    summary="Perform a Search",
    description="Searches for players, teams, or games based on the provided query string and target type. "
                "The structure of the results depends on the search target.",
)
async def perform_search_endpoint(
    request: SearchRequest = Body(...)
) -> Any:
    """
    Search for players, teams, or games.

    Request Body (`SearchRequest`):
    - **target** (str, required): The type of entity to search for.
      Supported values: "players", "teams", "games".
      (Refer to `SUPPORTED_SEARCH_TARGETS` in config).
    - **query** (str, required): The search query string (e.g., player name, team name, game keyword).
    - **limit** (int, optional): Maximum number of results to return. Defaults vary by logic function (typically 5-10).
    - **season** (Optional[str]): For "games" target. Season in YYYY-YY format (e.g., "2023-24").
    - **season_type** (Optional[str]): For "games" target. Type of season (e.g., "Regular Season", "Playoffs").

    Successful Response (200 OK):
    The response structure varies based on the `target`:
    - **target="players"**: Returns a list of player objects.
      ```json
      [
          {"id": 2544, "full_name": "LeBron James", "is_active": true, ...},
          ...
      ]
      ```
    - **target="teams"**: Returns a list of team objects.
      ```json
      [
          {"id": 1610612738, "full_name": "Boston Celtics", "abbreviation": "BOS", ...},
          ...
      ]
      ```
    - **target="games"**: Returns a dictionary, typically containing a list of game objects.
      (Refer to `search_games_logic` in `api_tools/search.py` for exact structure).
      Example:
      ```json
      {
          "query": "Lakers vs Celtics",
          "season": "2023-24",
          "games_found": [
              { "game_id": "0022300001", "home_team_name": "Celtics", "away_team_name": "Lakers", ... },
              ...
          ]
      }
      ```
    If no results are found, an empty list or a structure indicating no results (e.g., `{"games_found": []}`) is returned.

    Error Responses:
    - 400 Bad Request: If `target` is unsupported, or other request parameters are invalid.
    - 404 Not Found: If the search logic for a valid target explicitly returns a "not found" error.
    - 500 Internal Server Error: For unexpected errors during the search process.
    """
    logger.info(f"Received POST /search/ request with target: {request.target}, query: '{request.query}'")

    if request.target not in SUPPORTED_SEARCH_TARGETS:
        logger.warning(f"Unsupported search target: {request.target}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=Errors.UNSUPPORTED_SEARCH_TARGET.format(target=request.target, supported_targets=", ".join(SUPPORTED_SEARCH_TARGETS))
        )

    if not request.query or len(request.query.strip()) < getattr(request, 'min_query_length', 2): # Assuming min_query_length might be in SearchRequest
        logger.warning(f"Search query too short: '{request.query}' for target {request.target}")
        pass


    if request.target == "players":
        return await _handle_search_logic_call(
            search_players_logic, "player search",
            request.query, limit=request.limit
        )
    elif request.target == "teams":
        return await _handle_search_logic_call(
            search_teams_logic, "team search",
            request.query, limit=request.limit
        )
    elif request.target == "games":
        return await _handle_search_logic_call(
            search_games_logic, "game search",
            request.query, 
            season=request.season, 
            season_type=request.season_type, 
            limit=request.limit
        )
    else:
        logger.error(f"Reached unexpected else block for search target: {request.target}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error: Search target processing failed.")
import logging
import asyncio
from fastapi import APIRouter, HTTPException, Query, Path # Added Path
from typing import Dict, Any, Optional
import json

from backend.api_tools.game_tools import (
    fetch_boxscore_traditional_logic, # Aliased as fetch_game_boxscore_logic in original endpoint
    fetch_playbyplay_logic,           # Aliased as fetch_game_playbyplay_logic
    fetch_shotchart_logic,            # Aliased as fetch_game_shotchart_logic
    fetch_boxscore_advanced_logic,
    fetch_boxscore_four_factors_logic,
    fetch_boxscore_usage_logic,
    fetch_boxscore_defensive_logic,
    fetch_win_probability_logic
    # fetch_league_games_logic is used by /find endpoint, which might be in a different route file (e.g., league.py or search.py)
)
import backend.api_tools.utils as api_utils
from backend.config import Errors # Removed DEFAULT_TIMEOUT, CURRENT_SEASON as not directly used

router = APIRouter(
    prefix="/game", # Add prefix for all routes in this file
    tags=["Games"]  # Tag for OpenAPI documentation
)
logger = logging.getLogger(__name__)

async def _handle_logic_call(logic_function: callable, *args, **kwargs) -> Dict[str, Any]:
    """Helper to call logic function, parse JSON, and handle errors."""
    try:
        result_json_string = await asyncio.to_thread(logic_function, *args, **kwargs)
        result_data = json.loads(result_json_string)

        if isinstance(result_data, dict) and 'error' in result_data:
            error_detail = result_data['error']
            logger.error(f"Error from {logic_function.__name__}: {error_detail}")
            status_code = 404 if "not found" in error_detail.lower() or "invalid id" in error_detail.lower() else \
                          400 if "invalid" in error_detail.lower() else 500
            raise HTTPException(status_code=status_code, detail=error_detail)
        return result_data
    except HTTPException as http_exc:
        raise http_exc # Re-raise if it's already an HTTPException
    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to parse JSON response from {logic_function.__name__} for args {args}: {json_err}", exc_info=True)
        raise HTTPException(status_code=500, detail=Errors.JSON_PROCESSING_ERROR)
    except Exception as e:
        # Log the specific function and arguments for better debugging
        func_name = logic_function.__name__
        log_args = args[:2] # Log first few args to avoid overly long log lines
        logger.critical(f"Unexpected error in API route calling {func_name} with args {log_args}: {str(e)}", exc_info=True)
        error_msg_template = getattr(Errors, 'UNEXPECTED_ERROR', "An unexpected server error occurred: {error}")
        detail_msg = error_msg_template.format(error=f"processing game data via {func_name}")
        raise HTTPException(status_code=500, detail=detail_msg)


@router.get(
    "/boxscore/traditional/{game_id}",
    summary="Get Traditional Box Score for a Game",
    description="Fetches the traditional box score (points, rebounds, assists, etc.) for a specified NBA game ID. "
                "Data includes player stats, team stats, and starter/bench splits.",
    response_model=Dict[str, Any] # Explicitly define response model for OpenAPI
)
async def get_game_boxscore_traditional(
    game_id: str = Path(..., description="The 10-digit ID of the NBA game (e.g., '0022300161').", regex=r"^\d{10}$")
) -> Dict[str, Any]:
    """
    Endpoint to get the traditional box score for a game.
    Uses `fetch_boxscore_traditional_logic`.

    Path Parameters:
    - **game_id** (str, required): The 10-digit ID of the game.

    Successful Response (200 OK):
    Returns a dictionary containing traditional box score data.
    Refer to `fetch_boxscore_traditional_logic` in `game_tools.py` for detailed structure.
    Includes `teams`, `players`, and `starters_bench` statistics.

    Error Responses:
    - 400 Bad Request: If `game_id` is invalid.
    - 404 Not Found: If game data is not found.
    - 500 Internal Server Error: For other processing issues.
    """
    logger.info(f"Received GET /game/boxscore/traditional/{game_id} request.")
    # game_id format is validated by regex in Path parameter
    return await _handle_logic_call(fetch_boxscore_traditional_logic, game_id)

@router.get(
    "/playbyplay/{game_id}",
    summary="Get Play-by-Play Data for a Game",
    description="Fetches play-by-play data for a specified NBA game ID. "
                "Attempts to retrieve live data first; if unavailable, falls back to historical data. "
                "Period filtering applies only to historical data.",
    response_model=Dict[str, Any]
)
async def get_game_playbyplay(
    game_id: str = Path(..., description="The 10-digit ID of the NBA game.", regex=r"^\d{10}$"),
    start_period: int = Query(0, description="Filter Play-by-Play starting from this period (1-4, 5+ for OT, 0 for all). Only applies to historical data fallback.", ge=0),
    end_period: int = Query(0, description="Filter Play-by-Play ending at this period (1-4, 5+ for OT, 0 for all). Only applies to historical data fallback.", ge=0)
) -> Dict[str, Any]:
    """
    Endpoint to get Play-by-Play data for a game.
    Uses `fetch_playbyplay_logic`.

    Path Parameters:
    - **game_id** (str, required): The 10-digit ID of the game.

    Query Parameters:
    - **start_period** (int, optional): Starting period for filtering (0 for all). Default: 0.
    - **end_period** (int, optional): Ending period for filtering (0 for all). Default: 0.

    Successful Response (200 OK):
    Returns a dictionary containing play-by-play data.
    Refer to `fetch_playbyplay_logic` in `game_tools.py` for detailed structure.
    Includes `source` (live/historical) and `periods` with plays.

    Error Responses:
    - 400 Bad Request: If `game_id` is invalid.
    - 404 Not Found: If game data is not found.
    - 500 Internal Server Error: For other processing issues.
    """
    logger.info(f"Received GET /game/playbyplay/{game_id} request with start_period={start_period}, end_period={end_period}.")
    return await _handle_logic_call(fetch_playbyplay_logic, game_id, start_period, end_period)

@router.get(
    "/shotchart/{game_id}",
    summary="Get Shot Chart Data for a Game",
    description="Fetches shot chart data for all players in a specified NBA game ID, "
                "including shot locations, outcomes, and league averages for zones.",
    response_model=Dict[str, Any]
)
async def get_game_shotchart(
    game_id: str = Path(..., description="The 10-digit ID of the NBA game.", regex=r"^\d{10}$")
) -> Dict[str, Any]:
    """
    Endpoint to get shot chart data for a game.
    Uses `fetch_shotchart_logic`.

    Path Parameters:
    - **game_id** (str, required): The 10-digit ID of the game.

    Successful Response (200 OK):
    Returns a dictionary containing shot chart data.
    Refer to `fetch_shotchart_logic` in `game_tools.py` for detailed structure.
    Includes `teams` with player shots and `league_averages`.

    Error Responses:
    - 400 Bad Request: If `game_id` is invalid.
    - 404 Not Found: If game data is not found.
    - 500 Internal Server Error: For other processing issues.
    """
    logger.info(f"Received GET /game/shotchart/{game_id} request.")
    return await _handle_logic_call(fetch_shotchart_logic, game_id)

@router.get(
    "/boxscore/advanced/{game_id}",
    summary="Get Advanced Box Score for a Game",
    description="Fetches advanced box score statistics (e.g., Offensive/Defensive Rating, Pace, PIE) for a specified NBA game ID.",
    response_model=Dict[str, Any]
)
async def get_advanced_boxscore(
    game_id: str = Path(..., description="The 10-digit ID of the NBA game.", regex=r"^\d{10}$")
) -> Dict[str, Any]:
    """Endpoint to get advanced box score data. Uses `fetch_boxscore_advanced_logic`."""
    logger.info(f"Received GET /game/boxscore/advanced/{game_id}")
    return await _handle_logic_call(fetch_boxscore_advanced_logic, game_id)

@router.get(
    "/boxscore/fourfactors/{game_id}",
    summary="Get Four Factors Box Score for a Game",
    description="Fetches Four Factors box score statistics (Effective FG%, Turnover Rate, Rebound Rate, Free Throw Rate) for a specified NBA game ID.",
    response_model=Dict[str, Any]
)
async def get_four_factors_boxscore(
    game_id: str = Path(..., description="The 10-digit ID of the NBA game.", regex=r"^\d{10}$")
) -> Dict[str, Any]:
    """Endpoint to get Four Factors box score data. Uses `fetch_boxscore_four_factors_logic`."""
    logger.info(f"Received GET /game/boxscore/fourfactors/{game_id}")
    return await _handle_logic_call(fetch_boxscore_four_factors_logic, game_id)

@router.get(
    "/boxscore/usage/{game_id}",
    summary="Get Usage Statistics Box Score for a Game",
    description="Fetches usage statistics (e.g., USG%, %FGA, %AST) for all players in a specified NBA game ID.",
    response_model=Dict[str, Any]
)
async def get_usage_boxscore(
    game_id: str = Path(..., description="The 10-digit ID of the NBA game.", regex=r"^\d{10}$")
) -> Dict[str, Any]:
    """Endpoint to get usage box score data. Uses `fetch_boxscore_usage_logic`."""
    logger.info(f"Received GET /game/boxscore/usage/{game_id}")
    return await _handle_logic_call(fetch_boxscore_usage_logic, game_id)

@router.get(
    "/boxscore/defensive/{game_id}",
    summary="Get Defensive Box Score for a Game",
    description="Fetches defensive statistics (e.g., opponent shooting percentages when player is defending) for a specified NBA game ID.",
    response_model=Dict[str, Any]
)
async def get_defensive_boxscore(
    game_id: str = Path(..., description="The 10-digit ID of the NBA game.", regex=r"^\d{10}$")
) -> Dict[str, Any]:
    """Endpoint to get defensive box score data. Uses `fetch_boxscore_defensive_logic`."""
    logger.info(f"Received GET /game/boxscore/defensive/{game_id}")
    return await _handle_logic_call(fetch_boxscore_defensive_logic, game_id)

@router.get(
    "/winprobability/{game_id}",
    summary="Get Win Probability Data for a Game",
    description="Fetches win probability data points throughout a specified NBA game ID, showing how win likelihood changed with each play.",
    response_model=Dict[str, Any]
)
async def get_win_probability(
    game_id: str = Path(..., description="The 10-digit ID of the NBA game.", regex=r"^\d{10}$")
) -> Dict[str, Any]:
    """Endpoint to get win probability data. Uses `fetch_win_probability_logic`."""
    logger.info(f"Received GET /game/winprobability/{game_id}")
    # fetch_win_probability_logic takes an optional run_type, defaulting to "0".
    # If this needs to be exposed, add a Query parameter.
    return await _handle_logic_call(fetch_win_probability_logic, game_id)

# Note: The /find endpoint (LeagueGameFinder) is typically more of a league/search utility.
# If it's intended to be part of game-specific routes, it can be added here.
# Otherwise, it might belong in a separate `league.py` or `search.py` router.
# For now, assuming it's handled elsewhere or will be added if requested.
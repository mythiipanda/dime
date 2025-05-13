import logging
import asyncio
import json
from fastapi import APIRouter, HTTPException, Body, Query
from typing import Dict, Any, Optional # Added Optional for query parameters
# Use the correctly defined PlayerAnalysisRequest from schemas.py
from backend.schemas import PlayerAnalysisRequest # Changed from AnalyzeRequest
from backend.api_tools.analyze import analyze_player_stats_logic
from backend.api_tools.advanced_metrics import fetch_player_advanced_analysis_logic
from backend.api_tools.shot_charts import fetch_player_shot_chart
from backend.core.errors import Errors # Changed

# Router for player analysis related endpoints
# No prefix here, as it's applied in main.py (e.g., /api/v1/analyze)
router = APIRouter(
    tags=["Analysis", "Players"] # Grouped under Analysis, also relevant to Players
)
logger = logging.getLogger(__name__)

@router.post(
    "/player", # This will be mounted under /api/v1/analyze, resulting in /api/v1/analyze/player
    response_model=Dict[str, Any],
    summary="Analyze Player Statistics",
    description="Fetches and returns overall dashboard statistics for a specified player and season. "
                "The underlying logic uses the `PlayerDashboardByYearOverYear` NBA API endpoint, "
                "focusing on the 'OverallPlayerDashboard' data for the given season."
)
async def analyze_player_stats_endpoint(
    request: PlayerAnalysisRequest = Body(...) # Use the correct Pydantic model
) -> Dict[str, Any]:
    """
    Analyzes player statistics based on the provided player name and season.

    This endpoint retrieves overall dashboard statistics for a player for a specific season.
    It leverages a logic function that calls the NBA API.

    Request Body (`PlayerAnalysisRequest`):
    - **player_name** (str, required): The full name of the player to analyze (e.g., "LeBron James").
    - **season** (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
      If not provided, the logic layer defaults to the `CURRENT_SEASON` defined in the backend configuration.
    - **season_type** (str, optional): The type of season (e.g., "Regular Season", "Playoffs").
      Defaults to "Regular Season" in the logic layer.
    - **per_mode** (str, optional): The statistical mode (e.g., "PerGame", "Totals").
      Defaults to "PerGame" in the logic layer.
    - **league_id** (str, optional): The league ID (e.g., "00" for NBA).
      Defaults to "00" (NBA) in the logic layer.

    Successful Response (200 OK):
    Returns a dictionary containing the player's analysis. Example structure:
    ```json
    {
        "player_name": "LeBron James",
        "player_id": 2544,
        "season": "2023-24",
        // ... other fields from PlayerAnalysisRequest if returned by logic
        "overall_dashboard_stats": {
            "GROUP_SET": "Overall",
            "PLAYER_ID": 2544,
            // ... many other statistical fields
        }
    }
    ```
    If no data is found, `overall_dashboard_stats` might be empty or an error might be indicated.

    Error Responses:
    - **400 Bad Request**: If input validation fails (e.g., invalid season format, missing player_name).
    - **404 Not Found**: If the specified player is not found by the logic layer.
    - **500 Internal Server Error**: For unexpected errors during API calls or data processing.
    """
    logger.info(f"Received POST /analyze/player request for: {request.player_name}, Season: {request.season}")

    # Pydantic model `PlayerAnalysisRequest` handles initial validation of field types and presence.
    # Further business logic validation (e.g., season format if not covered by regex in Pydantic)
    # can be in the logic layer or here if simple.
    # The `pattern` in Pydantic Field for `season` should handle format validation.

    try:
        result_json_string = await asyncio.to_thread(
            analyze_player_stats_logic,
            request.player_name,
            request.season,
            request.season_type.value if request.season_type else None, # Pass enum value
            request.per_mode.value if request.per_mode else None,       # Pass enum value
            request.league_id.value if request.league_id else None      # Pass enum value
        )
        result_data = json.loads(result_json_string)

        if isinstance(result_data, dict) and 'error' in result_data:
            error_detail = result_data['error']
            logger.error(f"Error from analyze_player_stats_logic for {request.player_name}: {error_detail}")
            status_code = 404 if "not found" in error_detail.lower() or "invalid player" in error_detail.lower() else \
                          400 if "invalid" in error_detail.lower() or "missing parameter" in error_detail.lower() else 500
            raise HTTPException(status_code=status_code, detail=error_detail)

        logger.info(f"Successfully analyzed stats for player: {request.player_name}")
        return result_data

    except HTTPException as http_exc:
        raise http_exc
    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to parse JSON response from logic layer for {request.player_name}: {json_err}", exc_info=True)
        raise HTTPException(status_code=500, detail=Errors.JSON_PROCESSING_ERROR)
    except Exception as e:
        logger.critical(f"Unexpected error in /analyze/player endpoint for {request.player_name}: {str(e)}", exc_info=True)
        detail_msg = Errors.UNEXPECTED_ERROR.format(error=f"analyzing player stats for {request.player_name}")
        raise HTTPException(status_code=500, detail=detail_msg)

@router.get(
    "/player/{player_name}/advanced",
    response_model=Dict[str, Any],
    summary="Get Advanced Player Metrics",
    description="Fetches advanced metrics, skill grades, and similar players for a specified player."
)
async def get_player_advanced_metrics(
    player_name: str
) -> Dict[str, Any]:
    """
    Retrieves advanced metrics and analysis for a player.

    This endpoint provides comprehensive advanced analytics including:
    - Advanced metrics (EPM, RAPTOR, DARKO, LEBRON, etc.)
    - Skill grades (shooting, defense, playmaking, etc.)
    - Similar players with similarity scores

    Path Parameters:
    - **player_name** (str, required): The full name of the player to analyze (e.g., "LeBron James").

    Successful Response (200 OK):
    Returns a dictionary containing the player's advanced analysis. Example structure:
    ```json
    {
        "player_name": "LeBron James",
        "player_id": 2544,
        "advanced_metrics": {
            "EPM": 5.2,
            "EPM_OFF": 4.1,
            "EPM_DEF": 1.1,
            // ... other advanced metrics
        },
        "skill_grades": {
            "perimeter_shooting": "B",
            "interior_scoring": "A",
            // ... other skill grades
        },
        "similar_players": [
            {"player_id": 201142, "player_name": "Kevin Durant", "similarity_score": 0.92},
            // ... other similar players
        ]
    }
    ```

    Error Responses:
    - **404 Not Found**: If the specified player is not found.
    - **500 Internal Server Error**: For unexpected errors during data processing.
    """
    logger.info(f"Received GET /analyze/player/{player_name}/advanced request")

    try:
        result_json_string = await asyncio.to_thread(
            fetch_player_advanced_analysis_logic,
            player_name
        )
        result_data = json.loads(result_json_string)

        if isinstance(result_data, dict) and 'error' in result_data:
            error_detail = result_data['error']
            logger.error(f"Error from fetch_player_advanced_analysis_logic for {player_name}: {error_detail}")
            status_code = 404 if "not found" in error_detail.lower() else 500
            raise HTTPException(status_code=status_code, detail=error_detail)

        logger.info(f"Successfully fetched advanced metrics for player: {player_name}")
        return result_data

    except HTTPException as http_exc:
        raise http_exc
    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to parse JSON response from logic layer for {player_name}: {json_err}", exc_info=True)
        raise HTTPException(status_code=500, detail=Errors.JSON_PROCESSING_ERROR)
    except Exception as e:
        logger.critical(f"Unexpected error in /analyze/player/{player_name}/advanced endpoint: {str(e)}", exc_info=True)
        detail_msg = Errors.UNEXPECTED_ERROR.format(error=f"fetching advanced metrics for {player_name}")
        raise HTTPException(status_code=500, detail=detail_msg)

@router.get(
    "/player/{player_name}/shots",
    response_model=Dict[str, Any],
    summary="Get Player Shot Chart Data",
    description="Fetches shot chart data and zone analysis for a specified player."
)
async def get_player_shot_chart(
    player_name: str,
    season: Optional[str] = Query(None, description="NBA season in format YYYY-YY (e.g., '2023-24')"),
    season_type: str = Query("Regular Season", description="Type of season: 'Regular Season', 'Playoffs', 'Pre Season', 'All Star'"),
    last_n_games: int = Query(0, description="Number of most recent games to include (0 for all games)")
) -> Dict[str, Any]:
    """
    Retrieves shot chart data for a player.

    This endpoint provides comprehensive shot data including:
    - Individual shots with coordinates, shot type, and outcome
    - Zone analysis with shooting percentages and league comparisons

    Path Parameters:
    - **player_name** (str, required): The full name of the player to analyze (e.g., "LeBron James").

    Query Parameters:
    - **season** (str, optional): NBA season in format YYYY-YY (e.g., "2023-24"). Defaults to current season.
    - **season_type** (str, optional): Type of season. Options: "Regular Season", "Playoffs", "Pre Season", "All Star".
    - **last_n_games** (int, optional): Number of most recent games to include (0 for all games).

    Successful Response (200 OK):
    Returns a dictionary containing the player's shot data. Example structure:
    ```json
    {
        "player_name": "LeBron James",
        "player_id": 2544,
        "team_name": "Los Angeles Lakers",
        "team_id": 1610612747,
        "season": "2023-24",
        "season_type": "Regular Season",
        "shots": [
            {
                "x": -80.0,
                "y": 120.0,
                "made": true,
                "value": 2,
                "shot_type": "Jump Shot",
                "shot_zone": "Mid-Range - Left Side",
                "distance": 14.0,
                "game_date": "2023-10-24",
                "period": 1
            },
            // ... other shots
        ],
        "zones": [
            {
                "zone": "Restricted Area",
                "attempts": 120,
                "made": 84,
                "percentage": 0.7,
                "leaguePercentage": 0.65,
                "relativePercentage": 0.05
            },
            // ... other zones
        ]
    }
    ```

    Error Responses:
    - **404 Not Found**: If the specified player is not found.
    - **500 Internal Server Error**: For unexpected errors during data processing.
    """
    logger.info(f"Received GET /analyze/player/{player_name}/shots request")

    try:
        result_json_string = await asyncio.to_thread(
            fetch_player_shot_chart,
            player_name=player_name,
            season=season,
            season_type=season_type,
            last_n_games=last_n_games
        )
        result_data = json.loads(result_json_string)

        if isinstance(result_data, dict) and 'error' in result_data:
            error_detail = result_data['error']
            logger.error(f"Error from fetch_player_shot_chart for {player_name}: {error_detail}")
            status_code = 404 if "not found" in error_detail.lower() else 500
            raise HTTPException(status_code=status_code, detail=error_detail)

        logger.info(f"Successfully fetched shot chart data for player: {player_name}")
        return result_data

    except HTTPException as http_exc:
        raise http_exc
    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to parse JSON response from logic layer for {player_name}: {json_err}", exc_info=True)
        raise HTTPException(status_code=500, detail=Errors.JSON_PROCESSING_ERROR)
    except Exception as e:
        logger.critical(f"Unexpected error in /analyze/player/{player_name}/shots endpoint: {str(e)}", exc_info=True)
        detail_msg = Errors.UNEXPECTED_ERROR.format(error=f"fetching shot chart data for {player_name}")
        raise HTTPException(status_code=500, detail=detail_msg)
import logging
import asyncio
import json
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status

from backend.api_tools.odds_tools import fetch_odds_data_logic
from backend.core.errors import Errors

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/odds",  # Standard prefix for odds-related endpoints
    tags=["Odds"]    # Tag for OpenAPI documentation
)

async def _handle_odds_route_logic_call(
    logic_function: callable, 
    endpoint_name: str,
    *args, 
    **kwargs
) -> Dict[str, Any]:
    """Helper to call odds-related logic, parse JSON, and handle errors."""
    try:
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        
        result_json_string = await asyncio.to_thread(logic_function, *args, **filtered_kwargs)
        result_data = json.loads(result_json_string)

        if isinstance(result_data, dict) and 'error' in result_data:
            error_detail = result_data['error']
            logger.error(f"Error from {logic_function.__name__} with args {args}, kwargs {filtered_kwargs}: {error_detail}")
            status_code_to_raise = status.HTTP_502_BAD_GATEWAY if "external api" in error_detail.lower() or "provider error" in error_detail.lower() else \
                                   status.HTTP_400_BAD_REQUEST if "invalid parameter" in error_detail.lower() else \
                                   status.HTTP_500_INTERNAL_SERVER_ERROR # Default
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
    "/live",
    summary="Get Live Betting Odds for NBA Games",
    description="Fetches live betting odds for upcoming or in-progress NBA games from configured odds providers. "
                "The specific games and markets returned depend on the provider and data availability.",
    response_model=Dict[str, Any]
)
async def get_live_betting_odds_endpoint(
) -> Dict[str, Any]:
    """
    Endpoint to retrieve live betting odds for NBA games.
    Uses `fetch_odds_data_logic` from `odds_tools.py`.

    Query Parameters:
    - (Currently none exposed. The underlying logic fetches general live odds.
      Future enhancements could add parameters for date, league, odds format, markets.)

    Successful Response (200 OK):
    Returns a dictionary (or list) containing odds data. The exact structure depends
    on the `fetch_odds_data_logic` implementation and the odds provider's API.
    Typically, it might include a list of games, each with:
    - Game identifiers (e.g., home team, away team, start time).
    - Bookmakers list, each offering markets like:
        - Head-to-head (moneyline)
        - Spreads (points)
        - Totals (over/under)
    Example (conceptual):
    ```json
    {
        "source": "OddsProviderName",
        "last_update": "timestamp",
        "games": [
            {
                "game_id_provider": "unique_game_id",
                "home_team": "Team A",
                "away_team": "Team B",
                "start_time": "iso_timestamp",
                "bookmakers": [
                    {
                        "name": "Bookie1",
                        "markets": {
                            "h2h": [{"name": "Team A", "price": 1.90}, {"name": "Team B", "price": 1.90}],
                            "spreads": [{"name": "Team A", "points": -1.5, "price": 1.91}, {"name": "Team B", "points": 1.5, "price": 1.91}]
                        }
                    },
                    // ... more bookmakers
                ]
            },
            // ... more games
        ]
    }
    ```
    If no odds are available, it might return an empty list or a structure indicating no data.

    Error Responses:
    - 500 Internal Server Error: For unexpected errors.
    - 502 Bad Gateway: If there's an issue fetching data from the external odds provider.
    - 400 Bad Request: If query parameters were added and they are invalid.
    """
    logger.info("Request received for GET /odds/live")
    
    odds_kwargs = {
    }

    return await _handle_odds_route_logic_call(
        fetch_odds_data_logic, "live betting odds",
        **odds_kwargs
    )

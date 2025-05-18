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
    as_dataframe: bool = False
) -> Dict[str, Any]:
    """
    Endpoint to retrieve live betting odds for NBA games.
    Uses `fetch_odds_data_logic` from `odds_tools.py`.

    Query Parameters:
    - as_dataframe (bool, optional): If True, returns a flattened representation of the odds data
      and saves it to a CSV file in the cache directory. The DataFrame is structured to make it more
      usable for analysis. Defaults to False.

    Successful Response (200 OK):
    Returns a dictionary containing odds data. The exact structure depends
    on the `fetch_odds_data_logic` implementation and the odds provider's API.

    Standard response (as_dataframe=False):
    ```json
    {
        "games": [
            {
                "gameId": "0042400216",
                "homeTeamId": 1610612752,
                "awayTeamId": 1610612738,
                "gameTime": "2023-05-18T19:30:00Z",
                "gameStatus": 1,
                "gameStatusText": "Scheduled",
                "markets": [
                    {
                        "marketId": "spread",
                        "name": "Point Spread",
                        "books": [
                            {
                                "bookId": "fanduel",
                                "name": "FanDuel",
                                "outcomes": [
                                    {
                                        "type": "home",
                                        "odds": "-110",
                                        "value": "-5.5"
                                    },
                                    {
                                        "type": "away",
                                        "odds": "-110",
                                        "value": "+5.5"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }
    ```

    DataFrame response (as_dataframe=True):
    ```json
    {
        "games": [...],  // Same as standard response
        "dataframe_info": {
            "message": "Odds data has been converted to a DataFrame and saved as CSV",
            "dataframe_shape": [40, 14],
            "dataframe_columns": ["gameId", "awayTeamId", "homeTeamId", "gameTime", "gameStatus", "gameStatusText",
                                 "marketId", "marketName", "bookId", "bookName", "outcomeType", "odds", "openingOdds", "value"],
            "csv_path": "backend/cache/odds_data.csv",
            "sample_data": [
                {
                    "gameId": "0042400216",
                    "awayTeamId": 1610612738,
                    "homeTeamId": 1610612752,
                    "marketName": "Point Spread",
                    "bookName": "FanDuel",
                    "outcomeType": "home",
                    "odds": "-110",
                    "value": "-5.5"
                }
            ]
        }
    }
    ```

    If no odds are available, it might return an empty list or a structure indicating no data.

    Error Responses:
    - 500 Internal Server Error: For unexpected errors.
    - 502 Bad Gateway: If there's an issue fetching data from the external odds provider.
    - 400 Bad Request: If query parameters were added and they are invalid.
    """
    logger.info(f"Request received for GET /odds/live with as_dataframe={as_dataframe}")

    odds_kwargs = {
        "return_dataframe": as_dataframe
    }

    if as_dataframe:
        # For DataFrame output, we need to handle the response differently
        try:
            filtered_kwargs = {k: v for k, v in odds_kwargs.items() if v is not None}

            # Call the logic function with return_dataframe=True
            json_response, df = await asyncio.to_thread(fetch_odds_data_logic, **filtered_kwargs)
            result_data = json.loads(json_response)

            if isinstance(result_data, dict) and 'error' in result_data:
                error_detail = result_data['error']
                logger.error(f"Error from fetch_odds_data_logic with kwargs {filtered_kwargs}: {error_detail}")
                status_code_to_raise = status.HTTP_502_BAD_GATEWAY if "external api" in error_detail.lower() or "provider error" in error_detail.lower() else \
                                      status.HTTP_400_BAD_REQUEST if "invalid parameter" in error_detail.lower() else \
                                      status.HTTP_500_INTERNAL_SERVER_ERROR # Default
                raise HTTPException(status_code=status_code_to_raise, detail=error_detail)

            # Add DataFrame info to the response
            df_info = {
                "message": "Odds data has been converted to a DataFrame and saved as CSV",
                "dataframe_shape": df.shape,
                "dataframe_columns": df.columns.tolist(),
                "csv_path": "backend/cache/odds_data.csv",
                "sample_data": df.head(5).to_dict(orient="records") if not df.empty else []
            }
            result_data["dataframe_info"] = df_info

            return result_data

        except HTTPException as http_exc:
            raise http_exc
        except json.JSONDecodeError as json_err:
            logger.error(f"Failed to parse JSON response from fetch_odds_data_logic for kwargs {filtered_kwargs}: {json_err}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=Errors.JSON_PROCESSING_ERROR)
        except Exception as e:
            logger.critical(f"Unexpected error in API route calling fetch_odds_data_logic for kwargs {filtered_kwargs}: {str(e)}", exc_info=True)
            error_msg_template = getattr(Errors, 'UNEXPECTED_ERROR', "An unexpected server error occurred: {error}")
            detail_msg = error_msg_template.format(error=f"processing live betting odds")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail_msg)
    else:
        # For standard JSON output, use the existing helper function
        return await _handle_odds_route_logic_call(
            fetch_odds_data_logic, "live betting odds",
            **odds_kwargs
        )

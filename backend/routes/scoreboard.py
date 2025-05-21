from fastapi import APIRouter, Query, HTTPException, status, WebSocket, WebSocketDisconnect
import logging
from typing import Any, Dict, Optional
from datetime import date
import json
import asyncio
from starlette.websockets import WebSocketState

from backend.api_tools.scoreboard_tools import fetch_scoreboard_data_logic
from backend.utils.validation import validate_date_format
from backend.core.errors import Errors

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/scoreboard", # Add prefix for scoreboard routes
    tags=["Scoreboard"]    # Tag for OpenAPI documentation
)

@router.websocket("/ws")
async def scoreboard_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time NBA scoreboard updates.

    Connects a client via WebSocket and streams scoreboard data approximately every 30 seconds.
    The data streamed is the same as the `GET /scoreboard/` endpoint (for the current day).

    Message Format (JSON, sent from server to client):
    ```json
    {
        "game_date": "YYYY-MM-DD",
        "games": [
            {
                "game_id": "0022300161",
                "game_status_text": "Final",
                "home_team": { "team_id": ..., "team_name": "Nuggets", "score": 110, ... },
                "away_team": { "team_id": ..., "team_name": "Lakers", "score": 99, ... },
                // ... other game details
            },
            // ... more games
        ]
    }
    ```
    If an error occurs while fetching data on the server, updates might be skipped for that cycle,
    or the connection might be closed if the error is persistent or critical.
    """
    logger.info(f"New WebSocket connection request from {websocket.client}")
    await websocket.accept()
    logger.info(f"WebSocket connection accepted for {websocket.client}")
    try:
        while True:
            if websocket.application_state != WebSocketState.CONNECTED:
                logger.warning(f"WebSocket {websocket.client} no longer connected (application_state). Stopping updates.")
                break
            
            try:
                # Fetch latest scoreboard data (logic defaults to today if game_date is None)
                data_json_string = await asyncio.to_thread(
                    fetch_scoreboard_data_logic, 
                    game_date=None, 
                    bypass_cache=True # Ensure fresh data for WebSocket
                )
                
                try:
                    data_dict_parsed = json.loads(data_json_string)
                    
                    if isinstance(data_dict_parsed, dict) and 'error' not in data_dict_parsed:
                        logger.debug(f"Sending scoreboard update to WebSocket {websocket.client}")
                        await websocket.send_json(data_dict_parsed)
                    elif isinstance(data_dict_parsed, dict) and 'error' in data_dict_parsed:
                        logger.warning(f"Scoreboard logic returned an error: {data_dict_parsed['error']}. Not sending to WebSocket client {websocket.client}.")
                    else:
                        logger.warning(f"Scoreboard logic returned unexpected data structure. Not sending to WebSocket client {websocket.client}. Data (first 100 chars): {str(data_dict_parsed)[:100]}")
                
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON from scoreboard logic for WebSocket {websocket.client}. Response: {data_json_string[:200]}...")
                except Exception as send_err:
                    logger.error(f"Error processing/sending scoreboard data to WebSocket {websocket.client}: {send_err}", exc_info=True)
                    # Decide if to break or continue based on error type
                    if not (websocket.application_state == WebSocketState.CONNECTED): break # Break if disconnected during send
                    # Otherwise, log and continue to next update cycle for transient send issues.

                await asyncio.sleep(2) # Interval for updates, changed from 30 to 10

            except WebSocketDisconnect:
                logger.info(f"WebSocket client {websocket.client} disconnected.")
                break
            except asyncio.CancelledError:
                logger.info(f"WebSocket update task cancelled for {websocket.client}.")
                break
            except Exception as loop_err: # Catch errors within the loop (e.g., from fetch_scoreboard_data_logic if it raises)
                logger.error(f"Error during scoreboard update loop for {websocket.client}: {str(loop_err)}", exc_info=True)
                # Attempt to close gracefully if still connected
                if websocket.application_state == WebSocketState.CONNECTED:
                    await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
                break # Exit loop on significant error

    except Exception as e: # Catch errors during initial accept or setup
        logger.error(f"WebSocket connection error for {websocket.client}: {str(e)}", exc_info=True)
        if websocket.application_state != WebSocketState.DISCONNECTED:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
    finally:
        logger.info(f"Closing WebSocket connection for {websocket.client}")
        if websocket.application_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
            except RuntimeError as rt_err:
                 logger.debug(f"RuntimeError during final WebSocket close for {websocket.client} (likely already closing/closed): {rt_err}")
            except Exception as final_close_err:
                 logger.warning(f"Error during final WebSocket close for {websocket.client}: {final_close_err}")


@router.get(
    "/", 
    summary="Get Scoreboard by Date", 
    description="Fetches NBA scoreboard data (list of games, status, scores) for a specific date. "
                "If no date is provided, it defaults to the current day's scoreboard.",
    response_model=Dict[str, Any]
)
async def get_scoreboard_by_date_endpoint(
    game_date: Optional[str] = Query(
        default=None, 
        description="The date for which to fetch the scoreboard, in YYYY-MM-DD format. "
                    "If not provided, defaults to the current date.",
        regex=r"^\d{4}-\d{2}-\d{2}$"
    )
) -> Dict[str, Any]:
    """
    API endpoint to retrieve scoreboard data for a given date.
    Uses `fetch_scoreboard_data_logic`.

    Query Parameters:
    - **game_date** (str, optional): Date in YYYY-MM-DD format. Defaults to today.

    Successful Response (200 OK):
    Returns a dictionary containing the game date and a list of games.
    Example:
    ```json
    {
        "game_date": "2023-10-25",
        "games": [
            {
                "game_id": "0022300001",
                "game_status_text": "Final",
                "home_team": {"team_id": 1610612738, "team_name": "Celtics", "score": 120, ...},
                "away_team": {"team_id": 1610612752, "team_name": "Knicks", "score": 110, ...},
                // ... other game details like period, game_time_utc
            }
        ]
    }
    ```
    If no games are found for the date, `games` will be an empty list.

    Error Responses:
    - 400 Bad Request: If `game_date` format is invalid.
    - 500 Internal Server Error: For unexpected errors or issues fetching/processing data.
    - 502 Bad Gateway: If the underlying NBA API call fails. (Handled by logic layer, may result in 500 here)
    """
    effective_game_date_str = game_date or date.today().strftime('%Y-%m-%d')
    logger.info(f"Received GET /scoreboard/ request for date: {effective_game_date_str}.")

    if game_date and not validate_date_format(game_date):
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST, 
             detail=Errors.INVALID_DATE_FORMAT.format(date=game_date)
         )

    try:
        result_json_string = await asyncio.to_thread(fetch_scoreboard_data_logic, game_date=game_date)
        result_data = json.loads(result_json_string)

        if isinstance(result_data, dict) and 'error' in result_data:
            error_detail = result_data['error']
            logger.error(f"Error from fetch_scoreboard_data_logic for date {effective_game_date_str}: {error_detail}")
            # Map common errors from logic to appropriate HTTP status codes
            status_code_to_raise = status.HTTP_500_INTERNAL_SERVER_ERROR # Default
            if "not found" in error_detail.lower():
                status_code_to_raise = status.HTTP_404_NOT_FOUND
            elif "invalid date" in error_detail.lower() or "invalid format" in error_detail.lower():
                status_code_to_raise = status.HTTP_400_BAD_REQUEST
            
            raise HTTPException(status_code=status_code_to_raise, detail=error_detail)
        
        logger.info(f"Successfully processed scoreboard data for {result_data.get('game_date', effective_game_date_str)}.")
        return result_data

    except HTTPException as http_exc:
        raise http_exc
    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to parse JSON response from scoreboard logic for date {effective_game_date_str}: {json_err}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=Errors.JSON_PROCESSING_ERROR)
    except Exception as e:
        logger.critical(f"Unexpected error in scoreboard GET endpoint for date {effective_game_date_str}: {str(e)}", exc_info=True)
        error_msg = Errors.UNEXPECTED_ERROR.format(error=f"fetching scoreboard for date {effective_game_date_str}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg)
import asyncio
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from backend.api_tools.live_game_tools import fetch_league_scoreboard_logic
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/scoreboard")
async def get_live_scoreboard():
    """
    Get live NBA scoreboard data including game scores, status, and game leaders.
    
    Returns:
        JSON containing:
        - game_date: Date of the games
        - games: List of game information including:
            - game_id: Unique identifier for the game
            - status: Current game status
            - period: Current period
            - game_clock: Current game clock
            - home_team: Home team information and score
            - away_team: Away team information and score
            - game_leaders: Statistical leaders for both teams
    """
    try:
        scoreboard_data = fetch_league_scoreboard_logic()
        return scoreboard_data
    except Exception as e:
        logger.error(f"Error in GET /scoreboard: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching live scoreboard data: {str(e)}"
        )

@router.websocket("/scoreboard/ws")
async def websocket_scoreboard_endpoint(websocket: WebSocket):
    """Provides live scoreboard updates via WebSocket."""
    await websocket.accept()
    logger.info(f"WebSocket connection accepted for scoreboard from {websocket.client.host}:{websocket.client.port}")
    try:
        while True:
            try:
                scoreboard_data_str = fetch_league_scoreboard_logic()
                
                # Try sending data
                await websocket.send_text(scoreboard_data_str)
                logger.debug(f"Sent scoreboard update to {websocket.client.host}:{websocket.client.port}")
                
                # Wait for 3 seconds before fetching again
                await asyncio.sleep(3)
                
            # Catch specific exceptions related to sending to a closed connection
            except (WebSocketDisconnect, RuntimeError) as e:
                # RuntimeError typically occurs if send is called after close frame sent
                logger.info(f"Client {websocket.client.host}:{websocket.client.port} disconnected ({type(e).__name__}). Stopping updates for this client.")
                break # Exit the loop for this client
            except Exception as e:
                # Catch other potential errors during fetch/send
                logger.error(f"Error during WebSocket update loop for {websocket.client.host}:{websocket.client.port}: {str(e)}", exc_info=True)
                # Optional: Send error to client if connection is still open?
                # await websocket.send_text(json.dumps({"error": "Failed to fetch updates"}))
                # Decide if we should break or continue after other errors
                await asyncio.sleep(10) # Wait before retrying after other errors

    except WebSocketDisconnect:
        # This catches disconnects that happen *outside* the send attempt (e.g., during accept or sleep)
        logger.info(f"WebSocket connection closed by client {websocket.client.host}:{websocket.client.port} (caught outside send). ")
    except Exception as e:
        # Catch unexpected errors during initial connection handling or loop setup
        logger.error(f"Unexpected error in WebSocket handler for {websocket.client.host}:{websocket.client.port}: {str(e)}", exc_info=True)
        # Ensure connection is closed if possible
        try:
             await websocket.close(code=1011) # Internal Error
        except RuntimeError: # Handle cases where close is called on an already closed socket
             pass 
    finally:
        # Log when the handler function for a specific client is fully exiting
        logger.info(f"WebSocket handler finished for {websocket.client.host}:{websocket.client.port}")
import asyncio
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from backend.api_tools.live_game_tools import fetch_league_scoreboard_logic
import logging
import json

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
    
    await asyncio.sleep(0.1) # Keep delay
    
    try:
        # --- Remove initial simple message --- 
        # initial_message = json.dumps({"status": "connected", "message": "Connection acknowledged by server."}) 
        # try:
        #     await websocket.send_text(initial_message)
        #     logger.info(f"Sent initial connection acknowledgement to {websocket.client.host}:{websocket.client.port}")
        # except Exception as send_error:
        #     logger.error(f"*** Failed to send initial message to {websocket.client.host}:{websocket.client.port}: {send_error}", exc_info=True)
        #     try: await websocket.close(code=1011) 
        #     except: pass
        #     return
        # --- End removed initial message --- 
        
        # --- Restore the update loop --- 
        while True:
            try:
                scoreboard_data_str = fetch_league_scoreboard_logic()
                
                logger.debug(f"Attempting to send data to {websocket.client.host}:{websocket.client.port} (length: {len(scoreboard_data_str)}): {scoreboard_data_str[:500]}...")
                
                try:
                    await websocket.send_text(scoreboard_data_str)
                    logger.debug(f"Successfully sent scoreboard update to {websocket.client.host}:{websocket.client.port}")
                except Exception as send_error:
                    logger.error(f"*** Error DURING send_text to {websocket.client.host}:{websocket.client.port}: {send_error}", exc_info=True)
                    break 
                
                await asyncio.sleep(3)
                
            except (WebSocketDisconnect, RuntimeError) as e:
                logger.info(f"Client {websocket.client.host}:{websocket.client.port} disconnected ({type(e).__name__}). Stopping updates for this client.")
                break 
            except Exception as e:
                logger.error(f"Error during WebSocket update loop for {websocket.client.host}:{websocket.client.port}: {str(e)}", exc_info=True)
                await asyncio.sleep(10)
        # --- End restored loop --- 
        
        # --- Remove keep alive loop --- 
        # while True:
        #      await asyncio.sleep(60) 
        #      logger.debug(f"WebSocket connection still alive for {websocket.client.host}:{websocket.client.port}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket connection closed by client {websocket.client.host}:{websocket.client.port} (caught outside send). ")
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket handler for {websocket.client.host}:{websocket.client.port}: {str(e)}", exc_info=True)
        try: await websocket.close(code=1011) 
        except RuntimeError: pass 
    finally:
        logger.info(f"WebSocket handler finished for {websocket.client.host}:{websocket.client.port}")
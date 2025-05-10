import asyncio
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
import logging
import json
from typing import Dict, Any 
# Ensure this import points to the correct logic function for live scoreboard data.
from backend.api_tools.live_game_tools import fetch_league_scoreboard_logic # Corrected import
from backend.config import Errors
from starlette.websockets import WebSocketState # Added for explicit state checking

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/live",
    tags=["Live Games"]
)

# Note on Redundancy:
# The functionality in this file, particularly the GET /scoreboard and the /scoreboard/ws WebSocket,
# significantly overlaps with endpoints in `backend/routes/scoreboard.py`.
# Consideration should be given to consolidating these into a single, authoritative scoreboard route.

async def _handle_live_game_logic_call(
    logic_function: callable, 
    endpoint_name: str,
    *args, 
    **kwargs
) -> Dict[str, Any]:
    """Helper to call live game logic, parse JSON, and handle errors."""
    try:
        result_json_string = await asyncio.to_thread(logic_function, *args, **kwargs)
        result_data = json.loads(result_json_string)

        if isinstance(result_data, dict) and 'error' in result_data:
            error_detail = result_data['error']
            logger.error(f"Error from {logic_function.__name__} for {endpoint_name}: {error_detail}")
            status_code_to_raise = status.HTTP_502_BAD_GATEWAY if "external api" in error_detail.lower() or "provider error" in error_detail.lower() else \
                                   status.HTTP_500_INTERNAL_SERVER_ERROR
            raise HTTPException(status_code=status_code_to_raise, detail=error_detail)
        return result_data
    except HTTPException as http_exc:
        raise http_exc
    except json.JSONDecodeError as json_err:
        func_name = logic_function.__name__
        logger.error(f"Failed to parse JSON response from {func_name} for {endpoint_name}: {json_err}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=Errors.JSON_PROCESSING_ERROR)
    except Exception as e:
        func_name = logic_function.__name__
        logger.critical(f"Unexpected error in API route calling {func_name} for {endpoint_name}: {str(e)}", exc_info=True)
        error_msg_template = getattr(Errors, 'UNEXPECTED_ERROR', "An unexpected server error occurred: {error}")
        detail_msg = error_msg_template.format(error=f"processing {endpoint_name.lower()}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail_msg)

@router.get(
    "/scoreboard",
    summary="Get Current Live NBA Scoreboard",
    description="Fetches the current live NBA scoreboard data. (Consider using `/scoreboard/` in `scoreboard.py` for more flexibility).",
    response_model=Dict[str, Any]
)
async def get_current_live_scoreboard_endpoint() -> Dict[str, Any]:
    logger.info("Request received for GET /live/scoreboard (current live data)")
    # Corrected function call
    return await _handle_live_game_logic_call(fetch_league_scoreboard_logic, "live scoreboard")

@router.websocket("/scoreboard/ws")
async def live_scoreboard_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info(f"Live scoreboard WebSocket connection accepted from {websocket.client.host}:{websocket.client.port}")
    
    last_client_ping_time = asyncio.get_event_loop().time()
    stop_event = asyncio.Event()

    async def send_scoreboard_updates():
        nonlocal stop_event
        while not stop_event.is_set():
            try:
                if websocket.application_state != WebSocketState.CONNECTED:
                    logger.warning(f"WebSocket {websocket.client} no longer connected in send_scoreboard_updates. Stopping.")
                    stop_event.set()
                    break
                
                # Corrected function call
                scoreboard_json_str = await asyncio.to_thread(fetch_league_scoreboard_logic)
                try:
                    temp_data = json.loads(scoreboard_json_str)
                    if isinstance(temp_data, dict) and "error" in temp_data:
                        logger.warning(f"Live scoreboard logic returned error: {temp_data['error']}. Skipping send for this cycle.")
                        await asyncio.sleep(3) 
                        continue
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON from live scoreboard logic: {scoreboard_json_str[:200]}. Skipping send.")
                    await asyncio.sleep(3)
                    continue
                
                await websocket.send_text(scoreboard_json_str)
                logger.debug(f"Sent live scoreboard update to {websocket.client.host}:{websocket.client.port}")
            except WebSocketDisconnect: 
                logger.info(f"WebSocket client {websocket.client.host}:{websocket.client.port} disconnected during send. Stopping updates.")
                stop_event.set()
                break
            except Exception as send_error:
                logger.error(f"Error sending live scoreboard update to {websocket.client.host}:{websocket.client.port}: {send_error}", exc_info=True)
                stop_event.set() 
                break
            await asyncio.sleep(3) 

    async def client_ping_monitor():
        nonlocal last_client_ping_time, stop_event
        while not stop_event.is_set():
            await asyncio.sleep(5) 
            if (asyncio.get_event_loop().time() - last_client_ping_time) > 40: 
                logger.warning(f"No ping from client {websocket.client.host}:{websocket.client.port} in 40s. Closing connection.")
                stop_event.set()
                if websocket.application_state == WebSocketState.CONNECTED:
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION) 
                break
    
    update_task = asyncio.create_task(send_scoreboard_updates())
    monitor_task = asyncio.create_task(client_ping_monitor())

    try:
        while not stop_event.is_set():
            if websocket.application_state != WebSocketState.CONNECTED:
                logger.warning(f"WebSocket {websocket.client} disconnected in main receive loop. Stopping.")
                stop_event.set()
                break
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=45) 
                if message.strip().lower() == '{"type":"ping"}': 
                    last_client_ping_time = asyncio.get_event_loop().time()
                    logger.debug(f"Received ping from {websocket.client.host}:{websocket.client.port}")
                    await websocket.send_text('{"type":"pong"}') 
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for message/ping from {websocket.client.host}:{websocket.client.port}. Last ping: {last_client_ping_time:.0f}s ago.")
            except WebSocketDisconnect:
                logger.info(f"Client {websocket.client.host}:{websocket.client.port} disconnected (WebSocketDisconnect in receive loop).")
                stop_event.set()
                break 
    except WebSocketDisconnect: 
        logger.info(f"WebSocket connection (outer) closed by client {websocket.client.host}:{websocket.client.port}.")
    except Exception as e:
        logger.error(f"Unexpected error in live scoreboard WebSocket handler for {websocket.client.host}:{websocket.client.port}: {str(e)}", exc_info=True)
    finally:
        logger.info(f"Stopping tasks and closing live scoreboard WebSocket for {websocket.client.host}:{websocket.client.port}.")
        stop_event.set() 
        for task in [update_task, monitor_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.debug(f"Task {task.get_name()} cancelled for WebSocket {websocket.client.host}:{websocket.client.port}") # Use task.get_name()
                except Exception as task_ex:
                    logger.error(f"Error during task cleanup for {task.get_name()}: {task_ex}")
        
        if websocket.application_state == WebSocketState.CONNECTED:
            try:
                await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
            except RuntimeError as rt_err:
                 logger.debug(f"RuntimeError during final WebSocket close (live_game) for {websocket.client} (likely already closing/closed): {rt_err}")
            except Exception as final_close_err:
                 logger.warning(f"Error during final WebSocket close (live_game) for {websocket.client}: {final_close_err}")
        logger.info(f"Live scoreboard WebSocket handler finished for {websocket.client.host}:{websocket.client.port}")
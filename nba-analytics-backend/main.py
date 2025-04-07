# main.py - RESOLVED
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Generator, List # Added List for type hint
from agno.agent import RunResponse # Import RunResponse
import asyncio
import uvicorn
import logging
import json
import re
from textwrap import dedent

# Import agent classes/functions needed
from agno.agent import Agent
from agno.models.google import Gemini
from agents import data_aggregator_agent, analysis_agent, storage # Import sub-agents and storage
from teams import nba_analysis_team # Import the Team instance
# Removed duplicate import
from config import ( # Import constants
    LOG_FILENAME, LOG_FILE_MODE, CORS_ALLOWED_ORIGINS,
    SUPPORTED_FETCH_TARGETS, UVICORN_HOST, UVICORN_PORT,
    AGENT_MODEL_ID # Import AGENT_MODEL_ID for team instance
)

# Import tool logic functions
from api_tools.player_tools import (
    fetch_player_info_logic,
    fetch_player_gamelog_logic,
    fetch_player_career_stats_logic,
    get_player_headshot_url, # Keep headshot import
    find_players_by_name_fragment, # Keep search import
    _get_cached_player_list # Import helper to potentially pre-warm cache if needed
)
from api_tools.team_tools import (
    fetch_team_info_and_roster_logic
)
from api_tools.game_tools import (
    fetch_league_games_logic
)
from nba_api.stats.library.parameters import PerMode36, SeasonTypeAllStar

# Configure logging
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_level = logging.DEBUG

# Console Handler
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
stream_handler.setLevel(log_level)

# File Handler
file_handler = logging.FileHandler(LOG_FILENAME, mode=LOG_FILE_MODE) # Use config values
file_handler.setFormatter(log_formatter)
file_handler.setLevel(log_level)

# Get root logger and add handlers
root_logger = logging.getLogger()
# Clear existing handlers (important for reload)
if root_logger.hasHandlers():
    root_logger.handlers.clear()
root_logger.setLevel(log_level)
root_logger.addHandler(stream_handler)
root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__) # Get logger for this module

app = FastAPI(title="NBA Analytics Backend")

# Add CORS middleware
origins = CORS_ALLOWED_ORIGINS # Use config value
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return {"message": "NBA Analytics Backend using Agno"}

# --- Player Headshot Endpoint ---
@app.get("/player/{player_id}/headshot")
async def get_player_headshot(player_id: int):
    """
    Returns the URL for the player's headshot image.
    """
    logger.info(f"Received GET /player/{player_id}/headshot request.")
    try:
        # Basic validation (can be enhanced)
        if player_id <= 0:
            raise HTTPException(status_code=400, detail="Invalid player_id provided.")

        headshot_url = get_player_headshot_url(player_id)
        # We could potentially add a check here to see if the URL is valid
        # (e.g., using a HEAD request), but for simplicity, just return the URL.
        logger.info(f"Returning headshot URL for player ID {player_id}: {headshot_url}")
        return {"player_id": player_id, "headshot_url": headshot_url}
    except HTTPException as http_exc:
        # Re-raise known HTTP exceptions
        raise http_exc
    except Exception as e:
        logger.exception(f"Unexpected error fetching headshot for player ID {player_id}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# --- Pre-warm player cache (optional, run on startup) ---
# try:
#     logger.info("Pre-warming player list cache...")
#     _get_cached_player_list()
#     logger.info("Player list cache pre-warmed.")
# except Exception as cache_err:
#     logger.error(f"Failed to pre-warm player cache: {cache_err}")


# --- Player Search Endpoint ---
@app.get("/players/search", response_model=List[Dict[str, Any]]) # Add response model
async def search_players(q: str | None = None, limit: int = 10):
    """
    Searches for players by a name fragment.
    """
    logger.info(f"Received GET /players/search request with query: '{q}', limit: {limit}")
    if not q or len(q) < 2:
        # Return empty list or specific error if query is too short/missing
        # raise HTTPException(status_code=400, detail="Search query 'q' must be at least 2 characters long.")
        return [] # Return empty list for short/missing queries

    try:
        results = find_players_by_name_fragment(q, limit=limit)
        logger.info(f"Returning {len(results)} players for search query '{q}'")
        return results # FastAPI automatically converts list of dicts to JSON
    except Exception as e:
        logger.exception(f"Unexpected error during player search for query '{q}'")
        raise HTTPException(status_code=500, detail=f"Internal server error during player search: {str(e)}")

# NOTE: This endpoint is added to support the player search suggestions dropdown.
# It directly calls the logic function from player_tools.
@app.get("/players/search", response_model=List[Dict[str, Any]])
async def search_players_api(q: str | None = None, limit: int = 5): # Keep limit low for suggestions
    """
    API endpoint to search for players by name fragment (for suggestions).
    Matches the function signature used in the frontend fetch call.
    """
    logger.info(f"Received API GET /players/search request with query: '{q}', limit: {limit}")
    if not q or len(q) < 2:
        # Return empty list for short/missing queries, consistent with frontend expectation
        return []

    try:
        # Directly call the logic function used by the tool
        results = find_players_by_name_fragment(q, limit=limit)
        logger.info(f"API returning {len(results)} players for search query '{q}'")
        return results
    except Exception as e:
        logger.exception(f"API unexpected error during player search for query '{q}'")
        # Don't expose internal errors directly, return empty list for suggestion failures
        # raise HTTPException(status_code=500, detail=f"Internal server error during player search: {str(e)}")
        return []


# --- Request Models ---
class AnalyzeRequest(BaseModel):
    query: str = "Provide a general analysis of the data."
    data: Dict[str, Any]

class FetchRequest(BaseModel):
    target: str
    params: Dict[str, Any] = {}
    prompt: str | None = None

class NormalizeRequest(BaseModel):
    raw_data: Dict[str, Any]

# (Removed unused extract_json_string helper function)
# --- Agent Interaction Endpoints ---

@app.post("/analyze")
async def analyze_data(request: AnalyzeRequest):
    # ... (analyze endpoint remains the same) ...
    query = request.query
    data_input = request.data
    logger.debug(f"Received /analyze request for query: {query}")
    try:
        result = await analysis_agent.arun(f"{query}. Analyze the following data: {str(data_input)}")
        logger.debug(f"Analyze agent result object type: {type(result)}")
        logger.debug(f"Analyze agent result object attributes: {dir(result) if result else 'None'}")
        final_content = None
        if hasattr(result, 'messages') and result.messages:
            last_message = result.messages[-1]
            logger.debug(f"Analyze agent last message role: {last_message.role}, type: {type(last_message.content)}")
            if last_message.role == 'assistant' and isinstance(last_message.content, str):
                final_content = last_message.content
                logger.info("Using last assistant message content for /analyze response.")
            else:
                 logger.warning("Last message in /analyze history was not usable assistant content.")
        else:
            logger.warning("No message history found in /analyze agent result.")
            final_content = getattr(result, 'response', None) # Fallback
            logger.warning(f"Falling back to result.response for /analyze: Type={type(final_content)}")
        if final_content is not None:
             logger.info(f"/analyze successful for query: {query}")
             return {"analysis": str(final_content)}
        else:
             logger.error(f"Analysis agent did not return a usable response in history or attribute for query: {query}")
             raise HTTPException(status_code=500, detail="Analysis agent did not return a valid response.")
    except Exception as e:
        logger.exception(f"Error during /analyze for query: {query}")
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")

# Helper function to format SSE messages
def format_sse(data: str, event: str | None = None) -> str:
    msg = f"data: {data}\n\n"
    if event is not None:
        msg = f"event: {event}\n{msg}"
    return msg

# Removed local create_nba_team_instance function, using imported Team now

@app.get("/ask_team") # Keep as GET, but will return StreamingResponse
async def ask_team_keepalive_sse(request: Request, prompt: str):
    """
    Endpoint that sends initial SSE status, runs agent sync in background,
    sends keep-alive messages, then sends final SSE result using the imported Team.
    """
    logger.info(f"Received GET /ask_team (sync) request with prompt: '{prompt}'")
    # Use the imported team instance directly
    team_instance = nba_analysis_team
    logger.info("Using imported NBA Analysis Team instance for request.")

    async def keepalive_sse_generator():
        """Sends keep-alive messages while agent runs in background, then sends final result."""
        logger.info(f"START keepalive_sse_generator for prompt: '{prompt}'")
        agent_task = None
        keep_alive_interval = 5 # Seconds
        mock_messages = ["Analyzing data...", "Consulting sources...", "Synthesizing findings...", "Cross-referencing stats...", "Checking historical trends...", "Almost there..."]
        msg_index = 0
        try:
            # 1. Send initial status messages immediately
            yield format_sse(json.dumps({"type": "status", "message": "Processing prompt..."}), event="status")
            await asyncio.sleep(0.1) # Ensure flush
            # Removed disconnect check here as it's handled in the loop

            yield format_sse(json.dumps({"type": "status", "message": "Starting agent execution (this may take a while)..."}), event="status")
            await asyncio.sleep(0.1)
            # Removed disconnect check here

            # 2. Start agent task in background
            logger.info(f"Starting agent task in background for prompt: '{prompt}'")
            agent_task = asyncio.create_task(team_instance.arun(prompt)) # Use arun, not print_response

            # 3. Loop sending keep-alive/mock status until agent task is done
            while not agent_task.done():
                if await request.is_disconnected():
                    logger.warning("Client disconnected, cancelling agent task.")
                    agent_task.cancel()
                    raise asyncio.CancelledError("Client disconnected during keep-alive")

                # Send mock status
                status_msg = mock_messages[msg_index % len(mock_messages)]
                yield format_sse(json.dumps({"type": "status", "message": status_msg}), event="status")
                logger.debug(f"Sent keep-alive status: {status_msg}")
                msg_index += 1

                # Wait for the interval, checking frequently for task completion/disconnection
                wait_step = 0.5 # Check every 0.5 seconds
                for _ in range(int(keep_alive_interval / wait_step)):
                    if agent_task.done() or await request.is_disconnected():
                        break
                    await asyncio.sleep(wait_step)
                if agent_task.done() or await request.is_disconnected():
                        break # Exit outer loop if task finished or client disconnected during sleep

            # 4. Agent task finished or client disconnected
            if await request.is_disconnected():
                 # Task might have been cancelled above, or client disconnected just now
                 if agent_task and not agent_task.done(): agent_task.cancel()
                 raise asyncio.CancelledError("Client disconnected before agent completion")

            # Log prompt safely before processing result
            safe_prompt_log = prompt.encode('utf-8', errors='replace').decode('utf-8', errors='ignore')
            logger.info(f"Agent task finished for prompt: '{safe_prompt_log}'")
            result = await agent_task # Get result (or raise exception if task failed)
            # 5. Extract final content (Simplified: Use result.content directly)
            final_content = None
            final_content = result.content
            # Removed print statement and block attempting to send "thinking" events.

            # 6. Send final result (result.content) or error via SSE
            if final_content is None:
                 # Log the full result object if content extraction failed
                 logger.error(f"Final content extraction failed. Result type: {type(result)}, Result: {result!r}")
                 yield format_sse(json.dumps({"type": "error", "message": "Agent did not produce a recognizable final response."}))
            else:
                logger.debug(f"Sending final content via SSE: {final_content[:100]}...")
                final_sse_data = {"type": "final_response", "content": final_content}
                yield format_sse(json.dumps(final_sse_data), event="final")

        except asyncio.CancelledError as ce:
             logger.warning(f"Task cancelled: {ce}")
             # Ensure agent task is cancelled if it exists and isn't done
             if agent_task and not agent_task.done():
                 agent_task.cancel()
        except Exception as e:
            logger.exception(f"Error DURING keepalive_sse_generator for prompt: {prompt}")
            error_detail = f"Error processing team request: {str(e)}"
            try:
                 # Attempt to send error message back to client
                 yield format_sse(json.dumps({"type": "error", "message": error_detail}))
            except Exception as send_err:
                 logger.error(f"Failed to send error message back to client: {send_err}")
        finally:
            # Log prompt safely, replacing encoding errors
            # Removed prompt from log message to avoid encoding errors
            logger.info("END keepalive_sse_generator.")

    # Use the keep-alive generator with SSE headers
    headers = {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(keepalive_sse_generator(), headers=headers)


# Reverted: Endpoint calls tool logic directly due to agent/async test issues
@app.post("/fetch_data")
async def fetch_data(request: FetchRequest):
    target = request.target
    params = request.params
    logger.debug(f"Received /fetch_data request for target: {target}, params: {params}")
    tool_result_json = None

    # Validate target first
    supported_targets = SUPPORTED_FETCH_TARGETS # Use config value
    if target not in supported_targets:
        raise HTTPException(status_code=400, detail=f"Unsupported target '{target}'. Supported targets: {', '.join(supported_targets)}.")

    try:
        # Determine which logic function to call based on target
        if target == "player_info":
            player_name = params.get("player_name")
            if not player_name: raise HTTPException(status_code=400, detail="Missing 'player_name' in params for target 'player_info'.")
            logger.info(f"Calling fetch_player_info_logic for: {player_name}")
            tool_result_json = fetch_player_info_logic(player_name)

        elif target == "player_gamelog":
            player_name = params.get("player_name")
            season = params.get("season")
            if not player_name or not season: raise HTTPException(status_code=400, detail="Missing 'player_name' or 'season' in params for target 'player_gamelog'.")
            season_type = params.get("season_type", SeasonTypeAllStar.regular)
            logger.info(f"Calling fetch_player_gamelog_logic for: {player_name}, Season: {season}, Type: {season_type}")
            tool_result_json = fetch_player_gamelog_logic(player_name, season, season_type)

        elif target == "team_info":
             team_identifier = params.get("team_identifier")
             if not team_identifier: raise HTTPException(status_code=400, detail="Missing 'team_identifier' in params for target 'team_info'.")
             season = params.get("season")
             logger.info(f"Calling fetch_team_info_and_roster_logic for: {team_identifier}, Season: {season or 'Default'}")
             tool_result_json = fetch_team_info_and_roster_logic(team_identifier, season)

        elif target == "player_career_stats":
             player_name = params.get("player_name")
             if not player_name: raise HTTPException(status_code=400, detail="Missing 'player_name' in params for target 'player_career_stats'.")
             per_mode36 = params.get("per_mode36", PerMode36.per_game)
             logger.info(f"Calling fetch_player_career_stats_logic for: {player_name}, PerMode36: {per_mode36}")
             tool_result_json = fetch_player_career_stats_logic(player_name, per_mode36)

        elif target == "find_games":
             player_or_team = params.get("player_or_team")
             player_id = params.get("player_id")
             team_id = params.get("team_id")
             date_from = params.get("date_from")
             date_to = params.get("date_to")
             # Removed season, season_type, league_id as they are not supported in the simplified tool
             if not player_or_team or player_or_team not in ['P', 'T']:
                 raise HTTPException(status_code=400, detail="Missing or invalid 'player_or_team' ('P' or 'T') in params for target 'find_games'.")
             if player_or_team == 'P' and player_id is None:
                 raise HTTPException(status_code=400, detail="Missing 'player_id' in params for target 'find_games' with player_or_team='P'.")
             if player_or_team == 'T' and team_id is None:
                 raise HTTPException(status_code=400, detail="Missing 'team_id' in params for target 'find_games' with player_or_team='T'.")

             logger.info(f"Calling fetch_league_games_logic with params: {params}")
             tool_result_json = fetch_league_games_logic(
                 player_or_team_abbreviation=player_or_team,
                 player_id_nullable=player_id,
                 team_id_nullable=team_id,
                 # Pass None for unsupported params in logic call
                 season_nullable=None,
                 season_type_nullable=None,
                 league_id_nullable=None,
                 date_from_nullable=date_from,
                 date_to_nullable=date_to
             )
        # else case handled by initial target check

        # Parse the JSON string returned by the logic function
        if tool_result_json:
            logger.debug(f"Attempting to parse direct tool result: {tool_result_json[:200]}...")
            try:
                tool_data = json.loads(tool_result_json)
                if isinstance(tool_data, dict):
                    if 'error' in tool_data:
                        error_message = tool_data['error']
                        logger.warning(f"Tool logic returned error: {error_message}")
                        # Check for specific errors that should be 404
                        if "not found" in error_message.lower() or "could not find" in error_message.lower():
                            raise HTTPException(status_code=404, detail=error_message)
                        # Check for specific errors that should be 400 (e.g., invalid input handled by logic)
                        elif "invalid" in error_message.lower() or "required" in error_message.lower():
                             raise HTTPException(status_code=400, detail=error_message)
                        else: # Treat other tool errors as 500
                            raise HTTPException(status_code=500, detail=f"Tool execution error: {error_message}")
                    logger.info(f"/fetch_data successful for target: {target}")
                    return tool_data # Return the successful data dictionary
                else:
                    logger.error(f"Tool logic returned valid JSON but not a dictionary: {tool_data}")
                    raise HTTPException(status_code=500, detail="Tool returned unexpected data structure.")
            except json.JSONDecodeError as json_err:
                logger.error(f"Tool logic returned invalid JSON: {tool_result_json[:200]}... Error: {json_err}")
                raise HTTPException(status_code=500, detail=f"Tool failed to return valid JSON data.")
        else:
            logger.error("Tool logic function returned None unexpectedly.")
            raise HTTPException(status_code=500, detail="Internal server error: Tool logic failed.")

    except HTTPException as http_exc:
        # Re-raise specific HTTP exceptions (400, 404, 500 from tool errors)
        raise http_exc
    except Exception as e:
        # Catch unexpected errors during logic execution
        logger.exception(f"Unexpected error during /fetch_data direct logic call for target={target}")
        raise HTTPException(status_code=500, detail=f"Data fetching error: {str(e)}")


# @app.post("/normalize_data") # Commented out as agent is not used/causes errors
# async def normalize_data(request: NormalizeRequest):
#     # ... (normalize endpoint remains the same) ...
#     raw_data = request.raw_data
#     logger.debug(f"Received /normalize_data request.")
#     try:
#         # result = await data_normalizer_agent.arun(f"Simulate normalizing this data: {str(raw_data)}")
#         # logger.debug(f"Normalize agent result object type: {type(result)}")
#         # agent_response = getattr(result, 'response', None)
#         # if agent_response is None and hasattr(result, 'messages') and result.messages:
#         #      last_message = result.messages[-1]
#         #      if last_message.role == 'assistant':
#         #          agent_response = last_message.content
#         #          logger.warning("Normalize agent response attribute was None, using last assistant message content.")
#         # logger.debug(f"Normalize agent result response attribute type: {type(agent_response)}")
#         # logger.debug(f"Normalize agent result response content: {agent_response}")
#         # if agent_response is not None:
#         #      logger.info("/normalize_data simulation successful.")
#         #      return {"normalized_data_simulation_result": str(agent_response)}
#         # else:
#         #     logger.error("Data normalizer agent did not return a valid response.")
#         #     raise HTTPException(status_code=500, detail="Data normalizer agent did not return a valid response.")
#         logger.warning("/normalize_data endpoint is currently disabled.")
#         raise HTTPException(status_code=501, detail="Normalization endpoint not implemented.")
#     except Exception as e:
#         logger.exception("Error during /normalize_data")
#         raise HTTPException(status_code=500, detail=f"Data normalization error: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("main:app", host=UVICORN_HOST, port=UVICORN_PORT, reload=True, reload_excludes=["app_test_output.log"]) # Use config values
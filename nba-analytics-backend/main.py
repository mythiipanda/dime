from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import uvicorn
import logging
import json
import re

# Import defined agents
from agents import analysis_agent, data_aggregator_agent #, data_normalizer_agent (Commented out)
# Import tool logic functions directly for fetch_data workaround
from api_tools.player_tools import (
    fetch_player_info_logic,
    fetch_player_gamelog_logic,
    fetch_player_career_stats_logic
)
from api_tools.team_tools import (
    fetch_team_info_and_roster_logic
)
from api_tools.game_tools import (
    fetch_league_games_logic
)
from nba_api.stats.library.parameters import PerMode36, LeagueID, SeasonNullable, SeasonTypeNullable, SeasonTypeAllStar

# Configure logging for main app
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="NBA Analytics Backend")

@app.get("/")
async def read_root():
    return {"message": "NBA Analytics Backend using Agno"}

# --- Request Models ---
class AnalyzeRequest(BaseModel):
    query: str = "Provide a general analysis of the data."
    data: Dict[str, Any]

class FetchRequest(BaseModel):
    # Revert to target/params for direct logic calls
    target: str
    params: Dict[str, Any] = {}
    prompt: str | None = None # Keep for potential future use / logging

class NormalizeRequest(BaseModel):
    raw_data: Dict[str, Any]

# --- Helper to Extract JSON from Agent Response ---
# This helper might still be useful if the /analyze agent wraps output
def extract_json_string(response_str: str) -> str | None:
    """
    Attempts to extract the raw JSON string returned by the tool,
    handling potential wrapping by the agent (markdown, nested JSON).
    Focuses on the specific observed structure:
    {"<tool_name>_response": "{\"result\": \"<escaped_tool_output_json>\"}"}
    """
    if not isinstance(response_str, str):
        logger.debug(f"Input to extract_json_string is not a string: {type(response_str)}")
        return None

    logger.debug(f"Attempting to extract JSON from: {response_str[:200]}...")
    original_str = response_str
    content_to_parse = response_str

    # 1. Strip markdown code block if present
    match_md = re.search(r"```json\s*(.*?)\s*```", content_to_parse, re.DOTALL | re.IGNORECASE)
    if match_md:
        content_to_parse = match_md.group(1).strip()
        logger.debug(f"Stripped markdown, now processing: {content_to_parse[:100]}...")

    # 2. Check if the current string is valid JSON
    try:
        json.loads(content_to_parse)
        logger.debug("String is valid JSON after potential markdown stripping.")
        return content_to_parse
    except json.JSONDecodeError:
        logger.debug("String is not direct JSON, checking for specific Agno wrapper...")

    # 3. Check specifically for the observed Agno double-wrapper structure
    try:
        # First parse: {"<tool_name>_response": "<value_string>"}
        outer_dict = json.loads(content_to_parse)
        if isinstance(outer_dict, dict) and len(outer_dict) == 1:
            key = list(outer_dict.keys())[0]
            value_str = list(outer_dict.values())[0] # This should be "{\"result\": \"<escaped_json>\"}"

            if isinstance(key, str) and key.endswith("_response") and isinstance(value_str, str):
                logger.debug(f"Detected Agno wrapper. Key: {key}. Parsing inner value string: {value_str[:100]}...")
                try:
                    # Second parse: {"result": "<escaped_json>"}
                    inner_dict = json.loads(value_str)
                    if isinstance(inner_dict, dict) and "result" in inner_dict and isinstance(inner_dict["result"], str):
                        final_escaped_json_str = inner_dict["result"] # This is "<escaped_json>"
                        # Final validation: Can the innermost string be parsed as JSON?
                        try:
                            json.loads(final_escaped_json_str)
                            logger.debug("Successfully extracted JSON from Agno double wrapper ('result' key).")
                            return final_escaped_json_str # Return the innermost JSON string
                        except json.JSONDecodeError:
                             logger.error(f"Innermost 'result' string was not valid JSON: {final_escaped_json_str[:100]}...")
                             return None # Failed validation
                    else:
                         logger.warning("Inner dict from wrapper value didn't contain 'result' string.")
                         # Maybe value_str itself was the intended JSON? Try parsing it directly.
                         try:
                             json.loads(value_str)
                             logger.debug("Treating wrapper value string as the final JSON.")
                             return value_str
                         except json.JSONDecodeError:
                             logger.warning("Value string was not valid JSON either.")
                             return None
                except json.JSONDecodeError:
                     logger.warning(f"Value string '{value_str[:100]}...' in Agno wrapper was not valid JSON for 'result' structure.")
                     return None # Value wasn't JSON
            else:
                logger.debug("Structure is single-key dict, but doesn't match Agno wrapper pattern.")
        else:
            logger.debug("Response string is not a single-key dict wrapper.")

    except json.JSONDecodeError:
        logger.debug("Response string could not be parsed as outer JSON for wrapper check.")
        pass

    # 4. If no patterns matched
    logger.error(f"Failed to extract valid JSON string from agent response: {original_str[:200]}...")
    return None

# --- Agent Interaction Endpoints ---

@app.post("/analyze")
async def analyze_data(request: AnalyzeRequest):
    # ... (analyze endpoint remains the same, using agent history workaround) ...
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


# Reverted: Endpoint calls tool logic directly due to agent/async test issues
@app.post("/fetch_data")
async def fetch_data(request: FetchRequest):
    target = request.target
    params = request.params
    logger.debug(f"Received /fetch_data request for target: {target}, params: {params}")
    tool_result_json = None

    # Validate target first
    supported_targets = ["player_info", "player_gamelog", "team_info", "player_career_stats", "find_games"]
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

        # Logic functions now return dictionaries directly
        tool_data = tool_result_json # Rename variable for clarity

        if tool_data is not None:
            logger.debug(f"Direct tool result received (type: {type(tool_data)}): {str(tool_data)[:200]}...")
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
                # If the logic function is expected to return a list (e.g., gamelog),
                # we might need to adjust this. For now, assume dict is expected or error.
                # Let's refine this if specific list-returning tools cause issues.
                # For now, treat non-dict successful returns as unexpected.
                logger.error(f"Tool logic returned unexpected type: {type(tool_data)}")
                raise HTTPException(status_code=500, detail="Tool returned unexpected data structure.")
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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import uvicorn
import logging
import json
import re

# Import defined agents (still needed for /analyze)
from agents import analysis_agent, data_aggregator_agent, data_normalizer_agent
# Import tool logic functions directly
from api_tools.player_tools import (
    fetch_player_info_logic,
    fetch_player_gamelog_logic,
    fetch_player_career_stats_logic
)
from api_tools.team_tools import (
    fetch_team_info_and_roster_logic
)
from nba_api.stats.library.parameters import PerMode36 # For default value

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
    target: str = "player_info"
    params: Dict[str, Any] = {}

class NormalizeRequest(BaseModel):
    raw_data: Dict[str, Any]

# --- Helper (No longer needed for fetch_data) ---
# def extract_json_string(response_str: str) -> str | None: ...

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


# Updated: Endpoint calls tool logic directly, bypassing agent response handling
@app.post("/fetch_data")
async def fetch_data(request: FetchRequest):
    target = request.target
    params = request.params
    logger.debug(f"Received /fetch_data request for target: {target}, params: {params}")
    tool_result_json = None

    try:
        # Determine which logic function to call based on target
        if target == "player_info" and "player_name" in params:
            player_name = params["player_name"]
            logger.info(f"Calling fetch_player_info_logic for: {player_name}")
            tool_result_json = fetch_player_info_logic(player_name)

        elif target == "player_gamelog" and "player_name" in params and "season" in params:
            player_name = params["player_name"]
            season = params["season"]
            season_type = params.get("season_type", "Regular Season") # Default handled in logic
            logger.info(f"Calling fetch_player_gamelog_logic for: {player_name}, Season: {season}, Type: {season_type}")
            tool_result_json = fetch_player_gamelog_logic(player_name, season, season_type)

        elif target == "team_info" and "team_identifier" in params:
             team_identifier = params["team_identifier"]
             season = params.get("season") # Default handled in logic
             logger.info(f"Calling fetch_team_info_and_roster_logic for: {team_identifier}, Season: {season or 'Default'}")
             tool_result_json = fetch_team_info_and_roster_logic(team_identifier, season)

        elif target == "player_career_stats" and "player_name" in params:
             player_name = params["player_name"]
             per_mode36 = params.get("per_mode36", PerMode36.per_game) # Default handled in logic
             logger.info(f"Calling fetch_player_career_stats_logic for: {player_name}, PerMode36: {per_mode36}")
             tool_result_json = fetch_player_career_stats_logic(player_name, per_mode36)

        else:
            logger.warning(f"Unsupported target/params for /fetch_data: target={target}, params={params}")
            raise HTTPException(status_code=400, detail=f"Unsupported target '{target}' or missing/invalid parameters for that target. Supported targets: player_info, player_gamelog, team_info, player_career_stats.")

        # Parse the JSON string returned by the logic function
        if tool_result_json:
            logger.debug(f"Attempting to parse direct tool result: {tool_result_json[:200]}...")
            try:
                tool_data = json.loads(tool_result_json)
                if isinstance(tool_data, dict):
                    if 'error' in tool_data:
                        error_message = tool_data['error']
                        logger.warning(f"Tool logic returned error: {error_message}")
                        if "not found" in error_message.lower():
                            raise HTTPException(status_code=404, detail=error_message)
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
            # Should not happen if logic functions always return a string
            logger.error("Tool logic function returned None unexpectedly.")
            raise HTTPException(status_code=500, detail="Internal server error: Tool logic failed.")

    except HTTPException as http_exc:
        # Re-raise specific HTTP exceptions (400, 404, 500 from tool errors)
        raise http_exc
    except Exception as e:
        # Catch unexpected errors during logic execution
        logger.exception(f"Unexpected error during /fetch_data direct logic call for target={target}")
        raise HTTPException(status_code=500, detail=f"Data fetching error: {str(e)}")


@app.post("/normalize_data")
async def normalize_data(request: NormalizeRequest):
    # ... (normalize endpoint remains the same) ...
    raw_data = request.raw_data
    logger.debug(f"Received /normalize_data request.")
    try:
        result = await data_normalizer_agent.arun(f"Simulate normalizing this data: {str(raw_data)}")
        logger.debug(f"Normalize agent result object type: {type(result)}")
        agent_response = getattr(result, 'response', None)
        if agent_response is None and hasattr(result, 'messages') and result.messages:
             last_message = result.messages[-1]
             if last_message.role == 'assistant':
                 agent_response = last_message.content
                 logger.warning("Normalize agent response attribute was None, using last assistant message content.")

        logger.debug(f"Normalize agent result response attribute type: {type(agent_response)}")
        logger.debug(f"Normalize agent result response content: {agent_response}")
        if agent_response is not None:
             logger.info("/normalize_data simulation successful.")
             return {"normalized_data_simulation_result": str(agent_response)}
        else:
            logger.error("Data normalizer agent did not return a valid response.")
            raise HTTPException(status_code=500, detail="Data normalizer agent did not return a valid response.")
    except Exception as e:
        logger.exception("Error during /normalize_data")
        raise HTTPException(status_code=500, detail=f"Data normalization error: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
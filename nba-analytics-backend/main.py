from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import uvicorn
import logging
import json

# Import defined agents
from agents import analysis_agent, data_aggregator_agent, data_normalizer_agent

# Configure logging for main app
logging.basicConfig(level=logging.DEBUG)
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

# --- Agent Interaction Endpoints ---

@app.post("/analyze")
async def analyze_data(request: AnalyzeRequest):
    query = request.query
    data_input = request.data
    logger.debug(f"Received /analyze request for query: {query}")
    try:
        result = await analysis_agent.arun(f"{query}. Analyze the following data: {str(data_input)}")
        if result and hasattr(result, 'response'):
             logger.info(f"/analyze successful for query: {query}")
             return {"analysis": result.response}
        else:
             logger.error(f"Analysis agent did not return a valid response for query: {query}")
             raise HTTPException(status_code=500, detail="Analysis agent did not return a valid response.")
    except Exception as e:
        logger.exception(f"Error during /analyze for query: {query}")
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


# Reverted: Endpoint using agent.arun and parsing JSON response
@app.post("/fetch_data")
async def fetch_data(request: FetchRequest):
    target = request.target
    params = request.params
    logger.debug(f"Received /fetch_data request for target: {target}, params: {params}")
    try:
        # Construct the prompt
        prompt = ""
        if target == "player_info" and "player_name" in params:
            player_name = params["player_name"]
            prompt = f"Fetch basic player information for {player_name}."
        elif target == "player_gamelog" and "player_name" in params and "season" in params:
            player_name = params["player_name"]
            season = params["season"]
            season_type = params.get("season_type", "Regular Season")
            prompt = f"Fetch game log for player {player_name} for the {season} season, type {season_type}."
        elif target == "team_info" and "team_identifier" in params:
             team_identifier = params["team_identifier"]
             season = params.get("season")
             prompt = f"Fetch team info and roster for team '{team_identifier}'"
             if season: prompt += f" for the {season} season"
             prompt += "."
        elif target == "player_career_stats" and "player_name" in params:
             player_name = params["player_name"]
             per_mode = params.get("per_mode", "PerGame")
             prompt = f"Fetch career stats for player {player_name} in {per_mode} mode."
        else:
            logger.warning(f"Unsupported target/params for /fetch_data: target={target}, params={params}")
            raise HTTPException(status_code=400, detail=f"Unsupported target '{target}' or missing/invalid parameters for that target. Supported targets: player_info, player_gamelog, team_info, player_career_stats.")

        if not prompt:
             raise HTTPException(status_code=500, detail="Internal error: Failed to construct agent prompt.")

        logger.info(f"Calling DataAggregatorAgent with prompt: '{prompt}'")
        result = await data_aggregator_agent.arun(prompt)
        logger.debug(f"Agent raw response content: {getattr(result, 'response', 'N/A')}")

        # Process the agent's response (expecting JSON string from tool)
        if result and hasattr(result, 'response') and isinstance(result.response, str):
            agent_response_str = result.response
            try:
                tool_data = json.loads(agent_response_str)
                if isinstance(tool_data, dict):
                    if 'error' in tool_data:
                        error_message = tool_data['error']
                        logger.warning(f"Tool returned error: {error_message}")
                        if "not found" in error_message.lower():
                            raise HTTPException(status_code=404, detail=error_message)
                        else: # Map other tool errors to 500
                            raise HTTPException(status_code=500, detail=f"Tool execution error: {error_message}")
                    logger.info(f"/fetch_data successful for prompt: '{prompt}'")
                    return tool_data # Return the successful data dictionary
                else:
                    logger.error(f"Tool returned valid JSON but not a dictionary: {tool_data}")
                    raise HTTPException(status_code=500, detail="Agent returned unexpected data structure from tool.")
            except json.JSONDecodeError:
                logger.error(f"Agent response was not valid JSON: {agent_response_str}")
                # If it's not JSON, treat as failure to get structured data
                raise HTTPException(status_code=500, detail=f"Agent did not return expected JSON data. Response: {agent_response_str}")
        else:
            logger.error(f"Data aggregator agent did not return a valid string response after tool execution. Type: {type(getattr(result, 'response', None))}, Response: {getattr(result, 'response', 'N/A')}")
            raise HTTPException(status_code=500, detail="Data aggregator agent did not return a valid response structure after tool execution.")

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Unexpected error during /fetch_data agent call for target={target}")
        raise HTTPException(status_code=500, detail=f"Data fetching agent error: {str(e)}")


# Placeholder: Endpoint to trigger data normalization
@app.post("/normalize_data")
async def normalize_data(request: NormalizeRequest):
    raw_data = request.raw_data
    logger.debug(f"Received /normalize_data request.")
    try:
        result = await data_normalizer_agent.arun(f"Simulate normalizing this data: {str(raw_data)}")
        if result and hasattr(result, 'response'):
             logger.info("/normalize_data simulation successful.")
             return {"normalized_data_simulation_result": result.response}
        else:
            logger.error("Data normalizer agent did not return a valid response.")
            raise HTTPException(status_code=500, detail="Data normalizer agent did not return a valid response.")
    except Exception as e:
        logger.exception("Error during /normalize_data")
        raise HTTPException(status_code=500, detail=f"Data normalization error: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
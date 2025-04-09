import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from backend.schemas import AnalyzeRequest
from backend.api_tools.analyze import analyze_player_stats_logic
from backend.agents import nba_agent
import json

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/player")
async def analyze_player_stats(request: AnalyzeRequest) -> Dict[str, Any]:
    """
    Analyze player statistics based on the provided request.
    """
    try:
        result = analyze_player_stats_logic(request.player_name, request.season)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error analyzing player stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze")
async def analyze_data(request: AnalyzeRequest):
    query = request.query
    data_input = request.data
    logger.debug(f"Received /analyze request for query: {query}")
    try:
        result = await nba_agent.arun(f"{query}. Analyze the following data: {str(data_input)}") # Use nba_agent
        final_content = None
        if hasattr(result, 'messages') and result.messages:
            last_message = result.messages[-1]
            if last_message.role == 'assistant' and isinstance(last_message.content, str):
                final_content = last_message.content
                logger.info("Using last assistant message content for /analyze response.")
            else:
                logger.warning("Last message in /analyze history was not usable assistant content.")
        else:
            logger.warning("No message history found in /analyze agent result.")
            final_content = getattr(result, 'response', None)
            logger.warning(f"Falling back to result.response for /analyze: Type={type(final_content)}")
        if final_content is not None:
            logger.info(f"/analyze successful for query: {query}")
            return {"analysis": str(final_content)}
        else:
            logger.error(f"Analysis agent did not return a usable response for query: {query}")
            raise HTTPException(status_code=500, detail="Analysis agent did not return a valid response.")
    except Exception as e:
        logger.exception(f"Error during /analyze agent execution for query: {query}")
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")
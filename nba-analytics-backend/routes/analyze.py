from fastapi import APIRouter, HTTPException
import logging

from schemas import AnalyzeRequest
from agents import analysis_agent

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/analyze")
async def analyze_data(request: AnalyzeRequest):
    query = request.query
    data_input = request.data
    logger.debug(f"Received /analyze request for query: {query}")
    try:
        result = await analysis_agent.arun(f"{query}. Analyze the following data: {str(data_input)}")
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
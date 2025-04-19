import asyncio
import json
import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse # Import StreamingResponse
from pydantic import BaseModel

from backend.workflows.research import ResearchWorkflow # Import the workflow
from backend.agents import nba_agent # Keep nba_agent for suggestions
from backend.routes.sse import format_sse, recursive_asdict # Reuse formatting function and recursive_asdict
# Keep model import if needed for other things, otherwise can remove
# from backend.models.research import ResearchReportModel 

logger = logging.getLogger(__name__)

router = APIRouter()

class ResearchRequest(BaseModel):
    topic: str

# No response model needed for StreamingResponse endpoint
# class ResearchResponse(BaseModel):
#     report: str
#     suggestions: list[str] = []

# Restore suggestion generation function
async def generate_suggestions(report_content: str) -> list[str]:
    """Uses an LLM agent to generate follow-up suggestions based on report content."""
    if not report_content or report_content.startswith("# Research Report: Error"):
        return []

    suggestion_prompt = f"""Analyze the following NBA research report. Based *only* on the content and data points within, suggest 2-3 specific, actionable follow-up research questions or interesting comparisons that would provide deeper insights into the topic discussed. Focus on concrete data or analyses mentioned. Output *only* a JSON list of strings, where each string is a potential research topic. Example: ["Compare Player A's clutch performance vs Player B.", "Analyze Team X's defensive rating change after the trade."]

Report:
{report_content}
"""
    try:
        logger.info("Generating research suggestions...")
        suggestion_response = await nba_agent.arun(suggestion_prompt, stream=False)
        suggestions_list = []
        response_text = ""
        if isinstance(suggestion_response, str):
            response_text = suggestion_response
        elif hasattr(suggestion_response, 'content') and isinstance(suggestion_response.content, str):
            response_text = suggestion_response.content
        
        if response_text:
            cleaned_response = response_text.strip().removeprefix("```json\n").removesuffix("\n```").strip()
            try:
                suggestions = json.loads(cleaned_response)
                if isinstance(suggestions, list) and all(isinstance(s, str) for s in suggestions):
                    suggestions_list = suggestions
                    logger.info(f"Generated suggestions: {suggestions_list}")
                else:
                    logger.warning(f"Suggestion generation returned non-list or non-string list: {suggestions}")
            except json.JSONDecodeError as json_err:
                 logger.error(f"Failed to parse suggestions JSON: {json_err}. Response was: {response_text}")
        else:
             logger.warning(f"Unexpected or empty response type from suggestion agent: {type(suggestion_response)}")
        return suggestions_list
    except Exception as e:
        logger.exception("Error during suggestion generation")
        return []

@router.post("/") 
async def run_research_stream(request_body: ResearchRequest):
    """
    Accepts topic, runs the ResearchWorkflow, streams all events (intermediate steps 
    from gatherer, final report chunks from writer), and sends suggestions via SSE.
    """
    topic = request_body.topic
    logger.info(f"Received workflow research request for topic: '{topic}'")

    if not topic:
        logger.error("Research topic is empty!")
        async def error_stream():
             error_data = {"type": "error", "content": "Research topic cannot be empty."}
             yield format_sse(json.dumps(error_data), event="error")
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    async def research_sse_generator():
        full_report_content = ""
        try:
            logger.info(f"Instantiating and running ResearchWorkflow for topic: {topic}")
            workflow = ResearchWorkflow() # Instantiate the workflow
            # Run the workflow's arun method
            run_stream = workflow.arun(topic)
            
            async for chunk in run_stream:
                chunk_dict = {}
                try:
                    chunk_dict = recursive_asdict(chunk)
                    if 'event' not in chunk_dict and 'content' in chunk_dict:
                        chunk_dict['event'] = 'RunResponse' 
                except Exception as conversion_err:
                    logger.error(f"Error converting chunk to dict: {conversion_err}", exc_info=True)
                    error_chunk = {"type": "error", "event": "error", "content": "Error processing stream chunk."}
                    yield format_sse(json.dumps(error_chunk), event="error")
                    continue 

                if not isinstance(chunk_dict, dict):
                    logger.warning(f"Chunk conversion did not result in a dict: {chunk_dict}")
                    continue

                event_type = chunk_dict.get("event")
                content_part = chunk_dict.get("content")

                # Accumulate final report content from the writer agent's stream
                # We might need to refine this if the workflow yields other string content
                if event_type == "RunResponse" and isinstance(content_part, str):
                    # Heuristic: Assume RunResponse from the workflow's second stage (writer) is the report
                    # A more robust way might involve checking the agent name if the workflow yields it.
                    full_report_content += content_part
                
                # Yield the event (could be from gatherer or writer)
                sse_message_string = format_sse(json.dumps(chunk_dict), event="message") 
                yield sse_message_string
                await asyncio.sleep(0.01) 

            # --- Workflow stream finished, now generate suggestions --- 
            logger.info("Research workflow stream completed. Generating suggestions...")
            suggestions = await generate_suggestions(full_report_content)
            
            # Send suggestions as a final event
            if suggestions:
                 suggestions_data = {"suggestions": suggestions}
                 yield format_sse(json.dumps(suggestions_data), event="suggestions")
                 logger.info("Suggestions sent.")
            else:
                 logger.info("No suggestions generated or suggestion generation failed.")

        except Exception as e:
            logger.exception(f"Error during research stream for topic '{topic}'")
            error_data = {"type": "error", "content": f"Internal server error during research: {str(e)}"}
            try:
                yield format_sse(json.dumps(error_data), event="error")
            except Exception as final_err:
                 logger.error(f"Failed to send final error message in stream: {final_err}")
        finally:
             logger.info(f"END research_sse_generator (workflow) for topic: {topic}")

    # Return the streaming response (headers are the same)
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(research_sse_generator(), media_type="text/event-stream", headers=headers) 
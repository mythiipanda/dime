import asyncio
import json
import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse # Add JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict

from backend.workflows.research import ResearchWorkflow # Import the workflow
from backend.agents import nba_agent # Keep nba_agent for suggestions
# Remove agno Gemini model import for suggestions
# from backend.agents import model 
from backend.routes.sse import format_sse, recursive_asdict # Reuse formatting function and recursive_asdict

# Native Google GenAI imports
import google.generativeai as genai
# Import both model IDs
from backend.config import GOOGLE_API_KEY, AGENT_MODEL_ID, SUGGESTION_MODEL_ID

# Initialize logger FIRST
logger = logging.getLogger(__name__)

# Configure native Gemini library (Now logger is defined)
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    logger.info("Native Google GenAI library configured successfully.")
except Exception as e:
    logger.error(f"Failed to configure native Google GenAI library: {e}")
    # Decide how to handle this - maybe raise an error or proceed cautiously?
    # For now, log and continue, suggestion endpoints might fail.

router = APIRouter()

# Model for the main research request (topic only)
class ResearchRequest(BaseModel):
    topic: str
    # selected_sections is kept for report structure
    selected_sections: Optional[List[str]] = None

# New model for prompt suggestion request
class PromptSuggestionRequest(BaseModel):
    current_prompt: str

# No response model needed for StreamingResponse endpoint
# class ResearchResponse(BaseModel):
#     report: str
#     suggestions: list[str] = []

# Make this synchronous as generate_content is sync
def generate_suggestions(report_content: str) -> list[str]:
    """Uses the native Gemini model (specified for suggestions) to generate follow-up suggestions."""
    if not report_content or report_content.startswith("# Research Report: Error"):
        return []

    suggestion_prompt = f"""Analyze the following NBA research report. Based *only* on the content and data points within, suggest 2-3 specific, actionable follow-up research questions or interesting comparisons that would provide deeper insights into the topic discussed. Focus on concrete data or analyses mentioned. Output *only* a JSON list of strings, where each string is a potential research topic. Example: ["Compare Player A's clutch performance vs Player B.", "Analyze Team X's defensive rating change after the trade."]

Report:
{report_content}
"""
    try:
        logger.info(f"Generating follow-up suggestions using native model: {SUGGESTION_MODEL_ID}")
        # Use suggestion model ID
        native_model = genai.GenerativeModel(SUGGESTION_MODEL_ID)
        suggestion_response = native_model.generate_content(suggestion_prompt)
        suggestions_list = []
        response_text = ""

        # Extract text content using .text attribute
        if hasattr(suggestion_response, 'text') and isinstance(suggestion_response.text, str):
            response_text = suggestion_response.text
        else:
             logger.warning(f"Unexpected response structure from native Gemini model: {suggestion_response}")
        
        if response_text:
            cleaned_response = response_text.strip().removeprefix("```json").removesuffix("```").strip()
            try:
                suggestions = json.loads(cleaned_response)
                if isinstance(suggestions, list) and all(isinstance(s, str) for s in suggestions):
                    suggestions_list = suggestions
                    logger.info(f"Generated follow-up suggestions: {suggestions_list}")
                else:
                    logger.warning(f"Follow-up suggestion generation returned non-list or non-string list: {suggestions}")
            except json.JSONDecodeError as json_err:
                 logger.error(f"Failed to parse follow-up suggestions JSON: {json_err}. Response was: {response_text}")
        else:
             logger.warning(f"Empty response text from suggestion model.")
        return suggestions_list
    except Exception as e:
        logger.exception(f"Error during native follow-up suggestion generation: {e}")
        return []

# Rename and modify for prompt improvement
def generate_prompt_suggestions(current_prompt: str) -> List[str]:
    """Uses the native Gemini model to suggest improvements/alternatives to the user's current prompt."""
    if not current_prompt:
        return [
            "Analyze LeBron James' performance in the 2020 NBA Finals.",
            "Compare the Golden State Warriors' offensive rating in seasons with and without Kevin Durant.",
            "What impact did the James Harden trade have on the Brooklyn Nets' defense?"
        ] # Provide generic examples if input is empty

    prompt = f"""Given the user's initial NBA research prompt: '{current_prompt}'

Suggest 3 alternative or improved versions of this prompt. The suggestions should be:
1.  Clearer and more specific.
2.  Actionable for an NBA data analysis agent.
3.  Diverse in the angle or detail they explore, while staying related to the original prompt's core idea.

Output *only* a JSON list of 3 strings, where each string is a suggested prompt.

Example Input: 'LeBron vs Jordan'
Example Output: [
  "Compare LeBron James' and Michael Jordan's career regular season statistics.",
  "Analyze LeBron James' and Michael Jordan's performance in NBA Finals games.",
  "Who had a higher peak Player Efficiency Rating (PER), LeBron James or Michael Jordan?"
]

User's Prompt: '{current_prompt}'
"""

    try:
        logger.info(f"Generating prompt suggestions using native model: {SUGGESTION_MODEL_ID} for prompt: '{current_prompt}'")
        native_model = genai.GenerativeModel(SUGGESTION_MODEL_ID)
        suggestion_response = native_model.generate_content(prompt)
        suggestions_list = []
        response_text = ""

        if hasattr(suggestion_response, 'text') and isinstance(suggestion_response.text, str):
            response_text = suggestion_response.text
        else:
            logger.warning(f"Unexpected response structure from native Gemini prompt suggestion: {suggestion_response}")

        if response_text:
            cleaned_response = response_text.strip().removeprefix("```json").removesuffix("```").strip()
            try:
                suggestions = json.loads(cleaned_response)
                if isinstance(suggestions, list) and all(isinstance(s, str) for s in suggestions):
                    suggestions_list = suggestions[:3]
                    logger.info(f"Generated prompt suggestions: {suggestions_list}")
                else:
                    logger.warning(f"Prompt suggestion generation returned non-list or non-string list: {suggestions}")
            except json.JSONDecodeError as json_err:
                 logger.error(f"Failed to parse prompt suggestions JSON: {json_err}. Response was: {response_text}")
        else:
             logger.warning(f"Empty response text from prompt suggestion model.")
        return suggestions_list
    except Exception as e:
        logger.exception(f"Error during native prompt suggestion generation: {e}")
        return [] # Return empty list on error

# Change endpoint method from POST to GET for EventSource compatibility
@router.get("/") 
async def run_research_stream(topic: str, selected_sections: Optional[str] = None):
    """
    Accepts topic and selected_sections via query parameters, runs the ResearchWorkflow, 
    streams events, and sends suggestions via SSE.
    EventSource uses GET, so this must be a GET endpoint.
    """
    # Parse selected_sections from JSON string if provided
    sections_list: List[str] = []
    if selected_sections:
        try:
            parsed_list = json.loads(selected_sections)
            if isinstance(parsed_list, list) and all(isinstance(item, str) for item in parsed_list):
                sections_list = parsed_list
            else:
                 logger.warning(f"Could not parse selected_sections into a list of strings: {selected_sections}")
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in selected_sections query parameter: {selected_sections}")
            # Decide how to handle - error out or use default? Let's use default for now.
            sections_list = [] # Or fetch default sections
    else:
        sections_list = [] # Default if not provided

    logger.info(f"Received GET workflow research request for topic: '{topic}', Sections: {sections_list}")

    if not topic:
        logger.error("Research topic is empty!")
        async def error_stream():
             error_data = {"type": "error", "content": "Research topic cannot be empty."}
             yield format_sse(json.dumps(error_data), event="error")
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    async def research_sse_generator():
        full_report_content = ""
        try:
            logger.info(f"Instantiating ResearchWorkflow for topic: {topic}, Sections: {sections_list}")
            workflow = ResearchWorkflow()
            # Run the workflow's arun method, passing the parsed sections list
            run_stream = workflow.arun(topic=topic, selected_sections=sections_list)
            
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
            # Make sure generate_suggestions is called correctly (it's synchronous)
            suggestions = generate_suggestions(full_report_content)
            
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

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(research_sse_generator(), media_type="text/event-stream", headers=headers)

# Rename endpoint and update logic
@router.post("/prompt-suggestions", response_model=List[str])
async def get_prompt_suggestions(request_body: PromptSuggestionRequest):
    """Generates prompt suggestions based on the user's current input."""
    logger.info(f"Received request at /prompt-suggestions endpoint for prompt: '{request_body.current_prompt[:50]}...'" ) # Log start
    try:
        suggestions = generate_prompt_suggestions(request_body.current_prompt)
        return JSONResponse(content=suggestions)
    except Exception as e:
        logger.exception("Failed to generate prompt suggestions")
        raise HTTPException(status_code=500, detail="Failed to generate prompt suggestions.") 
import asyncio
import json
import logging
import hashlib # For generating deterministic session IDs for workflow caching
from fastapi import APIRouter, HTTPException, Request, Query, Body, status
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, AsyncGenerator

from backend.workflows.research import ResearchWorkflow
from backend.routes.sse import format_sse, recursive_asdict # Changed format_sse_message to format_sse
import google.generativeai as genai
from backend.config import GOOGLE_API_KEY, SUGGESTION_MODEL_ID, Errors, STORAGE_DB_FILE # Added STORAGE_DB_FILE
from agno.storage.workflow.sqlite import SqliteWorkflowStorage # For workflow state persistence

logger = logging.getLogger(__name__)

# Configure native Gemini library
try:
    if GOOGLE_API_KEY:
        genai.configure(api_key=GOOGLE_API_KEY)
        logger.info("Native Google GenAI library configured successfully for research routes.")
    else:
        logger.warning("GOOGLE_API_KEY not found. Native GenAI features (suggestions) will be disabled.")
except Exception as e:
    logger.error(f"Failed to configure native Google GenAI library: {e}", exc_info=True)

router = APIRouter(
    prefix="/research",
    tags=["Research & Suggestions"]
)

# --- Pydantic Models ---
# ResearchStreamQueryRequest is implicitly handled by Query params in the endpoint
# class ResearchStreamQueryRequest(BaseModel):
#     topic: str = Field(..., description="The main topic for the research workflow.")
#     selected_sections_json: Optional[str] = Field(None, alias="selected_sections", description="A JSON string representing a list of specific section names...")

class PromptSuggestionRequest(BaseModel):
    current_prompt: str = Field(..., description="The user's current research prompt to get suggestions for.")

class PromptSuggestionResponse(BaseModel):
    suggestions: List[str]

# --- Helper Functions for Suggestions (Assumed to be correct from previous review) ---

def _generate_suggestions_from_report(report_content: str) -> List[str]:
    """Uses a native Gemini model to generate follow-up research suggestions based on report content."""
    if not GOOGLE_API_KEY or not SUGGESTION_MODEL_ID:
        logger.warning("Google API Key or Suggestion Model ID not configured. Skipping report suggestions.")
        return []
    if not report_content or report_content.strip().startswith("# Research Report: Error"):
        logger.info("Report content is empty or an error report. Skipping suggestions.")
        return []
    suggestion_prompt_template = f"""Analyze the following NBA research report. Based *only* on the content and data points within, suggest 2-3 specific, actionable follow-up research questions or interesting comparisons that would provide deeper insights into the topic discussed. Focus on concrete data or analyses mentioned. Output *only* a JSON list of strings, where each string is a potential research topic. Example: ["Compare Player A's clutch performance vs Player B.", "Analyze Team X's defensive rating change after the trade."]

Report:
{report_content[:3000]}"""
    try:
        logger.info(f"Generating follow-up suggestions using native model: {SUGGESTION_MODEL_ID}")
        native_model = genai.GenerativeModel(SUGGESTION_MODEL_ID)
        response = native_model.generate_content(suggestion_prompt_template)
        response_text = response.text if hasattr(response, 'text') and isinstance(response.text, str) else ""
        if not response_text:
            logger.warning("Empty response text from suggestion model for report.")
            return []
        cleaned_response = response_text.strip().removeprefix("```json").removesuffix("```").strip()
        suggestions = json.loads(cleaned_response)
        if isinstance(suggestions, list) and all(isinstance(s, str) for s in suggestions):
            logger.info(f"Generated follow-up suggestions from report: {suggestions}")
            return suggestions
        else:
            logger.warning(f"Report suggestions returned non-list or non-string list: {suggestions}")
            return []
    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to parse report suggestions JSON: {json_err}. Response was: {response_text}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Error during native follow-up suggestion generation from report: {e}", exc_info=True)
        return []

def _generate_prompt_improvement_suggestions(current_prompt: str) -> List[str]:
    """Uses a native Gemini model to suggest improvements or alternatives to a user's research prompt."""
    generic_examples = [
        "Analyze LeBron James' performance in the 2020 NBA Finals.",
        "Compare the Golden State Warriors' offensive rating in seasons with and without Kevin Durant.",
        "What impact did the James Harden trade have on the Brooklyn Nets' defense?"
    ]
    if not GOOGLE_API_KEY or not SUGGESTION_MODEL_ID:
        logger.warning("Google API Key or Suggestion Model ID not configured. Returning generic prompt suggestions.")
        return generic_examples
    if not current_prompt:
        return generic_examples
    prompt_template = f"""Given the user's initial NBA research prompt: '{current_prompt}'
Suggest 3 alternative or improved versions of this prompt. The suggestions should be:
1. Clearer and more specific.
2. Actionable for an NBA data analysis agent.
3. Diverse in the angle or detail they explore, while staying related to the original prompt's core idea.
Output *only* a JSON list of 3 strings, where each string is a suggested prompt.
Example Input: 'LeBron vs Jordan'
Example Output: [
  "Compare LeBron James' and Michael Jordan's career regular season statistics.",
  "Analyze LeBron James' and Michael Jordan's performance in NBA Finals games.",
  "Who had a higher peak Player Efficiency Rating (PER), LeBron James or Michael Jordan?"
]
User's Prompt: '{current_prompt}'"""
    try:
        logger.info(f"Generating prompt improvement suggestions for: '{current_prompt}' using model: {SUGGESTION_MODEL_ID}")
        native_model = genai.GenerativeModel(SUGGESTION_MODEL_ID)
        response = native_model.generate_content(prompt_template)
        response_text = response.text if hasattr(response, 'text') and isinstance(response.text, str) else ""
        if not response_text:
            logger.warning(f"Empty response text from prompt suggestion model for input: '{current_prompt}'.")
            return generic_examples
        cleaned_response = response_text.strip().removeprefix("```json").removesuffix("```").strip()
        suggestions = json.loads(cleaned_response)
        if isinstance(suggestions, list) and all(isinstance(s, str) for s in suggestions) and len(suggestions) > 0:
            logger.info(f"Generated prompt improvement suggestions: {suggestions[:3]}")
            return suggestions[:3]
        else:
            logger.warning(f"Prompt improvement suggestions returned non-list/non-string or empty list: {suggestions}")
            return generic_examples
    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to parse prompt improvement suggestions JSON: {json_err}. Response was: {response_text}", exc_info=True)
        return generic_examples
    except Exception as e:
        logger.error(f"Error during native prompt improvement suggestion generation: {e}", exc_info=True)
        return generic_examples

# --- API Endpoints ---

@router.get(
    "/stream",
    summary="Run Research Workflow (SSE Stream with Caching)",
    description="Executes the research workflow for a given topic and optional sections, "
                "streaming progress and results via Server-Sent Events. Results for identical "
                "topic/section combinations are cached to improve response times for subsequent requests. "
                "After the main report content is streamed, it attempts to generate and stream follow-up suggestions.",
)
async def run_research_workflow_sse_endpoint(
    request: Request,
    topic: str = Query(..., description="The main topic for the research workflow."),
    selected_sections_json: Optional[str] = Query(None, alias="selected_sections", description="A URL-encoded JSON string representing a list of specific section names to focus on (e.g., '[\"Player Analysis\", \"Team Comparison\"]'. Optional.")
) -> StreamingResponse:
    """
    Server-Sent Events endpoint to stream results from the ResearchWorkflow.
    Supports caching of workflow results based on topic and selected sections.

    Query Parameters:
    - **topic** (str, required): The research topic.
    - **selected_sections** (str, optional, alias `selected_sections_json`): 
      A URL-encoded JSON string array of section names. If invalid JSON, it's ignored.

    SSE Event Stream: (Same as previously documented)
    - `event: message`: Chunks from the research workflow.
    - `event: suggestions`: Follow-up suggestions. `data`: `{"suggestions": List[str]}`.
    - `event: error`: Errors during stream. `data`: `{"type": "error", "content": "Error message"}`.
    """
    sections_list: List[str] = []
    if selected_sections_json:
        try:
            parsed_list = json.loads(selected_sections_json)
            if isinstance(parsed_list, list) and all(isinstance(item, str) for item in parsed_list):
                sections_list = parsed_list
            else:
                logger.warning(f"Query param 'selected_sections' was not a list of strings: {selected_sections_json}")
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in 'selected_sections' query parameter: {selected_sections_json}")

    logger.info(f"Received GET /research/stream request for topic: '{topic}', Sections: {sections_list}")

    if not topic.strip():
        logger.error("Research topic is empty.")
        async def empty_topic_error_stream():
            error_data = {"type": "error", "event": "error", "content": Errors.TOPIC_EMPTY}
            yield format_sse(json.dumps(error_data), event="error") # Changed format_sse_message to format_sse
        return StreamingResponse(empty_topic_error_stream(), media_type="text/event-stream")

    # --- Workflow Instantiation with Caching Support ---
    workflow_storage = None
    workflow_session_id = None
    try:
        # Generate a deterministic session_id for caching based on topic and sections
        key_string = f"{topic.lower().strip()}_{'_'.join(sorted(s.lower().strip() for s in sections_list))}"
        workflow_session_id = f"research_workflow_{hashlib.md5(key_string.encode()).hexdigest()}"
        
        # Ensure STORAGE_DB_FILE is configured for caching to work
        if STORAGE_DB_FILE:
            workflow_storage = SqliteWorkflowStorage(db_file=STORAGE_DB_FILE, table_name="research_workflows_state")
            logger.info(f"ResearchWorkflow will use SQLite storage for session_id: {workflow_session_id}")
        else:
            logger.warning("STORAGE_DB_FILE not configured. ResearchWorkflow caching will be disabled.")
            
        workflow = ResearchWorkflow(session_id=workflow_session_id, storage=workflow_storage)
        logger.info(f"Instantiated ResearchWorkflow for topic: '{topic}', Session ID: {workflow_session_id}")

    except Exception as wf_init_err:
        logger.error(f"Failed to initialize ResearchWorkflow: {wf_init_err}", exc_info=True)
        async def wf_init_error_stream():
            error_data = {"type": "error", "event": "error", "content": "Failed to initialize research process."}
            yield format_sse(json.dumps(error_data), event="error") # Changed format_sse_message to format_sse
        return StreamingResponse(wf_init_error_stream(), media_type="text/event-stream")
    # --- End Workflow Instantiation ---

    async def sse_event_generator() -> AsyncGenerator[str, None]:
        full_report_content_accumulator = ""
        try:
            async for agent_chunk in workflow.arun(topic=topic, selected_sections=sections_list):
                if await request.is_disconnected():
                    logger.info(f"Client disconnected during research stream for topic: '{topic}'. Stopping.")
                    break
                try:
                    chunk_dict = recursive_asdict(agent_chunk)
                    if not isinstance(chunk_dict, dict): chunk_dict = {"content": str(chunk_dict), "event": "UnknownChunkType"}
                    if 'event' not in chunk_dict: chunk_dict['event'] = 'RunResponse'
                    
                    if chunk_dict.get("event") == "RunResponse" and isinstance(chunk_dict.get("content"), str):
                        full_report_content_accumulator += chunk_dict["content"] + "\n"
                    elif chunk_dict.get("event_type") == "CacheHit" and chunk_dict.get("data", {}).get("step") == "DataGathering": # Check for specific cache hit event from workflow
                        # If data gathering was cached, its content might be in event.data.message or similar
                        cached_gathered_data = chunk_dict.get("data", {}).get("message", "") # Adjust based on actual cache hit event structure
                        if isinstance(cached_gathered_data, str):
                             full_report_content_accumulator = cached_gathered_data # Use the full cached content
                        logger.info("Data gathering step was served from cache. Accumulated content updated.")


                    yield format_sse(json.dumps(chunk_dict), event="message") # Changed format_sse_message to format_sse
                    await asyncio.sleep(0.01)
                except Exception as chunk_processing_err:
                    logger.error(f"Error processing/serializing chunk for topic '{topic}': {chunk_processing_err}", exc_info=True)
                    error_payload = {"type": "error", "event": "ChunkProcessingError", "content": "Error processing a stream chunk."}
                    yield format_sse(json.dumps(error_payload), event="error") # Changed format_sse_message to format_sse

            if not await request.is_disconnected():
                if workflow.session_state and workflow.session_state.get(f"final_report_{workflow._generate_cache_key(topic, sections_list)}"):
                    logger.info(f"Final report for topic '{topic}' was served from cache. Skipping suggestion generation if already done or not applicable.")
                    # Suggestions might also be cached or tied to the report generation.
                    # For simplicity, we regenerate suggestions if the report was cached, unless suggestions are also cached.
                    # A more robust system would cache suggestions alongside the report.
                    if not full_report_content_accumulator and isinstance(workflow.session_state.get(f"final_report_{workflow._generate_cache_key(topic, sections_list)}"), str) :
                        full_report_content_accumulator = workflow.session_state.get(f"final_report_{workflow._generate_cache_key(topic, sections_list)}")


                logger.info(f"Research workflow stream completed for topic '{topic}'. Generating follow-up suggestions.")
                suggestions = await asyncio.to_thread(_generate_suggestions_from_report, full_report_content_accumulator.strip())
                if suggestions:
                    suggestions_payload = {"suggestions": suggestions}
                    yield format_sse(json.dumps(suggestions_payload), event="suggestions") # Changed format_sse_message to format_sse
                    logger.info(f"Sent {len(suggestions)} follow-up suggestions for topic '{topic}'.")
                else:
                    logger.info(f"No follow-up suggestions generated for topic '{topic}'.")
            
        except Exception as e:
            logger.error(f"Error during research SSE generation for topic '{topic}': {e}", exc_info=True)
            error_payload = {"type": "error", "event": "StreamError", "content": Errors.SSE_GENERATION_ERROR.format(error_details=str(e))}
            try:
                yield format_sse(json.dumps(error_payload), event="error") # Changed format_sse_message to format_sse
            except Exception as final_err_send:
                logger.error(f"Failed to send final error SSE message for topic '{topic}': {final_err_send}")
        finally:
            logger.info(f"SSE research_event_generator finished for topic: '{topic}'")

    headers = {"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    return StreamingResponse(sse_event_generator(), media_type="text/event-stream", headers=headers)

@router.post(
    "/prompt-suggestions",
    summary="Get Prompt Improvement Suggestions",
    description="Generates a list of improved or alternative prompt suggestions based on the user's current input prompt, "
                "using a native Gemini model.",
    response_model=PromptSuggestionResponse
)
async def get_prompt_improvement_suggestions_endpoint(
    request_body: PromptSuggestionRequest = Body(...)
) -> PromptSuggestionResponse:
    """Endpoint to generate prompt improvement suggestions."""
    logger.info(f"Received POST /research/prompt-suggestions for prompt: '{request_body.current_prompt[:70]}...'")
    try:
        suggestions_list = await asyncio.to_thread(_generate_prompt_improvement_suggestions, request_body.current_prompt)
        return PromptSuggestionResponse(suggestions=suggestions_list)
    except Exception as e:
        logger.error(f"Failed to generate prompt suggestions for '{request_body.current_prompt[:70]}...': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=Errors.PROMPT_SUGGESTION_ERROR
        )
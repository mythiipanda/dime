"""
Handles Server-Sent Events (SSE) for streaming responses from the AI agent.
This module includes utilities for formatting SSE messages, recursively converting
complex objects to dictionaries for JSON serialization, and the main SSE route.
"""
import asyncio
import json
import logging
import re # For thinking pattern extraction
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from rich.pretty import pprint # For test_agent_stream
from agents import nba_agent
from dataclasses import is_dataclass # No need for asdict if using custom recursive one
from agno.agent import RunResponse # For type hinting in test_agent_stream
from typing import AsyncIterator, Dict, Any, Optional # Added Optional
from agno.utils.common import dataclass_to_dict # For test_agent_stream

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Constants ---
MAX_RECURSION_DEPTH = 20  # Limit recursion depth for object serialization
SSE_LOG_TRUNCATE_LIMIT = 1000 # Max characters to log for an SSE message

STAT_CARD_MARKER = "STAT_CARD_JSON::"
CHART_DATA_MARKER = "CHART_DATA_JSON::"
TABLE_DATA_MARKER = "TABLE_DATA_JSON::"
PLAYER_CARD_MARKER = "PLAYER_CARD_JSON::"
TEAM_ANALYSIS_MARKER = "TEAM_ANALYSIS_JSON::"
TRADE_SCENARIO_MARKER = "TRADE_SCENARIO_JSON::"

# --- Helper Functions ---
def recursive_asdict(obj: Any, _depth: int = 0) -> Any:
    """
    Recursively converts an object (especially dataclasses and nested structures)
    into a dictionary suitable for JSON serialization, with a depth limit.
    Handles basic types, lists, dicts, dataclasses, and other objects with __dict__.
    Provides fallbacks for unserializable types.
    """
    if _depth > MAX_RECURSION_DEPTH:
        return f"<Max Recursion Depth Exceeded ({MAX_RECURSION_DEPTH})>"

    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    elif is_dataclass(obj):
        result = {}
        # Iterate through fields defined in __init__ or __slots__ if available,
        # otherwise fallback to __dict__ but be mindful of potential issues.
        # For simplicity, __dict__ is used here as in the original.
        for key, value in obj.__dict__.items():
            result[key] = recursive_asdict(value, _depth + 1)
        return result
    elif isinstance(obj, list):
        return [recursive_asdict(item, _depth + 1) for item in obj]
    elif isinstance(obj, dict) or type(obj).__name__ == 'mappingproxy':
        current_dict = dict(obj) # Ensure mutable dict
        return {key: recursive_asdict(value, _depth + 1) for key, value in current_dict.items()}
    elif hasattr(obj, "__dict__"): # For general objects
        try:
            obj_dict = dict(vars(obj))
            return recursive_asdict(obj_dict, _depth + 1)
        except Exception as e:
            logger.warning(f"Could not serialize object part using vars() for {type(obj).__name__}: {e}")
            return f"<Object of type {type(obj).__name__} partially unserializable>"
    else: # Fallback for other types
        try:
            return str(obj)
        except Exception:
            return f"<Unserializable Type: {type(obj).__name__}>"

def format_sse(data: str, event: Optional[str] = None) -> str:
    """Formats data into an SSE message string."""
    msg = f"data: {data}\n\n"
    if event is not None:
        msg = f"event: {event}\n{msg}"
    return msg

def format_message_data(chunk_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms a raw agent chunk dictionary into a structured message dictionary
    suitable for sending to the frontend via SSE.

    This function extracts relevant information like event type, content, tool calls,
    and metadata. It also formats tool calls for better display, calculates
    a simple progress indicator, and attempts to extract structured data
    (stat cards, charts, tables) if markers are present in the content.
    """
    event_type = chunk_dict.get("event")
    content = chunk_dict.get("content", "")
    tools = chunk_dict.get("tools", [])

    # Extract additional metadata from the chunk
    agent_id = chunk_dict.get("agent_id")
    session_id = chunk_dict.get("session_id")
    run_id = chunk_dict.get("run_id")
    model = chunk_dict.get("model")
    thinking = chunk_dict.get("thinking")
    reasoning_content = chunk_dict.get("reasoning_content")
    created_at = chunk_dict.get("created_at")

    # Extract any rich data markers from content if it's a string
    data_type = None
    data_payload = None

    if isinstance(content, str):
        # Check for rich data markers
        for marker, marker_type in [
            (STAT_CARD_MARKER, "STAT_CARD"),
            (CHART_DATA_MARKER, "CHART_DATA"),
            (TABLE_DATA_MARKER, "TABLE_DATA"),
            (PLAYER_CARD_MARKER, "PLAYER_CARD"),
            (TEAM_ANALYSIS_MARKER, "TEAM_ANALYSIS"),
            (TRADE_SCENARIO_MARKER, "TRADE_SCENARIO")
        ]:
            if marker in content:
                try:
                    marker_start = content.find(marker)
                    json_start = marker_start + len(marker)
                    # Extract the content before the marker
                    pre_marker_content = content[:marker_start].strip()
                    # Extract the JSON data after the marker
                    json_data = content[json_start:].strip()

                    # Set the data type and payload
                    data_type = marker_type
                    data_payload = json_data

                    # Update content to only include pre-marker text
                    content = pre_marker_content
                    break
                except Exception as e:
                    logger.warning(f"Failed to extract {marker_type} data: {e}")

    # Format tool calls with more details
    formatted_tool_calls = []
    if tools:
        for tool in tools:
            tool_name = tool.get("tool_name", "Unknown Tool")
            tool_status = "started" if event_type == "ToolCallStarted" else "completed"
            tool_args = tool.get("args", {})
            tool_content = tool.get("content", "")
            tool_error = None

            # Check if tool content contains an error
            if isinstance(tool_content, str) and tool_content.startswith('{"error":'):
                try:
                    error_data = json.loads(tool_content)
                    tool_error = error_data.get("error")
                    tool_status = "error"
                except:
                    pass

            formatted_tool_calls.append({
                "tool_name": tool_name,
                "status": tool_status,
                "args": tool_args,
                "content": tool_content,
                "error": tool_error
            })

    # Determine message status based on event type
    status = "thinking"
    if event_type == "RunCompleted":
        status = "complete"
    elif event_type == "Error":
        status = "error"
    elif event_type == "ToolCallStarted":
        status = "tool_calling"

    # Calculate progress
    progress = 0
    if event_type in ["RunStarted", "ToolCallStarted", "ToolCallCompleted", "RunCompleted"]:
        progress_map = {
            "RunStarted": 10,
            "ToolCallStarted": 30,
            "ToolCallCompleted": 70,
            "RunCompleted": 100
        }
        progress = progress_map.get(event_type, 0)

    # Build the enhanced message data structure
    message_data = {
        "role": "assistant",
        "content": content,
        "event": event_type,
        "status": status,
        "progress": progress,
        "toolCalls": formatted_tool_calls,
        "dataType": data_type,
        "dataPayload": data_payload,
        "metadata": {
            "agent_id": agent_id,
            "session_id": session_id,
            "run_id": run_id,
            "model": model,
            "timestamp": created_at
        }
    }

    # Extract thinking patterns from content
    thinking_patterns = {}
    if isinstance(content, str):
        # Look for patterns like **Thinking:** or **Planning:** or **Analyzing:** in string content
        # The 're' import is now at the top of the file.
        patterns = {
            "thinking": r"\*\*Thinking:\*\*(.*?)(?=\*\*|$)",
            "planning": r"\*\*Planning:\*\*(.*?)(?=\*\*|$)",
            "analyzing": r"\*\*Analyzing:\*\*(.*?)(?=\*\*|$)"
        }
        for pattern_type, pattern_regex in patterns.items(): # Renamed pattern to pattern_regex
            matches = re.findall(pattern_regex, content, re.DOTALL | re.IGNORECASE)
            if matches:
                thinking_patterns[pattern_type] = "\n".join([match.strip() for match in matches])

    # Add thinking/reasoning if available
    if thinking or reasoning_content or thinking_patterns: # Check if any thinking data exists
        message_data["reasoning"] = {
            "thinking": thinking,
            "content": reasoning_content,
            "patterns": thinking_patterns
        }

    # Enhanced processing - add step detection and confidence extraction
    enhanced_data = {}
    content_str = str(content) if content is not None else ""

    if content_str:
        # Extract steps using simple patterns
        step_patterns = [
            r"\*\*Step (\d+)(?:/(\d+))?\*\*:?\s*(.*?)(?=\*\*|$)",
            r"Step (\d+)(?:/(\d+))?\s*[:.-]\s*(.*?)(?=Step|\n|$)"
        ]

        steps = []
        for pattern in step_patterns:
            matches = re.findall(pattern, content_str, re.DOTALL | re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    if len(match) == 3:  # Step X/Y: Description
                        step_num, total_steps, description = match
                        steps.append({
                            "step": int(step_num),
                            "total": int(total_steps) if total_steps else None,
                            "description": description.strip()
                        })

        if steps:
            enhanced_data["steps"] = sorted(steps, key=lambda x: x["step"])

        # Extract confidence levels
        confidence_patterns = [r"(\d+)%\s*confident", r"confidence(?:\s+level)?:?\s*(\d+)%"]
        confidence_levels = []

        for pattern in confidence_patterns:
            matches = re.findall(pattern, content_str, re.IGNORECASE)
            for match in matches:
                try:
                    confidence = int(match)
                    if 0 <= confidence <= 100:
                        confidence_levels.append({"level": confidence})
                except ValueError:
                    continue

        if confidence_levels:
            enhanced_data["confidence"] = confidence_levels

        # Extract key insights
        insight_patterns = [r"key insight:?\s*(.*?)(?=\.|$)", r"recommendation:?\s*(.*?)(?=\.|$)"]
        insights = []

        for pattern in insight_patterns:
            matches = re.findall(pattern, content_str, re.IGNORECASE)
            for match in matches:
                insight = match.strip()
                if len(insight) > 10:
                    insights.append(insight)

        if insights:
            enhanced_data["insights"] = insights

    # Enhanced progress calculation
    if enhanced_data.get("steps"):
        current_step = max(enhanced_data["steps"], key=lambda x: x["step"])
        if current_step.get("total"):
            step_progress = (current_step["step"] / current_step["total"]) * 100
            progress = max(progress, step_progress)
            message_data["progress"] = progress
            message_data["phase"] = "analysis" if progress < 80 else "synthesis"

    # Add enhanced data if any was found
    if enhanced_data:
        message_data["enhanced"] = enhanced_data

    # Set default content for certain events if no content is provided
    if not content:
        if event_type == "RunStarted":
            message_data["content"] = "Starting to process your request..."
        elif event_type == "ToolCallStarted" and formatted_tool_calls:
            message_data["content"] = f"Calling tool: {formatted_tool_calls[0]['tool_name']}..."
        elif event_type == "ToolCallCompleted" and formatted_tool_calls:
            if any(tool.get("error") for tool in formatted_tool_calls):
                message_data["content"] = "Tool call encountered an error."
            else:
                message_data["content"] = "Tool call completed successfully."
        elif event_type == "Error":
            message_data["content"] = "An error occurred during processing."

    return message_data

# --- SSE Route ---
@router.get("/ask")
async def ask_agent_keepalive_sse(request: Request, prompt: str) -> StreamingResponse:
    """
    Handles requests to the AI agent and streams responses back using SSE.
    It processes agent run chunks, formats them, and sends them to the client.
    Includes keep-alive messages and a final event upon completion.
    """
    logger.info(f"Received GET /ask request with prompt: '{prompt}'")
    workflow_instance = nba_agent # Assuming nba_agent is correctly initialized elsewhere

    async def keepalive_sse_generator() -> AsyncIterator[str]:
        """Generates SSE messages from the agent's run stream."""
        try:
            logger.info(f"Starting streaming NBA analysis workflow for prompt: {prompt}")
            async for chunk in await workflow_instance.arun(prompt): # Ensure arun is awaited if it's an async gen
                chunk_dict = recursive_asdict(chunk)
                message_data = format_message_data(chunk_dict)
                sse_message_string = format_sse(json.dumps(message_data))

                log_msg_preview = sse_message_string[:SSE_LOG_TRUNCATE_LIMIT]
                if len(sse_message_string) > SSE_LOG_TRUNCATE_LIMIT:
                    log_msg_preview += "..."
                logger.debug(f"Yielding SSE string (len={len(sse_message_string)}): {log_msg_preview}")

                yield sse_message_string
                await asyncio.sleep(0.01) # Small sleep to ensure flushing and allow other tasks

                if chunk_dict.get("event") == "RunCompleted":
                    logger.info("Detected RunCompleted event, preparing final SSE event.")
                    final_event_data = {
                        "role": "assistant",
                        "content": message_data.get("content", "Analysis complete."), # Use existing content or default
                        "event": "final",
                        "status": "complete",
                        "progress": 100,
                        "reasoning": message_data.get("reasoning"),
                        "metadata": message_data.get("metadata")
                    }
                    yield format_sse(json.dumps(final_event_data), event="final") # Send with 'final' event type
                    await asyncio.sleep(0.01) # Ensure final message is sent
                    logger.info("Final SSE event sent.")
                    break # Explicitly break after RunCompleted and final event

        except Exception as e:
            logger.exception("Error during SSE generation for /ask endpoint.")
            error_content = {
                "role": "assistant", "content": f"An error occurred: {str(e)}",
                "status": "error", "progress": 0, "event": "error"
            }
            yield format_sse(json.dumps(error_content), event="error")
        finally:
            logger.info("SSE generator for /ask finished.")

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform", # Important for SSE
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no", # Useful for Nginx
        # "Transfer-Encoding": "chunked" # Not typically set manually for StreamingResponse
    }
    return StreamingResponse(keepalive_sse_generator(), headers=headers, media_type="text/event-stream")

@router.get("/summer-strategy")
async def summer_strategy_sse(request: Request, team_name: str, season: str = "2024-25") -> StreamingResponse:
    """
    Handles summer strategy analysis for a specific NBA team using the specialized workflow.
    Streams comprehensive strategic analysis including performance evaluation, contract analysis, and recommendations.
    """
    logger.info(f"Received summer strategy request for {team_name} ({season})")

    # Import here to avoid circular imports
    from agents import summer_strategy_workflow

    async def summer_strategy_generator() -> AsyncIterator[str]:
        """Generates SSE messages from the summer strategy workflow."""
        try:
            logger.info(f"Starting summer strategy workflow for {team_name}")
            async for chunk in summer_strategy_workflow.arun(team_name, season):
                chunk_dict = recursive_asdict(chunk)
                message_data = format_message_data(chunk_dict)
                sse_message_string = format_sse(json.dumps(message_data))

                log_msg_preview = sse_message_string[:SSE_LOG_TRUNCATE_LIMIT]
                if len(sse_message_string) > SSE_LOG_TRUNCATE_LIMIT:
                    log_msg_preview += "..."
                logger.debug(f"Yielding summer strategy SSE (len={len(sse_message_string)}): {log_msg_preview}")

                yield sse_message_string
                await asyncio.sleep(0.01)

                # Only break on the main workflow completion, not individual agent completions
                # Check if this is the final workflow completion by looking for specific markers
                if (chunk_dict.get("event") == "RunCompleted" and
                    chunk_dict.get("run_id") == "summer-strategy-main"):
                    logger.info("Summer strategy analysis completed.")
                    final_event_data = {
                        "role": "assistant",
                        "content": message_data.get("content", "Summer strategy analysis complete."),
                        "event": "final",
                        "status": "complete",
                        "progress": 100,
                        "reasoning": message_data.get("reasoning"),
                        "metadata": message_data.get("metadata")
                    }
                    yield format_sse(json.dumps(final_event_data), event="final")
                    await asyncio.sleep(0.01)
                    logger.info("Final summer strategy SSE event sent.")
                    break

        except Exception as e:
            logger.exception("Error during summer strategy SSE generation.")
            error_content = {
                "role": "assistant",
                "content": f"An error occurred during summer strategy analysis: {str(e)}",
                "status": "error",
                "progress": 0,
                "event": "error"
            }
            yield format_sse(json.dumps(error_content), event="error")
        finally:
            logger.info("Summer strategy SSE generator finished.")

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(summer_strategy_generator(), headers=headers, media_type="text/event-stream")

@router.get("/test_stream")
async def test_agent_stream(request: Request, prompt: str) -> None: # Returns None as it prints
    logger.info(f"Received GET /test_streaming request with prompt: '{prompt}'")
    run_stream: AsyncIterator[RunResponse] = nba_agent.arun(prompt)
    async for chunk in run_stream:
        pprint(dataclass_to_dict(chunk, exclude={"messages"}))
        print("---" * 20)
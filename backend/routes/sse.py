import asyncio
import json
import logging
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from rich.pretty import pprint
from backend.agents import nba_agent
from dataclasses import asdict, is_dataclass
from agno.agent import RunResponse
from typing import AsyncIterator, Dict, Any
from agno.utils.common import dataclass_to_dict

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Revised recursive_asdict with depth limit ---
MAX_RECURSION_DEPTH = 20 # Limit recursion depth

def recursive_asdict(obj, _depth=0):
    if _depth > MAX_RECURSION_DEPTH:
        # Return placeholder if max depth is exceeded
        return f"<Max Recursion Depth Exceeded ({MAX_RECURSION_DEPTH})>"

    # Handle basic types and None first
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    # Handle dataclasses
    elif is_dataclass(obj):
        result = {}
        for key, value in obj.__dict__.items():
            result[key] = recursive_asdict(value, _depth + 1) # Increment depth
        return result
    # Handle lists
    elif isinstance(obj, list):
        return [recursive_asdict(item, _depth + 1) for item in obj] # Increment depth
    # Handle dictionaries (including mappingproxy if it occurs again)
    elif isinstance(obj, dict) or type(obj).__name__ == 'mappingproxy':
        # Ensure it's a mutable dict for processing
        current_dict = dict(obj)
        return {key: recursive_asdict(value, _depth + 1) for key, value in current_dict.items()} # Increment depth
    # Handle other objects with __dict__
    elif hasattr(obj, "__dict__"):
        try:
            # Explicitly convert vars(obj) to dict before recursion
            obj_dict = dict(vars(obj))
            return recursive_asdict(obj_dict, _depth + 1) # Increment depth
        except Exception as e:
             # Catch errors during vars() or dict() conversion
             logger.warning(f"Could not serialize object part using vars(): {e}")
             return f"<Object of type {type(obj).__name__} partially unserializable>"
    # Handle other non-serializable types gracefully
    else:
        try:
            # Attempt string conversion as a fallback
            return str(obj)
        except Exception:
            return f"<Unserializable Type: {type(obj).__name__}>"

def format_sse(data: str, event: str | None = None) -> str:
    msg = f"data: {data}\n\n"
    if event is not None:
        msg = f"event: {event}\n{msg}"
    return msg

STAT_CARD_MARKER = "STAT_CARD_JSON::"
CHART_DATA_MARKER = "CHART_DATA_JSON::"
TABLE_DATA_MARKER = "TABLE_DATA_JSON::"

def format_message_data(chunk_dict: Dict[Any, Any]) -> Dict[str, Any]:
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
            (TABLE_DATA_MARKER, "TABLE_DATA")
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
        # Look for patterns like **Thinking:** or **Planning:** or **Analyzing:**
        import re
        patterns = {
            "thinking": r"\*\*Thinking:\*\*(.*?)(?=\*\*|$)",
            "planning": r"\*\*Planning:\*\*(.*?)(?=\*\*|$)",
            "analyzing": r"\*\*Analyzing:\*\*(.*?)(?=\*\*|$)"
        }

        for pattern_type, pattern in patterns.items():
            matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
            if matches:
                thinking_patterns[pattern_type] = "\n".join([match.strip() for match in matches])

    # Add thinking/reasoning if available
    if thinking or reasoning_content or thinking_patterns:
        message_data["reasoning"] = {
            "thinking": thinking,
            "content": reasoning_content,
            "patterns": thinking_patterns
        }

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

@router.get("/ask")
async def ask_agent_keepalive_sse(request: Request, prompt: str):
    logger.info(f"Received GET /ask request with prompt: '{prompt}'")
    workflow_instance = nba_agent

    async def keepalive_sse_generator():
        try:
            logger.info(f"Starting streaming NBA analysis workflow for prompt: {prompt}")
            async for chunk in await workflow_instance.arun(prompt):
                chunk_dict = recursive_asdict(chunk)
                message_data = format_message_data(chunk_dict)

                # Format the final SSE message string
                sse_message_string = format_sse(json.dumps(message_data))

                # Log the string *before* yielding it (limit length for readability)
                log_limit = 1000 # Log first 1000 chars
                logger.debug(f"Yielding SSE string (len={len(sse_message_string)}): {sse_message_string[:log_limit]}{'...' if len(sse_message_string) > log_limit else ''}")

                # Send the chunk immediately and ensure it's flushed
                yield sse_message_string
                await asyncio.sleep(0)  # Allow other tasks to run and ensure streaming

                # Only send final event for RunCompleted
                if chunk_dict.get("event") == "RunCompleted":
                    logger.info("Detected RunCompleted event, sending final event")
                    # Use the same content as the last message but ensure we mark it as complete
                    final_data = {
                        "role": "assistant",
                        "content": message_data["content"],
                        "event": "final",  # Explicitly mark as final event
                        "status": "complete",
                        "progress": 100,
                        # Include any reasoning data from the original message
                        "reasoning": message_data.get("reasoning"),
                        # Include metadata
                        "metadata": message_data.get("metadata")
                    }
                    # Send as both a regular message and a final event to ensure proper handling
                    yield format_sse(json.dumps(final_data))
                    # Then send with the special 'final' event type
                    yield format_sse(json.dumps(final_data), event="final")
                    await asyncio.sleep(0)  # Ensure final message is sent

        except Exception as e:
            logger.exception("Error during SSE generation")
            error_data = {
                "role": "assistant",
                "content": f"Error: {str(e)}",
                "status": "error",
                "progress": 0
            }
            yield format_sse(json.dumps(error_data))
        finally:
            logger.info("END keepalive_sse_generator.")

    # Set up streaming response with appropriate headers
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Transfer-Encoding": "chunked"
    }

    # Return a streaming response with a larger chunk size and immediate flushing
    return StreamingResponse(
        keepalive_sse_generator(),
        headers=headers,
        media_type="text/event-stream"
    )

@router.get("/test_stream")
async def test_agent_stream(request: Request, prompt: str):
    logger.info(f"Received GET /test_streaming request with prompt: '{prompt}'")
    run_stream: AsyncIterator[RunResponse] = await nba_agent.arun(prompt)
    async for chunk in run_stream:
        pprint(dataclass_to_dict(chunk, exclude={"messages"}))
        print("---" * 20)
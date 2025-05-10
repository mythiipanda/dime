import asyncio
import json
import logging
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from rich.pretty import pprint
from backend.teams import nba_analysis_team # Corrected import
from dataclasses import asdict, is_dataclass
from agno.agent import RunResponse
from typing import Iterator, Dict, Any
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

# Markers from agents.py (ensure these are consistent if changed there)
STAT_CARD_MARKER = "STAT_CARD_JSON::"
CHART_DATA_MARKER = "CHART_DATA_JSON::"
TABLE_DATA_MARKER = "TABLE_DATA_JSON::"

def format_message_data(chunk_dict: Dict[Any, Any]) -> Dict[str, Any]:
    event_type = chunk_dict.get("event")
    content = chunk_dict.get("content", "") # Ensure content is a string
    tools = chunk_dict.get("tools", [])
    
    message_data = {
        "role": "assistant",
        "content": content, # Initial content
        "event": event_type,
        "status": "thinking", # Default status
        "toolCalls": [],
        "dataType": None, # For rich data
        "dataPayload": None # For rich data
    }

    # Check for rich data markers in content
    if isinstance(content, str):
        # Handle agent outputting ```json\nMARKER::\n{...}\n```
        cleaned_content_for_json_parsing = content # Assume no JSON yet
        potential_json_payload_str = None

        if "```json" in content and STAT_CARD_MARKER in content:
            message_data["dataType"] = "STAT_CARD"
            # Extract content after MARKER::, assuming it's wrapped in ```json ... ```
            # This expects MARKER:: to be *inside* the json block if agent does that, or after ```json
            if STAT_CARD_MARKER in content:
                payload_start_index = content.find(STAT_CARD_MARKER) + len(STAT_CARD_MARKER)
                potential_json_payload_str = content[payload_start_index:].strip()
                # Remove the ```json and marker from the displayed content for this chunk
                message_data["content"] = content[:content.find(STAT_CARD_MARKER)].replace("```json", "").strip()


        elif "```json" in content and CHART_DATA_MARKER in content:
            message_data["dataType"] = "CHART_DATA"
            if CHART_DATA_MARKER in content:
                payload_start_index = content.find(CHART_DATA_MARKER) + len(CHART_DATA_MARKER)
                potential_json_payload_str = content[payload_start_index:].strip()
                message_data["content"] = content[:content.find(CHART_DATA_MARKER)].replace("```json", "").strip()

        elif "```json" in content and TABLE_DATA_MARKER in content:
            message_data["dataType"] = "TABLE_DATA"
            if TABLE_DATA_MARKER in content:
                payload_start_index = content.find(TABLE_DATA_MARKER) + len(TABLE_DATA_MARKER)
                potential_json_payload_str = content[payload_start_index:].strip()
                # Example: content might be "```json\nTABLE_DATA_JSON::\n{\n  \"title\": \""
                # We want message_data["content"] to be "" for this chunk,
                # and the frontend will accumulate `potential_json_payload_str`
                # Strip initial ```json and marker for the first chunk
                # For subsequent chunks, content will just be part of JSON
                if content.strip().startswith("```json"): # If it's the start of the block
                     message_data["content"] = "" # Don't show the marker line itself as narrative
                else: # It's a continuation of JSON content
                     message_data["content"] = potential_json_payload_str # Pass through the JSON part
                
                # The actual parsing of potential_json_payload_str will now be deferred to the frontend hook,
                # which will accumulate it. For now, sse.py just signals the type.
                # We set dataPayload to the raw string part that *might* be JSON.
                # The frontend will be responsible for accumulating and parsing the full JSON.
                # This is a simplification; a more robust solution would involve sse.py managing accumulation state.
                if message_data["content"] == "": # If we cleared content because marker was found
                    message_data["dataPayload"] = potential_json_payload_str # Send the first part of JSON
                else: # If it's a continuation, this content is part of the JSON
                    message_data["dataPayload"] = content # Send this chunk of JSON
                
                # logger.info(f"Signaling {message_data['dataType']} with initial payload part: {potential_json_payload_str}")


    # Handle different event types (after potential dataType processing)
    if event_type == "RunStarted":
        message_data["status"] = "thinking"
        # Only set default content if no rich data was parsed for this initial event
        if not message_data["dataType"]:
            message_data["content"] = "Starting to process your request..."
    elif event_type == "RunResponse":
        message_data["status"] = "thinking"
        # Content is already set from chunk_dict or cleared if rich data marker was found
    elif event_type == "ToolCallStarted":
        for tool in tools:
            message_data["toolCalls"].append({
                "tool_name": tool.get("tool_name", "Unknown Tool"),
                "status": "started"
            })
        # Optionally, set content to indicate tool call if no other content/rich data
        if not message_data["content"] and not message_data["dataType"]:
             message_data["content"] = f"Calling tool: {tools[0].get('tool_name', 'Unknown Tool')}..." if tools else "Calling a tool..."
    elif event_type == "ToolCallCompleted":
        for tool in tools:
            message_data["toolCalls"].append({
                "tool_name": tool.get("tool_name", "Unknown Tool"),
                "status": "completed",
                "content": tool.get("content", "") # Tool's direct output if any
            })
        if not message_data["content"] and not message_data["dataType"]:
            message_data["content"] = f"Tool {tools[0].get('tool_name', 'Unknown Tool')} completed." if tools else "Tool completed."
    elif event_type == "RunCompleted":
        message_data["status"] = "complete"
        # Final content is already set from the last RunResponse or rich data chunk
    elif event_type == "Error":
        message_data["status"] = "error"
        if not message_data["dataType"]: # Don't overwrite if error itself was in a rich data payload
            message_data["content"] = content or "An error occurred" # Use original content if it was an error message

    # Calculate progress
    if event_type in ["RunStarted", "ToolCallStarted", "ToolCallCompleted", "RunCompleted"]:
        progress_map = {
            "RunStarted": 10,
            "ToolCallStarted": 30,
            "ToolCallCompleted": 70,
            "RunCompleted": 100
        }
        message_data["progress"] = progress_map.get(event_type, 0)

    return message_data

@router.get("/ask")
async def ask_agent_keepalive_sse(request: Request, prompt: str):
    logger.info(f"Received GET /ask request with prompt: '{prompt}'")
    agent_instance = nba_analysis_team

    async def keepalive_sse_generator():
        try:
            logger.info(f"Starting streaming NBA agent for prompt: {prompt}")
            run_stream = await agent_instance.arun(prompt, stream=True, stream_intermediate_steps=True)
            
            async for chunk in run_stream:
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
                    # Use the same content as the last message
                    final_data = {
                        "role": "assistant",
                        "content": message_data["content"],
                        "status": "complete",
                        "progress": 100
                    }
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
    run_stream: Iterator[RunResponse] = await nba_analysis_team.arun(
        prompt,
        stream=True,
        stream_intermediate_steps=True,
    )
    async for chunk in run_stream:
        pprint(dataclass_to_dict(chunk, exclude={"messages"}))
        print("---" * 20)
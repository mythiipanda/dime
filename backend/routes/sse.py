import asyncio
import json
import logging
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from rich.pretty import pprint
from teams import nba_analysis_team
from dataclasses import asdict, is_dataclass
from agno.agent import RunResponse
from typing import Iterator, Dict, Any
from agno.utils.common import dataclass_to_dict

logger = logging.getLogger(__name__)

router = APIRouter()

def recursive_asdict(obj):
    if is_dataclass(obj):
        result = {}
        for key, value in obj.__dict__.items():
            result[key] = recursive_asdict(value)
        return result
    elif isinstance(obj, list):
        return [recursive_asdict(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: recursive_asdict(value) for key, value in obj.items()}
    elif hasattr(obj, "__dict__"):
        return recursive_asdict(vars(obj))
    else:
        return obj

def format_sse(data: str, event: str | None = None) -> str:
    msg = f"data: {data}\n\n"
    if event is not None:
        msg = f"event: {event}\n{msg}"
    return msg

def format_message_data(chunk_dict: Dict[Any, Any]) -> Dict[str, Any]:
    event_type = chunk_dict.get("event")
    content = chunk_dict.get("content")
    tools = chunk_dict.get("tools", [])
    
    message_data = {
        "role": "assistant",
        "content": content or "",
        "event": event_type,
        "status": "thinking",
        "toolCalls": []
    }

    # Handle different event types
    if event_type == "RunStarted":
        message_data["status"] = "thinking"
        message_data["content"] = "Starting to process your request..."
    elif event_type == "RunResponse":
        # Don't modify the content for RunResponse events
        message_data["status"] = "thinking"
    elif event_type == "ToolCallStarted":
        for tool in tools:
            message_data["toolCalls"].append({
                "tool_name": tool.get("tool_name", "Unknown Tool"),
                "status": "started"
            })
    elif event_type == "ToolCallCompleted":
        for tool in tools:
            message_data["toolCalls"].append({
                "tool_name": tool.get("tool_name", "Unknown Tool"),
                "status": "completed",
                "content": tool.get("content", "")
            })
    elif event_type == "RunCompleted":
        message_data["status"] = "complete"
    elif event_type == "Error":
        message_data["status"] = "error"
        message_data["content"] = content or "An error occurred"

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
                
                logger.debug(f"Sending SSE chunk: {json.dumps(message_data)}")
                # Send the chunk immediately and ensure it's flushed
                yield format_sse(json.dumps(message_data))
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
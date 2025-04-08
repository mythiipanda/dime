import asyncio
import json
import logging
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from rich.pretty import pprint
from ..teams import nba_analysis_team
from dataclasses import asdict, is_dataclass
from agno.agent import RunResponse
from typing import Iterator
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
        # Fallback for objects with __dict__ but not dataclasses
        return recursive_asdict(vars(obj))
    else:
        return obj

def format_sse(data: str, event: str | None = None) -> str:
    msg = f"data: {data}\n\n"
    if event is not None:
        msg = f"event: {event}\n{msg}"
    # Add padding to force flush
    msg += ":" + (" " * 2048) + "\n\n"
    return msg

@router.get("/ask")
async def ask_agent_keepalive_sse(request: Request, prompt: str):
    logger.info(f"Received GET /ask_team request with prompt: '{prompt}'")
    agent_instance = nba_analysis_team

    async def keepalive_sse_generator():
        logger.info(f"START keepalive_sse_generator for prompt: '{prompt}'")
        try:
            logger.info(f"Starting streaming NBA agent for prompt: {prompt}")
            run_stream = await agent_instance.arun(prompt, stream=True, stream_intermediate_steps=True)
            async for chunk in run_stream:
                chunk_dict = recursive_asdict(chunk)
                event_type = chunk_dict.get("event")
                content = chunk_dict.get("content")
                member_responses = chunk_dict.get("member_responses") or []
                message = ""

                if event_type == "RunStarted":
                    message = "Agent run started."
                elif event_type == "ToolCallStarted":
                    tools = chunk_dict.get("tools") or []
                    if tools:
                        tool_names = ", ".join(t.get("tool_name", "unknown") for t in tools)
                        message = f"Calling tool(s): {tool_names}"
                    else:
                        message = "Tool call started."
                elif event_type == "ToolCallCompleted":
                    tools = chunk_dict.get("tools") or []
                    if tools:
                        tool_names = ", ".join(t.get("tool_name", "unknown") for t in tools)
                        message = f"Tool(s) completed: {tool_names}"
                    else:
                        message = "Tool call completed."
                elif event_type in ("RunResponse", "RunCompleted"):
                    message = content or ""
                else:
                    message = content or event_type or "Agent update."

                # Append member responses summaries
                for mr in member_responses:
                    mr_content = mr.get("content")
                    if mr_content:
                        message += f"\nMember response: {mr_content[:200]}"

                logger.debug(f"Streaming chunk: {chunk_dict}")
                yield format_sse(json.dumps({
                    "type": "agent_chunk",
                    "data": chunk_dict,
                    "message": message
                }))
            logger.info(f"Streaming Agno agent completed for prompt: {prompt}")
            final_content = chunk.content if 'chunk' in locals() else None

            if final_content is None:
                logger.error("Agent did not produce a recognizable final response.")
                yield format_sse(json.dumps({"type": "error", "message": "Agent did not produce a recognizable final response."}))
            else:
                logger.debug(f"Sending final content via SSE: {final_content[:100]}...")
                final_sse_data = {"type": "final_response", "content": final_content}
                yield format_sse(json.dumps(final_sse_data), event="final")
        except Exception as e:
            logger.exception("Error during SSE generation")
            error_detail = f"Error processing agent request: {str(e)}"
            try:
                yield format_sse(json.dumps({"type": "error", "message": error_detail}))
            except Exception as send_err:
                logger.error(f"Failed to send error message: {send_err}")
        finally:
            logger.info("END keepalive_sse_generator.")

    headers = {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(keepalive_sse_generator(), headers=headers)
@router.get("/test_stream")
async def test_agent_stream(request: Request, prompt: str):
    logger.info(f"Received GET /test_streaming request with prompt: '{prompt}'")
    run_stream: Iterator[RunResponse] = await nba_analysis_team.arun(  # Now points to nba_agent
        prompt,
        stream=True,
        stream_intermediate_steps=True,
    )
    async for chunk in run_stream:
        pprint(dataclass_to_dict(chunk, exclude={"messages"}))
        print("---" * 20)
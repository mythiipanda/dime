import asyncio
import json
import logging
from typing import Dict, Any

from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.types import Send

from langgraph_agent.graph import app as langgraph_app
from langgraph_agent.services import EventStreamProcessor
from langgraph_agent.memory import get_memory_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Create service instance
event_processor = EventStreamProcessor(langgraph_app, get_memory_manager())

async def agent_event_generator(input_query: str, thread_id: str = None, user_id: str = None):
    """
    Runs the LangGraph agent and yields formatted SSE events with memory support.
    """
    async for event in event_processor.process_events(input_query, thread_id, user_id):
        yield event

def format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """Format data as SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

@router.get("/agent/stream", tags=["AI Agent SSE"])
async def stream_agent_response(
    request: Request,
    query: str = Query(..., description="The user's query for the AI agent."),
    thread_id: str = Query(None, description="Thread ID for multi-turn conversation. If not provided, a new conversation starts."),
    user_id: str = Query(None, description="User ID for cross-thread persistence and user-specific memory."),
):
    """
    Streams the AI agent's processing steps and final response using Server-Sent Events (SSE).
    
    Enhanced streaming with reliable LangGraph modes and multi-turn conversation support:
    
    Multi-turn Conversation:
    - Use `thread_id` to continue existing conversations
    - Use `user_id` for user-specific memory across conversations
    - If no `thread_id` provided, a new conversation thread is created
    
    Events:
    - `node_update`: {"node_name": str} - Indicates which graph node just ran.
    - `message`: Various payloads depending on message type:
        - Human: {"type": "human", "content": str}
        - AI (text response): {"type": "ai", "content": str}
        - AI (tool call): {"type": "tool_call", "tool_calls": [{"name": str, "args": dict, "id": str}]}
        - Tool Result: {"type": "tool_result", "name": str, "content": str, "tool_call_id": str}
    - `thought_stream`: {"chunk": str} - Intermediate textual output from a node (e.g., LLM thinking).
    - `custom_data`: {various} - Custom streaming data from nodes with status updates.
    - `final_answer`: {"answer": str} - The final textual answer from the agent.
    - `graph_end`: {} - Signals the end of the graph execution.
    - `error`: {"message": str, "type": str} - If an error occurs.
    """
    logger.info(f"SSE connection established for query: '{query[:50]}...'")

    generator = agent_event_generator(query, thread_id, user_id)
    
    async def safe_generator_wrapper():
        try:
            async for data_chunk in generator:
                if await request.is_disconnected():
                    logger.warning(f"Client disconnected for query: '{query[:50]}...'. Stopping stream.")
                    break
                yield data_chunk
        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for query: '{query[:50]}...'")
        finally:
            logger.info(f"Generator cleanup for query: '{query[:50]}...'")

    return StreamingResponse(safe_generator_wrapper(), media_type="text/event-stream")

# For backwards compatibility
agent_sse_router = router
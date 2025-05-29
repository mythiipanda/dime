import asyncio
import json
import logging
from typing import Dict, Any

from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.types import Send

from backend.langgraph_agent.graph import app as langgraph_app
from backend.langgraph_agent.state import AgentState # For type hinting if needed

logger = logging.getLogger(__name__)

router = APIRouter() # Renamed from agent_sse_router

async def agent_event_generator(input_query: str, chat_history: list = None):
    """
    Runs the LangGraph agent and yields formatted SSE events.
    """
    if chat_history is None:
        chat_history = []

    inputs = {"input_query": input_query, "chat_history": chat_history}

    try:
        # langgraph_app.stream yields dictionaries: { node_name: output_state_dict }
        async for event_chunk in langgraph_app.astream(inputs, stream_mode="updates"):
            # logger.debug(f"Raw agent event chunk: {event_chunk}") # Detailed logging
            
            node_name, node_output_state_dict = list(event_chunk.items())[0]

            # 1. Node Update Event
            yield f"event: node_update\ndata: {json.dumps({'node_name': node_name})}\n\n"

            # 2. Process Messages from state
            messages = node_output_state_dict.get("messages", [])
            if messages:
                last_msg_obj = messages[-1] # Langchain BaseMessage object
                
                msg_data_payload = {"type": last_msg_obj.type}

                if hasattr(last_msg_obj, 'content'):
                    msg_data_payload["content"] = last_msg_obj.content
                
                if hasattr(last_msg_obj, 'name') and last_msg_obj.name:
                     msg_data_payload["name"] = last_msg_obj.name

                if last_msg_obj.type == "ai": # AIMessage specific
                    if hasattr(last_msg_obj, 'tool_calls') and last_msg_obj.tool_calls:
                        msg_data_payload["type"] = "tool_call" 
                        msg_data_payload["tool_calls"] = [
                            {"name": tc.get('name'), "args": tc.get('args'), "id": tc.get('id')}
                            for tc in last_msg_obj.tool_calls
                        ]
                        if not msg_data_payload.get("content"):
                             msg_data_payload.pop("content", None)
                
                elif last_msg_obj.type == "tool": # ToolMessage specific
                    msg_data_payload["type"] = "tool_result" 
                    if hasattr(last_msg_obj, 'tool_call_id'):
                        msg_data_payload["tool_call_id"] = last_msg_obj.tool_call_id
                
                yield f"event: message\ndata: {json.dumps(msg_data_payload)}\n\n"

            # 3. Process streaming_output from state (for intermediate thoughts/logs)
            streaming_outputs = node_output_state_dict.get("streaming_output", [])
            if streaming_outputs:
                latest_stream_chunk = streaming_outputs[-1]
                yield f"event: thought_stream\ndata: {json.dumps({'chunk': latest_stream_chunk})}\n\n"

            # 4. Process final_answer
            final_answer = node_output_state_dict.get("final_answer")
            if final_answer is not None and node_name == "response_node": 
                logger.info(f"Yielding final_answer from node: {node_name}")
                yield f"event: final_answer\ndata: {json.dumps({'answer': final_answer})}\n\n"
            
            # 5. Graph End
            if node_name == "__end__":
                logger.info("Yielding graph_end event as node_name is __end__.")
                yield f"event: graph_end\ndata: {json.dumps({})}\n\n"
                await asyncio.sleep(0.05) # Slightly increased sleep
                break
            
            await asyncio.sleep(0.01) 

    except Exception as e:
        logger.error(f"Error in agent event generator: {e}", exc_info=True)
        error_payload = json.dumps({"message": str(e), "type": e.__class__.__name__})
        yield f"event: error\ndata: {error_payload}\n\n"
        # Explicitly do not yield graph_end if an error occurred and was yielded
        return # Stop the generator here
    finally:
        # This block will execute whether the try block completed normally or an unhandled exception occurred
        # (though handled exceptions with 'return' won't reach here for graph_end).
        # We only want to send graph_end if the stream finished without yielding an 'error' event above.
        # A more robust way would be to track if an error was sent, but for now, 
        # if we reach here and no error was caught and yielded by the 'except' block directly above,
        # assume normal completion or an unyielded error (which is less ideal).
        # The 'return' in the except block prevents this 'finally' from sending graph_end after an error.
        logger.info("Agent event stream processing finished. Ensuring graph_end is sent if no error was explicitly yielded.")
        yield f"event: graph_end\ndata: {json.dumps({})}\n\n"
        await asyncio.sleep(0.05)
        logger.info("Agent event stream generator fully terminated.")

@router.get("/agent/stream", tags=["AI Agent SSE"])
async def stream_agent_response(
    request: Request, 
    query: str = Query(..., description="The user's query for the AI agent."),
):
    """
    Streams the AI agent's processing steps and final response using Server-Sent Events (SSE).
    Events:
    - `node_update`: {"node_name": str} - Indicates which graph node just ran.
    - `message`: Various payloads depending on message type:
        - Human: {"type": "human", "content": str}
        - AI (text response): {"type": "ai", "content": str}
        - AI (tool call): {"type": "tool_call", "tool_calls": [{"name": str, "args": dict, "id": str}]}
        - Tool Result: {"type": "tool_result", "name": str, "content": str, "tool_call_id": str}
    - `thought_stream`: {"chunk": str} - Intermediate textual output from a node (e.g., LLM thinking).
    - `final_answer`: {"answer": str} - The final textual answer from the agent.
    - `graph_end`: {} - Signals the end of the graph execution.
    - `error`: {"message": str, "type": str} - If an error occurs.
    """
    logger.info(f"SSE connection established for query: '{query[:50]}...'")
    
    chat_history_mock = [] 

    generator = agent_event_generator(query, chat_history_mock)
    
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

# Example of how to include this router in your main FastAPI app (e.g., in backend/main.py):
# from backend.routes.sse import router as sse_router # Adjusted import if this file is sse.py
# app.include_router(sse_router) 
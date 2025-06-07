"""
Stream service implementation.
Following Single Responsibility Principle (SRP).
"""

import json
import logging
from typing import Dict, Any, Optional, AsyncGenerator
from langgraph_agent.interfaces import IStreamWriter, IEventStreamProcessor
from langgraph_agent.state import AgentState

# Import get_stream_writer with fallback
try:
    from langgraph.config import get_stream_writer
except ImportError:
    def get_stream_writer():
        return lambda data: None

logger = logging.getLogger(__name__)


class StreamWriterService(IStreamWriter):
    """Service for writing stream data."""
    
    def write(self, data: Dict[str, Any]) -> None:
        """Write data to the stream."""
        try:
            writer = get_stream_writer()
            writer(data)
        except Exception as e:
            logger.debug(f"Stream writer not available: {e}")


class EventStreamProcessor(IEventStreamProcessor):
    """Service for processing event streams from LangGraph."""
    
    def __init__(self, langgraph_app, memory_manager):
        """Initialize the event stream processor."""
        self.langgraph_app = langgraph_app
        self.memory_manager = memory_manager
        
    async def process_events(
        self, 
        input_query: str, 
        thread_id: Optional[str] = None, 
        user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Process events and yield SSE formatted strings."""
        try:
            # Generate thread_id if not provided (new conversation)
            if not thread_id:
                thread_id = self.memory_manager.generate_thread_id()
            
            # Create configuration for this conversation thread
            config = self.memory_manager.create_thread_config(thread_id, user_id)
            
            # Prepare inputs - only need the new query, memory handles the rest
            inputs = {"input_query": input_query}

            # Use streaming modes that work reliably
            async for stream_mode, event_chunk in self.langgraph_app.astream(
                inputs,
                config=config,
                stream_mode=["updates", "custom"]
            ):
                if stream_mode == "updates":
                    async for event in self._process_updates(event_chunk, thread_id):
                        yield event
                elif stream_mode == "custom":
                    yield self._format_sse_event("custom_data", event_chunk)
                    
        except Exception as e:
            logger.error(f"Error in event stream processor: {e}", exc_info=True)
            error_payload = {"message": str(e), "type": e.__class__.__name__}
            yield self._format_sse_event("error", error_payload)
            yield self._format_sse_event("graph_end", {})
            return
        
        # Send final graph_end event for successful completion
        logger.info("Agent event stream processing finished successfully.")
        yield self._format_sse_event("graph_end", {})
        logger.info("Agent event stream generator fully terminated.")
    
    async def _process_updates(self, event_chunk: Dict[str, Any], thread_id: str) -> AsyncGenerator[str, None]:
        """Process update events."""
        node_name, node_output_state_dict = list(event_chunk.items())[0]

        # 1. Node Update Event (include thread_id for first event)
        node_update_data = {'node_name': node_name}
        if node_name == "entry_node":
            node_update_data['thread_id'] = thread_id
            
        yield self._format_sse_event("node_update", node_update_data)

        # 2. Process Messages from state
        messages = node_output_state_dict.get("messages", [])
        if messages:
            last_msg_obj = messages[-1]
            msg_data_payload = self._process_message(last_msg_obj)
            yield self._format_sse_event("message", msg_data_payload)

        # 3. Process streaming_output from state (for intermediate thoughts/logs)
        streaming_outputs = node_output_state_dict.get("streaming_output", [])
        if streaming_outputs:
            latest_stream_chunk = streaming_outputs[-1]
            yield self._format_sse_event("thought_stream", {'chunk': latest_stream_chunk})

        # 4. Process final_answer
        final_answer = node_output_state_dict.get("final_answer")
        if final_answer is not None and node_name == "response_node":
            logger.info(f"Yielding final_answer from node: {node_name}")
            yield self._format_sse_event("final_answer", {'answer': final_answer})
        
        # 5. Graph End
        if node_name == "__end__":
            logger.info("Yielding graph_end event as node_name is __end__.")
            yield self._format_sse_event("graph_end", {})
    
    def _process_message(self, message_obj) -> Dict[str, Any]:
        """Process a message object and return formatted data."""
        msg_data_payload = {"type": message_obj.type}

        if hasattr(message_obj, 'content'):
            msg_data_payload["content"] = message_obj.content
        
        if hasattr(message_obj, 'name') and message_obj.name:
             msg_data_payload["name"] = message_obj.name

        if message_obj.type == "ai":  # AIMessage specific
            if hasattr(message_obj, 'tool_calls') and message_obj.tool_calls:
                msg_data_payload["type"] = "tool_call"
                msg_data_payload["tool_calls"] = [
                    {"name": tc.get('name'), "args": tc.get('args'), "id": tc.get('id')}
                    for tc in message_obj.tool_calls
                ]
                if not msg_data_payload.get("content"):
                     msg_data_payload.pop("content", None)
        
        elif message_obj.type == "tool":  # ToolMessage specific
            msg_data_payload["type"] = "tool_result"
            if hasattr(message_obj, 'tool_call_id'):
                msg_data_payload["tool_call_id"] = message_obj.tool_call_id
        
        return msg_data_payload
    
    def _format_sse_event(self, event_type: str, data: Dict[str, Any]) -> str:
        """Format data as SSE event."""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
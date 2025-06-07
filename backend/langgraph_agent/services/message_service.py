"""
Message service implementation.
Following Single Responsibility Principle (SRP).
"""

import logging
from typing import Dict, Any
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage, HumanMessage

from langgraph_agent.interfaces import IMessageProcessor

logger = logging.getLogger(__name__)


class MessageProcessor(IMessageProcessor):
    """Service for processing messages."""
    
    def process_message(self, message: BaseMessage) -> Dict[str, Any]:
        """Process a message and return formatted data."""
        if isinstance(message, HumanMessage):
            return self._process_human_message(message)
        elif isinstance(message, AIMessage):
            return self._process_ai_message(message)
        elif isinstance(message, ToolMessage):
            return self._process_tool_message(message)
        else:
            logger.warning(f"Unknown message type: {type(message)}")
            return {"type": "unknown", "content": str(message)}
    
    def _process_human_message(self, message: HumanMessage) -> Dict[str, Any]:
        """Process a human message."""
        return {
            "type": "human",
            "content": message.content
        }
    
    def _process_ai_message(self, message: AIMessage) -> Dict[str, Any]:
        """Process an AI message."""
        msg_data = {"type": message.type}
        
        if hasattr(message, 'content'):
            msg_data["content"] = message.content
        
        if hasattr(message, 'name') and message.name:
            msg_data["name"] = message.name

        # Handle tool calls
        if hasattr(message, 'tool_calls') and message.tool_calls:
            msg_data["type"] = "tool_call"
            msg_data["tool_calls"] = [
                {"name": tc.get('name'), "args": tc.get('args'), "id": tc.get('id')}
                for tc in message.tool_calls
            ]
            if not msg_data.get("content"):
                msg_data.pop("content", None)
        
        return msg_data
    
    def _process_tool_message(self, message: ToolMessage) -> Dict[str, Any]:
        """Process a tool message."""
        msg_data = {
            "type": "tool_result",
            "content": message.content
        }
        
        if hasattr(message, 'tool_call_id'):
            msg_data["tool_call_id"] = message.tool_call_id
        
        if hasattr(message, 'name'):
            msg_data["name"] = message.name
            
        return msg_data


class MessageProcessorFactory:
    """Factory for creating message processors."""
    
    @staticmethod
    def create_message_processor() -> MessageProcessor:
        """Create a message processor."""
        return MessageProcessor()
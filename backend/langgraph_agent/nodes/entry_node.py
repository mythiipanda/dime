"""
Entry node implementation.
Following Single Responsibility Principle (SRP).
"""

import logging
from typing import Dict, Any
from langchain_core.messages import HumanMessage

from langgraph_agent.state import AgentState
from langgraph_agent.nodes.base_node import BaseAgentNode

logger = logging.getLogger(__name__)


class EntryNode(BaseAgentNode):
    """Initial node that handles both new conversations and multi-turn interactions."""
    
    def _execute_internal(self, state: AgentState) -> Dict[str, Any]:
        """Execute the entry node logic."""
        user_input = state['input_query']
        
        # Check if this is a continuation of an existing conversation
        existing_messages = state.get('messages', [])
        is_continuation = len(existing_messages) > 0
        
        if is_continuation:
            logger.info(f"Continuing conversation with {len(existing_messages)} existing messages")
            self._write_status("continuing", f"Continuing conversation with new query: {user_input[:100]}...")
        else:
            logger.info("Starting new conversation")
            self._write_status("processing", f"Processing new query: {user_input[:100]}...")
        
        # Always add the new user message to the conversation
        # LangGraph's add_messages will handle appending to existing history
        new_human_message = HumanMessage(content=user_input)
        
        return {
            "messages": [new_human_message],  # This gets added to existing messages by add_messages
            "streaming_output": [f"User: {user_input}"],
            "current_step": self._increment_step(state),
            "agent_scratchpad": state.get('agent_scratchpad', []),
            "tool_outputs": state.get('tool_outputs', [])
        }
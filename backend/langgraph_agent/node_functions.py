"""
Node functions for the LangGraph NBA agent.
Uses the refactored service-based architecture.
"""

from langgraph_agent.state import AgentState
from langgraph_agent.tool_manager import all_tools
# Import from specific modules
from langgraph_agent.nodes.entry_node import EntryNode
from langgraph_agent.services import LLMServiceFactory, PromptServiceFactory
import logging

logger = logging.getLogger(__name__)

# Create service instances
llm_service = LLMServiceFactory.create_gemini_service()
prompt_service = PromptServiceFactory.create_system_prompt_service()

# Create node instances
_entry_node = EntryNode()

# Node functions for LangGraph
def entry_node(state: AgentState) -> dict:
    """Initial node. Handles both new conversations and multi-turn interactions."""
    return _entry_node.execute(state)

# Public LLM interface - use the service's public method instead of private attribute
llm = llm_service.get_llm()

# Exports
__all__ = ['entry_node', 'llm_service', 'prompt_service', 'llm']

logger.info("Node functions loaded successfully using service-based architecture")
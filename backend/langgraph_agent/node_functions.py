"""
Node functions for the LangGraph NBA agent.
Uses the refactored service-based architecture.
"""

from langgraph_agent.state import AgentState
from langgraph_agent.tool_manager import all_tools
# Import from specific modules to avoid name collision with this nodes.py module
from langgraph_agent.nodes.entry_node import EntryNode
from langgraph_agent.nodes.llm_node import LLMNode
from langgraph_agent.nodes.response_node import ResponseNode
from langgraph_agent.services import LLMServiceFactory, PromptServiceFactory
import logging

logger = logging.getLogger(__name__)

# Create service instances
llm_service = LLMServiceFactory.create_gemini_service()
prompt_service = PromptServiceFactory.create_system_prompt_service()

# Bind tools to the LLM service
llm_with_tools = llm_service.bind_tools(all_tools)

# Create node instances
_entry_node = EntryNode()
_llm_node = LLMNode(llm_provider=llm_with_tools, prompt_provider=prompt_service)
_response_node = ResponseNode()

# Node functions for LangGraph
def entry_node(state: AgentState) -> dict:
    """Initial node. Handles both new conversations and multi-turn interactions."""
    return _entry_node.execute(state)

def llm_node(state: AgentState) -> dict:
    """Invokes the LLM with the current message history and bound tools."""
    return _llm_node.execute(state)

def response_node(state: AgentState) -> dict:
    """Formulates a final response."""
    return _response_node.execute(state)

# Public LLM interface - use the service's public method instead of private attribute
llm = llm_service.get_llm()

# Exports
__all__ = ['entry_node', 'llm_node', 'response_node', 'llm', 'llm_with_tools']

logger.info("Node functions loaded successfully using service-based architecture")
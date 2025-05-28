# This file will define the TypedDict states for the Langgraph agent. 

from typing import TypedDict, List, Optional, Annotated
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    Represents the state of the Langgraph agent.
    """
    input_query: str
    messages: Annotated[list, add_messages]
    agent_scratchpad: Optional[List[str]]  # For intermediate thoughts, tool calls, observations
    final_answer: Optional[str]
    # To store outputs from tool calls that need to be processed or returned to the LLM
    tool_outputs: Optional[List[dict]]
    # Name of the tool to be called next, if any
    next_tool_call: Optional[str]
    # Arguments for the next tool call
    next_tool_args: Optional[dict]
    # Accumulates parts of the streamed response for the user
    streaming_output: Optional[List[str]]
    # Current iteration or step count, can be useful for complex flows or retry logic
    current_step: Optional[int]
    # Potentially a list of available tools, could be dynamic based on context or user query
    available_tools: Optional[List[str]] # Or list of Tool objects
    # Error messages from tool execution or other processes
    error_message: Optional[str]
    # Flag to indicate if the agent should route to tool execution next
    should_call_tool: bool 
"""
Data Retrieval Agent for the LangGraph NBA data scientist.
Responsible for identifying and calling appropriate tools to gather raw data.
"""

from typing import Dict, Any, List
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph_agent.state import AgentState
from langgraph_agent.interfaces import ILLMProvider
from langgraph_agent.agents.base_agent import BaseAgent
import logging

logger = logging.getLogger(__name__)

class DataRetrievalAgent(BaseAgent):
    """
    This agent's primary role is to intelligently select and execute data retrieval tools
    (NBA API, web search) based on the user's query and the current state.
    It aims to gather all necessary raw data before passing control to the analysis phase.
    """
    def __init__(self, llm_provider: ILLMProvider):
        self.llm_provider = llm_provider

    def execute(self, state: AgentState) -> Dict[str, Any]:
        """
        Executes the data retrieval logic.
        1. Determines if data retrieval is needed.
        2. Uses LLM to select and call appropriate tools.
        3. Updates the state with tool calls or indicates readiness for analysis.
        """
        logger.info("Executing DataRetrievalAgent...")
        messages = state.get("messages", [])
        input_query = state.get("input_query", "")

        # If this is the first turn or a new query, add the human message
        if not messages or (isinstance(messages[-1], HumanMessage) and messages[-1].content != input_query):
            messages.append(HumanMessage(content=input_query))

        # Invoke LLM to decide on tool calls
        llm_response = self.llm_provider.invoke(messages)
        messages.append(llm_response)

        tool_calls = llm_response.tool_calls
        if tool_calls:
            logger.info(f"DataRetrievalAgent decided to call tools: {tool_calls}")
            # LangGraph's ToolNode will execute these, so we just need to pass them
            # The graph will then route to actual_tool_node
            return {"messages": messages, "should_call_tool": True}
        else:
            logger.info("DataRetrievalAgent did not identify any tools to call. Proceeding to analysis or response.")
            # If no tool calls, it means the LLM thinks it has enough info or needs to respond
            # The graph will route based on tools_condition
            return {"messages": messages, "should_call_tool": False}
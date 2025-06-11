"""
Analytics Agent for the LangGraph NBA data scientist.
Responsible for performing data analysis, transformations, and identifying patterns.
"""

from typing import Dict, Any, List
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph_agent.state import AgentState
from langgraph_agent.interfaces import ILLMProvider
from langgraph_agent.agents.base_agent import BaseAgent
import logging

logger = logging.getLogger(__name__)

class AnalyticsAgent(BaseAgent):
    """
    This agent's primary role is to analyze raw data, perform calculations,
    transformations, and identify patterns using data science tools (e.g., Pandas, Python REPL).
    It aims to derive insights from the gathered data.
    """
    def __init__(self, llm_provider: ILLMProvider):
        self.llm_provider = llm_provider

    def _get_analytics_system_prompt(self) -> str:
        """Get specialized system prompt for analytics phase."""
        return """You are the ANALYTICS AGENT in a specialized NBA data analysis pipeline.

**YOUR ROLE**: Analyze raw NBA data and create insights/visualizations. Your job is to:
1. Process raw NBA data from previous data retrieval
2. Perform calculations, comparisons, and statistical analysis
3. Create visualizations when requested
4. Prepare analytical insights for presentation

**WHEN TO USE TOOLS**:
- Use `python_code_execution` for data processing, calculations, and creating charts/visualizations
- Calculate advanced metrics, efficiency comparisons, per-game averages
- Create matplotlib/seaborn visualizations when requested

**WHEN TO STOP ANALYZING**:
- If you've completed the requested analysis (e.g., comparison done, chart created)
- If you've calculated the key metrics requested in the original query
- If you've successfully created any requested visualizations
- If the analysis addresses the user's question adequately

**CRITICAL**: After completing analysis/visualization, provide a BRIEF summary of what you did and DO NOT call more tools. Let the presentation agent handle the final response formatting.

**AVOID**: Endless analysis loops. Once core analysis is done, stop and summarize your work."""

    def execute(self, state: AgentState) -> Dict[str, Any]:
        """
        Executes the data analysis logic.
        1. Takes raw data (potentially from tool_outputs or messages).
        2. Uses LLM to decide on analytical steps and tool calls (e.g., python_repl_tool, pandas_dataframe_tool).
        3. Updates the state with analytical results or indicates readiness for presentation.
        """
        logger.info("Executing AnalyticsAgent...")
        messages = state.get("messages", [])
        tool_outputs = state.get("tool_outputs", [])

        # Add specialized system prompt for analytics
        from langchain_core.messages import SystemMessage
        analytics_prompt = SystemMessage(content=self._get_analytics_system_prompt())
        
        # Insert system message at the beginning if not already present
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [analytics_prompt] + messages

        # Add tool outputs to messages for LLM context
        for output in tool_outputs:
            # Assuming tool_outputs are structured as {tool_name: output_content}
            # Or if it's from LangGraph's ToolNode, it's already a ToolMessage
            if isinstance(output, ToolMessage):
                messages.append(output)
            else:
                # If not a ToolMessage, convert it for LLM context
                # This might need refinement based on actual tool output structure
                messages.append(AIMessage(content=f"Tool Output: {output}"))

        # The LLM needs to decide what analysis to perform
        llm_response = self.llm_provider.invoke(messages)
        messages.append(llm_response)

        tool_calls = llm_response.tool_calls
        if tool_calls:
            logger.info(f"AnalyticsAgent decided to call tools for analysis: {tool_calls}")
            # The graph will route to actual_tool_node for execution
            return {"messages": messages, "should_call_tool": True}
        else:
            logger.info("AnalyticsAgent did not identify further analytical tools to call. Proceeding to presentation or final response.")
            # If no tool calls, it means the LLM thinks analysis is complete or it's ready to respond
            return {"messages": messages, "should_call_tool": False}
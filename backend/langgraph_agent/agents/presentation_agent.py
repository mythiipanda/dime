"""
Presentation Agent for the LangGraph NBA data scientist.
Responsible for formulating the final, insightful, and well-presented answer,
including narrative and context, and potentially triggering visualizations.
"""

from typing import Dict, Any, List
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph_agent.state import AgentState
from langgraph_agent.interfaces import ILLMProvider
from langgraph_agent.agents.base_agent import BaseAgent
import logging

logger = logging.getLogger(__name__)

class PresentationAgent(BaseAgent):
    """
    This agent's primary role is to synthesize all gathered data and analytical insights
    into a clear, concise, and insightful final answer for the user.
    It also decides if a visualization is needed and triggers the `data_visualization_tool`.
    """
    def __init__(self, llm_provider: ILLMProvider):
        self.llm_provider = llm_provider

    def _get_presentation_system_prompt(self) -> str:
        """Get specialized system prompt for presentation phase."""
        return """You are the PRESENTATION AGENT in a specialized NBA data analysis pipeline.

**YOUR ROLE**: Provide the final response to the user. You must ALWAYS provide a response - never return empty content.

**SIMPLE QUERIES** (greetings, casual conversation):
- Respond naturally and offer to help with NBA analysis
- Example: "Hello! I'm doing well, thank you. How can I assist you with NBA data and analysis today?"

**COMPLEX QUERIES** (after data analysis):
- Review all previous data retrieval and analysis work
- Create a comprehensive, well-formatted final answer
- Present data clearly with proper context and insights
- Mention any visualizations that were created

**WHEN TO USE TOOLS**:
- RARELY - only if you need to create a final summary visualization
- Generally, all analysis should be complete by now

**RESPONSE FORMAT**:
- Use clear, structured formatting with markdown
- Include specific statistics and comparisons
- Provide context for the numbers (e.g., "This is above/below average")
- If visualizations were created, mention them in your response

**CRITICAL**: You MUST always provide a response. Never return empty content. Your response will be the final answer to the user."""

    def execute(self, state: AgentState) -> Dict[str, Any]:
        """
        Executes the presentation logic.
        1. Takes all available information (original query, tool outputs, analytical results).
        2. Uses LLM to formulate the final answer and decide on visualization.
        3. Updates the state with the final answer or a visualization tool call.
        """
        logger.info("Executing PresentationAgent...")
        messages = state.get("messages", [])
        input_query = state.get("input_query", "")
        
        # Add specialized system prompt for presentation
        from langchain_core.messages import SystemMessage
        presentation_prompt = SystemMessage(content=self._get_presentation_system_prompt())
        
        # Insert system message at the beginning if not already present
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [presentation_prompt] + messages
        
        # The LLM needs to see all previous messages, including tool outputs from analysis
        # to formulate the final response.
        
        # Invoke LLM to formulate the final answer or decide on visualization
        llm_response = self.llm_provider.invoke(messages)
        messages.append(llm_response)

        tool_calls = llm_response.tool_calls
        if tool_calls:
            logger.info(f"PresentationAgent decided to call tools (likely visualization): {tool_calls}")
            # The graph will route to actual_tool_node for execution
            return {"messages": messages, "should_call_tool": True}
        else:
            final_answer = llm_response.content if llm_response.content else "I'm ready to help you with NBA data and analysis. Please let me know what you'd like to know!"
            logger.info(f"PresentationAgent formulated final answer: {final_answer}")
            # If no tool calls, it means the LLM is ready to provide the final answer
            return {"messages": messages, "final_answer": final_answer, "should_call_tool": False}
"""
LLM node implementation.
Following Single Responsibility Principle (SRP) and Dependency Inversion Principle (DIP).
"""

import json
import datetime
import logging
from typing import Dict, Any
from langchain_core.messages import AIMessage, SystemMessage

from langgraph_agent.state import AgentState
from langgraph_agent.nodes.base_node import BaseAgentNode
from langgraph_agent.interfaces import ILLMProvider, ISystemPromptProvider

logger = logging.getLogger(__name__)


class LLMNode(BaseAgentNode):
    """Node that invokes the LLM with current message history and bound tools."""
    
    def __init__(self, llm_provider: ILLMProvider, prompt_provider: ISystemPromptProvider, **kwargs):
        """Initialize the LLM node with dependencies."""
        super().__init__(**kwargs)
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider
    
    def _execute_internal(self, state: AgentState) -> Dict[str, Any]:
        """Execute the LLM node logic."""
        current_messages_from_state = state.get('messages', [])
        streaming_log = []
        
        # Prepare dynamic system prompt
        current_season = "2024-25"  # TODO: Make dynamic
        current_date_str = datetime.date.today().strftime("%Y-%m-%d")
        
        self._write_status("preparing", "Preparing system prompt and context...")
        
        system_prompt_content = self.prompt_provider.get_prompt(
            current_season=current_season, 
            current_date=current_date_str
        )
        system_message = SystemMessage(content=system_prompt_content)
        
        # Prepend system message to the history for this LLM call
        messages_for_llm = [system_message] + current_messages_from_state
        
        self._write_status("invoking", f"Invoking LLM with {len(messages_for_llm)} messages...")
        
        logger.info(f"LLM Input Messages (with system prompt): {messages_for_llm}")
        streaming_log.append(
            f"LLM invoking with messages (incl. system prompt): "
            f"{json.dumps([self._message_to_dict(m) for m in messages_for_llm], indent=2)[:300]}..."
        )
        
        try:
            self._write_status("processing", "LLM is analyzing the request...")
            self._write_status("thinking", "🤔 Thinking...")
            
            # Invoke LLM with tools
            ai_response_message = self.llm_provider.invoke(messages_for_llm)
            
            # Diagnostic logging
            logger.info(f"RAW LLM Response Object: {ai_response_message!r}")
            self._log_response_metadata(ai_response_message)
            
            # Process response
            log_content = self._process_ai_response(ai_response_message)
            
            logger.info(f"LLM Output: {log_content}")
            streaming_log.append(f"LLM Output: {log_content}")
            
            self._write_status("processing_complete", "Processing completed, preparing response...")

        except ValueError as e:
            error_msg = f"Invalid input to LLM: {e}"
            logger.error(f"LLM NODE INPUT ERROR: {error_msg}")
            streaming_log.append(error_msg)
            self._write_status("error", f"LLM input error: {str(e)}")
            ai_response_message = AIMessage(
                content=f"Sorry, there was an issue with the input format: {e}"
            )
        except Exception as e:
            error_msg = f"Unexpected error invoking LLM: {e}"
            logger.exception(f"LLM NODE UNEXPECTED ERROR: {error_msg}")
            streaming_log.append(error_msg)
            self._write_status("error", f"LLM error: {str(e)}")
            ai_response_message = AIMessage(
                content=f"Sorry, I encountered an unexpected error: {e}"
            )

        return {
            "messages": [ai_response_message],  # Langgraph will add this to existing messages
            "streaming_output": streaming_log,
            "agent_scratchpad": streaming_log,  # For now, use streaming_log for scratchpad
            "current_step": self._increment_step(state),
            "system_prompt_used": system_prompt_content  # Adding this for debugging/verification
        }
    
    def _message_to_dict(self, message) -> Dict[str, Any]:
        """Convert message to dictionary for logging."""
        try:
            return message.dict()
        except AttributeError:
            return {"type": str(type(message)), "content": str(message)}
    
    def _log_response_metadata(self, ai_response_message) -> None:
        """Log response metadata for diagnostics."""
        if hasattr(ai_response_message, 'response_metadata') and ai_response_message.response_metadata:
            logger.info(f"LLM Response Metadata: {ai_response_message.response_metadata}")
            
            # Look for common error patterns in metadata
            if ai_response_message.response_metadata.get('error'):
                logger.error(f"ERROR in LLM Response Metadata: {ai_response_message.response_metadata['error']}")
            
            if ai_response_message.response_metadata.get('block_reason'):
                logger.warning(
                    f"CONTENT BLOCKED by Gemini. Reason: {ai_response_message.response_metadata.get('block_reason')}, "
                    f"Safety Ratings: {ai_response_message.response_metadata.get('safety_ratings')}"
                )
    
    def _process_ai_response(self, ai_response_message) -> str:
        """Process AI response and write appropriate status."""
        log_content = ai_response_message.content if ai_response_message.content else "[LLM decided to use a tool]"
        
        if hasattr(ai_response_message, 'tool_calls') and ai_response_message.tool_calls:
            log_content += f" Tool calls: {ai_response_message.tool_calls}"
            tool_names = [tc.get('name', 'Unknown') for tc in ai_response_message.tool_calls if isinstance(tc, dict)]
            self._write_status("tool_decision", f"🔧 LLM decided to use tools: {tool_names}")
        else:
            self._write_status("response_ready", "✅ LLM generated a direct response")
        
        return log_content
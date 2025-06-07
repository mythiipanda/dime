"""
Base node implementation.
Following Open/Closed Principle (OCP).
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any
from langgraph_agent.state import AgentState
from langgraph_agent.interfaces import IAgentNode, IStreamWriter
from langgraph_agent.services import StreamWriterService

logger = logging.getLogger(__name__)


class BaseAgentNode(IAgentNode, ABC):
    """Base class for all agent nodes."""
    
    def __init__(self, stream_writer: IStreamWriter = None):
        """Initialize the base node."""
        self.stream_writer = stream_writer or StreamWriterService()
        self.node_name = self.__class__.__name__
    
    def execute(self, state: AgentState) -> Dict[str, Any]:
        """Execute the node with the given state."""
        logger.info(f"Executing {self.node_name}")
        
        try:
            self._write_status("starting", f"Starting {self.node_name}")
            result = self._execute_internal(state)
            self._write_status("completed", f"Completed {self.node_name}")
            return result
        except Exception as e:
            error_msg = f"Error in {self.node_name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._write_status("error", error_msg)
            return self._handle_error(state, e)
    
    @abstractmethod
    def _execute_internal(self, state: AgentState) -> Dict[str, Any]:
        """Internal execution logic to be implemented by subclasses."""
        pass
    
    def _handle_error(self, state: AgentState, error: Exception) -> Dict[str, Any]:
        """Handle errors that occur during node execution."""
        return {
            "error_message": str(error),
            "current_step": state.get('current_step', 0) + 1
        }
    
    def _write_status(self, status: str, message: str) -> None:
        """Write status to stream."""
        try:
            self.stream_writer.write({
                "status": status,
                "step": self.node_name.lower(),
                "message": message
            })
        except Exception as e:
            logger.debug(f"Failed to write status: {e}")
    
    def _increment_step(self, state: AgentState) -> int:
        """Increment and return the current step count."""
        return state.get('current_step', 0) + 1
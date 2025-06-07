"""
Interfaces for the LangGraph agent components.
Following Interface Segregation Principle (ISP) and Dependency Inversion Principle (DIP).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, AsyncGenerator
from langchain_core.messages import BaseMessage
from langgraph_agent.state import AgentState


class IStreamWriter(ABC):
    """Interface for writing stream data."""
    
    @abstractmethod
    def write(self, data: Dict[str, Any]) -> None:
        """Write data to the stream."""
        pass


class ILLMProvider(ABC):
    """Interface for LLM providers."""
    
    @abstractmethod
    def invoke(self, messages: List[BaseMessage]) -> BaseMessage:
        """Invoke the LLM with messages."""
        pass
    
    @abstractmethod
    def bind_tools(self, tools: List[Any]) -> 'ILLMProvider':
        """Bind tools to the LLM."""
        pass


class IAgentNode(ABC):
    """Interface for agent nodes."""
    
    @abstractmethod
    def execute(self, state: AgentState) -> Dict[str, Any]:
        """Execute the node with the given state."""
        pass


class ISystemPromptProvider(ABC):
    """Interface for system prompt providers."""
    
    @abstractmethod
    def get_prompt(self, current_season: str, current_date: str) -> str:
        """Get the system prompt for the given parameters."""
        pass


class IEventStreamProcessor(ABC):
    """Interface for processing event streams."""
    
    @abstractmethod
    async def process_events(
        self, 
        input_query: str, 
        thread_id: Optional[str] = None, 
        user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Process events and yield SSE formatted strings."""
        pass


class IMessageProcessor(ABC):
    """Interface for processing messages."""
    
    @abstractmethod
    def process_message(self, message: BaseMessage) -> Dict[str, Any]:
        """Process a message and return formatted data."""
        pass


class IErrorHandler(ABC):
    """Interface for error handling."""
    
    @abstractmethod
    def handle_error(self, error: Exception) -> Dict[str, Any]:
        """Handle an error and return formatted error data."""
        pass
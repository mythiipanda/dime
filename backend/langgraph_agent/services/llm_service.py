"""
LLM Service implementation.
Following Single Responsibility Principle (SRP).
"""

import logging
from typing import List, Any
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from langgraph_agent.interfaces import ILLMProvider

# Import GEMINI_API_KEY from config
try:
    from config import GEMINI_API_KEY
except ImportError:
    import os
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

logger = logging.getLogger(__name__)


class GeminiLLMService(ILLMProvider):
    """Service for handling Gemini LLM interactions."""
    
    def __init__(self, model: str = "gemini-2.0-flash", streaming: bool = True):
        """Initialize the Gemini LLM service."""
        # Use disable_streaming instead of streaming parameter
        self._llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=GEMINI_API_KEY,
            convert_system_message_to_human=True,
            disable_streaming=not streaming
        )
        logger.info(f"GeminiLLMService initialized with model: {model}")
    
    def invoke(self, messages: List[BaseMessage]) -> BaseMessage:
        """Invoke the LLM with messages."""
        try:
            return self._llm.invoke(messages)
        except Exception as e:
            logger.error(f"Error invoking LLM: {e}")
            raise
    
    def bind_tools(self, tools: List[Any]) -> 'GeminiLLMService':
        """Bind tools to the LLM."""
        bound_llm = self._llm.bind_tools(tools)
        
        # Create a new instance with the bound LLM
        new_service = GeminiLLMService.__new__(GeminiLLMService)
        new_service._llm = bound_llm
        return new_service
    
    def get_llm(self):
        """Get the underlying LLM instance for backward compatibility."""
        return self._llm


class LLMServiceFactory:
    """Factory for creating LLM services."""
    
    @staticmethod
    def create_gemini_service(
        model: str = "gemini-2.0-flash", 
        streaming: bool = True
    ) -> GeminiLLMService:
        """Create a Gemini LLM service."""
        return GeminiLLMService(model=model, streaming=streaming)
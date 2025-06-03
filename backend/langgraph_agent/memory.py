"""
Memory module for multi-turn conversations in LangGraph agent.
Follows Single Responsibility Principle (SRP) and clean code practices.
"""

from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from dataclasses import dataclass
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import uuid
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConversationContext:
    """Represents the context of a conversation thread."""
    thread_id: str
    user_id: Optional[str] = None
    session_data: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


class MemoryInterface(ABC):
    """Abstract interface for memory management."""
    
    @abstractmethod
    def create_thread_config(self, thread_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Create configuration for a conversation thread."""
        pass
    
    @abstractmethod
    def generate_thread_id(self) -> str:
        """Generate a unique thread ID."""
        pass


class ConversationMemoryManager(MemoryInterface):
    """
    Manages conversation memory for multi-turn interactions.
    
    Responsibilities:
    - Generate and manage thread IDs
    - Create proper configurations for LangGraph
    - Handle conversation context
    """
    
    def __init__(self, checkpointer: Optional[InMemorySaver] = None):
        """
        Initialize the memory manager.
        
        Args:
            checkpointer: LangGraph checkpointer for state persistence
        """
        self.checkpointer = checkpointer or InMemorySaver()
        self._active_threads: Dict[str, ConversationContext] = {}
        logger.info("ConversationMemoryManager initialized")
    
    def generate_thread_id(self) -> str:
        """Generate a unique thread ID for a new conversation."""
        thread_id = str(uuid.uuid4())
        logger.debug(f"Generated new thread ID: {thread_id}")
        return thread_id
    
    def create_thread_config(self, thread_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create configuration for a conversation thread.
        
        Args:
            thread_id: Unique identifier for the conversation thread
            user_id: Optional user identifier for cross-thread persistence
            
        Returns:
            Configuration dictionary for LangGraph
        """
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }
        
        if user_id:
            config["configurable"]["user_id"] = user_id
        
        # Track the thread context
        context = ConversationContext(
            thread_id=thread_id,
            user_id=user_id
        )
        self._active_threads[thread_id] = context
        
        logger.debug(f"Created thread config for thread_id: {thread_id}, user_id: {user_id}")
        return config
    
    def get_checkpointer(self) -> InMemorySaver:
        """Get the checkpointer instance."""
        return self.checkpointer
    
    def get_thread_context(self, thread_id: str) -> Optional[ConversationContext]:
        """Get context for a specific thread."""
        return self._active_threads.get(thread_id)
    
    def list_active_threads(self) -> List[str]:
        """List all active thread IDs."""
        return list(self._active_threads.keys())
    
    def cleanup_thread(self, thread_id: str) -> bool:
        """
        Clean up a specific thread from memory.
        
        Args:
            thread_id: Thread to clean up
            
        Returns:
            True if thread was found and removed, False otherwise
        """
        if thread_id in self._active_threads:
            del self._active_threads[thread_id]
            logger.debug(f"Cleaned up thread: {thread_id}")
            return True
        return False


class ChatHistoryProcessor:
    """
    Processes chat history for multi-turn conversations.
    
    Responsibilities:
    - Extract previous messages from state
    - Format messages for frontend consumption
    - Handle message validation
    """
    
    @staticmethod
    def extract_chat_history(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """
        Extract and format chat history from LangGraph messages.
        
        Args:
            messages: List of LangGraph BaseMessage objects
            
        Returns:
            Formatted chat history for frontend
        """
        history = []
        
        for msg in messages:
            if isinstance(msg, HumanMessage):
                history.append({
                    "id": getattr(msg, 'id', str(uuid.uuid4())),
                    "type": "human",
                    "content": msg.content,
                    "timestamp": getattr(msg, 'timestamp', None)
                })
            elif isinstance(msg, AIMessage):
                history.append({
                    "id": getattr(msg, 'id', str(uuid.uuid4())),
                    "type": "ai", 
                    "content": msg.content,
                    "timestamp": getattr(msg, 'timestamp', None),
                    "tool_calls": getattr(msg, 'tool_calls', None)
                })
        
        return history
    
    @staticmethod
    def validate_message_input(content: str) -> bool:
        """
        Validate user message input.
        
        Args:
            content: User message content
            
        Returns:
            True if valid, False otherwise
        """
        if not content or not isinstance(content, str):
            return False
        
        # Basic validation - can be extended
        if len(content.strip()) == 0:
            return False
        
        if len(content) > 10000:  # Reasonable limit
            logger.warning(f"Message too long: {len(content)} characters")
            return False
        
        return True


class MemoryFactory:
    """Factory for creating memory-related objects."""
    
    @staticmethod
    def create_memory_manager() -> ConversationMemoryManager:
        """Create a new ConversationMemoryManager instance."""
        return ConversationMemoryManager()
    
    @staticmethod
    def create_chat_processor() -> ChatHistoryProcessor:
        """Create a new ChatHistoryProcessor instance."""
        return ChatHistoryProcessor()


# Singleton instance for the application
_memory_manager: Optional[ConversationMemoryManager] = None


def get_memory_manager() -> ConversationMemoryManager:
    """
    Get or create the global memory manager instance.
    
    Returns:
        Global ConversationMemoryManager instance
    """
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryFactory.create_memory_manager()
        logger.info("Created global memory manager instance")
    return _memory_manager


def get_chat_processor() -> ChatHistoryProcessor:
    """
    Get a chat history processor instance.
    
    Returns:
        ChatHistoryProcessor instance
    """
    return MemoryFactory.create_chat_processor()
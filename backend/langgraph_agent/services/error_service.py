"""
Error service implementation.
Following Single Responsibility Principle (SRP).
"""

import logging
from typing import Dict, Any, Optional
from langgraph_agent.interfaces import IErrorHandler

logger = logging.getLogger(__name__)


class ErrorHandler(IErrorHandler):
    """Service for handling errors."""
    
    def handle_error(self, error: Exception) -> Dict[str, Any]:
        """Handle an error and return formatted error data."""
        error_type = error.__class__.__name__
        error_message = str(error)
        
        logger.error(f"Handling error: {error_type} - {error_message}", exc_info=True)
        
        # Categorize errors and provide appropriate responses
        if isinstance(error, ConnectionError):
            return self._handle_connection_error(error_message)
        elif isinstance(error, TimeoutError):
            return self._handle_timeout_error(error_message)
        elif isinstance(error, ValueError):
            return self._handle_validation_error(error_message)
        else:
            return self._handle_generic_error(error_type, error_message)
    
    def _handle_connection_error(self, message: str) -> Dict[str, Any]:
        """Handle connection errors."""
        return {
            "type": "connection_error",
            "message": "Connection error occurred. Please check your network and try again.",
            "details": message,
            "retry_suggested": True
        }
    
    def _handle_timeout_error(self, message: str) -> Dict[str, Any]:
        """Handle timeout errors."""
        return {
            "type": "timeout_error",
            "message": "Request timed out. Please try again.",
            "details": message,
            "retry_suggested": True
        }
    
    def _handle_validation_error(self, message: str) -> Dict[str, Any]:
        """Handle validation errors."""
        return {
            "type": "validation_error",
            "message": "Invalid input provided. Please check your request and try again.",
            "details": message,
            "retry_suggested": False
        }
    
    def _handle_generic_error(self, error_type: str, message: str) -> Dict[str, Any]:
        """Handle generic errors."""
        return {
            "type": error_type,
            "message": "An unexpected error occurred. Please try again.",
            "details": message,
            "retry_suggested": True
        }


class ErrorHandlerFactory:
    """Factory for creating error handlers."""
    
    @staticmethod
    def create_error_handler() -> ErrorHandler:
        """Create an error handler."""
        return ErrorHandler()
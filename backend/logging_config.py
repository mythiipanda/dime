"""
Handles the logging configuration for the backend application.
Allows setting up a root logger with a specified level and format,
integrating with the application's central configuration.
"""
import logging
import sys
from typing import Optional

from backend.config import settings # Import application settings

# Default log format
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

def setup_logging(log_level_override: Optional[str] = None) -> logging.Logger:
    """
    Sets up the root logging configuration for the application.

    The logging level is determined by `log_level_override` if provided,
    otherwise it defaults to the `LOG_LEVEL` specified in the application settings.

    Args:
        log_level_override (Optional[str]): A string representation of the desired
            logging level (e.g., "DEBUG", "INFO"). If None, uses settings.LOG_LEVEL.

    Returns:
        logging.Logger: The configured root logger instance.
    """
    effective_log_level_str = log_level_override if log_level_override else settings.LOG_LEVEL
    
    # Convert string log level to logging module's integer constant
    numeric_level = logging.getLevelName(effective_log_level_str.upper())
    if not isinstance(numeric_level, int):
        logging.warning(
            f"Invalid log level string: '{effective_log_level_str}'. Defaulting to INFO."
        )
        numeric_level = logging.INFO

    # Get the root logger
    root_logger = logging.getLogger()
    
    # Clear any existing handlers to avoid duplicate logs if called multiple times
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    root_logger.setLevel(numeric_level)

    # Create console handler and set level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)

    # Create formatter
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    # Add formatter to console handler
    console_handler.setFormatter(formatter)

    # Add console handler to the root logger
    root_logger.addHandler(console_handler)
    
    logging.info(f"Logging setup complete. Level set to: {logging.getLevelName(root_logger.getEffectiveLevel())}")
    return root_logger
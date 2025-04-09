"""Logging configuration for the application."""
import logging
import sys

def setup_logging(level=logging.INFO):
    """Set up logging configuration."""
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # Create console handler and set level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Add formatter to console handler
    console_handler.setFormatter(formatter)

    # Add console handler to logger
    logger.addHandler(console_handler)

    return logger
"""
Manages application configuration settings using Pydantic's BaseSettings.
Loads settings from environment variables and a .env file located in the backend directory.
Provides a centralized `settings` object for use throughout the application.
"""
import os
import datetime
import logging
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Initialize logger for this module
logger = logging.getLogger(__name__)

# Helper function for dynamic default NBA season
def get_default_nba_season() -> str:
    """
    Calculates the current NBA season string (e.g., "2023-24").
    The NBA season typically starts in October and concludes mid-year.
    """
    now = datetime.datetime.now(datetime.timezone.utc) # Use timezone-aware now
    current_year = now.year
    # If current month is October or later, the season started this year.
    # Otherwise, the current season started last year.
    if now.month >= 10:
        return f"{current_year}-{str(current_year + 1)[-2:]}"
    else:
        return f"{current_year - 1}-{str(current_year)[-2:]}"

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.
    Defines the schema for all configurable parameters.
    """
    # --- Secrets & API Keys ---
    GOOGLE_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None  # Consider for deprecation if fully on Gemini
    GEMINI_API_KEY: Optional[str] = None  # If None and GOOGLE_API_KEY is set, will default to GOOGLE_API_KEY

    # --- Agent & AI Model Configuration ---
    AGENT_MODEL_ID: str = "gemini-2.0-flash" # Updated default
    SUGGESTION_MODEL_ID: str = "gemini-2.0-flash-lite" # Updated default
    AGENT_DEBUG_MODE: bool = False

    # --- Database & Storage ---
    STORAGE_DB_FILE: str = "agno_storage.db"  # Path relative to backend root or absolute path
    CHROMA_DB_NBA_AGENT: str = "./chroma_db_nba_agent_kb"  # Default path for the KB ChromaDB
    KB_COLLECTION_NAME: str = "nba_analyzer_global_kb" # Default collection name for the main KB

    # --- Application Behavior ---
    LOG_LEVEL: str = "INFO"  # Valid levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
    ENVIRONMENT: str = "development"  # e.g., development, staging, production
    CURRENT_NBA_SEASON: str = get_default_nba_season() # Default, can be overridden by env var
    DEFAULT_TIMEOUT_SECONDS: int = 30
    DEFAULT_LRU_CACHE_SIZE: int = 128 # Default size for LRU caches
    HEADSHOT_BASE_URL: str = "https://ak-static.cms.nba.com/wp-content/uploads/headshots/nba/latest/260x190"

    # --- CORS Configuration ---
    # Comma-separated string of allowed origins, e.g., "http://localhost:3000,https://yourdomain.com"
    CORS_ALLOWED_ORIGINS_STR: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def CORS_ALLOWED_ORIGINS(self) -> List[str]:
        """Parses the CORS_ALLOWED_ORIGINS_STR into a list of origins."""
        if not self.CORS_ALLOWED_ORIGINS_STR:
            return []
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS_STR.split(",") if origin.strip()]

    # Pydantic settings configuration
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'), # More robust path to .env
        env_file_encoding='utf-8',
        extra='ignore',  # Ignore extra fields from environment variables
        case_sensitive=False # Environment variable names are case-insensitive
    )

# Instantiate settings once for the application to use
settings = Settings()

# Post-processing: Default GEMINI_API_KEY to GOOGLE_API_KEY if GOOGLE_API_KEY is set and GEMINI_API_KEY is not
if settings.GOOGLE_API_KEY and not settings.GEMINI_API_KEY:
    settings.GEMINI_API_KEY = settings.GOOGLE_API_KEY # Directly assign to the instance
    logger.info("GEMINI_API_KEY was not set, defaulting to GOOGLE_API_KEY.")

# Log some important configurations at startup
logger.info(f"Application Environment: {settings.ENVIRONMENT}")
logger.info(f"Log Level: {settings.LOG_LEVEL}")
logger.info(f"Current NBA Season (determined): {settings.CURRENT_NBA_SEASON}") # Log the determined value
logger.info(f"Agent Model ID: {settings.AGENT_MODEL_ID}")
logger.info(f"CORS Allowed Origins: {settings.CORS_ALLOWED_ORIGINS}")

# Enhanced API key logging/warnings
if not settings.GEMINI_API_KEY and not settings.OPENAI_API_KEY: # Simplified check if GOOGLE_API_KEY is only for Gemini fallback
    logger.warning(
        "Neither GEMINI_API_KEY nor OPENAI_API_KEY is configured. "
        "AI-related features may not function correctly."
    )
elif not settings.GEMINI_API_KEY: # Specific warning if Gemini is intended primary but missing
     logger.warning(
        "GEMINI_API_KEY is not configured. AI features relying on Gemini may not work, "
        "even if GOOGLE_API_KEY (used as fallback) or OPENAI_API_KEY is set."
    )

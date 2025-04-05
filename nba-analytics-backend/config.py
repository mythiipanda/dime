# nba-analytics-backend/config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- API Keys ---
# Example: GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# Keep API key loading separate or manage via environment variables directly in deployment

# --- General Settings ---
DEFAULT_TIMEOUT: int = 15 # Increased default based on game_tools
CURRENT_SEASON: str = "2024-25"
MAX_GAMES_TO_RETURN: int = 20 # Limit for game finder results

# --- Agent Settings ---
AGENT_MODEL_ID: str = "gemini-2.0-flash" # Model used by agents
STORAGE_DB_FILE: str = "agno_storage.db" # Local SQLite DB for agent sessions
AGENT_DEBUG_MODE: bool = True # Enable debug logging for agents

# --- Logging ---
# Basic logging config can be set up here if needed, or handled in main.py/app entry point
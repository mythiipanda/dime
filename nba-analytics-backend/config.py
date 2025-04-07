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
AGENT_MODEL_ID: str = "google/gemini-2.0-flash-exp:free" # Model used by agents (via OpenRouter)
STORAGE_DB_FILE: str = "agno_storage.db" # Local SQLite DB for agent sessions
AGENT_DEBUG_MODE: bool = True # Enable debug logging for agents

# --- Logging ---
LOG_FILENAME: str = "backend_app.log"
LOG_FILE_MODE: str = 'a' # Append mode for log file
# Basic logging config can be set up here if needed, or handled in main.py/app entry point

# --- CORS ---
CORS_ALLOWED_ORIGINS: list[str] = [
    "http://localhost:3000", # Frontend dev server
    "http://localhost",      # General localhost access
]

# --- API Settings ---
SUPPORTED_FETCH_TARGETS: list[str] = [
    "player_info",
    "player_gamelog",
    "team_info",
    "player_career_stats",
    "find_games"
]

# --- Server Settings ---
UVICORN_HOST: str = "127.0.0.1"
UVICORN_PORT: int = 8000

# --- External URLs ---
HEADSHOT_BASE_URL: str = "https://cdn.nba.com/headshots/nba/latest/260x190/"

# --- Search Settings ---
DEFAULT_PLAYER_SEARCH_LIMIT: int = 10
MIN_PLAYER_SEARCH_LENGTH: int = 2

# --- Caching ---
# TODO: Implement a caching strategy (e.g., using Redis or in-memory cache like cachetools)
#       to reduce redundant API calls, especially for static data (player IDs, team IDs)
#       and potentially for results from nba_api endpoints with appropriate TTLs.
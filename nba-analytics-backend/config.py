import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- API Keys ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- NBA API Settings ---
# Consider adding more specific timeouts if needed (e.g., static vs endpoint)
DEFAULT_TIMEOUT = 10 # Default timeout for nba_api calls in seconds
CURRENT_SEASON = "2024-25" # TODO: Make this dynamic or easily updatable

# --- Agent/Model Settings ---
AGENT_MODEL = "gemini-2.0-flash-latest" # Or your preferred model

# --- Logging ---
LOG_LEVEL = "INFO" # e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL

# --- Other Constants ---
# Add other shared constants here as needed

# --- Validation ---
if not GOOGLE_API_KEY:
    print("Warning: GOOGLE_API_KEY environment variable not set.")
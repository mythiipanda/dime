import os
from dotenv import load_dotenv
from api_tools.errors import Errors as ErrorMessages

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    load_dotenv()

# API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Agent-related configs
AGENT_MODEL_ID = "gemini-2.0-flash"
STORAGE_DB_FILE = os.getenv("STORAGE_DB_FILE", "agno_storage.db")
AGENT_DEBUG_MODE = os.getenv("AGENT_DEBUG_MODE", "false").lower() == "true"

# Constants
CURRENT_SEASON = "2024-25"
DEFAULT_TIMEOUT = 30
HEADSHOT_BASE_URL = "https://ak-static.cms.nba.com/wp-content/uploads/headshots/nba/latest/260x190"
DEFAULT_PLAYER_SEARCH_LIMIT = 10
MIN_PLAYER_SEARCH_LENGTH = 3
MAX_SEARCH_RESULTS = 25  # Maximum number of results to return from any search
MAX_GAMES_TO_RETURN = 50
MAX_PLAYERS_TO_RETURN = 25

# Supported fetch targets
SUPPORTED_FETCH_TARGETS = [
    "traditional",
    "advanced",
    "fourfactors",
    "misc",
    "scoring",
    "usage",
    "defense"
]

# Supported search targets
SUPPORTED_SEARCH_TARGETS = [
    "players",
    "teams",
    "games"
]

# CORS allowed origins
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Validation for environment variables
if not GOOGLE_API_KEY:
    print("Warning: GOOGLE_API_KEY not found in environment variables. AI features may not work.")
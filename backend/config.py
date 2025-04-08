import os
from dotenv import load_dotenv

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    load_dotenv()

# API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Agent-related configs
AGENT_MODEL_ID = "gemini-2.0-flash"
STORAGE_DB_FILE = os.getenv("STORAGE_DB_FILE", "agno_storage.db")
AGENT_DEBUG_MODE = os.getenv("AGENT_DEBUG_MODE", "false").lower() == "true"

# Constants
CURRENT_SEASON = "2024-25"
DEFAULT_TIMEOUT = 10
HEADSHOT_BASE_URL = "https://ak-static.cms.nba.com/wp-content/uploads/headshots/nba/latest/260x190/"
DEFAULT_PLAYER_SEARCH_LIMIT = 10
MIN_PLAYER_SEARCH_LENGTH = 3
MAX_GAMES_TO_RETURN = 20

# Supported fetch targets
SUPPORTED_FETCH_TARGETS = [
    "player_info",
    "player_gamelog",
    "team_info",
    "player_career_stats",
    "find_games"
]

# CORS allowed origins
CORS_ALLOWED_ORIGINS = ["*"]  # Change to specific origins in production

# Error Messages
class ErrorMessages:
    # Player-related errors
    PLAYER_NOT_FOUND = "Player '{name}' not found."
    PLAYER_NAME_EMPTY = "Player name cannot be empty."
    PLAYER_CAREER_STATS_API = "API error fetching career stats for {name}: {error}"
    PLAYER_CAREER_STATS_PROCESSING = "Failed to process career stats data from API for {name}."
    PLAYER_CAREER_STATS_UNEXPECTED = "Unexpected error processing career stats request for {name}: {error}"
    PLAYER_GAMELOG_API = "API error fetching game log for {name} ({season}): {error}"
    PLAYER_GAMELOG_PROCESSING = "Failed to process game log data from API for {name} ({season})."
    PLAYER_GAMELOG_UNEXPECTED = "Unexpected error processing game log request for {name} ({season}): {error}"
    PLAYER_INFO_API = "API error fetching details for {name}: {error}"
    PLAYER_INFO_PROCESSING = "Failed to process data from API for {name}."
    PLAYER_INFO_UNEXPECTED = "Unexpected error processing request for {name}: {error}"
    PLAYER_AWARDS_API = "API error fetching awards for {name}: {error}"
    PLAYER_AWARDS_PROCESSING = "Failed to process awards data from API for {name}." # Currently unused in logic but good to have
    PLAYER_AWARDS_UNEXPECTED = "Unexpected error processing awards request for {name}: {error}"
    
    # Team-related errors
    TEAM_NOT_FOUND = "Team '{identifier}' not found."
    TEAM_IDENTIFIER_EMPTY = "Team identifier cannot be empty."
    TEAM_API = "API error fetching {data_type} for team ID {identifier}: {error}"
    TEAM_PROCESSING = "DataFrame processing failed for {data_type}, Team ID {identifier}"
    TEAM_ALL_FAILED = "Failed to fetch any data for team '{identifier}' ({season}). Errors: {errors}"
    TEAM_UNEXPECTED = "Unexpected error processing team info/roster request for {identifier} ({season}): {error}"
    
    # Game-related errors
    FIND_GAMES_API = "API error fetching games: {error}"
    FIND_GAMES_PROCESSING = "Failed to process game data from API."
    FIND_GAMES_UNEXPECTED = "Unexpected error processing find games request: {error}"
    GAME_ID_EMPTY = "Game ID cannot be empty."
    INVALID_GAME_ID_FORMAT = "Invalid Game ID format: {game_id}. Expected 10 digits."
    BOXSCORE_API = "API error fetching box score for game ID {game_id}: {error}"
    BOXSCORE_PROCESSING = "Failed to process box score data from API for game ID {game_id}."
    BOXSCORE_UNEXPECTED = "Unexpected error processing box score request for game ID {game_id}: {error}"
    PLAYBYPLAY_API = "API error fetching play-by-play for game ID {game_id}: {error}"
    PLAYBYPLAY_PROCESSING = "Failed to process play-by-play data from API for game ID {game_id}."
    PLAYBYPLAY_UNEXPECTED = "Unexpected error processing play-by-play request for game ID {game_id}: {error}"
    
    # General validation errors
    INVALID_SEASON_FORMAT = "Invalid season format: {season}. Expected YYYY-YY."
    INVALID_PLAYER_OR_TEAM = "Invalid player_or_team value. Must be 'P' for Player or 'T' for Team."
    MISSING_PLAYER_ID = "player_id is required when player_or_team='P'."
    MISSING_TEAM_ID = "team_id is required when player_or_team='T'."

    # League-related errors
    STANDINGS_API = "API error fetching standings for season {season}: {error}"
    STANDINGS_PROCESSING = "Failed to process standings data from API for season {season}."
    STANDINGS_UNEXPECTED = "Unexpected error processing standings request for season {season}: {error}"
    INVALID_DATE_FORMAT = "Invalid date format: {date}. Expected YYYY-MM-DD."
    SCOREBOARD_API = "API error fetching scoreboard for date {date}: {error}"
    SCOREBOARD_PROCESSING = "Failed to process scoreboard data from API for date {date}."
    SCOREBOARD_UNEXPECTED = "Unexpected error processing scoreboard request for date {date}: {error}"
    INVALID_DRAFT_YEAR_FORMAT = "Invalid draft year format: {year}. Expected YYYY."
    DRAFT_HISTORY_API = "API error fetching draft history for year {year}: {error}"
    DRAFT_HISTORY_PROCESSING = "Failed to process draft history data from API for year {year}."
    DRAFT_HISTORY_UNEXPECTED = "Unexpected error processing draft history request for year {year}: {error}"
    INVALID_STAT_CATEGORY = "Invalid stat category provided: {stat}."
    LEAGUE_LEADERS_API = "API error fetching league leaders for {stat}, season {season}: {error}"
    LEAGUE_LEADERS_PROCESSING = "Failed to process league leaders data from API for {stat}, season {season}."
    LEAGUE_LEADERS_UNEXPECTED = "Unexpected error processing league leaders request for {stat}, season {season}: {error}"

# Validation for environment variables
if not GOOGLE_API_KEY:
    print("Warning: GOOGLE_API_KEY not found in environment variables. AI features may not work.")
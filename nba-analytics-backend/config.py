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

# Constants
CURRENT_SEASON = "2024-25"
DEFAULT_TIMEOUT = 10
HEADSHOT_BASE_URL = "https://ak-static.cms.nba.com/wp-content/uploads/headshots/nba/latest/260x190/"
DEFAULT_PLAYER_SEARCH_LIMIT = 10
MIN_PLAYER_SEARCH_LENGTH = 3

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
    
    # General validation errors
    INVALID_SEASON_FORMAT = "Invalid season format: {season}. Expected YYYY-YY."
    INVALID_PLAYER_OR_TEAM = "Invalid player_or_team value. Must be 'P' for Player or 'T' for Team."
    MISSING_PLAYER_ID = "player_id is required when player_or_team='P'."
    MISSING_TEAM_ID = "team_id is required when player_or_team='T'."

# Validation for environment variables
if not GOOGLE_API_KEY:
    print("Warning: GOOGLE_API_KEY not found in environment variables. AI features may not work.")
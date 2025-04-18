import os
from dotenv import load_dotenv

# Define ErrorMessages directly here
class Errors:
    # Generic Errors
    INVALID_SEASON_FORMAT = "Invalid season format: '{season}'. Expected YYYY-YY (e.g., 2023-24)."
    REQUEST_TIMEOUT = "Request timed out after {timeout} seconds."
    API_ERROR = "NBA API request failed: {error}"
    PROCESSING_ERROR = "Failed to process data: {error}"
    UNEXPECTED_ERROR = "An unexpected error occurred: {error}"
    DATA_NOT_FOUND = "No data found for the specified criteria."

    # Player Errors
    PLAYER_NAME_EMPTY = "Player name cannot be empty."
    PLAYER_ID_EMPTY = "Player ID cannot be empty."
    INVALID_PLAYER_ID_FORMAT = "Invalid player ID format: '{player_id}'. Expected digits only."
    PLAYER_NOT_FOUND = "Player '{name}' not found."
    PLAYER_INFO_API = "API error fetching player info for {name}: {error}"
    PLAYER_INFO_PROCESSING = "Failed to process player info for {name}."
    PLAYER_INFO_UNEXPECTED = "Unexpected error fetching player info for {name}: {error}"
    PLAYER_GAMELOG_API = "API error fetching gamelog for {name} (Season: {season}): {error}"
    PLAYER_GAMELOG_PROCESSING = "Failed to process gamelog for {name} (Season: {season})."
    PLAYER_GAMELOG_UNEXPECTED = "Unexpected error fetching gamelog for {name} (Season: {season}): {error}"
    PLAYER_CAREER_STATS_API = "API error fetching career stats for {name}: {error}"
    PLAYER_CAREER_STATS_PROCESSING = "Failed to process career stats for {name}."
    PLAYER_CAREER_STATS_UNEXPECTED = "Unexpected error fetching career stats for {name}: {error}"
    PLAYER_AWARDS_API = "API error fetching awards for {name}: {error}"
    PLAYER_AWARDS_PROCESSING = "Failed to process awards for {name}."
    PLAYER_AWARDS_UNEXPECTED = "Unexpected error fetching awards for {name}: {error}"
    PLAYER_SHOTCHART_API = "API error fetching shot chart for {name}: {error}"
    PLAYER_SHOTCHART_PROCESSING = "Failed to process shot chart data for {name}."
    PLAYER_SHOTCHART_UNEXPECTED = "Unexpected error fetching shot chart for {name}: {error}"
    PLAYER_DEFENSE_API = "API error fetching defense stats for {name}: {error}"
    PLAYER_DEFENSE_PROCESSING = "Failed to process defense stats for {name}."
    PLAYER_DEFENSE_UNEXPECTED = "Unexpected error fetching defense stats for {name}: {error}"
    PLAYER_CLUTCH_API = "API error fetching clutch stats for {name}: {error}"
    PLAYER_CLUTCH_PROCESSING = "Failed to process clutch stats for {name}."
    PLAYER_CLUTCH_UNEXPECTED = "Unexpected error fetching clutch stats for {name}: {error}"
    PLAYER_PASSING_API = "API error fetching passing stats for {name}: {error}"
    PLAYER_PASSING_PROCESSING = "Failed to process passing stats for {name}."
    PLAYER_PASSING_UNEXPECTED = "Unexpected error fetching passing stats for {name}: {error}"
    PLAYER_REBOUNDING_API = "API error fetching rebounding stats for {name}: {error}"
    PLAYER_REBOUNDING_PROCESSING = "Failed to process rebounding stats for {name}."
    PLAYER_REBOUNDING_UNEXPECTED = "Unexpected error fetching rebounding stats for {name}: {error}"
    PLAYER_SHOTS_TRACKING_API = "API error fetching shot tracking stats for player ID {player_id}: {error}"
    PLAYER_SHOTS_TRACKING_PROCESSING = "Failed to process shot tracking stats for player ID {player_id}."
    PLAYER_SHOTS_TRACKING_UNEXPECTED = "Unexpected error fetching shot tracking stats for player ID {player_id}: {error}"
    PLAYER_ID_REQUIRED = "player_id is required when searching by player."

    # Player Profile Errors (Added)
    PLAYER_PROFILE_API = "API error fetching player profile for {name}: {error}"
    PLAYER_PROFILE_PROCESSING = "Failed to process essential profile data for {name}"
    PLAYER_PROFILE_UNEXPECTED = "Unexpected error fetching player profile for {name}: {error}"

    # Team Errors
    TEAM_IDENTIFIER_EMPTY = "Team identifier (name, abbreviation, or ID) cannot be empty."
    TEAM_NOT_FOUND = "Team '{identifier}' not found."
    TEAM_API = "API error fetching {data_type} for team {identifier}: {error}"
    TEAM_PROCESSING = "Failed to process {data_type} for team {identifier}."
    TEAM_UNEXPECTED = "Unexpected error fetching team data for {identifier} (Season: {season}): {error}"
    TEAM_ALL_FAILED = "Failed to fetch any data (info, ranks, roster, coaches) for team {identifier} (Season: {season}). Errors: {errors}"
    TEAM_ID_REQUIRED = "team_id is required when searching by team."
    TEAM_PASSING_API = "API error fetching passing stats for team {identifier}: {error}"
    TEAM_PASSING_PROCESSING = "Failed to process passing stats for team {identifier}."
    TEAM_PASSING_UNEXPECTED = "Unexpected error fetching passing stats for team {identifier}: {error}"
    TEAM_SHOOTING_API = "API error fetching shooting stats for team {identifier}: {error}"
    TEAM_SHOOTING_PROCESSING = "Failed to process shooting stats for team {identifier}."
    TEAM_SHOOTING_UNEXPECTED = "Unexpected error fetching shooting stats for team {identifier}: {error}"
    TEAM_REBOUNDING_API = "API error fetching rebounding stats for team {identifier}: {error}"
    TEAM_REBOUNDING_PROCESSING = "Failed to process rebounding stats for team {identifier}."
    TEAM_REBOUNDING_UNEXPECTED = "Unexpected error fetching rebounding stats for team {identifier}: {error}"

    # Game Errors
    GAME_ID_EMPTY = "Game ID cannot be empty."
    INVALID_GAME_ID_FORMAT = "Invalid game ID format: '{game_id}'. Expected 10 digits."
    GAME_NOT_FOUND = "Game with ID '{game_id}' not found."
    BOXSCORE_API = "API error fetching boxscore for game {game_id}: {error}"
    BOXSCORE_ADVANCED_API = "API error fetching advanced boxscore for game {game_id}: {error}"
    BOXSCORE_FOURFACTORS_API = "API error fetching four factors boxscore for game {game_id}: {error}"
    BOXSCORE_USAGE_API = "API error fetching usage boxscore for game {game_id}: {error}"
    BOXSCORE_DEFENSIVE_API = "API error fetching defensive boxscore for game {game_id}: {error}"
    WINPROBABILITY_API = "API error fetching win probability for game {game_id}: {error}"
    PLAYBYPLAY_API = "API error fetching play-by-play for game {game_id}: {error}"
    SHOTCHART_API = "API error fetching shot chart for game {game_id}: {error}"
    GAME_UNEXPECTED = "Unexpected error fetching data for game {game_id}: {error}"

    # League Errors
    LEAGUE_STANDINGS_API = "API error fetching league standings for season {season}: {error}"
    LEAGUE_STANDINGS_PROCESSING = "Failed to process league standings for season {season}."
    LEAGUE_STANDINGS_UNEXPECTED = "Unexpected error fetching league standings for season {season}: {error}"
    LEAGUE_SCOREBOARD_API = "API error fetching scoreboard for date {game_date}: {error}"
    LEAGUE_SCOREBOARD_UNEXPECTED = "Unexpected error fetching scoreboard for date {game_date}: {error}"
    DRAFT_HISTORY_API = "API error fetching draft history for year {year}: {error}"
    DRAFT_HISTORY_UNEXPECTED = "Unexpected error fetching draft history for year {year}: {error}"
    LEAGUE_LEADERS_API = "API error fetching league leaders for {stat} (Season: {season}): {error}"
    LEAGUE_LEADERS_UNEXPECTED = "Unexpected error fetching league leaders for {stat} (Season: {season}): {error}"
    LEAGUE_GAMES_API = "API error fetching league games: {error}"
    LEAGUE_GAMES_UNEXPECTED = "Unexpected error fetching league games: {error}"

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

# Player Profile Errors (New)
PLAYER_PROFILE_API = "API error fetching player profile for {name}: {error}"
PLAYER_PROFILE_PROCESSING = "Failed to process essential profile data for {name}"
PLAYER_PROFILE_UNEXPECTED = "Unexpected error fetching player profile for {name}: {error}"

# Team Errors
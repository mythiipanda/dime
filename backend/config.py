import os
from dotenv import load_dotenv
import datetime # For CURRENT_SEASON dynamic calculation attempt
import logging # Import logging module

# Initialize logger for this module at the top
logger = logging.getLogger(__name__)

# --- Error Message Constants ---
class Errors:
    # Generic Errors
    INVALID_SEASON_FORMAT = "Invalid season format: '{season}'. Expected YYYY-YY (e.g., 2023-24)."
    REQUEST_TIMEOUT = "Request timed out after {timeout} seconds."
    API_ERROR = "NBA API request failed: {error}" # General NBA API error
    PROCESSING_ERROR = "Failed to process data: {error}"
    UNEXPECTED_ERROR = "An unexpected error occurred: {error}"
    DATA_NOT_FOUND = "No data found for the specified criteria."
    INVALID_DATE_FORMAT = "Invalid date format: '{date}'. Expected YYYY-MM-DD."
    MISSING_REQUIRED_PARAMS = "Missing required parameters for the request: {missing_params}"
    TEAM_ID_NOT_FOUND = "Could not determine Team ID for identifier '{identifier}'."
    EMPTY_SEARCH_QUERY = "Search query cannot be empty."
    SEARCH_QUERY_TOO_SHORT = "Search query must be at least {min_length} characters long."
    JSON_PROCESSING_ERROR = "Internal server error: Invalid data format from an underlying service."
    SSE_GENERATION_ERROR = "Error during SSE stream generation: {error_details}"
    TOPIC_EMPTY = "Research topic cannot be empty."
    PROMPT_SUGGESTION_ERROR = "Failed to generate prompt suggestions due to an internal error."
    UNSUPPORTED_FETCH_TARGET = "Unsupported fetch target: '{target}'. Supported targets are: {supported_targets}."
    UNSUPPORTED_SEARCH_TARGET = "Unsupported search target: '{target}'. Supported targets are: {supported_targets}."

    # Player Errors
    PLAYER_NAME_EMPTY = "Player name cannot be empty."
    PLAYER_ID_EMPTY = "Player ID cannot be empty."
    INVALID_PLAYER_ID_FORMAT = "Invalid player ID format: '{player_id}'. Expected digits only."
    PLAYER_NOT_FOUND = "Player '{identifier}' not found."
    PLAYER_INFO_API = "API error fetching player info for {identifier}: {error}"
    PLAYER_INFO_PROCESSING = "Failed to process player info for {identifier}."
    PLAYER_INFO_UNEXPECTED = "Unexpected error fetching player info for {identifier}: {error}"
    PLAYER_GAMELOG_API = "API error fetching gamelog for {identifier} (Season: {season}): {error}"
    PLAYER_GAMELOG_PROCESSING = "Failed to process gamelog for {identifier} (Season: {season})."
    PLAYER_GAMELOG_UNEXPECTED = "Unexpected error fetching gamelog for {identifier} (Season: {season}): {error}"
    PLAYER_CAREER_STATS_API = "API error fetching career stats for {identifier}: {error}"
    PLAYER_CAREER_STATS_PROCESSING = "Failed to process career stats for {identifier}."
    PLAYER_CAREER_STATS_UNEXPECTED = "Unexpected error fetching career stats for {identifier}: {error}"
    PLAYER_AWARDS_API = "API error fetching awards for {identifier}: {error}"
    PLAYER_AWARDS_PROCESSING = "Failed to process awards for {identifier}."
    PLAYER_AWARDS_UNEXPECTED = "Unexpected error fetching awards for {identifier}: {error}"
    PLAYER_SHOTCHART_API = "API error fetching shot chart for {identifier} (Season: {season}): {error}"
    PLAYER_SHOTCHART_PROCESSING = "Failed to process shot chart data for {identifier} (Season: {season})."
    PLAYER_SHOTCHART_UNEXPECTED = "Unexpected error fetching shot chart for {identifier} (Season: {season}): {error}"
    PLAYER_DEFENSE_API = "API error fetching defense stats for {identifier} (Season: {season}): {error}"
    PLAYER_DEFENSE_PROCESSING = "Failed to process defense stats for {identifier} (Season: {season})."
    PLAYER_DEFENSE_UNEXPECTED = "Unexpected error fetching defense stats for {identifier} (Season: {season}): {error}"
    PLAYER_CLUTCH_API = "API error fetching clutch stats for {identifier} (Season: {season}): {error}"
    PLAYER_CLUTCH_PROCESSING = "Failed to process clutch stats for {identifier} (Season: {season})."
    PLAYER_CLUTCH_UNEXPECTED = "Unexpected error fetching clutch stats for {identifier} (Season: {season}): {error}"
    PLAYER_PASSING_API = "API error fetching passing stats for {identifier} (Season: {season}): {error}"
    PLAYER_PASSING_PROCESSING = "Failed to process passing stats for {identifier} (Season: {season})."
    PLAYER_PASSING_UNEXPECTED = "Unexpected error fetching passing stats for {identifier} (Season: {season}): {error}"
    PLAYER_REBOUNDING_API = "API error fetching rebounding stats for {identifier} (Season: {season}): {error}"
    PLAYER_REBOUNDING_PROCESSING = "Failed to process rebounding stats for {identifier} (Season: {season})."
    PLAYER_REBOUNDING_UNEXPECTED = "Unexpected error fetching rebounding stats for {identifier} (Season: {season}): {error}"
    PLAYER_SHOTS_TRACKING_API = "API error fetching shot tracking stats for {identifier} (Season: {season}): {error}"
    PLAYER_SHOTS_TRACKING_PROCESSING = "Failed to process shot tracking stats for {identifier} (Season: {season})."
    PLAYER_SHOTS_TRACKING_UNEXPECTED = "Unexpected error fetching shot tracking stats for {identifier} (Season: {season}): {error}"
    PLAYER_ID_REQUIRED = "player_id is required when searching by player."

    PLAYER_PROFILE_API = "API error fetching player profile for {identifier}: {error}"
    PLAYER_PROFILE_PROCESSING = "Failed to process essential profile data for {identifier}"
    PLAYER_PROFILE_UNEXPECTED = "Unexpected error fetching player profile for {identifier}: {error}"
    PLAYER_HUSTLE_API = "API error fetching hustle stats: {error}"
    PLAYER_HUSTLE_PROCESSING = "Data processing error for hustle stats."
    PLAYER_HUSTLE_UNEXPECTED = "Unexpected error fetching hustle stats: {error}"

    PLAYER_ANALYSIS_API = "API error analyzing stats for player {identifier}: {error}"
    PLAYER_ANALYSIS_PROCESSING = "Failed to process analysis stats for player {identifier}."
    PLAYER_ANALYSIS_UNEXPECTED = "Unexpected error analyzing stats for player {identifier}: {error}"
    PLAYER_SEARCH_UNEXPECTED = "Unexpected error searching for players: {error}"

    # Team Errors
    TEAM_IDENTIFIER_EMPTY = "Team identifier (name, abbreviation, or ID) cannot be empty."
    TEAM_NOT_FOUND = "Team '{identifier}' not found."
    TEAM_API = "API error fetching {data_type} for team {identifier} (Season: {season}): {error}"
    TEAM_PROCESSING = "Failed to process {data_type} for team {identifier} (Season: {season})."
    TEAM_UNEXPECTED = "Unexpected error fetching team data for {identifier} (Season: {season}): {error}"
    TEAM_ALL_FAILED = "Failed to fetch any data (info, ranks, roster, coaches) for team {identifier} (Season: {season}). Errors: {errors_list}"
    TEAM_ID_REQUIRED = "team_id is required when searching by team."
    TEAM_PASSING_API = "API error fetching passing stats for team {identifier} (Season: {season}): {error}"
    TEAM_PASSING_PROCESSING = "Failed to process passing stats for team {identifier} (Season: {season})."
    TEAM_PASSING_UNEXPECTED = "Unexpected error fetching passing stats for team {identifier} (Season: {season}): {error}"
    TEAM_SHOOTING_API = "API error fetching shooting stats for team {identifier} (Season: {season}): {error}"
    TEAM_SHOOTING_PROCESSING = "Failed to process shooting stats for team {identifier} (Season: {season})."
    TEAM_SHOOTING_UNEXPECTED = "Unexpected error fetching shooting stats for team {identifier} (Season: {season}): {error}"
    TEAM_REBOUNDING_API = "API error fetching rebounding stats for team {identifier} (Season: {season}): {error}"
    TEAM_REBOUNDING_PROCESSING = "Failed to process rebounding stats for team {identifier} (Season: {season})."
    TEAM_REBOUNDING_UNEXPECTED = "Unexpected error fetching rebounding stats for team {identifier} (Season: {season}): {error}"
    TEAM_SEARCH_UNEXPECTED = "Unexpected error searching for teams: {error}"

    # Game Errors
    GAME_ID_EMPTY = "Game ID cannot be empty."
    INVALID_GAME_ID_FORMAT = "Invalid game ID format: '{game_id}'. Expected 10 digits."
    GAME_NOT_FOUND = "Game with ID '{game_id}' not found."
    BOXSCORE_API = "API error fetching boxscore for game {game_id}: {error}"
    BOXSCORE_TRADITIONAL_API = "API error fetching traditional boxscore for game {game_id}: {error}"
    BOXSCORE_ADVANCED_API = "API error fetching advanced boxscore for game {game_id}: {error}"
    BOXSCORE_FOURFACTORS_API = "API error fetching four factors boxscore for game {game_id}: {error}"
    BOXSCORE_USAGE_API = "API error fetching usage boxscore for game {game_id}: {error}"
    BOXSCORE_DEFENSIVE_API = "API error fetching defensive boxscore for game {game_id}: {error}"
    WINPROBABILITY_API = "API error fetching win probability for game {game_id}: {error}"
    PLAYBYPLAY_API = "API error fetching play-by-play for game {game_id}: {error}"
    SHOTCHART_API = "API error fetching shot chart for game {game_id}: {error}"
    GAME_UNEXPECTED = "Unexpected error fetching data for game {game_id}: {error}"
    SHOTCHART_PROCESSING = "Failed to process shot chart data for game {game_id}."
    INVALID_SEASON_FOR_GAME_SEARCH = "Invalid season provided for game search: {season}."
    GAME_SEARCH_UNEXPECTED = "Unexpected error searching for games: {error}"

    # Synergy Errors
    SYNERGY_API = "API error fetching synergy play types: {error}"
    SYNERGY_PROCESSING = "Failed to process synergy play types data."
    SYNERGY_UNEXPECTED = "Unexpected error fetching synergy play types: {error}"
    INVALID_PLAY_TYPE = "Invalid play type: '{play_type}'. Valid options: {options}"
    INVALID_TYPE_GROUPING = "Invalid type grouping: '{type_grouping}'. Valid options: {options}"

    # League Errors
    LEAGUE_STANDINGS_API = "API error fetching league standings for season {season}, date {date}: {error}"
    LEAGUE_STANDINGS_PROCESSING = "Failed to process league standings for season {season}, date {date}."
    LEAGUE_STANDINGS_UNEXPECTED = "Unexpected error fetching league standings for season {season}, date {date}: {error}"
    LEAGUE_SCOREBOARD_API = "API error fetching scoreboard for date {game_date}: {error}"
    LEAGUE_SCOREBOARD_UNEXPECTED = "Unexpected error fetching scoreboard for date {game_date}: {error}"
    DRAFT_HISTORY_API = "API error fetching draft history for year {year}: {error}"
    DRAFT_HISTORY_UNEXPECTED = "Unexpected error fetching draft history for year {year}: {error}"
    LEAGUE_LEADERS_API = "API error fetching league leaders for {stat_category} (Season: {season}): {error}"
    LEAGUE_LEADERS_UNEXPECTED = "Unexpected error fetching league leaders for {stat_category} (Season: {season}): {error}"
    INVALID_DRAFT_YEAR_FORMAT = "Invalid draft year format: '{year}'. Expected YYYY."
    DRAFT_HISTORY_PROCESSING = "Failed to process draft history for year {year}."
    LEAGUE_GAMES_API = "API error fetching league games: {error}"
    LEAGUE_GAMES_UNEXPECTED = "Unexpected error fetching league games: {error}"

    # Trending Stats Errors
    INVALID_TOP_N = "Invalid top_n parameter: must be a positive integer > 0, got {value}"
    TRENDING_UNEXPECTED = "Unexpected error fetching trending player data: {error}"
    TRENDING_TEAMS_UNEXPECTED = "Unexpected error fetching trending teams data: {error}"

    # Matchup Errors
    MISSING_PLAYER_IDENTIFIER = "Player identifier (name or ID) cannot be empty."
    MATCHUPS_API = "Error fetching matchup data: {error}"
    MATCHUPS_ROLLUP_API = "Error fetching matchup rollup data: {error}"
    MATCHUPS_PROCESSING = "Failed to process matchup data."
    MATCHUPS_UNEXPECTED = "Unexpected error fetching matchup data: {error}"
    MATCHUPS_ROLLUP_PROCESSING = "Failed to process matchup rollup data."
    MATCHUPS_ROLLUP_UNEXPECTED = "Unexpected error fetching matchup rollup data: {error}"

    # Odds Errors
    ODDS_API_UNEXPECTED = "Unexpected error fetching odds data: {error}"

    # Parameter Validation Errors
    INVALID_SEASON_TYPE = "Invalid season_type: '{value}'. Valid options: {options}"
    INVALID_STAT_CATEGORY = "Invalid stat_category: '{value}'. Valid options: {options}"
    INVALID_PER_MODE = "Invalid per_mode: '{value}'. Valid options: {options}"
    INVALID_LEAGUE_ID = "Invalid league_id: '{value}'. Valid options: {options}"
    INVALID_MEASURE_TYPE = "Invalid measure_type: '{value}'. Valid options: {options}"
    INVALID_SCOPE = "Invalid scope: '{value}'. Valid options: {options}"
    INVALID_PLAYER_OR_TEAM_ABBREVIATION = "Invalid player_or_team_abbreviation: '{value}'. Must be 'P' or 'T'."
    INVALID_DEFENSE_CATEGORY = "Invalid defense_category: '{value}'. Valid options: {options}"
    INVALID_SHOT_CLOCK_RANGE = "Invalid shot_clock_range: '{value}'. Valid options: {options}"
    INVALID_PLUS_MINUS = "Invalid plus_minus: '{value}'. Must be 'Y' or 'N'."
    INVALID_PACE_ADJUST = "Invalid pace_adjust: '{value}'. Must be 'Y' or 'N'."
    INVALID_RANK = "Invalid rank: '{value}'. Must be 'Y' or 'N'."
    INVALID_GAME_SEGMENT = "Invalid game_segment: '{value}'. Valid options: {options}"
    INVALID_LOCATION = "Invalid location: '{value}'. Valid options: {options}"
    INVALID_OUTCOME = "Invalid outcome: '{value}'. Valid options: {options}"
    INVALID_CONFERENCE = "Invalid vs_conference: '{value}'. Valid options: {options}"
    INVALID_DIVISION = "Invalid vs_division: '{value}'. Valid options: {options}"
    INVALID_SEASON_SEGMENT = "Invalid season_segment: '{value}'. Valid options: {options}"

# --- Environment Variable Loading ---
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
    logger.info(f".env file loaded from {dotenv_path}")
else:
    load_dotenv() 
    logger.info(".env file not found in config directory, attempting to load from standard locations.")

# --- API Keys ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', GOOGLE_API_KEY)

if not GOOGLE_API_KEY:
    logger.warning("Warning: GOOGLE_API_KEY not found in environment variables. AI features relying on Google GenAI may not work.")

# --- Agent-related Configurations ---
AGENT_MODEL_ID = os.getenv("AGENT_MODEL_ID", "gemini-1.5-flash-latest")
SUGGESTION_MODEL_ID = os.getenv("SUGGESTION_MODEL_ID", "gemini-1.5-flash-latest")
STORAGE_DB_FILE = os.getenv("STORAGE_DB_FILE", "agno_storage.db")
AGENT_DEBUG_MODE = os.getenv("AGENT_DEBUG_MODE", "false").lower() == "true"

# --- General Application Constants ---
def get_current_nba_season() -> str:
    now = datetime.datetime.now()
    current_year = now.year
    if now.month >= 10: 
        return f"{current_year}-{str(current_year + 1)[-2:]}"
    else:
        return f"{current_year - 1}-{str(current_year)[-2:]}"

CURRENT_SEASON = get_current_nba_season()
logger.info(f"Application configured for NBA Season: {CURRENT_SEASON}")


DEFAULT_TIMEOUT = 30
HEADSHOT_BASE_URL = "https://ak-static.cms.nba.com/wp-content/uploads/headshots/nba/latest/260x190"
DEFAULT_PLAYER_SEARCH_LIMIT = 10
MIN_PLAYER_SEARCH_LENGTH = 2
MAX_SEARCH_RESULTS = 25
MAX_GAMES_TO_RETURN = 50
MAX_PLAYERS_TO_RETURN = 25

# --- Supported Targets for Endpoints ---
# Commented out as it's likely unused or miscategorized.
# SUPPORTED_FETCH_TARGETS = [
#     "traditional", "advanced", "fourfactors", "misc", 
#     "scoring", "usage", "defense"
# ]

SUPPORTED_FETCH_TARGETS_FOR_ROUTE = [
    "player_info", "player_gamelog", "team_info", 
    "player_career_stats", "find_games"
]

SUPPORTED_SEARCH_TARGETS = [
    "players",
    "teams",
    "games"
]

# --- CORS Configuration ---
CORS_ALLOWED_ORIGINS_STR = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in CORS_ALLOWED_ORIGINS_STR.split(",") if origin.strip()]
if not CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
logger.info(f"CORS allowed origins: {CORS_ALLOWED_ORIGINS}")

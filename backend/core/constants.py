# --- General Application Constants ---
HEADSHOT_BASE_URL = "https://ak-static.cms.nba.com/wp-content/uploads/headshots/nba/latest/260x190"
DEFAULT_PLAYER_SEARCH_LIMIT = 10
MIN_PLAYER_SEARCH_LENGTH = 2
MAX_SEARCH_RESULTS = 25 # General limit for search results if not specified otherwise
MAX_GAMES_TO_RETURN = 50 # Max games for endpoints like find_games
MAX_PLAYERS_TO_RETURN = 25 # Max players for endpoints like player search

# --- Supported Targets for Endpoints ---
# These define valid string identifiers used in some route/logic parameters.

SUPPORTED_FETCH_TARGETS_FOR_ROUTE = [
    "player_info", 
    "player_gamelog", 
    "team_info", 
    "player_career_stats", 
    "find_games"
]

SUPPORTED_SEARCH_TARGETS = [
    "players",
    "teams",
    "games"
]

# Example of other potential constants if needed in the future:
# DEFAULT_LEAGUE_ID = "00" # NBA
# SEASON_TYPE_REGULAR = "Regular Season"
# SEASON_TYPE_PLAYOFFS = "Playoffs"
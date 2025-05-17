"""
Core constants for the NBA analytics backend application.
This file contains static, non-configurable values used across various modules.
It does not include environment-specific settings, which are handled by `backend.config`.
"""
from typing import List

# --- General Application Constants ---
HEADSHOT_BASE_URL: str = "https://ak-static.cms.nba.com/wp-content/uploads/headshots/nba/latest/260x190"
DEFAULT_PLAYER_SEARCH_LIMIT: int = 10
MIN_PLAYER_SEARCH_LENGTH: int = 2
MAX_SEARCH_RESULTS: int = 25  # General limit for search results if not specified otherwise
MAX_GAMES_TO_RETURN: int = 50  # Max games for endpoints like find_games
MAX_PLAYERS_TO_RETURN: int = 25  # Max players for endpoints like player search

# --- Supported Targets for Endpoints ---
# These define valid string identifiers used in some route/logic parameters.

SUPPORTED_FETCH_TARGETS: List[str] = [
    "player_info",
    "player_gamelog",
    "team_info",
    "player_career_stats",
    "find_games"
]

SUPPORTED_SEARCH_TARGETS: List[str] = [
    "players",
    "teams",
    "games"
]

# --- Illustrative Examples (Not actively used unless integrated elsewhere) ---
# Example of other potential constants if needed in the future:
# DEFAULT_LEAGUE_ID: str = "00" # NBA
# SEASON_TYPE_REGULAR: str = "Regular Season"
# SEASON_TYPE_PLAYOFFS: str = "Playoffs"

# Example Team IDs (can be expanded or moved to a dynamic source if many are needed):
# These are illustrative and should be properly managed if used actively.
TEAM_ID_LAKERS: int = 1610612747
TEAM_ID_CELTICS: int = 1610612738
TEAM_ID_WARRIORS: int = 1610612744
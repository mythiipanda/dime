import logging
from typing import List, Dict, Optional
from functools import lru_cache
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import leaguegamefinder
from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID

from backend.config import settings
from backend.core.constants import (
    DEFAULT_PLAYER_SEARCH_LIMIT,
    MIN_PLAYER_SEARCH_LENGTH,
    MAX_SEARCH_RESULTS
)
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response,
    find_team_id_or_error,
    TeamNotFoundError
)
from backend.utils.validation import _validate_season_format

logger = logging.getLogger(__name__)

_player_list_cache = None
_team_list_cache = None # Cache for teams

def _get_cached_player_list() -> List[Dict]:
    """Gets the full player list, caching it after the first call."""
    global _player_list_cache
    if _player_list_cache is None:
        logger.info("Fetching and caching full player list...")
        try:
            _player_list_cache = players.get_players()
            if not _player_list_cache:
                 logger.warning("players.get_players() returned an empty list.")
                 _player_list_cache = []
            else:
                 logger.info(f"Successfully cached {len(_player_list_cache)} players.")
        except Exception as e:
            logger.error(f"Failed to fetch and cache player list: {e}", exc_info=True)
            _player_list_cache = []
    return _player_list_cache

def _get_cached_team_list() -> List[Dict]:
    """Gets the full team list, caching it after the first call."""
    global _team_list_cache
    if _team_list_cache is None:
        logger.info("Fetching and caching full team list...")
        try:
            _team_list_cache = teams.get_teams()
            if not _team_list_cache:
                 logger.warning("teams.get_teams() returned an empty list.")
                 _team_list_cache = []
            else:
                 logger.info(f"Successfully cached {len(_team_list_cache)} teams.")
        except Exception as e:
            logger.error(f"Failed to fetch and cache team list: {e}", exc_info=True)
            _team_list_cache = []
    return _team_list_cache

@lru_cache(maxsize=512) # Cache player name fragments
def find_players_by_name_fragment(name_fragment: str, limit: int = DEFAULT_PLAYER_SEARCH_LIMIT) -> List[Dict]:
    """
    Finds players whose full name contains the given fragment (case-insensitive).

    Args:
        name_fragment (str): The partial name to search for.
        limit (int): The maximum number of results to return.

    Returns:
        List[Dict]: A list of matching players [{'id': player_id, 'full_name': player_name, 'is_active': bool}, ...].
    """
    if not name_fragment or len(name_fragment) < MIN_PLAYER_SEARCH_LENGTH:
        return []

    all_players = _get_cached_player_list()
    if not all_players:
        return []

    name_fragment_lower = name_fragment.lower()
    matching_players = []

    try:
        for player in all_players:
            if name_fragment_lower in player['full_name'].lower():
                matching_players.append({
                    'id': player['id'],
                    'full_name': player['full_name'],
                    'is_active': player.get('is_active', False)
                })
                if len(matching_players) >= limit:
                    break
    except Exception as e:
        logger.error(f"Error filtering player list for fragment '{name_fragment}': {e}", exc_info=True)
        return []

    logger.info(f"Found {len(matching_players)} players matching fragment '{name_fragment}' (limit {limit}).")
    return matching_players

@lru_cache(maxsize=256) # Caches the JSON string result
def search_players_logic(query: str, limit: int = MAX_SEARCH_RESULTS) -> str:
    """
    Search for players by name fragment.

    Args:
        query (str): The player name fragment to search for.
        limit (int): Maximum number of results. Defaults to MAX_SEARCH_RESULTS.

    Returns:
        JSON string with a list of matching players or an error message.
    """
    logger.info(f"Executing search_players_logic with query: '{query}'")

    if not query:
        return format_response(error=Errors.EMPTY_SEARCH_QUERY)
    if len(query) < MIN_PLAYER_SEARCH_LENGTH:
        min_len = getattr(Errors, 'MIN_PLAYER_SEARCH_LENGTH', MIN_PLAYER_SEARCH_LENGTH) # Use constant from config if available
        return format_response(error=Errors.SEARCH_QUERY_TOO_SHORT.format(min_length=min_len) if hasattr(Errors, 'SEARCH_QUERY_TOO_SHORT') else f"Search query must be at least {min_len} characters long.")

    try:
        # Use the helper function which utilizes the cache
        matching_players = find_players_by_name_fragment(query, limit)
        result = {"players": matching_players}
        return format_response(result)

    except Exception as e:
        logger.error(f"Error in search_players_logic: {str(e)}", exc_info=True)
        error_msg = Errors.PLAYER_SEARCH_UNEXPECTED.format(error=str(e)) if hasattr(Errors, 'PLAYER_SEARCH_UNEXPECTED') else f"Unexpected error searching for players: {e}"
        return format_response(error=error_msg)

@lru_cache(maxsize=128) # Caches team search results
def search_teams_logic(query: str, limit: int = MAX_SEARCH_RESULTS) -> str:
    """
    Search for teams by name, city, nickname, or abbreviation.

    Args:
        query (str): The search term.
        limit (int): Maximum number of results. Defaults to MAX_SEARCH_RESULTS.

    Returns:
        JSON string with a list of matching teams or an error message.
    """
    logger.info(f"Executing search_teams_logic with query: '{query}'")

    if not query:
        return format_response(error=Errors.EMPTY_SEARCH_QUERY)

    try:
        all_teams = _get_cached_team_list() # Use cached team list
        if not all_teams:
            logger.warning("_get_cached_team_list() returned empty list.")
            return format_response({"teams": []})

        query_lower = query.lower()
        filtered_teams = [
            team for team in all_teams
            if query_lower in team['full_name'].lower() or
               query_lower in team['city'].lower() or
               query_lower in team['nickname'].lower() or
               query_lower in team['abbreviation'].lower()
        ]

        # Limit results
        filtered_teams = filtered_teams[:limit]
        result = {"teams": filtered_teams}
        return format_response(result)

    except Exception as e:
        logger.error(f"Error in search_teams_logic: {str(e)}", exc_info=True)
        error_msg = Errors.TEAM_SEARCH_UNEXPECTED.format(error=str(e)) if hasattr(Errors, 'TEAM_SEARCH_UNEXPECTED') else f"Unexpected error searching for teams: {e}"
        return format_response(error=error_msg)

@lru_cache(maxsize=128) # Caches game search results
def search_games_logic(
    query: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    limit: int = MAX_SEARCH_RESULTS
) -> str:
    """
    Search for games based on a query, attempting to find head-to-head matchups
    (e.g., "TeamA vs TeamB") or games involving a single team.

    Args:
        query (str): Search query (e.g., "LAL vs BOS", "Lakers").
        season (str): Season in YYYY-YY format.
        season_type (str): Season type (e.g., Regular Season). Defaults to Regular Season.
        limit (int): Maximum number of games to return. Defaults to MAX_SEARCH_RESULTS.

    Returns:
        JSON string with matching games or an error message.
    """
    logger.info(f"Executing search_games_logic with query: '{query}', season: {season}")

    if not query:
        return format_response(error=Errors.EMPTY_SEARCH_QUERY)
    if not season or not _validate_season_format(season):
        # Use the specific constant if available
        error_msg = Errors.INVALID_SEASON if hasattr(Errors, 'INVALID_SEASON') else Errors.INVALID_SEASON_FORMAT.format(season=season)
        return format_response(error=error_msg)

    VALID_SEASON_TYPES = [getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)]
    if season_type not in VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(VALID_SEASON_TYPES)))

    team1_id: Optional[int] = None
    team2_id: Optional[int] = None
    team1_name: Optional[str] = None
    team2_name: Optional[str] = None
    query_parts: List[str] = []

    # Attempt to parse query for two teams
    delimiters = [" vs ", " at ", " vs. "]
    for delim in delimiters:
        if delim in query.lower():
            parts = query.lower().split(delim)
            if len(parts) == 2:
                query_parts = [parts[0].strip(), parts[1].strip()]
                break

    try:
        if len(query_parts) == 2:
            try:
                team1_id, team1_name = find_team_id_or_error(query_parts[0])
            except TeamNotFoundError:
                logger.warning(f"First team identifier '{query_parts[0]}' not found.")
            try:
                team2_id, team2_name = find_team_id_or_error(query_parts[1])
            except TeamNotFoundError:
                logger.warning(f"Second team identifier '{query_parts[1]}' not found.")
            logger.info(f"Parsed query into two teams: '{team1_name or query_parts[0]}' (ID: {team1_id}) and '{team2_name or query_parts[1]}' (ID: {team2_id})")
            # Proceed even if one team wasn't found, LeagueGameFinder might handle it
        else:
            # If not a clear matchup, try finding a single team ID
            team1_id, team1_name = find_team_id_or_error(query)
            logger.info(f"Searching for single team: '{team1_name}' (ID: {team1_id})")

    except (TeamNotFoundError, ValueError) as e:
         # This happens if the single team search fails
         logger.warning(f"Could not find any team IDs for query '{query}': {e}")
         return format_response({"games": []}) # Return empty list if no team identified

    try:
        # Default to current season if not provided before API call
        effective_season = season or settings.CURRENT_NBA_SEASON # Changed
        
        game_finder = leaguegamefinder.LeagueGameFinder(
            team_id_nullable=team1_id,
            vs_team_id_nullable=team2_id if team1_id else None, # Only use vs_team if team1 is set
            season_nullable=effective_season, # Use effective_season
            season_type_nullable=season_type,
            league_id_nullable=LeagueID.nba,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS # Changed
        )
        logger.debug("leaguegamefinder API call successful.")

        games_df = game_finder.league_game_finder_results.get_data_frame()
        games_list = []
        if not games_df.empty:
            # If we searched for two teams AND found both, ensure both are in the matchup string
            if team1_id and team2_id:
                 team1_info = teams.find_team_name_by_id(team1_id)
                 team2_info = teams.find_team_name_by_id(team2_id)
                 if team1_info and team2_info:
                     team1_abbr = team1_info['abbreviation']
                     team2_abbr = team2_info['abbreviation']
                     games_df = games_df[
                         games_df['MATCHUP'].str.contains(team1_abbr) &
                         games_df['MATCHUP'].str.contains(team2_abbr)
                     ]
                 else:
                     logger.warning("Could not get abbreviations for matchup filtering.")

            games_list = _process_dataframe(games_df, single_row=False) # Process after potential filtering

        if games_list is None: # Check processing result
             logger.error("Failed to process game finder results.")
             return format_response(error=Errors.PROCESSING_ERROR.format(error="game search results"))

        # Sort by date and limit results
        if games_list:
            games_list.sort(key=lambda x: x.get("GAME_DATE", ""), reverse=True) # Use GAME_DATE
            games_list = games_list[:limit]

        result = {"games": games_list}
        return format_response(result)

    except Exception as e:
        logger.error(f"Error in search_games_logic during API call or processing: {str(e)}", exc_info=True)
        error_msg = Errors.GAME_SEARCH_UNEXPECTED.format(error=str(e)) if hasattr(Errors, 'GAME_SEARCH_UNEXPECTED') else f"Unexpected error searching for games: {e}"
        return format_response(error=error_msg)

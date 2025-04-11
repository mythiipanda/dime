import logging
import json
from typing import List, Dict, Optional, Any
import pandas as pd
from nba_api.stats.endpoints import commonallplayers, leaguegamefinder
from nba_api.stats.static import players, teams
from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueIDNullable
from fuzzywuzzy import fuzz

from config import DEFAULT_PLAYER_SEARCH_LIMIT, MIN_PLAYER_SEARCH_LENGTH, DEFAULT_TIMEOUT, MAX_SEARCH_RESULTS, ErrorMessages as Errors
from api_tools.utils import _process_dataframe

logger = logging.getLogger(__name__)

# Cache for player list to avoid repeated calls to get_players()
_player_list_cache = None

def _get_cached_player_list() -> List[Dict]:
    """Gets the full player list, caching it after the first call."""
    global _player_list_cache
    if _player_list_cache is None:
        logger.info("Fetching and caching full player list...")
        try:
            _player_list_cache = players.get_players()
            logger.info(f"Successfully cached {len(_player_list_cache)} players.")
        except Exception as e:
            logger.error(f"Failed to fetch and cache player list: {e}", exc_info=True)
            _player_list_cache = [] # Set to empty list on error to avoid retrying constantly
    return _player_list_cache

def find_players_by_name_fragment(name_fragment: str, limit: int = DEFAULT_PLAYER_SEARCH_LIMIT) -> List[Dict]:
    """
    Finds players whose full name contains the given fragment (case-insensitive).
    Args:
        name_fragment (str): The partial name to search for.
        limit (int): The maximum number of results to return.
    Returns:
        List[Dict]: A list of matching players [{'id': player_id, 'full_name': player_name}, ...].
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
                    'full_name': player['full_name']
                })
                if len(matching_players) >= limit:
                    break
    except Exception as e:
        logger.error(f"Error filtering player list for fragment '{name_fragment}': {e}", exc_info=True)
        return []

    logger.info(f"Found {len(matching_players)} players matching fragment '{name_fragment}' (limit {limit}).")
    return matching_players

def search_players_logic(query: str, limit: int = MAX_SEARCH_RESULTS) -> str:
    """
    Search for players by name.
    Returns JSON string with matching players.
    """
    logger.info(f"Executing search_players_logic with query: '{query}'")
    
    if not query:
        return json.dumps({"error": Errors.EMPTY_SEARCH_QUERY})
    
    if len(query) < MIN_PLAYER_SEARCH_LENGTH:
        return json.dumps({"error": Errors.SEARCH_QUERY_TOO_SHORT})
    
    try:
        # Use cached player list for better performance
        all_players = _get_cached_player_list()
        if not all_players:
            return json.dumps({"players": []})
        
        # Filter players based on query
        query_lower = query.lower()
        filtered_players = [
            player for player in all_players
            if query_lower in player['full_name'].lower()
        ]
        
        # Sort by relevance and limit results
        filtered_players = filtered_players[:limit]
        
        result = {
            "players": filtered_players
        }
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"Error in search_players_logic: {str(e)}", exc_info=True)
        return json.dumps({"error": Errors.UNEXPECTED_ERROR})

def search_teams_logic(query: str, limit: int = MAX_SEARCH_RESULTS) -> str:
    """
    Search for teams by name or city.
    Returns JSON string with matching teams.
    """
    logger.info(f"Executing search_teams_logic with query: '{query}'")
    
    if not query:
        return json.dumps({"error": Errors.EMPTY_SEARCH_QUERY})
    
    try:
        all_teams = teams.get_teams()
        if not all_teams:
            return json.dumps({"teams": []})
        
        # Filter teams based on query
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
        
        result = {
            "teams": filtered_teams
        }
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"Error in search_teams_logic: {str(e)}", exc_info=True)
        return json.dumps({"error": Errors.UNEXPECTED_ERROR})

def _find_team_id_by_name(name: str) -> Optional[int]:
    """Finds a team ID by full name, nickname, or abbreviation."""
    all_teams = teams.get_teams()
    name_lower = name.lower()
    for team in all_teams:
        if (name_lower == team['full_name'].lower() or
            name_lower == team['nickname'].lower() or
            name_lower == team['abbreviation'].lower()):
            return team['id']
    return None

def search_games_logic(
    query: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    limit: int = MAX_SEARCH_RESULTS
) -> str:
    """
    Search for games based on a query, attempting to find head-to-head matchups
    (e.g., "TeamA vs TeamB") or games involving a single team.
    Returns JSON string with matching games.
    """
    logger.info(f"Executing search_games_logic with query: '{query}', season: {season}")

    if not query:
        return json.dumps({"error": Errors.EMPTY_SEARCH_QUERY})
    if not season:
        return json.dumps({"error": Errors.INVALID_SEASON})

    team1_id = None
    team2_id = None
    query_parts = []

    # Attempt to parse query for two teams (simple split)
    delimiters = [" vs ", " at ", " vs. "]
    for delim in delimiters:
        if delim in query.lower():
            parts = query.lower().split(delim)
            if len(parts) == 2:
                query_parts = [parts[0].strip(), parts[1].strip()]
                break
    
    if len(query_parts) == 2:
        team1_id = _find_team_id_by_name(query_parts[0])
        team2_id = _find_team_id_by_name(query_parts[1])
        logger.info(f"Parsed query into two teams: '{query_parts[0]}' (ID: {team1_id}) and '{query_parts[1]}' (ID: {team2_id})")
    else:
        # If not a clear matchup, try finding a single team ID from the query
        team1_id = _find_team_id_by_name(query)
        logger.info(f"Could not parse into two teams. Searching for single team: '{query}' (ID: {team1_id})")

    if not team1_id and not team2_id:
         logger.warning(f"Could not find any team IDs for query: '{query}'")
         return json.dumps({"games": []}) # No teams found

    try:
        game_finder = leaguegamefinder.LeagueGameFinder(
            team_id_nullable=team1_id,
            vs_team_id_nullable=team2_id if team1_id else None, # Only use vs_team if team1 is set
            season_nullable=season,
            season_type_nullable=season_type,
            league_id_nullable=LeagueIDNullable.nba, # Ensure we only get NBA games
            timeout=DEFAULT_TIMEOUT
        )

        games_df = game_finder.league_game_finder_results.get_data_frame()
        games_list = []
        if not games_df.empty:
            # If we searched for two teams, ensure both are in the matchup string
            if team1_id and team2_id:
                 # Get team abbreviations for filtering matchup string
                 team1_abbr = teams.find_team_name_by_id(team1_id)['abbreviation']
                 team2_abbr = teams.find_team_name_by_id(team2_id)['abbreviation']
                 if team1_abbr and team2_abbr:
                     games_df = games_df[
                         games_df['MATCHUP'].str.contains(team1_abbr) &
                         games_df['MATCHUP'].str.contains(team2_abbr)
                     ]
                 else:
                     logger.warning("Could not get abbreviations for matchup filtering.")


            games_list = _process_dataframe(games_df, single_row=False)

        # Sort by date and limit results
        if games_list:
            games_list.sort(key=lambda x: x.get("GAME_DATE", ""), reverse=True)
            games_list = games_list[:limit]

        result = {
            "games": games_list
        }
        return json.dumps(result, default=str)

    except Exception as e:
        logger.error(f"Error in search_games_logic: {str(e)}", exc_info=True)
        return json.dumps({"error": Errors.UNEXPECTED_ERROR})

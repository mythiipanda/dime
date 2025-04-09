import logging
import json
from typing import List, Dict, Optional, Any
import pandas as pd
from nba_api.stats.endpoints import commonallplayers, leaguegamefinder
from nba_api.stats.static import players, teams
from nba_api.stats.library.parameters import SeasonTypeAllStar
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

def search_games_logic(
    query: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    limit: int = MAX_SEARCH_RESULTS
) -> str:
    """
    Search for games by team names.
    Returns JSON string with matching games.
    """
    logger.info(f"Executing search_games_logic with query: '{query}', season: {season}")
    
    if not query:
        return json.dumps({"error": Errors.EMPTY_SEARCH_QUERY})
    
    if not season:
        return json.dumps({"error": Errors.INVALID_SEASON})
        
    if season_type not in [t.value for t in SeasonTypeAllStar]:
        return json.dumps({"error": Errors.INVALID_SEASON_TYPE})
    
    try:
        # First search for teams to get team IDs
        teams_result = json.loads(search_teams_logic(query))
        if "error" in teams_result or not teams_result["teams"]:
            return json.dumps({"games": []})
        
        team_ids = [team["id"] for team in teams_result["teams"]]
        
        # Search for games involving these teams
        games_list = []
        for team_id in team_ids:
            game_finder = leaguegamefinder.LeagueGameFinder(
                team_id_nullable=team_id,
                season_nullable=season,
                season_type_nullable=season_type,
                timeout=DEFAULT_TIMEOUT
            )
            
            games_df = game_finder.league_game_finder_results.get_data_frame()
            if not games_df.empty:
                games = _process_dataframe(games_df, single_row=False)
                games_list.extend(games)
        
        # Sort by date and limit results
        if games_list:
            games_list.sort(key=lambda x: x["GAME_DATE"], reverse=True)
            games_list = games_list[:limit]
        
        result = {
            "games": games_list
        }
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"Error in search_games_logic: {str(e)}", exc_info=True)
        return json.dumps({"error": Errors.UNEXPECTED_ERROR})

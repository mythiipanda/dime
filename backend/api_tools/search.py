"""
Provides search functionalities for players, teams, and games within the NBA data.
Utilizes cached static lists for players and teams, and LeagueGameFinder for games.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
from typing import List, Dict, Optional, Tuple, Union
from functools import lru_cache
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import leaguegamefinder
from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID
import pandas as pd

from ..config import settings
from ..core.constants import (
    DEFAULT_PLAYER_SEARCH_LIMIT,
    MIN_PLAYER_SEARCH_LENGTH,
    MAX_SEARCH_RESULTS # Used as default limit for all searches
)
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response,
    find_team_id_or_error, # Used in game search
    TeamNotFoundError
)
from ..utils.validation import _validate_season_format
from ..utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
PLAYER_NAME_FRAGMENT_CACHE_SIZE = 512
PLAYER_SEARCH_CACHE_SIZE = 256
TEAM_SEARCH_CACHE_SIZE = 128
GAME_SEARCH_CACHE_SIZE = 128
GAME_SEARCH_DELIMITERS = [" vs ", " at ", " vs. "]

# --- Cache Directory Setup ---
SEARCH_CSV_DIR = get_cache_dir("search")
PLAYER_SEARCH_CSV_DIR = get_cache_dir("search/players")
TEAM_SEARCH_CSV_DIR = get_cache_dir("search/teams")
GAME_SEARCH_CSV_DIR = get_cache_dir("search/games")

# --- Helper Functions for CSV Caching ---
def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves a DataFrame to a CSV file.

    Args:
        df: DataFrame to save
        file_path: Path to save the CSV file
    """
    try:
        df.to_csv(file_path, index=False)
        logger.info(f"Saved DataFrame to CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)

def _get_csv_path_for_player_search(query: str) -> str:
    """
    Generates a file path for saving player search results as CSV.

    Args:
        query: The search query

    Returns:
        Path to the CSV file
    """
    # Clean query for filename
    clean_query = query.replace(" ", "_").replace(".", "").lower()

    filename = f"player_search_{clean_query}.csv"
    return get_cache_file_path(filename, "search/players")

def _get_csv_path_for_team_search(query: str) -> str:
    """
    Generates a file path for saving team search results as CSV.

    Args:
        query: The search query

    Returns:
        Path to the CSV file
    """
    # Clean query for filename
    clean_query = query.replace(" ", "_").replace(".", "").lower()

    filename = f"team_search_{clean_query}.csv"
    return get_cache_file_path(filename, "search/teams")

def _get_csv_path_for_game_search(query: str, season: str, season_type: str) -> str:
    """
    Generates a file path for saving game search results as CSV.

    Args:
        query: The search query
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')

    Returns:
        Path to the CSV file
    """
    # Clean query and season type for filename
    clean_query = query.replace(" ", "_").replace(".", "").lower()
    clean_season_type = season_type.replace(" ", "_").lower()

    filename = f"game_search_{clean_query}_{season}_{clean_season_type}.csv"
    return get_cache_file_path(filename, "search/games")

# --- Global Caches for Static Data ---
_player_list_cache: Optional[List[Dict]] = None
_team_list_cache: Optional[List[Dict]] = None

# --- Helper Functions for Static Data Caching ---
def _get_cached_player_list() -> List[Dict]:
    """Gets the full player list, caching it in memory after the first call."""
    global _player_list_cache
    if _player_list_cache is None:
        logger.info("Fetching and caching full player list from nba_api.stats.static...")
        try:
            _player_list_cache = players.get_players()
            if not _player_list_cache: # Should not happen with nba_api, but good check
                 logger.warning("players.get_players() returned an empty or invalid list.")
                 _player_list_cache = [] # Ensure it's an empty list on failure
            else:
                 logger.info(f"Successfully cached {len(_player_list_cache)} players.")
        except Exception as e:
            logger.error(f"Failed to fetch and cache player list: {e}", exc_info=True)
            _player_list_cache = [] # Ensure it's an empty list on failure
    return _player_list_cache

def _get_cached_team_list() -> List[Dict]:
    """Gets the full team list, caching it in memory after the first call."""
    global _team_list_cache
    if _team_list_cache is None:
        logger.info("Fetching and caching full team list from nba_api.stats.static...")
        try:
            _team_list_cache = teams.get_teams()
            if not _team_list_cache: # Should not happen
                 logger.warning("teams.get_teams() returned an empty or invalid list.")
                 _team_list_cache = []
            else:
                 logger.info(f"Successfully cached {len(_team_list_cache)} teams.")
        except Exception as e:
            logger.error(f"Failed to fetch and cache team list: {e}", exc_info=True)
            _team_list_cache = []
    return _team_list_cache

# --- Player Search Logic ---
@lru_cache(maxsize=PLAYER_NAME_FRAGMENT_CACHE_SIZE)
def find_players_by_name_fragment(name_fragment: str, limit: int = DEFAULT_PLAYER_SEARCH_LIMIT) -> List[Dict]:
    """
    Finds players whose full name contains the given fragment (case-insensitive).
    Uses the in-memory cached full player list.
    """
    if not name_fragment or len(name_fragment) < MIN_PLAYER_SEARCH_LENGTH:
        return []
    all_players = _get_cached_player_list()
    if not all_players: return []

    name_fragment_lower = name_fragment.lower()
    matching_players = []
    try:
        for player in all_players:
            if name_fragment_lower in player['full_name'].lower():
                matching_players.append({
                    'id': player['id'],
                    'full_name': player['full_name'],
                    'is_active': player.get('is_active', False) # is_active might not always be present
                })
                if len(matching_players) >= limit: break
    except Exception as e:
        logger.error(f"Error filtering player list for fragment '{name_fragment}': {e}", exc_info=True)
        return [] # Return empty on error during filtering
    logger.debug(f"Found {len(matching_players)} players for fragment '{name_fragment}' (limit {limit}).")
    return matching_players

def search_players_logic(
    query: str,
    limit: int = MAX_SEARCH_RESULTS,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public API to search for players by name fragment.

    Provides DataFrame output capabilities.

    Args:
        query: The search query string.
        limit: Maximum number of results to return.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: A JSON string containing search results or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing search_players_logic with query: '{query}', limit: {limit}, return_dataframe={return_dataframe}")

    if not query:
        error_response = format_response(error=Errors.EMPTY_SEARCH_QUERY)
        if return_dataframe:
            return error_response, {}
        return error_response

    if len(query) < MIN_PLAYER_SEARCH_LENGTH:
        error_response = format_response(error=Errors.SEARCH_QUERY_TOO_SHORT.format(min_length=MIN_PLAYER_SEARCH_LENGTH))
        if return_dataframe:
            return error_response, {}
        return error_response

    try:
        # Get matching players
        matching_players = find_players_by_name_fragment(query, limit)

        # Create response data
        response_data = {"players": matching_players}

        # Return the appropriate result based on return_dataframe
        if return_dataframe:
            # Convert list of dictionaries to DataFrame
            if matching_players:
                players_df = pd.DataFrame(matching_players)

                # Save DataFrame to CSV
                csv_path = _get_csv_path_for_player_search(query)
                _save_dataframe_to_csv(players_df, csv_path)

                # Add DataFrame metadata to the response
                csv_filename = os.path.basename(csv_path)
                relative_path = get_relative_cache_path(csv_filename, "search/players")

                response_data["dataframe_info"] = {
                    "message": "Player search results have been converted to DataFrame and saved as CSV file",
                    "dataframes": {
                        "players": {
                            "shape": list(players_df.shape),
                            "columns": players_df.columns.tolist(),
                            "csv_path": relative_path
                        }
                    }
                }

                dataframes = {"players": players_df}
                return format_response(response_data), dataframes
            else:
                # Return empty DataFrame
                empty_df = pd.DataFrame()
                return format_response(response_data), {"players": empty_df}

        return format_response(response_data)

    except Exception as e: # Should be rare as find_players_by_name_fragment handles its errors
        logger.error(f"Unexpected error in search_players_logic: {str(e)}", exc_info=True)
        error_response = format_response(error=Errors.PLAYER_SEARCH_UNEXPECTED.format(error=str(e)))
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Team Search Logic ---
def search_teams_logic(
    query: str,
    limit: int = MAX_SEARCH_RESULTS,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public API to search for teams by name, city, nickname, or abbreviation.

    Provides DataFrame output capabilities.

    Args:
        query: The search query string.
        limit: Maximum number of results to return.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: A JSON string containing search results or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing search_teams_logic with query: '{query}', limit: {limit}, return_dataframe={return_dataframe}")

    if not query:
        error_response = format_response(error=Errors.EMPTY_SEARCH_QUERY)
        if return_dataframe:
            return error_response, {}
        return error_response

    try:
        # Get all teams
        all_teams = _get_cached_team_list()
        if not all_teams:
            logger.warning("Team list cache is empty, cannot search teams.")
            response_data = {"teams": []}
            if return_dataframe:
                empty_df = pd.DataFrame()
                return format_response(response_data), {"teams": empty_df}
            return format_response(response_data)

        # Filter teams
        query_lower = query.lower()
        filtered_teams = [
            team for team in all_teams
            if query_lower in team.get('full_name', '').lower() or
               query_lower in team.get('city', '').lower() or
               query_lower in team.get('nickname', '').lower() or
               query_lower in team.get('abbreviation', '').lower()
        ][:limit] # Apply limit after filtering

        # Create response data
        response_data = {"teams": filtered_teams}

        # Return the appropriate result based on return_dataframe
        if return_dataframe:
            # Convert list of dictionaries to DataFrame
            if filtered_teams:
                teams_df = pd.DataFrame(filtered_teams)

                # Save DataFrame to CSV
                csv_path = _get_csv_path_for_team_search(query)
                _save_dataframe_to_csv(teams_df, csv_path)

                # Add DataFrame metadata to the response
                csv_filename = os.path.basename(csv_path)
                relative_path = get_relative_cache_path(csv_filename, "search/teams")

                response_data["dataframe_info"] = {
                    "message": "Team search results have been converted to DataFrame and saved as CSV file",
                    "dataframes": {
                        "teams": {
                            "shape": list(teams_df.shape),
                            "columns": teams_df.columns.tolist(),
                            "csv_path": relative_path
                        }
                    }
                }

                dataframes = {"teams": teams_df}
                return format_response(response_data), dataframes
            else:
                # Return empty DataFrame
                empty_df = pd.DataFrame()
                return format_response(response_data), {"teams": empty_df}

        return format_response(response_data)

    except Exception as e:
        logger.error(f"Error in search_teams_logic: {str(e)}", exc_info=True)
        error_response = format_response(error=Errors.TEAM_SEARCH_UNEXPECTED.format(error=str(e)))
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Game Search Logic ---
def _parse_game_search_query(query: str) -> Tuple[Optional[int], Optional[str], Optional[int], Optional[str]]:
    """Parses a game search query to identify one or two teams."""
    team1_id: Optional[int] = None
    team1_name: Optional[str] = None
    team2_id: Optional[int] = None
    team2_name: Optional[str] = None

    query_parts: List[str] = []
    for delim in GAME_SEARCH_DELIMITERS:
        if delim in query.lower():
            parts = query.lower().split(delim)
            if len(parts) == 2:
                query_parts = [parts[0].strip(), parts[1].strip()]
                break

    if len(query_parts) == 2:
        try: team1_id, team1_name = find_team_id_or_error(query_parts[0])
        except TeamNotFoundError: logger.warning(f"Game search: First team '{query_parts[0]}' not found.")
        try: team2_id, team2_name = find_team_id_or_error(query_parts[1])
        except TeamNotFoundError: logger.warning(f"Game search: Second team '{query_parts[1]}' not found.")
        logger.info(f"Parsed game query into two teams: '{team1_name or query_parts[0]}' (ID: {team1_id}) and '{team2_name or query_parts[1]}' (ID: {team2_id})")
    else:
        try: team1_id, team1_name = find_team_id_or_error(query)
        except TeamNotFoundError: logger.warning(f"Game search: Single team query '{query}' did not match any team.")
        logger.info(f"Parsed game query for single team: '{team1_name}' (ID: {team1_id})")

    return team1_id, team1_name, team2_id, team2_name

def _filter_for_head_to_head(games_df: pd.DataFrame, team1_id: Optional[int], team2_id: Optional[int]) -> pd.DataFrame:
    """Filters DataFrame for games explicitly between team1 and team2 if both IDs are valid."""
    if games_df.empty or not (team1_id and team2_id):
        return games_df

    team1_info = teams.find_team_name_by_id(team1_id) # nba_api.stats.static.teams
    team2_info = teams.find_team_name_by_id(team2_id)

    if team1_info and team2_info:
        team1_abbr = team1_info['abbreviation']
        team2_abbr = team2_info['abbreviation']
        # Ensure MATCHUP column exists and filter
        if 'MATCHUP' in games_df.columns:
            return games_df[
                games_df['MATCHUP'].str.contains(team1_abbr, case=False, na=False) &
                games_df['MATCHUP'].str.contains(team2_abbr, case=False, na=False)
            ]
        else:
            logger.warning("'MATCHUP' column not found in game finder results for head-to-head filtering.")
    else:
        logger.warning("Could not retrieve team abbreviations for head-to-head game filtering.")
    return games_df # Return original if filtering can't be applied

def search_games_logic(
    query: str,
    season: str, # Made season non-optional as LeagueGameFinder requires it or player/team ID
    season_type: str = SeasonTypeAllStar.regular,
    limit: int = MAX_SEARCH_RESULTS,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Searches for games based on a query (e.g., "TeamA vs TeamB", "Lakers").

    Provides DataFrame output capabilities.

    Args:
        query: The search query string.
        season: The NBA season in YYYY-YY format.
        season_type: The type of season (e.g., "Regular Season", "Playoffs").
        limit: Maximum number of results to return.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: A JSON string containing search results or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing search_games_logic with query: '{query}', season: {season}, type: {season_type}, limit: {limit}, return_dataframe={return_dataframe}")

    if not query:
        error_response = format_response(error=Errors.EMPTY_SEARCH_QUERY)
        if return_dataframe:
            return error_response, {}
        return error_response

    if not _validate_season_format(season): # Season is now mandatory
        error_response = format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
        if return_dataframe:
            return error_response, {}
        return error_response

    valid_season_types = [getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)]
    if season_type not in valid_season_types:
        error_response = format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(valid_season_types)))
        if return_dataframe:
            return error_response, {}
        return error_response

    team1_id, _, team2_id, _ = _parse_game_search_query(query)

    # If no team could be identified from the query, it's unlikely LeagueGameFinder will succeed well.
    if not team1_id and not team2_id:
        logger.warning(f"No valid teams identified from game search query: '{query}'. Returning empty.")
        response_data = {"games": []}
        if return_dataframe:
            empty_df = pd.DataFrame()
            return format_response(response_data), {"games": empty_df}
        return format_response(response_data)

    try:
        # Call the API
        game_finder = leaguegamefinder.LeagueGameFinder(
            team_id_nullable=team1_id,
            vs_team_id_nullable=team2_id if team1_id else None,
            season_nullable=season,
            season_type_nullable=season_type,
            league_id_nullable=LeagueID.nba, # Default to NBA
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug("LeagueGameFinder API call successful.")

        # Get DataFrame from the API response
        games_df = game_finder.league_game_finder_results.get_data_frame()

        if games_df.empty:
            response_data = {"games": []}
            if return_dataframe:
                empty_df = pd.DataFrame()
                return format_response(response_data), {"games": empty_df}
            return format_response(response_data)

        # If both team IDs were found from a "vs" query, perform stricter filtering
        if team1_id and team2_id and any(d in query.lower() for d in GAME_SEARCH_DELIMITERS):
            filtered_games_df = _filter_for_head_to_head(games_df, team1_id, team2_id)
        else:
            filtered_games_df = games_df

        # Process DataFrame for JSON response
        games_list = _process_dataframe(filtered_games_df, single_row=False)
        if games_list is None:
            logger.error("Failed to process game finder results after potential filtering.")
            error_response = format_response(error=Errors.PROCESSING_ERROR.format(error="game search results"))
            if return_dataframe:
                return error_response, {}
            return error_response

        if games_list: # Sort and limit only if list is not empty
            games_list.sort(key=lambda x: x.get("GAME_DATE", ""), reverse=True)
            games_list = games_list[:limit]

            # Also limit the DataFrame if we're returning it
            if return_dataframe and not filtered_games_df.empty:
                # Sort DataFrame by GAME_DATE in descending order
                if "GAME_DATE" in filtered_games_df.columns:
                    filtered_games_df = filtered_games_df.sort_values(by="GAME_DATE", ascending=False)

                # Limit to the same number of rows as the JSON response
                filtered_games_df = filtered_games_df.head(limit)

        # Create response data
        response_data = {"games": games_list}

        # Return the appropriate result based on return_dataframe
        if return_dataframe:
            # Save DataFrame to CSV if not empty
            if not filtered_games_df.empty:
                csv_path = _get_csv_path_for_game_search(query, season, season_type)
                _save_dataframe_to_csv(filtered_games_df, csv_path)

                # Add DataFrame metadata to the response
                csv_filename = os.path.basename(csv_path)
                relative_path = get_relative_cache_path(csv_filename, "search/games")

                response_data["dataframe_info"] = {
                    "message": "Game search results have been converted to DataFrame and saved as CSV file",
                    "dataframes": {
                        "games": {
                            "shape": list(filtered_games_df.shape),
                            "columns": filtered_games_df.columns.tolist(),
                            "csv_path": relative_path
                        }
                    }
                }

                dataframes = {"games": filtered_games_df}
                return format_response(response_data), dataframes
            else:
                # Return empty DataFrame
                empty_df = pd.DataFrame()
                return format_response(response_data), {"games": empty_df}

        return format_response(response_data)

    except Exception as e:
        logger.error(f"Error in search_games_logic API call/processing: {str(e)}", exc_info=True)
        error_response = format_response(error=Errors.GAME_SEARCH_UNEXPECTED.format(error=str(e)))
        if return_dataframe:
            return error_response, {}
        return error_response

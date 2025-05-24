from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import tool
from agno.utils.log import logger

from ..api_tools.search import (
    search_players_logic,
    search_teams_logic,
    search_games_logic,
)
from ..api_tools.game_finder import fetch_league_games_logic
from ..core.constants import MAX_SEARCH_RESULTS, MIN_PLAYER_SEARCH_LENGTH
from ..config import settings # For default season if applicable, though search_games requires it explicitly
from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID # Used in type hints/defaults

@tool
def search_players(
    query: str,
    limit: int = MAX_SEARCH_RESULTS,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Searches for NBA players by name fragment.
    Args:
        query (str): Search query (player's name). Min length: {MIN_PLAYER_SEARCH_LENGTH}.
        limit (int): Max results. Defaults to {MAX_SEARCH_RESULTS}.
        return_dataframe (bool): If True, returns (JSON, {{'players': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: search_players called with query: '{query}', limit: {limit}")
    if len(query) < MIN_PLAYER_SEARCH_LENGTH:
        return f'{{"error": "Query must be at least {MIN_PLAYER_SEARCH_LENGTH} characters long."}}'
    return search_players_logic(query=query, limit=limit, return_dataframe=return_dataframe)

@tool
def search_teams(
    query: str,
    limit: int = MAX_SEARCH_RESULTS,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Searches for NBA teams by name, city, nickname, or abbreviation.
    Args:
        query (str): Search query.
        limit (int): Max results. Defaults to {MAX_SEARCH_RESULTS}.
        return_dataframe (bool): If True, returns (JSON, {{'teams': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: search_teams called with query: '{query}', limit: {limit}")
    return search_teams_logic(query=query, limit=limit, return_dataframe=return_dataframe)

@tool
def search_games(
    query: str,
    season: str, # YYYY-YY format, made non-optional as per toolkit
    season_type: str = SeasonTypeAllStar.regular,
    limit: int = MAX_SEARCH_RESULTS,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Searches for NBA games (e.g., "TeamA vs TeamB", "Lakers") for a specific season.
    Args:
        query (str): Search query (team name or "TeamA vs TeamB").
        season (str): NBA season in YYYY-YY format (e.g., "2023-24").
        season_type (str): E.g., "Regular Season", "Playoffs". Defaults to "Regular Season".
        limit (int): Max results. Defaults to {MAX_SEARCH_RESULTS}.
        return_dataframe (bool): If True, returns (JSON, {{'games': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: search_games called with query: '{query}', season: {season}, type: {season_type}, limit: {limit}")
    return search_games_logic(query=query, season=season, season_type=season_type, limit=limit, return_dataframe=return_dataframe)

@tool
def find_league_games(
    player_or_team_abbreviation: str = 'T', # 'P' for player, 'T' for team
    player_id_nullable: Optional[int] = None,
    team_id_nullable: Optional[int] = None,
    season_nullable: Optional[str] = None, # YYYY-YY format
    season_type_nullable: Optional[str] = None, # e.g., "Regular Season", "Playoffs"
    league_id_nullable: Optional[str] = LeagueID.nba,
    date_from_nullable: Optional[str] = None, # YYYY-MM-DD
    date_to_nullable: Optional[str] = None,   # YYYY-MM-DD
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches NBA league games using LeagueGameFinder with various filters.
    Args:
        player_or_team_abbreviation (str): 'P' or 'T'. Defaults to 'T'.
        player_id_nullable (Optional[int]): Player ID. Required if 'P'.
        team_id_nullable (Optional[int]): Team ID.
        season_nullable (Optional[str]): Season (YYYY-YY).
        season_type_nullable (Optional[str]): E.g., "Regular Season".
        league_id_nullable (Optional[str]): League ID. Defaults to "00".
        date_from_nullable (Optional[str]): Start date (YYYY-MM-DD).
        date_to_nullable (Optional[str]): End date (YYYY-MM-DD).
        return_dataframe (bool): If True, returns (JSON, {{'games': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: find_league_games called with filters: P/T='{player_or_team_abbreviation}', PlayerID={player_id_nullable}, TeamID={team_id_nullable}, Season={season_nullable}")
    if player_or_team_abbreviation == 'P' and player_id_nullable is None:
        return '{"error": "player_id_nullable is required when player_or_team_abbreviation is \'P\".}'
    return fetch_league_games_logic(
        player_or_team_abbreviation=player_or_team_abbreviation,
        player_id_nullable=player_id_nullable,
        team_id_nullable=team_id_nullable,
        season_nullable=season_nullable,
        season_type_nullable=season_type_nullable,
        league_id_nullable=league_id_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        return_dataframe=return_dataframe
    ) 
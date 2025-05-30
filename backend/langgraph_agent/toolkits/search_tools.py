from typing import Optional, Dict, Any, Union, Tuple, List

from pydantic import BaseModel, Field
from langchain_core.tools import tool

from backend.api_tools.search import search_players_logic as fetch_search_players_data
from backend.api_tools.search import search_teams_logic as fetch_search_teams_data
from backend.api_tools.search import search_games_logic as fetch_search_games_data

class PlayerSearchInput(BaseModel):
    """Input schema for the NBA Player Search tool."""
    query: str = Field(
        description="The search query string (e.g., 'LeBron James', 'Curry'). Minimum 3 characters."
    )
    limit: Optional[int] = Field(
        default=10,
        description="Maximum number of results to return (e.g., 5, 10, 25). Defaults to 10."
    )

@tool("search_nba_players", args_schema=PlayerSearchInput)
def search_nba_players(
    query: str,
    limit: int = 10
) -> str:
    """Searches for NBA players by name fragment (case-insensitive). Returns a list of matching players with their ID, full name, and active status. Requires a minimum 3-character query."""
    
    json_response = fetch_search_players_data(
        query=query,
        limit=limit,
        return_dataframe=False
    )
    return json_response

class TeamSearchInput(BaseModel):
    """Input schema for the NBA Team Search tool."""
    query: str = Field(
        description="The search query string (e.g., 'Lakers', 'Boston', 'GSW')."
    )
    limit: Optional[int] = Field(
        default=10,
        description="Maximum number of results to return (e.g., 5, 10, 25). Defaults to 10."
    )

@tool("search_nba_teams", args_schema=TeamSearchInput)
def search_nba_teams(
    query: str,
    limit: int = 10
) -> str:
    """Searches for NBA teams by name, city, nickname, or abbreviation. Returns a list of matching teams with their ID, full name, city, and abbreviation."""
    
    json_response = fetch_search_teams_data(
        query=query,
        limit=limit,
        return_dataframe=False
    )
    return json_response

class GameSearchInput(BaseModel):
    """Input schema for the NBA Game Search tool."""
    query: str = Field(
        description="The search query string for games (e.g., 'Lakers vs Celtics', 'Warriors game')."
    )
    season: str = Field(
        description="The NBA season in YYYY-YY format (e.g., '2023-24')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="The type of season ('Regular Season', 'Playoffs', 'Pre Season', 'All-Star'). Defaults to 'Regular Season'."
    )
    limit: Optional[int] = Field(
        default=10,
        description="Maximum number of results to return (e.g., 5, 10, 25). Defaults to 10."
    )

@tool("search_nba_games", args_schema=GameSearchInput)
def search_nba_games(
    query: str,
    season: str,
    season_type: str = "Regular Season",
    limit: int = 10
) -> str:
    """Searches for NBA games based on a query (e.g., "TeamA vs TeamB", "Lakers"). Returns a list of matching games with their details. Requires a season and allows filtering by season type and result limit."""
    
    json_response = fetch_search_games_data(
        query=query,
        season=season,
        season_type=season_type,
        limit=limit,
        return_dataframe=False
    )
    return json_response
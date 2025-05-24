from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import Toolkit
from agno.utils.log import logger

from ..api_tools.search import (
    search_players_logic,
    search_teams_logic,
    search_games_logic,
)
from ..api_tools.game_finder import fetch_league_games_logic
from ..core.constants import MAX_SEARCH_RESULTS, MIN_PLAYER_SEARCH_LENGTH
from ..config import settings # For default season
from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID

class SearchToolkit(Toolkit):
    def __init__(self, **kwargs):
        tools = [
            self.search_players,
            self.search_teams,
            self.search_games,
            self.find_league_games,
        ]
        super().__init__(name="search_toolkit", tools=tools, **kwargs)

    def search_players(
        self,
        query: str,
        limit: int = MAX_SEARCH_RESULTS,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Searches for NBA players by name fragment.

        Args:
            query (str): The search query string for the player's name.
                         Must be at least {MIN_PLAYER_SEARCH_LENGTH} characters long.
            limit (int, optional): Maximum number of results to return.
                                   Defaults to {MAX_SEARCH_RESULTS}.
            return_dataframe (bool, optional): If True, returns a tuple containing the JSON response string
                                               and a dictionary of DataFrames: `{'players': df}`.
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False:
                    A JSON string containing a list of matching players or an error message.
                    Expected structure:
                    {{
                        "players": [
                            {{"id": int, "full_name": str, "is_active": bool}},
                            ...
                        ]
                    }}
                If return_dataframe=True:
                    A tuple (json_string, {'players': pd.DataFrame}).
                    The DataFrame has columns: 'id', 'full_name', 'is_active'.
                    CSV cache path is included in json_string under 'dataframe_info'.
        """
        logger.info(f"SearchToolkit: search_players called with query: '{query}'")
        return search_players_logic(query=query, limit=limit, return_dataframe=return_dataframe)

    def search_teams(
        self,
        query: str,
        limit: int = MAX_SEARCH_RESULTS,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Searches for NBA teams by name, city, nickname, or abbreviation.

        Args:
            query (str): The search query string.
            limit (int, optional): Maximum number of results to return.
                                   Defaults to {MAX_SEARCH_RESULTS}.
            return_dataframe (bool, optional): If True, returns a tuple containing the JSON response string
                                               and a dictionary of DataFrames: `{'teams': df}`.
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False:
                    A JSON string containing a list of matching teams or an error message.
                    Expected structure:
                    {{
                        "teams": [
                            {{
                                "id": int, "full_name": str, "abbreviation": str,
                                "nickname": str, "city": str, "state": str, "year_founded": int
                            }},
                            ...
                        ]
                    }}
                If return_dataframe=True:
                    A tuple (json_string, {'teams': pd.DataFrame}).
                    The DataFrame includes columns like 'id', 'full_name', 'abbreviation', etc.
                    CSV cache path is included in json_string under 'dataframe_info'.
        """
        logger.info(f"SearchToolkit: search_teams called with query: '{query}'")
        return search_teams_logic(query=query, limit=limit, return_dataframe=return_dataframe)

    def search_games(
        self,
        query: str,
        season: str,
        season_type: str = SeasonTypeAllStar.regular,
        limit: int = MAX_SEARCH_RESULTS,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Searches for NBA games based on a query (e.g., "TeamA vs TeamB", "Lakers").
        Requires a season to be specified.

        Args:
            query (str): The search query string. Can be a team name or a matchup like "TeamA vs TeamB".
            season (str): The NBA season in YYYY-YY format (e.g., "2023-24"). This is mandatory.
            season_type (str, optional): The type of season.
                                         Defaults to "Regular Season".
                                         Possible values include "Regular Season", "Playoffs", "Pre Season", "All Star".
            limit (int, optional): Maximum number of results to return.
                                   Defaults to {MAX_SEARCH_RESULTS}.
            return_dataframe (bool, optional): If True, returns a tuple containing the JSON response string
                                               and a dictionary of DataFrames: `{'games': df}`.
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False:
                    A JSON string containing a list of matching games or an error message.
                    Games are typically sorted by date in descending order.
                    Expected structure:
                    {{
                        "games": [
                            {{ "GAME_ID": str, "GAME_DATE": str, "MATCHUP": str, "WL": str, ... (other stats) ... }},
                            ...
                        ]
                    }}
                If return_dataframe=True:
                    A tuple (json_string, {'games': pd.DataFrame}).
                    The DataFrame includes columns like 'GAME_ID', 'GAME_DATE', 'MATCHUP', 'WL', 'PTS', etc.
                    CSV cache path is included in json_string under 'dataframe_info'.
        """
        logger.info(f"SearchToolkit: search_games called with query: '{query}', season: {season}")
        return search_games_logic(query=query, season=season, season_type=season_type, limit=limit, return_dataframe=return_dataframe)

    def find_league_games(
        self,
        player_or_team_abbreviation: str = 'T',
        player_id_nullable: Optional[int] = None,
        team_id_nullable: Optional[int] = None,
        season_nullable: Optional[str] = None,
        season_type_nullable: Optional[str] = None,
        league_id_nullable: Optional[str] = LeagueID.nba,
        date_from_nullable: Optional[str] = None,
        date_to_nullable: Optional[str] = None,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches NBA league games using LeagueGameFinder with various filters.
        This tool can find games for a specific player, team, season, or date range.
        Date filtering is applied post-API call due to API instability with date ranges.
        Results for broad queries (no player, team, or season filter) are limited.

        Args:
            player_or_team_abbreviation (str, optional): 'P' for player or 'T' for team. Defaults to 'T'.
            player_id_nullable (Optional[int], optional): Player ID. Required if player_or_team_abbreviation is 'P'.
            team_id_nullable (Optional[int], optional): Team ID.
            season_nullable (Optional[str], optional): Season in 'YYYY-YY' format (e.g., "2023-24").
            season_type_nullable (Optional[str], optional): Season type (e.g., 'Regular Season', 'Playoffs').
            league_id_nullable (Optional[str], optional): League ID. Defaults to NBA "00".
            date_from_nullable (Optional[str], optional): Start date for filtering games, format 'YYYY-MM-DD'.
            date_to_nullable (Optional[str], optional): End date for filtering games, format 'YYYY-MM-DD'.
            return_dataframe (bool, optional): If True, returns a tuple containing the JSON response string
                                               and a dictionary of DataFrames: `{'games': df}`.
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False:
                    A JSON string containing a list of games or an error message.
                    The 'GAME_DATE' in the response is formatted as 'YYYY-MM-DD'.
                    Expected structure:
                    {{
                        "games": [
                            {{
                                "SEASON_ID": str, "TEAM_ID": int, "TEAM_ABBREVIATION": str,
                                "TEAM_NAME": str, "GAME_ID": str, "GAME_DATE": str, "MATCHUP": str,
                                "WL": str, "MIN": int, "PTS": int, ... (other game stats) ...,
                                "GAME_DATE_FORMATTED": str (YYYY-MM-DD)
                            }},
                            ...
                        ]
                    }}
                If return_dataframe=True:
                    A tuple (json_string, {'games': pd.DataFrame}).
                    The DataFrame includes various game statistics and details.
                    CSV cache path is included in json_string under 'dataframe_info'.
        """
        logger.info(f"SearchToolkit: find_league_games called.")
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
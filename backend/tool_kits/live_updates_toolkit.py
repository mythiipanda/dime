from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import Toolkit
from agno.utils.log import logger

# Live data logic functions
from ..api_tools.live_game_tools import fetch_league_scoreboard_logic
from ..api_tools.odds_tools import fetch_odds_data_logic
from ..api_tools.scoreboard_tools import fetch_scoreboard_data_logic as fetch_static_or_live_scoreboard_logic # More comprehensive scoreboard

from nba_api.stats.library.parameters import LeagueID # For default league ID

class LiveUpdatesToolkit(Toolkit):
    def __init__(self, **kwargs):
        tools = [
            self.get_live_league_scoreboard,
            self.get_todays_game_odds,
            self.get_scoreboard_for_date,
        ]
        super().__init__(name="live_updates_toolkit", tools=tools, **kwargs)

    def get_live_league_scoreboard(
        self,
        bypass_cache: bool = False,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches and formats live scoreboard data for current NBA games using nba_api.live.
        This provides real-time game status, scores, and basic team info.
        Cache for this endpoint is typically short-lived (e.g., 10 seconds).

        Args:
            bypass_cache (bool, optional): If True, ignores cached data and fetches fresh data.
                                           Defaults to False.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'games': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string of current game information or an error message.
                    Expected success structure:
                    {{
                        "date": str (YYYY-MM-DD),
                        "games": [
                            {{
                                "game_id": Optional[str],
                                "start_time_utc": str,
                                "status": {{
                                    "clock": Optional[str], "period": int,
                                    "state_code": int (1=Scheduled, 2=In Progress, 3=Final),
                                    "state_text": str (e.g., "Halftime", "Q1 0:00", "Final")
                                }},
                                "home_team": {{ "id": Optional[int], "code": str, "name": Optional[str], "score": int, "record": Optional[str], "wins": Optional[int], "losses": Optional[int] }},
                                "away_team": {{ "id": Optional[int], "code": str, "name": Optional[str], "score": int, "record": Optional[str], "wins": Optional[int], "losses": Optional[int] }}
                            }}, ...
                        ]
                    }}
                If return_dataframe=True: Tuple (json_string, {{'games': pd.DataFrame}}).
                    The DataFrame flattens the game information for easier analysis.
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"LiveUpdatesToolkit: get_live_league_scoreboard called, bypass_cache: {bypass_cache}")
        return fetch_league_scoreboard_logic(
            bypass_cache=bypass_cache,
            return_dataframe=return_dataframe
        )

    def get_todays_game_odds(
        self,
        bypass_cache: bool = False,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches live betting odds for today's NBA games.
        Data includes various markets (moneyline, spread, total) from different bookmakers.
        Cache for this endpoint is typically around 1 hour.

        Args:
            bypass_cache (bool, optional): If True, ignores cached data and fetches fresh data.
                                           Defaults to False.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'odds': DataFrame}}).
                                               The DataFrame flattens the game-market-book-outcome structure.
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string containing a list of today's games with their odds.
                    Expected success structure:
                    {{
                        "games": [
                            {{
                                "gameId": str, "awayTeamId": int, "homeTeamId": int, "gameTime": str,
                                "gameStatus": int, "gameStatusText": str,
                                "markets": [
                                    {{
                                        "marketId": str, "name": str, // e.g., "Moneyline"
                                        "books": [
                                            {{
                                                "bookId": str, "name": str, // e.g., "DraftKings"
                                                "outcomes": [
                                                    {{ "type": str, "odds": str, "value": Optional[str] }}
                                                ]
                                            }}
                                        ]
                                    }}
                                ]
                            }}
                        ]
                    }}
                    Returns {{"games": []}} if no odds data or an error occurs.
                If return_dataframe=True: Tuple (json_string, {{'odds': pd.DataFrame}}).
                    The DataFrame flattens the nested structure into one record per game-market-book-outcome.
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"LiveUpdatesToolkit: get_todays_game_odds called, bypass_cache: {bypass_cache}")
        return fetch_odds_data_logic(
            bypass_cache=bypass_cache,
            return_dataframe=return_dataframe
        )

    def get_scoreboard_for_date(
        self,
        game_date: Optional[str] = None,
        league_id: str = LeagueID.nba,
        day_offset: int = 0,
        bypass_cache: bool = False,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches NBA scoreboard data for a specific date.
        Uses live API for today's date, static API (scoreboardv2) for past/future dates or if live is stale.

        Args:
            game_date (Optional[str], optional): Date for the scoreboard in YYYY-MM-DD format.
                                                 Defaults to the current local date if None.
            league_id (str, optional): League ID. Defaults to "00" (NBA).
                                       Primarily applies to the static ScoreboardV2 for non-current dates.
            day_offset (int, optional): Day offset from `game_date`. Defaults to 0.
                                        Primarily applies to static ScoreboardV2.
            bypass_cache (bool, optional): If True, ignores cached data. Defaults to False.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, dictionary of DataFrames).
                                               DataFrames: {{'games': df_games, 'teams': df_teams_combined}}.
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with formatted scoreboard data or an error.
                    Expected success structure:
                    {{
                        "gameDate": str (YYYY-MM-DD),
                        "games": [
                            {{
                                "gameId": str, "gameStatus": int, "gameStatusText": str, "period": int,
                                "gameClock": Optional[str],
                                "homeTeam": {{"teamId": int, "teamTricode": str, "score": int, "wins": Optional[int], "losses": Optional[int]}},
                                "awayTeam": {{"teamId": int, "teamTricode": str, "score": int, "wins": Optional[int], "losses": Optional[int]}},
                                "gameEt": str // Game start time (UTC for live, EST for static)
                            }}, ...
                        ]
                    }}
                    Returns {{"games": []}} if no games are found.
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict contains 'games' (one row per game) and 'teams' (one row per team per game).
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        effective_date = game_date if game_date else datetime.now().strftime('%Y-%m-%d')
        logger.info(f"LiveUpdatesToolkit: get_scoreboard_for_date called for date: {effective_date}")
        return fetch_static_or_live_scoreboard_logic(
            game_date=game_date,
            league_id=league_id,
            day_offset=day_offset,
            bypass_cache=bypass_cache,
            return_dataframe=return_dataframe
        )
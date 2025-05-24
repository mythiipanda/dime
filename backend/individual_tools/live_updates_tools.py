from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import tool
from agno.utils.log import logger
import datetime # Needed for get_scoreboard_for_date if game_date is None (handled by logic func though)

# Live data logic functions
from ..api_tools.live_game_tools import fetch_league_scoreboard_logic
from ..api_tools.odds_tools import fetch_odds_data_logic
from ..api_tools.scoreboard_tools import fetch_scoreboard_data_logic as fetch_static_or_live_scoreboard_logic

from nba_api.stats.library.parameters import LeagueID # For default league ID

@tool
def get_live_league_scoreboard(
    bypass_cache: bool = False,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches and formats live scoreboard data for current NBA games.
    Args:
        bypass_cache (bool): If True, ignores cached data. Defaults to False.
        return_dataframe (bool): If True, returns (JSON, {{'games': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_live_league_scoreboard called, bypass_cache: {bypass_cache}")
    return fetch_league_scoreboard_logic(
        bypass_cache=bypass_cache,
        return_dataframe=return_dataframe
    )

@tool
def get_todays_game_odds(
    bypass_cache: bool = False,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches live betting odds for today's NBA games.
    Args:
        bypass_cache (bool): If True, ignores cached data. Defaults to False.
        return_dataframe (bool): If True, returns (JSON, {{'odds': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_todays_game_odds called, bypass_cache: {bypass_cache}")
    return fetch_odds_data_logic(
        bypass_cache=bypass_cache,
        return_dataframe=return_dataframe
    )

@tool
def get_scoreboard_for_date(
    game_date: Optional[str] = None, # YYYY-MM-DD format
    league_id: str = LeagueID.nba,
    day_offset: int = 0,
    bypass_cache: bool = False,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches NBA scoreboard data for a specific date (live or static).
    Args:
        game_date (Optional[str]): Date (YYYY-MM-DD). Defaults to current date.
        league_id (str): League ID. Defaults to "00" (NBA).
        day_offset (int): Day offset from game_date. Defaults to 0.
        bypass_cache (bool): If True, ignores cached data. Defaults to False.
        return_dataframe (bool): If True, returns (JSON, Dict of DataFrames). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    # The logic function fetch_static_or_live_scoreboard_logic handles game_date being None
    effective_date_str = game_date if game_date else datetime.date.today().strftime('%Y-%m-%d')
    logger.info(f"Tool: get_scoreboard_for_date called for date: {effective_date_str}, league_id: {league_id}, offset: {day_offset}")
    return fetch_static_or_live_scoreboard_logic(
        game_date=game_date, # Pass None if not provided, logic function will handle it
        league_id=league_id,
        day_offset=day_offset,
        bypass_cache=bypass_cache,
        return_dataframe=return_dataframe
    ) 
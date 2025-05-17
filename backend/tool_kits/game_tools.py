"""
This module provides a toolkit of game-related functions exposed as agent tools.
These tools wrap specific logic functions from `backend.api_tools` to fetch
various NBA game statistics and information.
"""
import logging
from typing import Optional
from agno.tools import tool
from nba_api.stats.library.parameters import LeagueID, RunType, SeasonTypeAllStar # Added SeasonTypeAllStar

# Import specific logic functions for game tools
from backend.api_tools.game_finder import fetch_league_games_logic
from backend.api_tools.game_boxscores import (
    fetch_boxscore_traditional_logic,
    fetch_boxscore_advanced_logic,
    fetch_boxscore_four_factors_logic,
    fetch_boxscore_usage_logic,
    fetch_boxscore_defensive_logic,
    fetch_boxscore_summary_logic
)
from backend.api_tools.game_playbyplay import fetch_playbyplay_logic
from backend.api_tools.game_visuals_analytics import (
    fetch_shotchart_logic as fetch_game_shotchart_logic, # Alias to avoid confusion
    fetch_win_probability_logic
)

logger = logging.getLogger(__name__)

@tool
def find_games(
    player_or_team_abbreviation: str = 'T',
    player_id_nullable: Optional[int] = None,
    team_id_nullable: Optional[int] = None,
    season_nullable: Optional[str] = None,
    season_type_nullable: Optional[str] = None, # e.g., SeasonTypeAllStar.regular
    league_id_nullable: Optional[str] = LeagueID.nba,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None
) -> str:
    """
    Finds games based on various criteria using the LeagueGameFinder endpoint.

    Args:
        player_or_team_abbreviation (str, optional): Specify 'P' for player or 'T' for team. Defaults to 'T'.
        player_id_nullable (Optional[int], optional): Player's ID (required if player_or_team_abbreviation='P').
        team_id_nullable (Optional[int], optional): Team's ID (required if player_or_team_abbreviation='T').
        season_nullable (Optional[str], optional): Season in YYYY-YY format (e.g., "2023-24").
        season_type_nullable (Optional[str], optional): Type of season (e.g., "Regular Season", "Playoffs").
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`.
        league_id_nullable (Optional[str], optional): League ID. Defaults to "00" (NBA).
        date_from_nullable (Optional[str], optional): Start date in YYYY-MM-DD format.
        date_to_nullable (Optional[str], optional): End date in YYYY-MM-DD format.

    Returns:
        str: JSON string containing a list of found games or an error message.
    """
    logger.debug(f"Tool 'find_games' called with params: player_or_team={player_or_team_abbreviation}, player_id={player_id_nullable}, team_id={team_id_nullable}, season={season_nullable}, date_from={date_from_nullable}, date_to={date_to_nullable}")
    result = fetch_league_games_logic(
        player_or_team_abbreviation=player_or_team_abbreviation,
        player_id_nullable=player_id_nullable,
        team_id_nullable=team_id_nullable,
        season_nullable=season_nullable,
        season_type_nullable=season_type_nullable,
        league_id_nullable=league_id_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable
    )
    return result

@tool
def get_boxscore_traditional(game_id: str, start_period: int = 0, end_period: int = 0, start_range: int = 0, end_range: int = 0, range_type: int = 0) -> str:
    """
    Fetches the traditional box score (BoxScoreTraditionalV3) for a specific game.

    Args:
        game_id (str): The ID of the game.
        start_period (int, optional): Starting period number (0 for full game). Defaults to 0.
        end_period (int, optional): Ending period number (0 for full game). Defaults to 0.
        start_range (int, optional): Start of the range for range-based queries. Defaults to 0.
        end_range (int, optional): End of the range for range-based queries. Defaults to 0.
        range_type (int, optional): Type of range. Defaults to 0.


    Returns:
        str: JSON string with traditional box score data.
    """
    logger.debug(f"Tool 'get_boxscore_traditional' called for game_id '{game_id}', periods {start_period}-{end_period}")
    # Note: fetch_boxscore_traditional_logic in api_tools was updated to include start_range, end_range, range_type
    result = fetch_boxscore_traditional_logic(game_id, start_period=start_period, end_period=end_period, start_range=start_range, end_range=end_range, range_type=range_type)
    return result

@tool
def get_play_by_play(
    game_id: str,
    start_period: int = 0, # 0 for all
    end_period: int = 0   # 0 for all
) -> str:
    """
    Fetches the play-by-play data for a specific game (PlayByPlayV3).

    Args:
        game_id (str): The ID of the game.
        start_period (int, optional): Starting period number (0 for full game). Defaults to 0.
        end_period (int, optional): Ending period number (0 for full game). Defaults to 0.

    Returns:
        str: JSON string with play-by-play data.
    """
    logger.debug(f"Tool 'get_play_by_play' called for game_id '{game_id}', periods '{start_period}'-'{end_period}'")
    result_str = fetch_playbyplay_logic(game_id=game_id, start_period=start_period, end_period=end_period)
    return result_str

@tool
def get_game_shotchart(game_id: str) -> str:
    """
    Fetches shot chart details for all players in a specific game.

    Args:
        game_id (str): The ID of the game.

    Returns:
        str: JSON string with game shot chart data, including shots by team and league averages.
    """
    logger.debug(f"Tool 'get_game_shotchart' called for game '{game_id}'")
    result = fetch_game_shotchart_logic(game_id=game_id) # Uses aliased import
    return result

@tool
def get_boxscore_advanced(game_id: str, start_period: int = 0, end_period: int = 0, start_range: int = 0, end_range: int = 0) -> str:
    """
    Fetches advanced box score data (BoxScoreAdvancedV3) for a game.

    Args:
        game_id (str): The ID of the game.
        start_period (int, optional): Starting period number (0 for full game). Defaults to 0.
        end_period (int, optional): Ending period number (0 for full game). Defaults to 0.
        start_range (int, optional): Start of the range for range-based queries. Defaults to 0.
        end_range (int, optional): End of the range for range-based queries. Defaults to 0.

    Returns:
        str: JSON string with advanced box score data.
    """
    logger.debug(f"Tool 'get_boxscore_advanced' called for game_id '{game_id}'")
    result = fetch_boxscore_advanced_logic(game_id, start_period=start_period, end_period=end_period, start_range=start_range, end_range=end_range)
    return result

@tool
def get_boxscore_four_factors(game_id: str, start_period: int = 0, end_period: int = 0) -> str:
    """
    Fetches box score Four Factors (BoxScoreFourFactorsV3) for a game.

    Args:
        game_id (str): The ID of the game.
        start_period (int, optional): Starting period number (0 for full game). Defaults to 0.
        end_period (int, optional): Ending period number (0 for full game). Defaults to 0.

    Returns:
        str: JSON string with Four Factors box score data.
    """
    logger.debug(f"Tool 'get_boxscore_four_factors' called for game_id '{game_id}', periods {start_period}-{end_period}")
    result = fetch_boxscore_four_factors_logic(game_id, start_period=start_period, end_period=end_period)
    return result

@tool
def get_boxscore_usage(game_id: str) -> str:
    """
    Fetches box score usage statistics (BoxScoreUsageV3) for a game.

    Args:
        game_id (str): The ID of the game.

    Returns:
        str: JSON string with usage statistics for players and teams.
    """
    logger.debug(f"Tool 'get_boxscore_usage' called for game_id '{game_id}'")
    result = fetch_boxscore_usage_logic(game_id)
    return result

@tool
def get_boxscore_defensive(game_id: str) -> str:
    """
    Fetches box score defensive statistics (BoxScoreDefensiveV2) for a game.

    Args:
        game_id (str): The ID of the game.

    Returns:
        str: JSON string with defensive statistics for players and teams.
    """
    logger.debug(f"Tool 'get_boxscore_defensive' called for game_id '{game_id}'")
    result = fetch_boxscore_defensive_logic(game_id)
    return result

@tool
def get_boxscore_summary(game_id: str) -> str:
    """
    Fetches a comprehensive summary of a game (BoxScoreSummaryV2), including line scores,
    officials, inactive players, etc.

    Args:
        game_id (str): The ID of the game.

    Returns:
        str: JSON string with game summary datasets.
    """
    logger.debug(f"Tool 'get_boxscore_summary' called for game_id '{game_id}'")
    result = fetch_boxscore_summary_logic(game_id=game_id)
    return result

@tool
def get_win_probability(game_id: str, run_type: str = RunType.default) -> str:
    """
    Fetches win probability data throughout a specific game (WinProbabilityPBP).

    Args:
        game_id (str): The ID of the game.
        run_type (str, optional): Type of run for win probability.
            Valid values from `nba_api.stats.library.parameters.RunType`. Defaults to "Default".

    Returns:
        str: JSON string with win probability data including game info and PBP events.
    """
    logger.debug(f"Tool 'get_win_probability' called for game_id '{game_id}', run_type '{run_type}'")
    result = fetch_win_probability_logic(game_id, run_type=run_type)
    return result
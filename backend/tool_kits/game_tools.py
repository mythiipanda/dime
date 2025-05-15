import logging
from typing import Optional
import datetime
from agno.tools import tool
from nba_api.stats.library.parameters import LeagueID, RunType
from backend.config import settings # Assuming settings might be used for defaults like CURRENT_NBA_SEASON

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
    fetch_shotchart_logic as fetch_game_shotchart_logic, # Alias to avoid confusion if player shotchart is ever in same context
    fetch_win_probability_logic
)

logger = logging.getLogger(__name__)

@tool
def find_games(
    player_or_team: str = 'T',
    player_id: Optional[int] = None,
    team_id: Optional[int] = None,
    season: Optional[str] = None,
    season_type: Optional[str] = None,
    league_id: Optional[str] = LeagueID.nba,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Finds games based on various criteria.
    Args: player_or_team, player_id, team_id, season, season_type, league_id, date_from, date_to.
    Returns: JSON string with found games.
    """
    logger.debug(f"Tool 'find_games' called with params: player_or_team={player_or_team}, player_id={player_id}, team_id={team_id}, season={season}, date_from={date_from}, date_to={date_to}")
    result = fetch_league_games_logic(
        player_or_team_abbreviation=player_or_team,
        player_id_nullable=player_id,
        team_id_nullable=team_id,
        season_nullable=season,
        season_type_nullable=season_type,
        league_id_nullable=league_id,
        date_from_nullable=date_from,
        date_to_nullable=date_to
    )
    return result

@tool
def get_boxscore_traditional(game_id: str, start_period: int = 0, end_period: int = 0) -> str:
    """
    Fetches the traditional box score for a game.
    Args: game_id, start_period, end_period.
    Returns: JSON string with traditional box score data.
    """
    logger.debug(f"Tool 'get_boxscore_traditional' called for game_id '{game_id}', periods {start_period}-{end_period}")
    result = fetch_boxscore_traditional_logic(game_id, start_period=start_period, end_period=end_period)
    return result

@tool
def get_play_by_play(
    game_id: str,
    start_period: int = 0,
    end_period: int = 0
) -> str:
    """
    Fetches the play-by-play data for a game.
    Args: game_id, start_period, end_period.
    Returns: JSON string with play-by-play data.
    """
    logger.debug(f"Tool 'get_play_by_play' called for game_id '{game_id}', periods '{start_period}'-'{end_period}'")
    result_str = fetch_playbyplay_logic(game_id=game_id, start_period=start_period, end_period=end_period)
    return result_str

@tool
def get_game_shotchart(game_id: str) -> str:
    """
    Fetches shot chart details for all players in a specific game.
    Args: game_id.
    Returns: JSON string with game shot chart data.
    """
    logger.debug(f"Tool 'get_game_shotchart' called for game '{game_id}'")
    result = fetch_game_shotchart_logic(game_id=game_id)
    return result

@tool
def get_boxscore_advanced(game_id: str, start_period: int = 0, end_period: int = 0, start_range: int = 0, end_range: int = 0) -> str:
    """
    Fetches advanced box score data for a game.
    Args: game_id, start_period, end_period, start_range, end_range.
    Returns: JSON string with advanced box score data.
    """
    logger.debug(f"Tool 'get_boxscore_advanced' called for game_id '{game_id}'")
    result = fetch_boxscore_advanced_logic(game_id, end_period=end_period, end_range=end_range, start_period=start_period, start_range=start_range)
    return result

@tool
def get_boxscore_four_factors(game_id: str, start_period: int = 0, end_period: int = 0) -> str:
    """
    Fetches box score Four Factors for a game.
    Args: game_id, start_period, end_period.
    Returns: JSON string with Four Factors box score data.
    """
    logger.debug(f"Tool 'get_boxscore_four_factors' called for game_id '{game_id}', periods {start_period}-{end_period}")
    result = fetch_boxscore_four_factors_logic(game_id, start_period=start_period, end_period=end_period)
    return result

@tool
def get_boxscore_usage(game_id: str) -> str:
    """
    Fetches box score usage statistics for a game.
    Args: game_id.
    Returns: JSON string with usage statistics.
    """
    logger.debug(f"Tool 'get_boxscore_usage' called for game_id '{game_id}'")
    result = fetch_boxscore_usage_logic(game_id)
    return result

@tool
def get_boxscore_defensive(game_id: str) -> str:
    """
    Fetches box score defensive statistics for a game.
    Args: game_id.
    Returns: JSON string with defensive statistics.
    """
    logger.debug(f"Tool 'get_boxscore_defensive' called for game_id '{game_id}'")
    result = fetch_boxscore_defensive_logic(game_id)
    return result

@tool
def get_boxscore_summary(game_id: str) -> str:
    """
    Fetches a summary of a game.
    Args: game_id.
    Returns: JSON string with game summary datasets.
    """
    logger.debug(f"Tool 'get_boxscore_summary' called for game_id '{game_id}'")
    result = fetch_boxscore_summary_logic(game_id=game_id)
    return result

@tool
def get_win_probability(game_id: str, run_type: str = RunType.default) -> str:
    """
    Fetches win probability data throughout a specific game.
    Args: game_id, run_type.
    Returns: JSON string with win probability data.
    """
    logger.debug(f"Tool 'get_win_probability' called for game_id '{game_id}'")
    result = fetch_win_probability_logic(game_id, run_type)
    return result 
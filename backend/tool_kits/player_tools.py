import logging
from typing import Optional
from agno.tools import tool
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, PerMode36, LeagueID
from backend.config import settings
# Import specific logic functions for player tools
from backend.api_tools.player_common_info import fetch_player_info_logic
from backend.api_tools.player_gamelogs import fetch_player_gamelog_logic
from backend.api_tools.player_career_data import fetch_player_career_stats_logic, fetch_player_awards_logic
from backend.api_tools.player_dashboard_stats import fetch_player_profile_logic
from backend.api_tools.player_aggregate_stats import fetch_player_stats_logic
from backend.api_tools.analyze import analyze_player_stats_logic
from backend.api_tools.player_estimated_metrics import fetch_player_estimated_metrics_logic
from backend.api_tools.player_dashboard_team_performance import fetch_player_dashboard_by_team_performance_logic

logger = logging.getLogger(__name__)

@tool
def get_player_info(player_name: str) -> str:
    """
    Fetches basic player information, including biographical details and headline career statistics.

    Args:
        player_name (str): The full name of the player (e.g., "LeBron James").

    Returns:
        str: JSON string containing player information and headline stats.
    """
    logger.debug(f"Tool 'get_player_info' called for '{player_name}'")
    result = fetch_player_info_logic(player_name)
    return result

@tool
def get_player_gamelog(player_name: str, season: str, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches the game-by-game statistics for a specific player in a given season and season type.

    Args:
        player_name (str): The full name of the player (e.g., "Jayson Tatum").
        season (str): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
        season_type (str, optional): The type of season. Defaults to "Regular Season".

    Returns:
        str: JSON string containing a list of game log entries.
    """
    logger.debug(f"Tool 'get_player_gamelog' called for '{player_name}', season '{season}', type '{season_type}'")
    result = fetch_player_gamelog_logic(player_name, season, season_type)
    return result

@tool
def get_player_career_stats(player_name: str, per_mode: str = PerMode36.per_game) -> str:
    """
    Fetches player career statistics, including Regular Season and Playoffs if available, aggregated by season.
    Do NOT try to pass a 'season_type' argument to this tool.

    Args:
        player_name (str): The full name of the player (e.g., "Kevin Durant").
        per_mode (str, optional): The statistical mode. Defaults to "PerGame".

    Returns:
        str: JSON string containing career statistics data.
    """
    logger.debug(f"Tool 'get_player_career_stats' called for '{player_name}', per_mode '{per_mode}'")
    result = fetch_player_career_stats_logic(player_name, per_mode)
    return result

@tool
def get_player_awards(player_name: str) -> str:
    """
    Fetches a list of awards won by a specific player throughout their career.

    Args:
        player_name (str): The full name of the player (e.g., "Michael Jordan").

    Returns:
        str: JSON string containing a list of awards.
    """
    logger.debug(f"Tool 'get_player_awards' called for '{player_name}'")
    result = fetch_player_awards_logic(player_name)
    return result

@tool
def get_player_profile(player_name: str, per_mode: str = PerModeDetailed.per_game) -> str:
    """
    Fetches a comprehensive player profile, including biographical information, career stats,
    next game details, and season highlights.

    Args:
        player_name (str): The full name of the player (e.g., "Giannis Antetokounmpo").
        per_mode (str, optional): The statistical mode for career stats. Defaults to "PerGame".

    Returns:
        str: JSON string containing the player's profile.
    """
    logger.debug(f"Tool 'get_player_profile' called for {player_name}, per_mode {per_mode}")
    result = fetch_player_profile_logic(player_name, per_mode)
    return result

@tool
def get_player_aggregate_stats(player_name: str, season: str = settings.CURRENT_NBA_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches an aggregated set of player statistics for a specific season, including various dashboard views.

    Args:
        player_name (str): The full name of the player (e.g., "Trae Young").
        season (str, optional): The NBA season identifier. Defaults to the current season.
        season_type (str, optional): The type of season. Defaults to "Regular Season".

    Returns:
        str: JSON string containing aggregated player statistics.
    """
    logger.debug(f"Tool 'get_player_aggregate_stats' called for {player_name}, season {season}, type {season_type}")
    result = fetch_player_stats_logic(player_name=player_name, season=season, season_type=season_type)
    return result

@tool
def get_player_analysis(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    league_id: str = LeagueID.nba
) -> str:
    """
    Provides an analysis of a player's statistics, often comparing across seasons or providing dashboard views.
    This is a wrapper around `analyze_player_stats_logic`.

    Args:
        player_name (str): The full name of the player.
        season (str, optional): The primary NBA season for analysis. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode for dashboard stats. Defaults to "PerGame".
        league_id (str, optional): League ID. Defaults to "00".

    Returns:
        str: JSON string containing player analysis and dashboard statistics.
    """
    logger.debug(f"Tool 'get_player_analysis' called for Player: {player_name}, Season: {season}")
    return analyze_player_stats_logic(player_name, season, season_type, per_mode, league_id)

@tool
def get_player_insights(player_name: str, season: str = settings.CURRENT_NBA_SEASON, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerModeDetailed.per_game, league_id: str = LeagueID.nba) -> str:
    """
    Fetches overall player dashboard statistics for a given season, type, and mode, providing insights into performance.
    This is a wrapper around `analyze_player_stats_logic`.

    Args:
        player_name (str): The full name of the player (e.g., "Stephen Curry").
        season (str, optional): The primary NBA season for analysis. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
        league_id (str, optional): League ID. Defaults to "00".

    Returns:
        str: JSON string containing player dashboard statistics.
    """
    logger.debug(
        f"Tool 'get_player_insights' called for Player: {player_name}, Season: {season}, Type: {season_type}, "
        f"Mode: {per_mode}, League: {league_id}"
    )
    result = analyze_player_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        league_id=league_id
    )
    return result

@tool
def get_player_estimated_metrics(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches player estimated metrics (E_OFF_RATING, E_DEF_RATING, E_NET_RATING, etc.)
    for a given season and season type.

    Args:
        season (str, optional): NBA season in 'YYYY-YY' format. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        league_id (str, optional): League ID. Defaults to "00".

    Returns:
        str: JSON string containing player estimated metrics.
    """
    logger.debug(f"Tool 'get_player_estimated_metrics' called for Season: {season}, Type: {season_type}, League: {league_id}")
    return fetch_player_estimated_metrics_logic(
        season=season,
        season_type=season_type,
        league_id=league_id
    ) 

@tool
def get_player_dashboard_by_team_performance(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.totals,
    measure_type: str = "Base",
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    pace_adjust: str = "N",
    period: int = 0,
    plus_minus: str = "N",
    rank: str = "N",
    vs_division: str = None,
    vs_conference: str = None,
    shot_clock_range: str = None,
    season_segment: str = None,
    po_round: int = None,
    outcome: str = None,
    location: str = None,
    league_id: str = None,
    game_segment: str = None,
    date_from: str = None,
    date_to: str = None
) -> str:
    """
    Fetches a player's impact on their team's performance using the PlayerDashboardByTeamPerformance NBA API endpoint.

    Args:
        player_name (str): Full name of the player (e.g., "LeBron James").
        season (str): NBA season in 'YYYY-YY' format.
        season_type (str): "Regular Season", "Playoffs", or "Pre Season".
        per_mode (str): Statistical mode (e.g., "Totals", "PerGame").
        measure_type (str): "Base", "Advanced", etc.
        last_n_games (int): Number of most recent games to include.
        month (int): Month filter (0 for all).
        opponent_team_id (int): Opponent team ID (0 for all).
        pace_adjust (str): "Y" or "N".
        period (int): Period filter (0 for all).
        plus_minus (str): "Y" or "N".
        rank (str): "Y" or "N".
        vs_division (str, optional): Division filter.
        vs_conference (str, optional): Conference filter.
        shot_clock_range (str, optional): Shot clock range filter.
        season_segment (str, optional): "Pre All-Star" or "Post All-Star".
        po_round (int, optional): Playoff round filter.
        outcome (str, optional): "W" or "L".
        location (str, optional): "Home" or "Road".
        league_id (str, optional): League ID.
        game_segment (str, optional): "First Half", "Second Half", "Overtime".
        date_from (str, optional): Start date (YYYY-MM-DD).
        date_to (str, optional): End date (YYYY-MM-DD).

    Returns:
        str: JSON string with team performance dashboard data.
    """
    logger.debug(f"Tool 'get_player_dashboard_by_team_performance' called for {player_name}, season {season}")
    return fetch_player_dashboard_by_team_performance_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        last_n_games=last_n_games,
        month=month,
        opponent_team_id=opponent_team_id,
        pace_adjust=pace_adjust,
        period=period,
        plus_minus=plus_minus,
        rank=rank,
        vs_division=vs_division,
        vs_conference=vs_conference,
        shot_clock_range=shot_clock_range,
        season_segment=season_segment,
        po_round=po_round,
        outcome=outcome,
        location=location,
        league_id=league_id,
        game_segment=game_segment,
        date_from=date_from,
        date_to=date_to
    )
import logging
from typing import Optional
from agno.tools import tool
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, PerModeSimple, LeagueID
from backend.config import settings
# Import specific logic functions for tracking tools
from backend.api_tools.player_clutch import fetch_player_clutch_stats_logic
from backend.api_tools.player_passing import fetch_player_passing_stats_logic
from backend.api_tools.player_rebounding import fetch_player_rebounding_stats_logic
from backend.api_tools.player_shooting_tracking import fetch_player_shots_tracking_logic
from backend.api_tools.player_shot_charts import fetch_player_shotchart_logic
from backend.api_tools.player_dashboard_stats import fetch_player_defense_logic, fetch_player_hustle_stats_logic
from backend.api_tools.team_passing_tracking import fetch_team_passing_stats_logic
from backend.api_tools.team_shooting_tracking import fetch_team_shooting_stats_logic
from backend.api_tools.team_rebounding_tracking import fetch_team_rebounding_stats_logic

logger = logging.getLogger(__name__)

# Player Tracking Tools
@tool
def get_player_clutch_stats(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    measure_type: str = "Base",
    per_mode: str = "Totals"
) -> str:
    """
    Fetches player statistics in clutch situations.
    Args: player_name, season, season_type, measure_type, per_mode.
    Returns: JSON string with clutch statistics.
    """
    logger.debug(f"Tool 'get_player_clutch_stats' called for '{player_name}', season '{season}', type '{season_type}', measure '{measure_type}', mode '{per_mode}'")
    result = fetch_player_clutch_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode
    )
    return result

@tool
def get_player_passing_stats(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game
) -> str:
    """
    Fetches player passing tracking statistics.
    Args: player_name, season, season_type, per_mode.
    Returns: JSON string with player passing statistics.
    """
    logger.debug(f"Tool 'get_player_passing_stats' called for {player_name}, season {season}, type {season_type}, mode {per_mode}")
    result = fetch_player_passing_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    return result

@tool
def get_player_rebounding_stats(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game
) -> str:
    """
    Fetches player rebounding tracking statistics.
    Args: player_name, season, season_type, per_mode.
    Returns: JSON string with player rebounding statistics.
    """
    logger.debug(f"Tool 'get_player_rebounding_stats' called for {player_name}, season {season}, type {season_type}, mode {per_mode}")
    result = fetch_player_rebounding_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    return result

@tool
def get_player_shots_tracking(player_name: str, season: str = settings.CURRENT_NBA_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches detailed player shooting statistics by various factors.
    Args: player_name, season, season_type.
    Returns: JSON string with detailed shot tracking statistics.
    """
    logger.debug(f"Tool 'get_player_shots_tracking' called for player_name '{player_name}', season '{season}', type '{season_type}'")
    result = fetch_player_shots_tracking_logic(player_name=player_name, season=season, season_type=season_type)
    return result

@tool
def get_player_shotchart(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    """
    Fetches detailed shot chart data for a player.
    Args: player_name, season, season_type.
    Returns: JSON string with shot chart data and visualization path.
    """
    logger.debug(f"Tool 'get_player_shotchart' called for {player_name}, season {season}, type {season_type}")
    result = fetch_player_shotchart_logic(
        player_name=player_name,
        season=season,
        season_type=season_type
    )
    return result

@tool
def get_player_defense_stats(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> str:
    """
    Fetches detailed defensive statistics for a player.
    Args: player_name, season, season_type, per_mode.
    Returns: JSON string with defensive statistics.
    """
    logger.debug(f"Tool 'get_player_defense_stats' called for {player_name}, season {season}, per_mode {per_mode}")
    result = fetch_player_defense_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    return result

@tool
def get_player_hustle_stats(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    player_name: Optional[str] = None,
    team_id: Optional[int] = None,
    league_id: str = LeagueID.nba,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Fetches player or league-wide hustle statistics.
    Args: season, season_type, per_mode, player_name, team_id, league_id, date_from, date_to.
    Returns: JSON string with hustle statistics.
    """
    logger.debug(
        f"Tool 'get_player_hustle_stats' called for Season: {season}, Type: {season_type}, Mode: {per_mode}, "
        f"Player: {player_name}, Team: {team_id}, League: {league_id}"
    )
    result = fetch_player_hustle_stats_logic(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        player_name=player_name,
        team_id=team_id,
        league_id=league_id,
        date_from=date_from,
        date_to=date_to
    )
    return result

# Team Tracking Tools
@tool
def get_team_passing_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game
) -> str:
    """
    Fetches team passing tracking statistics.
    Args: team_identifier, season, season_type, per_mode.
    Returns: JSON string with team passing statistics.
    """
    logger.debug(f"Tool 'get_team_passing_stats' called for {team_identifier}, season {season}, mode {per_mode}")
    result = fetch_team_passing_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    return result

@tool
def get_team_shooting_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game
) -> str:
    """
    Fetches team shooting tracking statistics.
    Args: team_identifier, season, season_type, per_mode.
    Returns: JSON string with team shooting statistics.
    """
    logger.debug(f"Tool 'get_team_shooting_stats' called for {team_identifier}, season {season}, mode {per_mode}")
    result = fetch_team_shooting_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    return result

@tool
def get_team_rebounding_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game
) -> str:
    """
    Fetches team rebounding tracking statistics.
    Args: team_identifier, season, season_type, per_mode.
    Returns: JSON string with team rebounding statistics.
    """
    logger.debug(f"Tool 'get_team_rebounding_stats' called for {team_identifier}, season {season}, mode {per_mode}")
    result = fetch_team_rebounding_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    return result 
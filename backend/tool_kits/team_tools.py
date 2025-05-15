import logging
from typing import Optional
from agno.tools import tool
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, LeagueID
from backend.config import settings
# Import specific logic functions for team tools
from backend.api_tools.team_info_roster import fetch_team_info_and_roster_logic
from backend.api_tools.team_general_stats import fetch_team_stats_logic

logger = logging.getLogger(__name__)

@tool
def get_team_info_and_roster(team_identifier: str, season: str = settings.CURRENT_NBA_SEASON) -> str:
    """
    Fetches comprehensive team information including basic details, conference/division ranks,
    historical performance, current season roster, and coaching staff.

    Args:
        team_identifier (str): The team's name, abbreviation, or ID.
        season (str, optional): The NBA season identifier. Defaults to current season.

    Returns:
        str: JSON string containing detailed team data.
    """
    logger.debug(f"Tool 'get_team_info_and_roster' called for '{team_identifier}', season '{season}'")
    result = fetch_team_info_and_roster_logic(team_identifier, season)
    return result

@tool
def get_team_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    measure_type: str = "Base",
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches comprehensive team statistics for a given season, with various filtering options.

    Args:
        team_identifier (str): The team's name, abbreviation, or ID.
        season (str, optional): The NBA season. Defaults to current season.
        season_type (str, optional): The type of season. Defaults to "Regular Season".
        per_mode (str, optional): The statistical mode. Defaults to "PerGame".
        measure_type (str, optional): The category of stats. Defaults to "Base".
        opponent_team_id (int, optional): Filter stats against a specific opponent team ID. Defaults to 0.
        date_from (str, optional): Start date for filtering games (YYYY-MM-DD). Defaults to None.
        date_to (str, optional): End date for filtering games (YYYY-MM-DD). Defaults to None.
        league_id (str, optional): The league ID. Defaults to "00" (NBA).

    Returns:
        str: JSON string containing team statistics.
    """
    logger.debug(f"Tool 'get_team_stats' called for '{team_identifier}', season '{season}', measure '{measure_type}'")
    result = fetch_team_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        opponent_team_id=opponent_team_id,
        date_from=date_from,
        date_to=date_to,
        league_id=league_id
    )
    return result 
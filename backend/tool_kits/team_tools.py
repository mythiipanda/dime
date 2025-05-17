"""
This module provides a toolkit of team-related functions exposed as agent tools.
These tools wrap specific logic functions from `backend.api_tools` to fetch
various NBA team statistics and information.
"""
import logging
from typing import Optional
from agno.tools import tool
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, LeagueID, MeasureTypeDetailedDefense
from backend.config import settings
# Import specific logic functions for team tools
from backend.api_tools.team_info_roster import fetch_team_info_and_roster_logic
from backend.api_tools.team_general_stats import fetch_team_stats_logic

logger = logging.getLogger(__name__)

@tool
def get_team_info_and_roster(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular, # Added season_type for consistency with underlying logic
    league_id: str = LeagueID.nba # Added league_id for consistency
) -> str:
    """
    Fetches comprehensive team information for a specific season, including basic details,
    conference/division ranks, current season roster, and coaching staff.

    Args:
        team_identifier (str): The team's name, abbreviation, or ID (e.g., "Boston Celtics", "BOS", "1610612738").
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24"). Defaults to current season.
        season_type (str, optional): The type of season (e.g., "Regular Season", "Playoffs").
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`. Defaults to "Regular Season".
        league_id (str, optional): The league ID (e.g., "00" for NBA).
            Valid values from `nba_api.stats.library.parameters.LeagueID`. Defaults to "00".


    Returns:
        str: JSON string containing detailed team data including info, ranks, roster, and coaches for the specified season.
    """
    logger.debug(f"Tool 'get_team_info_and_roster' called for '{team_identifier}', season '{season}', type '{season_type}', league '{league_id}'")
    # Pass all relevant parameters to the logic function
    result = fetch_team_info_and_roster_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        league_id=league_id
    )
    return result

@tool
def get_team_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    measure_type: str = MeasureTypeDetailedDefense.base, # Corrected default to match nba_api
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches comprehensive team statistics for a given season, including current season dashboard stats
    and historical year-by-year performance, with various filtering options.

    Args:
        team_identifier (str): The team's name, abbreviation, or ID.
        season (str, optional): The NBA season for dashboard stats (e.g., "2023-24"). Defaults to current season.
        season_type (str, optional): The type of season for dashboard and historical stats.
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`. Defaults to "Regular Season".
        per_mode (str, optional): The statistical mode for dashboard stats (e.g., "PerGame", "Totals").
            Valid values from `nba_api.stats.library.parameters.PerModeDetailed`. Defaults to "PerGame".
        measure_type (str, optional): The category of stats for dashboard (e.g., "Base", "Advanced").
            Valid values from `nba_api.stats.library.parameters.MeasureTypeDetailedDefense`. Defaults to "Base".
        opponent_team_id (int, optional): Filter dashboard stats against a specific opponent team ID. Defaults to 0 (all).
        date_from (Optional[str], optional): Start date for filtering dashboard games (YYYY-MM-DD).
        date_to (Optional[str], optional): End date for filtering dashboard games (YYYY-MM-DD).
        league_id (str, optional): The league ID for historical stats (e.g., "00" for NBA).
            Valid values from `nba_api.stats.library.parameters.LeagueID`. Defaults to "00".

    Returns:
        str: JSON string containing team statistics, including 'current_season_dashboard_stats' and 'historical_year_by_year_stats'.
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
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
from backend.api_tools.player_clutch import fetch_player_clutch_stats_logic

logger = logging.getLogger(__name__)

# ... (other tools unchanged)

@tool
def get_player_clutch_stats(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    measure_type: str = "Base",
    per_mode: str = "Totals",
    plus_minus: str = "N",
    pace_adjust: str = "N",
    rank: str = "N",
    shot_clock_range_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    period: int = 0,
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    location_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None
) -> str:
    """
    Fetches all clutch split dashboards for a player in a given season using the PlayerDashboardByClutch NBA API endpoint.

    Args:
        player_name (str): Full name of the player (e.g., "LeBron James").
        season (str): NBA season in 'YYYY-YY' format.
        season_type (str): "Regular Season", "Playoffs", or "Pre Season".
        measure_type (str): "Base", "Advanced", etc.
        per_mode (str): Statistical mode (e.g., "Totals", "PerGame").
        plus_minus (str): "Y" or "N".
        pace_adjust (str): "Y" or "N".
        rank (str): "Y" or "N".
        shot_clock_range_nullable (str, optional): Shot clock range filter.
        game_segment_nullable (str, optional): Game segment filter.
        period (int, optional): Period filter.
        last_n_games (int, optional): Number of most recent games to include.
        month (int, optional): Month filter (0 for all).
        opponent_team_id (int, optional): Opponent team ID (0 for all).
        location_nullable (str, optional): "Home" or "Road".
        outcome_nullable (str, optional): "W" or "L".
        vs_conference_nullable (str, optional): Conference filter.
        vs_division_nullable (str, optional): Division filter.
        season_segment_nullable (str, optional): "Pre All-Star" or "Post All-Star".
        date_from_nullable (str, optional): Start date (YYYY-MM-DD).
        date_to_nullable (str, optional): End date (YYYY-MM-DD).

    Returns:
        str: JSON string with all clutch split dashboards for the player.
    """
    logger.debug(f"Tool 'get_player_clutch_stats' called for {player_name}, season {season}")
    return fetch_player_clutch_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode,
        plus_minus=plus_minus,
        pace_adjust=pace_adjust,
        rank=rank,
        shot_clock_range_nullable=shot_clock_range_nullable,
        game_segment_nullable=game_segment_nullable,
        period=period,
        last_n_games=last_n_games,
        month=month,
        opponent_team_id=opponent_team_id,
        location_nullable=location_nullable,
        outcome_nullable=outcome_nullable,
        vs_conference_nullable=vs_conference_nullable,
        vs_division_nullable=vs_division_nullable,
        season_segment_nullable=season_segment_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable
    )
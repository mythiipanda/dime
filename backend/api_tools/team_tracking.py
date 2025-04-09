# Team tracking logic functions
import logging
import json
from typing import Optional, Tuple

from nba_api.stats.endpoints import (
    teamdashptpass,
    teamdashptreb,
    teamdashptshots
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed
)

from config import DEFAULT_TIMEOUT, ErrorMessages as Errors
from api_tools.utils import _process_dataframe, retry_on_timeout, format_response
from api_tools.team_tools import _find_team_id, find_team_by_name

logger = logging.getLogger(__name__)

def fetch_team_passing_stats_logic(team_id: str, season: str, season_type: str = 'Regular Season') -> dict:
    """
    Fetch team passing stats from NBA API
    """
    try:
        passing_stats = teamdashptpass.TeamDashPtPass(
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            per_mode_simple='PerGame'
        )
        return passing_stats.get_normalized_dict()
    except Exception as e:
        logger.error(f"Error fetching team passing stats: {str(e)}")
        raise

def fetch_team_rebounding_stats_logic(team_id: str, season: str, season_type: str = 'Regular Season') -> dict:
    """
    Fetch team rebounding stats from NBA API
    """
    try:
        rebounding_stats = teamdashptreb.TeamDashPtReb(
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            per_mode_simple='PerGame'
        )
        return rebounding_stats.get_normalized_dict()
    except Exception as e:
        logger.error(f"Error fetching team rebounding stats: {str(e)}")
        raise

def fetch_team_shooting_stats_logic(team_id: str, season: str, season_type: str = 'Regular Season') -> dict:
    """
    Fetch team shooting stats from NBA API
    """
    try:
        shooting_stats = teamdashptshots.TeamDashPtShots(
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            per_mode_simple='PerGame'
        )
        return shooting_stats.get_normalized_dict()
    except Exception as e:
        logger.error(f"Error fetching team shooting stats: {str(e)}")
        raise

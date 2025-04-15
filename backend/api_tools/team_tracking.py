import logging
import json
from typing import Dict, List, Optional, TypedDict, Union

from nba_api.stats.endpoints import (
    teamdashptpass,
    teamdashptreb,
    teamdashptshots
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed
)

from backend.config import DEFAULT_TIMEOUT, ErrorMessages
from backend.api_tools.utils import _process_dataframe, retry_on_timeout, format_response
from backend.api_tools.team_tools import _find_team_id
from backend.api_tools.http_client import nba_session

logger = logging.getLogger(__name__)

# Update the endpoints to use our configured session
teamdashptpass.requests = nba_session
teamdashptreb.requests = nba_session
teamdashptshots.requests = nba_session

class PassStats(TypedDict):
    """Type definition for team pass statistics."""
    frequency: float
    passes: float
    assists: float
    fgm: float
    fga: float
    fg_pct: float
    fg2m: float
    fg2a: float
    fg2_pct: float
    fg3m: float
    fg3a: float
    fg3_pct: float

class ReboundingStats(TypedDict):
    """Type definition for team rebounding statistics."""
    total: float
    contested: float
    uncontested: float
    offensive: float
    defensive: float
    frequency: float
    pct_contested: float

class ShootingStats(TypedDict):
    """Type definition for team shooting statistics."""
    fga_frequency: float
    fgm: float
    fga: float
    fg_pct: float
    efg_pct: float
    fg2_pct: float
    fg3_pct: float
    shot_clock: Optional[str]
    dribbles: Optional[str]
    touch_time: Optional[str]
    defender_distance: Optional[str]

def _validate_team_tracking_params(team_identifier: str, season: str) -> Optional[str]:
    """Validate common parameters for team tracking stats functions."""
    if not team_identifier or not season:
        return format_response(error=ErrorMessages.MISSING_REQUIRED_PARAMS)
    return None

def _get_team_for_tracking(team_identifier: str) -> tuple[Optional[str], Optional[int], Optional[str]]:
    """Get team info for tracking stats functions."""
    team_id, team_name = _find_team_id(team_identifier)
    if team_id is None:
        return (format_response(error=ErrorMessages.TEAM_NOT_FOUND.format(identifier=team_identifier)), None, None)
    return (None, team_id, team_name)

def _create_team_tracking_result(team_id: int, team_name: str, season: str, season_type: str, data: Dict) -> Dict:
    """Create a standard result structure for team tracking stats."""
    return {
        "team_id": team_id,
        "team_name": team_name,
        "season": season,
        "season_type": season_type,
        **data
    }

def fetch_team_passing_stats_logic(
    team_identifier: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> str:
    """
    Fetch team passing stats from NBA API.
    
    Args:
        team_identifier (str): Team name or ID
        season (str): Season in YYYY-YY format
        season_type (str): Type of season (regular, playoffs, etc.)
        per_mode (str): Per mode type (per game, per minute, etc.)
        
    Returns:
        str: JSON string containing team passing stats
    """
    logger.info(f"Executing fetch_team_passing_stats_logic for: {team_identifier}, Season: {season}")
    
    # Validate parameters
    validation_error = _validate_team_tracking_params(team_identifier, season)
    if validation_error:
        return validation_error
    
    # Get team info
    error_response, team_id, team_name = _get_team_for_tracking(team_identifier)
    if error_response:
        return error_response

    try:
        pass_stats = teamdashptpass.TeamDashPtPass(
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            per_mode_simple=per_mode,
            timeout=DEFAULT_TIMEOUT
        )
        
        passes_made = _process_dataframe(pass_stats.passes_made.get_data_frame(), single_row=False)
        passes_received = _process_dataframe(pass_stats.passes_received.get_data_frame(), single_row=False)

        if passes_made is None or passes_received is None:
            return format_response(error=ErrorMessages.DATA_PROCESSING_ERROR)

        # Process into more focused format
        processed_passes_made = []
        for pass_data in passes_made:
            processed_passes_made.append({
                "pass_from": pass_data.get("PASS_FROM"),
                "frequency": pass_data.get("FREQUENCY"),
                "passes": pass_data.get("PASS"),
                "assists": pass_data.get("AST"),
                "shooting": {
                    "fgm": pass_data.get("FGM"),
                    "fga": pass_data.get("FGA"),
                    "fg_pct": pass_data.get("FG_PCT"),
                    "fg2m": pass_data.get("FG2M"),
                    "fg2a": pass_data.get("FG2A"),
                    "fg2_pct": pass_data.get("FG2_PCT"),
                    "fg3m": pass_data.get("FG3M"),
                    "fg3a": pass_data.get("FG3A"),
                    "fg3_pct": pass_data.get("FG3_PCT")
                }
            })

        processed_passes_received = []
        for pass_data in passes_received:
            processed_passes_received.append({
                "pass_to": pass_data.get("PASS_TO"),
                "frequency": pass_data.get("FREQUENCY"),
                "passes": pass_data.get("PASS"),
                "assists": pass_data.get("AST"),
                "shooting": {
                    "fgm": pass_data.get("FGM"),
                    "fga": pass_data.get("FGA"),
                    "fg_pct": pass_data.get("FG_PCT"),
                    "fg2m": pass_data.get("FG2M"),
                    "fg2a": pass_data.get("FG2A"),
                    "fg2_pct": pass_data.get("FG2_PCT"),
                    "fg3m": pass_data.get("FG3M"),
                    "fg3a": pass_data.get("FG3A"),
                    "fg3_pct": pass_data.get("FG3_PCT")
                }
            })

        result = _create_team_tracking_result(
            team_id,
            team_name,
            season,
            season_type,
            {
                "passes_made": processed_passes_made,
                "passes_received": processed_passes_received
            }
        )

        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching passing stats: {str(e)}", exc_info=True)
        return format_response(error=f"Error fetching passing stats: {str(e)}")

def fetch_team_rebounding_stats_logic(
    team_identifier: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> str:
    """
    Fetch team rebounding stats from NBA API.
    
    Args:
        team_identifier (str): Team name or ID
        season (str): Season in YYYY-YY format
        season_type (str): Type of season (regular, playoffs, etc.)
        per_mode (str): Per mode type (per game, per minute, etc.)
        
    Returns:
        str: JSON string containing:
        {
            "team_id": str,
            "team_name": str,
            "season": str,
            "season_type": str,
            "overall": {...},
            "shot_type": [...],
            "shot_distance": [...],
            "rebound_distance": [...],
            "shot_distance_rebounding": [...]
        }
    """
    logger.info(f"Executing fetch_team_rebounding_stats_logic for: {team_identifier}, Season: {season}")
    
    # Validate parameters
    validation_error = _validate_team_tracking_params(team_identifier, season)
    if validation_error:
        return validation_error
    
    # Get team info
    error_response, team_id, team_name = _get_team_for_tracking(team_identifier)
    if error_response:
        return error_response

    try:
        reb_stats = teamdashptreb.TeamDashPtReb(
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            per_mode_simple=per_mode,
            timeout=DEFAULT_TIMEOUT
        )
        
        overall = _process_dataframe(reb_stats.overall_rebounding.get_data_frame(), single_row=True)
        shot_type = _process_dataframe(reb_stats.shot_type_rebounding.get_data_frame(), single_row=False)
        shot_dist = _process_dataframe(reb_stats.shot_distance_rebounding.get_data_frame(), single_row=False)
        reb_dist = _process_dataframe(reb_stats.reb_distance_rebounding.get_data_frame(), single_row=False)

        if not all([overall, shot_type, shot_dist, reb_dist]):
            return format_response(error=ErrorMessages.DATA_PROCESSING_ERROR)

        result = _create_team_tracking_result(
            team_id,
            team_name,
            season,
            season_type,
            {
                "overall": {
                    "total": overall.get("REB", 0.0),
                    "offensive": overall.get("OREB", 0.0),
                    "defensive": overall.get("DREB", 0.0),
                    "contested": overall.get("C_REB", 0.0),
                    "uncontested": overall.get("UC_REB", 0.0),
                    "contested_pct": overall.get("C_REB_PCT", 0.0)
                },
                "shot_type": shot_type,
                "shot_distance": shot_dist,
                "rebound_distance": reb_dist,
                "shot_distance_rebounding": shot_dist
            }
        )

        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching rebounding stats: {str(e)}", exc_info=True)
        return format_response(error=f"Error fetching rebounding stats: {str(e)}")

def fetch_team_shooting_stats_logic(
    team_identifier: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> str:
    """
    Fetch team shooting stats from NBA API.
    
    Args:
        team_identifier (str): Team name or ID
        season (str): Season in YYYY-YY format
        season_type (str): Type of season (regular, playoffs, etc.)
        per_mode (str): Per mode type (per game, per minute, etc.)
        
    Returns:
        str: JSON string containing:
        {
            "team_id": str,
            "team_name": str,
            "season": str,
            "season_type": str,
            "general": {...},
            "shot_clock": [...],
            "dribbles": [...],
            "touch_time": [...],
            "defender_distance": [...],
            "closest_defender": [...]
        }
    """
    logger.info(f"Executing fetch_team_shooting_stats_logic for: {team_identifier}, Season: {season}")
    
    # Validate parameters
    validation_error = _validate_team_tracking_params(team_identifier, season)
    if validation_error:
        return validation_error
    
    # Get team info
    error_response, team_id, team_name = _get_team_for_tracking(team_identifier)
    if error_response:
        return error_response

    try:
        shot_stats = teamdashptshots.TeamDashPtShots(
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            per_mode_simple=per_mode,
            timeout=DEFAULT_TIMEOUT
        )
        
        general = _process_dataframe(shot_stats.general_shooting.get_data_frame(), single_row=False)
        shot_clock = _process_dataframe(shot_stats.shot_clock_shooting.get_data_frame(), single_row=False)
        dribbles = _process_dataframe(shot_stats.dribble_shooting.get_data_frame(), single_row=False)
        closest_def = _process_dataframe(shot_stats.closest_defender_shooting.get_data_frame(), single_row=False)
        touch_time = _process_dataframe(shot_stats.touch_time_shooting.get_data_frame(), single_row=False)

        if not all([general, shot_clock, dribbles, closest_def, touch_time]):
            return format_response(error=ErrorMessages.DATA_PROCESSING_ERROR)

        result = _create_team_tracking_result(
            team_id,
            team_name,
            season,
            season_type,
            {
                "general": {
                    shot_type["SHOT_TYPE"].lower().replace(" ", "_"): {
                        "frequency": shot_type.get("FGA_FREQUENCY", 0.0),
                        "fgm": shot_type.get("FGM", 0.0),
                        "fga": shot_type.get("FGA", 0.0),
                        "fg_pct": shot_type.get("FG_PCT", 0.0),
                        "efg_pct": shot_type.get("EFG_PCT", 0.0)
                    }
                    for shot_type in general
                },
                "shot_clock": shot_clock,
                "dribbles": dribbles,
                "touch_time": touch_time,
                "defender_distance": closest_def
            }
        )

        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching shooting stats: {str(e)}", exc_info=True)
        return format_response(error=f"Error fetching shooting stats: {str(e)}")

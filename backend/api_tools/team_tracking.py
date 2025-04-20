import logging
import json
import pandas as pd
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

from backend.config import DEFAULT_TIMEOUT, Errors
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
        return format_response(error=Errors.MISSING_REQUIRED_PARAMS)
    return None

def _get_team_for_tracking(team_identifier: str) -> tuple[Optional[str], Optional[int], Optional[str]]:
    """Get team info for tracking stats functions."""
    team_id, team_name = _find_team_id(team_identifier)
    if team_id is None:
        return (format_response(error=Errors.TEAM_NOT_FOUND.format(identifier=team_identifier)), None, None)
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
            return format_response(error=Errors.DATA_PROCESSING_ERROR)

        # Process using list comprehensions
        processed_passes_made = [
            {
                "pass_from": pass_data.get("PASS_FROM"),
                "frequency": pass_data.get("FREQUENCY"),
                "passes": pass_data.get("PASS"),
                "assists": pass_data.get("AST"),
                "shooting": {
                    "fgm": pass_data.get("FGM"), "fga": pass_data.get("FGA"), "fg_pct": pass_data.get("FG_PCT"),
                    "fg2m": pass_data.get("FG2M"), "fg2a": pass_data.get("FG2A"), "fg2_pct": pass_data.get("FG2_PCT"),
                    "fg3m": pass_data.get("FG3M"), "fg3a": pass_data.get("FG3A"), "fg3_pct": pass_data.get("FG3_PCT")
                }
            } for pass_data in passes_made
        ] if passes_made else []

        processed_passes_received = [
            {
                "pass_to": pass_data.get("PASS_TO"),
                "frequency": pass_data.get("FREQUENCY"),
                "passes": pass_data.get("PASS"),
                "assists": pass_data.get("AST"),
                "shooting": {
                    "fgm": pass_data.get("FGM"), "fga": pass_data.get("FGA"), "fg_pct": pass_data.get("FG_PCT"),
                    "fg2m": pass_data.get("FG2M"), "fg2a": pass_data.get("FG2A"), "fg2_pct": pass_data.get("FG2_PCT"),
                    "fg3m": pass_data.get("FG3M"), "fg3a": pass_data.get("FG3A"), "fg3_pct": pass_data.get("FG3_PCT")
                }
            } for pass_data in passes_received
        ] if passes_received else []

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
    per_mode: str = PerModeDetailed.per_game,
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Fetch team rebounding stats from NBA API.
    
    Args:
        team_identifier (str): Team name or ID
        season (str): Season in YYYY-YY format
        season_type (str): Type of season (regular, playoffs, etc.)
        per_mode (str): Per mode type (per game, per minute, etc.)
        opponent_team_id (int, optional): Filter by opponent team ID.
        date_from (str, optional): Start date filter.
        date_to (str, optional): End date filter.
        
    Returns:
        str: JSON string containing team rebounding stats
    """
    logger.info(
        f"Executing fetch_team_rebounding_stats_logic for: {team_identifier}, Season: {season}, Type: {season_type}, "
        f"PerMode: {per_mode}, Opp: {opponent_team_id}, From: {date_from}, To: {date_to}"
    )
    
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
            opponent_team_id=opponent_team_id,
            date_from_nullable=date_from,
            date_to_nullable=date_to,
            timeout=DEFAULT_TIMEOUT
        )

        overall_df = reb_stats.overall_rebounding.get_data_frame()
        shot_type_df = reb_stats.shot_type_rebounding.get_data_frame()
        contested_df = reb_stats.num_contested_rebounding.get_data_frame()
        distances_df = reb_stats.shot_distance_rebounding.get_data_frame()
        reb_dist_df = reb_stats.reb_distance_rebounding.get_data_frame()

        overall = _process_dataframe(overall_df, single_row=True)

        # Select essential columns for team rebounding splits
        split_cols = [
            'TEAM_ID', 'TEAM_NAME', 'TEAM_ABBREVIATION', 'GP', 'MIN',
            'REB', 'OREB', 'DREB', 'C_REB', 'UC_REB', 'REB_PCT', 'C_REB_PCT',
            'UC_REB_PCT', 'REB_FREQUENCY', 'REB_DISTANCE' # Common rebounding stats
        ]

        # Specific columns for each split
        shot_type_cols = split_cols + ['SHOT_TYPE']
        contested_cols = split_cols + ['CONTEST_TYPE']
        shot_distance_cols = split_cols + ['SHOT_DISTANCE_RANGE']
        reb_distance_cols = split_cols + ['REB_DISTANCE_RANGE']

        shot_type = _process_dataframe(shot_type_df.loc[:, [col for col in shot_type_cols if col in shot_type_df.columns]] if not shot_type_df.empty else shot_type_df, single_row=False)
        contested = _process_dataframe(contested_df.loc[:, [col for col in contested_cols if col in contested_df.columns]] if not contested_df.empty else contested_df, single_row=False)
        distances = _process_dataframe(distances_df.loc[:, [col for col in shot_distance_cols if col in distances_df.columns]] if not distances_df.empty else distances_df, single_row=False)
        reb_dist = _process_dataframe(reb_dist_df.loc[:, [col for col in reb_distance_cols if col in reb_dist_df.columns]] if not reb_dist_df.empty else reb_dist_df, single_row=False)

        if not overall: # Check if at least overall stats are available
             logger.warning(f"No overall rebounding stats found for team {team_name} with given filters.")
             # Allow returning partial data if other splits exist

        result = _create_team_tracking_result(
            team_id,
            team_name,
            season,
            season_type,
            {
                "per_mode": per_mode,
                "opponent_team_id": opponent_team_id,
                "date_from": date_from,
                "date_to": date_to,
                "overall": {
                    "total": overall.get("REB", 0), "contested": overall.get("C_REB", 0),
                    "uncontested": overall.get("UC_REB", 0), "offensive": overall.get("OREB", 0),
                    "defensive": overall.get("DREB", 0), "frequency": overall.get("REB_FREQUENCY", 0),
                    "pct_contested": overall.get("C_REB_PCT", 0)
                } if overall else {}, # Ensure overall is an empty dict if None
                "by_shot_type": shot_type or [],
                "by_contest": contested or [],
                "by_shot_distance": distances or [],
                "by_rebound_distance": reb_dist or []
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
    per_mode: str = PerModeDetailed.per_game,
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Fetch team shooting stats from NBA API.
    
    Args:
        team_identifier (str): Team name or ID
        season (str): Season in YYYY-YY format
        season_type (str): Type of season (regular, playoffs, etc.)
        per_mode (str): Per mode type (per game, per minute, etc.)
        opponent_team_id (int, optional): Filter by opponent team ID.
        date_from (str, optional): Start date filter.
        date_to (str, optional): End date filter.
        
    Returns:
        str: JSON string containing team shooting stats
    """
    logger.info(
        f"Executing fetch_team_shooting_stats_logic for: {team_identifier}, Season: {season}, Type: {season_type}, "
        f"PerMode: {per_mode}, Opp: {opponent_team_id}, From: {date_from}, To: {date_to}"
    )
    
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
            opponent_team_id=opponent_team_id,
            date_from_nullable=date_from,
            date_to_nullable=date_to,
            timeout=DEFAULT_TIMEOUT
        )

        # Use general_shooting as overall stats
        general_df = shot_stats.general_shooting.get_data_frame()
        shot_clock_df = shot_stats.shot_clock_shooting.get_data_frame()
        dribbles_df = shot_stats.dribble_shooting.get_data_frame()
        defender_df = shot_stats.closest_defender_shooting.get_data_frame()
        touch_time_df = shot_stats.touch_time_shooting.get_data_frame()

        # Get overall stats from general_shooting (first row contains overall)
        overall = _process_dataframe(general_df.head(1) if not general_df.empty else general_df, single_row=True)
        # Process remaining general shooting stats (excluding first row)
        general = _process_dataframe(general_df.iloc[1:] if len(general_df) > 1 else general_df, single_row=False)

        # Select essential columns for team shooting splits
        split_cols = [
            'TEAM_ID', 'TEAM_NAME', 'TEAM_ABBREVIATION', 'GP', 'MIN',
            'FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT', 'EFG_PCT' # Common shooting stats
        ]

        # Specific columns for each split
        general_cols = split_cols + ['SHOT_TYPE']
        shot_clock_cols = split_cols + ['SHOT_CLOCK_RANGE']
        dribbles_cols = split_cols + ['DRIBBLE_RANGE']
        touch_time_cols = split_cols + ['TOUCH_TIME_RANGE']
        defender_cols = split_cols + ['CLOSE_DEF_DIST_RANGE']

        # Process each split with selected columns
        general = _process_dataframe(general_df.loc[1:, [col for col in general_cols if col in general_df.columns]] if len(general_df) > 1 else pd.DataFrame(), single_row=False)
        shot_clock = _process_dataframe(shot_clock_df.loc[:, [col for col in shot_clock_cols if col in shot_clock_df.columns]] if not shot_clock_df.empty else shot_clock_df, single_row=False)
        shot_clock = _process_dataframe(shot_clock_df.loc[:, [col for col in shot_clock_cols if col in shot_clock_df.columns]] if not shot_clock_df.empty else shot_clock_df, single_row=False)
        dribbles = _process_dataframe(dribbles_df.loc[:, [col for col in dribbles_cols if col in dribbles_df.columns]] if not dribbles_df.empty else dribbles_df, single_row=False)
        defender = _process_dataframe(defender_df.loc[:, [col for col in defender_cols if col in defender_df.columns]] if not defender_df.empty else defender_df, single_row=False)
        touch_time = _process_dataframe(touch_time_df.loc[:, [col for col in touch_time_cols if col in touch_time_df.columns]] if not touch_time_df.empty else touch_time_df, single_row=False)


        if not overall: # Check if at least overall stats are available
             logger.warning(f"No overall shooting stats found for team {team_name} with given filters.")
             # Allow returning partial data if other splits exist

        result = _create_team_tracking_result(
            team_id,
            team_name,
            season,
            season_type,
            {
                "per_mode": per_mode,
                "opponent_team_id": opponent_team_id,
                "date_from": date_from,
                "date_to": date_to,
                "overall": {
                    "fga_frequency": overall.get("FGA_FREQUENCY", 0), "fgm": overall.get("FGM", 0),
                    "fga": overall.get("FGA", 0), "fg_pct": overall.get("FG_PCT", 0),
                    "efg_pct": overall.get("EFG_PCT", 0), "fg2_pct": overall.get("FG2_PCT", 0),
                    "fg3_pct": overall.get("FG3_PCT", 0)
                } if overall else {}, # Ensure overall is an empty dict if None
                "general_shooting": general or [],
                "by_shot_clock": shot_clock or [],
                "by_dribble": dribbles or [],
                "by_defender_distance": defender or [],
                "by_touch_time": touch_time or []
            }
        )

        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching shooting stats: {str(e)}", exc_info=True)
        return format_response(error=f"Error fetching shooting stats: {str(e)}")

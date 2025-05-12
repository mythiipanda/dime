import logging
import pandas as pd
from typing import Optional
from functools import lru_cache

from nba_api.stats.endpoints import teamdashptshots
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import _process_dataframe, format_response
from backend.utils.validation import validate_date_format
from backend.api_tools.team_tracking_utils import _validate_team_tracking_params, _get_team_info_for_tracking
from backend.api_tools.http_client import nba_session

logger = logging.getLogger(__name__)

# Apply session patch
teamdashptshots.requests = nba_session

@lru_cache(maxsize=128)
def fetch_team_shooting_stats_logic(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Fetches team shooting statistics, categorized by various factors like shot clock,
    number of dribbles, defender distance, and touch time.
    """
    logger.info(f"Executing fetch_team_shooting_stats_logic for: {team_identifier}, Season: {season}, PerMode: {per_mode}")

    validation_error_msg = _validate_team_tracking_params(team_identifier, season)
    if validation_error_msg: return validation_error_msg
    if date_from and not validate_date_format(date_from): return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from))
    if date_to and not validate_date_format(date_to): return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to))

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(VALID_SEASON_TYPES)))

    VALID_PER_MODES = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}
    if per_mode not in VALID_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(VALID_PER_MODES))
        return format_response(error=error_msg)

    error_resp, team_id_resolved, team_name_resolved = _get_team_info_for_tracking(team_identifier, None)
    if error_resp: return error_resp
    if team_id_resolved is None or team_name_resolved is None: return format_response(error=Errors.TEAM_INFO_RESOLUTION_FAILED.format(identifier=team_identifier))

    try:
        logger.debug(f"Fetching teamdashptshots for Team ID: {team_id_resolved}, Season: {season}")
        shot_stats_endpoint = teamdashptshots.TeamDashPtShots(
            team_id=team_id_resolved, season=season, season_type_all_star=season_type,
            per_mode_simple=per_mode, opponent_team_id=opponent_team_id,
            date_from_nullable=date_from, date_to_nullable=date_to, timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"teamdashptshots API call successful for {team_name_resolved}")

        general_df = shot_stats_endpoint.general_shooting.get_data_frame()
        overall_shooting_data = _process_dataframe(general_df.head(1) if not general_df.empty else pd.DataFrame(), single_row=True)
        general_splits_list = _process_dataframe(general_df.iloc[1:] if len(general_df) > 1 else pd.DataFrame(), single_row=False)
        
        shot_clock_list = _process_dataframe(shot_stats_endpoint.shot_clock_shooting.get_data_frame(), single_row=False)
        dribbles_list = _process_dataframe(shot_stats_endpoint.dribble_shooting.get_data_frame(), single_row=False)
        defender_list = _process_dataframe(shot_stats_endpoint.closest_defender_shooting.get_data_frame(), single_row=False)
        touch_time_list = _process_dataframe(shot_stats_endpoint.touch_time_shooting.get_data_frame(), single_row=False)

        if overall_shooting_data is None and not general_df.empty:
            logger.error(f"DataFrame processing failed for general shooting stats of {team_name_resolved}.")
            error_msg = Errors.TEAM_SHOOTING_PROCESSING.format(identifier=str(team_id_resolved))
            return format_response(error=error_msg)
        
        if general_df.empty:
             logger.warning(f"No shooting stats found for team {team_name_resolved} with given filters.")
             return format_response({
                 "team_id": team_id_resolved, "team_name": team_name_resolved, "season": season, "season_type": season_type,
                 "parameters": {"per_mode": per_mode, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to},
                 "overall_shooting": {}, "general_shooting_splits": [], "by_shot_clock": [],
                 "by_dribble": [], "by_defender_distance": [], "by_touch_time": []
             })

        result = {
            "team_id": team_id_resolved, "team_name": team_name_resolved, "season": season, "season_type": season_type,
            "parameters": {"per_mode": per_mode, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to},
            "overall_shooting": overall_shooting_data or {},
            "general_shooting_splits": general_splits_list or [],
            "by_shot_clock": shot_clock_list or [],
            "by_dribble": dribbles_list or [],
            "by_defender_distance": defender_list or [],
            "by_touch_time": touch_time_list or []
        }
        logger.info(f"fetch_team_shooting_stats_logic completed for {team_name_resolved}")
        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching shooting stats for team {team_identifier}: {str(e)}", exc_info=True)
        error_msg = Errors.TEAM_SHOOTING_UNEXPECTED.format(identifier=team_identifier, error=str(e))
        return format_response(error=error_msg)
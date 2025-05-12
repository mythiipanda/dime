import logging
from typing import Optional
from functools import lru_cache

from nba_api.stats.endpoints import teamdashptreb
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import _process_dataframe, format_response
from backend.utils.validation import validate_date_format
from backend.api_tools.team_tracking_utils import _validate_team_tracking_params, _get_team_info_for_tracking
from backend.api_tools.http_client import nba_session

logger = logging.getLogger(__name__)

# Apply session patch
teamdashptreb.requests = nba_session

@lru_cache(maxsize=128)
def fetch_team_rebounding_stats_logic(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Fetches team rebounding statistics, categorized by various factors like shot type,
    contest level, shot distance, and rebound distance.
    """
    logger.info(f"Executing fetch_team_rebounding_stats_logic for: {team_identifier}, Season: {season}, PerMode: {per_mode}")

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
        logger.debug(f"Fetching teamdashptreb for Team ID: {team_id_resolved}, Season: {season}")
        reb_stats_endpoint = teamdashptreb.TeamDashPtReb(
            team_id=team_id_resolved, season=season, season_type_all_star=season_type,
            per_mode_simple=per_mode, opponent_team_id=opponent_team_id,
            date_from_nullable=date_from, date_to_nullable=date_to, timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"teamdashptreb API call successful for {team_name_resolved}")

        overall_df = reb_stats_endpoint.overall_rebounding.get_data_frame()
        shot_type_df = reb_stats_endpoint.shot_type_rebounding.get_data_frame()
        contested_df = reb_stats_endpoint.num_contested_rebounding.get_data_frame()
        distances_df = reb_stats_endpoint.shot_distance_rebounding.get_data_frame()
        reb_dist_df = reb_stats_endpoint.reb_distance_rebounding.get_data_frame()

        overall_data = _process_dataframe(overall_df, single_row=True)
        shot_type_list = _process_dataframe(shot_type_df, single_row=False)
        contested_list = _process_dataframe(contested_df, single_row=False)
        distances_list = _process_dataframe(distances_df, single_row=False)
        reb_dist_list = _process_dataframe(reb_dist_df, single_row=False)

        if all(data is None for data in [overall_data, shot_type_list, contested_list, distances_list, reb_dist_list]):
            if all(df.empty for df in [overall_df, shot_type_df, contested_df, distances_df, reb_dist_df]):
                logger.warning(f"No rebounding stats found for team {team_name_resolved} with given filters.")
                return format_response({
                    "team_id": team_id_resolved, "team_name": team_name_resolved, "season": season, "season_type": season_type,
                    "parameters": {"per_mode": per_mode, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to},
                    "overall": {}, "by_shot_type": [], "by_contest": [],
                    "by_shot_distance": [], "by_rebound_distance": []
                })
            else:
                logger.error(f"DataFrame processing failed for rebounding stats of {team_name_resolved}.")
                error_msg = Errors.TEAM_REBOUNDING_PROCESSING.format(identifier=str(team_id_resolved))
                return format_response(error=error_msg)

        result = {
            "team_id": team_id_resolved, "team_name": team_name_resolved, "season": season, "season_type": season_type,
            "parameters": {"per_mode": per_mode, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to},
            "overall": overall_data or {}, "by_shot_type": shot_type_list or [],
            "by_contest": contested_list or [], "by_shot_distance": distances_list or [],
            "by_rebound_distance": reb_dist_list or []
        }
        logger.info(f"fetch_team_rebounding_stats_logic completed for {team_name_resolved}")
        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching rebounding stats for team {team_identifier}: {str(e)}", exc_info=True)
        error_msg = Errors.TEAM_REBOUNDING_UNEXPECTED.format(identifier=team_identifier, error=str(e))
        return format_response(error=error_msg)
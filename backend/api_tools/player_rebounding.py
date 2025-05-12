import logging
from functools import lru_cache

from nba_api.stats.endpoints import commonplayerinfo, playerdashptreb
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)
from backend.utils.validation import _validate_season_format

logger = logging.getLogger(__name__)

# Module-level constants for validation sets
_VALID_REB_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_VALID_REB_PER_MODES = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}

@lru_cache(maxsize=256)
def fetch_player_rebounding_stats_logic(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game
) -> str:
    logger.info(f"Executing fetch_player_rebounding_stats_logic for player: {player_name}, Season: {season}, PerMode: {per_mode}")

    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    if season_type not in _VALID_REB_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_REB_SEASON_TYPES)[:5])))

    if per_mode not in _VALID_REB_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_REB_PER_MODES)[:3]))
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching commonplayerinfo for team ID lookup (Player: {player_actual_name}, ID: {player_id})")
        player_info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
        info_dict = _process_dataframe(player_info_endpoint.common_player_info.get_data_frame(), single_row=True)

        if info_dict is None or "TEAM_ID" not in info_dict:
            logger.error(f"Could not retrieve team ID for player {player_actual_name} (ID: {player_id})")
            return format_response(error=Errors.TEAM_ID_NOT_FOUND.format(player_name=player_actual_name))
        team_id = info_dict["TEAM_ID"]
        logger.debug(f"Found Team ID {team_id} for player {player_actual_name}")

        logger.debug(f"Fetching playerdashptreb for Player ID: {player_id}, Team ID: {team_id}, Season: {season}")
        reb_stats_endpoint = playerdashptreb.PlayerDashPtReb(
            player_id=player_id, team_id=team_id, season=season,
            season_type_all_star=season_type, per_mode_simple=per_mode,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"playerdashptreb API call successful for {player_actual_name}")

        overall_df = reb_stats_endpoint.overall_rebounding.get_data_frame()
        shot_type_df = reb_stats_endpoint.shot_type_rebounding.get_data_frame()
        contested_df = reb_stats_endpoint.num_contested_rebounding.get_data_frame()
        distances_df = reb_stats_endpoint.shot_distance_rebounding.get_data_frame()
        reb_dist_df = reb_stats_endpoint.reb_distance_rebounding.get_data_frame()

        overall_data = _process_dataframe(overall_df, single_row=True)
        shot_type_data = _process_dataframe(shot_type_df, single_row=False)
        contested_data = _process_dataframe(contested_df, single_row=False)
        distances_data = _process_dataframe(distances_df, single_row=False)
        reb_dist_data = _process_dataframe(reb_dist_df, single_row=False)

        if overall_data is None or \
           shot_type_data is None or \
           contested_data is None or \
           distances_data is None or \
           reb_dist_data is None:
            logger.error(f"DataFrame processing failed for rebounding stats of {player_actual_name} (Season: {season}). At least one DF processing returned None.")
            error_msg = Errors.PLAYER_REBOUNDING_PROCESSING.format(identifier=player_actual_name, season=season) # Ensure season is included
            return format_response(error=error_msg)

        if overall_df.empty and \
           shot_type_df.empty and \
           contested_df.empty and \
           distances_df.empty and \
           reb_dist_df.empty:
            logger.warning(f"No rebounding stats found for player {player_actual_name} with given filters (all original DFs were empty).")
            return format_response({
                "player_name": player_actual_name, "player_id": player_id,
                "parameters": {"season": season, "season_type": season_type, "per_mode": per_mode},
                "overall": {}, "by_shot_type": [], "by_contest": [],
                "by_shot_distance": [], "by_rebound_distance": []
            })

        result = {
            "player_name": player_actual_name, "player_id": player_id,
            "parameters": {"season": season, "season_type": season_type, "per_mode": per_mode},
            "overall": overall_data or {}, "by_shot_type": shot_type_data or [],
            "by_contest": contested_data or [], "by_shot_distance": distances_data or [],
            "by_rebound_distance": reb_dist_data or []
        }
        logger.info(f"fetch_player_rebounding_stats_logic completed for {player_actual_name}")
        return format_response(result)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_rebounding_stats_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_rebounding_stats_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.error(f"Error fetching rebounding stats for {player_name} (Season: {season}): {str(e)}", exc_info=True)
        error_msg = Errors.PLAYER_REBOUNDING_UNEXPECTED.format(identifier=player_name, season=season, error=str(e))
        return format_response(error=error_msg)
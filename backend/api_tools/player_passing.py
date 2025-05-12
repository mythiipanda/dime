import logging
from functools import lru_cache

from nba_api.stats.endpoints import commonplayerinfo, playerdashptpass
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
_VALID_PASSING_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_VALID_PASSING_PER_MODES = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}

@lru_cache(maxsize=256)
def fetch_player_passing_stats_logic(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game
) -> str:
    logger.info(f"Executing fetch_player_passing_stats_logic for player: {player_name}, Season: {season}, PerMode: {per_mode}")

    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    if season_type not in _VALID_PASSING_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_PASSING_SEASON_TYPES)[:5])))

    if per_mode not in _VALID_PASSING_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_PASSING_PER_MODES)[:3]))
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

        logger.debug(f"Fetching playerdashptpass for Player ID: {player_id}, Team ID: {team_id}, Season: {season}")
        pass_stats_endpoint = playerdashptpass.PlayerDashPtPass(
            player_id=player_id, team_id=team_id, season=season,
            season_type_all_star=season_type, per_mode_simple=per_mode,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"playerdashptpass API call successful for {player_actual_name}")

        passes_made_df = pass_stats_endpoint.passes_made.get_data_frame()
        passes_received_df = pass_stats_endpoint.passes_received.get_data_frame()

        passes_made_list = _process_dataframe(passes_made_df, single_row=False)
        passes_received_list = _process_dataframe(passes_received_df, single_row=False)

        if passes_made_list is None or passes_received_list is None:
            if passes_made_df.empty and passes_received_df.empty:
                logger.warning(f"No passing stats found for player {player_actual_name} with given filters.")
                return format_response({
                    "player_name": player_actual_name, "player_id": player_id,
                    "parameters": {"season": season, "season_type": season_type, "per_mode": per_mode},
                    "passes_made": [], "passes_received": []
                })
            else:
                logger.error(f"DataFrame processing failed for passing stats of {player_actual_name} (Season: {season}).")
                error_msg = Errors.PLAYER_PASSING_PROCESSING.format(identifier=player_actual_name, season=season)
                return format_response(error=error_msg)

        result = {
            "player_name": player_actual_name, "player_id": player_id,
            "parameters": {"season": season, "season_type": season_type, "per_mode": per_mode},
            "passes_made": passes_made_list or [],
            "passes_received": passes_received_list or []
        }
        logger.info(f"fetch_player_passing_stats_logic completed for {player_actual_name}")
        return format_response(result)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_passing_stats_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_passing_stats_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.error(f"Error fetching passing stats for {player_name} (Season: {season}): {str(e)}", exc_info=True)
        error_msg = Errors.PLAYER_PASSING_UNEXPECTED.format(identifier=player_name, season=season, error=str(e))
        return format_response(error=error_msg)
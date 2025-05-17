"""
Handles fetching and processing player shooting tracking statistics,
categorized by general, shot clock, dribbles, touch time, and defender distance.
Requires an initial lookup for the player's current team_id via commonplayerinfo.
"""
import logging
from typing import Optional, Set
from functools import lru_cache

from nba_api.stats.endpoints import commonplayerinfo, playerdashptshots
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)
from backend.utils.validation import _validate_season_format, validate_date_format

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
PLAYER_SHOOTING_TRACKING_CACHE_SIZE = 128
NBA_API_DEFAULT_OPPONENT_TEAM_ID = 0 # Standard value for no specific opponent filter

_VALID_SHOOTING_TRACKING_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_VALID_SHOOTING_TRACKING_PER_MODES: Set[str] = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}

@lru_cache(maxsize=PLAYER_SHOOTING_TRACKING_CACHE_SIZE)
def fetch_player_shots_tracking_logic(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.totals,
    opponent_team_id: int = NBA_API_DEFAULT_OPPONENT_TEAM_ID,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Fetches player shooting tracking statistics, broken down by various categories.
    This function first determines the player's team_id for the given season,
    then uses that to fetch detailed shooting stats.

    Args:
        player_name (str): The name or ID of the player.
        season (str, optional): NBA season in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to Regular Season.
        per_mode (str, optional): Statistical mode (PerModeSimple). Defaults to Totals.
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0 (all).
        date_from (Optional[str], optional): Start date filter (YYYY-MM-DD).
        date_to (Optional[str], optional): End date filter (YYYY-MM-DD).

    Returns:
        str: A JSON string containing player shooting tracking stats or an error message.
             Successful response structure includes keys like: "general_shooting",
             "by_shot_clock", "by_dribble_count", "by_touch_time",
             "by_defender_distance", "by_defender_distance_10ft_plus".
    """
    logger.info(f"Executing fetch_player_shots_tracking_logic for player name: {player_name}, Season: {season}, PerMode: {per_mode}")

    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if date_from and not validate_date_format(date_from):
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from))
    if date_to and not validate_date_format(date_to):
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to))

    if season_type not in _VALID_SHOOTING_TRACKING_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_SHOOTING_TRACKING_SEASON_TYPES)[:5])))
    if per_mode not in _VALID_SHOOTING_TRACKING_PER_MODES:
        return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_SHOOTING_TRACKING_PER_MODES)[:3])))

    try:
        player_id_int, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching commonplayerinfo for team ID lookup (Player: {player_actual_name}, ID: {player_id_int})")
        player_info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id_int, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
        info_dict = _process_dataframe(player_info_endpoint.common_player_info.get_data_frame(), single_row=True)

        if info_dict is None or "TEAM_ID" not in info_dict:
            logger.error(f"Could not retrieve team ID for player {player_actual_name} (ID: {player_id_int})")
            return format_response(error=Errors.TEAM_ID_NOT_FOUND.format(player_name=player_actual_name))
        team_id = info_dict["TEAM_ID"]
        logger.debug(f"Found Team ID {team_id} for player {player_actual_name}")

        logger.debug(f"Fetching playerdashptshots for Player ID: {player_id_int}, Team ID: {team_id}, Season: {season}")
        shooting_stats_endpoint = playerdashptshots.PlayerDashPtShots(
            player_id=player_id_int, team_id=team_id, season=season,
            season_type_all_star=season_type, per_mode_simple=per_mode,
            opponent_team_id=opponent_team_id,
            date_from_nullable=date_from, date_to_nullable=date_to,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"playerdashptshots API call successful for {player_actual_name}")

        general_list = _process_dataframe(shooting_stats_endpoint.general_shooting.get_data_frame(), single_row=False)
        shot_clock_list = _process_dataframe(shooting_stats_endpoint.shot_clock_shooting.get_data_frame(), single_row=False)
        dribbles_list = _process_dataframe(shooting_stats_endpoint.dribble_shooting.get_data_frame(), single_row=False)
        touch_time_list = _process_dataframe(shooting_stats_endpoint.touch_time_shooting.get_data_frame(), single_row=False)
        defender_dist_list = _process_dataframe(shooting_stats_endpoint.closest_defender_shooting.get_data_frame(), single_row=False)
        defender_dist_10ft_list = _process_dataframe(shooting_stats_endpoint.closest_defender10ft_plus_shooting.get_data_frame(), single_row=False)

        # Check for processing errors first (any individually processed dataframe is None)
        if general_list is None or \
           shot_clock_list is None or \
           dribbles_list is None or \
           touch_time_list is None or \
           defender_dist_list is None or \
           defender_dist_10ft_list is None:
            logger.error(f"DataFrame processing failed for shooting stats of {player_actual_name} (ID: {player_id_int}, Season: {season}). At least one DF processing returned None.")
            error_msg = Errors.PLAYER_SHOTS_TRACKING_PROCESSING.format(identifier=player_actual_name, season=season)
            return format_response(error=error_msg)
        
        if not (general_list or shot_clock_list or dribbles_list or touch_time_list or defender_dist_list or defender_dist_10ft_list):
            original_dfs = [
                shooting_stats_endpoint.general_shooting.get_data_frame(),
                shooting_stats_endpoint.shot_clock_shooting.get_data_frame(),
                shooting_stats_endpoint.dribble_shooting.get_data_frame(),
                shooting_stats_endpoint.touch_time_shooting.get_data_frame(),
                shooting_stats_endpoint.closest_defender_shooting.get_data_frame(),
                shooting_stats_endpoint.closest_defender10ft_plus_shooting.get_data_frame()
            ]
            if all(df.empty for df in original_dfs):
                logger.warning(f"No shooting stats data found for player {player_actual_name} (ID: {player_id_int}) with given filters (all original DFs were empty).")
                return format_response({
                    "player_id": player_id_int, "player_name": player_actual_name, "team_id": team_id,
                    "parameters": {"season": season, "season_type": season_type, "per_mode": per_mode, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to},
                    "general_shooting": [], "by_shot_clock": [], "by_dribble_count": [],
                    "by_touch_time": [], "by_defender_distance": [], "by_defender_distance_10ft_plus": []
                })
        
        result = {
            "player_id": player_id_int, "player_name": player_actual_name, "team_id": team_id,
            "parameters": {
                "season": season, "season_type": season_type, "per_mode": per_mode, "opponent_team_id": opponent_team_id,
                "date_from": date_from, "date_to": date_to
            },
            "general_shooting": general_list or [], "by_shot_clock": shot_clock_list or [],
            "by_dribble_count": dribbles_list or [], "by_touch_time": touch_time_list or [],
            "by_defender_distance": defender_dist_list or [], "by_defender_distance_10ft_plus": defender_dist_10ft_list or []
        }
        logger.info(f"fetch_player_shots_tracking_logic completed for {player_actual_name}")
        return format_response(result)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_shots_tracking_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_shots_tracking_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        player_id_log = player_id_int if 'player_id_int' in locals() else 'unknown'
        logger.error(f"Error fetching shots tracking stats for player {player_name} (resolved ID: {player_id_log}, Season: {season}): {str(e)}", exc_info=True)
        error_msg = Errors.PLAYER_SHOTS_TRACKING_UNEXPECTED.format(identifier=player_name, season=season, error=str(e))
        return format_response(error=error_msg)
import logging
import json
from typing import Dict, List, Optional, Any 
import pandas as pd
from functools import lru_cache
from nba_api.stats.endpoints import (
    commonplayerinfo, 
    playerdashboardbyclutch,
    playerdashptreb,
    playerdashptpass,
    playerdashptshots
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, LeagueID, PerModeDetailed, PerModeSimple,
    MeasureTypeDetailed # Changed: Import MeasureTypeDetailed instead of individual ones
)
from backend.config import DEFAULT_TIMEOUT, Errors, CURRENT_SEASON
from backend.api_tools.utils import (
    _process_dataframe,
    _validate_season_format,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError,
    validate_date_format
)

logger = logging.getLogger(__name__)

@lru_cache(maxsize=256)
def fetch_player_rebounding_stats_logic(
    player_name: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game 
) -> str:
    logger.info(f"Executing fetch_player_rebounding_stats_logic for player: {player_name}, Season: {season}, PerMode: {per_mode}")

    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5])))

    VALID_PER_MODES = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}
    if per_mode not in VALID_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(VALID_PER_MODES)[:3]))
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching commonplayerinfo for team ID lookup (Player: {player_actual_name}, ID: {player_id})")
        player_info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=DEFAULT_TIMEOUT)
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
            timeout=DEFAULT_TIMEOUT
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

        if overall_data is None and shot_type_data is None and contested_data is None and distances_data is None and reb_dist_data is None:
            if all(df.empty for df in [overall_df, shot_type_df, contested_df, distances_df, reb_dist_df]):
                 logger.warning(f"No rebounding stats found for player {player_actual_name} with given filters.")
                 return format_response({
                     "player_name": player_actual_name, "player_id": player_id,
                     "parameters": {"season": season, "season_type": season_type, "per_mode": per_mode},
                     "overall": {}, "by_shot_type": [], "by_contest": [],
                     "by_shot_distance": [], "by_rebound_distance": []
                 })
            else: 
                logger.error(f"DataFrame processing failed for rebounding stats of {player_actual_name}.")
                error_msg = Errors.PLAYER_REBOUNDING_PROCESSING.format(identifier=player_actual_name)
                return format_response(error=error_msg)

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
        logger.error(f"Error fetching rebounding stats for {player_name}: {str(e)}", exc_info=True)
        error_msg = Errors.PLAYER_REBOUNDING_UNEXPECTED.format(identifier=player_name, error=str(e))
        return format_response(error=error_msg)

@lru_cache(maxsize=256)
def fetch_player_passing_stats_logic(
    player_name: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game 
) -> str:
    logger.info(f"Executing fetch_player_passing_stats_logic for player: {player_name}, Season: {season}, PerMode: {per_mode}")

    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5])))

    VALID_PER_MODES = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}
    if per_mode not in VALID_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(VALID_PER_MODES)[:3]))
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching commonplayerinfo for team ID lookup (Player: {player_actual_name}, ID: {player_id})")
        player_info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=DEFAULT_TIMEOUT)
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
            timeout=DEFAULT_TIMEOUT
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
                logger.error(f"DataFrame processing failed for passing stats of {player_actual_name}.")
                error_msg = Errors.PLAYER_PASSING_PROCESSING.format(identifier=player_actual_name)
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
        logger.error(f"Error fetching passing stats for {player_name}: {str(e)}", exc_info=True)
        error_msg = Errors.PLAYER_PASSING_UNEXPECTED.format(identifier=player_name, error=str(e))
        return format_response(error=error_msg)

@lru_cache(maxsize=128)
def fetch_player_shots_tracking_logic(
    player_name: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    opponent_team_id: int = 0, 
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    logger.info(f"Executing fetch_player_shots_tracking_logic for player name: {player_name}, Season: {season}")

    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if date_from and not validate_date_format(date_from):
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from))
    if date_to and not validate_date_format(date_to):
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to))

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5])))

    try:
        player_id_int, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching commonplayerinfo for team ID lookup (Player: {player_actual_name}, ID: {player_id_int})")
        player_info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id_int, timeout=DEFAULT_TIMEOUT)
        info_dict = _process_dataframe(player_info_endpoint.common_player_info.get_data_frame(), single_row=True)

        if info_dict is None or "TEAM_ID" not in info_dict:
            logger.error(f"Could not retrieve team ID for player {player_actual_name} (ID: {player_id_int})")
            return format_response(error=Errors.TEAM_ID_NOT_FOUND.format(player_name=player_actual_name))
        team_id = info_dict["TEAM_ID"]
        logger.debug(f"Found Team ID {team_id} for player {player_actual_name}")

        logger.debug(f"Fetching playerdashptshots for Player ID: {player_id_int}, Team ID: {team_id}, Season: {season}")
        shooting_stats_endpoint = playerdashptshots.PlayerDashPtShots(
            player_id=player_id_int, team_id=team_id, season=season,
            season_type_all_star=season_type, opponent_team_id=opponent_team_id,
            date_from_nullable=date_from, date_to_nullable=date_to,
            timeout=DEFAULT_TIMEOUT
        )
        logger.debug(f"playerdashptshots API call successful for {player_actual_name}")

        general_list = _process_dataframe(shooting_stats_endpoint.general_shooting.get_data_frame(), single_row=False)
        shot_clock_list = _process_dataframe(shooting_stats_endpoint.shot_clock_shooting.get_data_frame(), single_row=False)
        dribbles_list = _process_dataframe(shooting_stats_endpoint.dribble_shooting.get_data_frame(), single_row=False)
        touch_time_list = _process_dataframe(shooting_stats_endpoint.touch_time_shooting.get_data_frame(), single_row=False)
        defender_dist_list = _process_dataframe(shooting_stats_endpoint.closest_defender_shooting.get_data_frame(), single_row=False)
        defender_dist_10ft_list = _process_dataframe(shooting_stats_endpoint.closest_defender10ft_plus_shooting.get_data_frame(), single_row=False)

        if general_list is None and shot_clock_list is None and dribbles_list is None and touch_time_list is None and defender_dist_list is None and defender_dist_10ft_list is None:
            if all(df.empty for df in [
                shooting_stats_endpoint.general_shooting.get_data_frame(),
                shooting_stats_endpoint.shot_clock_shooting.get_data_frame(),
            ]):
                logger.warning(f"No shooting stats data found for player {player_actual_name} (ID: {player_id_int}) with given filters.")
                return format_response({
                    "player_id": player_id_int, "player_name": player_actual_name, "team_id": team_id,
                    "parameters": {"season": season, "season_type": season_type, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to},
                    "general_shooting": [], "by_shot_clock": [], "by_dribble_count": [],
                    "by_touch_time": [], "by_defender_distance": [], "by_defender_distance_10ft_plus": []
                })
            else:
                logger.error(f"DataFrame processing failed for shooting stats of {player_actual_name} (ID: {player_id_int}).")
                error_msg = Errors.PLAYER_SHOTS_TRACKING_PROCESSING.format(player_id=str(player_id_int)) 
                return format_response(error=error_msg)

        result = {
            "player_id": player_id_int, "player_name": player_actual_name, "team_id": team_id,
            "parameters": {
                "season": season, "season_type": season_type, "opponent_team_id": opponent_team_id,
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
        logger.error(f"Error fetching shots tracking stats for player {player_name} (resolved ID: {player_id_log}): {str(e)}", exc_info=True)
        error_msg = Errors.PLAYER_SHOTS_TRACKING_UNEXPECTED.format(identifier=player_name, error=str(e))
        return format_response(error=error_msg)

@lru_cache(maxsize=64)
def fetch_player_clutch_stats_logic(
    player_name: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    measure_type: str = MeasureTypeDetailed.base, # Corrected default, using MeasureTypeDetailed.base
    per_mode: str = PerModeDetailed.totals,   
    plus_minus: str = "N", 
    pace_adjust: str = "N", 
    rank: str = "N", 
    clutch_time_nullable: Optional[str] = None, 
    ahead_behind_nullable: Optional[str] = None, 
    point_diff_nullable: Optional[int] = None, 
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
    logger.info(f"Executing fetch_player_clutch_stats_logic for: '{player_name}', Season: {season}, Measure: {measure_type}")

    if not player_name or not player_name.strip(): return format_response(error=Errors.PLAYER_NAME_EMPTY)
    if not season or not _validate_season_format(season): return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if date_from_nullable and not validate_date_format(date_from_nullable): return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from_nullable))
    if date_to_nullable and not validate_date_format(date_to_nullable): return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to_nullable))

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES: return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5])))
    
    VALID_PER_MODES = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
    if per_mode not in VALID_PER_MODES: return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(VALID_PER_MODES)[:5])))

    # Consolidate valid measure types for PlayerDashboardByClutch
    # Consolidate valid measure types for PlayerDashboardByClutch
    # Assuming Base, Advanced, Misc, Scoring, Usage are attributes of MeasureTypeDetailed
    VALID_CLUTCH_MEASURE_TYPES = set()
    for attr in dir(MeasureTypeDetailed):
        if not attr.startswith('_') and isinstance(getattr(MeasureTypeDetailed, attr), str):
            # We expect attributes like 'Base', 'Advanced', 'Misc', 'Scoring', 'Usage'
            # The actual values passed to the API are usually lowercase like 'Base', 'Advanced'
            # The nba_api often uses uppercase for enum members that resolve to these strings.
            # Example: MeasureTypeDetailed.Base might be "Base"
            VALID_CLUTCH_MEASURE_TYPES.add(getattr(MeasureTypeDetailed, attr))
    
    if measure_type not in VALID_CLUTCH_MEASURE_TYPES: 
        return format_response(error=Errors.INVALID_MEASURE_TYPE.format(value=measure_type, options=", ".join(list(VALID_CLUTCH_MEASURE_TYPES)[:5])))

    VALID_Y_N = {"Y", "N", ""} 
    if plus_minus not in VALID_Y_N: return format_response(error=Errors.INVALID_PLUS_MINUS.format(value=plus_minus))
    if pace_adjust not in VALID_Y_N: return format_response(error=Errors.INVALID_PACE_ADJUST.format(value=pace_adjust))
    if rank not in VALID_Y_N: return format_response(error=Errors.INVALID_RANK.format(value=rank))

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching playerdashboardbyclutch for ID: {player_id}, Season: {season}")
        clutch_endpoint = playerdashboardbyclutch.PlayerDashboardByClutch(
            player_id=player_id, season=season, season_type_playoffs=season_type,
            measure_type_detailed=measure_type,
            per_mode_detailed=per_mode,
            plus_minus=plus_minus, # Removed _nullable and conditional
            pace_adjust=pace_adjust, # Removed _nullable and conditional
            rank=rank, # Removed _nullable and conditional
            # clutch_time_nullable, ahead_behind_nullable, point_diff_nullable removed as they are not in constructor
            shot_clock_range_nullable=shot_clock_range_nullable, # Keep as is, matches constructor
            game_segment_nullable=game_segment_nullable, # Keep as is, matches constructor
            period=period, last_n_games=last_n_games, month=month,
            opponent_team_id=opponent_team_id, location_nullable=location_nullable, # Keep as is
            outcome_nullable=outcome_nullable, # Keep as is
            vs_conference_nullable=vs_conference_nullable, # Keep as is
            vs_division_nullable=vs_division_nullable, # Keep as is
            season_segment_nullable=season_segment_nullable, # Keep as is
            date_from_nullable=date_from_nullable, # Keep as is
            date_to_nullable=date_to_nullable, # Keep as is
            timeout=DEFAULT_TIMEOUT
        )
        logger.debug(f"playerdashboardbyclutch API call successful for ID: {player_id}, Season: {season}")
        
        clutch_df = clutch_endpoint.overall_player_dashboard.get_data_frame() 
        if clutch_df.empty and hasattr(clutch_endpoint, 'clutch_player_dashboard'): 
             clutch_df = clutch_endpoint.clutch_player_dashboard.get_data_frame()


        clutch_stats_list = _process_dataframe(clutch_df, single_row=False)

        if clutch_stats_list is None:
            if clutch_df.empty: 
                logger.warning(f"No clutch stats data found for {player_actual_name} in season {season} with specified filters.")
                return format_response({
                    "player_name": player_actual_name, "player_id": player_id,
                    "parameters": { 
                        "season": season, "season_type": season_type, "measure_type": measure_type, "per_mode": per_mode,
                        "plus_minus": plus_minus, "pace_adjust": pace_adjust, "rank": rank,
                        "clutch_time_nullable": clutch_time_nullable, "ahead_behind_nullable": ahead_behind_nullable,
                        "point_diff_nullable": point_diff_nullable, "shot_clock_range_nullable": shot_clock_range_nullable,
                        "game_segment_nullable": game_segment_nullable, "period": period, "last_n_games": last_n_games,
                        "month": month, "opponent_team_id": opponent_team_id, "location_nullable": location_nullable,
                        "outcome_nullable": outcome_nullable, "vs_conference_nullable": vs_conference_nullable,
                        "vs_division_nullable": vs_division_nullable, "season_segment_nullable": season_segment_nullable,
                        "date_from_nullable": date_from_nullable, "date_to_nullable": date_to_nullable
                    },
                    "clutch_stats": []
                })
            else: 
                logger.error(f"DataFrame processing failed for clutch stats of {player_actual_name} ({season}).")
                error_msg = Errors.PLAYER_CLUTCH_PROCESSING.format(identifier=player_actual_name)
                return format_response(error=error_msg)

        result = {
            "player_name": player_actual_name, "player_id": player_id,
            "parameters": {
                "season": season, "season_type": season_type, "measure_type": measure_type, "per_mode": per_mode,
                "plus_minus": plus_minus, "pace_adjust": pace_adjust, "rank": rank,
                "clutch_time_nullable": clutch_time_nullable, "ahead_behind_nullable": ahead_behind_nullable,
                "point_diff_nullable": point_diff_nullable, "shot_clock_range_nullable": shot_clock_range_nullable,
                "game_segment_nullable": game_segment_nullable, "period": period, "last_n_games": last_n_games,
                "month": month, "opponent_team_id": opponent_team_id, "location_nullable": location_nullable,
                "outcome_nullable": outcome_nullable, "vs_conference_nullable": vs_conference_nullable,
                "vs_division_nullable": vs_division_nullable, "season_segment_nullable": season_segment_nullable,
                "date_from_nullable": date_from_nullable, "date_to_nullable": date_to_nullable
            },
            "clutch_stats": clutch_stats_list or []
        }
        logger.info(f"Successfully fetched clutch stats for {player_actual_name}")
        return format_response(data=result)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_clutch_stats_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e: 
        logger.warning(f"ValueError in fetch_player_clutch_stats_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_clutch_stats_logic for '{player_name}', Season {season}: {e}", exc_info=True)
        error_msg = Errors.PLAYER_CLUTCH_UNEXPECTED.format(identifier=player_name, season=season, error=str(e)) 
        return format_response(error=error_msg)

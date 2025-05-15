import logging
from typing import Optional
from functools import lru_cache

from nba_api.stats.endpoints import playerdashboardbyclutch
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailed
)
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

# Module-level constants for validation sets
_VALID_CLUTCH_SEASON_TYPES = {SeasonTypeAllStar.regular, SeasonTypeAllStar.playoffs, SeasonTypeAllStar.preseason}
_VALID_CLUTCH_PER_MODES = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
_VALID_CLUTCH_MEASURE_TYPES = {getattr(MeasureTypeDetailed, attr) for attr in dir(MeasureTypeDetailed) if not attr.startswith('_') and isinstance(getattr(MeasureTypeDetailed, attr), str)}
_VALID_Y_N_CLUTCH = {"Y", "N", ""}

@lru_cache(maxsize=64)
def fetch_player_clutch_stats_logic(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    measure_type: str = MeasureTypeDetailed.base,
    per_mode: str = PerModeDetailed.totals,
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
    logger.info(f"Executing fetch_player_clutch_stats_logic for: '{player_name}', Season: {season}, Measure: {measure_type}")

    if not player_name or not player_name.strip(): return format_response(error=Errors.PLAYER_NAME_EMPTY)
    if not season or not _validate_season_format(season): return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if date_from_nullable and not validate_date_format(date_from_nullable): return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from_nullable))
    if date_to_nullable and not validate_date_format(date_to_nullable): return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to_nullable))

    if season_type not in _VALID_CLUTCH_SEASON_TYPES: return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_CLUTCH_SEASON_TYPES)[:5])))
    if per_mode not in _VALID_CLUTCH_PER_MODES: return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_CLUTCH_PER_MODES)[:5])))
    if measure_type not in _VALID_CLUTCH_MEASURE_TYPES:
        return format_response(error=Errors.INVALID_MEASURE_TYPE.format(value=measure_type, options=", ".join(list(_VALID_CLUTCH_MEASURE_TYPES)[:5])))

    if plus_minus not in _VALID_Y_N_CLUTCH: return format_response(error=Errors.INVALID_PLUS_MINUS.format(value=plus_minus))
    if pace_adjust not in _VALID_Y_N_CLUTCH: return format_response(error=Errors.INVALID_PACE_ADJUST.format(value=pace_adjust))
    if rank not in _VALID_Y_N_CLUTCH: return format_response(error=Errors.INVALID_RANK.format(value=rank))

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching playerdashboardbyclutch for ID: {player_id}, Season: {season}")
        clutch_endpoint = playerdashboardbyclutch.PlayerDashboardByClutch(
            player_id=player_id, season=season, season_type_playoffs=season_type,
            measure_type_detailed=measure_type,
            per_mode_detailed=per_mode,
            plus_minus=plus_minus,
            pace_adjust=pace_adjust,
            rank=rank,
            shot_clock_range_nullable=shot_clock_range_nullable,
            game_segment_nullable=game_segment_nullable,
            period=period, last_n_games=last_n_games, month=month,
            opponent_team_id=opponent_team_id, location_nullable=location_nullable,
            outcome_nullable=outcome_nullable,
            vs_conference_nullable=vs_conference_nullable,
            vs_division_nullable=vs_division_nullable,
            season_segment_nullable=season_segment_nullable,
            date_from_nullable=date_from_nullable,
            date_to_nullable=date_to_nullable,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"playerdashboardbyclutch API call successful for ID: {player_id}, Season: {season}")

        # Collect all relevant clutch dashboards
        dashboards = [
            "overall_player_dashboard",
            "last5_min5_point_player_dashboard",
            "last3_min5_point_player_dashboard",
            "last1_min5_point_player_dashboard",
            "last5_min_plus_minus5_point_player_dashboard",
            "last3_min_plus_minus5_point_player_dashboard",
            "last1_min_plus_minus5_point_player_dashboard",
            "last10_sec3_point_player_dashboard",
            "last30_sec3_point_player_dashboard",
            "last10_sec3_point2_player_dashboard",
            "last30_sec3_point2_player_dashboard"
        ]

        clutch_data = {}
        for dash in dashboards:
            df = getattr(clutch_endpoint, dash, None)
            if df is not None:
                clutch_data[dash] = _process_dataframe(df.get_data_frame(), single_row=False)
            else:
                clutch_data[dash] = []

        # If all dashboards are empty, treat as no data
        if all(not v for v in clutch_data.values()):
            logger.warning(f"No clutch stats data found for {player_actual_name} in season {season} with specified filters (all dashboards empty).")
            return format_response({
                "player_name": player_actual_name, "player_id": player_id,
                "parameters": {
                    "season": season, "season_type": season_type, "measure_type": measure_type, "per_mode": per_mode,
                    "plus_minus": plus_minus, "pace_adjust": pace_adjust, "rank": rank,
                    "game_segment_nullable": game_segment_nullable, "period": period, "last_n_games": last_n_games,
                    "month": month, "opponent_team_id": opponent_team_id, "location_nullable": location_nullable,
                    "outcome_nullable": outcome_nullable, "vs_conference_nullable": vs_conference_nullable,
                    "vs_division_nullable": vs_division_nullable, "season_segment_nullable": season_segment_nullable,
                    "date_from_nullable": date_from_nullable, "date_to_nullable": date_to_nullable, "shot_clock_range_nullable": shot_clock_range_nullable
                },
                "clutch_dashboards": clutch_data
            })

        # If we reach here, data is valid and processed
        result = {
            "player_name": player_actual_name, "player_id": player_id,
            "parameters": {
                "season": season, "season_type": season_type, "measure_type": measure_type, "per_mode": per_mode,
                "plus_minus": plus_minus, "pace_adjust": pace_adjust, "rank": rank,
                "game_segment_nullable": game_segment_nullable, "period": period, "last_n_games": last_n_games,
                "month": month, "opponent_team_id": opponent_team_id, "location_nullable": location_nullable,
                "outcome_nullable": outcome_nullable, "vs_conference_nullable": vs_conference_nullable,
                "vs_division_nullable": vs_division_nullable, "season_segment_nullable": season_segment_nullable,
                "date_from_nullable": date_from_nullable, "date_to_nullable": date_to_nullable, "shot_clock_range_nullable": shot_clock_range_nullable
            },
            "clutch_dashboards": clutch_data
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
import logging
import json
from typing import Optional, Dict, Any
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import playerdashboardbyteamperformance
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, LeagueID, MeasureTypeDetailed
)
from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)
from ..utils.validation import _validate_season_format, validate_date_format

logger = logging.getLogger(__name__)

_VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_VALID_PER_MODES = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
_VALID_MEASURE_TYPES = {getattr(MeasureTypeDetailed, attr) for attr in dir(MeasureTypeDetailed) if not attr.startswith('_') and isinstance(getattr(MeasureTypeDetailed, attr), str)}
_VALID_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

@lru_cache(maxsize=128)
def fetch_player_dashboard_by_team_performance_logic(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.totals,
    measure_type: str = MeasureTypeDetailed.base,
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    pace_adjust: str = "N",
    period: int = 0,
    plus_minus: str = "N",
    rank: str = "N",
    vs_division: Optional[str] = None,
    vs_conference: Optional[str] = None,
    shot_clock_range: Optional[str] = None,
    season_segment: Optional[str] = None,
    po_round: Optional[int] = None,
    outcome: Optional[str] = None,
    location: Optional[str] = None,
    league_id: Optional[str] = None,
    game_segment: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    logger.info(f"Executing fetch_player_dashboard_by_team_performance_logic for '{player_name}', season {season}, type {season_type}")

    # Validate season
    if not season or not _validate_season_format(season):
        error_msg = Errors.INVALID_SEASON_FORMAT.format(season=season)
        return format_response(error=error_msg)
    # Validate dates
    if date_from and not validate_date_format(date_from):
        error_msg = Errors.INVALID_DATE_FORMAT.format(date=date_from)
        return format_response(error=error_msg)
    if date_to and not validate_date_format(date_to):
        error_msg = Errors.INVALID_DATE_FORMAT.format(date=date_to)
        return format_response(error=error_msg)
    # Validate season type
    if season_type not in _VALID_SEASON_TYPES:
        error_msg = Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_SEASON_TYPES)[:5]))
        return format_response(error=error_msg)
    # Validate per_mode
    if per_mode not in _VALID_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_PER_MODES)[:5]))
        return format_response(error=error_msg)
    # Validate measure_type
    if measure_type not in _VALID_MEASURE_TYPES:
        error_msg = Errors.INVALID_MEASURE_TYPE.format(value=measure_type, options=", ".join(list(_VALID_MEASURE_TYPES)[:5]))
        return format_response(error=error_msg)
    # Validate league_id
    if league_id and league_id not in _VALID_LEAGUE_IDS:
        error_msg = Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_VALID_LEAGUE_IDS)[:5]))
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.error(f"Unexpected error finding player: {e}", exc_info=True)
        return format_response(error=str(e))

    try:
        endpoint = playerdashboardbyteamperformance.PlayerDashboardByTeamPerformance(
            player_id=player_id,
            season=season,
            season_type_playoffs=season_type,
            per_mode_detailed=per_mode,
            measure_type_detailed=measure_type,
            last_n_games=last_n_games,
            month=month,
            opponent_team_id=opponent_team_id,
            pace_adjust=pace_adjust,
            period=period,
            plus_minus=plus_minus,
            rank=rank,
            vs_division_nullable=vs_division,
            vs_conference_nullable=vs_conference,
            shot_clock_range_nullable=shot_clock_range,
            season_segment_nullable=season_segment,
            po_round_nullable=po_round,
            outcome_nullable=outcome,
            location_nullable=location,
            league_id_nullable=league_id,
            game_segment_nullable=game_segment,
            date_from_nullable=date_from,
            date_to_nullable=date_to,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        datasets = endpoint.get_data_frames()
        dataset_names = [
            "overall_player_dashboard",
            "points_scored_player_dashboard",
            "ponts_against_player_dashboard",
            "score_differential_player_dashboard"
        ]
        result = {}
        for idx, name in enumerate(dataset_names):
            df = datasets[idx] if idx < len(datasets) else pd.DataFrame()
            result[name] = _process_dataframe(df, single_row=False)
        return format_response({
            "player_name": player_actual_name,
            "player_id": player_id,
            "parameters": {
                "season": season,
                "season_type": season_type,
                "per_mode": per_mode,
                "measure_type": measure_type,
                "last_n_games": last_n_games,
                "month": month,
                "opponent_team_id": opponent_team_id,
                "pace_adjust": pace_adjust,
                "period": period,
                "plus_minus": plus_minus,
                "rank": rank,
                "vs_division": vs_division,
                "vs_conference": vs_conference,
                "shot_clock_range": shot_clock_range,
                "season_segment": season_segment,
                "po_round": po_round,
                "outcome": outcome,
                "location": location,
                "league_id": league_id,
                "game_segment": game_segment,
                "date_from": date_from,
                "date_to": date_to
            },
            "team_performance_dashboards": result
        })
    except Exception as api_error:
        logger.error(f"nba_api playerdashboardbyteamperformance failed: {api_error}", exc_info=True)
        error_msg = Errors.PLAYER_DASHBOARD_TEAM_PERFORMANCE_API.format(identifier=player_actual_name, error=str(api_error)) if hasattr(Errors, "PLAYER_DASHBOARD_TEAM_PERFORMANCE_API") else str(api_error)
        return format_response(error=error_msg)
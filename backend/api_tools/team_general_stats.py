import logging
import json
from typing import Optional
from functools import lru_cache

from nba_api.stats.endpoints import teamdashboardbygeneralsplits, teamyearbyyearstats
from nba_api.stats.library.parameters import (
    LeagueID,
    SeasonTypeAllStar,
    MeasureTypeDetailedDefense,
    PerModeDetailed
)

from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response,
    find_team_id_or_error,
    TeamNotFoundError
)
from backend.utils.validation import _validate_season_format, validate_date_format


logger = logging.getLogger(__name__)

@lru_cache(maxsize=128)
def fetch_team_stats_logic(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    measure_type: str = MeasureTypeDetailedDefense.base, 
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches comprehensive team statistics, including current season dashboard stats and historical performance.
    """
    logger.info(f"Executing fetch_team_stats_logic for: '{team_identifier}', Season: {season}, Measure: {measure_type}")

    if not team_identifier or not str(team_identifier).strip():
        return format_response(error=Errors.TEAM_IDENTIFIER_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if date_from and not validate_date_format(date_from):
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from))
    if date_to and not validate_date_format(date_to):
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to))

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5])))

    VALID_PER_MODES = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
    if per_mode not in VALID_PER_MODES: 
        return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(VALID_PER_MODES)[:5])))
    
    # For teamyearbyyearstats, PerModeSimple is expected (Totals or PerGame).
    # We'll use PerGame as a sensible default for historical year-by-year data.
    # The main 'per_mode' parameter will still apply to teamdashboardbygeneralsplits.
    historical_per_mode = PerModeDetailed.per_game # PerModeSimple.per_game would be more direct if PerModeSimple was imported

    VALID_MEASURE_TYPES = {getattr(MeasureTypeDetailedDefense, attr) for attr in dir(MeasureTypeDetailedDefense) if not attr.startswith('_') and isinstance(getattr(MeasureTypeDetailedDefense, attr), str)}
    if measure_type not in VALID_MEASURE_TYPES:
        return format_response(error=Errors.INVALID_MEASURE_TYPE.format(value=measure_type, options=", ".join(list(VALID_MEASURE_TYPES)[:5])))

    VALID_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}
    if league_id not in VALID_LEAGUE_IDS: 
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(VALID_LEAGUE_IDS)[:3])))
    
    try:
        team_id, team_actual_name = find_team_id_or_error(team_identifier)

        dashboard_stats_dict, historical_stats_list = {}, []
        dashboard_error, historical_error = None, None

        logger.debug(f"Fetching team dashboard stats for Team ID: {team_id}, Season: {season}, Measure: {measure_type}")
        try:
            dashboard_endpoint = teamdashboardbygeneralsplits.TeamDashboardByGeneralSplits(
                team_id=team_id, season=season, season_type_all_star=season_type,
                per_mode_detailed=per_mode, measure_type_detailed_defense=measure_type,
                opponent_team_id=opponent_team_id, date_from_nullable=date_from,
                date_to_nullable=date_to, timeout=settings.DEFAULT_TIMEOUT_SECONDS
            )
            overall_stats_df = dashboard_endpoint.overall_team_dashboard.get_data_frame()
            dashboard_stats_dict = _process_dataframe(overall_stats_df, single_row=True)

            if dashboard_stats_dict is None:
                if overall_stats_df.empty:
                    logger.warning(f"No dashboard stats found for team {team_id}, season {season} with measure {measure_type} and filters.")
                    dashboard_stats_dict = {}
                else:
                    dashboard_error = Errors.TEAM_PROCESSING.format(data_type=f"dashboard stats ({measure_type})", identifier=str(team_id), season=season)
                    logger.error(dashboard_error)
                    dashboard_stats_dict = {}
        except json.JSONDecodeError as jde:
            logger.error(f"API JSONDecodeError for team dashboard {team_id}, measure_type {measure_type}: {jde}", exc_info=True)
            dashboard_error = Errors.TEAM_API.format(data_type=f"team dashboard ({measure_type})", identifier=str(team_id), season=season, error=f"JSONDecodeError: {str(jde)}")
            dashboard_stats_dict = {}
        except Exception as api_error:
            dashboard_error = Errors.TEAM_API.format(data_type=f"team dashboard ({measure_type})", identifier=str(team_id), season=season, error=str(api_error))
            logger.error(dashboard_error, exc_info=True)
            dashboard_stats_dict = {}

        logger.debug(f"Fetching historical stats for Team ID: {team_id}, League: {league_id}, PerModeSimple: {historical_per_mode}")
        try:
            historical_endpoint = teamyearbyyearstats.TeamYearByYearStats(
                team_id=team_id, league_id=league_id,
                season_type_all_star=season_type, # Historical data is usually Regular Season, but API takes season_type
                per_mode_simple=historical_per_mode,
                timeout=settings.DEFAULT_TIMEOUT_SECONDS
            )
            hist_df = historical_endpoint.team_stats.get_data_frame()
            historical_stats_list = _process_dataframe(hist_df, single_row=False)
            if historical_stats_list is None:
                if hist_df.empty:
                    logger.warning(f"No historical stats found for team {team_id}.")
                    historical_stats_list = []
                else:
                    historical_error = Errors.TEAM_PROCESSING.format(data_type="historical stats", identifier=str(team_id), season="N/A") 
                    logger.error(historical_error)
                    historical_stats_list = []
        except Exception as hist_api_error:
            historical_error = Errors.TEAM_API.format(data_type="historical stats", identifier=str(team_id), season="N/A", error=str(hist_api_error))
            logger.warning(f"Could not fetch historical stats: {historical_error}", exc_info=True)
            historical_stats_list = []

        result = {
            "team_id": team_id, "team_name": team_actual_name,
            "parameters": {
                "season_for_dashboard": season, "season_type_for_dashboard": season_type,
                "per_mode": per_mode, "measure_type_for_dashboard": measure_type,
                "opponent_team_id_for_dashboard": opponent_team_id,
                "date_from_for_dashboard": date_from, "date_to_for_dashboard": date_to,
                "league_id_for_historical": league_id
            },
            "current_stats": dashboard_stats_dict or {},
            "historical_stats": historical_stats_list or []
        }
        partial_errors = [err for err in [dashboard_error, historical_error] if err]
        if partial_errors:
            result["partial_errors"] = partial_errors

        logger.info(f"fetch_team_stats_logic completed for Team ID: {team_id}, Season: {season}")
        return format_response(result)

    except (TeamNotFoundError, ValueError) as e:
        logger.warning(f"Team lookup or validation failed for '{team_identifier}': {e}")
        return format_response(error=str(e))
    except Exception as e:
        error_msg = Errors.TEAM_UNEXPECTED.format(identifier=team_identifier, season=season, error=str(e))
        logger.critical(error_msg, exc_info=True)
        return format_response(error=error_msg)
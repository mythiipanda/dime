"""
Handles fetching general team statistics, including current season dashboard stats
and historical year-by-year performance.
"""
import logging
import json # For JSONDecodeError
from typing import Optional, Dict, List, Tuple, Any, Set
from functools import lru_cache

from nba_api.stats.endpoints import teamdashboardbygeneralsplits, teamyearbyyearstats
from nba_api.stats.library.parameters import (
    LeagueID,
    SeasonTypeAllStar,
    MeasureTypeDetailedDefense, # Note: API uses MeasureTypeDetailedDefense for teamdashboardbygeneralsplits
    PerModeDetailed,
    PerModeSimple # For teamyearbyyearstats
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

# --- Module-Level Constants ---
TEAM_GENERAL_STATS_CACHE_SIZE = 128
DEFAULT_HISTORICAL_PER_MODE = PerModeSimple.per_game # Sensible default for year-by-year

_TEAM_GENERAL_VALID_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_TEAM_GENERAL_VALID_PER_MODES: Set[str] = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
_TEAM_GENERAL_VALID_MEASURE_TYPES: Set[str] = {getattr(MeasureTypeDetailedDefense, attr) for attr in dir(MeasureTypeDetailedDefense) if not attr.startswith('_') and isinstance(getattr(MeasureTypeDetailedDefense, attr), str)}
_TEAM_GENERAL_VALID_LEAGUE_IDS: Set[str] = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

# --- Helper Functions ---
def _fetch_dashboard_general_splits_data(
    team_id: int, season: str, season_type: str, per_mode: str, measure_type: str,
    opponent_team_id: int, date_from: Optional[str], date_to: Optional[str]
) -> Tuple[Dict[str, Any], Optional[str]]:
    """Fetches and processes data from teamdashboardbygeneralsplits."""
    dashboard_stats_dict: Dict[str, Any] = {}
    error_message: Optional[str] = None
    logger.debug(f"Fetching team dashboard stats for Team ID: {team_id}, Season: {season}, Measure: {measure_type}")
    try:
        dashboard_endpoint = teamdashboardbygeneralsplits.TeamDashboardByGeneralSplits(
            team_id=team_id, season=season, season_type_all_star=season_type,
            per_mode_detailed=per_mode, measure_type_detailed_defense=measure_type,
            opponent_team_id=opponent_team_id, date_from_nullable=date_from,
            date_to_nullable=date_to, timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        overall_stats_df = dashboard_endpoint.overall_team_dashboard.get_data_frame()
        dashboard_stats_dict = _process_dataframe(overall_stats_df, single_row=True) or {}

        if overall_stats_df.empty and not dashboard_stats_dict: # Check if it was empty and processing yielded empty
            logger.warning(f"No dashboard stats found for team {team_id}, season {season} with measure {measure_type} and filters.")
        elif dashboard_stats_dict is None: # Should not happen if _process_dataframe returns {} for empty
            error_message = Errors.TEAM_PROCESSING.format(data_type=f"dashboard stats ({measure_type})", identifier=str(team_id), season=season)
            logger.error(error_message)
    except json.JSONDecodeError as jde:
        logger.error(f"API JSONDecodeError for team dashboard {team_id}, measure_type {measure_type}: {jde}", exc_info=True)
        error_message = Errors.TEAM_API.format(data_type=f"team dashboard ({measure_type})", identifier=str(team_id), season=season, error=f"JSONDecodeError: {str(jde)}")
    except Exception as api_error:
        error_message = Errors.TEAM_API.format(data_type=f"team dashboard ({measure_type})", identifier=str(team_id), season=season, error=str(api_error))
        logger.error(error_message, exc_info=True)
    return dashboard_stats_dict, error_message

def _fetch_historical_year_by_year_stats(
    team_id: int, league_id: str, season_type_for_hist: str # Use a distinct season_type for clarity
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Fetches and processes data from teamyearbyyearstats."""
    historical_stats_list: List[Dict[str, Any]] = []
    error_message: Optional[str] = None
    logger.debug(f"Fetching historical stats for Team ID: {team_id}, League: {league_id}, PerMode: {DEFAULT_HISTORICAL_PER_MODE}")
    try:
        historical_endpoint = teamyearbyyearstats.TeamYearByYearStats(
            team_id=team_id, league_id=league_id,
            season_type_all_star=season_type_for_hist, # API takes season_type, though typically 'Regular Season' for historical
            per_mode_simple=DEFAULT_HISTORICAL_PER_MODE,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        hist_df = historical_endpoint.team_stats.get_data_frame()
        historical_stats_list = _process_dataframe(hist_df, single_row=False) or []

        if hist_df.empty and not historical_stats_list:
            logger.warning(f"No historical stats found for team {team_id}.")
        elif historical_stats_list is None: # Should not happen if _process_dataframe returns [] for empty
            error_message = Errors.TEAM_PROCESSING.format(data_type="historical stats", identifier=str(team_id), season="N/A")
            logger.error(error_message)
    except Exception as hist_api_error:
        error_message = Errors.TEAM_API.format(data_type="historical stats", identifier=str(team_id), season="N/A", error=str(hist_api_error))
        logger.warning(f"Could not fetch historical stats: {error_message}", exc_info=True)
    return historical_stats_list, error_message

# --- Main Logic Function ---
@lru_cache(maxsize=TEAM_GENERAL_STATS_CACHE_SIZE)
def fetch_team_stats_logic(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON, # Season for dashboard stats
    season_type: str = SeasonTypeAllStar.regular, # SeasonType for dashboard stats
    per_mode: str = PerModeDetailed.per_game, # PerMode for dashboard stats
    measure_type: str = MeasureTypeDetailedDefense.base,  # MeasureType for dashboard stats
    opponent_team_id: int = 0, # For dashboard stats
    date_from: Optional[str] = None, # For dashboard stats
    date_to: Optional[str] = None,   # For dashboard stats
    league_id: str = LeagueID.nba    # LeagueID for historical stats (and dashboard if needed)
) -> str:
    """
    Fetches comprehensive team statistics: current season dashboard stats and historical year-by-year performance.
    """
    logger.info(f"Executing fetch_team_stats_logic for: '{team_identifier}', Dashboard Season: {season}, Dashboard Measure: {measure_type}")

    # Parameter Validations
    if not team_identifier or not str(team_identifier).strip():
        return format_response(error=Errors.TEAM_IDENTIFIER_EMPTY)
    if not season or not _validate_season_format(season): # Validates dashboard season
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if date_from and not validate_date_format(date_from):
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from))
    if date_to and not validate_date_format(date_to):
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to))
    if season_type not in _TEAM_GENERAL_VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_TEAM_GENERAL_VALID_SEASON_TYPES)[:5])))
    if per_mode not in _TEAM_GENERAL_VALID_PER_MODES:
        return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_TEAM_GENERAL_VALID_PER_MODES)[:5])))
    if measure_type not in _TEAM_GENERAL_VALID_MEASURE_TYPES:
        return format_response(error=Errors.INVALID_MEASURE_TYPE.format(value=measure_type, options=", ".join(list(_TEAM_GENERAL_VALID_MEASURE_TYPES)[:5])))
    if league_id not in _TEAM_GENERAL_VALID_LEAGUE_IDS:
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_TEAM_GENERAL_VALID_LEAGUE_IDS)[:3])))
    
    try:
        team_id, team_actual_name = find_team_id_or_error(team_identifier)
        all_errors: List[str] = []

        dashboard_stats, dash_err = _fetch_dashboard_general_splits_data(
            team_id, season, season_type, per_mode, measure_type, opponent_team_id, date_from, date_to
        )
        if dash_err: all_errors.append(dash_err)

        # For historical stats, typically 'Regular Season' is most relevant, but API allows passing season_type.
        # Using the main season_type for consistency, though it might mean less data for non-regular types.
        historical_stats, hist_err = _fetch_historical_year_by_year_stats(team_id, league_id, season_type)
        if hist_err: all_errors.append(hist_err)

        if not dashboard_stats and not historical_stats and all_errors:
            # If both fetches failed and produced errors
            error_summary = Errors.TEAM_ALL_FAILED.format(identifier=team_identifier, season=season, errors_list=', '.join(all_errors))
            logger.error(error_summary)
            return format_response(error=error_summary)
        
        result = {
            "team_id": team_id, "team_name": team_actual_name,
            "parameters": {
                "season_for_dashboard": season, "season_type_for_dashboard": season_type,
                "per_mode_for_dashboard": per_mode, "measure_type_for_dashboard": measure_type,
                "opponent_team_id_for_dashboard": opponent_team_id,
                "date_from_for_dashboard": date_from, "date_to_for_dashboard": date_to,
                "league_id_for_historical": league_id, "season_type_for_historical": season_type
            },
            "current_season_dashboard_stats": dashboard_stats, # Renamed for clarity
            "historical_year_by_year_stats": historical_stats # Renamed for clarity
        }
        if all_errors:
            result["partial_errors"] = all_errors

        logger.info(f"fetch_team_stats_logic completed for Team ID: {team_id}, Dashboard Season: {season}")
        return format_response(result)

    except (TeamNotFoundError, ValueError) as e: # From find_team_id_or_error
        logger.warning(f"Team lookup or initial validation failed for '{team_identifier}': {e}")
        return format_response(error=str(e))
    except Exception as e: # Catch-all for unexpected issues in orchestration
        error_msg = Errors.TEAM_UNEXPECTED.format(identifier=team_identifier, season=season, error=str(e))
        logger.critical(error_msg, exc_info=True)
        return format_response(error=error_msg)
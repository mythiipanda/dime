import logging
import json
from typing import Optional, Dict, List, Tuple, Any
import pandas as pd
from functools import lru_cache
from nba_api.stats.endpoints import (
    teaminfocommon,
    commonteamroster,
    teamdashboardbygeneralsplits,
    teamdashptpass, 
    teamyearbyyearstats
)
from nba_api.stats.library.parameters import (
    LeagueID,
    SeasonTypeAllStar,
    MeasureTypeDetailedDefense,
    PerModeDetailed,
    PerModeSimple # Added import for PerModeSimple
)

from backend.config import DEFAULT_TIMEOUT, CURRENT_SEASON, Errors
from backend.api_tools.utils import (
    _process_dataframe,
    _validate_season_format,
    format_response,
    find_team_id_or_error,
    TeamNotFoundError,
    validate_date_format
)

logger = logging.getLogger(__name__)

@lru_cache(maxsize=128)
def fetch_team_info_and_roster_logic(
    team_identifier: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular, 
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches comprehensive team information including basic details, conference/division ranks,
    current season roster, and coaching staff for a specified team and season.

    Args:
        team_identifier (str): The team's name (e.g., "Los Angeles Lakers"), abbreviation (e.g., "LAL"), or ID (e.g., 1610612747).
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
                                Defaults to the `CURRENT_SEASON` config value.
        season_type (str, optional): The type of season. Valid values from `SeasonTypeAllStar`
                                     (e.g., "Regular Season", "Playoffs", "Pre Season", "All Star").
                                     Defaults to "Regular Season".
        league_id (str, optional): The league ID. Valid values from `LeagueID` (e.g., "00" for NBA, "10" for WNBA, "20" for G-League).
                                   Defaults to "00" (NBA).

    Returns:
        str: JSON string with team information.
             Expected dictionary structure passed to format_response:
             {
                 "team_id": int,
                 "team_name": str,
                 "season": str,
                 "season_type": str,
                 "league_id": str,
                 "info": { ... },
                 "ranks": { ... },
                 "roster": [ ... ],
                 "coaches": [ ... ],
                 "partial_errors": Optional[List[str]]
             }
             Or an {'error': 'Error message'} object if a critical issue occurs.
    """
    logger.info(f"Executing fetch_team_info_and_roster_logic for: '{team_identifier}', Season: {season}, Type: {season_type}, League: {league_id}")
    if not team_identifier or not str(team_identifier).strip():
        return format_response(error=Errors.TEAM_IDENTIFIER_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5]))) 

    VALID_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}
    if league_id not in VALID_LEAGUE_IDS:
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(VALID_LEAGUE_IDS)[:3])))

    try:
        team_id, team_actual_name = find_team_id_or_error(team_identifier)

        team_info_dict, team_ranks_dict, roster_list, coaches_list = {}, {}, [], []
        errors: List[str] = []

        logger.debug(f"Fetching teaminfocommon for Team ID: {team_id}, Season: {season}, Type: {season_type}, League: {league_id}")
        try:
            team_info_endpoint = teaminfocommon.TeamInfoCommon(
                team_id=team_id, season_nullable=season, league_id=league_id,
                season_type_nullable=season_type, timeout=DEFAULT_TIMEOUT
            )
            team_info_df = team_info_endpoint.team_info_common.get_data_frame()
            team_ranks_df = team_info_endpoint.team_season_ranks.get_data_frame()
            
            team_info_dict = _process_dataframe(team_info_df, single_row=True) if not team_info_df.empty else {}
            team_ranks_dict = _process_dataframe(team_ranks_df, single_row=True) if not team_ranks_df.empty else {}

            if team_info_df.empty and team_ranks_df.empty:
                 logger.warning(f"No team info/ranks data returned by API for team {team_id}, season {season}.")
            elif team_info_dict is None or team_ranks_dict is None: 
                 errors.append("team info/ranks processing")
                 logger.error(Errors.TEAM_PROCESSING.format(data_type="team info/ranks", identifier=str(team_id), season=season))


        except Exception as api_error:
            error_msg = Errors.TEAM_API.format(data_type="teaminfocommon", identifier=str(team_id), season=season, error=str(api_error))
            logger.error(error_msg, exc_info=True)
            errors.append("team info/ranks API")
            team_info_dict, team_ranks_dict = {}, {}

        logger.debug(f"Fetching commonteamroster for Team ID: {team_id}, Season: {season}, League: {league_id}")
        try:
            roster_endpoint = commonteamroster.CommonTeamRoster(
                team_id=team_id, season=season, league_id_nullable=league_id, timeout=DEFAULT_TIMEOUT
            )
            roster_df = roster_endpoint.common_team_roster.get_data_frame()
            coaches_df = roster_endpoint.coaches.get_data_frame()

            roster_list = _process_dataframe(roster_df, single_row=False) if not roster_df.empty else []
            coaches_list = _process_dataframe(coaches_df, single_row=False) if not coaches_df.empty else []
            
            if roster_df.empty and coaches_df.empty:
                logger.warning(f"No roster/coaches data returned by API for team {team_id}, season {season}.")
            elif roster_list is None or coaches_list is None: 
                errors.append("roster/coaches processing")
                logger.error(Errors.TEAM_PROCESSING.format(data_type="roster/coaches", identifier=str(team_id), season=season))

        except Exception as api_error:
            error_msg = Errors.TEAM_API.format(data_type="commonteamroster", identifier=str(team_id), season=season, error=str(api_error))
            logger.error(error_msg, exc_info=True)
            errors.append("roster/coaches API")
            roster_list, coaches_list = [], []

        if not team_info_dict and not team_ranks_dict and not roster_list and not coaches_list and errors:
            error_summary = Errors.TEAM_ALL_FAILED.format(identifier=team_identifier, season=season, errors_list=', '.join(errors))
            logger.error(error_summary)
            return format_response(error=error_summary)
        
        result = {
            "team_id": team_id, "team_name": team_actual_name, "season": season,
            "season_type": season_type, "league_id": league_id,
            "info": team_info_dict or {}, "ranks": team_ranks_dict or {},
            "roster": roster_list or [], "coaches": coaches_list or []
        }
        if errors: 
            result["partial_errors"] = errors

        logger.info(f"fetch_team_info_and_roster_logic completed for Team ID: {team_id}, Season: {season}")
        return format_response(result)

    except (TeamNotFoundError, ValueError) as e:
        logger.warning(f"Team lookup or validation failed for '{team_identifier}': {e}")
        return format_response(error=str(e))
    except Exception as e:
        error_msg = Errors.TEAM_UNEXPECTED.format(identifier=team_identifier, season=season, error=str(e))
        logger.critical(error_msg, exc_info=True)
        return format_response(error=error_msg)

@lru_cache(maxsize=128)
def fetch_team_stats_logic(
    team_identifier: str,
    season: str = CURRENT_SEASON,
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
    (Docstring content remains largely the same as before, detailing args and return structure)
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
    
    per_mode_simple_for_historical = per_mode 

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
                date_to_nullable=date_to, timeout=DEFAULT_TIMEOUT
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
            # dashboard_endpoint might not be assigned if the error occurs during its instantiation (within nba_api library)
            logger.error(f"API JSONDecodeError for team dashboard {team_id}, measure_type {measure_type}: {jde}", exc_info=True)
            # We cannot reliably get raw_response_text or request_url from dashboard_endpoint if it's not assigned.
            # The traceback from exc_info=True should provide context from nba_api library.
            dashboard_error = Errors.TEAM_API.format(data_type=f"team dashboard ({measure_type})", identifier=str(team_id), season=season, error=f"JSONDecodeError: {str(jde)}")
            dashboard_stats_dict = {}
        except Exception as api_error:
            # This will catch other errors during the try block for dashboard_stats
            dashboard_error = Errors.TEAM_API.format(data_type=f"team dashboard ({measure_type})", identifier=str(team_id), season=season, error=str(api_error))
            logger.error(dashboard_error, exc_info=True)
            dashboard_stats_dict = {}

        logger.debug(f"Fetching historical stats for Team ID: {team_id}, League: {league_id}, PerModeSimple: {per_mode_simple_for_historical}")
        try:
            historical_endpoint = teamyearbyyearstats.TeamYearByYearStats(
                team_id=team_id, league_id=league_id,
                season_type_all_star=season_type, 
                per_mode_simple=per_mode_simple_for_historical, 
                timeout=DEFAULT_TIMEOUT
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

@lru_cache(maxsize=128)
def fetch_team_passing_stats_logic(
    team_identifier: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game 
) -> str:
    """
    Fetches team passing statistics.
    (Docstring content remains largely the same as before, detailing args and return structure)
    """
    logger.info(f"Executing fetch_team_passing_stats_logic for: '{team_identifier}', Season: {season}, PerMode: {per_mode}")

    if not team_identifier or not str(team_identifier).strip():
        return format_response(error=Errors.TEAM_IDENTIFIER_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5])))

    VALID_PER_MODES = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}
    if per_mode not in VALID_PER_MODES:
        return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(VALID_PER_MODES)[:3])))

    try:
        team_id, team_actual_name = find_team_id_or_error(team_identifier)
        logger.debug(f"Fetching teamdashptpass for Team ID: {team_id}, Season: {season}, PerMode: {per_mode}")
        try:
            passing_stats_endpoint = teamdashptpass.TeamDashPtPass(
                team_id=team_id, season=season, season_type_all_star=season_type,
                per_mode_simple=per_mode, timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"teamdashptpass API call successful for ID: {team_id}, Season: {season}")
            passes_made_df = passing_stats_endpoint.passes_made.get_data_frame()
            passes_received_df = passing_stats_endpoint.passes_received.get_data_frame()
        except Exception as api_error:
            logger.error(f"nba_api teamdashptpass failed for ID {team_id}, Season {season}: {api_error}", exc_info=True)
            error_msg = Errors.TEAM_PASSING_API.format(identifier=str(team_id), season=season, error=str(api_error))
            return format_response(error=error_msg)

        passes_made_list = _process_dataframe(passes_made_df, single_row=False)
        passes_received_list = _process_dataframe(passes_received_df, single_row=False)

        if passes_made_list is None or passes_received_list is None:
            if passes_made_df.empty and passes_received_df.empty:
                logger.warning(f"No passing stats found for team {team_actual_name} ({team_id}), season {season}.")
                passes_made_list, passes_received_list = [], []
            else: 
                logger.error(f"DataFrame processing failed for team passing stats of {team_actual_name} ({season}).")
                error_msg = Errors.TEAM_PASSING_PROCESSING.format(identifier=str(team_id), season=season)
                return format_response(error=error_msg)


        result = {
            "team_name": team_actual_name, "team_id": team_id, "season": season, "season_type": season_type,
            "parameters": {"per_mode": per_mode},
            "passes_made": passes_made_list or [],
            "passes_received": passes_received_list or []
        }
        logger.info(f"fetch_team_passing_stats_logic completed for '{team_actual_name}'")
        return format_response(result)

    except (TeamNotFoundError, ValueError) as lookup_error:
        logger.warning(f"Team lookup or validation failed for '{team_identifier}': {lookup_error}")
        return format_response(error=str(lookup_error))
    except Exception as unexpected_error:
        error_msg = Errors.TEAM_PASSING_UNEXPECTED.format(identifier=team_identifier, season=season, error=str(unexpected_error))
        logger.critical(error_msg, exc_info=True)
        return format_response(error=error_msg)

# fetch_team_shooting_stats_logic and fetch_team_rebounding_stats_logic would follow a similar pattern
# with imports for their specific endpoints (e.g., teamdashptshots) and parameters.
# For brevity, they are omitted here but would need PerModeSimple imported if they use it.
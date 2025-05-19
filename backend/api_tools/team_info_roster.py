"""
Handles fetching comprehensive team information, including common details,
season ranks, roster, and coaching staff.
"""
import logging
from typing import Optional, Dict, List, Tuple, Any, Set
from functools import lru_cache

from nba_api.stats.endpoints import teaminfocommon, commonteamroster
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar

from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response,
    find_team_id_or_error,
    TeamNotFoundError
)
from ..utils.validation import _validate_season_format

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
TEAM_INFO_ROSTER_CACHE_SIZE = 128
_TEAM_INFO_VALID_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_TEAM_INFO_VALID_LEAGUE_IDS: Set[str] = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

# --- Helper Functions ---
def _fetch_team_details_and_ranks(
    team_id: int, season: str, season_type: str, league_id: str
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """Fetches and processes team info and season ranks from teaminfocommon."""
    info_dict, ranks_dict = {}, {}
    current_errors: List[str] = []
    logger.debug(f"Fetching teaminfocommon for Team ID: {team_id}, Season: {season}, Type: {season_type}, League: {league_id}")
    try:
        team_info_endpoint = teaminfocommon.TeamInfoCommon(
            team_id=team_id, season_nullable=season, league_id=league_id,
            season_type_nullable=season_type, timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        team_info_df = team_info_endpoint.team_info_common.get_data_frame()
        team_ranks_df = team_info_endpoint.team_season_ranks.get_data_frame()
        
        info_dict = _process_dataframe(team_info_df, single_row=True) if not team_info_df.empty else {}
        ranks_dict = _process_dataframe(team_ranks_df, single_row=True) if not team_ranks_df.empty else {}

        if team_info_df.empty and team_ranks_df.empty:
            logger.warning(f"No team info/ranks data returned by API for team {team_id}, season {season}.")
        # _process_dataframe returns None on internal error, or empty dict for empty df
        if info_dict is None or ranks_dict is None: # Check for None which indicates processing failure
             current_errors.append("team info/ranks processing")
             logger.error(Errors.TEAM_PROCESSING.format(data_type="team info/ranks", identifier=str(team_id), season=season))
             info_dict = info_dict or {} # Ensure they are dicts even if one failed
             ranks_dict = ranks_dict or {}
    except Exception as api_error:
        error_msg = Errors.TEAM_API.format(data_type="teaminfocommon", identifier=str(team_id), season=season, error=str(api_error))
        logger.error(error_msg, exc_info=True)
        current_errors.append("team info/ranks API")
    return info_dict or {}, ranks_dict or {}, current_errors

def _fetch_team_roster_and_coaches(
    team_id: int, season: str, league_id: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """Fetches and processes team roster and coaches from commonteamroster."""
    roster_list, coaches_list = [], []
    current_errors: List[str] = []
    logger.debug(f"Fetching commonteamroster for Team ID: {team_id}, Season: {season}, League: {league_id}")
    try:
        roster_endpoint = commonteamroster.CommonTeamRoster(
            team_id=team_id, season=season, league_id_nullable=league_id, timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        roster_df = roster_endpoint.common_team_roster.get_data_frame()
        coaches_df = roster_endpoint.coaches.get_data_frame()

        roster_list = _process_dataframe(roster_df, single_row=False) if not roster_df.empty else []
        coaches_list = _process_dataframe(coaches_df, single_row=False) if not coaches_df.empty else []
        
        if roster_df.empty and coaches_df.empty:
            logger.warning(f"No roster/coaches data returned by API for team {team_id}, season {season}.")
        if roster_list is None or coaches_list is None: # Check for None which indicates processing failure
            current_errors.append("roster/coaches processing")
            logger.error(Errors.TEAM_PROCESSING.format(data_type="roster/coaches", identifier=str(team_id), season=season))
            roster_list = roster_list or [] # Ensure they are lists even if one failed
            coaches_list = coaches_list or []
    except Exception as api_error:
        error_msg = Errors.TEAM_API.format(data_type="commonteamroster", identifier=str(team_id), season=season, error=str(api_error))
        logger.error(error_msg, exc_info=True)
        current_errors.append("roster/coaches API")
    return roster_list or [], coaches_list or [], current_errors

# --- Main Logic Function ---
@lru_cache(maxsize=TEAM_INFO_ROSTER_CACHE_SIZE)
def fetch_team_info_and_roster_logic(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches comprehensive team information including basic details, conference/division ranks,
    current season roster, and coaching staff for a specified team and season.
    """
    logger.info(f"Executing fetch_team_info_and_roster_logic for: '{team_identifier}', Season: {season}, Type: {season_type}, League: {league_id}")
    if not team_identifier or not str(team_identifier).strip():
        return format_response(error=Errors.TEAM_IDENTIFIER_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if season_type not in _TEAM_INFO_VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_TEAM_INFO_VALID_SEASON_TYPES)[:5])))
    if league_id not in _TEAM_INFO_VALID_LEAGUE_IDS:
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_TEAM_INFO_VALID_LEAGUE_IDS)[:3])))

    try:
        team_id, team_actual_name = find_team_id_or_error(team_identifier)
        all_errors: List[str] = []

        team_info_dict, team_ranks_dict, info_errors = _fetch_team_details_and_ranks(team_id, season, season_type, league_id)
        all_errors.extend(info_errors)

        roster_list, coaches_list, roster_errors = _fetch_team_roster_and_coaches(team_id, season, league_id)
        all_errors.extend(roster_errors)

        if not team_info_dict and not team_ranks_dict and not roster_list and not coaches_list and all_errors:
            error_summary = Errors.TEAM_ALL_FAILED.format(identifier=team_identifier, season=season, errors_list=', '.join(all_errors))
            logger.error(error_summary)
            return format_response(error=error_summary)
        
        result = {
            "team_id": team_id, "team_name": team_actual_name, "season": season,
            "season_type": season_type, "league_id": league_id,
            "info": team_info_dict, "ranks": team_ranks_dict,
            "roster": roster_list, "coaches": coaches_list
        }
        if all_errors:
            result["partial_errors"] = all_errors

        logger.info(f"fetch_team_info_and_roster_logic completed for Team ID: {team_id}, Season: {season}")
        return format_response(result)

    except (TeamNotFoundError, ValueError) as e: # Handles find_team_id_or_error issues
        logger.warning(f"Team lookup or validation failed for '{team_identifier}': {e}")
        return format_response(error=str(e))
    except Exception as e: # Catch-all for unexpected issues in the main orchestration
        error_msg = Errors.TEAM_UNEXPECTED.format(identifier=team_identifier, season=season, error=str(e))
        logger.critical(error_msg, exc_info=True)
        return format_response(error=error_msg)
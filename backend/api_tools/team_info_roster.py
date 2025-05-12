import logging
import json
from typing import Optional, Dict, List, Tuple, Any
from functools import lru_cache

from nba_api.stats.endpoints import teaminfocommon, commonteamroster
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar

from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response,
    find_team_id_or_error,
    TeamNotFoundError
)
from backend.utils.validation import _validate_season_format # Import from new location

logger = logging.getLogger(__name__)

@lru_cache(maxsize=128)
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
                season_type_nullable=season_type, timeout=settings.DEFAULT_TIMEOUT_SECONDS
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
                team_id=team_id, season=season, league_id_nullable=league_id, timeout=settings.DEFAULT_TIMEOUT_SECONDS
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
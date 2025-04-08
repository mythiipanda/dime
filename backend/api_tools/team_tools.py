import logging
import json
from typing import Optional, Dict, List
import pandas as pd
from nba_api.stats.static import teams
from nba_api.stats.endpoints import teaminfocommon, commonteamroster
from nba_api.stats.library.parameters import LeagueID

from config import DEFAULT_TIMEOUT, CURRENT_SEASON, ErrorMessages as Errors
from .utils import _process_dataframe, _validate_season_format

logger = logging.getLogger(__name__)

def _find_team_id(team_identifier: str) -> Optional[int]:
    """
    Finds a team's ID from abbreviation or full name.
    """
    logger.debug(f"Searching for team ID using identifier: '{team_identifier}'")
    team_info = teams.find_team_by_abbreviation(team_identifier.upper())
    if team_info:
        logger.info(f"Found team by abbreviation: {team_info['full_name']} (ID: {team_info['id']})")
        return team_info['id']
    team_list = teams.find_teams_by_full_name(team_identifier)
    if team_list:
        team_info = team_list[0]
        logger.info(f"Found team by full name: {team_info['full_name']} (ID: {team_info['id']})")
        return team_info['id']
    logger.warning(f"Team not found for identifier: '{team_identifier}'")
    return None

def fetch_team_info_and_roster_logic(team_identifier: str, season: str = CURRENT_SEASON) -> str:
    """
    Fetches team info, ranks, roster, and coaches.
    Returns JSON string.
    """
    logger.info(f"Executing fetch_team_info_and_roster_logic for: '{team_identifier}', Season: {season}")
    if not team_identifier or not team_identifier.strip():
        return json.dumps({"error": Errors.TEAM_IDENTIFIER_EMPTY})
    if not season or not _validate_season_format(season):
        return json.dumps({"error": Errors.INVALID_SEASON_FORMAT.format(season=season)})

    try:
        team_id = _find_team_id(team_identifier)
        if team_id is None:
            return json.dumps({"error": Errors.TEAM_NOT_FOUND.format(identifier=team_identifier)})

        team_info_dict, team_ranks_dict, roster_list, coaches_list = {}, {}, [], []
        errors: List[str] = []

        logger.debug(f"Fetching teaminfocommon for Team ID: {team_id}, Season: {season}")
        try:
            team_info_endpoint = teaminfocommon.TeamInfoCommon(
                team_id=team_id,
                season_nullable=season,
                league_id=LeagueID.nba,
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"teaminfocommon API call successful for ID: {team_id}")
            team_info_dict = _process_dataframe(team_info_endpoint.team_info_common.get_data_frame(), single_row=True)
            team_ranks_dict = _process_dataframe(team_info_endpoint.team_season_ranks.get_data_frame(), single_row=True)
            if team_info_dict is None or team_ranks_dict is None:
                errors.append("team info/ranks processing")
                logger.error(Errors.TEAM_PROCESSING.format(data_type="team info/ranks", identifier=team_id))
        except Exception as api_error:
            logger.error(Errors.TEAM_API.format(data_type="teaminfocommon", identifier=team_id, error=api_error), exc_info=True)
            errors.append("team info/ranks API")

        logger.debug(f"Fetching commonteamroster for Team ID: {team_id}, Season: {season}")
        try:
            roster_endpoint = commonteamroster.CommonTeamRoster(
                team_id=team_id,
                season=season,
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"commonteamroster API call successful for ID: {team_id}")
            roster_list = _process_dataframe(roster_endpoint.common_team_roster.get_data_frame(), single_row=False)
            coaches_list = _process_dataframe(roster_endpoint.coaches.get_data_frame(), single_row=False)
            if roster_list is None or coaches_list is None:
                errors.append("roster/coaches processing")
                logger.error(Errors.TEAM_PROCESSING.format(data_type="roster/coaches", identifier=team_id))
        except Exception as api_error:
            logger.error(Errors.TEAM_API.format(data_type="commonteamroster", identifier=team_id, error=api_error), exc_info=True)
            errors.append("roster/coaches API")

        if not team_info_dict and not team_ranks_dict and not roster_list and not coaches_list:
            logger.error(Errors.TEAM_ALL_FAILED.format(identifier=team_identifier, season=season, errors=', '.join(errors)))
            return json.dumps({"error": Errors.TEAM_ALL_FAILED.format(identifier=team_identifier, season=season, errors=', '.join(errors))})

        result = {
            "team_info": team_info_dict or {},
            "team_ranks": team_ranks_dict or {},
            "roster": roster_list or [],
            "coaches": coaches_list or [],
            "fetch_errors": errors
        }
        logger.info(f"fetch_team_info_and_roster_logic completed for Team ID: {team_id}, Season: {season}")
        return json.dumps(result, default=str)
    except Exception as e:
        logger.critical(Errors.TEAM_UNEXPECTED.format(identifier=team_identifier, season=season, error=str(e)), exc_info=True)
        return json.dumps({"error": Errors.TEAM_UNEXPECTED.format(identifier=team_identifier, season=season, error=str(e))})
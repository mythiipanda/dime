# Team tracking logic functions
import logging
import json
from typing import Optional, Tuple

from nba_api.stats.endpoints import (
    teamdashptpass,
    teamdashptreb,
    teamdashptshots
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed # Ensure this is imported
)

from config import DEFAULT_TIMEOUT, ErrorMessages # Import ErrorMessages directly
from api_tools.utils import _process_dataframe, retry_on_timeout, format_response
from api_tools.team_tools import _find_team_id # Import the helper

logger = logging.getLogger(__name__)

def fetch_team_passing_stats_logic(team_identifier: str, season: str, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerModeDetailed.per_game) -> str:
    """
    Fetch team passing stats from NBA API. Accepts team name or ID.
    """
    logger.info(f"Fetching team passing stats for: {team_identifier}, Season: {season}, Mode: {per_mode}")
    if not team_identifier or not season:
        logger.warning("Team identifier or season is missing.")
        return format_response(error=ErrorMessages.TEAM_IDENTIFIER_EMPTY if not team_identifier else ErrorMessages.INVALID_SEASON_FORMAT.format(season=season))

    team_id, team_name = _find_team_id(team_identifier) # Get both ID and name

    # If team_id is None here, _find_team_id failed, return the error immediately
    if team_id is None:
        logger.warning(f"Team not found for identifier: {team_identifier}")
        return format_response(error=ErrorMessages.TEAM_NOT_FOUND.format(identifier=team_identifier))

    try:
        logger.debug(f"Attempting API call for team ID: {team_id}")
        passing_stats_endpoint = teamdashptpass.TeamDashPtPass(
            team_id=str(team_id), # Ensure team_id is string if needed by API
            season=season,
            season_type_all_star=season_type,
            per_mode_simple=per_mode, # Pass per_mode here
            timeout=DEFAULT_TIMEOUT
        )
        # Use get_normalized_dict which might be more robust or get_dict if needed
        data = passing_stats_endpoint.get_normalized_dict()
        # Check if data is empty or indicates an error implicitly
        if not data or not any(data.values()):
             logger.warning(f"No passing data returned for team {team_id}, season {season}")
             return format_response({"message": "No passing data found for the specified parameters."}) # Return empty data message
        # Add input parameters to the response dictionary
        response_data = {
            "team_id": team_id,
            "team_name": team_name,
            "season": season,
            "season_type": season_type,
            **data # Unpack the fetched data sets
        }
        return format_response(response_data)
    except KeyError as ke:
        # Specifically handle the 'resultSet' error if it persists from the library
        if 'resultSet' in str(ke):
             logger.error(f"KeyError 'resultSet' fetching team passing stats for team {team_id}: {str(ke)}", exc_info=True)
             return format_response(error="API response format error (missing 'resultSet').")
        else:
             logger.error(f"KeyError fetching team passing stats for team {team_id}: {str(ke)}", exc_info=True)
             return format_response(error=f"Unexpected data key error: {str(ke)}")
    except Exception as e:
        logger.error(f"Error fetching team passing stats for team {team_id}: {str(e)}", exc_info=True)
        return format_response(error=f"API error fetching passing stats: {str(e)}")


def fetch_team_rebounding_stats_logic(team_identifier: str, season: str, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerModeDetailed.per_game) -> str:
    """
    Fetch team rebounding stats from NBA API. Accepts team name or ID.
    """
    logger.info(f"Fetching team rebounding stats for: {team_identifier}, Season: {season}, Mode: {per_mode}")
    if not team_identifier or not season:
        logger.warning("Team identifier or season is missing.")
        return format_response(error=ErrorMessages.TEAM_IDENTIFIER_EMPTY if not team_identifier else ErrorMessages.INVALID_SEASON_FORMAT.format(season=season))

    team_id, team_name = _find_team_id(team_identifier)

    # If team_id is None here, _find_team_id failed, return the error immediately
    if team_id is None:
        logger.warning(f"Team not found for identifier: {team_identifier}")
        return format_response(error=ErrorMessages.TEAM_NOT_FOUND.format(identifier=team_identifier))

    try:
        logger.debug(f"Attempting API call for team ID: {team_id}")
        rebounding_stats_endpoint = teamdashptreb.TeamDashPtReb(
            team_id=str(team_id),
            season=season,
            season_type_all_star=season_type,
            per_mode_simple=per_mode, # Pass per_mode here
            timeout=DEFAULT_TIMEOUT
        )
        data = rebounding_stats_endpoint.get_normalized_dict()
        if not data or not any(data.values()):
             logger.warning(f"No rebounding data returned for team {team_id}, season {season}")
             return format_response({"message": "No rebounding data found for the specified parameters."})
        # Add input parameters to the response dictionary
        response_data = {
            "team_id": team_id,
            "team_name": team_name,
            "season": season,
            "season_type": season_type,
            **data
        }
        return format_response(response_data)
    except KeyError as ke:
        if 'resultSet' in str(ke):
             logger.error(f"KeyError 'resultSet' fetching team rebounding stats for team {team_id}: {str(ke)}", exc_info=True)
             return format_response(error="API response format error (missing 'resultSet').")
        else:
             logger.error(f"KeyError fetching team rebounding stats for team {team_id}: {str(ke)}", exc_info=True)
             return format_response(error=f"Unexpected data key error: {str(ke)}")
    except Exception as e:
        logger.error(f"Error fetching team rebounding stats for team {team_id}: {str(e)}", exc_info=True)
        return format_response(error=f"API error fetching rebounding stats: {str(e)}")


def fetch_team_shooting_stats_logic(team_identifier: str, season: str, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerModeDetailed.per_game) -> str:
    """
    Fetch team shooting stats from NBA API. Accepts team name or ID.
    """
    logger.info(f"Fetching team shooting stats for: {team_identifier}, Season: {season}, Mode: {per_mode}")
    if not team_identifier or not season:
        logger.warning("Team identifier or season is missing.")
        return format_response(error=ErrorMessages.TEAM_IDENTIFIER_EMPTY if not team_identifier else ErrorMessages.INVALID_SEASON_FORMAT.format(season=season))

    team_id, team_name = _find_team_id(team_identifier)

    # If team_id is None here, _find_team_id failed, return the error immediately
    if team_id is None:
        logger.warning(f"Team not found for identifier: {team_identifier}")
        return format_response(error=ErrorMessages.TEAM_NOT_FOUND.format(identifier=team_identifier))

    try:
        logger.debug(f"Attempting API call for team ID: {team_id}")
        shooting_stats_endpoint = teamdashptshots.TeamDashPtShots(
            team_id=str(team_id),
            season=season,
            season_type_all_star=season_type,
            per_mode_simple=per_mode, # Pass per_mode here
            timeout=DEFAULT_TIMEOUT
        )
        data = shooting_stats_endpoint.get_normalized_dict()
        if not data or not any(data.values()):
             logger.warning(f"No shooting data returned for team {team_id}, season {season}")
             return format_response({"message": "No shooting data found for the specified parameters."})
        # Add input parameters to the response dictionary
        response_data = {
            "team_id": team_id,
            "team_name": team_name,
            "season": season,
            "season_type": season_type,
            **data
        }
        return format_response(response_data)
    except KeyError as ke:
        if 'resultSet' in str(ke):
             logger.error(f"KeyError 'resultSet' fetching team shooting stats for team {team_id}: {str(ke)}", exc_info=True)
             return format_response(error="API response format error (missing 'resultSet').")
        else:
             logger.error(f"KeyError fetching team shooting stats for team {team_id}: {str(ke)}", exc_info=True)
             return format_response(error=f"Unexpected data key error: {str(ke)}")
    except Exception as e:
        logger.error(f"Error fetching team shooting stats for team {team_id}: {str(e)}", exc_info=True)
        return format_response(error=f"API error fetching shooting stats: {str(e)}")

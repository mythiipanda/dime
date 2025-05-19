import logging
import json
from typing import Optional, Dict, Any, Union, Tuple, List, Set
import pandas as pd
from nba_api.stats.endpoints import teamhistoricalleaders
from nba_api.stats.library.parameters import LeagueID # For default value
from ..config import settings
from ..core.errors import Errors
from .utils import format_response, _process_dataframe, find_team_id_or_error, TeamNotFoundError
from ..utils.validation import _validate_league_id # Assuming this exists and is appropriate

logger = logging.getLogger(__name__)

# Define valid league IDs, similar to other tools if not using _validate_league_id directly
_VALID_LEAGUE_IDS_HISTORICAL: Set[str] = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}


def _validate_season_id_format(season_id: str) -> bool:
    """Validates that the season_id is a 5-digit string."""
    return isinstance(season_id, str) and len(season_id) == 5 and season_id.isdigit()

def fetch_team_historical_leaders_logic(
    team_identifier: str,
    season_id: str, # e.g., "22022" for 2022-23 season
    league_id: str = LeagueID.nba, # Default to NBA "00"
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches historical career leaders for a specific team and season.

    The 'SeasonID' parameter for this endpoint refers to the season for which
    the historical leaders are being requested (e.g., if you want to see who
    the historical leaders were as of the end of the 2022-23 season, you would use "22022").

    Args:
        team_identifier (str): The name, abbreviation, or ID of the team.
        season_id (str): The 5-digit season ID (e.g., "22022" for the 2022-23 season).
                         This specifies the point in time for which to retrieve historical leaders.
        league_id (str, optional): The league ID. Defaults to "00" (NBA).
                                   Other examples: "10" (WNBA), "20" (G-League).
        return_dataframe (bool, optional): Whether to return DataFrames along with the JSON response. 
                                           Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: 
            If return_dataframe is False, a JSON string with the team historical leaders data or an error.
            If return_dataframe is True, a tuple containing the JSON response string and a dictionary 
            of DataFrames: {'career_leaders_by_team': df}.
    """
    dataframes: Dict[str, pd.DataFrame] = {}
    logger.info(
        f"Executing fetch_team_historical_leaders_logic for team: '{team_identifier}', "
        f"SeasonID: {season_id}, LeagueID: {league_id}, DataFrame: {return_dataframe}"
    )

    # Parameter Validations
    if not team_identifier or not str(team_identifier).strip():
        error_msg = Errors.TEAM_IDENTIFIER_EMPTY
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    if not _validate_season_id_format(season_id):
        error_msg = Errors.INVALID_PARAMETER_FORMAT.format(param_name="SeasonID", param_value=season_id, expected_format="a 5-digit string (e.g., '22022')")
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    # Use _validate_league_id if it's suitable, otherwise use the set directly
    if not _validate_league_id(league_id): # Or: if league_id not in _VALID_LEAGUE_IDS_HISTORICAL:
        error_msg = Errors.INVALID_LEAGUE_ID.format(value=league_id, options=list(_VALID_LEAGUE_IDS_HISTORICAL)[:3])
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    try:
        team_id_actual, team_actual_name = find_team_id_or_error(team_identifier)
    except (TeamNotFoundError, ValueError) as e:
        logger.warning(f"Team lookup failed for '{team_identifier}': {e}")
        if return_dataframe: return format_response(error=str(e)), dataframes
        return format_response(error=str(e))

    try:
        logger.debug(f"Calling TeamHistoricalLeaders API for TeamID: {team_id_actual}, SeasonID: {season_id}")
        endpoint = teamhistoricalleaders.TeamHistoricalLeaders(
            team_id=team_id_actual,
            season_id=season_id,
            league_id=league_id,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        
        career_leaders_df = endpoint.career_leaders_by_team.get_data_frame()

        if return_dataframe:
            dataframes["career_leaders_by_team"] = career_leaders_df

        processed_leaders = _process_dataframe(career_leaders_df, single_row=False) # Returns a list of dicts

        if processed_leaders is None: # Indicates a processing error in _process_dataframe
             error_msg = Errors.PROCESSING_ERROR.format(error=f"Failed to process TeamHistoricalLeaders data for team {team_actual_name}, season_id {season_id}")
             logger.error(error_msg)
             if return_dataframe: return format_response(error=error_msg), dataframes
             return format_response(error=error_msg)
        
        if not processed_leaders and career_leaders_df.empty:
            logger.info(f"No historical leaders data returned by API for team {team_actual_name}, season_id {season_id}.")
            # This is not necessarily an error, API might return empty for some valid queries.

        response_data = {
            "team_name": team_actual_name,
            "team_id": team_id_actual,
            "parameters": {
                "season_id": season_id,
                "league_id": league_id
            },
            "career_leaders_by_team": processed_leaders
        }
        
        logger.info(f"Successfully fetched TeamHistoricalLeaders for team {team_actual_name}, season_id {season_id}")
        if return_dataframe:
            return format_response(response_data), dataframes
        return format_response(response_data)

    except Exception as e:
        logger.error(
            f"API error in fetch_team_historical_leaders_logic for team '{team_actual_name}', season_id {season_id}: {e}",
            exc_info=True
        )
        error_msg = Errors.API_ERROR.format(error=f"Endpoint: TeamHistoricalLeaders, Team: {team_actual_name}, SeasonID: {season_id}, Details: {str(e)}")
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

# Example Error strings to add to backend/core/errors.py if they don't exist:
# class Errors:
#     ...
#     INVALID_SEASON_ID_FORMAT = "Invalid SeasonID format: '{season_id}'. Must be a 5-digit string (e.g., '22022')."
#     PROCESSING_ERROR = "An error occurred while processing data for {data_type}."
#     # NBA_API_ERROR = "NBA API request failed for endpoint {endpoint_name}: {error}" # Keep if distinct, else use API_ERROR
#     ... 
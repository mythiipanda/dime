import logging
from functools import lru_cache

from nba_api.stats.endpoints import CommonTeamYears
from nba_api.stats.library.parameters import LeagueID

from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response
)
from backend.utils.validation import _validate_league_id

logger = logging.getLogger(__name__)

@lru_cache(maxsize=settings.DEFAULT_LRU_CACHE_SIZE) # Keep a small cache for this relatively static data
def fetch_common_team_years_logic(league_id: str = LeagueID.nba) -> str:
    """
    Fetches a list of all team years for a given league, indicating the range of seasons each team existed.

    Args:
        league_id (str, optional): The league ID. Defaults to "00" (NBA).
                                   Valid examples: "00" (NBA), "10" (WNBA), "20" (G-League).

    Returns:
        str: JSON string containing a list of team year details or an error message.
             Expected structure:
             {
                 "parameters": {"league_id": str},
                 "team_years": [
                     {
                         "LEAGUE_ID": str, "TEAM_ID": int, "MIN_YEAR": str,
                         "MAX_YEAR": str, "ABBREVIATION": str
                     }, ...
                 ]
             }
    """
    logger.info(f"Executing fetch_common_team_years_logic for LeagueID: {league_id}")

    if not _validate_league_id(league_id):
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=["00", "10", "20"])) 

    try:
        team_years_endpoint = CommonTeamYears(
            league_id=league_id,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"CommonTeamYears API call successful for LeagueID: {league_id}")

        team_years_df = team_years_endpoint.team_years.get_data_frame()
        
        team_years_list = _process_dataframe(team_years_df, single_row=False)

        if team_years_list is None:
            logger.error(f"DataFrame processing failed for CommonTeamYears (LeagueID: {league_id}).")
            return format_response(error=Errors.COMMON_TEAM_YEARS_API_ERROR.format(error="DataFrame processing returned None unexpectedly."))

        response_data = {
            "parameters": {"league_id": league_id},
            "team_years": team_years_list
        }
        
        logger.info(f"Successfully fetched {len(team_years_list)} team year entries for LeagueID: {league_id}")
        return format_response(response_data)

    except Exception as e:
        logger.error(
            f"Error in fetch_common_team_years_logic for LeagueID {league_id}: {str(e)}",
            exc_info=True
        )
        return format_response(error=Errors.COMMON_TEAM_YEARS_API_ERROR.format(error=str(e))) 
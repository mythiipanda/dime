import logging
from functools import lru_cache
from typing import Optional

from nba_api.stats.endpoints import CommonPlayoffSeries
from nba_api.stats.library.parameters import LeagueID

from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response
)
from ..utils.validation import _validate_season_format, _validate_league_id

logger = logging.getLogger(__name__)

@lru_cache(maxsize=settings.DEFAULT_LRU_CACHE_SIZE)
def fetch_common_playoff_series_logic(
    season: str,
    league_id: str = LeagueID.nba,
    series_id: Optional[str] = None
) -> str:
    """
    Fetches information about playoff series for a given league and season.
    Can optionally be filtered by a specific SeriesID.

    Args:
        season (str): The NBA season identifier in YYYY-YY format (e.g., "2022-23").
        league_id (str, optional): The league ID. Defaults to "00" (NBA).
        series_id (Optional[str], optional): A specific SeriesID to filter for. Defaults to None.
                                            The NBA API docs refer to this as series_id_nullable.

    Returns:
        str: JSON string containing a list of playoff series game details or an error message.
             Expected structure:
             {
                 "parameters": {"season": str, "league_id": str, "series_id": Optional[str]},
                 "playoff_series": [
                     {
                         "GAME_ID": str, "HOME_TEAM_ID": int, "VISITOR_TEAM_ID": int,
                         "SERIES_ID": str, "GAME_NUM": int
                     }, ...
                 ]
             }
    """
    logger.info(
        f"Executing fetch_common_playoff_series_logic for Season: {season}, LeagueID: {league_id}, "
        f"SeriesID: {series_id}"
    )

    if not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if not _validate_league_id(league_id):
        # Specify valid options for clarity in the error message
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=["00", "10", "20"])) 
    
    # series_id can be None, so no specific validation on its format other than being a string if provided.
    # The API handles empty string or None for series_id_nullable.

    try:
        playoff_series_endpoint = CommonPlayoffSeries(
            league_id=league_id,
            season=season,
            series_id_nullable=series_id, # Parameter name as per nba_api
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"CommonPlayoffSeries API call successful for Season: {season}, SeriesID: {series_id}")

        series_df = playoff_series_endpoint.playoff_series.get_data_frame()
        
        series_list = _process_dataframe(series_df, single_row=False)

        if series_list is None: # Should not happen with single_row=False
            logger.error(f"DataFrame processing failed for CommonPlayoffSeries (Season: {season}, SeriesID: {series_id}).")
            return format_response(error=Errors.COMMON_PLAYOFF_SERIES_API_ERROR.format(error="DataFrame processing returned None unexpectedly."))

        response_data = {
            "parameters": {
                "season": season,
                "league_id": league_id,
                "series_id": series_id
            },
            "playoff_series": series_list
        }
        
        logger.info(f"Successfully fetched {len(series_list)} series entries for Season: {season}, LeagueID: {league_id}, SeriesID: {series_id}")
        return format_response(response_data)

    except Exception as e:
        logger.error(
            f"Error in fetch_common_playoff_series_logic for Season {season}, LeagueID {league_id}, SeriesID {series_id}: {str(e)}",
            exc_info=True
        )
        return format_response(error=Errors.COMMON_PLAYOFF_SERIES_API_ERROR.format(error=str(e))) 
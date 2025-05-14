import logging
from functools import lru_cache
from typing import Optional

from nba_api.stats.endpoints import CommonAllPlayers
from nba_api.stats.library.parameters import LeagueID

from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response
)
from backend.utils.validation import _validate_season_format, _validate_league_id

logger = logging.getLogger(__name__)

@lru_cache(maxsize=settings.DEFAULT_LRU_CACHE_SIZE)
def fetch_common_all_players_logic(
    season: str,
    league_id: str = LeagueID.nba,
    is_only_current_season: int = 1 # 1 for current season only, 0 for all players historically linked to that season
) -> str:
    """
    Fetches a list of all players for a given league and season, or all players historically
    if is_only_current_season is set to 0.

    Args:
        season (str): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
        league_id (str, optional): The league ID. Defaults to "00" (NBA).
        is_only_current_season (int, optional): Flag to filter for only the current season's active players (1)
                                                 or all players historically associated with that season context (0).
                                                 Defaults to 1.

    Returns:
        str: JSON string containing a list of players or an error message.
             Expected structure:
             {
                 "parameters": {"season": str, "league_id": str, "is_only_current_season": int},
                 "players": [
                     {
                         "PERSON_ID": int, "DISPLAY_LAST_COMMA_FIRST": str, "DISPLAY_FIRST_LAST": str,
                         "ROSTERSTATUS": int (0 or 1), "FROM_YEAR": int, "TO_YEAR": int,
                         "PLAYERCODE": str, "TEAM_ID": int, "TEAM_CITY": str, "TEAM_NAME": str,
                         "TEAM_ABBREVIATION": str, "TEAM_CODE": str, "GAMES_PLAYED_FLAG": str ("Y" or "N"),
                         "OTHERLEAGUE_EXPERIENCE_CH": str
                     }, ...
                 ]
             }
    """
    logger.info(
        f"Executing fetch_common_all_players_logic for Season: {season}, LeagueID: {league_id}, "
        f"IsOnlyCurrentSeason: {is_only_current_season}"
    )

    if not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if not _validate_league_id(league_id):
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=["00", "10", "20"])) # Specify valid options
    if is_only_current_season not in [0, 1]:
        return format_response(error=Errors.INVALID_PARAMETER_FORMAT.format(
            param_name="is_only_current_season",
            param_value=is_only_current_season,
            expected_format="0 or 1"
        ))

    try:
        common_all_players_endpoint = CommonAllPlayers(
            is_only_current_season=is_only_current_season,
            league_id=league_id,
            season=season,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"CommonAllPlayers API call successful for Season: {season}")

        players_df = common_all_players_endpoint.common_all_players.get_data_frame()
        
        # _process_dataframe handles empty DFs by returning an empty list or None if single_row=True
        # For CommonAllPlayers, we expect a list of players.
        players_list = _process_dataframe(players_df, single_row=False) 

        if players_list is None: # Should not happen if single_row=False, but defensive check
             logger.error(f"DataFrame processing failed for CommonAllPlayers (Season: {season}).")
             return format_response(error=Errors.COMMON_ALL_PLAYERS_API_ERROR.format(error="DataFrame processing returned None unexpectedly."))


        response_data = {
            "parameters": {
                "season": season,
                "league_id": league_id,
                "is_only_current_season": is_only_current_season
            },
            "players": players_list
        }
        
        logger.info(f"Successfully fetched {len(players_list)} players for Season: {season}, LeagueID: {league_id}, IsOnlyCurrentSeason: {is_only_current_season}")
        return format_response(response_data)

    except Exception as e:
        logger.error(
            f"Error in fetch_common_all_players_logic for Season {season}, LeagueID {league_id}: {str(e)}",
            exc_info=True
        )
        # Use the specific error constant
        return format_response(error=Errors.COMMON_ALL_PLAYERS_API_ERROR.format(error=str(e))) 
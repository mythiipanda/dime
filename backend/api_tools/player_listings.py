import logging
import os
from functools import lru_cache
from typing import Optional, Dict, Any, Union, Tuple
import pandas as pd

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

# --- Cache Directory Setup ---
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
PLAYER_LISTINGS_CSV_DIR = os.path.join(CSV_CACHE_DIR, "player_listings")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(PLAYER_LISTINGS_CSV_DIR, exist_ok=True)

# --- Helper Functions ---
def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves a DataFrame to a CSV file.

    Args:
        df: DataFrame to save
        file_path: Path to save the CSV file
    """
    try:
        df.to_csv(file_path, index=False)
        logger.info(f"Saved DataFrame to CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)

def _get_csv_path_for_player_listings(season: str, league_id: str, is_only_current_season: int) -> str:
    """
    Generates a file path for saving a player listings DataFrame as CSV.

    Args:
        season: The season in YYYY-YY format
        league_id: The league ID
        is_only_current_season: Flag for current season only (1) or all players (0)

    Returns:
        Path to the CSV file
    """
    filename = f"players_{season}_{league_id}_{is_only_current_season}.csv"
    return os.path.join(PLAYER_LISTINGS_CSV_DIR, filename)

def fetch_common_all_players_logic(
    season: str,
    league_id: str = LeagueID.nba,
    is_only_current_season: int = 1, # 1 for current season only, 0 for all players historically linked to that season
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches a list of all players for a given league and season, or all players historically
    if is_only_current_season is set to 0.

    Provides DataFrame output capabilities.

    Args:
        season: The NBA season identifier in YYYY-YY format (e.g., "2023-24").
        league_id: The league ID. Defaults to "00" (NBA).
        is_only_current_season: Flag to filter for only the current season's active players (1)
                               or all players historically associated with that season context (0).
                               Defaults to 1.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
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
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(
        f"Executing fetch_common_all_players_logic for Season: {season}, LeagueID: {league_id}, "
        f"IsOnlyCurrentSeason: {is_only_current_season}, return_dataframe={return_dataframe}"
    )

    if not _validate_season_format(season):
        error_response = format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
        if return_dataframe:
            return error_response, {}
        return error_response

    if not _validate_league_id(league_id):
        error_response = format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=["00", "10", "20"]))
        if return_dataframe:
            return error_response, {}
        return error_response

    if is_only_current_season not in [0, 1]:
        error_response = format_response(error=Errors.INVALID_PARAMETER_FORMAT.format(
            param_name="is_only_current_season",
            param_value=is_only_current_season,
            expected_format="0 or 1"
        ))
        if return_dataframe:
            return error_response, {}
        return error_response

    try:
        # Fetch data from the API
        common_all_players_endpoint = CommonAllPlayers(
            is_only_current_season=is_only_current_season,
            league_id=league_id,
            season=season,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"CommonAllPlayers API call successful for Season: {season}")

        # Get DataFrame
        players_df = common_all_players_endpoint.common_all_players.get_data_frame()

        # Save to CSV if returning DataFrame
        if return_dataframe:
            csv_path = _get_csv_path_for_player_listings(season, league_id, is_only_current_season)
            _save_dataframe_to_csv(players_df, csv_path)

        # Process the DataFrame for JSON response
        players_list = _process_dataframe(players_df, single_row=False)

        if players_list is None: # Should not happen if single_row=False, but defensive check
            logger.error(f"DataFrame processing failed for CommonAllPlayers (Season: {season}).")
            error_response = format_response(error=Errors.COMMON_ALL_PLAYERS_API_ERROR.format(error="DataFrame processing returned None unexpectedly."))
            if return_dataframe:
                return error_response, {}
            return error_response

        # Create the result dictionary
        response_data = {
            "parameters": {
                "season": season,
                "league_id": league_id,
                "is_only_current_season": is_only_current_season
            },
            "players": players_list
        }

        logger.info(f"Successfully fetched {len(players_list)} players for Season: {season}, LeagueID: {league_id}, IsOnlyCurrentSeason: {is_only_current_season}")

        # Return the appropriate result based on return_dataframe
        if return_dataframe:
            dataframes = {
                "players": players_df
            }
            return format_response(response_data), dataframes

        return format_response(response_data)

    except Exception as e:
        logger.error(
            f"Error in fetch_common_all_players_logic for Season {season}, LeagueID {league_id}: {str(e)}",
            exc_info=True
        )
        # Use the specific error constant
        error_response = format_response(error=Errors.COMMON_ALL_PLAYERS_API_ERROR.format(error=str(e)))
        if return_dataframe:
            return error_response, {}
        return error_response
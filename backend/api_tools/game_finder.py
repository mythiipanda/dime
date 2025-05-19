"""
Handles fetching league game data using the LeagueGameFinder endpoint.
Includes logic for parameter validation, post-fetch date filtering (due to API instability
with date range parameters), and result limiting for broad queries.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import pandas as pd
from typing import Optional, List, Dict, Any, Set, Union, Tuple
from datetime import datetime
from functools import lru_cache
from nba_api.stats.endpoints import leaguegamefinder
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar
from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response
)
from ..utils.validation import _validate_season_format, validate_date_format
from ..utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
GAME_FINDER_CACHE_SIZE = 32
VALID_PLAYER_TEAM_ABBREVIATIONS = ['P', 'T']
MAX_GAME_FINDER_RESULTS = 200
DATE_FORMAT_YYYY_MM_DD = '%Y-%m-%d'

_VALID_GAME_FINDER_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str) and attr != 'default'}
_VALID_GAME_FINDER_LEAGUE_IDS: Set[str] = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

# --- Cache Directory Setup ---
GAME_FINDER_CSV_DIR = get_cache_dir("game_finder")

# --- Helper Functions for CSV Caching ---
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

def _get_csv_path_for_game_finder(
    player_or_team_abbreviation: str,
    player_id_nullable: Optional[int] = None,
    team_id_nullable: Optional[int] = None,
    season_nullable: Optional[str] = None,
    season_type_nullable: Optional[str] = None,
    league_id_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None
) -> str:
    """
    Generates a file path for saving game finder DataFrame as CSV.

    Args:
        player_or_team_abbreviation: 'P' for player or 'T' for team
        player_id_nullable: Player ID
        team_id_nullable: Team ID
        season_nullable: Season in 'YYYY-YY' format
        season_type_nullable: Season type (e.g., 'Regular Season')
        league_id_nullable: League ID
        date_from_nullable: Start date 'YYYY-MM-DD'
        date_to_nullable: End date 'YYYY-MM-DD'

    Returns:
        Path to the CSV file
    """
    # Create a string with the parameters
    params = []

    if player_or_team_abbreviation:
        params.append(f"pt_{player_or_team_abbreviation}")

    if player_id_nullable:
        params.append(f"pid_{player_id_nullable}")

    if team_id_nullable:
        params.append(f"tid_{team_id_nullable}")

    if season_nullable:
        params.append(f"season_{season_nullable}")

    if season_type_nullable:
        clean_season_type = season_type_nullable.replace(" ", "_").lower()
        params.append(f"type_{clean_season_type}")

    if league_id_nullable:
        params.append(f"lid_{league_id_nullable}")

    if date_from_nullable:
        params.append(f"from_{date_from_nullable}")

    if date_to_nullable:
        params.append(f"to_{date_to_nullable}")

    # Join parameters with underscores
    filename = "_".join(params) + ".csv"

    return get_cache_file_path(filename, "game_finder")

# --- Helper Functions ---
def _validate_game_finder_params(
    player_or_team_abbreviation: str,
    player_id_nullable: Optional[int],
    team_id_nullable: Optional[int],
    season_nullable: Optional[str],
    season_type_nullable: Optional[str],
    league_id_nullable: Optional[str],
    date_from_nullable: Optional[str],
    date_to_nullable: Optional[str]
) -> Optional[str]:
    """Validates parameters for fetch_league_games_logic."""
    if player_or_team_abbreviation not in VALID_PLAYER_TEAM_ABBREVIATIONS:
        return Errors.INVALID_PLAYER_OR_TEAM_ABBREVIATION.format(value=player_or_team_abbreviation)
    if player_or_team_abbreviation == 'P' and player_id_nullable is None:
        return Errors.PLAYER_ID_REQUIRED
    if date_from_nullable and date_to_nullable and not season_nullable and not player_id_nullable and not team_id_nullable:
        logger.warning("Attempted date-only query for leaguegamefinder, which is unsupported.")
        return Errors.DATE_ONLY_GAME_FINDER_UNSUPPORTED
    if season_nullable and not _validate_season_format(season_nullable, league_id=league_id_nullable):
        return Errors.INVALID_SEASON_FORMAT.format(season=season_nullable)
    if date_from_nullable and not validate_date_format(date_from_nullable):
        return Errors.INVALID_DATE_FORMAT.format(date=date_from_nullable)
    if date_to_nullable and not validate_date_format(date_to_nullable):
        return Errors.INVALID_DATE_FORMAT.format(date=date_to_nullable)
    if season_type_nullable is not None and season_type_nullable not in _VALID_GAME_FINDER_SEASON_TYPES and season_type_nullable != SeasonTypeAllStar.default:
        return Errors.INVALID_SEASON_TYPE.format(value=season_type_nullable, options=", ".join(list(_VALID_GAME_FINDER_SEASON_TYPES)[:5]))
    if league_id_nullable is not None and league_id_nullable not in _VALID_GAME_FINDER_LEAGUE_IDS:
        return Errors.INVALID_LEAGUE_ID.format(value=league_id_nullable, options=", ".join(list(_VALID_GAME_FINDER_LEAGUE_IDS)[:5]))
    return None

def _apply_date_filters_to_df(
    games_df: pd.DataFrame,
    date_from_nullable: Optional[str],
    date_to_nullable: Optional[str]
) -> pd.DataFrame:
    """Applies date filtering to the DataFrame after initial fetch."""
    if not date_from_nullable and not date_to_nullable:
        return games_df
    if games_df.empty:
        return games_df

    logger.info(f"Applying post-fetch date filtering: From {date_from_nullable}, To {date_to_nullable}")
    try:
        games_df['GAME_DATE_DT'] = pd.to_datetime(games_df['GAME_DATE']).dt.date
        if date_from_nullable:
            from_date = datetime.strptime(date_from_nullable, DATE_FORMAT_YYYY_MM_DD).date()
            games_df = games_df[games_df['GAME_DATE_DT'] >= from_date]
        if date_to_nullable:
            to_date = datetime.strptime(date_to_nullable, DATE_FORMAT_YYYY_MM_DD).date()
            games_df = games_df[games_df['GAME_DATE_DT'] <= to_date]
        games_df = games_df.drop(columns=['GAME_DATE_DT'])
    except Exception as e:
        logger.error(f"Error during post-fetch date filtering: {str(e)}", exc_info=True)
        # Decide if to raise, return empty, or return original. Returning original for now.
        # Consider raising a specific processing error to be caught by the main function.
        raise ValueError(f"Date filtering failed: {str(e)}")
    return games_df

def _limit_results_if_broad(
    games_df: pd.DataFrame,
    player_id_nullable: Optional[int],
    team_id_nullable: Optional[int],
    season_nullable: Optional[str],
    season_type_nullable: Optional[str], # Added for more precise broad query check
    original_date_from: Optional[str], # Use original dates for this check
    original_date_to: Optional[str]
) -> pd.DataFrame:
    """Limits the number of results for broad queries."""
    if games_df.empty:
        return games_df

    # A query is considered broad if it's not filtered by player, team, or season,
    # but might have date filters applied post-fetch.
    is_broad_query_by_params = all(param is None for param in [player_id_nullable, team_id_nullable, season_nullable])

    # A query is very general if no specific filters (player, team, season, type, or original dates) were applied.
    is_very_general_query = all(param is None for param in [
        player_id_nullable, team_id_nullable, season_nullable, season_type_nullable,
        original_date_from, original_date_to
    ])

    if is_broad_query_by_params and len(games_df) > MAX_GAME_FINDER_RESULTS:
        logger.info(f"Limiting broad league game list to the top {MAX_GAME_FINDER_RESULTS} games. Original count: {len(games_df)}")
        return games_df.head(MAX_GAME_FINDER_RESULTS)
    elif is_very_general_query and len(games_df) > MAX_GAME_FINDER_RESULTS:
        logger.info(f"Limiting very general league game list to the top {MAX_GAME_FINDER_RESULTS} games. Original count: {len(games_df)}")
        return games_df.head(MAX_GAME_FINDER_RESULTS)
    return games_df

def _format_game_dates(games_list: List[Dict[str, Any]]) -> None:
    """Formats GAME_DATE to YYYY-MM-DD in place."""
    for game_item in games_list:
        if 'GAME_DATE' in game_item and isinstance(game_item['GAME_DATE'], str):
            try:
                parsed_date = datetime.fromisoformat(game_item['GAME_DATE'].split('T')[0])
                game_item['GAME_DATE_FORMATTED'] = parsed_date.strftime(DATE_FORMAT_YYYY_MM_DD)
            except ValueError:
                game_item['GAME_DATE_FORMATTED'] = game_item['GAME_DATE'].split('T')[0] # Fallback

# --- Main Logic Function ---
def fetch_league_games_logic(
    player_or_team_abbreviation: str = 'T',
    player_id_nullable: Optional[int] = None,
    team_id_nullable: Optional[int] = None,
    season_nullable: Optional[str] = None,
    season_type_nullable: Optional[str] = None,
    league_id_nullable: Optional[str] = LeagueID.nba,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches NBA league games using LeagueGameFinder with common filters.
    Applies date filtering post-API call due to API instability with date ranges.
    Provides DataFrame output capabilities.

    Args:
        player_or_team_abbreviation: 'P' for player or 'T' for team. Defaults to 'T'.
        player_id_nullable: Player ID.
        team_id_nullable: Team ID.
        season_nullable: Season in 'YYYY-YY' format.
        season_type_nullable: Season type (e.g., 'Regular Season').
        league_id_nullable: League ID. Defaults to NBA.
        date_from_nullable: Start date 'YYYY-MM-DD'.
        date_to_nullable: End date 'YYYY-MM-DD'.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string of games list or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_league_games_logic with P/T: {player_or_team_abbreviation}, TeamID: {team_id_nullable}, PlayerID: {player_id_nullable}, Season: {season_nullable}, League: {league_id_nullable}, Dates: {date_from_nullable}-{date_to_nullable}, return_dataframe: {return_dataframe}")

    # Store DataFrames if requested
    dataframes = {}

    param_error = _validate_game_finder_params(
        player_or_team_abbreviation, player_id_nullable, team_id_nullable,
        season_nullable, season_type_nullable, league_id_nullable,
        date_from_nullable, date_to_nullable
    )
    if param_error:
        error_response = format_response(error=param_error)
        if return_dataframe:
            return error_response, dataframes
        return error_response

    try:
        # API call is made without date filters initially due to potential instability
        logger.debug(f"Calling LeagueGameFinder with P/T: {player_or_team_abbreviation}, PlayerID: {player_id_nullable}, TeamID: {team_id_nullable}, Season: {season_nullable}, SeasonType: {season_type_nullable}, League: {league_id_nullable}")
        game_finder_endpoint = leaguegamefinder.LeagueGameFinder(
            player_or_team_abbreviation=player_or_team_abbreviation,
            player_id_nullable=player_id_nullable,
            team_id_nullable=team_id_nullable,
            season_nullable=season_nullable,
            season_type_nullable=season_type_nullable,
            league_id_nullable=league_id_nullable,
            date_from_nullable=None, # Fetch all, then filter
            date_to_nullable=None,   # Fetch all, then filter
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        games_df = game_finder_endpoint.league_game_finder_results.get_data_frame()
        logger.debug("LeagueGameFinder API call successful.")

        if games_df.empty:
            logger.warning("No league games found from initial API call.")
            empty_response = format_response({"games": []})
            if return_dataframe:
                return empty_response, dataframes
            return empty_response

        # Apply date filtering post-fetch
        try:
            games_df = _apply_date_filters_to_df(games_df, date_from_nullable, date_to_nullable)
        except ValueError as filter_error: # Catch specific error from helper
             logger.error(f"Error during post-fetch date filtering: {filter_error}", exc_info=True)
             error_response = format_response(error=Errors.PROCESSING_ERROR.format(error=str(filter_error)))
             if return_dataframe:
                 return error_response, dataframes
             return error_response

        if games_df.empty:
            logger.warning("No league games found after post-fetch date filtering.")
            empty_response = format_response({"games": []})
            if return_dataframe:
                return empty_response, dataframes
            return empty_response

        # Limit results for broad queries
        games_df = _limit_results_if_broad(
            games_df, player_id_nullable, team_id_nullable, season_nullable,
            season_type_nullable, date_from_nullable, date_to_nullable
        )

        # Store DataFrame if requested
        if return_dataframe:
            dataframes["games"] = games_df

            # Save to CSV if not empty
            if not games_df.empty:
                csv_path = _get_csv_path_for_game_finder(
                    player_or_team_abbreviation=player_or_team_abbreviation,
                    player_id_nullable=player_id_nullable,
                    team_id_nullable=team_id_nullable,
                    season_nullable=season_nullable,
                    season_type_nullable=season_type_nullable,
                    league_id_nullable=league_id_nullable,
                    date_from_nullable=date_from_nullable,
                    date_to_nullable=date_to_nullable
                )
                _save_dataframe_to_csv(games_df, csv_path)

        games_list = _process_dataframe(games_df, single_row=False)
        if games_list is None:
            logger.error("Failed to process league games DataFrame after all filters.")
            error_response = format_response(error=Errors.PROCESSING_ERROR.format(error="league games data"))
            if return_dataframe:
                return error_response, dataframes
            return error_response

        _format_game_dates(games_list)

        result = {"games": games_list}

        # Add DataFrame info to the response if requested
        if return_dataframe:
            csv_path = _get_csv_path_for_game_finder(
                player_or_team_abbreviation=player_or_team_abbreviation,
                player_id_nullable=player_id_nullable,
                team_id_nullable=team_id_nullable,
                season_nullable=season_nullable,
                season_type_nullable=season_type_nullable,
                league_id_nullable=league_id_nullable,
                date_from_nullable=date_from_nullable,
                date_to_nullable=date_to_nullable
            )
            relative_path = get_relative_cache_path(
                os.path.basename(csv_path),
                "game_finder"
            )

            result["dataframe_info"] = {
                "message": "League games data has been converted to DataFrame and saved as CSV file",
                "dataframes": {
                    "games": {
                        "shape": list(games_df.shape) if not games_df.empty else [],
                        "columns": games_df.columns.tolist() if not games_df.empty else [],
                        "csv_path": relative_path
                    }
                }
            }

        logger.info(f"fetch_league_games_logic found {len(games_list)} games matching criteria.")

        json_response = format_response(result)
        if return_dataframe:
            return json_response, dataframes
        return json_response

    except Exception as e:
        if "Expecting value: line 1 column 1 (char 0)" in str(e): # Handle potential JSONDecodeError from API
            logger.error(f"JSONDecodeError from NBA API (LeagueGameFinder): {str(e)}", exc_info=True)
            error_msg = Errors.JSON_PROCESSING_ERROR
        else:
            logger.error(f"Error fetching league games: {str(e)}", exc_info=True)
            error_msg = Errors.LEAGUE_GAMES_API.format(error=str(e))

        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, dataframes
        return error_response
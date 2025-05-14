import logging
import json
import time
from typing import Optional, Union, List, Dict, Any, Callable, Tuple
import pandas as pd
import numpy as np # Added numpy import
from datetime import datetime, date # Ensure date and datetime are imported from datetime
from requests.exceptions import ReadTimeout, ConnectionError

from backend.core.errors import Errors
from nba_api.stats.static import players, teams
logger = logging.getLogger(__name__)

def retry_on_timeout(func: Callable[[], Any], max_retries: int = 3, initial_delay: float = 1.0, max_delay: float = 8.0) -> Any:
    """
    Retries a function call with exponential backoff if a `ReadTimeout` or `ConnectionError` occurs.
    """
    delay = initial_delay
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            return func()
        except (ReadTimeout, ConnectionError) as e:
            last_exception = e
            if attempt < max_retries - 1:
                logger.warning(f"Attempt {attempt + 1} of {max_retries} failed with {type(e).__name__}: {str(e)}. Retrying in {delay:.2f} seconds...")
                time.sleep(delay)
                delay = min(delay * 2, max_delay)
            else:
                logger.error(f"All {max_retries} attempts failed. Last error: {type(e).__name__}: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"Function call failed with non-retryable error: {type(e).__name__}: {str(e)}", exc_info=True)
            raise

    if last_exception:
        raise last_exception
    logger.error("retry_on_timeout completed all retries without returning or raising a final exception. This indicates an issue with the retried function.")
    return None


def format_response(data: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> str:
    """
    Formats the API response as a JSON string.
    """
    if error:
        return json.dumps({"error": error})
    elif data is not None:
        return json.dumps(data, default=str)
    else:
        return json.dumps({})

def _process_dataframe(df: Optional[pd.DataFrame], single_row: bool = True) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
    """
    Processes a pandas DataFrame into a dictionary or list of dictionaries.
    """
    if df is None or df.empty:
        return {} if single_row else []

    df_copy = df.copy() # Work on a copy to avoid modifying the original DataFrame

    # Step 1: Convert all pandas/numpy NaNs/NaTs to Python None
    try:
        df_copy = df_copy.where(pd.notnull(df_copy), None)
    except Exception as e:
        logger.warning(f"Utils: _process_dataframe - Error during df.where(pd.notnull(df), None): {e}. Proceeding with original df_copy.")
        # If .where fails, df_copy remains the original copy; pd.isna() will handle NaNs later.

    # The aggressive astype(str) was causing numbers to become strings permanently.
    # Rely on the .where() for null normalization and the loop below for type conversion.

    try:
        if single_row:
            if len(df_copy) > 0:
                row_dict = {}
                for col_name, value in df_copy.iloc[0].items():
                    try:
                        if pd.isna(value):
                            row_dict[col_name] = None
                        elif isinstance(value, np.integer):
                            row_dict[col_name] = int(value)
                        elif isinstance(value, np.floating):
                            row_dict[col_name] = float(value)
                        elif isinstance(value, np.bool_):
                            row_dict[col_name] = bool(value)
                        elif isinstance(value, (datetime, date, pd.Timestamp)):
                            row_dict[col_name] = value.isoformat()
                        elif isinstance(value, (int, float, bool, str)):
                            row_dict[col_name] = value
                        else:
                            logger.debug(f"Utils: _process_dataframe (single_row) - Fallback to str for col '{col_name}', type '{type(value)}', value: '{str(value)[:100]}'")
                            row_dict[col_name] = str(value)
                    except Exception as val_e:
                        logger.error(f"Utils: _process_dataframe (single_row) - Error converting value for col '{col_name}', type '{type(value)}', value: '{str(value)[:100]}'. Error: {val_e}", exc_info=True)
                        row_dict[col_name] = None
                return row_dict
            else:
                return {}
        else: # For single_row == False
            records = []
            for index, row_series in df_copy.iterrows(): # Iterate over the pre-processed df_copy
                record = {}
                for col_name, value in row_series.items():
                    try:
                        if pd.isna(value): # Handle NaN/NaT here
                            record[col_name] = None
                        elif isinstance(value, np.integer):
                            record[col_name] = int(value)
                        elif isinstance(value, np.floating):
                            record[col_name] = float(value)
                        elif isinstance(value, np.bool_):
                            record[col_name] = bool(value)
                        elif isinstance(value, (datetime, date, pd.Timestamp)):
                            record[col_name] = value.isoformat()
                        elif isinstance(value, (int, float, bool, str)):
                            record[col_name] = value
                        else:
                            logger.debug(f"Utils: _process_dataframe (multi_row) - Fallback to str for col '{col_name}', type '{type(value)}', value: '{str(value)[:100]}'")
                            record[col_name] = str(value)
                    except Exception as val_e:
                        logger.error(f"Utils: _process_dataframe (multi_row) - Error converting value for col '{col_name}', type '{type(value)}', value: '{str(value)[:100]}'. Error: {val_e}", exc_info=True)
                        record[col_name] = None
                records.append(record)
            return records
    except Exception as e:
        logger.error(f"Error processing DataFrame (outer logic): {str(e)}", exc_info=True)
        return None

# --- Custom Exceptions ---

class PlayerNotFoundError(Exception):
    """Custom exception raised when a player cannot be found by the lookup utilities."""
    def __init__(self, player_identifier: str):
        self.player_identifier = player_identifier
        message = Errors.PLAYER_NOT_FOUND.format(identifier=player_identifier) if hasattr(Errors, 'PLAYER_NOT_FOUND') else f"Player '{player_identifier}' not found."
        super().__init__(message)

class TeamNotFoundError(Exception):
    """Custom exception raised when a team cannot be found by the lookup utilities."""
    def __init__(self, team_identifier: str):
        self.team_identifier = team_identifier
        message = Errors.TEAM_NOT_FOUND.format(identifier=team_identifier) if hasattr(Errors, 'TEAM_NOT_FOUND') else f"Team '{team_identifier}' not found."
        super().__init__(message)

# --- Lookup Helpers ---

def get_player_id_from_name(player_name: str) -> Union[int, Dict[str, str]]:
    """
    Gets a player's ID from their name.

    Args:
        player_name (str): The name of the player to look up.

    Returns:
        Union[int, Dict[str, str]]: The player's ID if found, or an error dictionary if not found.
    """
    try:
        player_id, _ = find_player_id_or_error(player_name)
        return player_id
    except PlayerNotFoundError:
        return {"error": f"Player '{player_name}' not found."}
    except Exception as e:
        logger.error(f"Error in get_player_id_from_name for {player_name}: {str(e)}", exc_info=True)
        return {"error": f"Failed to get player ID for {player_name}: {str(e)}"}

def find_player_id_or_error(player_name: str) -> Tuple[int, str]:
    """
    Finds a player's unique ID and their canonical full name.
    """
    if not player_name or not player_name.strip():
        error_msg = Errors.PLAYER_NAME_EMPTY if hasattr(Errors, 'PLAYER_NAME_EMPTY') else "Player name cannot be empty."
        logger.error(error_msg)
        raise ValueError(error_msg)

    try:
        logger.debug(f"Searching for player ID for: '{player_name}'")

        # Attempt to treat as ID first if it's all digits
        if player_name.isdigit():
            player_id_int = int(player_name)
            all_players_list = players.get_players() # Get all players
            for p in all_players_list:
                if p['id'] == player_id_int:
                    logger.info(f"Found player by ID: {p['full_name']} (ID: {p['id']}) for input '{player_name}' (interpreted as ID)")
                    return p['id'], p['full_name']
            # If not found by ID, it might be a name that happens to be all digits, or an invalid ID.
            # Proceed to name lookup, or let PlayerNotFoundError be raised if it's truly not found by name either.

        player_list_results = players.find_players_by_full_name(player_name)
        if player_list_results:
            player_info_dict = player_list_results[0]
            player_id_found = int(player_info_dict['id'])
            player_actual_name_found = player_info_dict['full_name']
            logger.info(f"Found player by name: {player_actual_name_found} (ID: {player_id_found}) for input '{player_name}'")
            return player_id_found, player_actual_name_found
        else:
            logger.warning(f"Player not found for identifier: '{player_name}' using nba_api.stats.static.players (tried as ID if applicable, then as name)")
            raise PlayerNotFoundError(player_name)

    except PlayerNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error finding player ID for '{player_name}': {e}", exc_info=True)
        raise Exception(f"An unexpected error occurred while searching for player '{player_name}'.") from e

def find_team_id_or_error(team_identifier: str) -> Tuple[int, str]:
    """
    Finds a team's unique ID and its canonical full name.
    """
    if not team_identifier or not str(team_identifier).strip():
        error_msg = Errors.TEAM_IDENTIFIER_EMPTY if hasattr(Errors, 'TEAM_IDENTIFIER_EMPTY') else "Team identifier cannot be empty."
        logger.error(error_msg)
        raise ValueError(error_msg)

    identifier_str_cleaned = str(team_identifier).strip()
    logger.debug(f"Searching for team ID using identifier: '{identifier_str_cleaned}'")

    try:
        if identifier_str_cleaned.isdigit():
            team_id_int_input = int(identifier_str_cleaned)
            all_teams_list_static = teams.get_teams()
            for team_dict_static in all_teams_list_static:
                if team_dict_static['id'] == team_id_int_input:
                    logger.info(f"Found team by ID: {team_dict_static['full_name']} (ID: {team_dict_static['id']})")
                    return team_dict_static['id'], team_dict_static['full_name']

        team_info_by_abbr_static = teams.find_team_by_abbreviation(identifier_str_cleaned.upper())
        if team_info_by_abbr_static:
            logger.info(f"Found team by abbreviation: {team_info_by_abbr_static['full_name']} (ID: {team_info_by_abbr_static['id']})")
            return team_info_by_abbr_static['id'], team_info_by_abbr_static['full_name']

        team_list_by_name_static = teams.find_teams_by_full_name(identifier_str_cleaned)
        if team_list_by_name_static:
            team_info_first_match = team_list_by_name_static[0]
            logger.info(f"Found team by full name: {team_info_first_match['full_name']} (ID: {team_info_first_match['id']})")
            return team_info_first_match['id'], team_info_first_match['full_name']

        all_teams_for_nickname_search = teams.get_teams()
        identifier_lower_case = identifier_str_cleaned.lower()
        for team_item in all_teams_for_nickname_search:
            if team_item['nickname'].lower() == identifier_lower_case:
                logger.info(f"Found team by nickname: {team_item['full_name']} (ID: {team_item['id']})")
                return team_item['id'], team_item['full_name']

        logger.warning(f"Team not found for identifier: '{identifier_str_cleaned}'")
        raise TeamNotFoundError(identifier_str_cleaned)

    except TeamNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error finding team ID for '{identifier_str_cleaned}': {e}", exc_info=True)
        raise Exception(f"An unexpected error occurred while searching for team '{identifier_str_cleaned}'.") from e
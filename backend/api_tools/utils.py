# nba-analytics-backend/api_tools/utils.py
import logging
import json
import re
import time
from typing import Optional, Union, List, Dict, Any, Callable
import pandas as pd
from requests.exceptions import ReadTimeout, ConnectionError
from backend.config import DEFAULT_TIMEOUT  # Fixed import path
import datetime

logger = logging.getLogger(__name__)

def retry_on_timeout(func: Callable, max_retries: int = 3, initial_delay: float = 1.0, max_delay: float = 8.0) -> Any:
    """
    Retry a function call with exponential backoff when a timeout occurs.
    
    Args:
        func: The function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
    
    Returns:
        The result of the function call if successful
    
    Raises:
        The last exception encountered if all retries fail
    """
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return func()
        except (ReadTimeout, ConnectionError) as e:
            last_exception = e
            if attempt < max_retries - 1:
                logger.warning(f"Attempt {attempt + 1} failed with {str(e)}. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay = min(delay * 2, max_delay)  # Exponential backoff
            else:
                logger.error(f"All {max_retries} attempts failed. Last error: {str(e)}")
                raise
    
    if last_exception:
        raise last_exception
    return None

def _validate_season_format(season: str) -> bool:
    """
    Validate that the season string is in the correct format (YYYY-YY).
    """
    if not season or not isinstance(season, str):
        return False
    
    try:
        start_year = int(season.split('-')[0])
        end_year = int(season.split('-')[1])
        
        if len(season.split('-')[1]) != 2:
            return False
            
        if start_year < 1946:  # NBA started in 1946
            return False
            
        if end_year != (start_year + 1) % 100:
            return False
            
        return True
    except (ValueError, IndexError):
        return False

def validate_season_format(season: str) -> bool:
    """
    Public interface to validate that the season string is in the correct format (YYYY-YY).
    """
    return _validate_season_format(season)

def validate_game_id_format(game_id: str) -> bool:
    """
    Validate that a game ID is in the correct format (10 digits).
    """
    if not game_id:
        return False
    
    pattern = r'^\d{10}$'
    return bool(re.match(pattern, game_id))

def validate_date_format(date_string: str) -> bool:
    """
    Validate that a date string is in the correct format (YYYY-MM-DD).
    """
    if not date_string or not isinstance(date_string, str):
        return False
    try:
        datetime.datetime.strptime(date_string, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def format_response(data: Optional[Dict] = None, error: Optional[str] = None) -> str:
    """
    Format API response as JSON string.
    """
    if error:
        return json.dumps({"error": error})
    elif data is not None:
        return json.dumps(data)
    else:
        return json.dumps({})

def handle_api_error(error_type: str, message: Optional[str] = None, details: Optional[Dict] = None) -> str:
    """
    Handle API errors and return formatted error response.
    """
    error_messages = {
        "InvalidGameId": "Invalid game ID format",
        "InvalidSeason": "Invalid season format",
        "InvalidPlayer": "Player not found",
        "InvalidTeam": "Team not found",
        "Timeout": "Request timed out",
        "Unknown": "An unexpected error occurred",
        "EmptyGameId": "Game ID cannot be empty",
        "MissingTeamId": "Team ID is missing in the response data",
        "NoDataFound": "No data found for the specified game",
        "APIError": "Error fetching data from NBA API"
    }
    
    error_msg = message or error_messages.get(error_type, error_messages["Unknown"])
    response = {"error": error_msg}
    
    if details:
        response.update(details)
    
    return json.dumps(response)

def _process_dataframe(df: pd.DataFrame, single_row: bool = True) -> Union[Dict, List[Dict], None]:
    """
    Process a pandas DataFrame into a dictionary or list of dictionaries.
    """
    if df is None or df.empty:
        return None
        
    try:
        if single_row:
            return df.iloc[0].to_dict()
        else:
            return df.to_dict('records')
    except Exception as e:
        logger.error(f"Error processing DataFrame: {str(e)}", exc_info=True)
        return None
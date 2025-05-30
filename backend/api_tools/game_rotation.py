"""
Handles fetching and processing game rotation data
from the GameRotation endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The GameRotation endpoint provides comprehensive game rotation data (12 columns):
- Game info: GAME_ID (1 column)
- Team info: TEAM_ID, TEAM_CITY, TEAM_NAME (3 columns)
- Player info: PERSON_ID, PLAYER_FIRST, PLAYER_LAST (3 columns)
- Rotation data: IN_TIME_REAL, OUT_TIME_REAL (2 columns)
- Performance: PLAYER_PTS, PT_DIFF, USG_PCT (3 columns)
- Game-specific data: Each game has detailed rotation information (33-44 records per game)
- Perfect for rotation analysis, performance impact, and coaching insights
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import gamerotation
import pandas as pd

from ..utils.path_utils import get_cache_dir, get_cache_file_path

# Define utility functions here since we can't import from .utils
def _process_dataframe(df, single_row=False):
    """Process a DataFrame into a list of dictionaries."""
    if df is None or df.empty:
        return []

    if single_row:
        return df.iloc[0].to_dict()

    return df.to_dict(orient="records")

def format_response(data=None, error=None):
    """Format a response as JSON."""
    if error:
        return json.dumps({"error": error})
    return json.dumps(data)

def _validate_game_id(game_id):
    """Validate game ID format."""
    if not game_id:
        return False
    
    try:
        # Check if it's a valid game ID (should be a 10-digit number)
        if len(game_id) == 10 and game_id.isdigit():
            return True
        return False
    except (ValueError, AttributeError):
        return False

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
GAME_ROTATION_CACHE_SIZE = 128

# Valid parameter sets
VALID_LEAGUE_IDS: Set[str] = {"00", "10"}  # NBA, WNBA

# --- Cache Directory Setup ---
GAME_ROTATION_CSV_DIR = get_cache_dir("game_rotation")

# Ensure cache directories exist
os.makedirs(GAME_ROTATION_CSV_DIR, exist_ok=True)

# --- Helper Functions for CSV Caching ---
def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves a DataFrame to a CSV file.
    
    Args:
        df: DataFrame to save
        file_path: Path to save the CSV file
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save DataFrame to CSV with UTF-8 encoding
        df.to_csv(file_path, index=False, encoding='utf-8')
        
        # Log the file size and path
        file_size = os.path.getsize(file_path)
        logger.info(f"Saved DataFrame to CSV: {file_path} (Size: {file_size} bytes)")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)

def _get_csv_path_for_game_rotation(
    game_id: str,
    league_id: str = "00",
    data_set_name: str = "GameRotation"
) -> str:
    """
    Generates a file path for saving game rotation DataFrame.
    
    Args:
        game_id: Game ID
        league_id: League ID (default: "00" for NBA)
        data_set_name: Name of the data set
        
    Returns:
        Path to the CSV file
    """
    filename = f"game_rotation_game{game_id}_league{league_id}_{data_set_name}.csv"
    return get_cache_file_path(filename, "game_rotation")

# --- Parameter Validation ---
def _validate_game_rotation_params(
    game_id: str,
    league_id: str
) -> Optional[str]:
    """Validates parameters for fetch_game_rotation_logic."""
    if not game_id:
        return "game_id is required"
    if not _validate_game_id(game_id):
        return f"Invalid game_id format: {game_id}. Expected 10-digit game ID"
    if league_id not in VALID_LEAGUE_IDS:
        return f"Invalid league_id: {league_id}. Valid options: {', '.join(VALID_LEAGUE_IDS)}"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=GAME_ROTATION_CACHE_SIZE)
def fetch_game_rotation_logic(
    game_id: str,
    league_id: str = "00",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches game rotation data using the GameRotation endpoint.
    
    Provides DataFrame output capabilities and CSV caching.
    
    Args:
        game_id: Game ID (required)
        league_id: League ID (default: "00" for NBA)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with game rotation data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(
        f"Executing fetch_game_rotation_logic for Game: {game_id}, League: {league_id}, "
        f"return_dataframe={return_dataframe}"
    )
    
    # Validate parameters
    validation_error = _validate_game_rotation_params(game_id, league_id)
    if validation_error:
        logger.warning(f"Parameter validation failed for game rotation: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response
    
    # Check for cached CSV files
    dataframes = {}
    
    # Try to load from cache first
    if return_dataframe:
        # Check for both possible data sets
        data_set_names = ["GameRotation", "AvailableRotation"]
        all_cached = True
        
        for data_set_name in data_set_names:
            csv_path = _get_csv_path_for_game_rotation(game_id, league_id, data_set_name)
            if os.path.exists(csv_path):
                try:
                    # Check if the file is empty or too small
                    file_size = os.path.getsize(csv_path)
                    if file_size < 100:  # If file is too small, it's probably empty or corrupted
                        logger.warning(f"CSV file is too small ({file_size} bytes), fetching from API instead")
                        all_cached = False
                        break
                    else:
                        logger.info(f"Loading game rotation from CSV: {csv_path}")
                        # Read CSV with appropriate data types
                        df = pd.read_csv(csv_path, encoding='utf-8')
                        dataframes[data_set_name] = df
                except Exception as e:
                    logger.error(f"Error loading CSV: {e}", exc_info=True)
                    all_cached = False
                    break
            else:
                all_cached = False
                break
        
        # If all data sets are cached, return cached data
        if all_cached and dataframes:
            # Process for JSON response
            result_dict = {
                "parameters": {
                    "game_id": game_id,
                    "league_id": league_id
                },
                "data_sets": {}
            }
            
            for data_set_name, df in dataframes.items():
                result_dict["data_sets"][data_set_name] = _process_dataframe(df, single_row=False)
            
            return format_response(result_dict), dataframes
    
    try:
        # Prepare API parameters
        api_params = {
            "game_id": game_id,
            "league_id": league_id
        }
        
        logger.debug(f"Calling GameRotation with parameters: {api_params}")
        game_rotation_endpoint = gamerotation.GameRotation(**api_params)
        
        # Get data frames
        list_of_dataframes = game_rotation_endpoint.get_data_frames()
        
        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": api_params,
            "data_sets": {}
        }
        
        # Process each data frame
        data_set_names = ["GameRotation", "AvailableRotation"]
        
        for idx, df in enumerate(list_of_dataframes):
            if not df.empty:
                # Use predefined names for the data sets
                data_set_name = data_set_names[idx] if idx < len(data_set_names) else f"GameRotation_{idx}"
                
                # Store DataFrame if requested
                if return_dataframe:
                    dataframes[data_set_name] = df
                    
                    # Save DataFrame to CSV
                    csv_path = _get_csv_path_for_game_rotation(game_id, league_id, data_set_name)
                    _save_dataframe_to_csv(df, csv_path)
                
                # Process for JSON response
                processed_data = _process_dataframe(df, single_row=False)
                result_dict["data_sets"][data_set_name] = processed_data
        
        final_json_response = format_response(result_dict)
        if return_dataframe:
            return final_json_response, dataframes
        return final_json_response
        
    except Exception as e:
        logger.error(f"Unexpected error in fetch_game_rotation_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_game_rotation(
    game_id: str,
    league_id: str = "00",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get game rotation data.
    
    Args:
        game_id: Game ID (required)
        league_id: League ID (default: "00" for NBA)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with game rotation data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_game_rotation_logic(
        game_id=game_id,
        league_id=league_id,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Test basic functionality
    print("Testing GameRotation endpoint...")
    
    # Test 1: Basic fetch
    json_response = get_game_rotation("0022400001")
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")
    
    # Test 2: With DataFrame output
    json_response, dataframes = get_game_rotation("0022400001", return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")
    
    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")
    
    print("GameRotation endpoint test completed.")

"""
Handles fetching and processing FanDuel player infographic data
from the InfographicFanDuelPlayer endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The InfographicFanDuelPlayer endpoint provides comprehensive FanDuel fantasy data (1 DataFrame):
- Player Info: PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM_NAME, TEAM_ABBREVIATION, JERSEY_NUM, PLAYER_POSITION, LOCATION (8 columns)
- Fantasy Scoring: FAN_DUEL_PTS, NBA_FANTASY_PTS, USG_PCT (3 columns)
- Traditional Stats: Complete box score with 22 statistical categories
- Rich fantasy data: 19-26 players per game with detailed fantasy statistics (33 columns total)
- Perfect for fantasy analysis, DFS optimization, and player evaluation
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import infographicfanduelplayer
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
INFOGRAPHIC_FANDUEL_CACHE_SIZE = 128

# --- Cache Directory Setup ---
INFOGRAPHIC_FANDUEL_CSV_DIR = get_cache_dir("infographic_fanduel")

# Ensure cache directories exist
os.makedirs(INFOGRAPHIC_FANDUEL_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_infographic_fanduel(
    game_id: str,
    data_set_name: str = "FanDuelPlayers"
) -> str:
    """
    Generates a file path for saving infographic FanDuel DataFrame.
    
    Args:
        game_id: Game ID
        data_set_name: Name of the data set
        
    Returns:
        Path to the CSV file
    """
    filename = f"infographic_fanduel_game{game_id}_{data_set_name}.csv"
    return get_cache_file_path(filename, "infographic_fanduel")

# --- Parameter Validation ---
def _validate_infographic_fanduel_params(game_id: str) -> Optional[str]:
    """Validates parameters for fetch_infographic_fanduel_logic."""
    if not game_id:
        return "game_id is required"
    if not _validate_game_id(game_id):
        return f"Invalid game_id format: {game_id}. Expected 10-digit game ID"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=INFOGRAPHIC_FANDUEL_CACHE_SIZE)
def fetch_infographic_fanduel_logic(
    game_id: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches FanDuel player infographic data using the InfographicFanDuelPlayer endpoint.
    
    Provides DataFrame output capabilities and CSV caching.
    
    Args:
        game_id: Game ID (required)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with FanDuel player data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(
        f"Executing fetch_infographic_fanduel_logic for Game: {game_id}, "
        f"return_dataframe={return_dataframe}"
    )
    
    # Validate parameters
    validation_error = _validate_infographic_fanduel_params(game_id)
    if validation_error:
        logger.warning(f"Parameter validation failed for infographic FanDuel: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response
    
    # Check for cached CSV file
    csv_path = _get_csv_path_for_infographic_fanduel(game_id, "FanDuelPlayers")
    dataframes = {}
    
    if os.path.exists(csv_path) and return_dataframe:
        try:
            # Check if the file is empty or too small
            file_size = os.path.getsize(csv_path)
            if file_size < 100:  # If file is too small, it's probably empty or corrupted
                logger.warning(f"CSV file is too small ({file_size} bytes), fetching from API instead")
                # Delete the corrupted file
                try:
                    os.remove(csv_path)
                    logger.info(f"Deleted corrupted CSV file: {csv_path}")
                except Exception as e:
                    logger.error(f"Error deleting corrupted CSV file: {e}", exc_info=True)
                # Continue to API fetch
            else:
                logger.info(f"Loading infographic FanDuel from CSV: {csv_path}")
                # Read CSV with appropriate data types
                df = pd.read_csv(csv_path, encoding='utf-8')
                
                # Process for JSON response
                result_dict = {
                    "parameters": {
                        "game_id": game_id
                    },
                    "data_sets": {}
                }
                
                # Store the DataFrame
                dataframes["FanDuelPlayers"] = df
                result_dict["data_sets"]["FanDuelPlayers"] = _process_dataframe(df, single_row=False)
                
                if return_dataframe:
                    return format_response(result_dict), dataframes
                return format_response(result_dict)
            
        except Exception as e:
            logger.error(f"Error loading CSV: {e}", exc_info=True)
            # If there's an error loading the CSV, fetch from the API
    
    try:
        # Prepare API parameters
        api_params = {
            "game_id": game_id
        }
        
        logger.debug(f"Calling InfographicFanDuelPlayer with parameters: {api_params}")
        infographic_endpoint = infographicfanduelplayer.InfographicFanDuelPlayer(**api_params)
        
        # Get data frames
        list_of_dataframes = infographic_endpoint.get_data_frames()
        
        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": api_params,
            "data_sets": {}
        }
        
        # Create a combined DataFrame for CSV storage
        combined_df = pd.DataFrame()
        
        # Process each data frame
        for idx, df in enumerate(list_of_dataframes):
            # Use a generic name for the data set
            data_set_name = f"FanDuelPlayers_{idx}" if idx > 0 else "FanDuelPlayers"
            
            # Store DataFrame if requested (even if empty for caching purposes)
            if return_dataframe:
                dataframes[data_set_name] = df
                
                # Use the first (main) DataFrame for CSV storage
                if idx == 0:
                    combined_df = df.copy()
            
            # Process for JSON response
            processed_data = _process_dataframe(df, single_row=False)
            result_dict["data_sets"][data_set_name] = processed_data
        
        # Save combined DataFrame to CSV (even if empty for caching purposes)
        if return_dataframe:
            _save_dataframe_to_csv(combined_df, csv_path)
        
        final_json_response = format_response(result_dict)
        if return_dataframe:
            return final_json_response, dataframes
        return final_json_response
        
    except Exception as e:
        logger.error(f"Unexpected error in fetch_infographic_fanduel_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_infographic_fanduel_player(
    game_id: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get FanDuel player infographic data.
    
    Args:
        game_id: Game ID (required)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with FanDuel player data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_infographic_fanduel_logic(
        game_id=game_id,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Test basic functionality
    print("Testing InfographicFanDuelPlayer endpoint...")
    
    # Test 1: Basic fetch
    json_response = get_infographic_fanduel_player("0022400001")
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")
    
    # Test 2: With DataFrame output
    json_response, dataframes = get_infographic_fanduel_player("0022400001", return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")
    
    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")
    
    print("InfographicFanDuelPlayer endpoint test completed.")

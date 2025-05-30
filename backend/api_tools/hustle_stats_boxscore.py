"""
Handles fetching and processing hustle stats box score data
from the HustleStatsBoxScore endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The HustleStatsBoxScore endpoint provides comprehensive hustle stats data (3 DataFrames):
- Game Status: Game ID and hustle status (2 columns)
- Player Stats: Individual player hustle statistics (19-22 players, 25 columns)
- Team Stats: Team totals for all hustle metrics (2 teams, 22 columns)
- Rich hustle metrics: Contested shots, deflections, charges drawn, screen assists, loose balls recovered, box outs
- Perfect for advanced analytics, player evaluation, and performance tracking
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import hustlestatsboxscore
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
HUSTLE_STATS_CACHE_SIZE = 128

# --- Cache Directory Setup ---
HUSTLE_STATS_CSV_DIR = get_cache_dir("hustle_stats")

# Ensure cache directories exist
os.makedirs(HUSTLE_STATS_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_hustle_stats(
    game_id: str,
    data_set_name: str = "HustleStats"
) -> str:
    """
    Generates a file path for saving hustle stats DataFrame.
    
    Args:
        game_id: Game ID
        data_set_name: Name of the data set
        
    Returns:
        Path to the CSV file
    """
    filename = f"hustle_stats_game{game_id}_{data_set_name}.csv"
    return get_cache_file_path(filename, "hustle_stats")

# --- Parameter Validation ---
def _validate_hustle_stats_params(game_id: str) -> Optional[str]:
    """Validates parameters for fetch_hustle_stats_logic."""
    if not game_id:
        return "game_id is required"
    if not _validate_game_id(game_id):
        return f"Invalid game_id format: {game_id}. Expected 10-digit game ID"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=HUSTLE_STATS_CACHE_SIZE)
def fetch_hustle_stats_logic(
    game_id: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches hustle stats box score data using the HustleStatsBoxScore endpoint.
    
    Provides DataFrame output capabilities and CSV caching.
    
    Args:
        game_id: Game ID (required)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with hustle stats data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(
        f"Executing fetch_hustle_stats_logic for Game: {game_id}, "
        f"return_dataframe={return_dataframe}"
    )
    
    # Validate parameters
    validation_error = _validate_hustle_stats_params(game_id)
    if validation_error:
        logger.warning(f"Parameter validation failed for hustle stats: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response
    
    # Check for cached CSV files
    dataframes = {}
    
    # Try to load from cache first
    if return_dataframe:
        # Check for all possible data sets
        data_set_names = ["GameStatus", "PlayerStats", "TeamStats"]
        all_cached = True
        
        for data_set_name in data_set_names:
            csv_path = _get_csv_path_for_hustle_stats(game_id, data_set_name)
            if os.path.exists(csv_path):
                try:
                    # Check if the file is empty or too small
                    file_size = os.path.getsize(csv_path)
                    if file_size < 50:  # If file is too small, it's probably empty or corrupted
                        logger.warning(f"CSV file is too small ({file_size} bytes), fetching from API instead")
                        all_cached = False
                        break
                    else:
                        logger.info(f"Loading hustle stats from CSV: {csv_path}")
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
                    "game_id": game_id
                },
                "data_sets": {}
            }
            
            for data_set_name, df in dataframes.items():
                result_dict["data_sets"][data_set_name] = _process_dataframe(df, single_row=False)
            
            return format_response(result_dict), dataframes
    
    try:
        # Prepare API parameters
        api_params = {
            "game_id": game_id
        }
        
        logger.debug(f"Calling HustleStatsBoxScore with parameters: {api_params}")
        hustle_stats_endpoint = hustlestatsboxscore.HustleStatsBoxScore(**api_params)
        
        # Get data frames
        list_of_dataframes = hustle_stats_endpoint.get_data_frames()
        
        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": api_params,
            "data_sets": {}
        }
        
        # Process each data frame
        data_set_names = ["GameStatus", "PlayerStats", "TeamStats"]
        
        for idx, df in enumerate(list_of_dataframes):
            if not df.empty:
                # Use predefined names for the data sets
                data_set_name = data_set_names[idx] if idx < len(data_set_names) else f"HustleStats_{idx}"
                
                # Store DataFrame if requested
                if return_dataframe:
                    dataframes[data_set_name] = df
                    
                    # Save DataFrame to CSV
                    csv_path = _get_csv_path_for_hustle_stats(game_id, data_set_name)
                    _save_dataframe_to_csv(df, csv_path)
                
                # Process for JSON response
                processed_data = _process_dataframe(df, single_row=False)
                result_dict["data_sets"][data_set_name] = processed_data
        
        final_json_response = format_response(result_dict)
        if return_dataframe:
            return final_json_response, dataframes
        return final_json_response
        
    except Exception as e:
        logger.error(f"Unexpected error in fetch_hustle_stats_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_hustle_stats_boxscore(
    game_id: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get hustle stats box score data.
    
    Args:
        game_id: Game ID (required)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with hustle stats data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_hustle_stats_logic(
        game_id=game_id,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Test basic functionality
    print("Testing HustleStatsBoxScore endpoint...")
    
    # Test 1: Basic fetch
    json_response = get_hustle_stats_boxscore("0022400001")
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")
    
    # Test 2: With DataFrame output
    json_response, dataframes = get_hustle_stats_boxscore("0022400001", return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")
    
    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")
    
    print("HustleStatsBoxScore endpoint test completed.")

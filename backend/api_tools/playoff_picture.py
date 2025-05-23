"""
Handles fetching and processing playoff picture data
from the PlayoffPicture endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The PlayoffPicture endpoint provides comprehensive playoff picture data (6 DataFrames):
- Series Data (East/West): CONFERENCE, HIGH_SEED_RANK, HIGH_SEED_TEAM, LOW_SEED_RANK, LOW_SEED_TEAM, SERIES_W, SERIES_L, REMAINING_G (12 columns)
- Standings Data (East/West): CONFERENCE, RANK, TEAM, WINS, LOSSES, PCT, DIV, CONF, HOME, AWAY, GB, CLINCHED_PLAYOFFS, CLINCHED_CONFERENCE, CLINCHED_DIVISION, ELIMINATED_PLAYOFFS (25 columns)
- Remaining Games (East/West): TEAM, TEAM_ID, REMAINING_G, REMAINING_HOME_G, REMAINING_AWAY_G (5 columns)
- Rich playoff data: Complete playoff standings, series results, and remaining games (5-25 columns total)
- Perfect for playoff analysis, standings tracking, and postseason evaluation
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import playoffpicture
import pandas as pd

from utils.path_utils import get_cache_dir, get_cache_file_path

# Define utility functions here since we can't import from .utils
def _process_dataframe(df, single_row=False):
    """Process a DataFrame into a list of dictionaries."""
    if df is None or df.empty:
        return []

    # Handle multi-level columns by flattening them
    if hasattr(df.columns, 'nlevels') and df.columns.nlevels > 1:
        # Flatten multi-level columns
        df = df.copy()
        df.columns = ['_'.join(str(col).strip() for col in cols if str(col).strip()) for cols in df.columns.values]
    
    # Convert any remaining tuple columns to strings
    if any(isinstance(col, tuple) for col in df.columns):
        df = df.copy()
        df.columns = [str(col) if isinstance(col, tuple) else col for col in df.columns]

    if single_row:
        return df.iloc[0].to_dict()

    return df.to_dict(orient="records")

def format_response(data=None, error=None):
    """Format a response as JSON."""
    if error:
        return json.dumps({"error": error})
    return json.dumps(data)

def _validate_season_format(season_id):
    """Validate season ID format."""
    if not season_id:
        return True  # Empty season is allowed (uses default)
    
    # Check if it's a valid season ID format (e.g., "22024" for 2024-25 season)
    if isinstance(season_id, (str, int)):
        try:
            season_int = int(season_id)
            # Season IDs are typically 5 digits starting with 2
            return 20000 <= season_int <= 99999
        except ValueError:
            return False
    
    return False

# Default current NBA season
CURRENT_NBA_SEASON_ID = "22024"  # 2024-25 season

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
PLAYOFF_PICTURE_CACHE_SIZE = 64

# Valid parameter sets
VALID_LEAGUE_IDS: Set[str] = {"00", "10"}  # NBA, WNBA

# --- Cache Directory Setup ---
PLAYOFF_PICTURE_CSV_DIR = get_cache_dir("playoff_picture")

# Ensure cache directories exist
os.makedirs(PLAYOFF_PICTURE_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_playoff_picture(
    league_id: str = "00",
    season_id: str = CURRENT_NBA_SEASON_ID,
    data_set_name: str = "PlayoffPicture"
) -> str:
    """
    Generates a file path for saving playoff picture DataFrame.
    
    Args:
        league_id: League ID (default: "00" for NBA)
        season_id: Season ID (default: current season)
        data_set_name: Name of the data set
        
    Returns:
        Path to the CSV file
    """
    # Create a filename based on the parameters
    filename_parts = [
        f"playoff_picture",
        f"league{league_id}",
        f"season{season_id}",
        data_set_name
    ]
    
    filename = "_".join(filename_parts) + ".csv"
    
    return get_cache_file_path(filename, "playoff_picture")

# --- Parameter Validation ---
def _validate_playoff_picture_params(
    league_id: str,
    season_id: str
) -> Optional[str]:
    """Validates parameters for fetch_playoff_picture_logic."""
    if league_id not in VALID_LEAGUE_IDS:
        return f"Invalid league_id: {league_id}. Valid options: {', '.join(VALID_LEAGUE_IDS)}"
    if not _validate_season_format(season_id):
        return f"Invalid season_id format: {season_id}. Expected format: 5-digit season ID (e.g., 22024)"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=PLAYOFF_PICTURE_CACHE_SIZE)
def fetch_playoff_picture_logic(
    league_id: str = "00",
    season_id: str = CURRENT_NBA_SEASON_ID,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches playoff picture data using the PlayoffPicture endpoint.
    
    Provides DataFrame output capabilities and CSV caching.
    
    Args:
        league_id: League ID (default: "00" for NBA)
        season_id: Season ID (default: current season)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with playoff picture data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(
        f"Executing fetch_playoff_picture_logic for League: {league_id}, Season: {season_id}, "
        f"return_dataframe={return_dataframe}"
    )
    
    # Validate parameters
    validation_error = _validate_playoff_picture_params(league_id, season_id)
    if validation_error:
        logger.warning(f"Parameter validation failed for playoff picture: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response
    
    # Check for cached CSV files
    dataframes = {}
    
    # Try to load from cache first
    if return_dataframe:
        # Check for all possible data sets
        data_set_names = ["EastSeries", "WestSeries", "EastStandings", "WestStandings", "EastRemainingGames", "WestRemainingGames"]
        all_cached = True
        
        for data_set_name in data_set_names:
            csv_path = _get_csv_path_for_playoff_picture(league_id, season_id, data_set_name)
            if os.path.exists(csv_path):
                try:
                    # Check if the file is empty or too small
                    file_size = os.path.getsize(csv_path)
                    if file_size < 50:  # If file is too small, it's probably empty or corrupted
                        logger.warning(f"CSV file is too small ({file_size} bytes), fetching from API instead")
                        all_cached = False
                        break
                    else:
                        logger.info(f"Loading playoff picture from CSV: {csv_path}")
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
                    "league_id": league_id,
                    "season_id": season_id
                },
                "data_sets": {}
            }
            
            for data_set_name, df in dataframes.items():
                result_dict["data_sets"][data_set_name] = _process_dataframe(df, single_row=False)
            
            return format_response(result_dict), dataframes
    
    try:
        # Prepare API parameters
        api_params = {
            "league_id": league_id,
            "season_id": season_id
        }
        
        logger.debug(f"Calling PlayoffPicture with parameters: {api_params}")
        playoff_picture_endpoint = playoffpicture.PlayoffPicture(**api_params)
        
        # Get data frames
        list_of_dataframes = playoff_picture_endpoint.get_data_frames()
        
        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": {
                "league_id": league_id,
                "season_id": season_id
            },
            "data_sets": {}
        }
        
        # Process each data frame
        data_set_names = ["EastSeries", "WestSeries", "EastStandings", "WestStandings", "EastRemainingGames", "WestRemainingGames"]
        
        for idx, df in enumerate(list_of_dataframes):
            # Use predefined names for the data sets
            data_set_name = data_set_names[idx] if idx < len(data_set_names) else f"PlayoffPicture_{idx}"
            
            # Store DataFrame if requested (even if empty for caching purposes)
            if return_dataframe:
                dataframes[data_set_name] = df
                
                # Save DataFrame to CSV
                csv_path = _get_csv_path_for_playoff_picture(league_id, season_id, data_set_name)
                _save_dataframe_to_csv(df, csv_path)
            
            # Process for JSON response
            processed_data = _process_dataframe(df, single_row=False)
            result_dict["data_sets"][data_set_name] = processed_data
        
        final_json_response = format_response(result_dict)
        if return_dataframe:
            return final_json_response, dataframes
        return final_json_response
        
    except Exception as e:
        logger.error(f"Unexpected error in fetch_playoff_picture_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_playoff_picture(
    league_id: str = "00",
    season_id: str = CURRENT_NBA_SEASON_ID,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get playoff picture data.
    
    Args:
        league_id: League ID (default: "00" for NBA)
        season_id: Season ID (default: current season)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with playoff picture data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_playoff_picture_logic(
        league_id=league_id,
        season_id=season_id,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Test basic functionality
    print("Testing PlayoffPicture endpoint...")
    
    # Test 1: Basic fetch
    json_response = get_playoff_picture()
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")
    
    # Test 2: With DataFrame output
    json_response, dataframes = get_playoff_picture(return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")
    
    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")
    
    print("PlayoffPicture endpoint test completed.")

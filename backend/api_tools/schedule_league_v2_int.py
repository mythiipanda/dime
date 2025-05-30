"""
Handles fetching and processing schedule league v2 int data
from the ScheduleLeagueV2Int endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The ScheduleLeagueV2Int endpoint provides comprehensive league schedule data (3 DataFrames):
- Games Data: Complete game schedule with detailed information (1,403 games, 808 columns)
- Weeks Data: Season weeks with start/end dates (36 weeks, 6 columns)
- Broadcasters Data: Broadcaster information by league and season (128 broadcasters, 7 columns)
- Rich schedule data: Complete league schedule with games, weeks, and broadcaster information
- Perfect for schedule analysis, game tracking, and broadcast planning
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import scheduleleaguev2int
import pandas as pd

from ..utils.path_utils import get_cache_dir, get_cache_file_path

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

def _validate_season_format(season):
    """Validate season format (YYYY-YY)."""
    if not season:
        return True  # Empty season is allowed (uses default)
    
    # Check if it matches YYYY-YY format
    if len(season) == 7 and season[4] == '-':
        try:
            year1 = int(season[:4])
            year2 = int(season[5:])
            # Check if the second year is the next year
            return year2 == (year1 + 1) % 100
        except ValueError:
            return False
    
    return False

# Default current NBA season
CURRENT_NBA_SEASON = "2024-25"

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
SCHEDULE_LEAGUE_V2_INT_CACHE_SIZE = 64

# Valid parameter sets
VALID_LEAGUE_IDS: Set[str] = {"00", "10"}  # NBA, WNBA

# --- Cache Directory Setup ---
SCHEDULE_LEAGUE_V2_INT_CSV_DIR = get_cache_dir("schedule_league_v2_int")

# Ensure cache directories exist
os.makedirs(SCHEDULE_LEAGUE_V2_INT_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_schedule_league_v2_int(
    league_id: str = "00",
    season: str = CURRENT_NBA_SEASON,
    data_set_name: str = "ScheduleLeagueV2Int"
) -> str:
    """
    Generates a file path for saving schedule league v2 int DataFrame.
    
    Args:
        league_id: League ID (default: "00" for NBA)
        season: Season (default: current season)
        data_set_name: Name of the data set
        
    Returns:
        Path to the CSV file
    """
    # Create a filename based on the parameters
    filename_parts = [
        f"schedule_league_v2_int",
        f"league{league_id}",
        f"season{season.replace('-', '_')}",
        data_set_name
    ]
    
    filename = "_".join(filename_parts) + ".csv"
    
    return get_cache_file_path(filename, "schedule_league_v2_int")

# --- Parameter Validation ---
def _validate_schedule_league_v2_int_params(
    league_id: str,
    season: str
) -> Optional[str]:
    """Validates parameters for fetch_schedule_league_v2_int_logic."""
    if league_id not in VALID_LEAGUE_IDS:
        return f"Invalid league_id: {league_id}. Valid options: {', '.join(VALID_LEAGUE_IDS)}"
    if not _validate_season_format(season):
        return f"Invalid season format: {season}. Expected format: YYYY-YY"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=SCHEDULE_LEAGUE_V2_INT_CACHE_SIZE)
def fetch_schedule_league_v2_int_logic(
    league_id: str = "00",
    season: str = CURRENT_NBA_SEASON,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches schedule league v2 int data using the ScheduleLeagueV2Int endpoint.
    
    Provides DataFrame output capabilities and CSV caching.
    
    Args:
        league_id: League ID (default: "00" for NBA)
        season: Season (default: current season)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with schedule league v2 int data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(
        f"Executing fetch_schedule_league_v2_int_logic for League: {league_id}, Season: {season}, "
        f"return_dataframe={return_dataframe}"
    )
    
    # Validate parameters
    validation_error = _validate_schedule_league_v2_int_params(league_id, season)
    if validation_error:
        logger.warning(f"Parameter validation failed for schedule league v2 int: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response
    
    # Check for cached CSV files
    dataframes = {}
    
    # Try to load from cache first
    if return_dataframe:
        # Check for all possible data sets
        data_set_names = ["Games", "Weeks", "Broadcasters"]
        all_cached = True
        
        for data_set_name in data_set_names:
            csv_path = _get_csv_path_for_schedule_league_v2_int(league_id, season, data_set_name)
            if os.path.exists(csv_path):
                try:
                    # Check if the file is empty or too small
                    file_size = os.path.getsize(csv_path)
                    if file_size < 100:  # If file is too small, it's probably empty or corrupted
                        logger.warning(f"CSV file is too small ({file_size} bytes), fetching from API instead")
                        all_cached = False
                        break
                    else:
                        logger.info(f"Loading schedule league v2 int from CSV: {csv_path}")
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
                    "season": season
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
            "season": season
        }
        
        logger.debug(f"Calling ScheduleLeagueV2Int with parameters: {api_params}")
        schedule_endpoint = scheduleleaguev2int.ScheduleLeagueV2Int(**api_params)
        
        # Get data frames
        list_of_dataframes = schedule_endpoint.get_data_frames()
        
        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": {
                "league_id": league_id,
                "season": season
            },
            "data_sets": {}
        }
        
        # Process each data frame
        data_set_names = ["Games", "Weeks", "Broadcasters"]
        
        for idx, df in enumerate(list_of_dataframes):
            # Use predefined names for the data sets
            data_set_name = data_set_names[idx] if idx < len(data_set_names) else f"ScheduleLeagueV2Int_{idx}"
            
            # Store DataFrame if requested (even if empty for caching purposes)
            if return_dataframe:
                dataframes[data_set_name] = df
                
                # Save DataFrame to CSV
                csv_path = _get_csv_path_for_schedule_league_v2_int(league_id, season, data_set_name)
                _save_dataframe_to_csv(df, csv_path)
            
            # Process for JSON response (limit to first 100 records for large datasets)
            if len(df) > 100:
                logger.info(f"Large dataset detected ({len(df)} records), limiting JSON response to first 100 records")
                processed_data = _process_dataframe(df.head(100), single_row=False)
                result_dict["data_sets"][data_set_name] = {
                    "total_records": len(df),
                    "displayed_records": 100,
                    "data": processed_data
                }
            else:
                processed_data = _process_dataframe(df, single_row=False)
                result_dict["data_sets"][data_set_name] = processed_data
        
        final_json_response = format_response(result_dict)
        if return_dataframe:
            return final_json_response, dataframes
        return final_json_response
        
    except Exception as e:
        logger.error(f"Unexpected error in fetch_schedule_league_v2_int_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_schedule_league_v2_int(
    league_id: str = "00",
    season: str = CURRENT_NBA_SEASON,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get schedule league v2 int data.
    
    Args:
        league_id: League ID (default: "00" for NBA)
        season: Season (default: current season)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with schedule league v2 int data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_schedule_league_v2_int_logic(
        league_id=league_id,
        season=season,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Test basic functionality
    print("Testing ScheduleLeagueV2Int endpoint...")
    
    # Test 1: Basic fetch
    json_response = get_schedule_league_v2_int()
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")
    
    # Test 2: With DataFrame output
    json_response, dataframes = get_schedule_league_v2_int(return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")
    
    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()[:10]}...")  # Show first 10 columns
            print(f"Sample data: {df.head(1).to_dict('records')}")
    
    print("ScheduleLeagueV2Int endpoint test completed.")

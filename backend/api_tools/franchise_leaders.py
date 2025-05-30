"""
Handles fetching and processing franchise statistical leaders data
from the FranchiseLeaders endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The FranchiseLeaders endpoint provides comprehensive franchise statistical leaders data (16 columns):
- Team info: TEAM_ID (1 column)
- Points leaders: PTS, PTS_PERSON_ID, PTS_PLAYER (3 columns)
- Assists leaders: AST, AST_PERSON_ID, AST_PLAYER (3 columns)
- Rebounds leaders: REB, REB_PERSON_ID, REB_PLAYER (3 columns)
- Blocks leaders: BLK, BLK_PERSON_ID, BLK_PLAYER (3 columns)
- Steals leaders: STL, STL_PERSON_ID, STL_PLAYER (3 columns)
- Team-specific data: Each team has their all-time statistical leaders
- Perfect for franchise legends, historical context, and team comparisons
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import franchiseleaders
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

def _validate_team_id(team_id):
    """Validate team ID format."""
    if not team_id:
        return False
    
    try:
        # Check if it's a valid team ID (should be a number)
        int(team_id)
        return True
    except ValueError:
        return False

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
FRANCHISE_LEADERS_CACHE_SIZE = 64

# Valid NBA team IDs (current teams)
VALID_TEAM_IDS: Set[str] = {
    "1610612737",  # Atlanta Hawks
    "1610612738",  # Boston Celtics
    "1610612751",  # Brooklyn Nets
    "1610612766",  # Charlotte Hornets
    "1610612741",  # Chicago Bulls
    "1610612739",  # Cleveland Cavaliers
    "1610612742",  # Dallas Mavericks
    "1610612743",  # Denver Nuggets
    "1610612765",  # Detroit Pistons
    "1610612744",  # Golden State Warriors
    "1610612745",  # Houston Rockets
    "1610612754",  # Indiana Pacers
    "1610612746",  # LA Clippers
    "1610612747",  # Los Angeles Lakers
    "1610612763",  # Memphis Grizzlies
    "1610612748",  # Miami Heat
    "1610612749",  # Milwaukee Bucks
    "1610612750",  # Minnesota Timberwolves
    "1610612740",  # New Orleans Pelicans
    "1610612752",  # New York Knicks
    "1610612760",  # Oklahoma City Thunder
    "1610612753",  # Orlando Magic
    "1610612755",  # Philadelphia 76ers
    "1610612756",  # Phoenix Suns
    "1610612757",  # Portland Trail Blazers
    "1610612758",  # Sacramento Kings
    "1610612759",  # San Antonio Spurs
    "1610612761",  # Toronto Raptors
    "1610612762",  # Utah Jazz
    "1610612764",  # Washington Wizards
}

# --- Cache Directory Setup ---
FRANCHISE_LEADERS_CSV_DIR = get_cache_dir("franchise_leaders")

# Ensure cache directories exist
os.makedirs(FRANCHISE_LEADERS_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_franchise_leaders(
    team_id: str
) -> str:
    """
    Generates a file path for saving franchise leaders DataFrame.
    
    Args:
        team_id: Team ID
        
    Returns:
        Path to the CSV file
    """
    filename = f"franchise_leaders_team{team_id}.csv"
    return get_cache_file_path(filename, "franchise_leaders")

# --- Parameter Validation ---
def _validate_franchise_leaders_params(
    team_id: str
) -> Optional[str]:
    """Validates parameters for fetch_franchise_leaders_logic."""
    if not team_id:
        return "team_id is required"
    if not _validate_team_id(team_id):
        return f"Invalid team_id format: {team_id}. Expected numeric team ID"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=FRANCHISE_LEADERS_CACHE_SIZE)
def fetch_franchise_leaders_logic(
    team_id: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches franchise statistical leaders data using the FranchiseLeaders endpoint.
    
    Provides DataFrame output capabilities and CSV caching.
    
    Args:
        team_id: Team ID (required)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with franchise leaders data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(
        f"Executing fetch_franchise_leaders_logic for Team: {team_id}, "
        f"return_dataframe={return_dataframe}"
    )
    
    # Validate parameters
    validation_error = _validate_franchise_leaders_params(team_id)
    if validation_error:
        logger.warning(f"Parameter validation failed for franchise leaders: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response
    
    # Check for cached CSV file
    csv_path = _get_csv_path_for_franchise_leaders(team_id)
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
                logger.info(f"Loading franchise leaders from CSV: {csv_path}")
                # Read CSV with appropriate data types
                df = pd.read_csv(csv_path, encoding='utf-8')
                
                # Process for JSON response
                result_dict = {
                    "parameters": {
                        "team_id": team_id
                    },
                    "data_sets": {}
                }
                
                # Store the DataFrame
                dataframes["FranchiseLeaders"] = df
                result_dict["data_sets"]["FranchiseLeaders"] = _process_dataframe(df, single_row=False)
                
                if return_dataframe:
                    return format_response(result_dict), dataframes
                return format_response(result_dict)
            
        except Exception as e:
            logger.error(f"Error loading CSV: {e}", exc_info=True)
            # If there's an error loading the CSV, fetch from the API
    
    try:
        # Prepare API parameters
        api_params = {
            "team_id": team_id
        }
        
        logger.debug(f"Calling FranchiseLeaders with parameters: {api_params}")
        franchise_leaders_endpoint = franchiseleaders.FranchiseLeaders(**api_params)
        
        # Get data frames
        list_of_dataframes = franchise_leaders_endpoint.get_data_frames()
        
        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": api_params,
            "data_sets": {}
        }
        
        # Create a combined DataFrame for CSV storage
        combined_df = pd.DataFrame()
        
        # Process each data frame
        for idx, df in enumerate(list_of_dataframes):
            if not df.empty:
                # Use a generic name for the data set
                data_set_name = f"FranchiseLeaders_{idx}" if idx > 0 else "FranchiseLeaders"
                
                # Store DataFrame if requested
                if return_dataframe:
                    dataframes[data_set_name] = df
                    
                    # Use the first (main) DataFrame for CSV storage
                    if idx == 0:
                        combined_df = df.copy()
                
                # Process for JSON response
                processed_data = _process_dataframe(df, single_row=False)
                result_dict["data_sets"][data_set_name] = processed_data
        
        # Save combined DataFrame to CSV
        if return_dataframe and not combined_df.empty:
            _save_dataframe_to_csv(combined_df, csv_path)
        
        final_json_response = format_response(result_dict)
        if return_dataframe:
            return final_json_response, dataframes
        return final_json_response
        
    except Exception as e:
        logger.error(f"Unexpected error in fetch_franchise_leaders_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_franchise_leaders(
    team_id: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get franchise statistical leaders data.
    
    Args:
        team_id: Team ID (required)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with franchise leaders data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_franchise_leaders_logic(
        team_id=team_id,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Test basic functionality
    print("Testing FranchiseLeaders endpoint...")
    
    # Test 1: Basic fetch
    json_response = get_franchise_leaders("1610612747")  # Lakers
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")
    
    # Test 2: With DataFrame output
    json_response, dataframes = get_franchise_leaders("1610612747", return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")
    
    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")
    
    print("FranchiseLeaders endpoint test completed.")

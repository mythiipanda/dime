"""
Handles fetching and processing NBA Draft Combine drill results data
from the DraftCombineDrillResults endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The DraftCombineDrillResults endpoint provides comprehensive NBA Draft Combine athletic measurements:
- Player info: ID, names, position (6 columns)
- Athletic measurements: vertical leap, agility times, sprint times, bench press (6 columns)
- Data available for multiple years (2021: 74 players, 2022: 83 players, 2023: 81 players, 2024: 83 players)
- Perfect for pre-draft player analysis and athletic evaluation
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import draftcombinedrillresults
import pandas as pd

from utils.path_utils import get_cache_dir, get_cache_file_path

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

def _validate_season_year_format(season_year):
    """Validate season year format (YYYY)."""
    if not season_year:
        return False
    
    try:
        year = int(season_year)
        # Check if it's a reasonable year (2000-2030)
        return 2000 <= year <= 2030
    except ValueError:
        return False

# Default current NBA season year
CURRENT_NBA_SEASON_YEAR = "2024"

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
DRAFT_COMBINE_CACHE_SIZE = 32

# Valid parameter sets
VALID_LEAGUE_IDS: Set[str] = {"00", "10"}  # NBA, WNBA

# --- Cache Directory Setup ---
DRAFT_COMBINE_CSV_DIR = get_cache_dir("draft_combine_drill_results")

# Ensure cache directories exist
os.makedirs(DRAFT_COMBINE_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_draft_combine(
    league_id: str = "00",
    season_year: str = CURRENT_NBA_SEASON_YEAR
) -> str:
    """
    Generates a file path for saving draft combine drill results DataFrame.
    
    Args:
        league_id: League ID (default: "00" for NBA)
        season_year: Season year in YYYY format
        
    Returns:
        Path to the CSV file
    """
    filename = f"draft_combine_drill_results_league{league_id}_season{season_year}.csv"
    return get_cache_file_path(filename, "draft_combine_drill_results")

# --- Parameter Validation ---
def _validate_draft_combine_params(
    league_id: str,
    season_year: str
) -> Optional[str]:
    """Validates parameters for fetch_draft_combine_drill_results_logic."""
    if league_id not in VALID_LEAGUE_IDS:
        return f"Invalid league_id: {league_id}. Valid options: {', '.join(VALID_LEAGUE_IDS)}"
    if not season_year or not _validate_season_year_format(season_year):
        return f"Invalid season_year format: {season_year}. Expected format: YYYY"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=DRAFT_COMBINE_CACHE_SIZE)
def fetch_draft_combine_drill_results_logic(
    league_id: str = "00",
    season_year: str = CURRENT_NBA_SEASON_YEAR,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches NBA Draft Combine drill results data using the DraftCombineDrillResults endpoint.
    
    Provides DataFrame output capabilities and CSV caching.
    
    Args:
        league_id: League ID (default: "00" for NBA)
        season_year: Season year in YYYY format (default: current NBA season year)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with draft combine drill results data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(
        f"Executing fetch_draft_combine_drill_results_logic for League: {league_id}, "
        f"Season Year: {season_year}, return_dataframe={return_dataframe}"
    )
    
    # Validate parameters
    validation_error = _validate_draft_combine_params(league_id, season_year)
    if validation_error:
        logger.warning(f"Parameter validation failed for draft combine drill results: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response
    
    # Check for cached CSV file
    csv_path = _get_csv_path_for_draft_combine(league_id, season_year)
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
                logger.info(f"Loading draft combine drill results from CSV: {csv_path}")
                # Read CSV with appropriate data types
                df = pd.read_csv(csv_path, encoding='utf-8')
                
                # Process for JSON response
                result_dict = {
                    "parameters": {
                        "league_id": league_id,
                        "season_year": season_year
                    },
                    "data_sets": {}
                }
                
                # Store the DataFrame
                dataframes["DraftCombineDrillResults"] = df
                result_dict["data_sets"]["DraftCombineDrillResults"] = _process_dataframe(df, single_row=False)
                
                if return_dataframe:
                    return format_response(result_dict), dataframes
                return format_response(result_dict)
            
        except Exception as e:
            logger.error(f"Error loading CSV: {e}", exc_info=True)
            # If there's an error loading the CSV, fetch from the API
    
    try:
        # Prepare API parameters
        api_params = {
            "league_id": league_id,
            "season_year": season_year
        }
        
        logger.debug(f"Calling DraftCombineDrillResults with parameters: {api_params}")
        draft_combine_endpoint = draftcombinedrillresults.DraftCombineDrillResults(**api_params)
        
        # Get data frames
        list_of_dataframes = draft_combine_endpoint.get_data_frames()
        
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
                data_set_name = f"DraftCombineDrillResults_{idx}" if idx > 0 else "DraftCombineDrillResults"
                
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
        logger.error(f"Unexpected error in fetch_draft_combine_drill_results_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_draft_combine_drill_results(
    league_id: str = "00",
    season_year: str = CURRENT_NBA_SEASON_YEAR,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get NBA Draft Combine drill results data.
    
    Args:
        league_id: League ID (default: "00" for NBA)
        season_year: Season year in YYYY format (default: current NBA season year)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with draft combine drill results data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_draft_combine_drill_results_logic(
        league_id=league_id,
        season_year=season_year,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Test basic functionality
    print("Testing DraftCombineDrillResults endpoint...")
    
    # Test 1: Basic fetch
    json_response = get_draft_combine_drill_results()
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")
    
    # Test 2: With DataFrame output
    json_response, dataframes = get_draft_combine_drill_results(return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")
    
    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")
    
    print("DraftCombineDrillResults endpoint test completed.")

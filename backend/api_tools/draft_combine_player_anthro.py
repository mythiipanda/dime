"""
NBA API tools for accessing draft combine player anthropometric data.

This module provides functions to fetch and process data from the NBA's draft combine
player anthropometric endpoint, which includes physical measurements such as:
- Height (with and without shoes)
- Weight
- Wingspan
- Standing reach
- Body fat percentage
- Hand length and width

The data is returned as pandas DataFrames and can be cached as CSV files for faster access.
"""

import os
import logging
import json
from typing import Optional, Dict, Any, Union, Tuple, List
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import draftcombineplayeranthro
from utils.validation import _validate_season_format
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

# Set up logging
logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
DRAFT_COMBINE_PLAYER_ANTHRO_CACHE_SIZE = 128
DRAFT_COMBINE_CSV_DIR = get_cache_dir("draft_combine")

# Valid parameter values
VALID_LEAGUE_IDS = {
    "00": "00",  # NBA
    "10": "10",  # WNBA
    "20": "20"   # G-League
}

# --- Helper Functions for DataFrame Processing ---
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
        
        # Save DataFrame to CSV
        df.to_csv(file_path, index=False)
        logger.info(f"Saved DataFrame to CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)


def _get_csv_path_for_draft_combine_player_anthro(season_year: str, league_id: str = "00") -> str:
    """
    Generates a file path for saving draft combine player anthropometric DataFrame.
    
    Args:
        season_year: Season year in YYYY format
        league_id: League ID (default: "00" for NBA)
        
    Returns:
        Path to the CSV file
    """
    filename = f"draft_combine_player_anthro_{season_year}_{league_id}.csv"
    return get_cache_file_path(filename, "draft_combine")

# --- Parameter Validation Functions ---
def _validate_draft_combine_player_anthro_params(
    season_year: str,
    league_id: str
) -> Optional[str]:
    """
    Validates parameters for the draft combine player anthropometric function.
    
    Args:
        season_year: Season year in YYYY format
        league_id: League ID (e.g., "00" for NBA)
        
    Returns:
        Error message if validation fails, None otherwise
    """
    if not season_year:
        return "Season year cannot be empty"
    
    # Validate season format
    season_error = _validate_season_format(season_year)
    if season_error:
        return season_error
    
    if league_id not in VALID_LEAGUE_IDS:
        return f"Invalid league_id: {league_id}. Valid options are: {', '.join(VALID_LEAGUE_IDS.keys())}"
    
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=DRAFT_COMBINE_PLAYER_ANTHRO_CACHE_SIZE)
def fetch_draft_combine_player_anthro_logic(
    season_year: str,
    league_id: str = "00",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches draft combine player anthropometric data from the NBA API.
    
    This endpoint provides physical measurements from the NBA Draft Combine:
    - Height (with and without shoes)
    - Weight
    - Wingspan
    - Standing reach
    - Body fat percentage
    - Hand length and width
    
    Args:
        season_year (str): Season year in YYYY format (e.g., "2023")
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        return_dataframe (bool, optional): Whether to return DataFrames. Defaults to False.
        
    Returns:
        If return_dataframe=False:
            str: JSON string with draft combine player anthropometric data or error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: JSON response and dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_draft_combine_player_anthro_logic for: Season: {season_year}, League: {league_id}")
    
    dataframes: Dict[str, pd.DataFrame] = {}
    
    # Validate parameters
    validation_error = _validate_draft_combine_player_anthro_params(season_year, league_id)
    if validation_error:
        if return_dataframe:
            return format_response(error=validation_error), dataframes
        return format_response(error=validation_error)
    
    # Check if cached CSV file exists
    csv_path = _get_csv_path_for_draft_combine_player_anthro(season_year, league_id)
    
    if os.path.exists(csv_path) and return_dataframe:
        try:
            logger.info(f"Loading draft combine player anthropometric data from CSV: {csv_path}")
            # Read CSV with appropriate data types
            df = pd.read_csv(csv_path)
            
            # Convert numeric columns to appropriate types
            numeric_columns = [
                "HEIGHT_WO_SHOES", "HEIGHT_W_SHOES", "WEIGHT", 
                "WINGSPAN", "STANDING_REACH", "BODY_FAT_PCT",
                "HAND_LENGTH", "HAND_WIDTH"
            ]
            
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Store DataFrame
            dataframes["Results"] = df
            
            # Process for JSON response
            result_dict = {
                "parameters": {
                    "season_year": season_year,
                    "league_id": league_id
                },
                "data_sets": {
                    "Results": _process_dataframe(df, single_row=False)
                }
            }
            
            if return_dataframe:
                return format_response(result_dict), dataframes
            return format_response(result_dict)
            
        except Exception as e:
            logger.error(f"Error loading CSV: {e}", exc_info=True)
            # If there's an error loading the CSV, fetch from the API
    
    # Prepare API parameters
    api_params = {
        "league_id": league_id,
        "season_year": season_year
    }
    
    try:
        # Call the NBA API endpoint
        logger.debug(f"Calling DraftCombinePlayerAnthro with parameters: {api_params}")
        player_anthro_results = draftcombineplayeranthro.DraftCombinePlayerAnthro(**api_params)
        
        # Get normalized dictionary for data set names
        normalized_dict = player_anthro_results.get_normalized_dict()
        
        # Get data frames
        list_of_dataframes = player_anthro_results.get_data_frames()
        
        # Expected data set name based on documentation
        expected_data_set_name = "Results"
        
        # Get data set names from the result sets
        data_set_names = []
        if "resultSets" in normalized_dict:
            data_set_names = list(normalized_dict["resultSets"].keys())
        else:
            # If no result sets found, use expected name
            data_set_names = [expected_data_set_name]
        
        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": api_params,
            "data_sets": {}
        }
        
        # Process each data set
        for idx, data_set_name in enumerate(data_set_names):
            if idx < len(list_of_dataframes):
                df = list_of_dataframes[idx]
                
                # Store DataFrame if requested
                if return_dataframe:
                    dataframes[data_set_name] = df
                    
                    # Save to CSV if not empty
                    if not df.empty:
                        _save_dataframe_to_csv(df, csv_path)
                
                # Process for JSON response
                processed_data = _process_dataframe(df, single_row=False)
                result_dict["data_sets"][data_set_name] = processed_data
        
        # Return response
        logger.info(f"Successfully fetched draft combine player anthropometric data for {season_year}")
        if return_dataframe:
            return format_response(result_dict), dataframes
        return format_response(result_dict)
        
    except Exception as e:
        logger.error(f"API error in fetch_draft_combine_player_anthro_logic: {e}", exc_info=True)
        error_msg = f"Error fetching draft combine player anthropometric data for season {season_year}: {str(e)}"
        
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)


def get_draft_combine_player_anthro(
    season_year: str,
    league_id: str = "00",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Gets draft combine player anthropometric data.
    
    This function is the main entry point for fetching draft combine player anthropometric data.
    It calls the fetch_draft_combine_player_anthro_logic function and returns the results.
    
    Args:
        season_year (str): Season year in YYYY format (e.g., "2023")
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        return_dataframe (bool, optional): Whether to return DataFrames. Defaults to False.
        
    Returns:
        If return_dataframe=False:
            str: JSON string with draft combine player anthropometric data or error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: JSON response and dictionary of DataFrames.
    """
    return fetch_draft_combine_player_anthro_logic(
        season_year=season_year,
        league_id=league_id,
        return_dataframe=return_dataframe
    )

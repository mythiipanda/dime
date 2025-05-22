"""
NBA API tools for accessing all-time statistical leaders data.

This module provides functions to fetch and process data from the NBA's all-time leaders
endpoint, which includes information such as:
- Points leaders
- Rebounds leaders
- Assists leaders
- Steals leaders
- Blocks leaders
- Field goal percentage leaders
- Free throw percentage leaders
- Three-point percentage leaders
- Games played leaders
- And many other statistical categories

The data is returned as pandas DataFrames and can be cached as CSV files for faster access.
"""

import os
import logging
import json
from typing import Optional, Dict, Any, Union, Tuple, List
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import alltimeleadersgrids
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
ALL_TIME_LEADERS_CACHE_SIZE = 128
ALL_TIME_LEADERS_CSV_DIR = get_cache_dir("all_time_leaders")

# Valid parameter values
VALID_LEAGUE_IDS = {
    "00": "00",  # NBA
    "10": "10",  # WNBA
    "20": "20"   # G-League
}

VALID_PER_MODES = {
    "Totals": "Totals",
    "PerGame": "PerGame"
}

VALID_SEASON_TYPES = {
    "Regular Season": "Regular Season",
    "Pre Season": "Pre Season"
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

        # Save DataFrame to CSV with UTF-8 encoding
        df.to_csv(file_path, index=False, encoding='utf-8')

        # Log the file size and path
        file_size = os.path.getsize(file_path)
        logger.info(f"Saved DataFrame to CSV: {file_path} (Size: {file_size} bytes)")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)


def _get_csv_path_for_all_time_leaders(
    league_id: str = "00",
    per_mode: str = "Totals",
    season_type: str = "Regular Season",
    topx: int = 10
) -> str:
    """
    Generates a file path for saving all-time leaders DataFrame.

    Args:
        league_id: League ID (default: "00" for NBA)
        per_mode: Per mode (default: "Totals")
        season_type: Season type (default: "Regular Season")
        topx: Number of top players to return (default: 10)

    Returns:
        Path to the CSV file
    """
    # Create a filename based on the parameters
    # Replace spaces with underscores for season_type
    safe_season_type = season_type.replace(" ", "_")

    # Create a unique filename that includes all parameters
    filename = f"all_time_leaders_league{league_id}_mode{per_mode}_season{safe_season_type}_top{topx}.csv"

    return get_cache_file_path(filename, "all_time_leaders")

# --- Parameter Validation Functions ---
def _validate_all_time_leaders_params(
    league_id: str,
    per_mode: str,
    season_type: str,
    topx: int
) -> Optional[str]:
    """
    Validates parameters for the all-time leaders function.

    Args:
        league_id: League ID (e.g., "00" for NBA)
        per_mode: Per mode (e.g., "Totals", "PerGame")
        season_type: Season type (e.g., "Regular Season", "Pre Season")
        topx: Number of top players to return

    Returns:
        Error message if validation fails, None otherwise
    """
    if league_id not in VALID_LEAGUE_IDS:
        return f"Invalid league_id: {league_id}. Valid options are: {', '.join(VALID_LEAGUE_IDS.keys())}"

    if per_mode not in VALID_PER_MODES:
        return f"Invalid per_mode: {per_mode}. Valid options are: {', '.join(VALID_PER_MODES.keys())}"

    if season_type not in VALID_SEASON_TYPES:
        return f"Invalid season_type: {season_type}. Valid options are: {', '.join(VALID_SEASON_TYPES.keys())}"

    if not isinstance(topx, int) or topx <= 0:
        return f"Invalid topx: {topx}. Must be a positive integer."

    return None

# --- Main Logic Function ---
@lru_cache(maxsize=ALL_TIME_LEADERS_CACHE_SIZE)
def fetch_all_time_leaders_logic(
    league_id: str = "00",
    per_mode: str = "Totals",
    season_type: str = "Regular Season",
    topx: int = 10,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches all-time statistical leaders data from the NBA API.

    This endpoint provides all-time statistical leaders in various categories:
    - Points leaders
    - Rebounds leaders
    - Assists leaders
    - Steals leaders
    - Blocks leaders
    - Field goal percentage leaders
    - Free throw percentage leaders
    - Three-point percentage leaders
    - Games played leaders
    - And many other statistical categories

    Args:
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        per_mode (str, optional): Per mode. Defaults to "Totals".
        season_type (str, optional): Season type. Defaults to "Regular Season".
        topx (int, optional): Number of top players to return. Defaults to 10.
        return_dataframe (bool, optional): Whether to return DataFrames. Defaults to False.

    Returns:
        If return_dataframe=False:
            str: JSON string with all-time leaders data or error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: JSON response and dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_all_time_leaders_logic for: League: {league_id}, PerMode: {per_mode}, TopX: {topx}")

    dataframes: Dict[str, pd.DataFrame] = {}

    # Validate parameters
    validation_error = _validate_all_time_leaders_params(
        league_id=league_id,
        per_mode=per_mode,
        season_type=season_type,
        topx=topx
    )

    if validation_error:
        if return_dataframe:
            return format_response(error=validation_error), dataframes
        return format_response(error=validation_error)

    # Check if cached CSV file exists
    csv_path = _get_csv_path_for_all_time_leaders(
        league_id=league_id,
        per_mode=per_mode,
        season_type=season_type,
        topx=topx
    )

    if os.path.exists(csv_path) and return_dataframe:
        try:
            # Check if the file is empty or too small
            file_size = os.path.getsize(csv_path)
            if file_size < 10:  # If file is too small, it's probably empty or corrupted
                logger.warning(f"CSV file is too small ({file_size} bytes), fetching from API instead")
                # Delete the corrupted file
                try:
                    os.remove(csv_path)
                    logger.info(f"Deleted corrupted CSV file: {csv_path}")
                except Exception as e:
                    logger.error(f"Error deleting corrupted CSV file: {e}", exc_info=True)
                # Continue to API fetch
            else:
                logger.info(f"Loading all-time leaders from CSV: {csv_path}")
                # Read CSV with appropriate data types
                df = pd.read_csv(csv_path, encoding='utf-8')

                # Process for JSON response
                result_dict = {
                    "parameters": {
                        "league_id": league_id,
                        "per_mode": per_mode,
                        "season_type": season_type,
                        "topx": topx
                    },
                    "data_sets": {}
                }

                # Split the CSV into multiple DataFrames based on the category
                categories = [
                    "ASTLeaders", "BLKLeaders", "DREBLeaders", "FG3ALeaders", "FG3MLeaders",
                    "FG3_PCTLeaders", "FGALeaders", "FGMLeaders", "FG_PCTLeaders", "FTALeaders",
                    "FTMLeaders", "FT_PCTLeaders", "GPLeaders", "OREBLeaders", "PFLeaders",
                    "PTSLeaders", "REBLeaders", "STLLeaders", "TOVLeaders"
                ]

                # Check if the CSV contains a 'Category' column
                if 'Category' in df.columns:
                    # Split the DataFrame by category
                    for category in categories:
                        category_df = df[df['Category'] == category]
                        if not category_df.empty:
                            # Drop the Category column for the individual dataframes
                            category_df = category_df.drop('Category', axis=1)
                            dataframes[category] = category_df
                            result_dict["data_sets"][category] = _process_dataframe(category_df, single_row=False)
                else:
                    # If no Category column, assume it's a combined CSV with all categories
                    dataframes["AllTimeLeaders"] = df
                    result_dict["data_sets"]["AllTimeLeaders"] = _process_dataframe(df, single_row=False)

                if return_dataframe:
                    return format_response(result_dict), dataframes
                return format_response(result_dict)

        except Exception as e:
            logger.error(f"Error loading CSV: {e}", exc_info=True)
            # If there's an error loading the CSV, fetch from the API

    # Prepare API parameters
    api_params = {
        "league_id": league_id,
        "per_mode_simple": per_mode,
        "season_type": season_type,
        "topx": topx
    }

    try:
        # Call the NBA API endpoint
        logger.debug(f"Calling AllTimeLeadersGrids with parameters: {api_params}")
        all_time_leaders_results = alltimeleadersgrids.AllTimeLeadersGrids(**api_params)

        # Get data frames directly
        list_of_dataframes = all_time_leaders_results.get_data_frames()

        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": api_params,
            "data_sets": {}
        }

        # List of expected data set names for reference
        # These are the categories we expect to see in the API response
        # We'll use this for debugging and documentation purposes
        # "ASTLeaders", "BLKLeaders", "DREBLeaders", "FG3ALeaders", "FG3MLeaders",
        # "FG3_PCTLeaders", "FGALeaders", "FGMLeaders", "FG_PCTLeaders", "FTALeaders",
        # "FTMLeaders", "FT_PCTLeaders", "GPLeaders", "OREBLeaders", "PFLeaders",
        # "PTSLeaders", "REBLeaders", "STLLeaders", "TOVLeaders"

        # Create a combined DataFrame for CSV storage
        combined_df = pd.DataFrame()

        # Process each data frame
        for idx, df in enumerate(list_of_dataframes):
            if not df.empty:
                # Try to determine the data set name based on columns
                data_set_name = None

                # Check for specific columns to identify the data set
                if 'PTS' in df.columns:
                    data_set_name = "PTSLeaders"
                elif 'AST' in df.columns:
                    data_set_name = "ASTLeaders"
                elif 'REB' in df.columns:
                    data_set_name = "REBLeaders"
                elif 'BLK' in df.columns:
                    data_set_name = "BLKLeaders"
                elif 'STL' in df.columns:
                    data_set_name = "STLLeaders"
                elif 'FG_PCT' in df.columns:
                    data_set_name = "FG_PCTLeaders"
                elif 'FT_PCT' in df.columns:
                    data_set_name = "FT_PCTLeaders"
                elif 'FG3_PCT' in df.columns:
                    data_set_name = "FG3_PCTLeaders"
                elif 'FGM' in df.columns:
                    data_set_name = "FGMLeaders"
                elif 'FGA' in df.columns:
                    data_set_name = "FGALeaders"
                elif 'FTM' in df.columns:
                    data_set_name = "FTMLeaders"
                elif 'FTA' in df.columns:
                    data_set_name = "FTALeaders"
                elif 'FG3M' in df.columns:
                    data_set_name = "FG3MLeaders"
                elif 'FG3A' in df.columns:
                    data_set_name = "FG3ALeaders"
                elif 'OREB' in df.columns:
                    data_set_name = "OREBLeaders"
                elif 'DREB' in df.columns:
                    data_set_name = "DREBLeaders"
                elif 'GP' in df.columns:
                    data_set_name = "GPLeaders"
                elif 'PF' in df.columns:
                    data_set_name = "PFLeaders"
                elif 'TOV' in df.columns:
                    data_set_name = "TOVLeaders"
                else:
                    # If we can't identify the data set, use a generic name
                    data_set_name = f"DataSet_{idx}"

                # Store DataFrame if requested
                if return_dataframe:
                    dataframes[data_set_name] = df

                    # Add category column and append to combined DataFrame
                    df_with_category = df.copy()
                    df_with_category['Category'] = data_set_name

                    # Make sure all stats columns are present in the combined DataFrame
                    # This ensures that each row has the correct structure for all stats
                    if not combined_df.empty:
                        # Get all columns from both DataFrames
                        all_columns = set(list(combined_df.columns) + list(df_with_category.columns))

                        # Add missing columns to both DataFrames with NaN values
                        for col in all_columns:
                            if col not in combined_df.columns:
                                combined_df[col] = None
                            if col not in df_with_category.columns:
                                df_with_category[col] = None

                    # Now concatenate the DataFrames
                    combined_df = pd.concat([combined_df, df_with_category], ignore_index=True)

                # Process for JSON response
                processed_data = _process_dataframe(df, single_row=False)
                result_dict["data_sets"][data_set_name] = processed_data

        # Save combined DataFrame to CSV
        if return_dataframe:
            # Even if the DataFrame is empty, save it to indicate we tried to fetch the data
            # This will help with caching and prevent repeated API calls
            _save_dataframe_to_csv(combined_df, csv_path)

        # Return response
        logger.info(f"Successfully fetched all-time leaders data")
        if return_dataframe:
            return format_response(result_dict), dataframes
        return format_response(result_dict)

    except Exception as e:
        logger.error(f"API error in fetch_all_time_leaders_logic: {e}", exc_info=True)
        error_msg = f"Error fetching all-time leaders data: {str(e)}"

        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)


def get_all_time_leaders(
    league_id: str = "00",
    per_mode: str = "Totals",
    season_type: str = "Regular Season",
    topx: int = 10,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Gets all-time statistical leaders data.

    This function is the main entry point for fetching all-time leaders data.
    It calls the fetch_all_time_leaders_logic function and returns the results.

    Args:
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        per_mode (str, optional): Per mode. Defaults to "Totals".
        season_type (str, optional): Season type. Defaults to "Regular Season".
        topx (int, optional): Number of top players to return. Defaults to 10.
        return_dataframe (bool, optional): Whether to return DataFrames. Defaults to False.

    Returns:
        If return_dataframe=False:
            str: JSON string with all-time leaders data or error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: JSON response and dictionary of DataFrames.
    """
    return fetch_all_time_leaders_logic(
        league_id=league_id,
        per_mode=per_mode,
        season_type=season_type,
        topx=topx,
        return_dataframe=return_dataframe
    )

"""
Handles fetching and processing team details data
from the TeamDetails endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The TeamDetails endpoint provides comprehensive team information with 8 DataFrames:
- TeamInfo: basic team details, arena, ownership, management (11 columns)
- TeamHistory: historical team info with year ranges (5 columns)
- SocialMediaAccounts: Facebook, Instagram, Twitter links (2 columns)
- Championships: championship history with opponents (2 columns)
- ConferenceChampionships: conference championship history (2 columns)
- DivisionChampionships: division championship history (2 columns)
- RetiredPlayers: retired jersey numbers and players (6 columns)
- HallOfFamePlayers: HOF players associated with team (6 columns)
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import teamdetails
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

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
TEAM_DETAILS_CACHE_SIZE = 32

# Valid parameter sets
VALID_TEAM_IDS: Set[str] = {
    # NBA Teams
    "1610612737", "1610612738", "1610612739", "1610612740", "1610612741",
    "1610612742", "1610612743", "1610612744", "1610612745", "1610612746",
    "1610612747", "1610612748", "1610612749", "1610612750", "1610612751",
    "1610612752", "1610612753", "1610612754", "1610612755", "1610612756",
    "1610612757", "1610612758", "1610612759", "1610612760", "1610612761",
    "1610612762", "1610612763", "1610612764", "1610612765", "1610612766"
}

# --- Cache Directory Setup ---
TEAM_DETAILS_CSV_DIR = get_cache_dir("team_details")

# Ensure cache directories exist
os.makedirs(TEAM_DETAILS_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_team_details(team_id: str, dataset_name: str = "TeamInfo") -> str:
    """
    Generates a file path for saving team details DataFrame.

    Args:
        team_id: Team ID
        dataset_name: Name of the dataset (e.g., "TeamInfo", "Championships", etc.)

    Returns:
        Path to the CSV file
    """
    filename = f"team_details_{team_id}_{dataset_name}.csv"
    return get_cache_file_path(filename, "team_details")

# --- Parameter Validation ---
def _validate_team_details_params(team_id: str) -> Optional[str]:
    """Validates parameters for fetch_team_details_logic."""
    if not team_id:
        return "team_id is required"
    if team_id not in VALID_TEAM_IDS:
        return f"Invalid team_id: {team_id}. Must be a valid NBA team ID"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=TEAM_DETAILS_CACHE_SIZE)
def fetch_team_details_logic(
    team_id: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches team details data using the TeamDetails endpoint.

    Provides DataFrame output capabilities and CSV caching.

    Args:
        team_id: Team ID (required)
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False:
            str: JSON string with team details data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(f"Executing fetch_team_details_logic for Team ID: {team_id}, return_dataframe={return_dataframe}")

    # Validate parameters
    validation_error = _validate_team_details_params(team_id)
    if validation_error:
        logger.warning(f"Parameter validation failed for team details: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response

    # Check for cached CSV files for all datasets
    dataframes = {}
    dataframe_names = [
        "TeamInfo", "TeamHistory", "SocialMediaAccounts", "Championships",
        "ConferenceChampionships", "DivisionChampionships", "RetiredPlayers", "HallOfFamePlayers"
    ]

    # Check if all CSV files exist
    all_csvs_exist = True
    csv_paths = {}

    if return_dataframe:
        for dataset_name in dataframe_names:
            csv_path = _get_csv_path_for_team_details(team_id, dataset_name)
            csv_paths[dataset_name] = csv_path
            if not os.path.exists(csv_path):
                all_csvs_exist = False
                break

        if all_csvs_exist:
            try:
                logger.info(f"Loading team details from cached CSV files for team {team_id}")

                # Load all DataFrames from CSV
                for dataset_name in dataframe_names:
                    csv_path = csv_paths[dataset_name]
                    if os.path.exists(csv_path):
                        file_size = os.path.getsize(csv_path)
                        if file_size > 50:  # Only load if file has content
                            df = pd.read_csv(csv_path, encoding='utf-8')
                            dataframes[dataset_name] = df

                # Process for JSON response
                result_dict = {
                    "parameters": {
                        "team_id": team_id
                    },
                    "data_sets": {}
                }

                # Add all datasets to response
                for dataset_name, df in dataframes.items():
                    result_dict["data_sets"][dataset_name] = _process_dataframe(df, single_row=False)

                # Add empty datasets for missing ones
                for dataset_name in dataframe_names:
                    if dataset_name not in result_dict["data_sets"]:
                        result_dict["data_sets"][dataset_name] = []

                if return_dataframe:
                    return format_response(result_dict), dataframes
                return format_response(result_dict)

            except Exception as e:
                logger.error(f"Error loading CSV files: {e}", exc_info=True)
                # If there's an error loading the CSVs, fetch from the API

    try:
        logger.debug(f"Calling TeamDetails with team_id: {team_id}")
        team_details_endpoint = teamdetails.TeamDetails(team_id=team_id)

        # Get data frames
        list_of_dataframes = team_details_endpoint.get_data_frames()

        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": {
                "team_id": team_id
            },
            "data_sets": {}
        }

        # Define meaningful names for the 8 DataFrames
        dataframe_names = [
            "TeamInfo",           # Basic team information
            "TeamHistory",        # Historical team information
            "SocialMediaAccounts", # Social media links
            "Championships",      # Championship history
            "ConferenceChampionships", # Conference championship history
            "DivisionChampionships",   # Division championship history
            "RetiredPlayers",     # Retired jersey numbers
            "HallOfFamePlayers"   # Hall of Fame players
        ]

        # Process each data frame
        for idx, df in enumerate(list_of_dataframes):
            if idx < len(dataframe_names):
                data_set_name = dataframe_names[idx]
            else:
                data_set_name = f"TeamDetails_{idx}"

            if not df.empty:
                # Store DataFrame if requested
                if return_dataframe:
                    dataframes[data_set_name] = df

                    # Save each DataFrame to its own CSV file
                    csv_path = _get_csv_path_for_team_details(team_id, data_set_name)
                    _save_dataframe_to_csv(df, csv_path)

                # Process for JSON response
                processed_data = _process_dataframe(df, single_row=False)
                result_dict["data_sets"][data_set_name] = processed_data
            else:
                # Include empty datasets in the response
                result_dict["data_sets"][data_set_name] = []

                # Save empty CSV file for consistency
                if return_dataframe:
                    csv_path = _get_csv_path_for_team_details(team_id, data_set_name)
                    empty_df = pd.DataFrame()
                    _save_dataframe_to_csv(empty_df, csv_path)

        final_json_response = format_response(result_dict)
        if return_dataframe:
            return final_json_response, dataframes
        return final_json_response

    except Exception as e:
        logger.error(f"Unexpected error in fetch_team_details_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_team_details(
    team_id: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get team details data.

    Args:
        team_id: Team ID (required)
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False:
            str: JSON string with team details data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_team_details_logic(
        team_id=team_id,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Test basic functionality
    print("Testing TeamDetails endpoint...")

    # Test 1: Basic fetch for Cleveland Cavaliers
    json_response = get_team_details("1610612739")
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")

    # Test 2: With DataFrame output
    json_response, dataframes = get_team_details("1610612739", return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")

    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")

    print("TeamDetails endpoint test completed.")

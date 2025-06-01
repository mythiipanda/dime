"""
Handles fetching and processing team estimated metrics data
from the TeamEstimatedMetrics endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The TeamEstimatedMetrics endpoint provides team estimated metrics data (1 DataFrame):
- Team Info: TEAM_NAME, TEAM_ID, GP, W, L, W_PCT, MIN (7 columns)
- Estimated Metrics: E_OFF_RATING, E_DEF_RATING, E_NET_RATING, E_PACE, E_AST_RATIO, E_OREB_PCT, E_DREB_PCT, E_REB_PCT, E_TM_TOV_PCT (9 columns)
- Rankings: All metrics have corresponding rank columns (14 columns)
- Rich metrics data: Team estimated metrics with advanced analytics (30 columns total)
- Perfect for team analytics, advanced metrics evaluation, and team comparison
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import teamestimatedmetrics
from nba_api.stats.library.parameters import SeasonType
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
TEAM_ESTIMATED_METRICS_CACHE_SIZE = 64

# Valid parameter sets
VALID_LEAGUE_IDS: Set[str] = {"00", "10", ""}  # NBA, WNBA, or empty
VALID_SEASON_TYPES: Set[str] = {"Regular Season", "Playoffs", "Pre Season", ""}

# --- Cache Directory Setup ---
TEAM_ESTIMATED_METRICS_CSV_DIR = get_cache_dir("team_estimated_metrics")

# Ensure cache directories exist
os.makedirs(TEAM_ESTIMATED_METRICS_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_team_estimated_metrics(
    league_id: str = "",
    season: str = CURRENT_NBA_SEASON,
    season_type: str = "",
    data_set_name: str = "TeamEstimatedMetrics"
) -> str:
    """
    Generates a file path for saving team estimated metrics DataFrame.

    Args:
        league_id: League ID (default: "")
        season: Season (default: current season)
        season_type: Season type (default: "")
        data_set_name: Name of the data set

    Returns:
        Path to the CSV file
    """
    # Create a filename based on the parameters
    filename_parts = [
        f"team_estimated_metrics",
        f"league{league_id if league_id else 'all'}",
        f"season{season.replace('-', '_')}",
        f"type{season_type.replace(' ', '_') if season_type else 'all'}",
        data_set_name
    ]

    filename = "_".join(filename_parts) + ".csv"

    return get_cache_file_path(filename, "team_estimated_metrics")

# --- Parameter Validation ---
def _validate_team_estimated_metrics_params(
    league_id: str,
    season: str,
    season_type: str
) -> Optional[str]:
    """Validates parameters for fetch_team_estimated_metrics_logic."""
    if league_id not in VALID_LEAGUE_IDS:
        return f"Invalid league_id: {league_id}. Valid options: {', '.join(VALID_LEAGUE_IDS)}"
    if not _validate_season_format(season):
        return f"Invalid season format: {season}. Expected format: YYYY-YY"
    if season_type not in VALID_SEASON_TYPES:
        return f"Invalid season_type: {season_type}. Valid options: {', '.join(VALID_SEASON_TYPES)}"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=TEAM_ESTIMATED_METRICS_CACHE_SIZE)
def fetch_team_estimated_metrics_logic(
    league_id: str = "",
    season: str = CURRENT_NBA_SEASON,
    season_type: str = "",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches team estimated metrics data using the TeamEstimatedMetrics endpoint.

    Provides DataFrame output capabilities and CSV caching.

    Args:
        league_id: League ID (default: "")
        season: Season (default: current season)
        season_type: Season type (default: "")
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False:
            str: JSON string with team estimated metrics data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(
        f"Executing fetch_team_estimated_metrics_logic for League: {league_id}, Season: {season}, "
        f"Type: {season_type}, return_dataframe={return_dataframe}"
    )

    # Validate parameters
    validation_error = _validate_team_estimated_metrics_params(league_id, season, season_type)
    if validation_error:
        logger.warning(f"Parameter validation failed for team estimated metrics: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response

    # Check for cached CSV file
    csv_path = _get_csv_path_for_team_estimated_metrics(league_id, season, season_type, "TeamEstimatedMetrics")
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
                logger.info(f"Loading team estimated metrics from CSV: {csv_path}")
                # Read CSV with appropriate data types
                df = pd.read_csv(csv_path, encoding='utf-8')

                # Process for JSON response
                result_dict = {
                    "parameters": {
                        "league_id": league_id,
                        "season": season,
                        "season_type": season_type
                    },
                    "data_sets": {}
                }

                # Store the DataFrame
                dataframes["TeamEstimatedMetrics"] = df
                result_dict["data_sets"]["TeamEstimatedMetrics"] = _process_dataframe(df, single_row=False)

                if return_dataframe:
                    return format_response(result_dict), dataframes
                return format_response(result_dict)

        except Exception as e:
            logger.error(f"Error loading CSV: {e}", exc_info=True)
            # If there's an error loading the CSV, fetch from the API

    try:
        # Prepare API parameters (only include non-empty parameters)
        api_params = {
            "season": season
        }

        if league_id:
            api_params["league_id"] = league_id
        if season_type:
            api_params["season_type"] = season_type

        logger.debug(f"Calling TeamEstimatedMetrics with parameters: {api_params}")
        team_metrics_endpoint = teamestimatedmetrics.TeamEstimatedMetrics(**api_params)

        # Get data frames
        list_of_dataframes = team_metrics_endpoint.get_data_frames()

        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": {
                "league_id": league_id,
                "season": season,
                "season_type": season_type
            },
            "data_sets": {}
        }

        # Create a combined DataFrame for CSV storage
        combined_df = pd.DataFrame()

        # Process each data frame
        for idx, df in enumerate(list_of_dataframes):
            # Use a generic name for the data set
            data_set_name = f"TeamEstimatedMetrics_{idx}" if idx > 0 else "TeamEstimatedMetrics"

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
        logger.error(f"Unexpected error in fetch_team_estimated_metrics_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_team_estimated_metrics(
    league_id: str = "",
    season: str = CURRENT_NBA_SEASON,
    season_type: str = "",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get team estimated metrics data.

    Args:
        league_id: League ID (default: "")
        season: Season (default: current season)
        season_type: Season type (default: "")
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False:
            str: JSON string with team estimated metrics data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_team_estimated_metrics_logic(
        league_id=league_id,
        season=season,
        season_type=season_type,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Test basic functionality
    print("Testing TeamEstimatedMetrics endpoint...")

    # Test 1: Basic fetch
    json_response = get_team_estimated_metrics()
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")

    # Test 2: With DataFrame output
    json_response, dataframes = get_team_estimated_metrics(return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")

    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")

    print("TeamEstimatedMetrics endpoint test completed.")

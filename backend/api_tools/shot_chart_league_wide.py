"""
Handles fetching and processing shot chart league wide data
from the ShotChartLeagueWide endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The ShotChartLeagueWide endpoint provides league-wide shot chart data (1 DataFrame):
- Zone Info: GRID_TYPE, SHOT_ZONE_BASIC, SHOT_ZONE_AREA, SHOT_ZONE_RANGE (4 columns)
- Shooting Stats: FGA, FGM, FG_PCT (3 columns)
- Rich shot data: League averages by shot zones with detailed shooting statistics (7 columns total)
- Perfect for shot chart analysis, zone-based shooting evaluation, and league-wide shooting trends
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import shotchartleaguewide
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
SHOT_CHART_LEAGUE_WIDE_CACHE_SIZE = 64

# Valid parameter sets
VALID_LEAGUE_IDS: Set[str] = {"00", "10"}  # NBA, WNBA

# --- Cache Directory Setup ---
SHOT_CHART_LEAGUE_WIDE_CSV_DIR = get_cache_dir("shot_chart_league_wide")

# Ensure cache directories exist
os.makedirs(SHOT_CHART_LEAGUE_WIDE_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_shot_chart_league_wide(
    league_id: str = "00",
    season: str = CURRENT_NBA_SEASON,
    data_set_name: str = "ShotChartLeagueWide"
) -> str:
    """
    Generates a file path for saving shot chart league wide DataFrame.
    
    Args:
        league_id: League ID (default: "00" for NBA)
        season: Season (default: current season)
        data_set_name: Name of the data set
        
    Returns:
        Path to the CSV file
    """
    # Create a filename based on the parameters
    filename_parts = [
        f"shot_chart_league_wide",
        f"league{league_id}",
        f"season{season.replace('-', '_')}",
        data_set_name
    ]
    
    filename = "_".join(filename_parts) + ".csv"
    
    return get_cache_file_path(filename, "shot_chart_league_wide")

# --- Parameter Validation ---
def _validate_shot_chart_league_wide_params(
    league_id: str,
    season: str
) -> Optional[str]:
    """Validates parameters for fetch_shot_chart_league_wide_logic."""
    if league_id not in VALID_LEAGUE_IDS:
        return f"Invalid league_id: {league_id}. Valid options: {', '.join(VALID_LEAGUE_IDS)}"
    if not _validate_season_format(season):
        return f"Invalid season format: {season}. Expected format: YYYY-YY"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=SHOT_CHART_LEAGUE_WIDE_CACHE_SIZE)
def fetch_shot_chart_league_wide_logic(
    league_id: str = "00",
    season: str = CURRENT_NBA_SEASON,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches shot chart league wide data using the ShotChartLeagueWide endpoint.
    
    Provides DataFrame output capabilities and CSV caching.
    
    Args:
        league_id: League ID (default: "00" for NBA)
        season: Season (default: current season)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with shot chart league wide data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(
        f"Executing fetch_shot_chart_league_wide_logic for League: {league_id}, Season: {season}, "
        f"return_dataframe={return_dataframe}"
    )
    
    # Validate parameters
    validation_error = _validate_shot_chart_league_wide_params(league_id, season)
    if validation_error:
        logger.warning(f"Parameter validation failed for shot chart league wide: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response
    
    # Check for cached CSV file
    csv_path = _get_csv_path_for_shot_chart_league_wide(league_id, season, "ShotChartLeagueWide")
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
                logger.info(f"Loading shot chart league wide from CSV: {csv_path}")
                # Read CSV with appropriate data types
                df = pd.read_csv(csv_path, encoding='utf-8')
                
                # Process for JSON response
                result_dict = {
                    "parameters": {
                        "league_id": league_id,
                        "season": season
                    },
                    "data_sets": {}
                }
                
                # Store the DataFrame
                dataframes["ShotChartLeagueWide"] = df
                result_dict["data_sets"]["ShotChartLeagueWide"] = _process_dataframe(df, single_row=False)
                
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
            "season": season
        }
        
        logger.debug(f"Calling ShotChartLeagueWide with parameters: {api_params}")
        shot_chart_endpoint = shotchartleaguewide.ShotChartLeagueWide(**api_params)
        
        # Get data frames
        list_of_dataframes = shot_chart_endpoint.get_data_frames()
        
        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": {
                "league_id": league_id,
                "season": season
            },
            "data_sets": {}
        }
        
        # Create a combined DataFrame for CSV storage
        combined_df = pd.DataFrame()
        
        # Process each data frame
        for idx, df in enumerate(list_of_dataframes):
            # Use a generic name for the data set
            data_set_name = f"ShotChartLeagueWide_{idx}" if idx > 0 else "ShotChartLeagueWide"
            
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
        logger.error(f"Unexpected error in fetch_shot_chart_league_wide_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_shot_chart_league_wide(
    league_id: str = "00",
    season: str = CURRENT_NBA_SEASON,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get shot chart league wide data.
    
    Args:
        league_id: League ID (default: "00" for NBA)
        season: Season (default: current season)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with shot chart league wide data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_shot_chart_league_wide_logic(
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
    print("Testing ShotChartLeagueWide endpoint...")
    
    # Test 1: Basic fetch
    json_response = get_shot_chart_league_wide()
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")
    
    # Test 2: With DataFrame output
    json_response, dataframes = get_shot_chart_league_wide(return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")
    
    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")
    
    print("ShotChartLeagueWide endpoint test completed.")

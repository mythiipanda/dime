"""
Handles fetching and processing assist leaders statistics
from the AssistLeaders endpoint.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import assistleaders
from nba_api.stats.library.parameters import SeasonTypeAllStar
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

def _validate_season_format(season):
    """Validate season format (YYYY-YY)."""
    if not season:
        return False

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
CURRENT_NBA_SEASON = "2023-24"

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
ASSIST_LEADERS_CACHE_SIZE = 32

# Valid parameter sets
VALID_LEAGUE_IDS: Set[str] = {"00", "10", "20"}  # NBA, WNBA, G-League
VALID_SEASON_TYPES: Set[str] = {
    SeasonTypeAllStar.regular,
    SeasonTypeAllStar.playoffs,
    SeasonTypeAllStar.preseason,
    SeasonTypeAllStar.all_star
}
VALID_PER_MODES: Set[str] = {"Totals", "PerGame"}
VALID_PLAYER_OR_TEAM: Set[str] = {"Team", "Player"}

# --- Cache Directory Setup ---
ASSIST_LEADERS_CSV_DIR = get_cache_dir("assist_leaders")

# Ensure cache directories exist
os.makedirs(ASSIST_LEADERS_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_assist_leaders(
    league_id: str = "00",
    season: str = CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = "Totals",
    player_or_team: str = "Team"
) -> str:
    """
    Generates a file path for saving assist leaders DataFrame.

    Args:
        league_id: League ID (default: "00" for NBA)
        season: Season in YYYY-YY format
        season_type: Season type (default: "Regular Season")
        per_mode: Per mode (default: "Totals")
        player_or_team: Player or Team (default: "Team")

    Returns:
        Path to the CSV file
    """
    # Create a filename based on the parameters
    safe_season_type = season_type.replace(" ", "_")
    filename = f"assist_leaders_league{league_id}_season{season}_type{safe_season_type}_mode{per_mode}_{player_or_team.lower()}.csv"

    return get_cache_file_path(filename, "assist_leaders")

# --- Parameter Validation ---
def _validate_assist_leaders_params(
    league_id: str,
    season: str,
    season_type: str,
    per_mode: str,
    player_or_team: str
) -> Optional[str]:
    """Validates parameters for fetch_assist_leaders_logic."""
    if league_id not in VALID_LEAGUE_IDS:
        return f"Invalid league_id: {league_id}. Valid options: {', '.join(VALID_LEAGUE_IDS)}"
    if not season or not _validate_season_format(season):
        return f"Invalid season format: {season}. Expected format: YYYY-YY"
    if season_type not in VALID_SEASON_TYPES:
        return f"Invalid season_type: {season_type}. Valid options: {', '.join(VALID_SEASON_TYPES)}"
    if per_mode not in VALID_PER_MODES:
        return f"Invalid per_mode: {per_mode}. Valid options: {', '.join(VALID_PER_MODES)}"
    if player_or_team not in VALID_PLAYER_OR_TEAM:
        return f"Invalid player_or_team: {player_or_team}. Valid options: {', '.join(VALID_PLAYER_OR_TEAM)}"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=ASSIST_LEADERS_CACHE_SIZE)
def fetch_assist_leaders_logic(
    league_id: str = "00",
    season: str = CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = "Totals",
    player_or_team: str = "Team",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches assist leaders statistics using the AssistLeaders endpoint.

    Provides DataFrame output capabilities and CSV caching.

    Args:
        league_id: League ID (default: "00" for NBA)
        season: Season in YYYY-YY format (default: current NBA season)
        season_type: Type of season (default: "Regular Season")
        per_mode: Per mode (default: "Totals")
        player_or_team: Player or Team (default: "Team")
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False:
            str: JSON string with assist leaders data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(
        f"Executing fetch_assist_leaders_logic for League: {league_id}, Season: {season}, "
        f"Season Type: {season_type}, Per Mode: {per_mode}, Player/Team: {player_or_team}, return_dataframe={return_dataframe}"
    )

    # Validate parameters
    validation_error = _validate_assist_leaders_params(league_id, season, season_type, per_mode, player_or_team)
    if validation_error:
        logger.warning(f"Parameter validation failed for assist leaders: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response

    # Check for cached CSV file
    csv_path = _get_csv_path_for_assist_leaders(league_id, season, season_type, per_mode, player_or_team)
    dataframes = {}

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
                logger.info(f"Loading assist leaders from CSV: {csv_path}")
                # Read CSV with appropriate data types
                df = pd.read_csv(csv_path, encoding='utf-8')

                # Process for JSON response
                result_dict = {
                    "parameters": {
                        "league_id": league_id,
                        "season": season,
                        "season_type_playoffs": season_type,
                        "per_mode_simple": per_mode,
                        "player_or_team": player_or_team
                    },
                    "data_sets": {}
                }

                # Store the DataFrame
                dataframes["AssistLeaders"] = df
                result_dict["data_sets"]["AssistLeaders"] = _process_dataframe(df, single_row=False)

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
            "season": season,
            "season_type_playoffs": season_type,
            "per_mode_simple": per_mode,
            "player_or_team": player_or_team
        }

        logger.debug(f"Calling AssistLeaders with parameters: {api_params}")
        assist_leaders_endpoint = assistleaders.AssistLeaders(**api_params)

        # Get data frames
        list_of_dataframes = assist_leaders_endpoint.get_data_frames()

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
                data_set_name = f"AssistLeaders_{idx}" if idx > 0 else "AssistLeaders"

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
        logger.error(f"Unexpected error in fetch_assist_leaders_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_assist_leaders(
    league_id: str = "00",
    season: str = CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = "Totals",
    player_or_team: str = "Team",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get assist leaders data.

    Args:
        league_id: League ID (default: "00" for NBA)
        season: Season in YYYY-YY format (default: current NBA season)
        season_type: Type of season (default: "Regular Season")
        per_mode: Per mode (default: "Totals")
        player_or_team: Player or Team (default: "Team")
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False:
            str: JSON string with assist leaders data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_assist_leaders_logic(
        league_id=league_id,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        player_or_team=player_or_team,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Test basic functionality
    print("Testing AssistLeaders endpoint...")

    # Test 1: Basic fetch
    json_response = get_assist_leaders()
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")

    # Test 2: With DataFrame output
    json_response, dataframes = get_assist_leaders(return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")

    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")

    print("AssistLeaders endpoint test completed.")

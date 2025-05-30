"""
Handles fetching and processing player game streak finder data
from the PlayerGameStreakFinder endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The PlayerGameStreakFinder endpoint provides game streak data (1 DataFrame):
- Player Info: PLAYER_NAME_LAST_FIRST, PLAYER_ID (2 columns)
- Streak Info: GAMESTREAK, STARTDATE, ENDDATE, ACTIVESTREAK (4 columns)
- Career Info: NUMSEASONS, LASTSEASON, FIRSTSEASON (3 columns)
- Rich streak data: Player game streaks with detailed information (9 columns total)
- Perfect for streak analysis, durability tracking, and historical performance evaluation
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import playergamestreakfinder
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
        return True  # Empty season is allowed
    
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

def _validate_player_id(player_id):
    """Validate player ID format."""
    if not player_id:
        return True  # Empty player ID is allowed
    
    # Check if it's a string or integer
    if isinstance(player_id, (str, int)):
        # If string, check if it's a valid number
        if isinstance(player_id, str):
            try:
                int(player_id)
                return True
            except ValueError:
                return False
        return True
    
    return False

# Default current NBA season
CURRENT_NBA_SEASON = "2024-25"

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
PLAYER_GAME_STREAK_FINDER_CACHE_SIZE = 256

# Valid parameter sets (focusing on most useful parameters)
VALID_LEAGUE_IDS: Set[str] = {"00", "10", ""}  # NBA, WNBA, or empty
VALID_SEASON_TYPES: Set[str] = {"Regular Season", "Playoffs", ""}
VALID_ACTIVE_STREAKS: Set[str] = {"Y", "N", ""}
VALID_LOCATIONS: Set[str] = {"Home", "Road", ""}
VALID_OUTCOMES: Set[str] = {"W", "L", ""}

# --- Cache Directory Setup ---
PLAYER_GAME_STREAK_FINDER_CSV_DIR = get_cache_dir("player_game_streak_finder")

# Ensure cache directories exist
os.makedirs(PLAYER_GAME_STREAK_FINDER_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_player_game_streak_finder(
    player_id_nullable: str = "",
    season_nullable: str = "",
    season_type_nullable: str = "",
    league_id_nullable: str = "",
    active_streaks_only_nullable: str = "",
    location_nullable: str = "",
    outcome_nullable: str = "",
    gt_pts_nullable: str = "",
    data_set_name: str = "PlayerGameStreakFinder"
) -> str:
    """
    Generates a file path for saving player game streak finder DataFrame.
    
    Args:
        player_id_nullable: Player ID (default: "")
        season_nullable: Season (default: "")
        season_type_nullable: Season type (default: "")
        league_id_nullable: League ID (default: "")
        active_streaks_only_nullable: Active streaks only (default: "")
        location_nullable: Location (default: "")
        outcome_nullable: Outcome (default: "")
        gt_pts_nullable: Greater than points (default: "")
        data_set_name: Name of the data set
        
    Returns:
        Path to the CSV file
    """
    # Create a filename based on the parameters
    filename_parts = [
        f"player_game_streak_finder",
        f"player{player_id_nullable if player_id_nullable else 'all'}",
        f"season{season_nullable.replace('-', '_') if season_nullable else 'all'}",
        f"type{season_type_nullable.replace(' ', '_') if season_type_nullable else 'all'}",
        f"league{league_id_nullable if league_id_nullable else 'all'}",
        f"active{active_streaks_only_nullable if active_streaks_only_nullable else 'all'}",
        f"location{location_nullable if location_nullable else 'all'}",
        f"outcome{outcome_nullable if outcome_nullable else 'all'}",
        f"pts{gt_pts_nullable if gt_pts_nullable else 'all'}",
        data_set_name
    ]
    
    filename = "_".join(filename_parts) + ".csv"
    
    return get_cache_file_path(filename, "player_game_streak_finder")

# --- Parameter Validation ---
def _validate_player_game_streak_finder_params(
    player_id_nullable: str,
    season_nullable: str,
    season_type_nullable: str,
    league_id_nullable: str,
    active_streaks_only_nullable: str,
    location_nullable: str,
    outcome_nullable: str,
    gt_pts_nullable: str
) -> Optional[str]:
    """Validates parameters for fetch_player_game_streak_finder_logic."""
    if not _validate_player_id(player_id_nullable):
        return f"Invalid player_id_nullable: {player_id_nullable}. Must be a valid player ID or empty"
    if not _validate_season_format(season_nullable):
        return f"Invalid season_nullable format: {season_nullable}. Expected format: YYYY-YY or empty"
    if season_type_nullable not in VALID_SEASON_TYPES:
        return f"Invalid season_type_nullable: {season_type_nullable}. Valid options: {', '.join(VALID_SEASON_TYPES)}"
    if league_id_nullable not in VALID_LEAGUE_IDS:
        return f"Invalid league_id_nullable: {league_id_nullable}. Valid options: {', '.join(VALID_LEAGUE_IDS)}"
    if active_streaks_only_nullable not in VALID_ACTIVE_STREAKS:
        return f"Invalid active_streaks_only_nullable: {active_streaks_only_nullable}. Valid options: {', '.join(VALID_ACTIVE_STREAKS)}"
    if location_nullable not in VALID_LOCATIONS:
        return f"Invalid location_nullable: {location_nullable}. Valid options: {', '.join(VALID_LOCATIONS)}"
    if outcome_nullable not in VALID_OUTCOMES:
        return f"Invalid outcome_nullable: {outcome_nullable}. Valid options: {', '.join(VALID_OUTCOMES)}"
    if gt_pts_nullable and gt_pts_nullable != "":
        try:
            int(gt_pts_nullable)
        except ValueError:
            return f"Invalid gt_pts_nullable: {gt_pts_nullable}. Must be a number or empty"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=PLAYER_GAME_STREAK_FINDER_CACHE_SIZE)
def fetch_player_game_streak_finder_logic(
    player_id_nullable: str = "",
    season_nullable: str = "",
    season_type_nullable: str = "",
    league_id_nullable: str = "",
    active_streaks_only_nullable: str = "",
    location_nullable: str = "",
    outcome_nullable: str = "",
    gt_pts_nullable: str = "",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player game streak finder data using the PlayerGameStreakFinder endpoint.
    
    Provides DataFrame output capabilities and CSV caching.
    
    Args:
        player_id_nullable: Player ID (default: "")
        season_nullable: Season (default: "")
        season_type_nullable: Season type (default: "")
        league_id_nullable: League ID (default: "")
        active_streaks_only_nullable: Active streaks only (default: "")
        location_nullable: Location (default: "")
        outcome_nullable: Outcome (default: "")
        gt_pts_nullable: Greater than points (default: "")
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with player game streak finder data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(
        f"Executing fetch_player_game_streak_finder_logic for Player: {player_id_nullable}, Season: {season_nullable}, "
        f"Type: {season_type_nullable}, League: {league_id_nullable}, Active: {active_streaks_only_nullable}, "
        f"Location: {location_nullable}, Outcome: {outcome_nullable}, Points: {gt_pts_nullable}, "
        f"return_dataframe={return_dataframe}"
    )
    
    # Validate parameters
    validation_error = _validate_player_game_streak_finder_params(
        player_id_nullable, season_nullable, season_type_nullable, league_id_nullable,
        active_streaks_only_nullable, location_nullable, outcome_nullable, gt_pts_nullable
    )
    if validation_error:
        logger.warning(f"Parameter validation failed for player game streak finder: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response
    
    # Check for cached CSV file
    csv_path = _get_csv_path_for_player_game_streak_finder(
        player_id_nullable, season_nullable, season_type_nullable, league_id_nullable,
        active_streaks_only_nullable, location_nullable, outcome_nullable, gt_pts_nullable, "PlayerGameStreakFinder"
    )
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
                logger.info(f"Loading player game streak finder from CSV: {csv_path}")
                # Read CSV with appropriate data types
                df = pd.read_csv(csv_path, encoding='utf-8')
                
                # Process for JSON response
                result_dict = {
                    "parameters": {
                        "player_id_nullable": player_id_nullable,
                        "season_nullable": season_nullable,
                        "season_type_nullable": season_type_nullable,
                        "league_id_nullable": league_id_nullable,
                        "active_streaks_only_nullable": active_streaks_only_nullable,
                        "location_nullable": location_nullable,
                        "outcome_nullable": outcome_nullable,
                        "gt_pts_nullable": gt_pts_nullable
                    },
                    "data_sets": {}
                }
                
                # Store the DataFrame
                dataframes["PlayerGameStreakFinder"] = df
                result_dict["data_sets"]["PlayerGameStreakFinder"] = _process_dataframe(df, single_row=False)
                
                if return_dataframe:
                    return format_response(result_dict), dataframes
                return format_response(result_dict)
            
        except Exception as e:
            logger.error(f"Error loading CSV: {e}", exc_info=True)
            # If there's an error loading the CSV, fetch from the API
    
    try:
        # Prepare API parameters (only include non-empty parameters)
        api_params = {}
        
        if player_id_nullable:
            api_params["player_id_nullable"] = player_id_nullable
        if season_nullable:
            api_params["season_nullable"] = season_nullable
        if season_type_nullable:
            api_params["season_type_nullable"] = season_type_nullable
        if league_id_nullable:
            api_params["league_id_nullable"] = league_id_nullable
        if active_streaks_only_nullable:
            api_params["active_streaks_only_nullable"] = active_streaks_only_nullable
        if location_nullable:
            api_params["location_nullable"] = location_nullable
        if outcome_nullable:
            api_params["outcome_nullable"] = outcome_nullable
        if gt_pts_nullable:
            api_params["gt_pts_nullable"] = gt_pts_nullable
        
        logger.debug(f"Calling PlayerGameStreakFinder with parameters: {api_params}")
        streak_finder_endpoint = playergamestreakfinder.PlayerGameStreakFinder(**api_params)
        
        # Get data frames
        list_of_dataframes = streak_finder_endpoint.get_data_frames()
        
        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": {
                "player_id_nullable": player_id_nullable,
                "season_nullable": season_nullable,
                "season_type_nullable": season_type_nullable,
                "league_id_nullable": league_id_nullable,
                "active_streaks_only_nullable": active_streaks_only_nullable,
                "location_nullable": location_nullable,
                "outcome_nullable": outcome_nullable,
                "gt_pts_nullable": gt_pts_nullable
            },
            "data_sets": {}
        }
        
        # Create a combined DataFrame for CSV storage
        combined_df = pd.DataFrame()
        
        # Process each data frame
        for idx, df in enumerate(list_of_dataframes):
            # Use a generic name for the data set
            data_set_name = f"PlayerGameStreakFinder_{idx}" if idx > 0 else "PlayerGameStreakFinder"
            
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
        logger.error(f"Unexpected error in fetch_player_game_streak_finder_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_player_game_streak_finder(
    player_id_nullable: str = "",
    season_nullable: str = "",
    season_type_nullable: str = "",
    league_id_nullable: str = "",
    active_streaks_only_nullable: str = "",
    location_nullable: str = "",
    outcome_nullable: str = "",
    gt_pts_nullable: str = "",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get player game streak finder data.
    
    Args:
        player_id_nullable: Player ID (default: "")
        season_nullable: Season (default: "")
        season_type_nullable: Season type (default: "")
        league_id_nullable: League ID (default: "")
        active_streaks_only_nullable: Active streaks only (default: "")
        location_nullable: Location (default: "")
        outcome_nullable: Outcome (default: "")
        gt_pts_nullable: Greater than points (default: "")
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with player game streak finder data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_player_game_streak_finder_logic(
        player_id_nullable=player_id_nullable,
        season_nullable=season_nullable,
        season_type_nullable=season_type_nullable,
        league_id_nullable=league_id_nullable,
        active_streaks_only_nullable=active_streaks_only_nullable,
        location_nullable=location_nullable,
        outcome_nullable=outcome_nullable,
        gt_pts_nullable=gt_pts_nullable,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Test basic functionality
    print("Testing PlayerGameStreakFinder endpoint...")
    
    # Test 1: Basic fetch (all players)
    json_response = get_player_game_streak_finder()
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")
    
    # Test 2: Specific player with DataFrame output
    json_response, dataframes = get_player_game_streak_finder(player_id_nullable="2544", return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")
    
    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")
    
    print("PlayerGameStreakFinder endpoint test completed.")

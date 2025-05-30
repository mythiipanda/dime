"""
Handles fetching and processing player fantasy profile bar graph data
from the PlayerFantasyProfileBarGraph endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The PlayerFantasyProfileBarGraph endpoint provides fantasy bar graph data (2 DataFrames):
- Player Info: PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM_ABBREVIATION (4 columns)
- Fantasy Metrics: FAN_DUEL_PTS, NBA_FANTASY_PTS (2 columns)
- Core Stats: PTS, REB, AST (3 columns)
- Shooting: FG3M, FT_PCT, FG_PCT (3 columns)
- Defense: STL, BLK (2 columns)
- Turnovers: TOV (1 column)
- Rich fantasy data: Per-game fantasy statistics optimized for bar graph visualization (15 columns total)
- Perfect for fantasy bar graph visualization, player comparison charts, and performance dashboards
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import playerfantasyprofilebargraph
from nba_api.stats.library.parameters import SeasonTypeAllStar
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

def _validate_player_id(player_id):
    """Validate player ID format."""
    if not player_id:
        return False
    
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
PLAYER_FANTASY_PROFILE_BAR_GRAPH_CACHE_SIZE = 256

# Valid parameter sets
VALID_LEAGUE_IDS: Set[str] = {"00", "10", ""}  # NBA, WNBA, or empty
VALID_SEASON_TYPES: Set[str] = {SeasonTypeAllStar.regular, SeasonTypeAllStar.playoffs, SeasonTypeAllStar.all_star, ""}

# --- Cache Directory Setup ---
PLAYER_FANTASY_PROFILE_BAR_GRAPH_CSV_DIR = get_cache_dir("player_fantasy_profile_bar_graph")

# Ensure cache directories exist
os.makedirs(PLAYER_FANTASY_PROFILE_BAR_GRAPH_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_player_fantasy_profile_bar_graph(
    player_id: str,
    season: str = CURRENT_NBA_SEASON,
    league_id_nullable: str = "",
    season_type_all_star_nullable: str = "",
    data_set_name: str = "PlayerFantasyProfileBarGraph"
) -> str:
    """
    Generates a file path for saving player fantasy profile bar graph DataFrame.
    
    Args:
        player_id: Player ID (required)
        season: Season (default: current season)
        league_id_nullable: League ID (default: "")
        season_type_all_star_nullable: Season type (default: "")
        data_set_name: Name of the data set
        
    Returns:
        Path to the CSV file
    """
    # Create a filename based on the parameters
    filename_parts = [
        f"player_fantasy_profile_bar_graph",
        f"player{player_id}",
        f"season{season.replace('-', '_')}",
        f"league{league_id_nullable if league_id_nullable else 'all'}",
        f"type{season_type_all_star_nullable.replace(' ', '_') if season_type_all_star_nullable else 'all'}",
        data_set_name
    ]
    
    filename = "_".join(filename_parts) + ".csv"
    
    return get_cache_file_path(filename, "player_fantasy_profile_bar_graph")

# --- Parameter Validation ---
def _validate_player_fantasy_profile_bar_graph_params(
    player_id: str,
    season: str,
    league_id_nullable: str,
    season_type_all_star_nullable: str
) -> Optional[str]:
    """Validates parameters for fetch_player_fantasy_profile_bar_graph_logic."""
    if not _validate_player_id(player_id):
        return f"Invalid player_id: {player_id}. Must be a valid player ID"
    if not _validate_season_format(season):
        return f"Invalid season format: {season}. Expected format: YYYY-YY"
    if league_id_nullable not in VALID_LEAGUE_IDS:
        return f"Invalid league_id_nullable: {league_id_nullable}. Valid options: {', '.join(VALID_LEAGUE_IDS)}"
    if season_type_all_star_nullable not in VALID_SEASON_TYPES:
        return f"Invalid season_type_all_star_nullable: {season_type_all_star_nullable}. Valid options: {', '.join(VALID_SEASON_TYPES)}"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=PLAYER_FANTASY_PROFILE_BAR_GRAPH_CACHE_SIZE)
def fetch_player_fantasy_profile_bar_graph_logic(
    player_id: str,
    season: str = CURRENT_NBA_SEASON,
    league_id_nullable: str = "",
    season_type_all_star_nullable: str = "",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player fantasy profile bar graph data using the PlayerFantasyProfileBarGraph endpoint.
    
    Provides DataFrame output capabilities and CSV caching.
    
    Args:
        player_id: Player ID (required)
        season: Season (default: current season)
        league_id_nullable: League ID (default: "")
        season_type_all_star_nullable: Season type (default: "")
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with player fantasy profile bar graph data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(
        f"Executing fetch_player_fantasy_profile_bar_graph_logic for Player: {player_id}, Season: {season}, "
        f"League: {league_id_nullable}, Type: {season_type_all_star_nullable}, "
        f"return_dataframe={return_dataframe}"
    )
    
    # Validate parameters
    validation_error = _validate_player_fantasy_profile_bar_graph_params(
        player_id, season, league_id_nullable, season_type_all_star_nullable
    )
    if validation_error:
        logger.warning(f"Parameter validation failed for player fantasy profile bar graph: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response
    
    # Check for cached CSV files
    dataframes = {}
    
    # Try to load from cache first
    if return_dataframe:
        # Check for all possible data sets
        data_set_names = ["SeasonStats", "RecentStats"]
        all_cached = True
        
        for data_set_name in data_set_names:
            csv_path = _get_csv_path_for_player_fantasy_profile_bar_graph(
                player_id, season, league_id_nullable, season_type_all_star_nullable, data_set_name
            )
            if os.path.exists(csv_path):
                try:
                    # Check if the file is empty or too small
                    file_size = os.path.getsize(csv_path)
                    if file_size < 100:  # If file is too small, it's probably empty or corrupted
                        logger.warning(f"CSV file is too small ({file_size} bytes), fetching from API instead")
                        all_cached = False
                        break
                    else:
                        logger.info(f"Loading player fantasy profile bar graph from CSV: {csv_path}")
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
                    "player_id": player_id,
                    "season": season,
                    "league_id_nullable": league_id_nullable,
                    "season_type_all_star_nullable": season_type_all_star_nullable
                },
                "data_sets": {}
            }
            
            for data_set_name, df in dataframes.items():
                result_dict["data_sets"][data_set_name] = _process_dataframe(df, single_row=False)
            
            return format_response(result_dict), dataframes
    
    try:
        # Prepare API parameters
        api_params = {
            "player_id": player_id,
            "season": season
        }
        
        # Add optional parameters if they're not empty
        if league_id_nullable:
            api_params["league_id_nullable"] = league_id_nullable
        if season_type_all_star_nullable:
            api_params["season_type_all_star_nullable"] = season_type_all_star_nullable
        
        logger.debug(f"Calling PlayerFantasyProfileBarGraph with parameters: {api_params}")
        fantasy_bar_graph_endpoint = playerfantasyprofilebargraph.PlayerFantasyProfileBarGraph(**api_params)
        
        # Get data frames
        list_of_dataframes = fantasy_bar_graph_endpoint.get_data_frames()
        
        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": {
                "player_id": player_id,
                "season": season,
                "league_id_nullable": league_id_nullable,
                "season_type_all_star_nullable": season_type_all_star_nullable
            },
            "data_sets": {}
        }
        
        # Process each data frame
        data_set_names = ["SeasonStats", "RecentStats"]
        
        for idx, df in enumerate(list_of_dataframes):
            if not df.empty:
                # Use predefined names for the data sets
                data_set_name = data_set_names[idx] if idx < len(data_set_names) else f"PlayerFantasyProfileBarGraph_{idx}"
                
                # Store DataFrame if requested
                if return_dataframe:
                    dataframes[data_set_name] = df
                    
                    # Save DataFrame to CSV
                    csv_path = _get_csv_path_for_player_fantasy_profile_bar_graph(
                        player_id, season, league_id_nullable, season_type_all_star_nullable, data_set_name
                    )
                    _save_dataframe_to_csv(df, csv_path)
                
                # Process for JSON response
                processed_data = _process_dataframe(df, single_row=False)
                result_dict["data_sets"][data_set_name] = processed_data
        
        final_json_response = format_response(result_dict)
        if return_dataframe:
            return final_json_response, dataframes
        return final_json_response
        
    except Exception as e:
        logger.error(f"Unexpected error in fetch_player_fantasy_profile_bar_graph_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_player_fantasy_profile_bar_graph(
    player_id: str,
    season: str = CURRENT_NBA_SEASON,
    league_id_nullable: str = "",
    season_type_all_star_nullable: str = "",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get player fantasy profile bar graph data.
    
    Args:
        player_id: Player ID (required)
        season: Season (default: current season)
        league_id_nullable: League ID (default: "")
        season_type_all_star_nullable: Season type (default: "")
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with player fantasy profile bar graph data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_player_fantasy_profile_bar_graph_logic(
        player_id=player_id,
        season=season,
        league_id_nullable=league_id_nullable,
        season_type_all_star_nullable=season_type_all_star_nullable,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Test basic functionality
    print("Testing PlayerFantasyProfileBarGraph endpoint...")
    
    # Test 1: Basic fetch
    json_response = get_player_fantasy_profile_bar_graph(player_id="2544")  # LeBron James
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")
    
    # Test 2: With DataFrame output
    json_response, dataframes = get_player_fantasy_profile_bar_graph(player_id="2544", return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")
    
    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")
    
    print("PlayerFantasyProfileBarGraph endpoint test completed.")

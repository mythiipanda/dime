"""
Handles fetching and processing statistical leaders tiles data
from the LeadersTiles endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The LeadersTiles endpoint provides comprehensive statistical leaders data (4 DataFrames):
- Current Season Leaders: Top 5 teams in current season (5 columns)
- All-Time High Record: Historical best performance (1 team, 5 columns)
- Last Season Leaders: Top 5 teams from previous season (5 columns)
- All-Time Low Record: Historical worst performance (1 team, 5 columns)
- Rich leaders data: RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, [STAT]
- Perfect for visual leader boards, historical context, and statistical insights
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import leaderstiles
from nba_api.stats.library.parameters import SeasonTypePlayoffs, PlayerOrTeam, PlayerScope, GameScopeDetailed
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
CURRENT_NBA_SEASON = "2024-25"

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
LEADERS_TILES_CACHE_SIZE = 128

# Valid parameter sets
VALID_LEAGUE_IDS: Set[str] = {"00"}  # Only NBA supported
VALID_PLAYER_OR_TEAM: Set[str] = {PlayerOrTeam.team, PlayerOrTeam.player}
VALID_PLAYER_SCOPE: Set[str] = {PlayerScope.all_players, PlayerScope.rookies}
VALID_SEASON_TYPE: Set[str] = {SeasonTypePlayoffs.regular, SeasonTypePlayoffs.playoffs}
VALID_GAME_SCOPE: Set[str] = {GameScopeDetailed.season, GameScopeDetailed.last_10}
VALID_STATS: Set[str] = {"PTS", "REB", "AST", "STL", "BLK", "FG_PCT", "FG3_PCT", "FT_PCT"}

# --- Cache Directory Setup ---
LEADERS_TILES_CSV_DIR = get_cache_dir("leaders_tiles")

# Ensure cache directories exist
os.makedirs(LEADERS_TILES_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_leaders_tiles(
    game_scope_detailed: str = GameScopeDetailed.season,
    league_id: str = "00",
    player_or_team: str = PlayerOrTeam.team,
    player_scope: str = PlayerScope.all_players,
    season: str = CURRENT_NBA_SEASON,
    season_type_playoffs: str = SeasonTypePlayoffs.regular,
    stat: str = "PTS",
    data_set_name: str = "LeadersTiles"
) -> str:
    """
    Generates a file path for saving leaders tiles DataFrame.
    
    Args:
        game_scope_detailed: Game scope (default: Season)
        league_id: League ID (default: "00" for NBA)
        player_or_team: Player or Team (default: Team)
        player_scope: Player scope (default: All Players)
        season: Season in YYYY-YY format
        season_type_playoffs: Season type (default: Regular Season)
        stat: Statistical category (default: PTS)
        data_set_name: Name of the data set
        
    Returns:
        Path to the CSV file
    """
    # Create a filename based on the parameters
    filename_parts = [
        f"leaders_tiles_league{league_id}",
        f"season{season}",
        f"type{season_type_playoffs.replace(' ', '_')}",
        f"scope{player_or_team}",
        f"players{player_scope.replace(' ', '_')}",
        f"stat{stat}",
        f"game{game_scope_detailed.replace(' ', '_')}",
        data_set_name
    ]
    
    filename = "_".join(filename_parts) + ".csv"
    
    return get_cache_file_path(filename, "leaders_tiles")

# --- Parameter Validation ---
def _validate_leaders_tiles_params(
    game_scope_detailed: str,
    league_id: str,
    player_or_team: str,
    player_scope: str,
    season: str,
    season_type_playoffs: str,
    stat: str
) -> Optional[str]:
    """Validates parameters for fetch_leaders_tiles_logic."""
    if league_id not in VALID_LEAGUE_IDS:
        return f"Invalid league_id: {league_id}. Valid options: {', '.join(VALID_LEAGUE_IDS)}"
    if not season or not _validate_season_format(season):
        return f"Invalid season format: {season}. Expected format: YYYY-YY"
    if season_type_playoffs not in VALID_SEASON_TYPE:
        return f"Invalid season_type_playoffs: {season_type_playoffs}. Valid options: {', '.join(VALID_SEASON_TYPE)}"
    if player_or_team not in VALID_PLAYER_OR_TEAM:
        return f"Invalid player_or_team: {player_or_team}. Valid options: {', '.join(VALID_PLAYER_OR_TEAM)}"
    if player_scope not in VALID_PLAYER_SCOPE:
        return f"Invalid player_scope: {player_scope}. Valid options: {', '.join(VALID_PLAYER_SCOPE)}"
    if game_scope_detailed not in VALID_GAME_SCOPE:
        return f"Invalid game_scope_detailed: {game_scope_detailed}. Valid options: {', '.join(VALID_GAME_SCOPE)}"
    if stat not in VALID_STATS:
        return f"Invalid stat: {stat}. Valid options: {', '.join(VALID_STATS)}"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=LEADERS_TILES_CACHE_SIZE)
def fetch_leaders_tiles_logic(
    game_scope_detailed: str = GameScopeDetailed.season,
    league_id: str = "00",
    player_or_team: str = PlayerOrTeam.team,
    player_scope: str = PlayerScope.all_players,
    season: str = CURRENT_NBA_SEASON,
    season_type_playoffs: str = SeasonTypePlayoffs.regular,
    stat: str = "PTS",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches statistical leaders tiles data using the LeadersTiles endpoint.
    
    Provides DataFrame output capabilities and CSV caching.
    
    Args:
        game_scope_detailed: Game scope (default: Season)
        league_id: League ID (default: "00" for NBA)
        player_or_team: Player or Team (default: Team)
        player_scope: Player scope (default: All Players)
        season: Season in YYYY-YY format (default: current NBA season)
        season_type_playoffs: Season type (default: Regular Season)
        stat: Statistical category (default: PTS)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with leaders tiles data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(
        f"Executing fetch_leaders_tiles_logic for League: {league_id}, Season: {season}, "
        f"Type: {season_type_playoffs}, Scope: {player_or_team}, Players: {player_scope}, "
        f"Stat: {stat}, Game: {game_scope_detailed}, return_dataframe={return_dataframe}"
    )
    
    # Validate parameters
    validation_error = _validate_leaders_tiles_params(
        game_scope_detailed, league_id, player_or_team, player_scope, season, season_type_playoffs, stat
    )
    if validation_error:
        logger.warning(f"Parameter validation failed for leaders tiles: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response
    
    # Check for cached CSV files
    dataframes = {}
    
    # Try to load from cache first
    if return_dataframe:
        # Check for all possible data sets
        data_set_names = ["CurrentSeasonLeaders", "AllTimeHigh", "LastSeasonLeaders", "AllTimeLow"]
        all_cached = True
        
        for data_set_name in data_set_names:
            csv_path = _get_csv_path_for_leaders_tiles(
                game_scope_detailed, league_id, player_or_team, player_scope, 
                season, season_type_playoffs, stat, data_set_name
            )
            if os.path.exists(csv_path):
                try:
                    # Check if the file is empty or too small
                    file_size = os.path.getsize(csv_path)
                    if file_size < 50:  # If file is too small, it's probably empty or corrupted
                        logger.warning(f"CSV file is too small ({file_size} bytes), fetching from API instead")
                        all_cached = False
                        break
                    else:
                        logger.info(f"Loading leaders tiles from CSV: {csv_path}")
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
                    "game_scope_detailed": game_scope_detailed,
                    "league_id": league_id,
                    "player_or_team": player_or_team,
                    "player_scope": player_scope,
                    "season": season,
                    "season_type_playoffs": season_type_playoffs,
                    "stat": stat
                },
                "data_sets": {}
            }
            
            for data_set_name, df in dataframes.items():
                result_dict["data_sets"][data_set_name] = _process_dataframe(df, single_row=False)
            
            return format_response(result_dict), dataframes
    
    try:
        # Prepare API parameters
        api_params = {
            "game_scope_detailed": game_scope_detailed,
            "league_id": league_id,
            "player_or_team": player_or_team,
            "player_scope": player_scope,
            "season": season,
            "season_type_playoffs": season_type_playoffs,
            "stat": stat
        }
        
        logger.debug(f"Calling LeadersTiles with parameters: {api_params}")
        leaders_tiles_endpoint = leaderstiles.LeadersTiles(**api_params)
        
        # Get data frames
        list_of_dataframes = leaders_tiles_endpoint.get_data_frames()
        
        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": api_params,
            "data_sets": {}
        }
        
        # Process each data frame
        data_set_names = ["CurrentSeasonLeaders", "AllTimeHigh", "LastSeasonLeaders", "AllTimeLow"]
        
        for idx, df in enumerate(list_of_dataframes):
            if not df.empty:
                # Use predefined names for the data sets
                data_set_name = data_set_names[idx] if idx < len(data_set_names) else f"LeadersTiles_{idx}"
                
                # Store DataFrame if requested
                if return_dataframe:
                    dataframes[data_set_name] = df
                    
                    # Save DataFrame to CSV
                    csv_path = _get_csv_path_for_leaders_tiles(
                        game_scope_detailed, league_id, player_or_team, player_scope,
                        season, season_type_playoffs, stat, data_set_name
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
        logger.error(f"Unexpected error in fetch_leaders_tiles_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_leaders_tiles(
    game_scope_detailed: str = GameScopeDetailed.season,
    league_id: str = "00",
    player_or_team: str = PlayerOrTeam.team,
    player_scope: str = PlayerScope.all_players,
    season: str = CURRENT_NBA_SEASON,
    season_type_playoffs: str = SeasonTypePlayoffs.regular,
    stat: str = "PTS",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get statistical leaders tiles data.
    
    Args:
        game_scope_detailed: Game scope (default: Season)
        league_id: League ID (default: "00" for NBA)
        player_or_team: Player or Team (default: Team)
        player_scope: Player scope (default: All Players)
        season: Season in YYYY-YY format (default: current NBA season)
        season_type_playoffs: Season type (default: Regular Season)
        stat: Statistical category (default: PTS)
        return_dataframe: Whether to return DataFrames along with the JSON response
        
    Returns:
        If return_dataframe=False:
            str: JSON string with leaders tiles data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_leaders_tiles_logic(
        game_scope_detailed=game_scope_detailed,
        league_id=league_id,
        player_or_team=player_or_team,
        player_scope=player_scope,
        season=season,
        season_type_playoffs=season_type_playoffs,
        stat=stat,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Test basic functionality
    print("Testing LeadersTiles endpoint...")
    
    # Test 1: Basic fetch
    json_response = get_leaders_tiles()
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")
    
    # Test 2: With DataFrame output
    json_response, dataframes = get_leaders_tiles(return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")
    
    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")
    
    print("LeadersTiles endpoint test completed.")

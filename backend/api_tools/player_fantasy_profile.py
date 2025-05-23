"""
Handles fetching and processing player fantasy profile data
from the PlayerFantasyProfile endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The PlayerFantasyProfile endpoint provides comprehensive fantasy profile data (5 DataFrames):
- Group Info: GROUP_SET, GROUP_VALUE, SEASON_YEAR (where applicable) (2-3 columns)
- Team Performance: GP, W, L, W_PCT (4 columns)
- Minutes: MIN (1 column)
- Shooting: FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT (9 columns)
- Rebounding: OREB, DREB, REB (3 columns)
- Other Stats: AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS (9 columns)
- Fantasy Metrics: DD2, TD3, FAN_DUEL_PTS, NBA_FANTASY_PTS (4 columns)
- Rich fantasy data: Complete fantasy basketball statistics with multiple breakdowns (32-33 columns total)
- Perfect for fantasy basketball analysis, player evaluation, and performance tracking
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import playerfantasyprofile
from nba_api.stats.library.parameters import SeasonTypePlayoffs, MeasureTypeBase, PerMode36
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
PLAYER_FANTASY_PROFILE_CACHE_SIZE = 256

# Valid parameter sets
VALID_LEAGUE_IDS: Set[str] = {"00", "10", ""}  # NBA, WNBA, or empty
VALID_MEASURE_TYPES: Set[str] = {MeasureTypeBase.base}
VALID_PER_MODES: Set[str] = {PerMode36.totals, PerMode36.per_game}
VALID_SEASON_TYPES: Set[str] = {SeasonTypePlayoffs.regular, SeasonTypePlayoffs.playoffs}
VALID_YES_NO: Set[str] = {"Y", "N"}

# --- Cache Directory Setup ---
PLAYER_FANTASY_PROFILE_CSV_DIR = get_cache_dir("player_fantasy_profile")

# Ensure cache directories exist
os.makedirs(PLAYER_FANTASY_PROFILE_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_player_fantasy_profile(
    player_id: str,
    season: str = CURRENT_NBA_SEASON,
    season_type_playoffs: str = SeasonTypePlayoffs.regular,
    measure_type_base: str = MeasureTypeBase.base,
    per_mode36: str = PerMode36.totals,
    league_id_nullable: str = "",
    pace_adjust_no: str = "N",
    plus_minus_no: str = "N",
    rank_no: str = "N",
    data_set_name: str = "PlayerFantasyProfile"
) -> str:
    """
    Generates a file path for saving player fantasy profile DataFrame.

    Args:
        player_id: Player ID (required)
        season: Season (default: current season)
        season_type_playoffs: Season type (default: Regular Season)
        measure_type_base: Measure type (default: Base)
        per_mode36: Per mode (default: Totals)
        league_id_nullable: League ID (default: "")
        pace_adjust_no: Pace adjust (default: "N")
        plus_minus_no: Plus minus (default: "N")
        rank_no: Rank (default: "N")
        data_set_name: Name of the data set

    Returns:
        Path to the CSV file
    """
    # Create a filename based on the parameters
    filename_parts = [
        f"player_fantasy_profile",
        f"player{player_id}",
        f"season{season.replace('-', '_')}",
        f"type{season_type_playoffs.replace(' ', '_')}",
        f"measure{measure_type_base.replace(' ', '_')}",
        f"per{per_mode36.replace(' ', '_')}",
        f"league{league_id_nullable if league_id_nullable else 'all'}",
        f"pace{pace_adjust_no}",
        f"plus{plus_minus_no}",
        f"rank{rank_no}",
        data_set_name
    ]

    filename = "_".join(filename_parts) + ".csv"

    return get_cache_file_path(filename, "player_fantasy_profile")

# --- Parameter Validation ---
def _validate_player_fantasy_profile_params(
    player_id: str,
    season: str,
    season_type_playoffs: str,
    measure_type_base: str,
    per_mode36: str,
    league_id_nullable: str,
    pace_adjust_no: str,
    plus_minus_no: str,
    rank_no: str
) -> Optional[str]:
    """Validates parameters for fetch_player_fantasy_profile_logic."""
    if not _validate_player_id(player_id):
        return f"Invalid player_id: {player_id}. Must be a valid player ID"
    if not _validate_season_format(season):
        return f"Invalid season format: {season}. Expected format: YYYY-YY"
    if season_type_playoffs not in VALID_SEASON_TYPES:
        return f"Invalid season_type_playoffs: {season_type_playoffs}. Valid options: {', '.join(VALID_SEASON_TYPES)}"
    if measure_type_base not in VALID_MEASURE_TYPES:
        return f"Invalid measure_type_base: {measure_type_base}. Valid options: {', '.join(VALID_MEASURE_TYPES)}"
    if per_mode36 not in VALID_PER_MODES:
        return f"Invalid per_mode36: {per_mode36}. Valid options: {', '.join(VALID_PER_MODES)}"
    if league_id_nullable not in VALID_LEAGUE_IDS:
        return f"Invalid league_id_nullable: {league_id_nullable}. Valid options: {', '.join(VALID_LEAGUE_IDS)}"
    if pace_adjust_no not in VALID_YES_NO:
        return f"Invalid pace_adjust_no: {pace_adjust_no}. Valid options: {', '.join(VALID_YES_NO)}"
    if plus_minus_no not in VALID_YES_NO:
        return f"Invalid plus_minus_no: {plus_minus_no}. Valid options: {', '.join(VALID_YES_NO)}"
    if rank_no not in VALID_YES_NO:
        return f"Invalid rank_no: {rank_no}. Valid options: {', '.join(VALID_YES_NO)}"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=PLAYER_FANTASY_PROFILE_CACHE_SIZE)
def fetch_player_fantasy_profile_logic(
    player_id: str,
    season: str = CURRENT_NBA_SEASON,
    season_type_playoffs: str = SeasonTypePlayoffs.regular,
    measure_type_base: str = MeasureTypeBase.base,
    per_mode36: str = PerMode36.totals,
    league_id_nullable: str = "",
    pace_adjust_no: str = "N",
    plus_minus_no: str = "N",
    rank_no: str = "N",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player fantasy profile data using the PlayerFantasyProfile endpoint.

    Provides DataFrame output capabilities and CSV caching.

    Args:
        player_id: Player ID (required)
        season: Season (default: current season)
        season_type_playoffs: Season type (default: Regular Season)
        measure_type_base: Measure type (default: Base)
        per_mode36: Per mode (default: Totals)
        league_id_nullable: League ID (default: "")
        pace_adjust_no: Pace adjust (default: "N")
        plus_minus_no: Plus minus (default: "N")
        rank_no: Rank (default: "N")
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False:
            str: JSON string with player fantasy profile data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(
        f"Executing fetch_player_fantasy_profile_logic for Player: {player_id}, Season: {season}, "
        f"Type: {season_type_playoffs}, Measure: {measure_type_base}, Per: {per_mode36}, "
        f"League: {league_id_nullable}, return_dataframe={return_dataframe}"
    )

    # Validate parameters
    validation_error = _validate_player_fantasy_profile_params(
        player_id, season, season_type_playoffs, measure_type_base, per_mode36,
        league_id_nullable, pace_adjust_no, plus_minus_no, rank_no
    )
    if validation_error:
        logger.warning(f"Parameter validation failed for player fantasy profile: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response

    # Check for cached CSV files
    dataframes = {}

    # Try to load from cache first
    if return_dataframe:
        # Check for all possible data sets
        data_set_names = ["Overall", "Location", "LastNGames", "DaysRest", "VsOpponent"]
        all_cached = True

        for data_set_name in data_set_names:
            csv_path = _get_csv_path_for_player_fantasy_profile(
                player_id, season, season_type_playoffs, measure_type_base, per_mode36,
                league_id_nullable, pace_adjust_no, plus_minus_no, rank_no, data_set_name
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
                        logger.info(f"Loading player fantasy profile from CSV: {csv_path}")
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
                    "season_type_playoffs": season_type_playoffs,
                    "measure_type_base": measure_type_base,
                    "per_mode36": per_mode36,
                    "league_id_nullable": league_id_nullable,
                    "pace_adjust_no": pace_adjust_no,
                    "plus_minus_no": plus_minus_no,
                    "rank_no": rank_no
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
            "season": season,
            "season_type_playoffs": season_type_playoffs,
            "measure_type_base": measure_type_base,
            "per_mode36": per_mode36,
            "pace_adjust_no": pace_adjust_no,
            "plus_minus_no": plus_minus_no,
            "rank_no": rank_no
        }

        # Add league_id_nullable (can be empty string)
        api_params["league_id_nullable"] = league_id_nullable

        logger.debug(f"Calling PlayerFantasyProfile with parameters: {api_params}")
        fantasy_profile_endpoint = playerfantasyprofile.PlayerFantasyProfile(**api_params)

        # Get data frames
        list_of_dataframes = fantasy_profile_endpoint.get_data_frames()

        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": {
                "player_id": player_id,
                "season": season,
                "season_type_playoffs": season_type_playoffs,
                "measure_type_base": measure_type_base,
                "per_mode36": per_mode36,
                "league_id_nullable": league_id_nullable,
                "pace_adjust_no": pace_adjust_no,
                "plus_minus_no": plus_minus_no,
                "rank_no": rank_no
            },
            "data_sets": {}
        }

        # Process each data frame
        data_set_names = ["Overall", "Location", "LastNGames", "DaysRest", "VsOpponent"]

        for idx, df in enumerate(list_of_dataframes):
            if not df.empty:
                # Use predefined names for the data sets
                data_set_name = data_set_names[idx] if idx < len(data_set_names) else f"PlayerFantasyProfile_{idx}"

                # Store DataFrame if requested
                if return_dataframe:
                    dataframes[data_set_name] = df

                    # Save DataFrame to CSV
                    csv_path = _get_csv_path_for_player_fantasy_profile(
                        player_id, season, season_type_playoffs, measure_type_base, per_mode36,
                        league_id_nullable, pace_adjust_no, plus_minus_no, rank_no, data_set_name
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
        logger.error(f"Unexpected error in fetch_player_fantasy_profile_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_player_fantasy_profile(
    player_id: str,
    season: str = CURRENT_NBA_SEASON,
    season_type_playoffs: str = SeasonTypePlayoffs.regular,
    measure_type_base: str = MeasureTypeBase.base,
    per_mode36: str = PerMode36.totals,
    league_id_nullable: str = "",
    pace_adjust_no: str = "N",
    plus_minus_no: str = "N",
    rank_no: str = "N",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get player fantasy profile data.

    Args:
        player_id: Player ID (required)
        season: Season (default: current season)
        season_type_playoffs: Season type (default: Regular Season)
        measure_type_base: Measure type (default: Base)
        per_mode36: Per mode (default: Totals)
        league_id_nullable: League ID (default: "")
        pace_adjust_no: Pace adjust (default: "N")
        plus_minus_no: Plus minus (default: "N")
        rank_no: Rank (default: "N")
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False:
            str: JSON string with player fantasy profile data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_player_fantasy_profile_logic(
        player_id=player_id,
        season=season,
        season_type_playoffs=season_type_playoffs,
        measure_type_base=measure_type_base,
        per_mode36=per_mode36,
        league_id_nullable=league_id_nullable,
        pace_adjust_no=pace_adjust_no,
        plus_minus_no=plus_minus_no,
        rank_no=rank_no,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Test basic functionality
    print("Testing PlayerFantasyProfile endpoint...")

    # Test 1: Basic fetch
    json_response = get_player_fantasy_profile(player_id="2544")  # LeBron James
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")

    # Test 2: With DataFrame output
    json_response, dataframes = get_player_fantasy_profile(player_id="2544", return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")

    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")

    print("PlayerFantasyProfile endpoint test completed.")

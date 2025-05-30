"""
Handles fetching and processing player comparison data
from the PlayerCompare endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The PlayerCompare endpoint provides comprehensive player comparison data (2 DataFrames):
- Comparison Info: GROUP_SET, DESCRIPTION (2 columns)
- Minutes: MIN (1 column)
- Shooting: FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT (9 columns)
- Rebounding: OREB, DREB, REB (3 columns)
- Other Stats: AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS (9 columns)
- Rich comparison data: Head-to-head player statistics with detailed breakdowns (24 columns total)
- Perfect for head-to-head comparisons, performance analysis, and historical comparisons
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple, List
from functools import lru_cache

from nba_api.stats.endpoints import playercompare
from nba_api.stats.library.parameters import SeasonTypePlayoffs, PerModeDetailed, MeasureTypeDetailedDefense
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

def _validate_player_id_list(player_id_list):
    """Validate player ID list format."""
    if not player_id_list:
        return False

    if isinstance(player_id_list, list):
        # Check if all items are strings or integers
        for player_id in player_id_list:
            if not isinstance(player_id, (str, int)):
                return False
            # If string, check if it's a valid number
            if isinstance(player_id, str):
                try:
                    int(player_id)
                except ValueError:
                    return False
        return True

    return False

# Default current NBA season
CURRENT_NBA_SEASON = "2024-25"

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
PLAYER_COMPARE_CACHE_SIZE = 256

# Valid parameter sets
VALID_LEAGUE_IDS: Set[str] = {"00", "10", ""}  # NBA, WNBA, or empty
VALID_PER_MODES: Set[str] = {PerModeDetailed.totals, PerModeDetailed.per_game}
VALID_SEASON_TYPES: Set[str] = {SeasonTypePlayoffs.regular, SeasonTypePlayoffs.playoffs}
VALID_MEASURE_TYPES: Set[str] = {MeasureTypeDetailedDefense.base, MeasureTypeDetailedDefense.advanced, MeasureTypeDetailedDefense.misc, MeasureTypeDetailedDefense.scoring, MeasureTypeDetailedDefense.usage}
VALID_PACE_ADJUST: Set[str] = {"Y", "N"}
VALID_PLUS_MINUS: Set[str] = {"Y", "N"}
VALID_RANK: Set[str] = {"Y", "N"}

# --- Cache Directory Setup ---
PLAYER_COMPARE_CSV_DIR = get_cache_dir("player_compare")

# Ensure cache directories exist
os.makedirs(PLAYER_COMPARE_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_player_compare(
    vs_player_id_list: List[str],
    player_id_list: List[str],
    season: str = CURRENT_NBA_SEASON,
    season_type_playoffs: str = SeasonTypePlayoffs.regular,
    per_mode_detailed: str = PerModeDetailed.totals,
    measure_type_detailed_defense: str = MeasureTypeDetailedDefense.base,
    league_id_nullable: str = "",
    last_n_games: int = 0,
    data_set_name: str = "PlayerCompare"
) -> str:
    """
    Generates a file path for saving player compare DataFrame.

    Args:
        vs_player_id_list: List of player IDs to compare against
        player_id_list: List of player IDs to compare
        season: Season (default: current season)
        season_type_playoffs: Season type (default: Regular Season)
        per_mode_detailed: Per mode (default: Totals)
        measure_type_detailed_defense: Measure type (default: Base)
        league_id_nullable: League ID (default: "")
        last_n_games: Last N games (default: 0)
        data_set_name: Name of the data set

    Returns:
        Path to the CSV file
    """
    # Create a filename based on the parameters
    vs_players_str = "_".join(vs_player_id_list)
    players_str = "_".join(player_id_list)

    filename_parts = [
        f"player_compare",
        f"vs{vs_players_str}",
        f"players{players_str}",
        f"season{season.replace('-', '_')}",
        f"type{season_type_playoffs.replace(' ', '_')}",
        f"per{per_mode_detailed.replace(' ', '_')}",
        f"measure{measure_type_detailed_defense.replace(' ', '_')}",
        f"league{league_id_nullable if league_id_nullable else 'all'}",
        f"games{last_n_games}",
        data_set_name
    ]

    filename = "_".join(filename_parts) + ".csv"

    return get_cache_file_path(filename, "player_compare")

# --- Parameter Validation ---
def _validate_player_compare_params(
    vs_player_id_list: List[str],
    player_id_list: List[str],
    season: str,
    season_type_playoffs: str,
    per_mode_detailed: str,
    measure_type_detailed_defense: str,
    league_id_nullable: str,
    last_n_games: int,
    pace_adjust: str,
    plus_minus: str,
    rank: str
) -> Optional[str]:
    """Validates parameters for fetch_player_compare_logic."""
    if not _validate_player_id_list(vs_player_id_list):
        return f"Invalid vs_player_id_list: {vs_player_id_list}. Must be a list of valid player IDs"
    if not _validate_player_id_list(player_id_list):
        return f"Invalid player_id_list: {player_id_list}. Must be a list of valid player IDs"
    if not _validate_season_format(season):
        return f"Invalid season format: {season}. Expected format: YYYY-YY"
    if season_type_playoffs not in VALID_SEASON_TYPES:
        return f"Invalid season_type_playoffs: {season_type_playoffs}. Valid options: {', '.join(VALID_SEASON_TYPES)}"
    if per_mode_detailed not in VALID_PER_MODES:
        return f"Invalid per_mode_detailed: {per_mode_detailed}. Valid options: {', '.join(VALID_PER_MODES)}"
    if measure_type_detailed_defense not in VALID_MEASURE_TYPES:
        return f"Invalid measure_type_detailed_defense: {measure_type_detailed_defense}. Valid options: {', '.join(VALID_MEASURE_TYPES)}"
    if league_id_nullable not in VALID_LEAGUE_IDS:
        return f"Invalid league_id_nullable: {league_id_nullable}. Valid options: {', '.join(VALID_LEAGUE_IDS)}"
    if not isinstance(last_n_games, int) or last_n_games < 0:
        return f"Invalid last_n_games: {last_n_games}. Must be a non-negative integer"
    if pace_adjust not in VALID_PACE_ADJUST:
        return f"Invalid pace_adjust: {pace_adjust}. Valid options: {', '.join(VALID_PACE_ADJUST)}"
    if plus_minus not in VALID_PLUS_MINUS:
        return f"Invalid plus_minus: {plus_minus}. Valid options: {', '.join(VALID_PLUS_MINUS)}"
    if rank not in VALID_RANK:
        return f"Invalid rank: {rank}. Valid options: {', '.join(VALID_RANK)}"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=PLAYER_COMPARE_CACHE_SIZE)
def fetch_player_compare_logic(
    vs_player_id_list: Tuple[str, ...],
    player_id_list: Tuple[str, ...],
    season: str = CURRENT_NBA_SEASON,
    season_type_playoffs: str = SeasonTypePlayoffs.regular,
    per_mode_detailed: str = PerModeDetailed.totals,
    measure_type_detailed_defense: str = MeasureTypeDetailedDefense.base,
    league_id_nullable: str = "",
    last_n_games: int = 0,
    pace_adjust: str = "N",
    plus_minus: str = "N",
    rank: str = "N",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player comparison data using the PlayerCompare endpoint.

    Provides DataFrame output capabilities and CSV caching.

    Args:
        vs_player_id_list: Tuple of player IDs to compare against
        player_id_list: Tuple of player IDs to compare
        season: Season (default: current season)
        season_type_playoffs: Season type (default: Regular Season)
        per_mode_detailed: Per mode (default: Totals)
        measure_type_detailed_defense: Measure type (default: Base)
        league_id_nullable: League ID (default: "")
        last_n_games: Last N games (default: 0)
        pace_adjust: Pace adjust (default: "N")
        plus_minus: Plus minus (default: "N")
        rank: Rank (default: "N")
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False:
            str: JSON string with player comparison data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    # Convert tuples back to lists for processing
    vs_player_id_list = list(vs_player_id_list)
    player_id_list = list(player_id_list)

    logger.info(
        f"Executing fetch_player_compare_logic for VS Players: {vs_player_id_list}, Players: {player_id_list}, "
        f"Season: {season}, Type: {season_type_playoffs}, Per: {per_mode_detailed}, "
        f"Measure: {measure_type_detailed_defense}, League: {league_id_nullable}, "
        f"Games: {last_n_games}, return_dataframe={return_dataframe}"
    )

    # Validate parameters
    validation_error = _validate_player_compare_params(
        vs_player_id_list, player_id_list, season, season_type_playoffs, per_mode_detailed,
        measure_type_detailed_defense, league_id_nullable, last_n_games, pace_adjust, plus_minus, rank
    )
    if validation_error:
        logger.warning(f"Parameter validation failed for player compare: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response

    # Check for cached CSV files
    dataframes = {}

    # Try to load from cache first
    if return_dataframe:
        # Check for all possible data sets
        data_set_names = ["OverallComparison", "IndividualComparison"]
        all_cached = True

        for data_set_name in data_set_names:
            csv_path = _get_csv_path_for_player_compare(
                vs_player_id_list, player_id_list, season, season_type_playoffs, per_mode_detailed,
                measure_type_detailed_defense, league_id_nullable, last_n_games, data_set_name
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
                        logger.info(f"Loading player compare from CSV: {csv_path}")
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
                    "vs_player_id_list": vs_player_id_list,
                    "player_id_list": player_id_list,
                    "season": season,
                    "season_type_playoffs": season_type_playoffs,
                    "per_mode_detailed": per_mode_detailed,
                    "measure_type_detailed_defense": measure_type_detailed_defense,
                    "league_id_nullable": league_id_nullable,
                    "last_n_games": last_n_games,
                    "pace_adjust": pace_adjust,
                    "plus_minus": plus_minus,
                    "rank": rank
                },
                "data_sets": {}
            }

            for data_set_name, df in dataframes.items():
                result_dict["data_sets"][data_set_name] = _process_dataframe(df, single_row=False)

            return format_response(result_dict), dataframes

    try:
        # Prepare API parameters
        api_params = {
            "vs_player_id_list": vs_player_id_list,
            "player_id_list": player_id_list,
            "season": season,
            "season_type_playoffs": season_type_playoffs,
            "per_mode_detailed": per_mode_detailed,
            "measure_type_detailed_defense": measure_type_detailed_defense,
            "last_n_games": last_n_games,
            "pace_adjust": pace_adjust,
            "plus_minus": plus_minus,
            "rank": rank
        }

        # Add league_id_nullable (can be empty string)
        api_params["league_id_nullable"] = league_id_nullable

        logger.debug(f"Calling PlayerCompare with parameters: {api_params}")
        player_compare_endpoint = playercompare.PlayerCompare(**api_params)

        # Get data frames
        list_of_dataframes = player_compare_endpoint.get_data_frames()

        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": {
                "vs_player_id_list": vs_player_id_list,
                "player_id_list": player_id_list,
                "season": season,
                "season_type_playoffs": season_type_playoffs,
                "per_mode_detailed": per_mode_detailed,
                "measure_type_detailed_defense": measure_type_detailed_defense,
                "league_id_nullable": league_id_nullable,
                "last_n_games": last_n_games,
                "pace_adjust": pace_adjust,
                "plus_minus": plus_minus,
                "rank": rank
            },
            "data_sets": {}
        }

        # Process each data frame
        data_set_names = ["OverallComparison", "IndividualComparison"]

        for idx, df in enumerate(list_of_dataframes):
            if not df.empty:
                # Use predefined names for the data sets
                data_set_name = data_set_names[idx] if idx < len(data_set_names) else f"PlayerCompare_{idx}"

                # Store DataFrame if requested
                if return_dataframe:
                    dataframes[data_set_name] = df

                    # Save DataFrame to CSV
                    csv_path = _get_csv_path_for_player_compare(
                        vs_player_id_list, player_id_list, season, season_type_playoffs, per_mode_detailed,
                        measure_type_detailed_defense, league_id_nullable, last_n_games, data_set_name
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
        logger.error(f"Unexpected error in fetch_player_compare_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_player_compare(
    vs_player_id_list: List[str],
    player_id_list: List[str],
    season: str = CURRENT_NBA_SEASON,
    season_type_playoffs: str = SeasonTypePlayoffs.regular,
    per_mode_detailed: str = PerModeDetailed.totals,
    measure_type_detailed_defense: str = MeasureTypeDetailedDefense.base,
    league_id_nullable: str = "",
    last_n_games: int = 0,
    pace_adjust: str = "N",
    plus_minus: str = "N",
    rank: str = "N",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get player comparison data.

    Args:
        vs_player_id_list: List of player IDs to compare against
        player_id_list: List of player IDs to compare
        season: Season (default: current season)
        season_type_playoffs: Season type (default: Regular Season)
        per_mode_detailed: Per mode (default: Totals)
        measure_type_detailed_defense: Measure type (default: Base)
        league_id_nullable: League ID (default: "")
        last_n_games: Last N games (default: 0)
        pace_adjust: Pace adjust (default: "N")
        plus_minus: Plus minus (default: "N")
        rank: Rank (default: "N")
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False:
            str: JSON string with player comparison data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_player_compare_logic(
        vs_player_id_list=tuple(vs_player_id_list),
        player_id_list=tuple(player_id_list),
        season=season,
        season_type_playoffs=season_type_playoffs,
        per_mode_detailed=per_mode_detailed,
        measure_type_detailed_defense=measure_type_detailed_defense,
        league_id_nullable=league_id_nullable,
        last_n_games=last_n_games,
        pace_adjust=pace_adjust,
        plus_minus=plus_minus,
        rank=rank,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Test basic functionality
    print("Testing PlayerCompare endpoint...")

    # Test 1: Basic fetch
    json_response = get_player_compare(
        vs_player_id_list=["2544"],  # LeBron James
        player_id_list=["201939"]    # Stephen Curry
    )
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")

    # Test 2: With DataFrame output
    json_response, dataframes = get_player_compare(
        vs_player_id_list=["2544"],  # LeBron James
        player_id_list=["201939"],   # Stephen Curry
        return_dataframe=True
    )
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")

    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")

    print("PlayerCompare endpoint test completed.")

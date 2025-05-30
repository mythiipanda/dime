"""
Handles fetching and processing league lineup visualization data
from the LeagueLineupViz endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The LeagueLineupViz endpoint provides comprehensive lineup data (1 DataFrame):
- Lineup Info: GROUP_ID, GROUP_NAME, TEAM_ID, TEAM_ABBREVIATION, MIN (5 columns)
- Performance Ratings: OFF_RATING, DEF_RATING, NET_RATING, PACE (4 columns)
- Shooting Efficiency: TS_PCT, FTA_RATE, PCT_FGA_2PT, PCT_FGA_3PT (4 columns)
- Scoring Breakdown: PCT_PTS_2PT_MR, PCT_PTS_FB, PCT_PTS_FT, PCT_PTS_PAINT (4 columns)
- Team Play: TM_AST_PCT, PCT_AST_FGM, PCT_UAST_FGM (3 columns)
- Opponent Stats: OPP_FG3_PCT, OPP_EFG_PCT, OPP_FTA_RATE, OPP_TOV_PCT (4 columns)
- Rich lineup data: 5000+ lineups with detailed performance statistics (24 columns total)
- Perfect for lineup analysis, performance tracking, and strategic insights
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import leaguelineupviz
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailedDefense
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

# Default current NBA season
CURRENT_NBA_SEASON = "2024-25"

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
LEAGUE_LINEUP_VIZ_CACHE_SIZE = 128

# Valid parameter sets
VALID_LEAGUE_IDS: Set[str] = {"00", "10"}  # NBA, WNBA
VALID_GROUP_QUANTITIES: Set[int] = {2, 3, 4, 5}  # 2-5 player lineups
VALID_MEASURE_TYPES: Set[str] = {MeasureTypeDetailedDefense.base}
VALID_PER_MODES: Set[str] = {PerModeDetailed.totals, PerModeDetailed.per_game}
VALID_SEASON_TYPES: Set[str] = {SeasonTypeAllStar.regular, SeasonTypeAllStar.playoffs, SeasonTypeAllStar.all_star}
VALID_PACE_ADJUST: Set[str] = {"Y", "N"}
VALID_PLUS_MINUS: Set[str] = {"Y", "N"}
VALID_RANK: Set[str] = {"Y", "N"}

# --- Cache Directory Setup ---
LEAGUE_LINEUP_VIZ_CSV_DIR = get_cache_dir("league_lineup_viz")

# Ensure cache directories exist
os.makedirs(LEAGUE_LINEUP_VIZ_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_league_lineup_viz(
    minutes_min: int = 5,
    group_quantity: int = 5,
    last_n_games: int = 0,
    measure_type_detailed_defense: str = MeasureTypeDetailedDefense.base,
    per_mode_detailed: str = PerModeDetailed.totals,
    season: str = CURRENT_NBA_SEASON,
    season_type_all_star: str = SeasonTypeAllStar.regular,
    league_id_nullable: str = "",
    data_set_name: str = "LineupViz"
) -> str:
    """
    Generates a file path for saving league lineup viz DataFrame.

    Args:
        minutes_min: Minimum minutes played (default: 5)
        group_quantity: Number of players in lineup (default: 5)
        last_n_games: Last N games (default: 0)
        measure_type_detailed_defense: Measure type (default: Base)
        per_mode_detailed: Per mode (default: Totals)
        season: Season in YYYY-YY format
        season_type_all_star: Season type (default: Regular Season)
        league_id_nullable: League ID (default: "")
        data_set_name: Name of the data set

    Returns:
        Path to the CSV file
    """
    # Create a filename based on the parameters
    filename_parts = [
        f"league_lineup_viz",
        f"season{season}",
        f"type{season_type_all_star.replace(' ', '_')}",
        f"measure{measure_type_detailed_defense.replace(' ', '_')}",
        f"per{per_mode_detailed.replace(' ', '_')}",
        f"min{minutes_min}",
        f"group{group_quantity}",
        f"games{last_n_games}",
        f"league{league_id_nullable if league_id_nullable else 'all'}",
        data_set_name
    ]

    filename = "_".join(filename_parts) + ".csv"

    return get_cache_file_path(filename, "league_lineup_viz")

# --- Parameter Validation ---
def _validate_league_lineup_viz_params(
    minutes_min: int,
    group_quantity: int,
    last_n_games: int,
    measure_type_detailed_defense: str,
    per_mode_detailed: str,
    season: str,
    season_type_all_star: str,
    league_id_nullable: str
) -> Optional[str]:
    """Validates parameters for fetch_league_lineup_viz_logic."""
    if minutes_min < 0:
        return f"Invalid minutes_min: {minutes_min}. Must be >= 0"
    if group_quantity not in VALID_GROUP_QUANTITIES:
        return f"Invalid group_quantity: {group_quantity}. Valid options: {', '.join(map(str, VALID_GROUP_QUANTITIES))}"
    if last_n_games < 0:
        return f"Invalid last_n_games: {last_n_games}. Must be >= 0"
    if measure_type_detailed_defense not in VALID_MEASURE_TYPES:
        return f"Invalid measure_type_detailed_defense: {measure_type_detailed_defense}. Valid options: {', '.join(VALID_MEASURE_TYPES)}"
    if per_mode_detailed not in VALID_PER_MODES:
        return f"Invalid per_mode_detailed: {per_mode_detailed}. Valid options: {', '.join(VALID_PER_MODES)}"
    if not season or not _validate_season_format(season):
        return f"Invalid season format: {season}. Expected format: YYYY-YY"
    if season_type_all_star not in VALID_SEASON_TYPES:
        return f"Invalid season_type_all_star: {season_type_all_star}. Valid options: {', '.join(VALID_SEASON_TYPES)}"
    if league_id_nullable and league_id_nullable not in VALID_LEAGUE_IDS:
        return f"Invalid league_id_nullable: {league_id_nullable}. Valid options: {', '.join(VALID_LEAGUE_IDS)}"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=LEAGUE_LINEUP_VIZ_CACHE_SIZE)
def fetch_league_lineup_viz_logic(
    minutes_min: int = 5,
    group_quantity: int = 5,
    last_n_games: int = 0,
    measure_type_detailed_defense: str = MeasureTypeDetailedDefense.base,
    per_mode_detailed: str = PerModeDetailed.totals,
    season: str = CURRENT_NBA_SEASON,
    season_type_all_star: str = SeasonTypeAllStar.regular,
    league_id_nullable: str = "",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league lineup visualization data using the LeagueLineupViz endpoint.

    Provides DataFrame output capabilities and CSV caching.

    Args:
        minutes_min: Minimum minutes played (default: 5)
        group_quantity: Number of players in lineup (default: 5)
        last_n_games: Last N games (default: 0)
        measure_type_detailed_defense: Measure type (default: Base)
        per_mode_detailed: Per mode (default: Totals)
        season: Season in YYYY-YY format (default: current NBA season)
        season_type_all_star: Season type (default: Regular Season)
        league_id_nullable: League ID (default: "")
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False:
            str: JSON string with lineup viz data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(
        f"Executing fetch_league_lineup_viz_logic for Season: {season}, "
        f"Type: {season_type_all_star}, Measure: {measure_type_detailed_defense}, Per: {per_mode_detailed}, "
        f"Min: {minutes_min}, Group: {group_quantity}, Games: {last_n_games}, League: {league_id_nullable}, "
        f"return_dataframe={return_dataframe}"
    )

    # Validate parameters
    validation_error = _validate_league_lineup_viz_params(
        minutes_min, group_quantity, last_n_games, measure_type_detailed_defense,
        per_mode_detailed, season, season_type_all_star, league_id_nullable
    )
    if validation_error:
        logger.warning(f"Parameter validation failed for league lineup viz: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response

    # Check for cached CSV file
    csv_path = _get_csv_path_for_league_lineup_viz(
        minutes_min, group_quantity, last_n_games, measure_type_detailed_defense,
        per_mode_detailed, season, season_type_all_star, league_id_nullable, "LineupViz"
    )
    dataframes = {}

    if os.path.exists(csv_path) and return_dataframe:
        try:
            # Check if the file is empty or too small
            file_size = os.path.getsize(csv_path)
            if file_size < 1000:  # If file is too small, it's probably empty or corrupted
                logger.warning(f"CSV file is too small ({file_size} bytes), fetching from API instead")
                # Delete the corrupted file
                try:
                    os.remove(csv_path)
                    logger.info(f"Deleted corrupted CSV file: {csv_path}")
                except Exception as e:
                    logger.error(f"Error deleting corrupted CSV file: {e}", exc_info=True)
                # Continue to API fetch
            else:
                logger.info(f"Loading league lineup viz from CSV: {csv_path}")
                # Read CSV with appropriate data types
                df = pd.read_csv(csv_path, encoding='utf-8')

                # Process for JSON response
                result_dict = {
                    "parameters": {
                        "minutes_min": minutes_min,
                        "group_quantity": group_quantity,
                        "last_n_games": last_n_games,
                        "measure_type_detailed_defense": measure_type_detailed_defense,
                        "per_mode_detailed": per_mode_detailed,
                        "season": season,
                        "season_type_all_star": season_type_all_star,
                        "league_id_nullable": league_id_nullable
                    },
                    "data_sets": {}
                }

                # Store the DataFrame
                dataframes["LineupViz"] = df
                result_dict["data_sets"]["LineupViz"] = _process_dataframe(df, single_row=False)

                if return_dataframe:
                    return format_response(result_dict), dataframes
                return format_response(result_dict)

        except Exception as e:
            logger.error(f"Error loading CSV: {e}", exc_info=True)
            # If there's an error loading the CSV, fetch from the API

    try:
        # Prepare API parameters
        api_params = {
            "minutes_min": minutes_min,
            "group_quantity": group_quantity,
            "last_n_games": last_n_games,
            "measure_type_detailed_defense": measure_type_detailed_defense,
            "per_mode_detailed": per_mode_detailed,
            "season": season,
            "season_type_all_star": season_type_all_star
        }

        # Add league_id_nullable only if it's not empty
        if league_id_nullable:
            api_params["league_id_nullable"] = league_id_nullable

        logger.debug(f"Calling LeagueLineupViz with parameters: {api_params}")
        lineup_viz_endpoint = leaguelineupviz.LeagueLineupViz(**api_params)

        # Get data frames
        list_of_dataframes = lineup_viz_endpoint.get_data_frames()

        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": {
                "minutes_min": minutes_min,
                "group_quantity": group_quantity,
                "last_n_games": last_n_games,
                "measure_type_detailed_defense": measure_type_detailed_defense,
                "per_mode_detailed": per_mode_detailed,
                "season": season,
                "season_type_all_star": season_type_all_star,
                "league_id_nullable": league_id_nullable
            },
            "data_sets": {}
        }

        # Create a combined DataFrame for CSV storage
        combined_df = pd.DataFrame()

        # Process each data frame
        for idx, df in enumerate(list_of_dataframes):
            # Use a generic name for the data set
            data_set_name = f"LineupViz_{idx}" if idx > 0 else "LineupViz"

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
        logger.error(f"Unexpected error in fetch_league_lineup_viz_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_league_lineup_viz(
    minutes_min: int = 5,
    group_quantity: int = 5,
    last_n_games: int = 0,
    measure_type_detailed_defense: str = MeasureTypeDetailedDefense.base,
    per_mode_detailed: str = PerModeDetailed.totals,
    season: str = CURRENT_NBA_SEASON,
    season_type_all_star: str = SeasonTypeAllStar.regular,
    league_id_nullable: str = "",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get league lineup visualization data.

    Args:
        minutes_min: Minimum minutes played (default: 5)
        group_quantity: Number of players in lineup (default: 5)
        last_n_games: Last N games (default: 0)
        measure_type_detailed_defense: Measure type (default: Base)
        per_mode_detailed: Per mode (default: Totals)
        season: Season in YYYY-YY format (default: current NBA season)
        season_type_all_star: Season type (default: Regular Season)
        league_id_nullable: League ID (default: "")
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False:
            str: JSON string with lineup viz data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_league_lineup_viz_logic(
        minutes_min=minutes_min,
        group_quantity=group_quantity,
        last_n_games=last_n_games,
        measure_type_detailed_defense=measure_type_detailed_defense,
        per_mode_detailed=per_mode_detailed,
        season=season,
        season_type_all_star=season_type_all_star,
        league_id_nullable=league_id_nullable,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Test basic functionality
    print("Testing LeagueLineupViz endpoint...")

    # Test 1: Basic fetch
    json_response = get_league_lineup_viz()
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")

    # Test 2: With DataFrame output
    json_response, dataframes = get_league_lineup_viz(return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")

    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")

    print("LeagueLineupViz endpoint test completed.")

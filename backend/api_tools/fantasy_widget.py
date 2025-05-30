"""
Handles fetching and processing fantasy basketball widget data
from the FantasyWidget endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The FantasyWidget endpoint provides comprehensive fantasy basketball data (20 columns):
- Player info: ID, name, position, team (5 columns)
- Game stats: games played, minutes (2 columns)
- Fantasy points: FanDuel points, NBA fantasy points (2 columns)
- Traditional stats: PTS, REB, AST, BLK, STL, TOV, FG3M, FGA, FG_PCT, FTA, FT_PCT (11 columns)
- Multi-season data: 2021-22: 605 players, 2022-23: 539 players, 2023-24: 572 players, 2024-25: 569 players
- Perfect for fantasy basketball analysis, player evaluation, and DFS optimization
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import fantasywidget
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
CURRENT_NBA_SEASON = "2024-25"

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
FANTASY_WIDGET_CACHE_SIZE = 32

# Valid parameter sets
VALID_LEAGUE_IDS: Set[str] = {"00", "10"}  # NBA, WNBA
VALID_ACTIVE_PLAYERS: Set[str] = {"Y", "N"}
VALID_TODAYS_PLAYERS: Set[str] = {"Y", "N"}
VALID_TODAYS_OPPONENT: Set[str] = {"0", "1"}
VALID_POSITIONS: Set[str] = {"F", "C", "G", "F-C", "F-G", "G-F", "C-F"}

# --- Cache Directory Setup ---
FANTASY_WIDGET_CSV_DIR = get_cache_dir("fantasy_widget")

# Ensure cache directories exist
os.makedirs(FANTASY_WIDGET_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_fantasy_widget(
    league_id: str = "00",
    season: str = CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    active_players: Optional[str] = None,
    last_n_games: Optional[int] = None,
    team_id: Optional[str] = None,
    position: Optional[str] = None
) -> str:
    """
    Generates a file path for saving fantasy widget DataFrame.

    Args:
        league_id: League ID (default: "00" for NBA)
        season: Season in YYYY-YY format
        season_type: Season type (default: Regular Season)
        active_players: Active players filter (optional)
        last_n_games: Last N games filter (optional)
        team_id: Team ID filter (optional)
        position: Position filter (optional)

    Returns:
        Path to the CSV file
    """
    # Create a filename based on the parameters
    filename_parts = [
        f"fantasy_widget_league{league_id}",
        f"season{season}",
        f"type{season_type.replace(' ', '_')}"
    ]

    # Add optional filters to filename
    if active_players:
        filename_parts.append(f"active{active_players}")
    if last_n_games and last_n_games > 0:
        filename_parts.append(f"lastN{last_n_games}")
    if team_id:
        filename_parts.append(f"team{team_id}")
    if position:
        filename_parts.append(f"pos{position}")

    filename = "_".join(filename_parts) + ".csv"

    return get_cache_file_path(filename, "fantasy_widget")

# --- Parameter Validation ---
def _validate_fantasy_widget_params(
    league_id: str,
    season: str,
    season_type: str,
    active_players: Optional[str] = None,
    position: Optional[str] = None
) -> Optional[str]:
    """Validates parameters for fetch_fantasy_widget_logic."""
    if league_id not in VALID_LEAGUE_IDS:
        return f"Invalid league_id: {league_id}. Valid options: {', '.join(VALID_LEAGUE_IDS)}"
    if not season or not _validate_season_format(season):
        return f"Invalid season format: {season}. Expected format: YYYY-YY"
    if active_players and active_players not in VALID_ACTIVE_PLAYERS:
        return f"Invalid active_players: {active_players}. Valid options: {', '.join(VALID_ACTIVE_PLAYERS)}"
    if position and position not in VALID_POSITIONS:
        return f"Invalid position: {position}. Valid options: {', '.join(VALID_POSITIONS)}"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=FANTASY_WIDGET_CACHE_SIZE)
def fetch_fantasy_widget_logic(
    league_id: str = "00",
    season: str = CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    active_players: str = "N",
    last_n_games: int = 0,
    todays_opponent: str = "0",
    todays_players: str = "N",
    team_id: Optional[str] = None,
    position: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches fantasy widget data using the FantasyWidget endpoint.

    Provides DataFrame output capabilities and CSV caching.

    Args:
        league_id: League ID (default: "00" for NBA)
        season: Season in YYYY-YY format (default: current NBA season)
        season_type: Season type (default: Regular Season)
        active_players: Active players only flag (default: "N")
        last_n_games: Last N games filter (default: 0)
        todays_opponent: Today's opponent filter (default: "0")
        todays_players: Today's players filter (default: "N")
        team_id: Team ID filter (optional)
        position: Position filter (optional)
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False:
            str: JSON string with fantasy widget data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(
        f"Executing fetch_fantasy_widget_logic for League: {league_id}, Season: {season}, "
        f"Season Type: {season_type}, Active: {active_players}, Last N Games: {last_n_games}, "
        f"Team: {team_id}, Position: {position}, return_dataframe={return_dataframe}"
    )

    # Validate parameters
    validation_error = _validate_fantasy_widget_params(league_id, season, season_type, active_players, position)
    if validation_error:
        logger.warning(f"Parameter validation failed for fantasy widget: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response

    # Check for cached CSV file
    csv_path = _get_csv_path_for_fantasy_widget(
        league_id=league_id,
        season=season,
        season_type=season_type,
        active_players=active_players if active_players != "N" else None,
        last_n_games=last_n_games if last_n_games > 0 else None,
        team_id=team_id,
        position=position
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
                logger.info(f"Loading fantasy widget from CSV: {csv_path}")
                # Read CSV with appropriate data types
                df = pd.read_csv(csv_path, encoding='utf-8')

                # Process for JSON response
                result_dict = {
                    "parameters": {
                        "league_id": league_id,
                        "season": season,
                        "season_type_all_star": season_type,
                        "active_players": active_players,
                        "last_n_games": last_n_games,
                        "todays_opponent": todays_opponent,
                        "todays_players": todays_players,
                        "team_id_nullable": team_id,
                        "position_nullable": position
                    },
                    "data_sets": {}
                }

                # Store the DataFrame
                dataframes["FantasyWidget"] = df
                result_dict["data_sets"]["FantasyWidget"] = _process_dataframe(df, single_row=False)

                if return_dataframe:
                    return format_response(result_dict), dataframes
                return format_response(result_dict)

        except Exception as e:
            logger.error(f"Error loading CSV: {e}", exc_info=True)
            # If there's an error loading the CSV, fetch from the API

    try:
        # Prepare API parameters (only include non-None values)
        api_params = {
            "league_id": league_id,
            "season": season,
            "season_type_all_star": season_type,
            "active_players": active_players,
            "last_n_games": last_n_games,
            "todays_opponent": todays_opponent,
            "todays_players": todays_players
        }

        # Add optional parameters if provided
        if team_id:
            api_params["team_id_nullable"] = team_id
        if position:
            api_params["position_nullable"] = position

        logger.debug(f"Calling FantasyWidget with parameters: {api_params}")
        fantasy_widget_endpoint = fantasywidget.FantasyWidget(**api_params)

        # Get data frames
        list_of_dataframes = fantasy_widget_endpoint.get_data_frames()

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
                data_set_name = f"FantasyWidget_{idx}" if idx > 0 else "FantasyWidget"

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
            # Recalculate CSV path to ensure consistency
            save_csv_path = _get_csv_path_for_fantasy_widget(
                league_id=league_id,
                season=season,
                season_type=season_type,
                active_players=active_players if active_players != "N" else None,
                last_n_games=last_n_games if last_n_games > 0 else None,
                team_id=team_id,
                position=position
            )
            _save_dataframe_to_csv(combined_df, save_csv_path)

        final_json_response = format_response(result_dict)
        if return_dataframe:
            return final_json_response, dataframes
        return final_json_response

    except Exception as e:
        logger.error(f"Unexpected error in fetch_fantasy_widget_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_fantasy_widget(
    league_id: str = "00",
    season: str = CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    active_players: str = "N",
    last_n_games: int = 0,
    todays_opponent: str = "0",
    todays_players: str = "N",
    team_id: Optional[str] = None,
    position: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get fantasy widget data.

    Args:
        league_id: League ID (default: "00" for NBA)
        season: Season in YYYY-YY format (default: current NBA season)
        season_type: Season type (default: Regular Season)
        active_players: Active players only flag (default: "N")
        last_n_games: Last N games filter (default: 0)
        todays_opponent: Today's opponent filter (default: "0")
        todays_players: Today's players filter (default: "N")
        team_id: Team ID filter (optional)
        position: Position filter (optional)
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False:
            str: JSON string with fantasy widget data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_fantasy_widget_logic(
        league_id=league_id,
        season=season,
        season_type=season_type,
        active_players=active_players,
        last_n_games=last_n_games,
        todays_opponent=todays_opponent,
        todays_players=todays_players,
        team_id=team_id,
        position=position,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Test basic functionality
    print("Testing FantasyWidget endpoint...")

    # Test 1: Basic fetch
    json_response = get_fantasy_widget()
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")

    # Test 2: With DataFrame output
    json_response, dataframes = get_fantasy_widget(return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")

    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")

    print("FantasyWidget endpoint test completed.")

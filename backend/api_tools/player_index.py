"""
Handles fetching and processing player index data
from the PlayerIndex endpoint.
Provides both JSON and DataFrame outputs with CSV caching.

The PlayerIndex endpoint provides a comprehensive directory of all players (575+ players)
with detailed information including:
- Player details: ID, names, slug
- Team info: team name, city, abbreviation
- Physical stats: height, weight, position, jersey number
- Background: college, country, draft information
- Career stats: points, rebounds, assists averages
- Career span: from/to years
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple
from functools import lru_cache

from nba_api.stats.endpoints import playerindex
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
PLAYER_INDEX_CACHE_SIZE = 32

# Valid parameter sets
VALID_LEAGUE_IDS: Set[str] = {"00", "10", "20"}  # NBA, WNBA, G-League
VALID_POSITIONS: Set[str] = {"F", "C", "G", "F-C", "F-G", "G-F", "C-F"}
VALID_ACTIVE_FLAGS: Set[str] = {"Y", "N"}
VALID_ALLSTAR_FLAGS: Set[str] = {"Y", "N"}
VALID_HISTORICAL_FLAGS: Set[str] = {"Y", "N"}

# --- Cache Directory Setup ---
PLAYER_INDEX_CSV_DIR = get_cache_dir("player_index")

# Ensure cache directories exist
os.makedirs(PLAYER_INDEX_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_player_index(
    league_id: str = "00",
    season: str = CURRENT_NBA_SEASON,
    active: Optional[str] = None,
    allstar: Optional[str] = None,
    historical: Optional[str] = None,
    team_id: Optional[str] = None,
    position: Optional[str] = None
) -> str:
    """
    Generates a file path for saving player index DataFrame.

    Args:
        league_id: League ID (default: "00" for NBA)
        season: Season in YYYY-YY format
        active: Active flag filter (optional)
        allstar: All-star flag filter (optional)
        historical: Historical flag filter (optional)
        team_id: Team ID filter (optional)
        position: Position filter (optional)

    Returns:
        Path to the CSV file
    """
    # Create a filename based on the parameters
    filename_parts = [
        f"player_index_league{league_id}",
        f"season{season}"
    ]

    # Add optional filters to filename
    if active:
        filename_parts.append(f"active{active}")
    if allstar:
        filename_parts.append(f"allstar{allstar}")
    if historical:
        filename_parts.append(f"hist{historical}")
    if team_id:
        filename_parts.append(f"team{team_id}")
    if position:
        filename_parts.append(f"pos{position}")

    filename = "_".join(filename_parts) + ".csv"

    return get_cache_file_path(filename, "player_index")

# --- Parameter Validation ---
def _validate_player_index_params(
    league_id: str,
    season: str,
    active: Optional[str] = None,
    allstar: Optional[str] = None,
    historical: Optional[str] = None,
    position: Optional[str] = None
) -> Optional[str]:
    """Validates parameters for fetch_player_index_logic."""
    if league_id not in VALID_LEAGUE_IDS:
        return f"Invalid league_id: {league_id}. Valid options: {', '.join(VALID_LEAGUE_IDS)}"
    if not season or not _validate_season_format(season):
        return f"Invalid season format: {season}. Expected format: YYYY-YY"
    if active and active not in VALID_ACTIVE_FLAGS:
        return f"Invalid active flag: {active}. Valid options: {', '.join(VALID_ACTIVE_FLAGS)}"
    if allstar and allstar not in VALID_ALLSTAR_FLAGS:
        return f"Invalid allstar flag: {allstar}. Valid options: {', '.join(VALID_ALLSTAR_FLAGS)}"
    if historical and historical not in VALID_HISTORICAL_FLAGS:
        return f"Invalid historical flag: {historical}. Valid options: {', '.join(VALID_HISTORICAL_FLAGS)}"
    if position and position not in VALID_POSITIONS:
        return f"Invalid position: {position}. Valid options: {', '.join(VALID_POSITIONS)}"
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=PLAYER_INDEX_CACHE_SIZE)
def fetch_player_index_logic(
    league_id: str = "00",
    season: str = CURRENT_NBA_SEASON,
    active: Optional[str] = None,
    allstar: Optional[str] = None,
    historical: Optional[str] = None,
    team_id: Optional[str] = None,
    position: Optional[str] = None,
    college: Optional[str] = None,
    country: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player index data using the PlayerIndex endpoint.

    Provides DataFrame output capabilities and CSV caching.

    Args:
        league_id: League ID (default: "00" for NBA)
        season: Season in YYYY-YY format (default: current NBA season)
        active: Active players only flag (optional)
        allstar: All-star players only flag (optional)
        historical: Historical players flag (optional)
        team_id: Team ID filter (optional)
        position: Position filter (optional)
        college: College filter (optional)
        country: Country filter (optional)
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False:
            str: JSON string with player index data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    logger.info(
        f"Executing fetch_player_index_logic for League: {league_id}, Season: {season}, "
        f"Active: {active}, AllStar: {allstar}, Historical: {historical}, Team: {team_id}, "
        f"Position: {position}, College: {college}, Country: {country}, return_dataframe={return_dataframe}"
    )

    # Validate parameters
    validation_error = _validate_player_index_params(league_id, season, active, allstar, historical, position)
    if validation_error:
        logger.warning(f"Parameter validation failed for player index: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response

    # Check for cached CSV file
    csv_path = _get_csv_path_for_player_index(league_id, season, active, allstar, historical, team_id, position)
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
                logger.info(f"Loading player index from CSV: {csv_path}")
                # Read CSV with appropriate data types
                df = pd.read_csv(csv_path, encoding='utf-8')

                # Process for JSON response
                result_dict = {
                    "parameters": {
                        "league_id": league_id,
                        "season": season,
                        "active_nullable": active,
                        "allstar_nullable": allstar,
                        "historical_nullable": historical,
                        "team_id_nullable": team_id,
                        "player_position_abbreviation_nullable": position,
                        "college_nullable": college,
                        "country_nullable": country
                    },
                    "data_sets": {}
                }

                # Store the DataFrame
                dataframes["PlayerIndex"] = df
                result_dict["data_sets"]["PlayerIndex"] = _process_dataframe(df, single_row=False)

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
            "season": season
        }

        # Add optional parameters if provided
        if active:
            api_params["active_nullable"] = active
        if allstar:
            api_params["allstar_nullable"] = allstar
        if historical:
            api_params["historical_nullable"] = historical
        if team_id:
            api_params["team_id_nullable"] = team_id
        if position:
            api_params["player_position_abbreviation_nullable"] = position
        if college:
            api_params["college_nullable"] = college
        if country:
            api_params["country_nullable"] = country

        logger.debug(f"Calling PlayerIndex with parameters: {api_params}")
        player_index_endpoint = playerindex.PlayerIndex(**api_params)

        # Get data frames
        list_of_dataframes = player_index_endpoint.get_data_frames()

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
                data_set_name = f"PlayerIndex_{idx}" if idx > 0 else "PlayerIndex"

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
        logger.error(f"Unexpected error in fetch_player_index_logic: {e}", exc_info=True)
        error_response = format_response(error=f"Unexpected error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Public API Functions ---
def get_player_index(
    league_id: str = "00",
    season: str = CURRENT_NBA_SEASON,
    active: Optional[str] = None,
    allstar: Optional[str] = None,
    historical: Optional[str] = None,
    team_id: Optional[str] = None,
    position: Optional[str] = None,
    college: Optional[str] = None,
    country: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Public function to get player index data.

    Args:
        league_id: League ID (default: "00" for NBA)
        season: Season in YYYY-YY format (default: current NBA season)
        active: Active players only flag (optional)
        allstar: All-star players only flag (optional)
        historical: Historical players flag (optional)
        team_id: Team ID filter (optional)
        position: Position filter (optional)
        college: College filter (optional)
        country: Country filter (optional)
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False:
            str: JSON string with player index data or an error message
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames
    """
    return fetch_player_index_logic(
        league_id=league_id,
        season=season,
        active=active,
        allstar=allstar,
        historical=historical,
        team_id=team_id,
        position=position,
        college=college,
        country=country,
        return_dataframe=return_dataframe
    )

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Test basic functionality
    print("Testing PlayerIndex endpoint...")

    # Test 1: Basic fetch
    json_response = get_player_index()
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")

    # Test 2: With DataFrame output
    json_response, dataframes = get_player_index(return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")

    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")

    print("PlayerIndex endpoint test completed.")

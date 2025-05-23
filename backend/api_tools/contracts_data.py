"""
NBA player contract data API tools.
Fetches data from clean CSV files with NBA API ID mappings.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
from typing import Any, Dict, Optional, Union, List, Tuple
from functools import lru_cache
import pandas as pd

from ..utils.path_utils import get_cache_dir, get_cache_file_path

logger = logging.getLogger(__name__)

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

# Cache directory setup
CONTRACTS_CSV_DIR = get_cache_dir("contracts")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CONTRACTS_CSV = os.path.join(DATA_DIR, "contracts_clean.csv")

def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """Saves a DataFrame to a CSV file."""
    try:
        df.to_csv(file_path, index=False)
        logger.info(f"Saved DataFrame to CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)

def _load_contracts_data() -> pd.DataFrame:
    """Load the clean contracts CSV data."""
    if not os.path.exists(CONTRACTS_CSV):
        raise FileNotFoundError(f"Clean contracts file not found: {CONTRACTS_CSV}")

    df = pd.read_csv(CONTRACTS_CSV)
    logger.info(f"Loaded {len(df)} contract records")
    return df

@lru_cache(maxsize=32)
def fetch_contracts_data_logic(
    player_id: Optional[int] = None,
    team_id: Optional[int] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches NBA player contract data with optional filtering.

    Args:
        player_id: Optional NBA API player ID to filter by
        team_id: Optional NBA API team ID to filter by
        return_dataframe: Whether to return DataFrame alongside JSON

    Returns:
        JSON string or tuple of (JSON string, DataFrames dict)
    """
    try:
        # Generate cache filename based on filters
        cache_parts = ["contracts"]
        if player_id:
            cache_parts.append(f"player_{player_id}")
        if team_id:
            cache_parts.append(f"team_{team_id}")

        cache_filename = "_".join(cache_parts) + ".csv"
        cache_path = get_cache_file_path(cache_filename, "contracts")

        # Try to load from cache first
        if os.path.exists(cache_path):
            try:
                df = pd.read_csv(cache_path)
                logger.info(f"Loaded cached contracts data: {len(df)} records")
            except Exception as e:
                logger.warning(f"Error reading cache, loading fresh data: {e}")
                df = _load_contracts_data()
        else:
            df = _load_contracts_data()

            # Apply filters
            if player_id:
                df = df[df['nba_player_id'] == player_id]
            if team_id:
                df = df[df['nba_team_id'] == team_id]

            # Cache the filtered results
            _save_dataframe_to_csv(df, cache_path)

        # Process data for JSON response
        data_sets = {
            "contracts": _process_dataframe(df)
        }

        response_data = {
            "data_sets": data_sets,
            "parameters": {
                "player_id": player_id,
                "team_id": team_id
            }
        }

        json_response = format_response(response_data)

        if return_dataframe:
            dataframes = {"contracts": df}
            return json_response, dataframes

        return json_response

    except Exception as e:
        error_msg = f"Error fetching contracts data: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return format_response(error=error_msg)

def get_player_contract(player_id: int, return_dataframe: bool = False) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Gets contract information for a specific player.

    Args:
        player_id: NBA API player ID
        return_dataframe: Whether to return DataFrame alongside JSON

    Returns:
        JSON string or tuple of (JSON string, DataFrames dict)
    """
    return fetch_contracts_data_logic(player_id=player_id, return_dataframe=return_dataframe)

def get_team_payroll(team_id: int, return_dataframe: bool = False) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Gets payroll summary for a team.

    Args:
        team_id: NBA API team ID
        return_dataframe: Whether to return DataFrame alongside JSON

    Returns:
        JSON string or tuple of (JSON string, DataFrames dict)
    """
    return fetch_contracts_data_logic(team_id=team_id, return_dataframe=return_dataframe)

def get_highest_paid_players(limit: int = 50, return_dataframe: bool = False) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Gets the highest paid players by guaranteed money.

    Args:
        limit: Maximum number of players to return
        return_dataframe: Whether to return DataFrame alongside JSON

    Returns:
        JSON string or tuple of (JSON string, DataFrames dict)
    """
    try:
        cache_filename = f"highest_paid_players_limit_{limit}.csv"
        cache_path = get_cache_file_path(cache_filename, "contracts")

        # Try to load from cache first
        if os.path.exists(cache_path):
            try:
                df = pd.read_csv(cache_path)
                logger.info(f"Loaded cached highest paid players: {len(df)} records")
            except Exception as e:
                logger.warning(f"Error reading cache, loading fresh data: {e}")
                df = _load_contracts_data()
                # Filter and sort
                df = df[df['Guaranteed'].notna()].sort_values('Guaranteed', ascending=False).head(limit)
                _save_dataframe_to_csv(df, cache_path)
        else:
            df = _load_contracts_data()
            # Filter and sort
            df = df[df['Guaranteed'].notna()].sort_values('Guaranteed', ascending=False).head(limit)
            _save_dataframe_to_csv(df, cache_path)

        # Process data for JSON response
        data_sets = {
            "highest_paid_players": _process_dataframe(df)
        }

        response_data = {
            "data_sets": data_sets,
            "parameters": {
                "limit": limit
            }
        }

        json_response = format_response(response_data)

        if return_dataframe:
            dataframes = {"highest_paid_players": df}
            return json_response, dataframes

        return json_response

    except Exception as e:
        error_msg = f"Error getting highest paid players: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return format_response(error=error_msg)

def search_player_contracts(player_name: str, return_dataframe: bool = False) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Search for player contracts by name.

    Args:
        player_name: Player name to search for (partial matches allowed)
        return_dataframe: Whether to return DataFrame alongside JSON

    Returns:
        JSON string or tuple of (JSON string, DataFrames dict)
    """
    try:
        df = _load_contracts_data()

        # Search for players with names containing the search term
        mask = df['Player'].str.contains(player_name, case=False, na=False)
        df_filtered = df[mask]

        # Sort by guaranteed money descending
        df_filtered = df_filtered.sort_values('Guaranteed', ascending=False, na_position='last')

        # Process data for JSON response
        data_sets = {
            "player_contracts": _process_dataframe(df_filtered)
        }

        response_data = {
            "data_sets": data_sets,
            "parameters": {
                "player_name": player_name
            }
        }

        json_response = format_response(response_data)

        if return_dataframe:
            dataframes = {"player_contracts": df_filtered}
            return json_response, dataframes

        return json_response

    except Exception as e:
        error_msg = f"Error searching player contracts: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return format_response(error=error_msg)

if __name__ == "__main__":
    # Test basic functionality
    print("Testing Contracts Data endpoint...")

    # Test 1: Basic fetch
    json_response = fetch_contracts_data_logic()
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")

    # Test 2: With DataFrame output
    json_response, dataframes = fetch_contracts_data_logic(return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")

    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")

    print("Contracts Data endpoint test completed.")

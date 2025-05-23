"""
NBA free agent data API tools.
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
FREE_AGENTS_CSV_DIR = get_cache_dir("free_agents")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FREE_AGENTS_CSV = os.path.join(DATA_DIR, "free_agents_clean.csv")

def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """Saves a DataFrame to a CSV file."""
    try:
        df.to_csv(file_path, index=False)
        logger.info(f"Saved DataFrame to CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)

def _load_free_agents_data() -> pd.DataFrame:
    """Load the clean free agents CSV data."""
    if not os.path.exists(FREE_AGENTS_CSV):
        raise FileNotFoundError(f"Clean free agents file not found: {FREE_AGENTS_CSV}")

    df = pd.read_csv(FREE_AGENTS_CSV)
    logger.info(f"Loaded {len(df)} free agent records")
    return df

@lru_cache(maxsize=32)
def fetch_free_agents_data_logic(
    player_id: Optional[int] = None,
    team_id: Optional[int] = None,
    position: Optional[str] = None,
    free_agent_type: Optional[str] = None,
    min_ppg: Optional[float] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches NBA free agent data with optional filtering.

    Args:
        player_id: Optional NBA API player ID to filter by
        team_id: Optional NBA API team ID to filter by (old team)
        position: Optional position to filter by (G, F, C, etc.)
        free_agent_type: Optional free agent type (ufa, rfa)
        min_ppg: Optional minimum PPG to filter by
        return_dataframe: Whether to return DataFrame alongside JSON

    Returns:
        JSON string or tuple of (JSON string, DataFrames dict)
    """
    try:
        # Generate cache filename based on filters
        cache_parts = ["free_agents"]
        if player_id:
            cache_parts.append(f"player_{player_id}")
        if team_id:
            cache_parts.append(f"team_{team_id}")
        if position:
            cache_parts.append(f"pos_{position}")
        if free_agent_type:
            cache_parts.append(f"type_{free_agent_type}")
        if min_ppg:
            cache_parts.append(f"minppg_{min_ppg}")

        cache_filename = "_".join(cache_parts) + ".csv"
        cache_path = get_cache_file_path(cache_filename, "free_agents")

        # Try to load from cache first
        if os.path.exists(cache_path):
            try:
                df = pd.read_csv(cache_path)
                logger.info(f"Loaded cached free agents data: {len(df)} records")
            except Exception as e:
                logger.warning(f"Error reading cache, loading fresh data: {e}")
                df = _load_free_agents_data()
        else:
            df = _load_free_agents_data()

            # Apply filters
            if player_id:
                df = df[df['nba_player_id'] == player_id]
            if team_id:
                df = df[df['nba_old_team_id'] == team_id]
            if position:
                df = df[df['position'].str.contains(position, case=False, na=False)]
            if free_agent_type:
                df = df[df['type'] == free_agent_type]
            if min_ppg is not None:
                df = df[df['PPG'] >= min_ppg]

            # Cache the filtered results
            _save_dataframe_to_csv(df, cache_path)

        # Process data for JSON response
        data_sets = {
            "free_agents": _process_dataframe(df)
        }

        response_data = {
            "data_sets": data_sets,
            "parameters": {
                "player_id": player_id,
                "team_id": team_id,
                "position": position,
                "free_agent_type": free_agent_type,
                "min_ppg": min_ppg
            }
        }

        json_response = format_response(response_data)

        if return_dataframe:
            dataframes = {"free_agents": df}
            return json_response, dataframes

        return json_response

    except Exception as e:
        error_msg = f"Error fetching free agents data: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return format_response(error=error_msg)

def get_free_agent_info(player_id: int, return_dataframe: bool = False) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Gets free agent information for a specific player.

    Args:
        player_id: NBA API player ID
        return_dataframe: Whether to return DataFrame alongside JSON

    Returns:
        JSON string or tuple of (JSON string, DataFrames dict)
    """
    return fetch_free_agents_data_logic(player_id=player_id, return_dataframe=return_dataframe)

def get_team_free_agents(team_id: int, return_dataframe: bool = False) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Gets all free agents who previously played for a team.

    Args:
        team_id: NBA API team ID
        return_dataframe: Whether to return DataFrame alongside JSON

    Returns:
        JSON string or tuple of (JSON string, DataFrames dict)
    """
    return fetch_free_agents_data_logic(team_id=team_id, return_dataframe=return_dataframe)

def get_top_free_agents(
    position: Optional[str] = None,
    free_agent_type: Optional[str] = None,
    limit: int = 50,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Gets top free agents ranked by PPG.

    Args:
        position: Optional position filter
        free_agent_type: Optional free agent type filter
        limit: Maximum number of results to return
        return_dataframe: Whether to return DataFrame alongside JSON

    Returns:
        JSON string or tuple of (JSON string, DataFrames dict)
    """
    try:
        cache_parts = ["top_free_agents"]
        if position:
            cache_parts.append(f"pos_{position}")
        if free_agent_type:
            cache_parts.append(f"type_{free_agent_type}")
        cache_parts.append(f"limit_{limit}")

        cache_filename = "_".join(cache_parts) + ".csv"
        cache_path = get_cache_file_path(cache_filename, "free_agents")

        # Try to load from cache first
        if os.path.exists(cache_path):
            try:
                df = pd.read_csv(cache_path)
                logger.info(f"Loaded cached top free agents: {len(df)} records")
            except Exception as e:
                logger.warning(f"Error reading cache, loading fresh data: {e}")
                df = _load_free_agents_data()
                # Apply filters and sort
                if position:
                    df = df[df['position'].str.contains(position, case=False, na=False)]
                if free_agent_type:
                    df = df[df['type'] == free_agent_type]
                df = df.sort_values('PPG', ascending=False).head(limit)
                _save_dataframe_to_csv(df, cache_path)
        else:
            df = _load_free_agents_data()
            # Apply filters and sort
            if position:
                df = df[df['position'].str.contains(position, case=False, na=False)]
            if free_agent_type:
                df = df[df['type'] == free_agent_type]
            df = df.sort_values('PPG', ascending=False).head(limit)
            _save_dataframe_to_csv(df, cache_path)

        # Process data for JSON response
        data_sets = {
            "top_free_agents": _process_dataframe(df)
        }

        response_data = {
            "data_sets": data_sets,
            "parameters": {
                "position": position,
                "free_agent_type": free_agent_type,
                "limit": limit
            }
        }

        json_response = format_response(response_data)

        if return_dataframe:
            dataframes = {"top_free_agents": df}
            return json_response, dataframes

        return json_response

    except Exception as e:
        error_msg = f"Error getting top free agents: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return format_response(error=error_msg)

def search_free_agents(player_name: str, return_dataframe: bool = False) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Search for free agents by name.

    Args:
        player_name: Player name to search for (partial matches allowed)
        return_dataframe: Whether to return DataFrame alongside JSON

    Returns:
        JSON string or tuple of (JSON string, DataFrames dict)
    """
    try:
        df = _load_free_agents_data()

        # Search for players with names containing the search term
        mask = df['playerDisplayName'].str.contains(player_name, case=False, na=False)
        df_filtered = df[mask]

        # Sort by PPG descending
        df_filtered = df_filtered.sort_values('PPG', ascending=False, na_position='last')

        # Process data for JSON response
        data_sets = {
            "free_agent_search": _process_dataframe(df_filtered)
        }

        response_data = {
            "data_sets": data_sets,
            "parameters": {
                "player_name": player_name
            }
        }

        json_response = format_response(response_data)

        if return_dataframe:
            dataframes = {"free_agent_search": df_filtered}
            return json_response, dataframes

        return json_response

    except Exception as e:
        error_msg = f"Error searching free agents: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return format_response(error=error_msg)

if __name__ == "__main__":
    # Test basic functionality
    print("Testing Free Agents Data endpoint...")

    # Test 1: Basic fetch
    json_response = fetch_free_agents_data_logic()
    data = json.loads(json_response)
    print(f"Basic test - Data sets: {list(data.get('data_sets', {}).keys())}")

    # Test 2: With DataFrame output
    json_response, dataframes = fetch_free_agents_data_logic(return_dataframe=True)
    data = json.loads(json_response)
    print(f"DataFrame test - DataFrames: {list(dataframes.keys())}")

    for name, df in dataframes.items():
        print(f"DataFrame '{name}' shape: {df.shape}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample data: {df.head(1).to_dict('records')}")

    print("Free Agents Data endpoint test completed.")

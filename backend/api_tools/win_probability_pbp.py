"""
Handles fetching win probability play-by-play data for NBA games.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import os
import logging
import json
from typing import Optional, List, Dict, Any, Set, Union, Tuple
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import winprobabilitypbp
from nba_api.stats.library.parameters import RunType
from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response
)
from ..utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
WIN_PROBABILITY_PBP_CACHE_SIZE = 64

# --- Cache Directory Setup ---
WIN_PROBABILITY_PBP_CSV_DIR = get_cache_dir("win_probability_pbp")

# Validation sets for parameters
_VALID_RUN_TYPES: Set[str] = {
    getattr(RunType, attr) 
    for attr in dir(RunType) 
    if not attr.startswith('_') and isinstance(getattr(RunType, attr), str)
}

# --- Helper Functions for CSV Caching ---
def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves a DataFrame to a CSV file.

    Args:
        df: DataFrame to save
        file_path: Path to save the CSV file
    """
    try:
        df.to_csv(file_path, index=False)
        logger.info(f"Saved DataFrame to CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)

def _get_csv_path_for_win_probability_pbp(
    game_id: str,
    run_type: str
) -> str:
    """
    Generates a file path for saving win probability PBP DataFrame as CSV.

    Args:
        game_id: The game ID
        run_type: The run type (e.g., 'default', 'each second', 'each poss')

    Returns:
        Path to the CSV file
    """
    # Clean run type for filename
    clean_run_type = run_type.replace(" ", "_").lower()

    return get_cache_file_path(
        f"game_{game_id}_win_prob_pbp_{clean_run_type}.csv",
        "win_probability_pbp"
    )

# --- Helper for Parameter Validation ---
def _validate_win_probability_pbp_params(
    game_id: str,
    run_type: str
) -> Optional[str]:
    """Validates parameters for win probability PBP function."""
    if not game_id or not isinstance(game_id, str):
        return "Invalid game_id. Must be a non-empty string."
    if run_type not in _VALID_RUN_TYPES:
        return f"Invalid run_type '{run_type}'. Valid options: {', '.join(list(_VALID_RUN_TYPES))}"
    return None

# --- Logic Functions ---
@lru_cache(maxsize=WIN_PROBABILITY_PBP_CACHE_SIZE)
def fetch_win_probability_pbp_logic(
    game_id: str,
    run_type: str = RunType.default,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches win probability play-by-play data for a specific NBA game.
    Provides DataFrame output capabilities.

    Args:
        game_id (str): The NBA game ID (e.g., "0022300061").
        run_type (str, optional): The type of run data to fetch. Defaults to "default".
                                 Options: "default", "each second", "each poss"
        return_dataframe (bool, optional): Whether to return DataFrames along with the JSON response.
                                          Defaults to False.

    Returns:
        If return_dataframe=False:
            str: A JSON string containing the win probability data or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
            and a dictionary of DataFrames with keys for different data sets.
    """
    try:
        # Validate parameters
        validation_error = _validate_win_probability_pbp_params(game_id, run_type)
        if validation_error:
            error_response = format_response(error=validation_error)
            if return_dataframe:
                return error_response, {}
            return error_response

        # Make API call
        win_prob = winprobabilitypbp.WinProbabilityPBP(
            game_id=game_id,
            run_type=run_type
        )

        # Process data sets
        dataframes = {}
        
        def get_df_safe(dataset_name: str) -> pd.DataFrame:
            """Safely get DataFrame from dataset."""
            try:
                dataset = getattr(win_prob, dataset_name)
                return dataset.get_data_frame()
            except Exception as e:
                logger.warning(f"Could not retrieve {dataset_name}: {e}")
                return pd.DataFrame()

        # Get available data sets (using correct attribute names)
        win_prob_pbp_df = get_df_safe('win_prob_p_bp')  # Correct attribute name
        game_info_df = get_df_safe('game_info')

        if not win_prob_pbp_df.empty:
            dataframes['win_prob_pbp'] = win_prob_pbp_df
        if not game_info_df.empty:
            dataframes['game_info'] = game_info_df

        # Save to CSV if DataFrames are not empty
        if return_dataframe and dataframes:
            csv_path = _get_csv_path_for_win_probability_pbp(game_id, run_type)
            
            # Save the main win probability DataFrame
            if 'win_prob_pbp' in dataframes:
                _save_dataframe_to_csv(dataframes['win_prob_pbp'], csv_path)

        # Prepare response data
        response_data = {
            "game_id": game_id,
            "run_type": run_type,
            "parameters": {
                "game_id": game_id,
                "run_type": run_type
            },
            "data_sets": list(dataframes.keys()) if dataframes else [],
            "total_records": sum(len(df) for df in dataframes.values()) if dataframes else 0
        }

        # Add data to response if not returning DataFrames
        if not return_dataframe:
            for key, df in dataframes.items():
                response_data[key] = _process_dataframe(df, single_row=False) if not df.empty else []

        json_response = format_response(data=response_data)
        
        if return_dataframe:
            return json_response, dataframes
        return json_response

    except Exception as e:
        logger.error(f"Error fetching win probability PBP for game {game_id}: {e}", exc_info=True)
        error_response = format_response(error=f"API error: {str(e)}")
        if return_dataframe:
            return error_response, {}
        return error_response 
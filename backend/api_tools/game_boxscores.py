"""
Handles fetching and processing various types of game box score data
(Traditional, Advanced, Four Factors, Usage, Defensive, Summary)
using a generic helper function.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
from functools import lru_cache
import pandas as pd
from typing import Any, Dict, Optional, Type, Union, Tuple, List

from nba_api.stats.endpoints import (
    BoxScoreAdvancedV3,
    BoxScoreTraditionalV3,
    BoxScoreFourFactorsV3,
    BoxScoreUsageV3,
    BoxScoreDefensiveV2,
    BoxScoreSummaryV2,
    BoxScoreMiscV3,
    BoxScorePlayerTrackV3
)
from ..config import settings
from ..core.errors import Errors
from nba_api.stats.library.parameters import EndPeriod, EndRange, RangeType, StartPeriod, StartRange
from .utils import (
    _process_dataframe,
    format_response
)
from ..utils.validation import validate_game_id_format

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
GAME_BOXSCORE_CACHE_SIZE = 128
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
BOXSCORE_CSV_DIR = os.path.join(CSV_CACHE_DIR, "boxscores")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(BOXSCORE_CSV_DIR, exist_ok=True)

# --- Helper Functions for DataFrame Processing ---
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

def _get_csv_path_for_boxscore(game_id: str, boxscore_type: str, **kwargs) -> str:
    """
    Generates a file path for saving a boxscore DataFrame as CSV.

    Args:
        game_id: The game ID
        boxscore_type: The type of boxscore (e.g., 'traditional', 'advanced')
        **kwargs: Additional parameters to include in the filename

    Returns:
        Path to the CSV file
    """
    # Create a string with the parameters
    params_str = ""
    if kwargs:
        params_str = "_" + "_".join(f"{k}_{v}" for k, v in kwargs.items() if v != 0)

    filename = f"{game_id}_{boxscore_type}{params_str}.csv"
    return os.path.join(BOXSCORE_CSV_DIR, filename)

def _get_dataframes_from_endpoint(
    endpoint_instance: Any,
    dataset_mapping: Dict[str, str]
) -> Dict[str, pd.DataFrame]:
    """
    Extracts DataFrames from an endpoint instance based on the dataset mapping.

    Args:
        endpoint_instance: The NBA API endpoint instance
        dataset_mapping: Mapping of output keys to dataset attribute names

    Returns:
        Dictionary of DataFrames with output keys as keys
    """
    dataframes = {}
    for output_key, dataset_attr_name in dataset_mapping.items():
        if not hasattr(endpoint_instance, dataset_attr_name):
            logger.error(f"Dataset attribute '{dataset_attr_name}' not found on endpoint instance.")
            dataframes[output_key] = pd.DataFrame()
            continue

        dataset_obj = getattr(endpoint_instance, dataset_attr_name)
        if not hasattr(dataset_obj, 'get_data_frame'):
            logger.error(f"Dataset attribute '{dataset_attr_name}' does not have 'get_data_frame' method.")
            dataframes[output_key] = pd.DataFrame()
            continue

        df = dataset_obj.get_data_frame()
        dataframes[output_key] = df

    return dataframes

# --- Generic Helper Function ---
def _fetch_boxscore_data_generic(
    game_id: str,
    endpoint_class: Type[Any], # Using Type[Any] as a placeholder for specific endpoint types
    dataset_mapping: Dict[str, str], # e.g., {"players": "player_stats", "teams": "team_stats"}
    error_constants: Dict[str, str], # e.g., {"api": Errors.BOXSCORE_API, "processing": Errors.PROCESSING_ERROR}
    endpoint_name_for_logging: str,
    additional_params_for_response: Optional[Dict[str, Any]] = None,
    return_dataframe: bool = False,
    **kwargs: Any # Parameters for the endpoint_class constructor
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Generic helper to fetch and process box score data from various nba_api endpoints.

    Args:
        game_id: The ID of the game to fetch data for
        endpoint_class: The NBA API endpoint class to use
        dataset_mapping: Mapping of output keys to dataset attribute names
        error_constants: Error message constants for different error types
        endpoint_name_for_logging: Name of the endpoint for logging purposes
        additional_params_for_response: Additional parameters to include in the response
        return_dataframe: Whether to return DataFrames along with the JSON response
        **kwargs: Additional parameters for the endpoint class constructor

    Returns:
        If return_dataframe=False: JSON string containing the boxscore data
        If return_dataframe=True: Tuple of (JSON string, Dictionary of DataFrames)
    """
    logger.info(f"Executing generic boxscore fetch for {endpoint_name_for_logging}, game ID: {game_id}, params: {kwargs}, return_dataframe: {return_dataframe}")

    if not game_id:
        error_response = format_response(error=Errors.GAME_ID_EMPTY)
        if return_dataframe:
            return error_response, {}
        return error_response

    if not validate_game_id_format(game_id):
        error_response = format_response(error=Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id))
        if return_dataframe:
            return error_response, {}
        return error_response

    try:
        endpoint_instance = endpoint_class(game_id=game_id, **kwargs, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
        logger.debug(f"{endpoint_name_for_logging} API call successful for {game_id}")

        # Extract DataFrames from the endpoint
        dataframes = _get_dataframes_from_endpoint(endpoint_instance, dataset_mapping)

        # Process data for JSON response
        processed_data: Dict[str, Any] = {}
        all_datasets_valid = True

        for output_key, df in dataframes.items():
            if df.empty:
                logger.warning(f"Empty DataFrame for '{output_key}' in {endpoint_name_for_logging} of game {game_id}.")
                processed_data[output_key] = []
                continue

            # Process DataFrame for JSON response
            data_list = _process_dataframe(df, single_row=False)

            if data_list is None:  # _process_dataframe returns None on internal error
                logger.error(f"DataFrame processing failed for '{output_key}' in {endpoint_name_for_logging} of game {game_id}.")
                all_datasets_valid = False
                processed_data[output_key] = []
            else:
                processed_data[output_key] = data_list

        # Check if essential datasets failed
        if not all_datasets_valid and any(val == [] for key, val in processed_data.items()
                                         if dataset_mapping.get(key) != "team_starter_bench_stats"):
            error_msg = error_constants["processing"].format(error=f"{endpoint_name_for_logging} data for game {game_id}")
            error_response = format_response(error=error_msg)
            if return_dataframe:
                return error_response, dataframes
            return error_response

        # Prepare the result
        result = {"game_id": game_id, **processed_data}
        if additional_params_for_response:
            result["parameters"] = additional_params_for_response

        # Save DataFrames to CSV if requested
        if return_dataframe:
            boxscore_type = endpoint_name_for_logging.replace("BoxScore", "").replace("V2", "").replace("V3", "").lower()
            for output_key, df in dataframes.items():
                if not df.empty:
                    csv_path = _get_csv_path_for_boxscore(game_id, f"{boxscore_type}_{output_key}", **kwargs)
                    _save_dataframe_to_csv(df, csv_path)

        logger.info(f"Generic boxscore fetch for {endpoint_name_for_logging} completed for game {game_id}")
        json_response = format_response(result)

        if return_dataframe:
            return json_response, dataframes
        return json_response

    except IndexError as ie:  # Specific catch for endpoints that might return empty data sets causing index errors
        logger.warning(f"IndexError during {endpoint_name_for_logging} processing for game {game_id}: {ie}. Data likely unavailable.", exc_info=False)
        error_msg = Errors.DATA_NOT_FOUND + f" ({endpoint_name_for_logging} data might be unavailable for game {game_id} with current filters)"
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response

    except Exception as e:
        logger.error(f"Error fetching {endpoint_name_for_logging} for game {game_id}: {str(e)}", exc_info=True)
        error_msg = error_constants["api"].format(game_id=game_id, error=str(e))
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response


# --- Public Fetch Logic Functions ---

@lru_cache(maxsize=GAME_BOXSCORE_CACHE_SIZE)
def fetch_boxscore_traditional_logic(
    game_id: str,
    start_period: int = StartPeriod.default,
    end_period: int = EndPeriod.default,
    start_range: int = StartRange.default,
    end_range: int = EndRange.default,
    range_type: int = RangeType.default,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Traditional Box Score data (V3) for a given game_id.

    Args:
        game_id: The ID of the game to fetch data for
        start_period: Starting period number (0 for full game)
        end_period: Ending period number (0 for full game)
        start_range: Starting range in seconds
        end_range: Ending range in seconds
        range_type: Type of range (0 for full game)
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False: JSON string containing the boxscore data
        If return_dataframe=True: Tuple of (JSON string, Dictionary of DataFrames)
    """
    return _fetch_boxscore_data_generic(
        game_id=game_id,
        endpoint_class=BoxScoreTraditionalV3,
        dataset_mapping={
            "teams": "team_stats",
            "players": "player_stats",
            "starters_bench": "team_starter_bench_stats"
        },
        error_constants={"api": Errors.BOXSCORE_API, "processing": Errors.PROCESSING_ERROR},
        endpoint_name_for_logging="BoxScoreTraditionalV3",
        additional_params_for_response={
            "start_period": start_period, "end_period": end_period,
            "start_range": start_range, "end_range": end_range,
            "range_type": range_type, "note": "Using BoxScoreTraditionalV3"
        },
        return_dataframe=return_dataframe,
        # Kwargs for BoxScoreTraditionalV3 constructor
        start_period=start_period, end_period=end_period,
        start_range=start_range, end_range=end_range, range_type=range_type
    )

@lru_cache(maxsize=GAME_BOXSCORE_CACHE_SIZE)
def fetch_boxscore_advanced_logic(
    game_id: str,
    start_period: int = StartPeriod.default,
    end_period: int = EndPeriod.default,
    start_range: int = StartRange.default,
    end_range: int = EndRange.default,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Advanced Box Score data (V3) for a given game_id.

    Args:
        game_id: The ID of the game to fetch data for
        start_period: Starting period number (0 for full game)
        end_period: Ending period number (0 for full game)
        start_range: Starting range in seconds
        end_range: Ending range in seconds
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False: JSON string containing the boxscore data
        If return_dataframe=True: Tuple of (JSON string, Dictionary of DataFrames)
    """
    return _fetch_boxscore_data_generic(
        game_id=game_id,
        endpoint_class=BoxScoreAdvancedV3,
        dataset_mapping={"player_stats": "player_stats", "team_stats": "team_stats"},
        error_constants={"api": Errors.BOXSCORE_ADVANCED_API, "processing": Errors.PROCESSING_ERROR},
        endpoint_name_for_logging="BoxScoreAdvancedV3",
        additional_params_for_response={
            "start_period": start_period, "end_period": end_period,
            "start_range": start_range, "end_range": end_range
        },
        return_dataframe=return_dataframe,
        start_period=start_period, end_period=end_period,
        start_range=start_range, end_range=end_range
    )

@lru_cache(maxsize=GAME_BOXSCORE_CACHE_SIZE)
def fetch_boxscore_four_factors_logic(
    game_id: str,
    start_period: int = StartPeriod.default,
    end_period: int = EndPeriod.default,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Four Factors Box Score data (V3) for a given game_id.

    Args:
        game_id: The ID of the game to fetch data for
        start_period: Starting period number (0 for full game)
        end_period: Ending period number (0 for full game)
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False: JSON string containing the boxscore data
        If return_dataframe=True: Tuple of (JSON string, Dictionary of DataFrames)
    """
    return _fetch_boxscore_data_generic(
        game_id=game_id,
        endpoint_class=BoxScoreFourFactorsV3,
        dataset_mapping={"player_stats": "player_stats", "team_stats": "team_stats"},
        error_constants={"api": Errors.BOXSCORE_FOURFACTORS_API, "processing": Errors.PROCESSING_ERROR},
        endpoint_name_for_logging="BoxScoreFourFactorsV3",
        additional_params_for_response={"start_period": start_period, "end_period": end_period},
        return_dataframe=return_dataframe,
        start_period=start_period, end_period=end_period
    )

@lru_cache(maxsize=GAME_BOXSCORE_CACHE_SIZE)
def fetch_boxscore_usage_logic(
    game_id: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Usage Box Score data (V3) for a given game_id.

    Args:
        game_id: The ID of the game to fetch data for
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False: JSON string containing the boxscore data
        If return_dataframe=True: Tuple of (JSON string, Dictionary of DataFrames)
    """
    return _fetch_boxscore_data_generic(
        game_id=game_id,
        endpoint_class=BoxScoreUsageV3,
        dataset_mapping={"player_usage_stats": "player_stats", "team_usage_stats": "team_stats"},
        error_constants={"api": Errors.BOXSCORE_USAGE_API, "processing": Errors.PROCESSING_ERROR},
        endpoint_name_for_logging="BoxScoreUsageV3",
        return_dataframe=return_dataframe
        # No additional constructor kwargs beyond game_id for BoxScoreUsageV3 apart from defaults
    )

@lru_cache(maxsize=GAME_BOXSCORE_CACHE_SIZE)
def fetch_boxscore_defensive_logic(
    game_id: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Defensive Box Score data (V2) for a given game_id.

    Args:
        game_id: The ID of the game to fetch data for
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False: JSON string containing the boxscore data
        If return_dataframe=True: Tuple of (JSON string, Dictionary of DataFrames)
    """
    return _fetch_boxscore_data_generic(
        game_id=game_id,
        endpoint_class=BoxScoreDefensiveV2,
        dataset_mapping={"player_defensive_stats": "player_stats", "team_defensive_stats": "team_stats"},
        error_constants={"api": Errors.BOXSCORE_DEFENSIVE_API, "processing": Errors.PROCESSING_ERROR},
        endpoint_name_for_logging="BoxScoreDefensiveV2",
        return_dataframe=return_dataframe
        # No additional constructor kwargs beyond game_id for BoxScoreDefensiveV2
    )

@lru_cache(maxsize=GAME_BOXSCORE_CACHE_SIZE)
def fetch_boxscore_summary_logic(
    game_id: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches the comprehensive summary box score (V2) for a given game_id.

    Args:
        game_id: The ID of the game to fetch data for
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False: JSON string containing the boxscore data
        If return_dataframe=True: Tuple of (JSON string, Dictionary of DataFrames)
    """
    return _fetch_boxscore_data_generic(
        game_id=game_id,
        endpoint_class=BoxScoreSummaryV2,
        dataset_mapping={
            "available_video": "available_video",
            "game_info": "game_info",
            "game_summary": "game_summary",
            "inactive_players": "inactive_players",
            "last_meeting": "last_meeting",
            "line_score": "line_score",
            "officials": "officials",
            "other_stats": "other_stats",
            "season_series": "season_series"
        },
        error_constants={"api": Errors.BOXSCORE_SUMMARY_API, "processing": Errors.PROCESSING_ERROR},
        endpoint_name_for_logging="BoxScoreSummaryV2",
        return_dataframe=return_dataframe
        # No additional constructor kwargs beyond game_id for BoxScoreSummaryV2
    )

@lru_cache(maxsize=GAME_BOXSCORE_CACHE_SIZE)
def fetch_boxscore_misc_logic(
    game_id: str,
    start_period: int = StartPeriod.default,
    end_period: int = EndPeriod.default,
    start_range: int = StartRange.default,
    end_range: int = EndRange.default,
    range_type: int = RangeType.default,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Miscellaneous Box Score data (V3) for a given game_id.

    Args:
        game_id: The ID of the game to fetch data for
        start_period: Starting period number (0 for full game)
        end_period: Ending period number (0 for full game)
        start_range: Starting range in seconds
        end_range: Ending range in seconds
        range_type: Type of range (0 for full game)
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False: JSON string containing the boxscore data
        If return_dataframe=True: Tuple of (JSON string, Dictionary of DataFrames)
    """
    return _fetch_boxscore_data_generic(
        game_id=game_id,
        endpoint_class=BoxScoreMiscV3,
        dataset_mapping={"player_stats": "player_stats", "team_stats": "team_stats"},
        error_constants={"api": Errors.BOXSCORE_API, "processing": Errors.PROCESSING_ERROR},
        endpoint_name_for_logging="BoxScoreMiscV3",
        additional_params_for_response={
            "start_period": start_period, "end_period": end_period,
            "start_range": start_range, "end_range": end_range,
            "range_type": range_type
        },
        return_dataframe=return_dataframe,
        start_period=start_period, end_period=end_period,
        start_range=start_range, end_range=end_range, range_type=range_type
    )

@lru_cache(maxsize=GAME_BOXSCORE_CACHE_SIZE)
def fetch_boxscore_playertrack_logic(
    game_id: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Player Tracking Box Score data (V3) for a given game_id.

    Args:
        game_id: The ID of the game to fetch data for
        return_dataframe: Whether to return DataFrames along with the JSON response

    Returns:
        If return_dataframe=False: JSON string containing the boxscore data
        If return_dataframe=True: Tuple of (JSON string, Dictionary of DataFrames)
    """
    return _fetch_boxscore_data_generic(
        game_id=game_id,
        endpoint_class=BoxScorePlayerTrackV3,
        dataset_mapping={"player_stats": "player_stats", "team_stats": "team_stats"},
        error_constants={"api": Errors.BOXSCORE_API, "processing": Errors.PROCESSING_ERROR},
        endpoint_name_for_logging="BoxScorePlayerTrackV3",
        return_dataframe=return_dataframe
    )
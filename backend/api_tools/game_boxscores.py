import logging
from functools import lru_cache
from nba_api.stats.endpoints import (
    BoxScoreAdvancedV3,
    BoxScoreTraditionalV3,
    BoxScoreFourFactorsV3,
    BoxScoreUsageV3,
    BoxScoreDefensiveV2
)
from backend.config import settings
from backend.core.errors import Errors
from nba_api.stats.library.parameters import EndPeriod, EndRange, RangeType, StartPeriod, StartRange
from backend.api_tools.utils import (
    _process_dataframe,
    format_response
)
from backend.utils.validation import validate_game_id_format
from typing import Any, Dict, Optional
logger = logging.getLogger(__name__)


def _fetch_boxscore_data_generic(
    game_id: str,
    endpoint_class: Any, # Type[Endpoint] but Endpoint is not directly imported
    dataset_mapping: Dict[str, str], # e.g., {"players": "player_stats", "teams": "team_stats"}
    error_constants: Dict[str, str], # e.g., {"api": Errors.BOXSCORE_API, "processing": Errors.PROCESSING_ERROR}
    endpoint_name_for_logging: str,
    additional_params_for_response: Optional[Dict[str, Any]] = None,
    **kwargs: Any # Parameters for the endpoint_class constructor
) -> str:
    """
    Generic helper to fetch and process box score data from various nba_api endpoints.
    """
    logger.info(f"Executing generic boxscore fetch for {endpoint_name_for_logging}, game ID: {game_id}, params: {kwargs}")

    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)
    if not validate_game_id_format(game_id):
        return format_response(error=Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id))

    try:
        endpoint_instance = endpoint_class(game_id=game_id, **kwargs, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
        logger.debug(f"{endpoint_name_for_logging} API call successful for {game_id}")

        processed_data: Dict[str, Any] = {}
        all_datasets_valid = True
        for output_key, dataset_attr_name in dataset_mapping.items():
            if not hasattr(endpoint_instance, dataset_attr_name):
                logger.error(f"Dataset attribute '{dataset_attr_name}' not found on {endpoint_name_for_logging} instance for game {game_id}.")
                all_datasets_valid = False
                processed_data[output_key] = [] # Default to empty list if dataset is missing
                continue
            
            dataset_obj = getattr(endpoint_instance, dataset_attr_name)
            if not hasattr(dataset_obj, 'get_data_frame'):
                logger.error(f"Dataset attribute '{dataset_attr_name}' on {endpoint_name_for_logging} for game {game_id} does not have 'get_data_frame' method.")
                all_datasets_valid = False
                processed_data[output_key] = []
                continue

            df = dataset_obj.get_data_frame()
            # Determine if dataset is typically single row (e.g. career totals) or multiple (e.g. player stats per game)
            # For box scores, most datasets are multi-row (player/team stats).
            # If a specific dataset in a box score is always single (e.g. a summary object not yet encountered), this might need adjustment.
            # For now, assume all box score sub-datasets are multi-row unless explicitly known otherwise.
            # The _process_dataframe handles empty DFs correctly.
            data_list = _process_dataframe(df, single_row=False)
            
            if data_list is None: # _process_dataframe returns None on internal error
                logger.error(f"DataFrame processing failed for '{dataset_attr_name}' in {endpoint_name_for_logging} of game {game_id}.")
                all_datasets_valid = False
            processed_data[output_key] = data_list if data_list is not None else []

        if not all_datasets_valid and any(val == [] for key, val in processed_data.items() if dataset_mapping[key] != "team_starter_bench_stats"): # Check if essential datasets failed
            # Allow team_starter_bench_stats to be empty without failing the whole request if others are present
            # This condition might need refinement based on which datasets are truly essential for each boxscore type
            error_msg = error_constants["processing"].format(error=f"{endpoint_name_for_logging} data for game {game_id}")
            return format_response(error=error_msg)

        result = {"game_id": game_id, **processed_data}
        if additional_params_for_response:
            result["parameters"] = additional_params_for_response
        
        logger.info(f"Generic boxscore fetch for {endpoint_name_for_logging} completed for game {game_id}")
        return format_response(result)

    except IndexError as ie: # Specific catch for endpoints that might return empty data sets causing index errors
        logger.warning(f"IndexError during {endpoint_name_for_logging} processing for game {game_id}: {ie}. Data likely unavailable.", exc_info=False)
        error_msg = Errors.DATA_NOT_FOUND + f" ({endpoint_name_for_logging} data might be unavailable for game {game_id} with current filters)"
        return format_response(error=error_msg)
    except Exception as e:
        logger.error(f"Error fetching {endpoint_name_for_logging} for game {game_id}: {str(e)}", exc_info=True)
        error_msg = error_constants["api"].format(game_id=game_id, error=str(e))
        return format_response(error=error_msg)


@lru_cache(maxsize=128)
def fetch_boxscore_traditional_logic(
    game_id: str,
    start_period: int = StartPeriod.default,
    end_period: int = EndPeriod.default,
    start_range: int = StartRange.default,
    end_range: int = EndRange.default,
    range_type: int = RangeType.default
) -> str:
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
        # Kwargs for BoxScoreTraditionalV3 constructor
        start_period=start_period, end_period=end_period,
        start_range=start_range, end_range=end_range, range_type=range_type
    )

@lru_cache(maxsize=128)
def fetch_boxscore_advanced_logic(
    game_id: str,
    start_period: int = StartPeriod.default,
    end_period: int = EndPeriod.default,
    start_range: int = StartRange.default,
    end_range: int = EndRange.default
) -> str:
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
        start_period=start_period, end_period=end_period,
        start_range=start_range, end_range=end_range
    )

@lru_cache(maxsize=128)
def fetch_boxscore_four_factors_logic(
    game_id: str,
    start_period: int = StartPeriod.default,
    end_period: int = EndPeriod.default
) -> str:
    return _fetch_boxscore_data_generic(
        game_id=game_id,
        endpoint_class=BoxScoreFourFactorsV3,
        dataset_mapping={"player_stats": "player_stats", "team_stats": "team_stats"},
        error_constants={"api": Errors.BOXSCORE_FOURFACTORS_API, "processing": Errors.PROCESSING_ERROR},
        endpoint_name_for_logging="BoxScoreFourFactorsV3",
        additional_params_for_response={"start_period": start_period, "end_period": end_period},
        start_period=start_period, end_period=end_period
    )

@lru_cache(maxsize=128)
def fetch_boxscore_usage_logic(game_id: str) -> str:
    return _fetch_boxscore_data_generic(
        game_id=game_id,
        endpoint_class=BoxScoreUsageV3,
        dataset_mapping={"player_usage_stats": "player_stats", "team_usage_stats": "team_stats"},
        error_constants={"api": Errors.BOXSCORE_USAGE_API, "processing": Errors.PROCESSING_ERROR},
        endpoint_name_for_logging="BoxScoreUsageV3"
        # No additional constructor kwargs beyond game_id for BoxScoreUsageV3 apart from defaults
    )

@lru_cache(maxsize=128)
def fetch_boxscore_defensive_logic(game_id: str) -> str:
    return _fetch_boxscore_data_generic(
        game_id=game_id,
        endpoint_class=BoxScoreDefensiveV2,
        dataset_mapping={"player_defensive_stats": "player_stats", "team_defensive_stats": "team_stats"},
        error_constants={"api": Errors.BOXSCORE_DEFENSIVE_API, "processing": Errors.PROCESSING_ERROR},
        endpoint_name_for_logging="BoxScoreDefensiveV2"
        # No additional constructor kwargs beyond game_id for BoxScoreDefensiveV2
    )
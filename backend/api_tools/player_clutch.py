"""
Handles fetching and processing player clutch performance statistics
from the PlayerDashboardByClutch endpoint.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
from typing import Optional, Dict, Any, Set, Union, Tuple, List
from functools import lru_cache

from nba_api.stats.endpoints import playerdashboardbyclutch
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailed
)
import pandas as pd

from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)
from ..utils.validation import _validate_season_format, validate_date_format

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
PLAYER_CLUTCH_CACHE_SIZE = 64

_VALID_CLUTCH_SEASON_TYPES: Set[str] = {SeasonTypeAllStar.regular, SeasonTypeAllStar.playoffs, SeasonTypeAllStar.preseason}
_VALID_CLUTCH_PER_MODES: Set[str] = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
_VALID_CLUTCH_MEASURE_TYPES: Set[str] = {getattr(MeasureTypeDetailed, attr) for attr in dir(MeasureTypeDetailed) if not attr.startswith('_') and isinstance(getattr(MeasureTypeDetailed, attr), str)}
_VALID_Y_N_CLUTCH: Set[str] = {"Y", "N", ""} # Used for plus_minus, pace_adjust, rank

# --- Cache Directory Setup ---
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
PLAYER_CLUTCH_CSV_DIR = os.path.join(CSV_CACHE_DIR, "player_clutch")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(PLAYER_CLUTCH_CSV_DIR, exist_ok=True)

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

def _get_csv_path_for_player_clutch(
    player_name: str,
    season: str,
    season_type: str,
    dashboard_name: str
) -> str:
    """
    Generates a file path for saving player clutch DataFrame as CSV.

    Args:
        player_name: The player's name
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        dashboard_name: The name of the clutch dashboard

    Returns:
        Path to the CSV file
    """
    # Clean player name and dashboard name for filename
    clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()
    clean_season_type = season_type.replace(" ", "_").lower()
    clean_dashboard = dashboard_name.replace(" ", "_").lower()

    filename = f"{clean_player_name}_{season}_{clean_season_type}_{clean_dashboard}.csv"
    return os.path.join(PLAYER_CLUTCH_CSV_DIR, filename)

# --- Helper for Parameter Validation ---
def _validate_clutch_params(
    player_name: str, season: str, season_type: str, measure_type: str, per_mode: str,
    plus_minus: str, pace_adjust: str, rank: str, league_id: Optional[str],
    period: int, last_n_games: int, month: int, opponent_team_id: int,
    date_from_nullable: Optional[str], date_to_nullable: Optional[str]
) -> Optional[str]:
    """Validates parameters for fetch_player_clutch_stats_logic."""
    if not player_name or not player_name.strip():
        return Errors.PLAYER_NAME_EMPTY
    if not season or not _validate_season_format(season):
        return Errors.INVALID_SEASON_FORMAT.format(season=season)
    if date_from_nullable and not validate_date_format(date_from_nullable):
        return Errors.INVALID_DATE_FORMAT.format(date=date_from_nullable)
    if date_to_nullable and not validate_date_format(date_to_nullable):
        return Errors.INVALID_DATE_FORMAT.format(date=date_to_nullable)
    if season_type not in _VALID_CLUTCH_SEASON_TYPES:
        return Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_CLUTCH_SEASON_TYPES)[:5]))
    if per_mode not in _VALID_CLUTCH_PER_MODES:
        return Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_CLUTCH_PER_MODES)[:5]))
    if measure_type not in _VALID_CLUTCH_MEASURE_TYPES:
        return Errors.INVALID_MEASURE_TYPE.format(value=measure_type, options=", ".join(list(_VALID_CLUTCH_MEASURE_TYPES)[:5]))
    if plus_minus not in _VALID_Y_N_CLUTCH:
        return Errors.INVALID_PLUS_MINUS.format(value=plus_minus)
    if pace_adjust not in _VALID_Y_N_CLUTCH:
        return Errors.INVALID_PACE_ADJUST.format(value=pace_adjust)
    if rank not in _VALID_Y_N_CLUTCH:
        return Errors.INVALID_RANK.format(value=rank)
    if league_id is not None and not isinstance(league_id, str): # Basic check, can be expanded
        return Errors.INVALID_LEAGUE_ID_FORMAT.format(league_id=league_id)
    if not isinstance(period, int):
        return "Invalid type for period, must be int."
    if not isinstance(last_n_games, int):
        return "Invalid type for last_n_games, must be int."
    if not isinstance(month, int):
        return "Invalid type for month, must be int."
    if not isinstance(opponent_team_id, int):
        return "Invalid type for opponent_team_id, must be int."
    # Add more specific validation for other params if needed, e.g., enums for location, outcome etc.
    return None

# --- Main Logic Function ---
@lru_cache(maxsize=PLAYER_CLUTCH_CACHE_SIZE)
def fetch_player_clutch_stats_logic(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    measure_type: str = MeasureTypeDetailed.base,
    per_mode: str = PerModeDetailed.totals,
    league_id: Optional[str] = "00", # Corresponds to league_id_nullable, NBA default
    plus_minus: str = "N", # Y or N
    pace_adjust: str = "N", # Y or N
    rank: str = "N", # Y or N
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    period: int = 0,
    shot_clock_range_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player clutch performance statistics using the PlayerDashboardByClutch endpoint.
    The "clutch" aspect is inherent to the endpoint; parameters serve to filter these stats.
    Various clutch scenarios are returned as different data sets within the response.

    Provides DataFrame output capabilities and CSV caching for each data set.

    Args:
        player_name: Name or ID of the player.
        season: Season in YYYY-YY format. Defaults to current NBA season.
        season_type: Type of season (e.g., 'Regular Season', 'Playoffs'). Defaults to 'Regular Season'.
                     Corresponds to 'season_type_playoffs' API parameter.
        measure_type: Type of stats (e.g., 'Base', 'Advanced'). Defaults to 'Base'.
                      Corresponds to 'measure_type_detailed' API parameter.
        per_mode: Statistical mode (e.g., 'Totals', 'PerGame'). Defaults to 'Totals'.
                  Corresponds to 'per_mode_detailed' API parameter.
        league_id: League ID. Defaults to "00" (NBA). Corresponds to 'league_id_nullable'.
        plus_minus: Flag for plus-minus stats ("Y" or "N"). Defaults to "N".
        pace_adjust: Flag for pace adjustment ("Y" or "N"). Defaults to "N".
        rank: Flag for ranking ("Y" or "N"). Defaults to "N".
        last_n_games: Filter by last N games. Defaults to 0 (all games).
        month: Filter by month (1-12). Defaults to 0 (all months).
        opponent_team_id: Filter by opponent team ID. Defaults to 0 (all opponents).
        period: Filter by period (e.g., 1, 2, 3, 4 for quarters, 0 for all). Defaults to 0.
        shot_clock_range_nullable: Filter by shot clock range (e.g., '24-22', '4-0 Very Late').
        game_segment_nullable: Filter by game segment (e.g., 'First Half', 'Overtime').
        location_nullable: Filter by location ('Home' or 'Road').
        outcome_nullable: Filter by game outcome ('W' or 'L').
        vs_conference_nullable: Filter by opponent conference (e.g., 'East', 'West').
        vs_division_nullable: Filter by opponent division (e.g., 'Atlantic', 'Pacific').
        season_segment_nullable: Filter by season segment (e.g., 'Post All-Star').
        date_from_nullable: Start date filter (YYYY-MM-DD).
        date_to_nullable: End date filter (YYYY-MM-DD).
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string with clutch stats dashboards or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames, where keys are
                                               dashboard names (e.g., 'OverallPlayerDashboard').
    """
    logger.info(
        f"Executing fetch_player_clutch_stats_logic for: '{player_name}', Season: {season}, "
        f"Measure: {measure_type}, LeagueID: {league_id}, return_dataframe={return_dataframe}"
    )

    validation_error = _validate_clutch_params(
        player_name, season, season_type, measure_type, per_mode,
        plus_minus, pace_adjust, rank, league_id, period, last_n_games, month, opponent_team_id,
        date_from_nullable, date_to_nullable
    )
    if validation_error:
        logger.warning(f"Parameter validation failed for clutch stats: {validation_error}")
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, {}
        return error_response

    try:
        player_id_val, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching playerdashboardbyclutch for ID: {player_id_val}, Name: {player_actual_name} Season: {season}")

        # Prepare parameters to be passed to the API
        api_params = {
            "player_id": player_id_val,
            "season": season,
            "season_type_playoffs": season_type,
            "measure_type_detailed": measure_type,
            "per_mode_detailed": per_mode,
            "league_id_nullable": league_id,
            "plus_minus": plus_minus,
            "pace_adjust": pace_adjust,
            "rank": rank,
            "last_n_games": last_n_games,
            "month": month,
            "opponent_team_id": opponent_team_id,
            "period": period,
            "shot_clock_range_nullable": shot_clock_range_nullable,
            "game_segment_nullable": game_segment_nullable,
            "location_nullable": location_nullable,
            "outcome_nullable": outcome_nullable,
            "vs_conference_nullable": vs_conference_nullable,
            "vs_division_nullable": vs_division_nullable,
            "season_segment_nullable": season_segment_nullable,
            "date_from_nullable": date_from_nullable,
            "date_to_nullable": date_to_nullable,
        }
        
        # Filter out None values for nullable parameters, as the API expects them to be absent or have a valid value
        # The nba_api library handles empty strings for some nullable parameters, but None might cause issues.
        # Explicitly passing default values like 0 for ints if not provided, or relying on API defaults.
        filtered_api_params = {k: v for k, v in api_params.items() if v is not None or k in \
            ['last_n_games', 'month', 'opponent_team_id', 'period']} # Keep these even if 0


        logger.debug(f"Calling PlayerDashboardByClutch with parameters: {filtered_api_params}")
        clutch_endpoint = playerdashboardbyclutch.PlayerDashboardByClutch(**filtered_api_params)

        normalized_dict = clutch_endpoint.get_normalized_dict()
        # get_data_frames() returns a list of DataFrames in the order of the data sets
        list_of_dataframes = clutch_endpoint.get_data_frames()
        # get_normalized_dict().keys() gives the names in the same order usually
        data_set_names = list(normalized_dict.keys())

        result_dict: Dict[str, Any] = {
            "player_name": player_actual_name,
            "player_id": player_id_val,
            "parameters_used": filtered_api_params, 
            "data_sets": {}
        }
        
        dataframes_for_return: Dict[str, pd.DataFrame] = {}

        if len(data_set_names) != len(list_of_dataframes):
            logger.error(
                f"Mismatch between number of data set names ({len(data_set_names)}) "
                f"and number of dataframes ({len(list_of_dataframes)}) for {player_actual_name}."
            )
            # Fallback or error handling here if necessary, for now, we log and try to proceed
            # This might indicate an issue with the endpoint or library version for this specific call

        # Iterate using zip, assuming names and dataframes correspond by order
        for set_name, current_df in zip(data_set_names, list_of_dataframes):
            if not current_df.empty:
                try:
                    # Explicitly call with single_row=False to ensure a list of records is returned
                    processed_df_output = _process_dataframe(current_df.copy(), single_row=False)
                    
                    if processed_df_output is not None:
                        result_dict["data_sets"][set_name] = processed_df_output
                    else:
                        # Handle cases where _process_dataframe might return None due to an internal error
                        logger.error(f"_process_dataframe returned None for data set '{set_name}'. Assigning empty list.")
                        result_dict["data_sets"][set_name] = [] 

                    if return_dataframe: # This stores the original, unprocessed DataFrame
                        dataframes_for_return[set_name] = current_df.copy() # Store a copy of the original df
                        # Save the processed_df_output (list of dicts) to CSV if needed, or save current_df
                        # For consistency with to_dict(orient='records'), we should save the processed data if that was the intent
                        # However, the CSV saving logic was using processed_df which was a DataFrame before.
                        # Let's save the current_df to CSV as it's the raw data for that table.
                        csv_path = _get_csv_path_for_player_clutch(
                            player_actual_name, season, season_type, set_name
                        )
                        _save_dataframe_to_csv(current_df.copy(), csv_path) # Save the unprocessed df to CSV
                except Exception as e:
                    logger.error(f"Error processing data set '{set_name}' for player clutch stats: {e}", exc_info=True)
                    result_dict["data_sets"][set_name] = {"error": f"Failed to process data set: {e}"}
            else:
                # If the DataFrame is empty, use the corresponding list from normalized_dict (which might also be empty or just headers)
                result_dict["data_sets"][set_name] = normalized_dict.get(set_name, [])
                logger.info(f"Data set '{set_name}' was empty for player {player_actual_name}, season {season}.")

        final_json_response = json.dumps(result_dict, indent=4)
        if return_dataframe:
            return final_json_response, dataframes_for_return
        return final_json_response

    except PlayerNotFoundError as e:
        logger.warning(f"Player not found for clutch stats: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except Exception as e:
        logger.error(f"Unexpected error in fetch_player_clutch_stats_logic: {e}", exc_info=True)
        error_response = format_response(error=f"{Errors.UNEXPECTED_ERROR} Error: {e}")
        if return_dataframe:
            return error_response, {}
        return error_response

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # --- Test Cases ---
    SAMPLE_PLAYER_NAME = "LeBron James"
    SAMPLE_SEASON = "2022-23" # settings.CURRENT_NBA_SEASON
    SAMPLE_SEASON_TYPE = SeasonTypeAllStar.regular

    def run_clutch_test(test_name, params, expected_player_name, expect_data=True):
        print(f"\n--- Running Test: {test_name} ---")
        json_response, dataframes = fetch_player_clutch_stats_logic(
            **params,
            return_dataframe=True
        )
        data = json.loads(json_response)

        if "error" in data:
            print(f"Error received: {data['error']}")
            assert not expect_data, f"Expected data for {test_name}, but got error."
            return

        assert "player_name" in data, "player_name missing from response"
        assert data["player_name"] == expected_player_name, f"Expected player {expected_player_name}, got {data['player_name']}"
        assert "data_sets" in data, "'data_sets' missing from response"
        
        if expect_data:
            assert data["data_sets"], f"Expected data_sets to be non-empty for {test_name}"
            print(f"Parameters used: {data.get('parameters_used')}")
            print(f"Available data sets: {list(data['data_sets'].keys())}")

            if dataframes:
                for name, df in dataframes.items():
                    print(f"DataFrame '{name}' shape: {df.shape}")
                    assert not df.empty, f"DataFrame {name} should not be empty."
            else:
                print("No DataFrames returned, but JSON might have data.")
        else:
             assert not data.get("data_sets") or not any(data["data_sets"].values()), f"Expected empty data_sets for {test_name}"


        print(f"--- Test '{test_name}' Completed ---")
        return data, dataframes

    # Test 1: Basic fetch for LeBron James
    run_clutch_test("Basic LeBron Clutch", {"player_name": SAMPLE_PLAYER_NAME, "season": SAMPLE_SEASON}, SAMPLE_PLAYER_NAME)

    # Test 2: Specific season type (Playoffs)
    run_clutch_test("LeBron Playoffs Clutch", {"player_name": SAMPLE_PLAYER_NAME, "season": "2019-20", "season_type": SeasonTypeAllStar.playoffs}, SAMPLE_PLAYER_NAME)

    # Test 3: Different PerMode and MeasureType
    run_clutch_test(
        "LeBron PerGame Advanced Clutch",
        {
            "player_name": SAMPLE_PLAYER_NAME, "season": SAMPLE_SEASON,
            "per_mode": PerModeDetailed.per_game, "measure_type": MeasureTypeDetailed.advanced
        },
        SAMPLE_PLAYER_NAME
    )
    
    # Test 4: With Optional Parameters (e.g., Location, Outcome)
    run_clutch_test(
        "LeBron Clutch Home Wins",
        {
            "player_name": SAMPLE_PLAYER_NAME, "season": SAMPLE_SEASON,
            "location_nullable": "Home", "outcome_nullable": "W"
        },
        SAMPLE_PLAYER_NAME
    )

    # Test 5: With Date Range (expect fewer games or specific focus)
    # Note: Date range might lead to empty sets if no clutch games fall within.
    # Adjust dates for a known period of clutch activity if possible.
    run_clutch_test(
        "LeBron Clutch Specific Dates",
        {
            "player_name": SAMPLE_PLAYER_NAME, "season": "2022-23", # Ensure season matches date range
            "date_from_nullable": "2023-03-01", "date_to_nullable": "2023-03-15"
        },
        SAMPLE_PLAYER_NAME,
        expect_data=True # Might be false if no games in range
    )
    
    # Test 6: Different League ID (WNBA - requires a WNBA player)
    # This will likely fail for LeBron but tests LeagueID pass-through
    try:
        run_clutch_test(
            "WNBA Player Clutch (Example - Diana Taurasi)",
            {"player_name": "Diana Taurasi", "season": "2023", "league_id": "10"}, # WNBA League ID is 10, season format might differ
            "Diana Taurasi"
        )
    except PlayerNotFoundError:
        print("WNBA Player test skipped as Diana Taurasi not found by default find_player_id (expected).")
    except Exception as e:
        print(f"Error in WNBA test: {e}")


    # Test 7: Non-existent player
    try:
        run_clutch_test(
            "Non-existent Player Clutch",
            {"player_name": "Non Existent Player XYZ", "season": SAMPLE_SEASON},
            "",
            expect_data=False
        )
    except PlayerNotFoundError as e:
        print(f"Successfully caught PlayerNotFoundError for non-existent player: {e}")
    
    print("\nAll standalone tests for player_clutch completed.")
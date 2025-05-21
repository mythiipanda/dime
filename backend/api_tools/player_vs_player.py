"""
Handles fetching player vs player comparison statistics.
Provides both JSON and DataFrame outputs with CSV caching.

This module implements the PlayerVsPlayer endpoint, which provides
detailed statistics comparing two players:
- Head-to-head performance
- On/off court statistics
- Shot area and distance breakdowns
- Player biographical information
"""
import os
import logging
import json
from typing import Optional, Dict, Any, Union, Tuple, List
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import playervsplayer
from nba_api.stats.library.parameters import (
    SeasonTypePlayoffs, PerModeDetailed, MeasureTypeDetailedDefense
)
from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response
)
from ..utils.path_utils import get_cache_dir, get_cache_file_path

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
PLAYER_VS_PLAYER_CACHE_SIZE = 128
PLAYER_VS_PLAYER_CSV_DIR = get_cache_dir("player_vs_player")

# Valid parameter values
VALID_SEASON_TYPES = {
    "Regular Season": SeasonTypePlayoffs.regular,
    "Playoffs": SeasonTypePlayoffs.playoffs,
    "Pre Season": SeasonTypePlayoffs.preseason
}

VALID_PER_MODES = {
    "Totals": PerModeDetailed.totals,
    "PerGame": PerModeDetailed.per_game,
    "MinutesPer": PerModeDetailed.minutes_per,
    "Per48": PerModeDetailed.per_48,
    "Per40": PerModeDetailed.per_40,
    "Per36": PerModeDetailed.per_36,
    "PerMinute": PerModeDetailed.per_minute,
    "PerPossession": PerModeDetailed.per_possession,
    "PerPlay": PerModeDetailed.per_play,
    "Per100Possessions": PerModeDetailed.per_100_possessions,
    "Per100Plays": PerModeDetailed.per_100_plays
}

VALID_MEASURE_TYPES = {
    "Base": MeasureTypeDetailedDefense.base,
    "Advanced": MeasureTypeDetailedDefense.advanced,
    "Misc": MeasureTypeDetailedDefense.misc,
    "Four Factors": MeasureTypeDetailedDefense.four_factors,
    "Scoring": MeasureTypeDetailedDefense.scoring,
    "Opponent": MeasureTypeDetailedDefense.opponent,
    "Usage": MeasureTypeDetailedDefense.usage,
    "Defense": MeasureTypeDetailedDefense.defense
}

# --- Helper Functions for DataFrame Processing ---
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

        # Save DataFrame to CSV
        df.to_csv(file_path, index=False)
        logger.info(f"Saved DataFrame to CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)

def _get_csv_path_for_player_vs_player(
    player_id: str,
    vs_player_id: str,
    season: str,
    season_type: str,
    per_mode: str,
    measure_type: str,
    data_set_name: str
) -> str:
    """
    Generates a file path for saving a player vs player DataFrame as CSV.

    Args:
        player_id: The ID of the first player
        vs_player_id: The ID of the second player (comparison player)
        season: The season in YYYY-YY format
        season_type: The season type (e.g., Regular Season, Playoffs)
        per_mode: The per mode (e.g., Totals, PerGame)
        measure_type: The measure type (e.g., Base, Advanced)
        data_set_name: The name of the data set (e.g., OnOffCourt, Overall)

    Returns:
        Path to the CSV file
    """
    # Clean up parameters for filename
    season_clean = season.replace("-", "_")
    season_type_clean = season_type.replace(" ", "_").lower()
    per_mode_clean = per_mode.replace(" ", "_").lower()
    measure_type_clean = measure_type.replace(" ", "_").lower()
    data_set_clean = data_set_name.replace(" ", "_").lower()

    # Create filename
    filename = f"player_{player_id}_vs_{vs_player_id}_{season_clean}_{season_type_clean}_{per_mode_clean}_{measure_type_clean}_{data_set_clean}.csv"

    return get_cache_file_path(filename, "player_vs_player")

# --- Parameter Validation Functions ---
def _validate_player_vs_player_params(
    player_id: str,
    vs_player_id: str,
    season: str,
    season_type: str,
    per_mode: str,
    measure_type: str
) -> Optional[str]:
    """
    Validates parameters for the player vs player stats function.

    Args:
        player_id: ID of the first player
        vs_player_id: ID of the second player (comparison player)
        season: Season in YYYY-YY format
        season_type: Season type (e.g., Regular Season, Playoffs)
        per_mode: Per mode (e.g., Totals, PerGame)
        measure_type: Measure type (e.g., Base, Advanced)

    Returns:
        Error message if validation fails, None otherwise
    """
    if not player_id:
        return Errors.PLAYER_ID_EMPTY

    if not vs_player_id:
        return "Comparison player ID cannot be empty"

    if not season:
        return Errors.SEASON_EMPTY

    if season_type not in VALID_SEASON_TYPES:
        return Errors.INVALID_SEASON_TYPE.format(
            value=season_type,
            options=", ".join(list(VALID_SEASON_TYPES.keys()))
        )

    if per_mode not in VALID_PER_MODES:
        return Errors.INVALID_PER_MODE.format(
            value=per_mode,
            options=", ".join(list(VALID_PER_MODES.keys()))
        )

    if measure_type not in VALID_MEASURE_TYPES:
        return Errors.INVALID_MEASURE_TYPE.format(
            value=measure_type,
            options=", ".join(list(VALID_MEASURE_TYPES.keys()))
        )

    return None

# --- Main Logic Function ---
@lru_cache(maxsize=PLAYER_VS_PLAYER_CACHE_SIZE)
def fetch_player_vs_player_stats_logic(
    player_id: str,
    vs_player_id: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    period: int = 0,
    date_from: str = "",
    date_to: str = "",
    game_segment: str = "",
    location: str = "",
    outcome: str = "",
    season_segment: str = "",
    vs_conference: str = "",
    vs_division: str = "",
    league_id: str = "",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player vs player comparison statistics using the PlayerVsPlayer endpoint.

    This endpoint provides detailed statistics comparing two players:
    - Head-to-head performance
    - On/off court statistics
    - Shot area and distance breakdowns
    - Player biographical information

    Args:
        player_id (str): ID of the first player
        vs_player_id (str): ID of the second player (comparison player)
        season (str, optional): Season in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Per mode for stats. Defaults to "PerGame".
        measure_type (str, optional): Statistical category. Defaults to "Base".
        last_n_games (int, optional): Last N games filter. Defaults to 0 (all games).
        month (int, optional): Month filter (0-12). Defaults to 0 (all months).
        opponent_team_id (int, optional): Opponent team ID filter. Defaults to 0 (all teams).
        period (int, optional): Period filter (0-4). Defaults to 0 (all periods).
        date_from (str, optional): Start date filter (MM/DD/YYYY). Defaults to "".
        date_to (str, optional): End date filter (MM/DD/YYYY). Defaults to "".
        game_segment (str, optional): Game segment filter. Defaults to "".
        location (str, optional): Location filter (Home/Road). Defaults to "".
        outcome (str, optional): Outcome filter (W/L). Defaults to "".
        season_segment (str, optional): Season segment filter. Defaults to "".
        vs_conference (str, optional): Conference filter. Defaults to "".
        vs_division (str, optional): Division filter. Defaults to "".
        league_id (str, optional): League ID filter. Defaults to "".
        return_dataframe (bool, optional): Whether to return DataFrames. Defaults to False.

    Returns:
        If return_dataframe=False:
            str: JSON string with player vs player stats data or error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: JSON response and dictionary of DataFrames.
    """
    logger.info(
        f"Executing fetch_player_vs_player_stats_logic for: "
        f"Player: {player_id}, Vs Player: {vs_player_id}, Season: {season}, Type: {season_type}"
    )

    dataframes: Dict[str, pd.DataFrame] = {}

    # Validate parameters
    validation_error = _validate_player_vs_player_params(
        player_id, vs_player_id, season, season_type, per_mode, measure_type
    )
    if validation_error:
        if return_dataframe:
            return format_response(error=validation_error), dataframes
        return format_response(error=validation_error)

    # Prepare API parameters - using only parameters that work based on testing
    api_params = {
        "player_id": player_id,
        "vs_player_id": vs_player_id,
        "season": season,
        "season_type_playoffs": VALID_SEASON_TYPES[season_type],
        "per_mode_detailed": VALID_PER_MODES[per_mode],
        "measure_type_detailed_defense": VALID_MEASURE_TYPES[measure_type],
        "last_n_games": str(last_n_games),
        "month": str(month),
        "opponent_team_id": opponent_team_id,
        "period": str(period),
        "pace_adjust": "N",
        "plus_minus": "N",
        "rank": "N",
        "timeout": settings.DEFAULT_TIMEOUT_SECONDS
    }

    # Add optional filters if provided
    if date_from:
        api_params["date_from_nullable"] = date_from

    if date_to:
        api_params["date_to_nullable"] = date_to

    if game_segment:
        api_params["game_segment_nullable"] = game_segment

    if location:
        api_params["location_nullable"] = location

    if outcome:
        api_params["outcome_nullable"] = outcome

    if season_segment:
        api_params["season_segment_nullable"] = season_segment

    if vs_conference:
        api_params["vs_conference_nullable"] = vs_conference

    if vs_division:
        api_params["vs_division_nullable"] = vs_division

    if league_id:
        api_params["league_id_nullable"] = league_id

    # Filter out None values for cleaner logging
    filtered_api_params = {k: v for k, v in api_params.items() if v is not None and k != "timeout"}

    try:
        logger.debug(f"Calling PlayerVsPlayer with parameters: {filtered_api_params}")
        player_vs_player_endpoint = playervsplayer.PlayerVsPlayer(**api_params)

        # Get normalized dictionary for data set names
        normalized_dict = player_vs_player_endpoint.get_normalized_dict()

        # Get data frames
        list_of_dataframes = player_vs_player_endpoint.get_data_frames()

        # Expected data set names based on documentation
        expected_data_set_names = [
            "OnOffCourt", "Overall", "PlayerInfo", "ShotAreaOffCourt",
            "ShotAreaOnCourt", "ShotAreaOverall", "ShotDistanceOffCourt",
            "ShotDistanceOnCourt", "ShotDistanceOverall", "VsPlayerInfo"
        ]

        # Get data set names from the result sets
        data_set_names = []
        if "resultSets" in normalized_dict:
            data_set_names = list(normalized_dict["resultSets"].keys())
        else:
            # If no result sets found, use expected names
            data_set_names = expected_data_set_names

        # Process data for JSON response
        result_dict: Dict[str, Any] = {
            "parameters": filtered_api_params,
            "data_sets": {}
        }

        # Process each data set
        for idx, data_set_name in enumerate(data_set_names):
            if idx < len(list_of_dataframes):
                df = list_of_dataframes[idx]

                # Store DataFrame if requested
                if return_dataframe:
                    dataframes[data_set_name] = df

                    # Save to CSV if not empty
                    if not df.empty:
                        csv_path = _get_csv_path_for_player_vs_player(
                            player_id, vs_player_id, season, season_type, per_mode, measure_type, data_set_name
                        )
                        _save_dataframe_to_csv(df, csv_path)

                # Process for JSON response
                processed_data = _process_dataframe(df, single_row=False)
                result_dict["data_sets"][data_set_name] = processed_data

        # Return response
        logger.info(f"Successfully fetched player vs player stats for {player_id} vs {vs_player_id} in {season} {season_type}")
        if return_dataframe:
            return format_response(result_dict), dataframes
        return format_response(result_dict)

    except Exception as e:
        logger.error(
            f"API error in fetch_player_vs_player_stats_logic: {e}",
            exc_info=True
        )
        error_msg = Errors.PLAYER_VS_PLAYER_API.format(
            player_id=player_id, vs_player_id=vs_player_id, season=season, error=str(e)
        )
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

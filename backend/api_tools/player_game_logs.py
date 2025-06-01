"""
Handles fetching player game logs.
Provides both JSON and DataFrame outputs with CSV caching.

This module implements the PlayerGameLogs endpoint, which provides
detailed game-by-game statistics for players:
- Basic and advanced statistics for each game
- Game information (date, matchup, outcome)
- Statistical rankings
"""
import os
import logging
import json
from typing import Optional, Dict, Any, Union, Tuple, List
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import playergamelogs
from nba_api.stats.library.parameters import (
    SeasonType, PerModeSimple, MeasureTypePlayerGameLogs
)
from config import settings
from core.errors import Errors
from api_tools.utils import (
    _process_dataframe,
    format_response
)
from utils.path_utils import get_cache_dir, get_cache_file_path

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
PLAYER_GAME_LOGS_CACHE_SIZE = 128
PLAYER_GAME_LOGS_CSV_DIR = get_cache_dir("player_game_logs")

# Valid parameter values
VALID_SEASON_TYPES = {
    "Regular Season": SeasonType.regular,
    "Pre Season": SeasonType.preseason
    # "All" season type removed because it causes 'resultSet' errors
}

VALID_PER_MODES = {
    "Totals": PerModeSimple.totals,
    "PerGame": PerModeSimple.per_game
}

VALID_MEASURE_TYPES = {
    "Base": MeasureTypePlayerGameLogs.base,
    "Advanced": MeasureTypePlayerGameLogs.advanced
}

VALID_GAME_SEGMENTS = {
    "First Half": "First Half",
    "Second Half": "Second Half",
    "Overtime": "Overtime"
}

VALID_LOCATIONS = {
    "Home": "Home",
    "Road": "Road"
}

VALID_OUTCOMES = {
    "W": "W",
    "L": "L"
}

VALID_SEASON_SEGMENTS = {
    "Post All-Star": "Post All-Star",
    "Pre All-Star": "Pre All-Star"
}

VALID_SHOT_CLOCK_RANGES = {
    "24-22": "24-22",
    "22-18 Very Early": "22-18 Very Early",
    "18-15 Early": "18-15 Early",
    "15-7 Average": "15-7 Average",
    "7-4 Late": "7-4 Late",
    "4-0 Very Late": "4-0 Very Late"
}

VALID_CONFERENCES = {
    "East": "East",
    "West": "West"
}

VALID_DIVISIONS = {
    "Atlantic": "Atlantic",
    "Central": "Central",
    "Southeast": "Southeast",
    "Northwest": "Northwest",
    "Pacific": "Pacific",
    "Southwest": "Southwest"
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

def _get_csv_path_for_player_game_logs(
    season: str,
    season_type: str,
    per_mode: str,
    measure_type: str,
    player_id: Optional[str] = None,
    team_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Generates a file path for saving a player game logs DataFrame as CSV.

    Args:
        season: The season in YYYY-YY format
        season_type: The season type (e.g., Regular Season, Playoffs)
        per_mode: The per mode (e.g., Totals, PerGame)
        measure_type: The measure type (e.g., Base, Advanced)
        player_id: Optional player ID filter
        team_id: Optional team ID filter
        date_from: Optional start date filter (MM/DD/YYYY)
        date_to: Optional end date filter (MM/DD/YYYY)

    Returns:
        Path to the CSV file
    """
    # Clean up parameters for filename
    season_clean = season.replace("-", "_") if season else "all_seasons"
    season_type_clean = season_type.replace(" ", "_").lower()
    per_mode_clean = per_mode.replace(" ", "_").lower()
    measure_type_clean = measure_type.replace(" ", "_").lower()

    # Create filename with optional filters
    filename_parts = [
        f"player_game_logs_{season_clean}_{season_type_clean}_{per_mode_clean}_{measure_type_clean}"
    ]

    if player_id:
        filename_parts.append(f"player_{player_id}")

    if team_id:
        filename_parts.append(f"team_{team_id}")

    if date_from:
        date_from_clean = date_from.replace("/", "_")
        filename_parts.append(f"from_{date_from_clean}")

    if date_to:
        date_to_clean = date_to.replace("/", "_")
        filename_parts.append(f"to_{date_to_clean}")

    filename = "_".join(filename_parts) + ".csv"

    return get_cache_file_path(filename, "player_game_logs")

# --- Parameter Validation Functions ---
def _validate_player_game_logs_params(
    season_type: str,
    per_mode: str,
    measure_type: str,
    game_segment: Optional[str] = None,
    location: Optional[str] = None,
    outcome: Optional[str] = None,
    season_segment: Optional[str] = None,
    shot_clock_range: Optional[str] = None,
    vs_conference: Optional[str] = None,
    vs_division: Optional[str] = None
) -> Optional[str]:
    """
    Validates parameters for the player game logs function.

    Args:
        season_type: Season type (e.g., Regular Season, Playoffs)
        per_mode: Per mode (e.g., Totals, PerGame)
        measure_type: Measure type (e.g., Base, Advanced)
        game_segment: Optional game segment filter
        location: Optional location filter
        outcome: Optional outcome filter
        season_segment: Optional season segment filter
        shot_clock_range: Optional shot clock range filter
        vs_conference: Optional conference filter
        vs_division: Optional division filter

    Returns:
        Error message if validation fails, None otherwise
    """
    if season_type and season_type not in VALID_SEASON_TYPES:
        return Errors.INVALID_SEASON_TYPE.format(
            value=season_type,
            options=", ".join(list(VALID_SEASON_TYPES.keys()))
        )

    if per_mode and per_mode not in VALID_PER_MODES:
        return Errors.INVALID_PER_MODE.format(
            value=per_mode,
            options=", ".join(list(VALID_PER_MODES.keys()))
        )

    if measure_type and measure_type not in VALID_MEASURE_TYPES:
        return Errors.INVALID_MEASURE_TYPE.format(
            value=measure_type,
            options=", ".join(list(VALID_MEASURE_TYPES.keys()))
        )

    if game_segment and game_segment not in VALID_GAME_SEGMENTS:
        return f"Invalid game_segment: '{game_segment}'. Valid options: {', '.join(list(VALID_GAME_SEGMENTS.keys()))}"

    if location and location not in VALID_LOCATIONS:
        return f"Invalid location: '{location}'. Valid options: {', '.join(list(VALID_LOCATIONS.keys()))}"

    if outcome and outcome not in VALID_OUTCOMES:
        return f"Invalid outcome: '{outcome}'. Valid options: {', '.join(list(VALID_OUTCOMES.keys()))}"

    if season_segment and season_segment not in VALID_SEASON_SEGMENTS:
        return f"Invalid season_segment: '{season_segment}'. Valid options: {', '.join(list(VALID_SEASON_SEGMENTS.keys()))}"

    if shot_clock_range and shot_clock_range not in VALID_SHOT_CLOCK_RANGES:
        return f"Invalid shot_clock_range: '{shot_clock_range}'. Valid options: {', '.join(list(VALID_SHOT_CLOCK_RANGES.keys()))}"

    if vs_conference and vs_conference not in VALID_CONFERENCES:
        return f"Invalid vs_conference: '{vs_conference}'. Valid options: {', '.join(list(VALID_CONFERENCES.keys()))}"

    if vs_division and vs_division not in VALID_DIVISIONS:
        return f"Invalid vs_division: '{vs_division}'. Valid options: {', '.join(list(VALID_DIVISIONS.keys()))}"

    return None

# --- Main Logic Function ---
@lru_cache(maxsize=PLAYER_GAME_LOGS_CACHE_SIZE)
def fetch_player_game_logs_logic(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    player_id: str = "",
    team_id: str = "",
    date_from: str = "",
    date_to: str = "",
    game_segment: str = "",
    last_n_games: int = 0,
    league_id: str = "00",  # NBA
    location: str = "",
    month: int = 0,
    opponent_team_id: str = "",
    outcome: str = "",
    po_round: str = "",
    period: int = 0,
    season_segment: str = "",
    shot_clock_range: str = "",
    vs_conference: str = "",
    vs_division: str = "",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player game logs using the PlayerGameLogs endpoint.

    This endpoint provides detailed game-by-game statistics for players:
    - Basic and advanced statistics for each game
    - Game information (date, matchup, outcome)
    - Statistical rankings

    Args:
        season (str, optional): Season in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Per mode for stats. Defaults to "PerGame".
        measure_type (str, optional): Statistical category. Defaults to "Base".
        player_id (str, optional): Player ID filter. Defaults to "".
        team_id (str, optional): Team ID filter. Defaults to "".
        date_from (str, optional): Start date filter (MM/DD/YYYY). Defaults to "".
        date_to (str, optional): End date filter (MM/DD/YYYY). Defaults to "".
        game_segment (str, optional): Game segment filter. Defaults to "".
        last_n_games (int, optional): Last N games filter. Defaults to 0 (all games).
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        location (str, optional): Location filter (Home/Road). Defaults to "".
        month (int, optional): Month filter (0-12). Defaults to 0 (all months).
        opponent_team_id (str, optional): Opponent team ID filter. Defaults to "".
        outcome (str, optional): Outcome filter (W/L). Defaults to "".
        po_round (str, optional): Playoff round filter. Defaults to "".
        period (int, optional): Period filter (0-4). Defaults to 0 (all periods).
        season_segment (str, optional): Season segment filter. Defaults to "".
        shot_clock_range (str, optional): Shot clock range filter. Defaults to "".
        vs_conference (str, optional): Conference filter. Defaults to "".
        vs_division (str, optional): Division filter. Defaults to "".
        return_dataframe (bool, optional): Whether to return DataFrames. Defaults to False.

    Returns:
        If return_dataframe=False:
            str: JSON string with player game logs data or error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: JSON response and dictionary of DataFrames.
    """
    logger.info(
        f"Executing fetch_player_game_logs_logic for: "
        f"Season: {season}, Type: {season_type}, Player ID: {player_id}, Team ID: {team_id}"
    )

    dataframes: Dict[str, pd.DataFrame] = {}

    # Validate parameters
    validation_error = _validate_player_game_logs_params(
        season_type, per_mode, measure_type, game_segment, location, outcome,
        season_segment, shot_clock_range, vs_conference, vs_division
    )
    if validation_error:
        if return_dataframe:
            return format_response(error=validation_error), dataframes
        return format_response(error=validation_error)

    # Prepare API parameters - using only parameters that work based on testing
    api_params = {
        "season_nullable": season,
        "season_type_nullable": VALID_SEASON_TYPES.get(season_type, ""),
        "per_mode_simple_nullable": VALID_PER_MODES.get(per_mode, ""),
        "measure_type_player_game_logs_nullable": VALID_MEASURE_TYPES.get(measure_type, ""),
        "player_id_nullable": player_id,
        "team_id_nullable": team_id,
        "date_from_nullable": date_from,
        "date_to_nullable": date_to,
        # Removed problematic parameters that cause 'resultSet' errors
        # "game_segment_nullable": game_segment,
        # "last_n_games_nullable": str(last_n_games) if last_n_games > 0 else "",
        "league_id_nullable": league_id,
        "location_nullable": location,
        # "month_nullable": str(month) if month > 0 else "",
        # "opp_team_id_nullable": opponent_team_id,
        "outcome_nullable": outcome,
        # "po_round_nullable": po_round,
        # "period_nullable": str(period) if period > 0 else "",
        "season_segment_nullable": season_segment,
        # "shot_clock_range_nullable": shot_clock_range,
        "vs_conference_nullable": vs_conference,
        "vs_division_nullable": vs_division,
        "timeout": settings.DEFAULT_TIMEOUT_SECONDS
    }

    # Filter out empty values for cleaner logging
    filtered_api_params = {k: v for k, v in api_params.items() if v and k != "timeout"}

    try:
        logger.debug(f"Calling PlayerGameLogs with parameters: {filtered_api_params}")
        game_logs_endpoint = playergamelogs.PlayerGameLogs(**api_params)

        # Get normalized dictionary for data set names
        normalized_dict = game_logs_endpoint.get_normalized_dict()

        # Get data frames
        list_of_dataframes = game_logs_endpoint.get_data_frames()

        # Expected data set name based on documentation
        expected_data_set_name = "PlayerGameLogs"

        # Get data set names from the result sets
        data_set_names = []
        if "resultSets" in normalized_dict:
            data_set_names = list(normalized_dict["resultSets"].keys())
        else:
            # If no result sets found, use expected name
            data_set_names = [expected_data_set_name]

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
                        csv_path = _get_csv_path_for_player_game_logs(
                            season, season_type, per_mode, measure_type, player_id, team_id, date_from, date_to
                        )
                        _save_dataframe_to_csv(df, csv_path)

                # Process for JSON response
                processed_data = _process_dataframe(df, single_row=False)
                result_dict["data_sets"][data_set_name] = processed_data

        # Return response
        logger.info(f"Successfully fetched player game logs for Season: {season}, Player ID: {player_id}, Team ID: {team_id}")
        if return_dataframe:
            return format_response(result_dict), dataframes
        return format_response(result_dict)

    except Exception as e:
        logger.error(
            f"API error in fetch_player_game_logs_logic: {e}",
            exc_info=True
        )
        error_msg = Errors.PLAYER_GAME_LOGS_API.format(
            player_id=player_id or "N/A", team_id=team_id or "N/A", season=season or "N/A", error=str(e)
        )
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

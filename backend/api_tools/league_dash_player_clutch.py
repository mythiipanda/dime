"""
Handles fetching player clutch statistics.
Provides both JSON and DataFrame outputs with CSV caching.

This module implements the LeagueDashPlayerClutch endpoint, which provides
detailed player statistics in clutch situations:
- Performance in close games
- Statistics in the final minutes of games
- Performance when ahead or behind
"""
import os
import logging
import json
from typing import Optional, Dict, Any, Union, Tuple, List
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import leaguedashplayerclutch
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailedDefense,
    PlayerPositionAbbreviationNullable, PlayerExperienceNullable, StarterBenchNullable
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
LEAGUE_DASH_PLAYER_CLUTCH_CACHE_SIZE = 128
LEAGUE_DASH_PLAYER_CLUTCH_CSV_DIR = get_cache_dir("league_dash_player_clutch")

# Valid parameter values
VALID_SEASON_TYPES = {
    "Regular Season": SeasonTypeAllStar.regular,
    "Playoffs": SeasonTypeAllStar.playoffs,
    "Pre Season": SeasonTypeAllStar.preseason,
    "All Star": SeasonTypeAllStar.all_star
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

VALID_PLAYER_POSITIONS = {
    "Forward": PlayerPositionAbbreviationNullable.forward,
    "Center": PlayerPositionAbbreviationNullable.center,
    "Guard": PlayerPositionAbbreviationNullable.guard,
    "Center-Forward": PlayerPositionAbbreviationNullable.center_forward,
    "Forward-Center": PlayerPositionAbbreviationNullable.forward_center,
    "Forward-Guard": PlayerPositionAbbreviationNullable.forward_guard,
    "Guard-Forward": PlayerPositionAbbreviationNullable.guard_forward
}

VALID_PLAYER_EXPERIENCES = {
    "Rookie": PlayerExperienceNullable.rookie,
    "Sophomore": PlayerExperienceNullable.sophomore,
    "Veteran": PlayerExperienceNullable.veteran
}

VALID_STARTER_BENCH = {
    "Starters": StarterBenchNullable.starters,
    "Bench": StarterBenchNullable.bench
}

VALID_CLUTCH_TIMES = {
    "Last 5 Minutes": "Last 5 Minutes",
    "Last 4 Minutes": "Last 4 Minutes",
    "Last 3 Minutes": "Last 3 Minutes",
    "Last 2 Minutes": "Last 2 Minutes",
    "Last 1 Minute": "Last 1 Minute",
    "Last 30 Seconds": "Last 30 Seconds",
    "Last 10 Seconds": "Last 10 Seconds"
}

VALID_AHEAD_BEHIND = {
    "Ahead or Behind": "Ahead or Behind",
    "Behind or Tied": "Behind or Tied",
    "Ahead or Tied": "Ahead or Tied"
}

VALID_LEAGUE_IDS = {
    "00": "00",  # NBA
    "10": "10",  # WNBA
    "20": "20"   # G-League
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

def _get_csv_path_for_player_clutch(
    season: str,
    season_type: str,
    per_mode: str,
    measure_type: str,
    clutch_time: str,
    ahead_behind: str,
    point_diff: int,
    team_id: Optional[str] = None,
    player_position: Optional[str] = None,
    player_experience: Optional[str] = None
) -> str:
    """
    Generates a file path for saving a player clutch DataFrame as CSV.

    Args:
        season: The season in YYYY-YY format
        season_type: The season type (e.g., Regular Season, Playoffs)
        per_mode: The per mode (e.g., Totals, PerGame)
        measure_type: The measure type (e.g., Base, Advanced)
        clutch_time: The clutch time definition (e.g., Last 5 Minutes)
        ahead_behind: The ahead/behind filter (e.g., Ahead or Behind)
        point_diff: The point differential
        team_id: Optional team ID filter
        player_position: Optional player position filter
        player_experience: Optional player experience filter

    Returns:
        Path to the CSV file
    """
    # Clean up parameters for filename
    season_clean = season.replace("-", "_")
    season_type_clean = season_type.replace(" ", "_").lower()
    per_mode_clean = per_mode.replace(" ", "_").lower()
    measure_type_clean = measure_type.replace(" ", "_").lower()
    clutch_time_clean = clutch_time.replace(" ", "_").lower()
    ahead_behind_clean = ahead_behind.replace(" ", "_").lower()

    # Create filename with optional filters
    filename_parts = [
        f"clutch_stats_{season_clean}_{season_type_clean}_{per_mode_clean}_{measure_type_clean}",
        f"clutch_{clutch_time_clean}_{ahead_behind_clean}_pt{point_diff}"
    ]

    if team_id:
        filename_parts.append(f"team_{team_id}")

    if player_position:
        pos_clean = player_position.replace("-", "_").lower()
        filename_parts.append(f"pos_{pos_clean}")

    if player_experience:
        exp_clean = player_experience.lower()
        filename_parts.append(f"exp_{exp_clean}")

    filename = "_".join(filename_parts) + ".csv"

    return get_cache_file_path(filename, "league_dash_player_clutch")

# --- Parameter Validation Functions ---
def _validate_player_clutch_params(
    season: str,
    season_type: str,
    per_mode: str,
    measure_type: str,
    clutch_time: str,
    ahead_behind: str,
    point_diff: int,
    league_id: str,
    player_position: Optional[str] = None,
    player_experience: Optional[str] = None,
    starter_bench: Optional[str] = None
) -> Optional[str]:
    """
    Validates parameters for the player clutch stats function.

    Args:
        season: Season in YYYY-YY format
        season_type: Season type (e.g., Regular Season, Playoffs)
        per_mode: Per mode (e.g., Totals, PerGame)
        measure_type: Measure type (e.g., Base, Advanced)
        clutch_time: Clutch time definition (e.g., Last 5 Minutes)
        ahead_behind: Ahead/behind filter (e.g., Ahead or Behind)
        point_diff: Point differential
        league_id: League ID (e.g., 00 for NBA, 10 for WNBA, 20 for G-League)
        player_position: Optional player position filter
        player_experience: Optional player experience filter
        starter_bench: Optional starter/bench filter

    Returns:
        Error message if validation fails, None otherwise
    """
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

    if clutch_time not in VALID_CLUTCH_TIMES:
        return Errors.INVALID_CLUTCH_TIME.format(
            value=clutch_time,
            options=", ".join(list(VALID_CLUTCH_TIMES.keys()))
        )

    if ahead_behind not in VALID_AHEAD_BEHIND:
        return Errors.INVALID_AHEAD_BEHIND.format(
            value=ahead_behind,
            options=", ".join(list(VALID_AHEAD_BEHIND.keys()))
        )

    if not isinstance(point_diff, int) or point_diff < 0:
        return Errors.INVALID_POINT_DIFF.format(value=point_diff)

    if league_id not in VALID_LEAGUE_IDS:
        return Errors.INVALID_LEAGUE_ID.format(
            value=league_id,
            options=", ".join(list(VALID_LEAGUE_IDS.keys()))
        )

    if player_position and player_position not in VALID_PLAYER_POSITIONS:
        return Errors.INVALID_PLAYER_POSITION.format(
            value=player_position,
            options=", ".join(list(VALID_PLAYER_POSITIONS.keys()))
        )

    if player_experience and player_experience not in VALID_PLAYER_EXPERIENCES:
        return Errors.INVALID_PLAYER_EXPERIENCE.format(
            value=player_experience,
            options=", ".join(list(VALID_PLAYER_EXPERIENCES.keys()))
        )

    if starter_bench and starter_bench not in VALID_STARTER_BENCH:
        return Errors.INVALID_STARTER_BENCH.format(
            value=starter_bench,
            options=", ".join(list(VALID_STARTER_BENCH.keys()))
        )

    return None

# --- Main Logic Function ---
@lru_cache(maxsize=LEAGUE_DASH_PLAYER_CLUTCH_CACHE_SIZE)
def fetch_league_player_clutch_stats_logic(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    clutch_time: str = "Last 5 Minutes",
    ahead_behind: str = "Ahead or Behind",
    point_diff: int = 5,
    league_id: str = "00",  # NBA
    team_id: Optional[str] = None,
    player_position: Optional[str] = None,
    player_experience: Optional[str] = None,
    starter_bench: Optional[str] = None,
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    period: int = 0,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player clutch statistics using the LeagueDashPlayerClutch endpoint.

    This endpoint provides detailed player statistics in clutch situations:
    - Performance in close games
    - Statistics in the final minutes of games
    - Performance when ahead or behind

    Args:
        season (str, optional): Season in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Per mode for stats. Defaults to "PerGame".
        measure_type (str, optional): Statistical category. Defaults to "Base".
        clutch_time (str, optional): Clutch time definition. Defaults to "Last 5 Minutes".
        ahead_behind (str, optional): Ahead/behind filter. Defaults to "Ahead or Behind".
        point_diff (int, optional): Point differential. Defaults to 5.
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        team_id (str, optional): Team ID filter. Defaults to None.
        player_position (str, optional): Player position filter. Defaults to None.
        player_experience (str, optional): Player experience filter. Defaults to None.
        starter_bench (str, optional): Starter/bench filter. Defaults to None.
        last_n_games (int, optional): Last N games filter. Defaults to 0 (all games).
        month (int, optional): Month filter (0-12). Defaults to 0 (all months).
        opponent_team_id (int, optional): Opponent team ID filter. Defaults to 0 (all teams).
        period (int, optional): Period filter (0-4). Defaults to 0 (all periods).
        return_dataframe (bool, optional): Whether to return DataFrames. Defaults to False.

    Returns:
        If return_dataframe=False:
            str: JSON string with player clutch stats data or error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: JSON response and dictionary of DataFrames.
    """
    logger.info(
        f"Executing fetch_league_player_clutch_stats_logic for: "
        f"Season: {season}, Type: {season_type}, ClutchTime: {clutch_time}, PointDiff: {point_diff}"
    )

    dataframes: Dict[str, pd.DataFrame] = {}

    # Validate parameters
    validation_error = _validate_player_clutch_params(
        season, season_type, per_mode, measure_type, clutch_time, ahead_behind, point_diff,
        league_id, player_position, player_experience, starter_bench
    )
    if validation_error:
        if return_dataframe:
            return format_response(error=validation_error), dataframes
        return format_response(error=validation_error)

    # Prepare API parameters - using only parameters that work based on testing
    api_params = {
        "league_id_nullable": league_id,
        "season": season,
        "season_type_all_star": VALID_SEASON_TYPES[season_type],
        "per_mode_detailed": VALID_PER_MODES[per_mode],
        "measure_type_detailed_defense": VALID_MEASURE_TYPES[measure_type],
        "clutch_time": clutch_time,
        "ahead_behind": ahead_behind,
        "point_diff": str(point_diff),
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
    if team_id:
        api_params["team_id_nullable"] = team_id

    if player_position:
        api_params["player_position_abbreviation_nullable"] = VALID_PLAYER_POSITIONS[player_position]

    if player_experience:
        api_params["player_experience_nullable"] = VALID_PLAYER_EXPERIENCES[player_experience]

    if starter_bench:
        api_params["starter_bench_nullable"] = VALID_STARTER_BENCH[starter_bench]

    # Filter out None values for cleaner logging
    filtered_api_params = {k: v for k, v in api_params.items() if v is not None and k != "timeout"}

    try:
        logger.debug(f"Calling LeagueDashPlayerClutch with parameters: {filtered_api_params}")
        clutch_stats_endpoint = leaguedashplayerclutch.LeagueDashPlayerClutch(**api_params)

        # Get normalized dictionary for data set names
        normalized_dict = clutch_stats_endpoint.get_normalized_dict()

        # Get data frames
        list_of_dataframes = clutch_stats_endpoint.get_data_frames()

        # Expected data set name based on documentation
        expected_data_set_name = "LeagueDashPlayerClutch"

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
                        csv_path = _get_csv_path_for_player_clutch(
                            season, season_type, per_mode, measure_type, clutch_time, ahead_behind, point_diff,
                            team_id, player_position, player_experience
                        )
                        _save_dataframe_to_csv(df, csv_path)

                # Process for JSON response
                processed_data = _process_dataframe(df, single_row=False)
                result_dict["data_sets"][data_set_name] = processed_data

        # Return response
        logger.info(f"Successfully fetched player clutch stats for {season} {season_type}")
        if return_dataframe:
            return format_response(result_dict), dataframes
        return format_response(result_dict)

    except Exception as e:
        logger.error(
            f"API error in fetch_league_player_clutch_stats_logic: {e}",
            exc_info=True
        )
        error_msg = Errors.LEAGUE_DASH_PLAYER_CLUTCH_API.format(
            season=season, season_type=season_type, clutch_time=clutch_time, error=str(e)
        )
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

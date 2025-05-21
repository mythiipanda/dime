"""
Handles fetching league player statistics.
Provides both JSON and DataFrame outputs with CSV caching.

This module implements the LeagueDashPlayerStats endpoint, which provides
comprehensive player statistics across the league:
- Basic and advanced statistics
- Scoring and defensive metrics
- Player rankings
- Filtering by team, position, experience, etc.
"""
import os
import logging
import json
from typing import Optional, Dict, Any, Union, Tuple, List
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import leaguedashplayerstats
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailedDefense
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
LEAGUE_DASH_PLAYER_STATS_CACHE_SIZE = 128
LEAGUE_DASH_PLAYER_STATS_CSV_DIR = get_cache_dir("league_dash_player_stats")

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
    "F": "F",  # Forward
    "C": "C",  # Center
    "G": "G",  # Guard
    "C-F": "C-F",  # Center-Forward
    "F-C": "F-C",  # Forward-Center
    "F-G": "F-G",  # Forward-Guard
    "G-F": "G-F"   # Guard-Forward
}

VALID_PLAYER_EXPERIENCES = {
    "Rookie": "Rookie",
    "Sophomore": "Sophomore",
    "Veteran": "Veteran"
}

VALID_STARTER_BENCH = {
    "Starters": "Starters",
    "Bench": "Bench"
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
    "Southwest": "Southwest",
    "East": "East",
    "West": "West"
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

def _get_csv_path_for_league_player_stats(
    season: str,
    season_type: str,
    per_mode: str,
    measure_type: str,
    team_id: Optional[str] = None,
    player_position: Optional[str] = None,
    player_experience: Optional[str] = None,
    starter_bench: Optional[str] = None
) -> str:
    """
    Generates a file path for saving a league player stats DataFrame as CSV.

    Args:
        season: The season in YYYY-YY format
        season_type: The season type (e.g., Regular Season, Playoffs)
        per_mode: The per mode (e.g., Totals, PerGame)
        measure_type: The measure type (e.g., Base, Advanced)
        team_id: Optional team ID filter
        player_position: Optional player position filter
        player_experience: Optional player experience filter
        starter_bench: Optional starter/bench filter

    Returns:
        Path to the CSV file
    """
    # Clean up parameters for filename
    season_clean = season.replace("-", "_")
    season_type_clean = season_type.replace(" ", "_").lower()
    per_mode_clean = per_mode.replace(" ", "_").lower()
    measure_type_clean = measure_type.replace(" ", "_").lower()

    # Create filename with optional filters
    filename_parts = [
        f"league_player_stats_{season_clean}_{season_type_clean}_{per_mode_clean}_{measure_type_clean}"
    ]

    if team_id:
        filename_parts.append(f"team_{team_id}")

    if player_position:
        position_clean = player_position.replace("-", "_")
        filename_parts.append(f"pos_{position_clean}")

    if player_experience:
        experience_clean = player_experience.lower()
        filename_parts.append(f"exp_{experience_clean}")

    if starter_bench:
        starter_bench_clean = starter_bench.lower()
        filename_parts.append(f"role_{starter_bench_clean}")

    filename = "_".join(filename_parts) + ".csv"

    return get_cache_file_path(filename, "league_dash_player_stats")

# --- Parameter Validation Functions ---
def _validate_league_player_stats_params(
    season: str,
    season_type: str,
    per_mode: str,
    measure_type: str,
    player_position: Optional[str] = None,
    player_experience: Optional[str] = None,
    starter_bench: Optional[str] = None,
    game_segment: Optional[str] = None,
    location: Optional[str] = None,
    outcome: Optional[str] = None,
    season_segment: Optional[str] = None,
    vs_conference: Optional[str] = None,
    vs_division: Optional[str] = None
) -> Optional[str]:
    """
    Validates parameters for the league player stats function.

    Args:
        season: Season in YYYY-YY format
        season_type: Season type (e.g., Regular Season, Playoffs)
        per_mode: Per mode (e.g., Totals, PerGame)
        measure_type: Measure type (e.g., Base, Advanced)
        player_position: Optional player position filter
        player_experience: Optional player experience filter
        starter_bench: Optional starter/bench filter
        game_segment: Optional game segment filter
        location: Optional location filter
        outcome: Optional outcome filter
        season_segment: Optional season segment filter
        vs_conference: Optional conference filter
        vs_division: Optional division filter

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

    if game_segment and game_segment not in VALID_GAME_SEGMENTS:
        return f"Invalid game_segment: '{game_segment}'. Valid options: {', '.join(list(VALID_GAME_SEGMENTS.keys()))}"

    if location and location not in VALID_LOCATIONS:
        return f"Invalid location: '{location}'. Valid options: {', '.join(list(VALID_LOCATIONS.keys()))}"

    if outcome and outcome not in VALID_OUTCOMES:
        return f"Invalid outcome: '{outcome}'. Valid options: {', '.join(list(VALID_OUTCOMES.keys()))}"

    if season_segment and season_segment not in VALID_SEASON_SEGMENTS:
        return f"Invalid season_segment: '{season_segment}'. Valid options: {', '.join(list(VALID_SEASON_SEGMENTS.keys()))}"

    if vs_conference and vs_conference not in VALID_CONFERENCES:
        return f"Invalid vs_conference: '{vs_conference}'. Valid options: {', '.join(list(VALID_CONFERENCES.keys()))}"

    if vs_division and vs_division not in VALID_DIVISIONS:
        return f"Invalid vs_division: '{vs_division}'. Valid options: {', '.join(list(VALID_DIVISIONS.keys()))}"

    return None

# --- Main Logic Function ---
@lru_cache(maxsize=LEAGUE_DASH_PLAYER_STATS_CACHE_SIZE)
def fetch_league_player_stats_logic(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    team_id: str = "",
    player_position: str = "",
    player_experience: str = "",
    starter_bench: str = "",
    date_from: str = "",
    date_to: str = "",
    game_segment: str = "",
    last_n_games: int = 0,
    league_id: str = "00",  # NBA
    location: str = "",
    month: int = 0,
    opponent_team_id: int = 0,
    outcome: str = "",
    period: int = 0,
    season_segment: str = "",
    vs_conference: str = "",
    vs_division: str = "",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league player statistics using the LeagueDashPlayerStats endpoint.

    This endpoint provides comprehensive player statistics across the league:
    - Basic and advanced statistics
    - Scoring and defensive metrics
    - Player rankings
    - Filtering by team, position, experience, etc.

    Args:
        season (str, optional): Season in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Per mode for stats. Defaults to "PerGame".
        measure_type (str, optional): Statistical category. Defaults to "Base".
        team_id (str, optional): Team ID filter. Defaults to "".
        player_position (str, optional): Player position filter. Defaults to "".
        player_experience (str, optional): Player experience filter. Defaults to "".
        starter_bench (str, optional): Starter/bench filter. Defaults to "".
        date_from (str, optional): Start date filter (MM/DD/YYYY). Defaults to "".
        date_to (str, optional): End date filter (MM/DD/YYYY). Defaults to "".
        game_segment (str, optional): Game segment filter. Defaults to "".
        last_n_games (int, optional): Last N games filter. Defaults to 0 (all games).
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        location (str, optional): Location filter (Home/Road). Defaults to "".
        month (int, optional): Month filter (0-12). Defaults to 0 (all months).
        opponent_team_id (int, optional): Opponent team ID filter. Defaults to 0 (all teams).
        outcome (str, optional): Outcome filter (W/L). Defaults to "".
        period (int, optional): Period filter (0-4). Defaults to 0 (all periods).
        season_segment (str, optional): Season segment filter. Defaults to "".
        vs_conference (str, optional): Conference filter. Defaults to "".
        vs_division (str, optional): Division filter. Defaults to "".
        return_dataframe (bool, optional): Whether to return DataFrames. Defaults to False.

    Returns:
        If return_dataframe=False:
            str: JSON string with league player stats data or error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: JSON response and dictionary of DataFrames.
    """
    logger.info(
        f"Executing fetch_league_player_stats_logic for: "
        f"Season: {season}, Type: {season_type}, Measure Type: {measure_type}"
    )

    dataframes: Dict[str, pd.DataFrame] = {}

    # Validate parameters
    validation_error = _validate_league_player_stats_params(
        season, season_type, per_mode, measure_type, player_position, player_experience,
        starter_bench, game_segment, location, outcome, season_segment, vs_conference, vs_division
    )
    if validation_error:
        if return_dataframe:
            return format_response(error=validation_error), dataframes
        return format_response(error=validation_error)

    # Prepare API parameters - using only parameters that work based on testing
    api_params = {
        "season": season,
        "season_type_all_star": VALID_SEASON_TYPES[season_type],
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
    if team_id:
        api_params["team_id_nullable"] = team_id

    if player_position:
        api_params["player_position_abbreviation_nullable"] = player_position

    if player_experience:
        api_params["player_experience_nullable"] = player_experience

    if starter_bench:
        api_params["starter_bench_nullable"] = starter_bench

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
        logger.debug(f"Calling LeagueDashPlayerStats with parameters: {filtered_api_params}")
        player_stats_endpoint = leaguedashplayerstats.LeagueDashPlayerStats(**api_params)

        # Get normalized dictionary for data set names
        normalized_dict = player_stats_endpoint.get_normalized_dict()

        # Get data frames
        list_of_dataframes = player_stats_endpoint.get_data_frames()

        # Expected data set name based on documentation
        expected_data_set_name = "LeagueDashPlayerStats"

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
                        csv_path = _get_csv_path_for_league_player_stats(
                            season, season_type, per_mode, measure_type, team_id, player_position, player_experience, starter_bench
                        )
                        _save_dataframe_to_csv(df, csv_path)

                # Process for JSON response
                processed_data = _process_dataframe(df, single_row=False)
                result_dict["data_sets"][data_set_name] = processed_data

        # Return response
        logger.info(f"Successfully fetched league player stats for {season} {season_type}")
        if return_dataframe:
            return format_response(result_dict), dataframes
        return format_response(result_dict)

    except Exception as e:
        logger.error(
            f"API error in fetch_league_player_stats_logic: {e}",
            exc_info=True
        )
        error_msg = Errors.LEAGUE_DASH_PLAYER_STATS_API.format(
            season=season, season_type=season_type, measure_type=measure_type, error=str(e)
        )
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

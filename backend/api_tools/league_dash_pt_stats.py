"""
Handles fetching player tracking statistics across the league.
Provides both JSON and DataFrame outputs with CSV caching.

This module implements the LeagueDashPtStats endpoint, which provides
comprehensive player tracking statistics for players or teams across the league.
The endpoint offers various player tracking measure types including:

1. SpeedDistance - Distance covered and speed metrics
2. Rebounding - Rebounding opportunities, contested rebounds, etc.
3. Possessions - Time of possession, touches, etc.
4. CatchShoot - Catch and shoot statistics
5. PullUpShot - Pull-up shot statistics
6. Defense - Defensive impact metrics
7. Drives - Drive statistics (frequency, points, assists)
8. Passing - Passing statistics (assists, potential assists)
9. ElbowTouch - Elbow touch statistics
10. PostTouch - Post touch statistics
11. PaintTouch - Paint touch statistics
12. Efficiency - Scoring efficiency metrics

The data includes metrics like distance traveled, average speed, and various
specialized statistics based on the selected measure type.
"""
import os
import logging
import json
from typing import Optional, Dict, Any, Union, Tuple, List, Set
import pandas as pd

from nba_api.stats.endpoints import leaguedashptstats
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeSimple, PlayerOrTeam, PtMeasureType
)
from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response
)
from ..utils.path_utils import get_cache_dir, get_cache_file_path
from ..utils.validation import _validate_season_format, validate_date_format

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
LEAGUE_DASH_PT_STATS_CACHE_SIZE = 128
LEAGUE_DASH_PT_STATS_CSV_DIR = get_cache_dir("league_dash_pt_stats")

# Valid parameter values
_VALID_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar)
                               if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}

_VALID_PER_MODES: Set[str] = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple)
                            if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}

_VALID_PLAYER_OR_TEAM: Set[str] = {getattr(PlayerOrTeam, attr) for attr in dir(PlayerOrTeam)
                                 if not attr.startswith('_') and isinstance(getattr(PlayerOrTeam, attr), str)}

_VALID_PT_MEASURE_TYPES: Set[str] = {getattr(PtMeasureType, attr) for attr in dir(PtMeasureType)
                                   if not attr.startswith('_') and isinstance(getattr(PtMeasureType, attr), str)}

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

def _get_csv_path_for_pt_stats(
    season: str,
    season_type: str,
    per_mode: str,
    player_or_team: str,
    pt_measure_type: str,
    team_id_nullable: Optional[str] = None,
    player_position_abbreviation_nullable: Optional[str] = None,
    conference_nullable: Optional[str] = None,
    division_simple_nullable: Optional[str] = None
) -> str:
    """
    Generates a file path for saving a league player tracking stats DataFrame as CSV.

    Args:
        season: The season in YYYY-YY format
        season_type: The season type (e.g., Regular Season, Playoffs)
        per_mode: The per mode (e.g., Totals, PerGame)
        player_or_team: Player or Team filter (e.g., Player, Team)
        pt_measure_type: Player tracking measure type (e.g., SpeedDistance, Rebounding)
        team_id_nullable: Optional team ID filter
        player_position_abbreviation_nullable: Optional player position filter
        conference_nullable: Optional conference filter
        division_simple_nullable: Optional division filter

    Returns:
        Path to the CSV file
    """
    # Clean up parameters for filename
    season_clean = season.replace("-", "_")
    season_type_clean = season_type.replace(" ", "_").lower()
    per_mode_clean = per_mode.replace(" ", "_").lower()
    player_or_team_clean = player_or_team.lower()
    pt_measure_type_clean = pt_measure_type.lower()

    # Create filename with optional filters
    filename_parts = [
        f"pt_stats_{season_clean}_{season_type_clean}_{per_mode_clean}_{player_or_team_clean}_{pt_measure_type_clean}"
    ]

    if team_id_nullable:
        filename_parts.append(f"team_{team_id_nullable}")

    if player_position_abbreviation_nullable:
        position_clean = player_position_abbreviation_nullable.replace("-", "_").lower()
        filename_parts.append(f"pos_{position_clean}")

    if conference_nullable:
        conference_clean = conference_nullable.lower()
        filename_parts.append(f"conf_{conference_clean}")

    if division_simple_nullable:
        division_clean = division_simple_nullable.replace(" ", "_").lower()
        filename_parts.append(f"div_{division_clean}")

    filename = "_".join(filename_parts) + ".csv"

    return get_cache_file_path(filename, "league_dash_pt_stats")

# --- Main Logic Function ---
def fetch_league_dash_pt_stats_logic(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    player_or_team: str = PlayerOrTeam.team,
    pt_measure_type: str = PtMeasureType.speed_distance,
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    game_scope_simple_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    player_experience_nullable: Optional[str] = None,
    player_position_abbreviation_nullable: Optional[str] = None,
    starter_bench_nullable: Optional[str] = None,
    team_id_nullable: Optional[str] = None,
    college_nullable: Optional[str] = None,
    conference_nullable: Optional[str] = None,
    country_nullable: Optional[str] = None,
    division_simple_nullable: Optional[str] = None,
    draft_pick_nullable: Optional[str] = None,
    draft_year_nullable: Optional[str] = None,
    height_nullable: Optional[str] = None,
    league_id_nullable: Optional[str] = None,
    po_round_nullable: Optional[str] = None,
    weight_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player tracking statistics across the league using the LeagueDashPtStats endpoint.

    This endpoint provides comprehensive player tracking statistics for players or teams across the league.
    The data returned varies based on the selected pt_measure_type, but generally includes metrics like
    distance traveled, average speed, and specialized statistics for the chosen tracking category.

    For SpeedDistance measure type (default), the data includes:
    - Team/player identification (ID, name, abbreviation)
    - Games played (GP), wins (W), and losses (L)
    - Minutes played (MIN)
    - Distance metrics (DIST_FEET, DIST_MILES, DIST_MILES_OFF, DIST_MILES_DEF)
    - Speed metrics (AVG_SPEED, AVG_SPEED_OFF, AVG_SPEED_DEF)

    Other measure types provide specialized statistics:
    - Rebounding: Rebounding opportunities, contested rebounds, box outs
    - Possessions: Time of possession, touches, passes, points per touch
    - CatchShoot: Catch and shoot frequency, points, FG%
    - PullUpShot: Pull-up shot frequency, points, FG%
    - Defense: Defensive impact metrics like DFGM, DFGA, DFG%
    - Drives: Drive frequency, points, assists, FG% on drives
    - Passing: Passing statistics like assists, potential assists, assist points
    - ElbowTouch: Elbow touch frequency, points, FG%
    - PostTouch: Post touch frequency, points, FG%
    - PaintTouch: Paint touch frequency, points, FG%
    - Efficiency: Scoring efficiency metrics

    Args:
        season (str): Season in YYYY-YY format (e.g., "2023-24"). Defaults to current season.
        season_type (str): Season type from SeasonTypeAllStar (e.g., "Regular Season", "Playoffs").
            Defaults to "Regular Season".
        per_mode (str): Per mode from PerModeSimple (e.g., "PerGame", "Totals").
            Defaults to "PerGame".
        player_or_team (str): Player or Team filter from PlayerOrTeam (e.g., "Player", "Team").
            Defaults to "Team".
        pt_measure_type (str): Player tracking measure type from PtMeasureType (e.g., "SpeedDistance",
            "Rebounding", "Drives"). Defaults to "SpeedDistance".
        last_n_games (int): Last N games filter. Defaults to 0 (all games).
        month (int): Month filter (0-12). Defaults to 0 (all months).
        opponent_team_id (int): Opponent team ID filter. Defaults to 0 (all teams).
        date_from_nullable (Optional[str]): Start date filter in YYYY-MM-DD format.
        date_to_nullable (Optional[str]): End date filter in YYYY-MM-DD format.
        game_scope_simple_nullable (Optional[str]): Game scope filter (e.g., "Yesterday", "Last 10").
        location_nullable (Optional[str]): Location filter ("Home" or "Road").
        outcome_nullable (Optional[str]): Outcome filter ("W" or "L").
        season_segment_nullable (Optional[str]): Season segment filter (e.g., "Pre All-Star", "Post All-Star").
        vs_conference_nullable (Optional[str]): Conference filter for opponents (e.g., "East", "West").
        vs_division_nullable (Optional[str]): Division filter for opponents (e.g., "Atlantic", "Pacific").
        player_experience_nullable (Optional[str]): Player experience filter (e.g., "Rookie", "Sophomore", "Veteran").
        player_position_abbreviation_nullable (Optional[str]): Player position filter (e.g., "G", "F", "C", "G-F").
        starter_bench_nullable (Optional[str]): Starter/bench filter ("Starters" or "Bench").
        team_id_nullable (Optional[str]): Team ID filter.
        college_nullable (Optional[str]): College filter.
        conference_nullable (Optional[str]): Conference filter for teams (e.g., "East", "West").
        country_nullable (Optional[str]): Country filter.
        division_simple_nullable (Optional[str]): Division filter for teams (e.g., "Atlantic", "Pacific").
        draft_pick_nullable (Optional[str]): Draft pick filter.
        draft_year_nullable (Optional[str]): Draft year filter.
        height_nullable (Optional[str]): Height filter.
        league_id_nullable (Optional[str]): League ID filter.
        po_round_nullable (Optional[str]): Playoff round filter.
        weight_nullable (Optional[str]): Weight filter.
        return_dataframe (bool): Whether to return DataFrames. Defaults to False.

    Returns:
        If return_dataframe=False:
            str: JSON string with player tracking stats data or error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: JSON response and dictionary of DataFrames.
    """
    logger.info(
        f"Executing fetch_league_dash_pt_stats_logic for: "
        f"Season: {season}, Type: {season_type}, Per Mode: {per_mode}, "
        f"Player/Team: {player_or_team}, Measure Type: {pt_measure_type}"
    )

    dataframes: Dict[str, pd.DataFrame] = {}

    # Parameter validation
    if not season or not _validate_season_format(season):
        error_response = format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if season_type not in _VALID_SEASON_TYPES:
        error_response = format_response(error=Errors.INVALID_SEASON_TYPE.format(
            value=season_type, options=", ".join(list(_VALID_SEASON_TYPES)[:5])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if per_mode not in _VALID_PER_MODES:
        error_response = format_response(error=Errors.INVALID_PER_MODE.format(
            value=per_mode, options=", ".join(list(_VALID_PER_MODES)[:5])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if player_or_team not in _VALID_PLAYER_OR_TEAM:
        error_response = format_response(error=f"Invalid player_or_team: '{player_or_team}'. Valid options: {', '.join(list(_VALID_PLAYER_OR_TEAM))}")
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if pt_measure_type not in _VALID_PT_MEASURE_TYPES:
        error_response = format_response(error=f"Invalid pt_measure_type: '{pt_measure_type}'. Valid options: {', '.join(list(_VALID_PT_MEASURE_TYPES))}")
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if date_from_nullable and not validate_date_format(date_from_nullable):
        error_response = format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from_nullable))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if date_to_nullable and not validate_date_format(date_to_nullable):
        error_response = format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to_nullable))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    try:
        # Prepare API parameters
        api_params = {
            "season": season,
            "season_type_all_star": season_type,
            "per_mode_simple": per_mode,
            "player_or_team": player_or_team,
            "pt_measure_type": pt_measure_type,
            "last_n_games": last_n_games,
            "month": month,
            "opponent_team_id": opponent_team_id,
            "timeout": settings.DEFAULT_TIMEOUT_SECONDS
        }

        # Add optional parameters if provided
        if date_from_nullable:
            api_params["date_from_nullable"] = date_from_nullable
        if date_to_nullable:
            api_params["date_to_nullable"] = date_to_nullable
        if game_scope_simple_nullable:
            api_params["game_scope_simple_nullable"] = game_scope_simple_nullable
        if location_nullable:
            api_params["location_nullable"] = location_nullable
        if outcome_nullable:
            api_params["outcome_nullable"] = outcome_nullable
        if season_segment_nullable:
            api_params["season_segment_nullable"] = season_segment_nullable
        if vs_conference_nullable:
            api_params["vs_conference_nullable"] = vs_conference_nullable
        if vs_division_nullable:
            api_params["vs_division_nullable"] = vs_division_nullable
        if player_experience_nullable:
            api_params["player_experience_nullable"] = player_experience_nullable
        if player_position_abbreviation_nullable:
            api_params["player_position_abbreviation_nullable"] = player_position_abbreviation_nullable
        if starter_bench_nullable:
            api_params["starter_bench_nullable"] = starter_bench_nullable
        if team_id_nullable:
            api_params["team_id_nullable"] = team_id_nullable
        if college_nullable:
            api_params["college_nullable"] = college_nullable
        if conference_nullable:
            api_params["conference_nullable"] = conference_nullable
        if country_nullable:
            api_params["country_nullable"] = country_nullable
        if division_simple_nullable:
            api_params["division_simple_nullable"] = division_simple_nullable
        if draft_pick_nullable:
            api_params["draft_pick_nullable"] = draft_pick_nullable
        if draft_year_nullable:
            api_params["draft_year_nullable"] = draft_year_nullable
        if height_nullable:
            api_params["height_nullable"] = height_nullable
        if league_id_nullable:
            api_params["league_id_nullable"] = league_id_nullable
        if po_round_nullable:
            api_params["po_round_nullable"] = po_round_nullable
        if weight_nullable:
            api_params["weight_nullable"] = weight_nullable

        # Filter out None values for cleaner logging
        filtered_api_params = {k: v for k, v in api_params.items() if v is not None and k != "timeout"}

        logger.debug(f"Calling LeagueDashPtStats with parameters: {filtered_api_params}")
        pt_stats_endpoint = leaguedashptstats.LeagueDashPtStats(**api_params)

        # Get data frames
        pt_stats_df = pt_stats_endpoint.get_data_frames()[0]

        # Store DataFrame if requested
        if return_dataframe:
            dataframes["LeagueDashPtStats"] = pt_stats_df

            # Save to CSV if not empty
            if not pt_stats_df.empty:
                csv_path = _get_csv_path_for_pt_stats(
                    season, season_type, per_mode, player_or_team, pt_measure_type,
                    team_id_nullable, player_position_abbreviation_nullable,
                    conference_nullable, division_simple_nullable
                )
                _save_dataframe_to_csv(pt_stats_df, csv_path)

        # Process for JSON response
        processed_data = _process_dataframe(pt_stats_df, single_row=False)

        # Create result dictionary
        result_dict = {
            "parameters": filtered_api_params,
            "pt_stats": processed_data or []
        }

        # Return response
        logger.info(f"Successfully fetched player tracking stats for {season} {season_type}")
        if return_dataframe:
            return format_response(result_dict), dataframes
        return format_response(result_dict)

    except Exception as e:
        logger.error(
            f"API error in fetch_league_dash_pt_stats_logic: {e}",
            exc_info=True
        )
        error_msg = f"Error fetching player tracking stats: {str(e)}"
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

"""
Handles fetching player shooting statistics across the league.
Provides both JSON and DataFrame outputs with CSV caching.

This module implements the LeagueDashPlayerPtShot endpoint, which provides
comprehensive shooting statistics for players across the league.
"""
import os
import logging
import json
from typing import Optional, Dict, Any, Union, Tuple, List, Set
import pandas as pd

from nba_api.stats.endpoints import leaguedashplayerptshot
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeSimple, LeagueID
)
from config import settings
from core.errors import Errors
from api_tools.utils import (
    _process_dataframe,
    format_response
)
from utils.path_utils import get_cache_dir, get_cache_file_path
from utils.validation import _validate_season_format, validate_date_format

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
LEAGUE_DASH_PLAYER_PT_SHOT_CACHE_SIZE = 128
LEAGUE_DASH_PLAYER_PT_SHOT_CSV_DIR = get_cache_dir("league_dash_player_pt_shot")

# Valid parameter values
_VALID_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar)
                               if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}

_VALID_PER_MODES: Set[str] = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple)
                            if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}

_VALID_LEAGUE_IDS: Set[str] = {getattr(LeagueID, attr) for attr in dir(LeagueID)
                             if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

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

def _get_csv_path_for_player_pt_shot(
    season: str,
    season_type: str,
    per_mode: str,
    league_id: str,
    team_id_nullable: Optional[str] = None,
    player_position_nullable: Optional[str] = None,
    conference_nullable: Optional[str] = None,
    division_nullable: Optional[str] = None
) -> str:
    """
    Generates a file path for saving a league player shot DataFrame as CSV.

    Args:
        season: The season in YYYY-YY format
        season_type: The season type (e.g., Regular Season, Playoffs)
        per_mode: The per mode (e.g., Totals, PerGame)
        league_id: The league ID (e.g., 00 for NBA)
        team_id_nullable: Optional team ID filter
        player_position_nullable: Optional player position filter
        conference_nullable: Optional conference filter
        division_nullable: Optional division filter

    Returns:
        Path to the CSV file
    """
    # Clean up parameters for filename
    season_clean = season.replace("-", "_")
    season_type_clean = season_type.replace(" ", "_").lower()
    per_mode_clean = per_mode.replace(" ", "_").lower()

    # Create filename with optional filters
    filename_parts = [
        f"player_pt_shot_{season_clean}_{season_type_clean}_{per_mode_clean}_{league_id}"
    ]

    if team_id_nullable:
        filename_parts.append(f"team_{team_id_nullable}")

    if player_position_nullable:
        position_clean = player_position_nullable.replace(" ", "_").lower()
        filename_parts.append(f"pos_{position_clean}")

    if conference_nullable:
        conference_clean = conference_nullable.lower()
        filename_parts.append(f"conf_{conference_clean}")

    if division_nullable:
        division_clean = division_nullable.replace(" ", "_").lower()
        filename_parts.append(f"div_{division_clean}")

    filename = "_".join(filename_parts) + ".csv"

    return get_cache_file_path(filename, "league_dash_player_pt_shot")

# --- Main Logic Function ---
def fetch_league_dash_player_pt_shot_logic(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    league_id: str = LeagueID.nba,
    close_def_dist_range_nullable: Optional[str] = None,
    college_nullable: Optional[str] = None,
    conference_nullable: Optional[str] = None,
    country_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    division_nullable: Optional[str] = None,
    draft_pick_nullable: Optional[str] = None,
    draft_year_nullable: Optional[str] = None,
    dribble_range_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    general_range_nullable: Optional[str] = None,
    height_nullable: Optional[str] = None,
    last_n_games_nullable: Optional[int] = None,
    location_nullable: Optional[str] = None,
    month_nullable: Optional[int] = None,
    opponent_team_id_nullable: Optional[int] = None,
    outcome_nullable: Optional[str] = None,
    po_round_nullable: Optional[str] = None,
    period_nullable: Optional[int] = None,
    player_experience_nullable: Optional[str] = None,
    player_position_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    shot_clock_range_nullable: Optional[str] = None,
    shot_dist_range_nullable: Optional[str] = None,
    starter_bench_nullable: Optional[str] = None,
    team_id_nullable: Optional[str] = None,
    touch_time_range_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    weight_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player shooting statistics across the league using the LeagueDashPlayerPtShot endpoint.

    This endpoint provides comprehensive shooting statistics for players across the league.

    Args:
        season: Season in YYYY-YY format. Defaults to current season.
        season_type: Season type. Defaults to Regular Season.
        per_mode: Per mode for stats. Defaults to PerGame.
        league_id: League ID. Defaults to "00" (NBA).
        close_def_dist_range_nullable: Filter by defender distance.
        college_nullable: Filter by college.
        conference_nullable: Filter by conference.
        country_nullable: Filter by country.
        date_from_nullable: Start date filter (YYYY-MM-DD).
        date_to_nullable: End date filter (YYYY-MM-DD).
        division_nullable: Filter by division.
        draft_pick_nullable: Filter by draft pick.
        draft_year_nullable: Filter by draft year.
        dribble_range_nullable: Filter by dribble range.
        game_segment_nullable: Filter by game segment.
        general_range_nullable: Filter by general range.
        height_nullable: Filter by player height.
        last_n_games_nullable: Filter by last N games.
        location_nullable: Filter by location (Home/Road).
        month_nullable: Filter by month.
        opponent_team_id_nullable: Filter by opponent team ID.
        outcome_nullable: Filter by game outcome (W/L).
        po_round_nullable: Filter by playoff round.
        period_nullable: Filter by period.
        player_experience_nullable: Filter by player experience.
        player_position_nullable: Filter by player position.
        season_segment_nullable: Filter by season segment.
        shot_clock_range_nullable: Filter by shot clock range.
        shot_dist_range_nullable: Filter by shot distance range.
        starter_bench_nullable: Filter by starter/bench.
        team_id_nullable: Filter by team ID.
        touch_time_range_nullable: Filter by touch time range.
        vs_conference_nullable: Filter by opponent conference.
        vs_division_nullable: Filter by opponent division.
        weight_nullable: Filter by player weight.
        return_dataframe: Whether to return DataFrames. Defaults to False.

    Returns:
        If return_dataframe=False:
            str: JSON string with player shooting stats data or error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: JSON response and dictionary of DataFrames.
    """
    logger.info(
        f"Executing fetch_league_dash_player_pt_shot_logic for: "
        f"Season: {season}, Type: {season_type}, Per Mode: {per_mode}, League ID: {league_id}"
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

    if league_id not in _VALID_LEAGUE_IDS:
        error_response = format_response(error=Errors.INVALID_LEAGUE_ID.format(
            value=league_id, options=", ".join(list(_VALID_LEAGUE_IDS)[:5])))
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
            "league_id": league_id,
            "timeout": settings.DEFAULT_TIMEOUT_SECONDS
        }

        # Add optional parameters if provided
        if close_def_dist_range_nullable:
            api_params["close_def_dist_range_nullable"] = close_def_dist_range_nullable
        if college_nullable:
            api_params["college_nullable"] = college_nullable
        if conference_nullable:
            api_params["conference_nullable"] = conference_nullable
        if country_nullable:
            api_params["country_nullable"] = country_nullable
        if date_from_nullable:
            api_params["date_from_nullable"] = date_from_nullable
        if date_to_nullable:
            api_params["date_to_nullable"] = date_to_nullable
        if division_nullable:
            api_params["division_nullable"] = division_nullable
        if draft_pick_nullable:
            api_params["draft_pick_nullable"] = draft_pick_nullable
        if draft_year_nullable:
            api_params["draft_year_nullable"] = draft_year_nullable
        if dribble_range_nullable:
            api_params["dribble_range_nullable"] = dribble_range_nullable
        if game_segment_nullable:
            api_params["game_segment_nullable"] = game_segment_nullable
        if general_range_nullable:
            api_params["general_range_nullable"] = general_range_nullable
        if height_nullable:
            api_params["height_nullable"] = height_nullable
        if last_n_games_nullable is not None:
            api_params["last_n_games_nullable"] = last_n_games_nullable
        if location_nullable:
            api_params["location_nullable"] = location_nullable
        if month_nullable is not None:
            api_params["month_nullable"] = month_nullable
        if opponent_team_id_nullable is not None:
            api_params["opponent_team_id_nullable"] = opponent_team_id_nullable
        if outcome_nullable:
            api_params["outcome_nullable"] = outcome_nullable
        if po_round_nullable:
            api_params["po_round_nullable"] = po_round_nullable
        if period_nullable is not None:
            api_params["period_nullable"] = period_nullable
        if player_experience_nullable:
            api_params["player_experience_nullable"] = player_experience_nullable
        if player_position_nullable:
            api_params["player_position_nullable"] = player_position_nullable
        if season_segment_nullable:
            api_params["season_segment_nullable"] = season_segment_nullable
        if shot_clock_range_nullable:
            api_params["shot_clock_range_nullable"] = shot_clock_range_nullable
        if shot_dist_range_nullable:
            api_params["shot_dist_range_nullable"] = shot_dist_range_nullable
        if starter_bench_nullable:
            api_params["starter_bench_nullable"] = starter_bench_nullable
        if team_id_nullable:
            api_params["team_id_nullable"] = team_id_nullable
        if touch_time_range_nullable:
            api_params["touch_time_range_nullable"] = touch_time_range_nullable
        if vs_conference_nullable:
            api_params["vs_conference_nullable"] = vs_conference_nullable
        if vs_division_nullable:
            api_params["vs_division_nullable"] = vs_division_nullable
        if weight_nullable:
            api_params["weight_nullable"] = weight_nullable

        # Filter out None values for cleaner logging
        filtered_api_params = {k: v for k, v in api_params.items() if v is not None and k != "timeout"}

        logger.debug(f"Calling LeagueDashPlayerPtShot with parameters: {filtered_api_params}")
        player_pt_shot_endpoint = leaguedashplayerptshot.LeagueDashPlayerPtShot(**api_params)

        # Get data frames
        player_pt_shot_df = player_pt_shot_endpoint.get_data_frames()[0]

        # Store DataFrame if requested
        if return_dataframe:
            dataframes["LeagueDashPTShots"] = player_pt_shot_df

            # Save to CSV if not empty
            if not player_pt_shot_df.empty:
                csv_path = _get_csv_path_for_player_pt_shot(
                    season, season_type, per_mode, league_id,
                    team_id_nullable, player_position_nullable, conference_nullable, division_nullable
                )
                _save_dataframe_to_csv(player_pt_shot_df, csv_path)

        # Process for JSON response
        processed_data = _process_dataframe(player_pt_shot_df, single_row=False)

        # Create result dictionary
        result_dict = {
            "parameters": filtered_api_params,
            "player_pt_shots": processed_data or []
        }

        # Return response
        logger.info(f"Successfully fetched player shooting stats for {season} {season_type}")
        if return_dataframe:
            return format_response(result_dict), dataframes
        return format_response(result_dict)

    except Exception as e:
        logger.error(
            f"API error in fetch_league_dash_player_pt_shot_logic: {e}",
            exc_info=True
        )
        error_msg = f"Error fetching player shooting stats: {str(e)}"
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

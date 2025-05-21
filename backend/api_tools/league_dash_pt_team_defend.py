"""
Handles fetching defensive team tracking statistics across the league.
Provides both JSON and DataFrame outputs with CSV caching.

This module implements the LeagueDashPtTeamDefend endpoint, which provides
comprehensive defensive statistics for teams across the league.
The endpoint offers various defensive categories including:

1. Overall - All defensive possessions
2. 3 Pointers - Defense against 3-point shots
3. 2 Pointers - Defense against 2-point shots
4. Less Than 6Ft - Defense against shots less than 6 feet from the basket
5. Less Than 10Ft - Defense against shots less than 10 feet from the basket
6. Greater Than 15Ft - Defense against shots greater than 15 feet from the basket

The data includes metrics like defended field goal percentage, normal field goal
percentage, and the difference between them (PCT_PLUSMINUS) which indicates
defensive impact at the team level.
"""
import os
import logging
import json
from typing import Optional, Dict, Any, Union, Tuple, List, Set
import pandas as pd

from nba_api.stats.endpoints import leaguedashptteamdefend
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeSimple, LeagueID, DefenseCategory
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
LEAGUE_DASH_PT_TEAM_DEFEND_CACHE_SIZE = 128
LEAGUE_DASH_PT_TEAM_DEFEND_CSV_DIR = get_cache_dir("league_dash_pt_team_defend")

# Valid parameter values
_VALID_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar)
                               if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}

_VALID_PER_MODES: Set[str] = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple)
                            if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}

_VALID_LEAGUE_IDS: Set[str] = {getattr(LeagueID, attr) for attr in dir(LeagueID)
                             if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

_VALID_DEFENSE_CATEGORIES: Set[str] = {getattr(DefenseCategory, attr) for attr in dir(DefenseCategory)
                                     if not attr.startswith('_') and isinstance(getattr(DefenseCategory, attr), str)}

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

def _get_csv_path_for_pt_team_defend(
    season: str,
    season_type: str,
    per_mode: str,
    defense_category: str,
    league_id: str,
    team_id_nullable: Optional[str] = None,
    conference_nullable: Optional[str] = None,
    division_nullable: Optional[str] = None
) -> str:
    """
    Generates a file path for saving a league defensive team tracking stats DataFrame as CSV.

    Args:
        season: The season in YYYY-YY format
        season_type: The season type (e.g., Regular Season, Playoffs)
        per_mode: The per mode (e.g., Totals, PerGame)
        defense_category: The defense category (e.g., Overall, 3 Pointers)
        league_id: The league ID (e.g., 00 for NBA)
        team_id_nullable: Optional team ID filter
        conference_nullable: Optional conference filter
        division_nullable: Optional division filter

    Returns:
        Path to the CSV file
    """
    # Clean up parameters for filename
    season_clean = season.replace("-", "_")
    season_type_clean = season_type.replace(" ", "_").lower()
    per_mode_clean = per_mode.replace(" ", "_").lower()
    defense_category_clean = defense_category.replace(" ", "_").lower()

    # Create filename with optional filters
    filename_parts = [
        f"pt_team_defend_{season_clean}_{season_type_clean}_{per_mode_clean}_{defense_category_clean}_{league_id}"
    ]

    if team_id_nullable:
        filename_parts.append(f"team_{team_id_nullable}")

    if conference_nullable:
        conference_clean = conference_nullable.lower()
        filename_parts.append(f"conf_{conference_clean}")

    if division_nullable:
        division_clean = division_nullable.replace(" ", "_").lower()
        filename_parts.append(f"div_{division_clean}")

    filename = "_".join(filename_parts) + ".csv"

    return get_cache_file_path(filename, "league_dash_pt_team_defend")

# --- Main Logic Function ---
def fetch_league_dash_pt_team_defend_logic(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    defense_category: str = DefenseCategory.overall,
    league_id: str = LeagueID.nba,
    conference_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    division_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    last_n_games_nullable: Optional[int] = None,
    location_nullable: Optional[str] = None,
    month_nullable: Optional[int] = None,
    opponent_team_id_nullable: Optional[int] = None,
    outcome_nullable: Optional[str] = None,
    po_round_nullable: Optional[str] = None,
    period_nullable: Optional[int] = None,
    season_segment_nullable: Optional[str] = None,
    team_id_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches defensive team tracking statistics across the league using the LeagueDashPtTeamDefend endpoint.

    This endpoint provides comprehensive defensive statistics for teams across the league,
    showing how teams perform when defending shots in different categories.

    The data includes:
    - Team identification (ID, name, abbreviation)
    - Games played (GP, G)
    - Frequency of defensive matchups (FREQ)
    - Defended field goal makes and attempts (D_FGM, D_FGA)
    - Defended field goal percentage (D_FG_PCT)
    - Normal field goal percentage of opponents (NORMAL_FG_PCT)
    - Difference between normal and defended FG% (PCT_PLUSMINUS) - negative values indicate good defense

    Args:
        season (str): Season in YYYY-YY format (e.g., "2023-24"). Defaults to current season.
        season_type (str): Season type from SeasonTypeAllStar (e.g., "Regular Season", "Playoffs").
            Defaults to "Regular Season".
        per_mode (str): Per mode from PerModeSimple (e.g., "PerGame", "Totals").
            Defaults to "PerGame".
        defense_category (str): Defense category from DefenseCategory (e.g., "Overall", "3 Pointers").
            Defaults to "Overall".
        league_id (str): League ID from LeagueID (e.g., "00" for NBA). Defaults to "00".
        conference_nullable (Optional[str]): Conference filter for teams (e.g., "East", "West").
        date_from_nullable (Optional[str]): Start date filter in YYYY-MM-DD format.
        date_to_nullable (Optional[str]): End date filter in YYYY-MM-DD format.
        division_nullable (Optional[str]): Division filter for teams (e.g., "Atlantic", "Pacific").
        game_segment_nullable (Optional[str]): Game segment filter (e.g., "First Half", "Second Half").
        last_n_games_nullable (Optional[int]): Last N games filter.
        location_nullable (Optional[str]): Location filter ("Home" or "Road").
        month_nullable (Optional[int]): Month filter (0-12).
        opponent_team_id_nullable (Optional[int]): Opponent team ID filter.
        outcome_nullable (Optional[str]): Outcome filter ("W" or "L").
        po_round_nullable (Optional[str]): Playoff round filter.
        period_nullable (Optional[int]): Period filter.
        season_segment_nullable (Optional[str]): Season segment filter (e.g., "Pre All-Star", "Post All-Star").
        team_id_nullable (Optional[str]): Team ID filter.
        vs_conference_nullable (Optional[str]): Conference filter for opponents (e.g., "East", "West").
        vs_division_nullable (Optional[str]): Division filter for opponents (e.g., "Atlantic", "Pacific").
        return_dataframe (bool): Whether to return DataFrames. Defaults to False.

    Returns:
        If return_dataframe=False:
            str: JSON string with defensive team tracking stats data or error.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: JSON response and dictionary of DataFrames.
    """
    logger.info(
        f"Executing fetch_league_dash_pt_team_defend_logic for: "
        f"Season: {season}, Type: {season_type}, Per Mode: {per_mode}, "
        f"Defense Category: {defense_category}, League ID: {league_id}"
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

    if defense_category not in _VALID_DEFENSE_CATEGORIES:
        error_response = format_response(error=f"Invalid defense_category: '{defense_category}'. Valid options: {', '.join(list(_VALID_DEFENSE_CATEGORIES))}")
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
            "defense_category": defense_category,
            "league_id": league_id,
            "timeout": settings.DEFAULT_TIMEOUT_SECONDS
        }

        # Add optional parameters if provided
        if conference_nullable:
            api_params["conference_nullable"] = conference_nullable
        if date_from_nullable:
            api_params["date_from_nullable"] = date_from_nullable
        if date_to_nullable:
            api_params["date_to_nullable"] = date_to_nullable
        if division_nullable:
            api_params["division_nullable"] = division_nullable
        if game_segment_nullable:
            api_params["game_segment_nullable"] = game_segment_nullable
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
        # Only add po_round_nullable for playoff data
        if po_round_nullable and season_type == SeasonTypeAllStar.playoffs:
            api_params["po_round_nullable"] = po_round_nullable
        if period_nullable is not None:
            api_params["period_nullable"] = period_nullable
        if season_segment_nullable:
            api_params["season_segment_nullable"] = season_segment_nullable
        if team_id_nullable:
            api_params["team_id_nullable"] = team_id_nullable
        if vs_conference_nullable:
            api_params["vs_conference_nullable"] = vs_conference_nullable
        if vs_division_nullable:
            api_params["vs_division_nullable"] = vs_division_nullable

        # Filter out None values for cleaner logging
        filtered_api_params = {k: v for k, v in api_params.items() if v is not None and k != "timeout"}

        logger.debug(f"Calling LeagueDashPtTeamDefend with parameters: {filtered_api_params}")
        pt_team_defend_endpoint = leaguedashptteamdefend.LeagueDashPtTeamDefend(**api_params)

        # Get data frames
        pt_team_defend_df = pt_team_defend_endpoint.get_data_frames()[0]

        # Store DataFrame if requested
        if return_dataframe:
            dataframes["LeagueDashPtTeamDefend"] = pt_team_defend_df

            # Save to CSV if not empty
            if not pt_team_defend_df.empty:
                csv_path = _get_csv_path_for_pt_team_defend(
                    season, season_type, per_mode, defense_category, league_id,
                    team_id_nullable, conference_nullable, division_nullable
                )
                _save_dataframe_to_csv(pt_team_defend_df, csv_path)

        # Process for JSON response
        processed_data = _process_dataframe(pt_team_defend_df, single_row=False)

        # Create result dictionary
        result_dict = {
            "parameters": filtered_api_params,
            "pt_team_defend": processed_data or []
        }

        # Return response
        logger.info(f"Successfully fetched defensive team tracking stats for {season} {season_type}")
        if return_dataframe:
            return format_response(result_dict), dataframes
        return format_response(result_dict)

    except Exception as e:
        logger.error(
            f"API error in fetch_league_dash_pt_team_defend_logic: {e}",
            exc_info=True
        )
        error_msg = f"Error fetching defensive team tracking stats: {str(e)}"
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

"""
Handles fetching NBA draft history data using the drafthistory endpoint.
Allows filtering by various parameters like season year, league, team, round, and pick.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json # Not explicitly used, but format_response returns JSON string. Good to keep for context.
from typing import Optional, Dict, Any, List, Set, Union, Tuple
import pandas as pd
from functools import lru_cache

from nba_api.stats.endpoints import drafthistory
from nba_api.stats.library.parameters import LeagueID
from api_tools.utils import _process_dataframe, format_response
from config import settings
from core.errors import Errors
from utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
LEAGUE_DRAFT_CACHE_SIZE = 32

_VALID_DRAFT_LEAGUE_IDS: Set[str] = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

# --- Cache Directory Setup ---
DRAFT_HISTORY_CSV_DIR = get_cache_dir("draft_history")

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

def _get_csv_path_for_draft_history(
    season_year_nullable: Optional[str] = None,
    league_id_nullable: str = LeagueID.nba,
    team_id_nullable: Optional[int] = None,
    round_num_nullable: Optional[int] = None,
    overall_pick_nullable: Optional[int] = None
) -> str:
    """
    Generates a file path for saving draft history DataFrame as CSV.

    Args:
        season_year_nullable: Four-digit draft year (e.g., '2023')
        league_id_nullable: League ID
        team_id_nullable: NBA team ID to filter by team
        round_num_nullable: Draft round number to filter by round
        overall_pick_nullable: Overall pick number to filter by pick

    Returns:
        Path to the CSV file
    """
    # Create a string with the parameters
    params = []

    if season_year_nullable:
        params.append(f"year_{season_year_nullable}")
    else:
        params.append("year_all")

    if league_id_nullable:
        params.append(f"league_{league_id_nullable}")

    if team_id_nullable:
        params.append(f"team_{team_id_nullable}")

    if round_num_nullable:
        params.append(f"round_{round_num_nullable}")

    if overall_pick_nullable:
        params.append(f"pick_{overall_pick_nullable}")

    # Join parameters with underscores
    filename = "_".join(params) + ".csv"

    return get_cache_file_path(filename, "draft_history")

# --- Logic Function ---
def fetch_draft_history_logic(
    season_year_nullable: Optional[str] = None,
    league_id_nullable: str = LeagueID.nba,
    team_id_nullable: Optional[int] = None,
    round_num_nullable: Optional[int] = None,
    overall_pick_nullable: Optional[int] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches NBA draft history using nba_api's DraftHistory endpoint, optionally filtered by season year, league, team, round number, or overall pick.
    Provides DataFrame output capabilities.

    Args:
        season_year_nullable: Four-digit draft year (e.g., '2023'). If None, returns all years.
        league_id_nullable: League ID (default: NBA).
        team_id_nullable: NBA team ID to filter by team.
        round_num_nullable: Draft round number to filter by round.
        overall_pick_nullable: Overall pick number to filter by pick.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON-formatted string containing a list of draft picks or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.

    Notes:
        - Returns an error for invalid year format or league ID.
        - Returns an empty list if no draft picks are found for the filters.
        - Each draft pick includes player, year, round, pick, team, and organization info.
    """
    year_log_display = season_year_nullable or "All"
    logger.info(f"Executing fetch_draft_history_logic for SeasonYear: {year_log_display}, League: {league_id_nullable}, Team: {team_id_nullable}, Round: {round_num_nullable}, Pick: {overall_pick_nullable}, return_dataframe={return_dataframe}")

    # Store DataFrames if requested
    dataframes = {}

    if season_year_nullable and (not season_year_nullable.isdigit() or len(season_year_nullable) != 4):
        error_msg = Errors.INVALID_DRAFT_YEAR_FORMAT.format(year=season_year_nullable)
        logger.error(error_msg)
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if league_id_nullable not in _VALID_DRAFT_LEAGUE_IDS:
        error_response = format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id_nullable, options=", ".join(_VALID_DRAFT_LEAGUE_IDS)))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    try:
        logger.debug(f"Fetching drafthistory for SeasonYear: {year_log_display}, League: {league_id_nullable}")
        draft_endpoint = drafthistory.DraftHistory(
            league_id=league_id_nullable,
            season_year_nullable=season_year_nullable,
            team_id_nullable=team_id_nullable,
            round_num_nullable=round_num_nullable,
            overall_pick_nullable=overall_pick_nullable,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"drafthistory API call successful for SeasonYear: {year_log_display}")
        draft_df = draft_endpoint.draft_history.get_data_frame()

        # Store DataFrame if requested
        if return_dataframe:
            dataframes["draft_history"] = draft_df

            # Save to CSV if not empty
            if not draft_df.empty:
                csv_path = _get_csv_path_for_draft_history(
                    season_year_nullable=season_year_nullable,
                    league_id_nullable=league_id_nullable,
                    team_id_nullable=team_id_nullable,
                    round_num_nullable=round_num_nullable,
                    overall_pick_nullable=overall_pick_nullable
                )
                _save_dataframe_to_csv(draft_df, csv_path)

        draft_list = _process_dataframe(draft_df, single_row=False)

        if draft_list is None:
            if draft_df.empty:
                logger.warning(f"No draft history data found for year {year_log_display} with specified filters.")
                empty_result = {
                    "season_year_requested": year_log_display, "league_id": league_id_nullable,
                    "team_id_filter": team_id_nullable, "round_num_filter": round_num_nullable,
                    "overall_pick_filter": overall_pick_nullable, "draft_picks": []
                }

                if return_dataframe:
                    return format_response(empty_result), dataframes
                return format_response(empty_result)
            else:
                logger.error(f"DataFrame processing failed for draft history ({year_log_display}).")
                error_msg = Errors.DRAFT_HISTORY_PROCESSING.format(year=year_log_display)
                error_response = format_response(error=error_msg)

                if return_dataframe:
                    return error_response, dataframes
                return error_response

        result = {
            "season_year_requested": year_log_display, "league_id": league_id_nullable,
            "team_id_filter": team_id_nullable, "round_num_filter": round_num_nullable,
            "overall_pick_filter": overall_pick_nullable, "draft_picks": draft_list or []
        }

        # Add DataFrame info to the response if requested
        if return_dataframe:
            csv_path = _get_csv_path_for_draft_history(
                season_year_nullable=season_year_nullable,
                league_id_nullable=league_id_nullable,
                team_id_nullable=team_id_nullable,
                round_num_nullable=round_num_nullable,
                overall_pick_nullable=overall_pick_nullable
            )
            relative_path = get_relative_cache_path(
                os.path.basename(csv_path),
                "draft_history"
            )

            result["dataframe_info"] = {
                "message": "Draft history data has been converted to DataFrame and saved as CSV file",
                "dataframes": {
                    "draft_history": {
                        "shape": list(draft_df.shape) if not draft_df.empty else [],
                        "columns": draft_df.columns.tolist() if not draft_df.empty else [],
                        "csv_path": relative_path
                    }
                }
            }

            logger.info(f"fetch_draft_history_logic completed for SeasonYear: {year_log_display}")
            return format_response(result), dataframes

        logger.info(f"fetch_draft_history_logic completed for SeasonYear: {year_log_display}")
        return format_response(result)

    except Exception as e:
        logger.critical(f"Unexpected error in fetch_draft_history_logic for SeasonYear '{year_log_display}': {e}", exc_info=True)
        error_msg = Errors.DRAFT_HISTORY_UNEXPECTED.format(year=year_log_display, error=str(e))
        error_response = format_response(error=error_msg)

        if return_dataframe:
            return error_response, dataframes
        return error_response
"""
Handles fetching league lineup statistics with extensive filtering options.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
from functools import lru_cache
from typing import Optional, Dict, Union, Tuple

import pandas as pd
from nba_api.stats.endpoints import LeagueDashLineups
from nba_api.stats.library.parameters import (
    GroupQuantity,
    LastNGames,
    MeasureTypeDetailedDefense,
    Month,
    PaceAdjust,
    PerModeDetailed,
    Period,
    PlusMinus,
    Rank,
    SeasonTypeAllStar,
    LeagueIDNullable,
    LocationNullable,
    OutcomeNullable,
    SeasonSegmentNullable,
    ConferenceNullable,
    DivisionNullable,
    GameSegmentNullable,
    ShotClockRangeNullable
)

from config import settings
from core.errors import Errors
from api_tools.utils import (
    _process_dataframe,
    format_response
)
from utils.validation import validate_season_format, validate_date_format, validate_team_id
from utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Cache Directory Setup ---
LEAGUE_LINEUPS_CSV_DIR = get_cache_dir("league_lineups")

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

def _get_csv_path_for_league_lineups(
    season: str,
    group_quantity: int,
    measure_type: str,
    per_mode: str,
    season_type: str,
    team_id_nullable: Optional[int] = None
) -> str:
    """
    Generates a file path for saving league lineups DataFrame as CSV.

    Args:
        season: The season in YYYY-YY format
        group_quantity: Number of players in the lineup
        measure_type: Type of stats (Base, Advanced, Misc, etc.)
        per_mode: Stat mode (Totals, PerGame, Per100Possessions, etc.)
        season_type: Type of season (Regular Season, Playoffs, etc.)
        team_id_nullable: Filter by a specific team ID

    Returns:
        Path to the CSV file
    """
    # Clean measure type and per mode for filename
    clean_measure_type = measure_type.replace(" ", "_").lower()
    clean_per_mode = per_mode.replace(" ", "_").lower()
    clean_season_type = season_type.replace(" ", "_").lower()

    # Add team ID to filename if provided
    team_part = f"_team_{team_id_nullable}" if team_id_nullable else ""

    filename = f"lineups_{season}_{group_quantity}_{clean_measure_type}_{clean_per_mode}_{clean_season_type}{team_part}.csv"
    return get_cache_file_path(filename, "league_lineups")

def fetch_league_dash_lineups_logic(
    season: str,
    group_quantity: int = 5,
    last_n_games: int = LastNGames.default,
    measure_type: str = MeasureTypeDetailedDefense.base,
    month: int = Month.default,
    opponent_team_id: int = 0, # Defaults to 0 (all teams)
    pace_adjust: str = PaceAdjust.no,
    per_mode: str = PerModeDetailed.totals,
    period: int = Period.default,
    plus_minus: str = PlusMinus.no,
    rank: str = Rank.no,
    season_type: str = "Regular Season",
    conference_nullable: Optional[str] = ConferenceNullable.default,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    division_nullable: Optional[str] = DivisionNullable.default,
    game_segment_nullable: Optional[str] = GameSegmentNullable.default,
    league_id_nullable: Optional[str] = LeagueIDNullable.default, # Typically "00" for NBA
    location_nullable: Optional[str] = LocationNullable.default,
    outcome_nullable: Optional[str] = OutcomeNullable.default,
    po_round_nullable: Optional[str] = None, # NBA API docs show no enum, pass as string e.g., "1", "2"
    season_segment_nullable: Optional[str] = SeasonSegmentNullable.default,
    shot_clock_range_nullable: Optional[str] = ShotClockRangeNullable.default,
    team_id_nullable: Optional[int] = None, # Specific team ID, defaults to all
    vs_conference_nullable: Optional[str] = ConferenceNullable.default, # Yes, ConferenceNullable again for VsConference
    vs_division_nullable: Optional[str] = DivisionNullable.default, # Yes, DivisionNullable again for VsDivision
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league-wide lineup statistics with extensive filtering options.
    Provides DataFrame output capabilities.

    Args:
        season: YYYY-YY format (e.g., "2023-24").
        group_quantity: Number of players in the lineup (e.g., 2, 3, 4, 5). Defaults to 5.
        last_n_games: Filter by last N games. Defaults to 0 (all games).
        measure_type: Type of stats (Base, Advanced, Misc, etc.). Defaults to "Base".
        month: Filter by month (1-12). Defaults to 0 (all months).
        opponent_team_id: Filter by opponent team ID. Defaults to 0 (all opponents).
        pace_adjust: Pace adjust stats (Y/N). Defaults to "N".
        per_mode: Stat mode (Totals, PerGame, Per100Possessions, etc.). Defaults to "Totals".
        period: Filter by period (1-4 for quarters, 0 for full game). Defaults to 0.
        plus_minus: Include plus/minus (Y/N). Defaults to "N".
        rank: Include rank (Y/N). Defaults to "N".
        season_type: Type of season (Regular Season, Playoffs, etc.). Defaults to "Regular Season".
        conference_nullable: Filter by conference (East, West).
        date_from_nullable: Start date (YYYY-MM-DD).
        date_to_nullable: End date (YYYY-MM-DD).
        division_nullable: Filter by division.
        game_segment_nullable: Filter by game segment (First Half, Second Half, Overtime).
        league_id_nullable: League ID (e.g., "00" for NBA). Defaults to "00".
        location_nullable: Filter by location (Home, Road).
        outcome_nullable: Filter by outcome (W, L).
        po_round_nullable: Playoff round.
        season_segment_nullable: Filter by season segment (Pre All-Star, Post All-Star).
        shot_clock_range_nullable: Filter by shot clock range.
        team_id_nullable: Filter by a specific team ID.
        vs_conference_nullable: Filter by opponent conference.
        vs_division_nullable: Filter by opponent division.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string with lineup stats or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_league_dash_lineups_logic for Season: {season}, GroupQty: {group_quantity}, Measure: {measure_type}, return_dataframe={return_dataframe}")

    # Store DataFrames if requested
    dataframes = {}

    if not validate_season_format(season):
        error_response = format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
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

    if team_id_nullable is not None and not validate_team_id(team_id_nullable):
        error_response = format_response(error=Errors.INVALID_TEAM_ID_VALUE.format(team_id=team_id_nullable))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if opponent_team_id != 0 and not validate_team_id(opponent_team_id):
        error_response = format_response(error=Errors.INVALID_TEAM_ID_VALUE.format(team_id=opponent_team_id))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    # Input type validation for enums can be added if necessary, but nba_api often handles string versions.

    try:
        lineups_endpoint = LeagueDashLineups(
            season=season,
            group_quantity=group_quantity,
            last_n_games=last_n_games,
            measure_type_detailed_defense=measure_type, # Maps to library's naming
            month=month,
            opponent_team_id=opponent_team_id,
            pace_adjust=pace_adjust,
            per_mode_detailed=per_mode, # Maps to library's naming
            period=period,
            plus_minus=plus_minus,
            rank=rank,
            season_type_all_star=season_type, # Maps to library's naming
            conference_nullable=conference_nullable,
            date_from_nullable=date_from_nullable,
            date_to_nullable=date_to_nullable,
            division_simple_nullable=division_nullable,
            game_segment_nullable=game_segment_nullable,
            league_id_nullable=league_id_nullable,
            location_nullable=location_nullable,
            outcome_nullable=outcome_nullable,
            po_round_nullable=po_round_nullable,
            season_segment_nullable=season_segment_nullable,
            shot_clock_range_nullable=shot_clock_range_nullable,
            team_id_nullable=team_id_nullable,
            vs_conference_nullable=vs_conference_nullable,
            vs_division_nullable=vs_division_nullable,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"LeagueDashLineups API call successful for Season: {season}")

        lineups_df = lineups_endpoint.lineups.get_data_frame()

        # Store DataFrame if requested
        if return_dataframe:
            dataframes["lineups"] = lineups_df

            # Save to CSV if not empty
            if not lineups_df.empty:
                csv_path = _get_csv_path_for_league_lineups(
                    season=season,
                    group_quantity=group_quantity,
                    measure_type=measure_type,
                    per_mode=per_mode,
                    season_type=season_type,
                    team_id_nullable=team_id_nullable
                )
                _save_dataframe_to_csv(lineups_df, csv_path)

        lineups_list = _process_dataframe(lineups_df, single_row=False)

        if lineups_list is None:
            logger.error("DataFrame processing failed for LeagueDashLineups.")
            error_response = format_response(error=Errors.LEAGUE_DASH_LINEUPS_API_ERROR.format(error="DataFrame processing returned None unexpectedly."))
            if return_dataframe:
                return error_response, dataframes
            return error_response

        response_data = {
            "parameters": {
                "season": season,
                "group_quantity": group_quantity,
                "measure_type": measure_type,
                "per_mode": per_mode,
                "season_type": season_type,
                "team_id": team_id_nullable,
                "opponent_team_id": opponent_team_id,
                "date_from": date_from_nullable,
                "date_to": date_to_nullable
            },
            "lineups": lineups_list
        }

        # Add DataFrame info to the response if requested
        if return_dataframe:
            csv_path = _get_csv_path_for_league_lineups(
                season=season,
                group_quantity=group_quantity,
                measure_type=measure_type,
                per_mode=per_mode,
                season_type=season_type,
                team_id_nullable=team_id_nullable
            )
            relative_path = get_relative_cache_path(
                os.path.basename(csv_path),
                "league_lineups"
            )

            response_data["dataframe_info"] = {
                "message": "League lineups data has been converted to DataFrame and saved as CSV file",
                "dataframes": {
                    "lineups": {
                        "shape": list(lineups_df.shape) if not lineups_df.empty else [],
                        "columns": lineups_df.columns.tolist() if not lineups_df.empty else [],
                        "csv_path": relative_path
                    }
                }
            }

        logger.info(f"Successfully fetched {len(lineups_list)} lineup entries for Season: {season}")

        if return_dataframe:
            return format_response(response_data), dataframes
        return format_response(response_data)

    except Exception as e:
        logger.error(
            f"Error in fetch_league_dash_lineups_logic for Season {season}: {str(e)}",
            exc_info=True
        )
        error_response = format_response(error=Errors.LEAGUE_DASH_LINEUPS_API_ERROR.format(error=str(e)))
        if return_dataframe:
            return error_response, dataframes
        return error_response
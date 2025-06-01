"""
Handles fetching general team statistics, including current season dashboard stats
and historical year-by-year performance.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json # For JSONDecodeError
from typing import Optional, Dict, List, Tuple, Any, Set, Union

import pandas as pd
from nba_api.stats.endpoints import teamdashboardbygeneralsplits, teamyearbyyearstats
from nba_api.stats.library.parameters import (
    LeagueID,
    SeasonTypeAllStar,
    MeasureTypeDetailedDefense, # Note: API uses MeasureTypeDetailedDefense for teamdashboardbygeneralsplits
    PerModeDetailed,
    PerModeSimple # For teamyearbyyearstats
)

from config import settings
from core.errors import Errors
from api_tools.utils import (
    _process_dataframe,
    format_response,
    find_team_id_or_error,
    TeamNotFoundError
)
from utils.validation import _validate_season_format, validate_date_format

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
TEAM_GENERAL_STATS_CACHE_SIZE = 128
DEFAULT_HISTORICAL_PER_MODE = PerModeSimple.per_game # Sensible default for year-by-year

_TEAM_GENERAL_VALID_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_TEAM_GENERAL_VALID_PER_MODES: Set[str] = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
_TEAM_GENERAL_VALID_MEASURE_TYPES: Set[str] = {getattr(MeasureTypeDetailedDefense, attr) for attr in dir(MeasureTypeDetailedDefense) if not attr.startswith('_') and isinstance(getattr(MeasureTypeDetailedDefense, attr), str)}
_TEAM_GENERAL_VALID_LEAGUE_IDS: Set[str] = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

# --- Cache Directory Setup ---
from utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path
TEAM_GENERAL_CSV_DIR = get_cache_dir("team_general")

# --- Helper Functions for CSV Caching ---
def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves a DataFrame to a CSV file, creating the directory if it doesn't exist.

    Args:
        df: The DataFrame to save
        file_path: The path to save the CSV file
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Save DataFrame to CSV
        df.to_csv(file_path, index=False)
        logger.debug(f"Saved DataFrame to {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to {file_path}: {e}", exc_info=True)

def _get_csv_path_for_team_general(
    team_name: str,
    season: str,
    season_type: str,
    per_mode: str,
    measure_type: str,
    data_type: str
) -> str:
    """
    Generates a file path for saving team general stats DataFrame as CSV.

    Args:
        team_name: The team's name
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        per_mode: The per mode (e.g., 'PerGame', 'Totals')
        measure_type: The measure type (e.g., 'Base', 'Advanced')
        data_type: The type of data ('dashboard' or 'historical')

    Returns:
        Path to the CSV file
    """
    # Clean team name and data type for filename
    clean_team_name = team_name.replace(" ", "_").replace(".", "").lower()
    clean_season_type = season_type.replace(" ", "_").lower()
    clean_per_mode = per_mode.replace(" ", "_").lower()
    clean_measure_type = measure_type.replace(" ", "_").lower()

    filename = f"{clean_team_name}_{season}_{clean_season_type}_{clean_per_mode}_{clean_measure_type}_{data_type}.csv"
    return get_cache_file_path(filename, "team_general")

# --- Helper Functions ---
def _fetch_dashboard_general_splits_data(
    team_id: int, season: str, season_type: str, per_mode: str, measure_type: str,
    opponent_team_id: int, date_from: Optional[str], date_to: Optional[str],
    team_name: str = "",
    last_n_games: int = 0,
    league_id_nullable: Optional[str] = None,
    month: int = 0,
    period: int = 0,
    vs_division_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    pace_adjust: str = "N",
    plus_minus: str = "N",
    rank: str = "N",
    shot_clock_range_nullable: Optional[str] = None,
    po_round_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[Tuple[Dict[str, Any], Optional[str]], Tuple[Dict[str, Any], Optional[str], pd.DataFrame]]:
    """
    Fetches and processes data from teamdashboardbygeneralsplits.

    Args:
        team_id: The team's ID
        season: NBA season in YYYY-YY format
        season_type: Type of season (e.g., "Regular Season")
        per_mode: Statistical mode (e.g., "PerGame")
        measure_type: Type of statistics to retrieve (e.g., "Base", "Advanced")
        opponent_team_id: Filter by opponent team ID
        date_from: Start date filter (YYYY-MM-DD)
        date_to: End date filter (YYYY-MM-DD)
        team_name: The team's name (for CSV file naming)
        last_n_games: Number of games to include (0 for all games)
        league_id_nullable: League ID (e.g., "00" for NBA)
        month: Month number (0 for all months)
        period: Period number (0 for all periods)
        vs_division_nullable: Filter by division (e.g., "Atlantic", "Central")
        vs_conference_nullable: Filter by conference (e.g., "East", "West")
        season_segment_nullable: Filter by season segment (e.g., "Post All-Star", "Pre All-Star")
        outcome_nullable: Filter by game outcome (e.g., "W", "L")
        location_nullable: Filter by game location (e.g., "Home", "Road")
        game_segment_nullable: Filter by game segment (e.g., "First Half", "Second Half")
        pace_adjust: Whether to adjust for pace (Y/N)
        plus_minus: Whether to include plus-minus (Y/N)
        rank: Whether to include rank (Y/N)
        shot_clock_range_nullable: Filter by shot clock range
        po_round_nullable: Filter by playoff round
        return_dataframe: Whether to return the original DataFrame

    Returns:
        If return_dataframe=False:
            Tuple[Dict[str, Any], Optional[str]]: Processed data and error message (if any)
        If return_dataframe=True:
            Tuple[Dict[str, Any], Optional[str], pd.DataFrame]: Processed data, error message, and original DataFrame
    """
    dashboard_stats_dict: Dict[str, Any] = {}
    error_message: Optional[str] = None
    overall_stats_df = pd.DataFrame()  # Initialize empty DataFrame

    logger.debug(f"Fetching team dashboard stats for Team ID: {team_id}, Season: {season}, Measure: {measure_type}")
    try:
        dashboard_endpoint = teamdashboardbygeneralsplits.TeamDashboardByGeneralSplits(
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            per_mode_detailed=per_mode,
            measure_type_detailed_defense=measure_type,
            opponent_team_id=opponent_team_id,
            date_from_nullable=date_from,
            date_to_nullable=date_to,
            last_n_games=last_n_games,
            league_id_nullable=league_id_nullable,
            month=month,
            period=period,
            vs_division_nullable=vs_division_nullable,
            vs_conference_nullable=vs_conference_nullable,
            season_segment_nullable=season_segment_nullable,
            outcome_nullable=outcome_nullable,
            location_nullable=location_nullable,
            game_segment_nullable=game_segment_nullable,
            pace_adjust=pace_adjust,
            plus_minus=plus_minus,
            rank=rank,
            shot_clock_range_nullable=shot_clock_range_nullable,
            po_round_nullable=po_round_nullable,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        overall_stats_df = dashboard_endpoint.overall_team_dashboard.get_data_frame()

        # Save DataFrame to CSV if requested and not empty
        if return_dataframe and not overall_stats_df.empty and team_name:
            csv_path = _get_csv_path_for_team_general(
                team_name, season, season_type, per_mode, measure_type, "dashboard"
            )
            _save_dataframe_to_csv(overall_stats_df, csv_path)

        dashboard_stats_dict = _process_dataframe(overall_stats_df, single_row=True) or {}

        if overall_stats_df.empty and not dashboard_stats_dict: # Check if it was empty and processing yielded empty
            logger.warning(f"No dashboard stats found for team {team_id}, season {season} with measure {measure_type} and filters.")
        elif dashboard_stats_dict is None: # Should not happen if _process_dataframe returns {} for empty
            error_message = Errors.TEAM_PROCESSING.format(data_type=f"dashboard stats ({measure_type})", identifier=str(team_id), season=season)
            logger.error(error_message)
    except json.JSONDecodeError as jde:
        logger.error(f"API JSONDecodeError for team dashboard {team_id}, measure_type {measure_type}: {jde}", exc_info=True)
        error_message = Errors.TEAM_API.format(data_type=f"team dashboard ({measure_type})", identifier=str(team_id), season=season, error=f"JSONDecodeError: {str(jde)}")
    except Exception as api_error:
        error_message = Errors.TEAM_API.format(data_type=f"team dashboard ({measure_type})", identifier=str(team_id), season=season, error=str(api_error))
        logger.error(error_message, exc_info=True)

    if return_dataframe:
        return dashboard_stats_dict, error_message, overall_stats_df
    return dashboard_stats_dict, error_message

def _fetch_historical_year_by_year_stats(
    team_id: int, league_id: str, season_type_for_hist: str, # Use a distinct season_type for clarity
    team_name: str = "",
    return_dataframe: bool = False
) -> Union[Tuple[List[Dict[str, Any]], Optional[str]], Tuple[List[Dict[str, Any]], Optional[str], pd.DataFrame]]:
    """
    Fetches and processes data from teamyearbyyearstats.

    Args:
        team_id: The team's ID
        league_id: League ID (e.g., "00" for NBA)
        season_type_for_hist: Type of season for historical stats
        team_name: The team's name (for CSV file naming)
        return_dataframe: Whether to return the original DataFrame

    Returns:
        If return_dataframe=False:
            Tuple[List[Dict[str, Any]], Optional[str]]: Processed data and error message (if any)
        If return_dataframe=True:
            Tuple[List[Dict[str, Any]], Optional[str], pd.DataFrame]: Processed data, error message, and original DataFrame
    """
    historical_stats_list: List[Dict[str, Any]] = []
    error_message: Optional[str] = None
    hist_df = pd.DataFrame()  # Initialize empty DataFrame

    logger.debug(f"Fetching historical stats for Team ID: {team_id}, League: {league_id}, PerMode: {DEFAULT_HISTORICAL_PER_MODE}")
    try:
        historical_endpoint = teamyearbyyearstats.TeamYearByYearStats(
            team_id=team_id, league_id=league_id,
            season_type_all_star=season_type_for_hist, # API takes season_type, though typically 'Regular Season' for historical
            per_mode_simple=DEFAULT_HISTORICAL_PER_MODE,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        hist_df = historical_endpoint.team_stats.get_data_frame()

        # Save DataFrame to CSV if requested and not empty
        if return_dataframe and not hist_df.empty and team_name:
            csv_path = _get_csv_path_for_team_general(
                team_name, "all_seasons", season_type_for_hist, DEFAULT_HISTORICAL_PER_MODE, "base", "historical"
            )
            _save_dataframe_to_csv(hist_df, csv_path)

        historical_stats_list = _process_dataframe(hist_df, single_row=False) or []

        if hist_df.empty and not historical_stats_list:
            logger.warning(f"No historical stats found for team {team_id}.")
        elif historical_stats_list is None: # Should not happen if _process_dataframe returns [] for empty
            error_message = Errors.TEAM_PROCESSING.format(data_type="historical stats", identifier=str(team_id), season="N/A")
            logger.error(error_message)
    except Exception as hist_api_error:
        error_message = Errors.TEAM_API.format(data_type="historical stats", identifier=str(team_id), season="N/A", error=str(hist_api_error))
        logger.warning(f"Could not fetch historical stats: {error_message}", exc_info=True)

    if return_dataframe:
        return historical_stats_list, error_message, hist_df
    return historical_stats_list, error_message

# --- Main Logic Function ---
def fetch_team_stats_logic(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON, # Season for dashboard stats
    season_type: str = SeasonTypeAllStar.regular, # SeasonType for dashboard stats
    per_mode: str = PerModeDetailed.per_game, # PerMode for dashboard stats
    measure_type: str = MeasureTypeDetailedDefense.base,  # MeasureType for dashboard stats
    opponent_team_id: int = 0, # For dashboard stats
    date_from: Optional[str] = None, # For dashboard stats
    date_to: Optional[str] = None,   # For dashboard stats
    league_id: str = LeagueID.nba,    # LeagueID for historical stats (and dashboard if needed)
    last_n_games: int = 0,
    month: int = 0,
    period: int = 0,
    vs_division_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    pace_adjust: str = "N",
    plus_minus: str = "N",
    rank: str = "N",
    shot_clock_range_nullable: Optional[str] = None,
    po_round_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches comprehensive team statistics: current season dashboard stats and historical year-by-year performance.
    Provides DataFrame output capabilities.

    Args:
        team_identifier: Name, abbreviation, or ID of the team.
        season: NBA season in YYYY-YY format for dashboard stats. Defaults to current season.
        season_type: Type of season for dashboard stats. Defaults to Regular Season.
        per_mode: Statistical mode for dashboard stats. Defaults to PerGame.
        measure_type: Type of statistics to retrieve for dashboard stats. Defaults to Base.
        opponent_team_id: Filter by opponent team ID for dashboard stats. Defaults to 0 (all).
        date_from: Start date filter for dashboard stats (YYYY-MM-DD).
        date_to: End date filter for dashboard stats (YYYY-MM-DD).
        league_id: League ID for historical stats. Defaults to NBA.
        last_n_games: Number of games to include (0 for all games).
        month: Month number (0 for all months).
        period: Period number (0 for all periods).
        vs_division_nullable: Filter by division (e.g., "Atlantic", "Central").
        vs_conference_nullable: Filter by conference (e.g., "East", "West").
        season_segment_nullable: Filter by season segment (e.g., "Post All-Star", "Pre All-Star").
        outcome_nullable: Filter by game outcome (e.g., "W", "L").
        location_nullable: Filter by game location (e.g., "Home", "Road").
        game_segment_nullable: Filter by game segment (e.g., "First Half", "Second Half").
        pace_adjust: Whether to adjust for pace (Y/N).
        plus_minus: Whether to include plus-minus (Y/N).
        rank: Whether to include rank (Y/N).
        shot_clock_range_nullable: Filter by shot clock range.
        po_round_nullable: Filter by playoff round.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string with team stats or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_team_stats_logic for: '{team_identifier}', Dashboard Season: {season}, Dashboard Measure: {measure_type}, " +
              f"LastNGames: {last_n_games}, Month: {month}, Period: {period}, VsDivision: {vs_division_nullable}, " +
              f"VsConference: {vs_conference_nullable}, SeasonSegment: {season_segment_nullable}, Outcome: {outcome_nullable}, " +
              f"Location: {location_nullable}, GameSegment: {game_segment_nullable}, PaceAdjust: {pace_adjust}, " +
              f"PlusMinus: {plus_minus}, Rank: {rank}, ShotClockRange: {shot_clock_range_nullable}, " +
              f"PORound: {po_round_nullable}, return_dataframe={return_dataframe}")

    # Store DataFrames if requested
    dataframes = {}

    # Parameter Validations
    if not team_identifier or not str(team_identifier).strip():
        if return_dataframe:
            return format_response(error=Errors.TEAM_IDENTIFIER_EMPTY), dataframes
        return format_response(error=Errors.TEAM_IDENTIFIER_EMPTY)

    if not season or not _validate_season_format(season): # Validates dashboard season
        if return_dataframe:
            return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season)), dataframes
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    if date_from and not validate_date_format(date_from):
        if return_dataframe:
            return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from)), dataframes
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from))

    if date_to and not validate_date_format(date_to):
        if return_dataframe:
            return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to)), dataframes
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to))

    if season_type not in _TEAM_GENERAL_VALID_SEASON_TYPES:
        if return_dataframe:
            return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_TEAM_GENERAL_VALID_SEASON_TYPES)[:5]))), dataframes
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_TEAM_GENERAL_VALID_SEASON_TYPES)[:5])))

    if per_mode not in _TEAM_GENERAL_VALID_PER_MODES:
        if return_dataframe:
            return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_TEAM_GENERAL_VALID_PER_MODES)[:5]))), dataframes
        return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_TEAM_GENERAL_VALID_PER_MODES)[:5])))

    if measure_type not in _TEAM_GENERAL_VALID_MEASURE_TYPES:
        if return_dataframe:
            return format_response(error=Errors.INVALID_MEASURE_TYPE.format(value=measure_type, options=", ".join(list(_TEAM_GENERAL_VALID_MEASURE_TYPES)[:5]))), dataframes
        return format_response(error=Errors.INVALID_MEASURE_TYPE.format(value=measure_type, options=", ".join(list(_TEAM_GENERAL_VALID_MEASURE_TYPES)[:5])))

    if league_id not in _TEAM_GENERAL_VALID_LEAGUE_IDS:
        if return_dataframe:
            return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_TEAM_GENERAL_VALID_LEAGUE_IDS)[:3]))), dataframes
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_TEAM_GENERAL_VALID_LEAGUE_IDS)[:3])))

    try:
        team_id, team_actual_name = find_team_id_or_error(team_identifier)
        all_errors: List[str] = []

        # Fetch dashboard stats with DataFrame if requested
        if return_dataframe:
            dashboard_stats, dash_err, dashboard_df = _fetch_dashboard_general_splits_data(
                team_id, season, season_type, per_mode, measure_type, opponent_team_id, date_from, date_to,
                team_name=team_actual_name,
                last_n_games=last_n_games,
                league_id_nullable=league_id,
                month=month,
                period=period,
                vs_division_nullable=vs_division_nullable,
                vs_conference_nullable=vs_conference_nullable,
                season_segment_nullable=season_segment_nullable,
                outcome_nullable=outcome_nullable,
                location_nullable=location_nullable,
                game_segment_nullable=game_segment_nullable,
                pace_adjust=pace_adjust,
                plus_minus=plus_minus,
                rank=rank,
                shot_clock_range_nullable=shot_clock_range_nullable,
                po_round_nullable=po_round_nullable,
                return_dataframe=True
            )
            dataframes["dashboard"] = dashboard_df
        else:
            dashboard_stats, dash_err = _fetch_dashboard_general_splits_data(
                team_id, season, season_type, per_mode, measure_type, opponent_team_id, date_from, date_to,
                last_n_games=last_n_games,
                league_id_nullable=league_id,
                month=month,
                period=period,
                vs_division_nullable=vs_division_nullable,
                vs_conference_nullable=vs_conference_nullable,
                season_segment_nullable=season_segment_nullable,
                outcome_nullable=outcome_nullable,
                location_nullable=location_nullable,
                game_segment_nullable=game_segment_nullable,
                pace_adjust=pace_adjust,
                plus_minus=plus_minus,
                rank=rank,
                shot_clock_range_nullable=shot_clock_range_nullable,
                po_round_nullable=po_round_nullable
            )

        if dash_err: all_errors.append(dash_err)

        # Fetch historical stats with DataFrame if requested
        if return_dataframe:
            historical_stats, hist_err, historical_df = _fetch_historical_year_by_year_stats(
                team_id, league_id, season_type,
                team_name=team_actual_name, return_dataframe=True
            )
            dataframes["historical"] = historical_df
        else:
            historical_stats, hist_err = _fetch_historical_year_by_year_stats(
                team_id, league_id, season_type
            )

        if hist_err: all_errors.append(hist_err)

        if not dashboard_stats and not historical_stats and all_errors:
            # If both fetches failed and produced errors
            error_summary = Errors.TEAM_ALL_FAILED.format(identifier=team_identifier, season=season, errors_list=', '.join(all_errors))
            logger.error(error_summary)

            if return_dataframe:
                return format_response(error=error_summary), dataframes
            return format_response(error=error_summary)

        result = {
            "team_id": team_id, "team_name": team_actual_name,
            "parameters": {
                "season_for_dashboard": season,
                "season_type_for_dashboard": season_type,
                "per_mode_for_dashboard": per_mode,
                "measure_type_for_dashboard": measure_type,
                "opponent_team_id_for_dashboard": opponent_team_id,
                "date_from_for_dashboard": date_from,
                "date_to_for_dashboard": date_to,
                "league_id_for_historical": league_id,
                "season_type_for_historical": season_type,
                "last_n_games": last_n_games,
                "month": month,
                "period": period,
                "vs_division": vs_division_nullable,
                "vs_conference": vs_conference_nullable,
                "season_segment": season_segment_nullable,
                "outcome": outcome_nullable,
                "location": location_nullable,
                "game_segment": game_segment_nullable,
                "pace_adjust": pace_adjust,
                "plus_minus": plus_minus,
                "rank": rank,
                "shot_clock_range": shot_clock_range_nullable,
                "po_round": po_round_nullable
            },
            "current_season_dashboard_stats": dashboard_stats, # Renamed for clarity
            "historical_year_by_year_stats": historical_stats # Renamed for clarity
        }
        if all_errors:
            result["partial_errors"] = all_errors

        logger.info(f"fetch_team_stats_logic completed for Team ID: {team_id}, Dashboard Season: {season}")

        if return_dataframe:
            # Add DataFrame metadata to the response
            result["dataframe_info"] = {
                "message": "Team stats data has been converted to DataFrames and saved as CSV files",
                "dataframes": {}
            }

            # Add dashboard DataFrame metadata if available
            if "dashboard" in dataframes and not dataframes["dashboard"].empty:
                dashboard_csv_path = _get_csv_path_for_team_general(
                    team_actual_name, season, season_type, per_mode, measure_type, "dashboard"
                )
                csv_filename = os.path.basename(dashboard_csv_path)
                relative_path = get_relative_cache_path(csv_filename, "team_general")

                result["dataframe_info"]["dataframes"]["dashboard"] = {
                    "shape": list(dataframes["dashboard"].shape),
                    "columns": dataframes["dashboard"].columns.tolist(),
                    "csv_path": relative_path
                }

            # Add historical DataFrame metadata if available
            if "historical" in dataframes and not dataframes["historical"].empty:
                historical_csv_path = _get_csv_path_for_team_general(
                    team_actual_name, "all_seasons", season_type, DEFAULT_HISTORICAL_PER_MODE, "base", "historical"
                )
                csv_filename = os.path.basename(historical_csv_path)
                relative_path = get_relative_cache_path(csv_filename, "team_general")

                result["dataframe_info"]["dataframes"]["historical"] = {
                    "shape": list(dataframes["historical"].shape),
                    "columns": dataframes["historical"].columns.tolist(),
                    "csv_path": relative_path
                }

            return format_response(result), dataframes
        return format_response(result)

    except (TeamNotFoundError, ValueError) as e: # From find_team_id_or_error
        logger.warning(f"Team lookup or initial validation failed for '{team_identifier}': {e}")

        if return_dataframe:
            return format_response(error=str(e)), dataframes
        return format_response(error=str(e))

    except Exception as e: # Catch-all for unexpected issues in orchestration
        error_msg = Errors.TEAM_UNEXPECTED.format(identifier=team_identifier, season=season, error=str(e))
        logger.critical(error_msg, exc_info=True)

        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)
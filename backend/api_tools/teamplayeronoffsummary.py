import logging
import json
import os # Added for path operations
from typing import Optional, Dict, Any, Union, Tuple
import pandas as pd
from nba_api.stats.endpoints import teamplayeronoffsummary
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, LeagueID, MeasureTypeDetailedDefense
)
from ..config import settings
from ..core.errors import Errors
from .utils import format_response, _process_dataframe, find_team_id_or_error
from ..utils.validation import _validate_season_format, validate_date_format
from ..utils.path_utils import get_cache_dir, get_cache_file_path # Added imports

logger = logging.getLogger(__name__)

# Define cache directory
TEAM_PLAYER_ON_OFF_CSV_DIR = get_cache_dir("team_player_on_off_summary")

_VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_VALID_PER_MODES = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
_VALID_MEASURE_TYPES = {getattr(MeasureTypeDetailedDefense, attr) for attr in dir(MeasureTypeDetailedDefense) if not attr.startswith('_') and isinstance(getattr(MeasureTypeDetailedDefense, attr), str)}
_VALID_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

# --- Helper Functions for CSV Caching ---
def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves a DataFrame to a CSV file.

    Args:
        df: DataFrame to save
        file_path: Path to save the CSV file
    """
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        df.to_csv(file_path, index=False)
        logger.info(f"Saved DataFrame to CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)

def _get_csv_path_for_team_player_on_off_summary(
    team_id: str,
    season: str,
    season_type: str,
    per_mode: str,
    measure_type: str,
    dashboard_type: str # To distinguish between overall, on_court, off_court
) -> str:
    """
    Generates a file path for saving team player on/off summary DataFrame as CSV.

    Args:
        team_id: The team's ID
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        per_mode: The per mode (e.g., 'PerGame', 'Totals')
        measure_type: The measure type (e.g., 'Base', 'Advanced')
        dashboard_type: The type of dashboard (e.g., 'overall', 'on_court')

    Returns:
        Path to the CSV file
    """
    clean_season_type = season_type.replace(" ", "_").lower()
    clean_per_mode = per_mode.replace(" ", "_").lower()
    clean_measure_type = measure_type.replace(" ", "_").lower()
    clean_dashboard_type = dashboard_type.replace(" ", "_").lower()

    filename = f"team_{team_id}_onoffsummary_{clean_dashboard_type}_{season}_{clean_season_type}_{clean_per_mode}_{clean_measure_type}.csv"
    return get_cache_file_path(filename, "team_player_on_off_summary")

def fetch_teamplayeronoffsummary_logic(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.totals,
    measure_type: str = MeasureTypeDetailedDefense.base,
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    pace_adjust: str = "N",
    period: int = 0,
    plus_minus: str = "N",
    rank: str = "N",
    vs_division: Optional[str] = None,
    vs_conference: Optional[str] = None,
    season_segment: Optional[str] = None,
    outcome: Optional[str] = None,
    location: Optional[str] = None,
    league_id: Optional[str] = None,
    game_segment: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches team player on/off summary statistics from the NBA API.
    Args:
        team_identifier: Name, abbreviation, or ID of the team
        season: NBA season in YYYY-YY format
        season_type: Type of season (e.g., 'Regular Season', 'Playoffs')
        per_mode: Statistical mode (e.g., 'PerGame', 'Totals')
        measure_type: Measure type (e.g., 'Base', 'Advanced')
        last_n_games: Number of most recent games to include
        month: Filter by month (0 for all)
        opponent_team_id: Filter by opponent team ID
        pace_adjust: Whether to adjust for pace ('Y' or 'N')
        period: Filter by period (0 for all)
        plus_minus: Whether to include plus/minus ('Y' or 'N')
        rank: Whether to include statistical ranks ('Y' or 'N')
        vs_division: Filter by division
        vs_conference: Filter by conference
        season_segment: Filter by season segment
        outcome: Filter by game outcome ('W' or 'L')
        location: Filter by game location ('Home' or 'Road')
        league_id: League ID
        game_segment: Filter by game segment
        date_from: Start date filter (YYYY-MM-DD)
        date_to: End date filter (YYYY-MM-DD)
        return_dataframe: Whether to return DataFrames along with the JSON response
    Returns:
        If return_dataframe=False:
            str: A JSON string containing the team player on/off summary data or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string and a dictionary of DataFrames.
    """
    dataframes = {}
    logger.info(f"Executing fetch_teamplayeronoffsummary_logic for '{team_identifier}', season {season}, type {season_type}, return_dataframe={return_dataframe}")

    # Validate season
    if not season or not _validate_season_format(season):
        error_msg = Errors.INVALID_SEASON_FORMAT.format(season=season)
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    # Validate dates
    if date_from and not validate_date_format(date_from):
        error_msg = Errors.INVALID_DATE_FORMAT.format(date=date_from)
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    if date_to and not validate_date_format(date_to):
        error_msg = Errors.INVALID_DATE_FORMAT.format(date=date_to)
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    # Validate season type
    if season_type not in _VALID_SEASON_TYPES:
        error_msg = Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_SEASON_TYPES)[:5]))
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    # Validate per_mode
    if per_mode not in _VALID_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_PER_MODES)[:5]))
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    # Validate measure_type
    if measure_type not in _VALID_MEASURE_TYPES:
        error_msg = Errors.INVALID_MEASURE_TYPE.format(value=measure_type, options=", ".join(list(_VALID_MEASURE_TYPES)[:5]))
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    # Validate league_id
    if league_id and league_id not in _VALID_LEAGUE_IDS:
        error_msg = Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_VALID_LEAGUE_IDS)[:5]))
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    try:
        team_id, team_actual_name = find_team_id_or_error(team_identifier)
    except Exception as e:
        logger.error(f"Error finding team: {e}", exc_info=True)
        if return_dataframe:
            return format_response(error=str(e)), dataframes
        return format_response(error=str(e))

    try:
        endpoint = teamplayeronoffsummary.TeamPlayerOnOffSummary(
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            per_mode_detailed=per_mode,
            measure_type_detailed_defense=measure_type,
            last_n_games=last_n_games,
            month=month,
            opponent_team_id=opponent_team_id,
            pace_adjust=pace_adjust,
            period=period,
            plus_minus=plus_minus,
            rank=rank,
            vs_division_nullable=vs_division,
            vs_conference_nullable=vs_conference,
            season_segment_nullable=season_segment,
            outcome_nullable=outcome,
            location_nullable=location,
            league_id_nullable=league_id,
            game_segment_nullable=game_segment,
            date_from_nullable=date_from,
            date_to_nullable=date_to,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )

        # DataFrames from the API response
        overall_df = endpoint.overall_team_player_on_off_summary.get_data_frame()
        off_court_df = endpoint.players_off_court_team_player_on_off_summary.get_data_frame()
        on_court_df = endpoint.players_on_court_team_player_on_off_summary.get_data_frame()

        if return_dataframe:
            dataframes["overall"] = overall_df
            dataframes["off_court"] = off_court_df
            dataframes["on_court"] = on_court_df

            # Save DataFrames to CSV
            if not overall_df.empty:
                csv_path_overall = _get_csv_path_for_team_player_on_off_summary(
                    str(team_id), season, season_type, per_mode, measure_type, "overall"
                )
                _save_dataframe_to_csv(overall_df, csv_path_overall)
            
            if not off_court_df.empty:
                csv_path_off_court = _get_csv_path_for_team_player_on_off_summary(
                    str(team_id), season, season_type, per_mode, measure_type, "off_court"
                )
                _save_dataframe_to_csv(off_court_df, csv_path_off_court)

            if not on_court_df.empty:
                csv_path_on_court = _get_csv_path_for_team_player_on_off_summary(
                    str(team_id), season, season_type, per_mode, measure_type, "on_court"
                )
                _save_dataframe_to_csv(on_court_df, csv_path_on_court)

        # Process DataFrames for JSON response
        overall_list = _process_dataframe(overall_df, single_row=False)
        off_court_list = _process_dataframe(off_court_df, single_row=False)
        on_court_list = _process_dataframe(on_court_df, single_row=False)

        response_data = {
            "team_name": team_actual_name,
            "team_id": team_id,
            "parameters": {
                "season": season,
                "season_type": season_type,
                "per_mode": per_mode,
                "measure_type": measure_type,
                "last_n_games": last_n_games,
                "month": month,
                "opponent_team_id": opponent_team_id,
                "pace_adjust": pace_adjust,
                "period": period,
                "plus_minus": plus_minus,
                "rank": rank,
                "vs_division": vs_division,
                "vs_conference": vs_conference,
                "season_segment": season_segment,
                "outcome": outcome,
                "location": location,
                "league_id": league_id,
                "game_segment": game_segment,
                "date_from": date_from,
                "date_to": date_to
            },
            "overall_team_player_on_off_summary": overall_list,
            "players_off_court_team_player_on_off_summary": off_court_list,
            "players_on_court_team_player_on_off_summary": on_court_list
        }

        if return_dataframe:
            return format_response(response_data), dataframes
        return format_response(response_data)

    except Exception as api_error:
        logger.error(f"nba_api teamplayeronoffsummary failed: {api_error}", exc_info=True)
        error_label = team_actual_name if 'team_actual_name' in locals() else team_identifier
        error_msg = Errors.TEAM_PLAYER_ON_OFF_SUMMARY_API.format(identifier=error_label, error=str(api_error)) if hasattr(Errors, "TEAM_PLAYER_ON_OFF_SUMMARY_API") else Errors.API_ERROR.format(error=str(api_error))
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg) 
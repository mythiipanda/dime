import logging
import json
import os # Added for path operations
from typing import Optional, Dict, Any, Union, Tuple
import pandas as pd
from nba_api.stats.endpoints import teamvsplayer
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, LeagueID, MeasureTypeDetailedDefense
)
from ..config import settings
from ..core.errors import Errors
from .utils import format_response, _process_dataframe, find_team_id_or_error, find_player_id_or_error
from ..utils.validation import _validate_season_format, validate_date_format
from ..utils.path_utils import get_cache_dir, get_cache_file_path # Added imports

logger = logging.getLogger(__name__)

# Define cache directory
TEAM_VS_PLAYER_CSV_DIR = get_cache_dir("team_vs_player")

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
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        df.to_csv(file_path, index=False)
        logger.info(f"Saved DataFrame to CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)

def _get_csv_path_for_team_vs_player(
    team_id: str,
    vs_player_id: str,
    season: str,
    season_type: str,
    per_mode: str,
    measure_type: str,
    dashboard_type: str 
) -> str:
    """
    Generates a file path for saving team vs player DataFrame as CSV.

    Args:
        team_id: The team's ID
        vs_player_id: The opposing player's ID
        season: The season in YYYY-YY format
        season_type: The season type
        per_mode: The per mode
        measure_type: The measure type
        dashboard_type: The type of dashboard (e.g., 'overall', 'on_off_court')

    Returns:
        Path to the CSV file
    """
    clean_season_type = season_type.replace(" ", "_").lower()
    clean_per_mode = per_mode.replace(" ", "_").lower()
    clean_measure_type = measure_type.replace(" ", "_").lower()
    clean_dashboard_type = dashboard_type.replace(" ", "_").lower()

    filename = f"team_{team_id}_vs_player_{vs_player_id}_{clean_dashboard_type}_{season}_{clean_season_type}_{clean_per_mode}_{clean_measure_type}.csv"
    return get_cache_file_path(filename, "team_vs_player")

def fetch_teamvsplayer_logic(
    team_identifier: str,
    vs_player_identifier: str,
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
    player_identifier: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches team vs player statistics from the NBA API.
    Args:
        team_identifier: Name, abbreviation, or ID of the team
        vs_player_identifier: Name or ID of the opposing player
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
        player_identifier: (Optional) Player name or ID for PlayerID param
        return_dataframe: Whether to return DataFrames along with the JSON response
    Returns:
        If return_dataframe=False:
            str: A JSON string containing the team vs player data or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string and a dictionary of DataFrames.
    """
    dataframes = {}
    logger.info(f"Executing fetch_teamvsplayer_logic for team '{team_identifier}', vs_player '{vs_player_identifier}', season {season}, type {season_type}, return_dataframe={return_dataframe}")

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
        vs_player_id, vs_player_actual_name = find_player_id_or_error(vs_player_identifier)
        player_id = None
        if player_identifier:
            player_id, _ = find_player_id_or_error(player_identifier)
    except Exception as e:
        logger.error(f"Error finding team/player: {e}", exc_info=True)
        if return_dataframe:
            return format_response(error=str(e)), dataframes
        return format_response(error=str(e))

    try:
        endpoint = teamvsplayer.TeamVsPlayer(
            team_id=team_id,
            vs_player_id=vs_player_id,
            season=season,
            season_type_playoffs=season_type,
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
            player_id_nullable=player_id,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )

        # DataFrames from the API response
        overall_df = endpoint.overall.get_data_frame()
        on_off_court_df = endpoint.on_off_court.get_data_frame()
        shot_area_overall_df = endpoint.shot_area_overall.get_data_frame()
        shot_area_on_court_df = endpoint.shot_area_on_court.get_data_frame()
        shot_area_off_court_df = endpoint.shot_area_off_court.get_data_frame()
        shot_distance_overall_df = endpoint.shot_distance_overall.get_data_frame()
        shot_distance_on_court_df = endpoint.shot_distance_on_court.get_data_frame()
        shot_distance_off_court_df = endpoint.shot_distance_off_court.get_data_frame()
        vs_player_overall_df = endpoint.vs_player_overall.get_data_frame()

        if return_dataframe:
            dataframes = {
                "overall": overall_df,
                "on_off_court": on_off_court_df,
                "shot_area_overall": shot_area_overall_df,
                "shot_area_on_court": shot_area_on_court_df,
                "shot_area_off_court": shot_area_off_court_df,
                "shot_distance_overall": shot_distance_overall_df,
                "shot_distance_on_court": shot_distance_on_court_df,
                "shot_distance_off_court": shot_distance_off_court_df,
                "vs_player_overall": vs_player_overall_df
            }
            # Save DataFrames to CSV
            for df_key, df_value in dataframes.items():
                if not df_value.empty:
                    csv_path = _get_csv_path_for_team_vs_player(
                        str(team_id),
                        str(vs_player_id),
                        season,
                        season_type,
                        per_mode,
                        measure_type,
                        dashboard_type=df_key
                    )
                    _save_dataframe_to_csv(df_value, csv_path)

        # Process DataFrames for JSON response
        response_data = {
            "team_name": team_actual_name,
            "team_id": team_id,
            "vs_player_name": vs_player_actual_name,
            "vs_player_id": vs_player_id,
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
                "date_to": date_to,
                "player_id": player_id
            },
            "overall": _process_dataframe(overall_df, single_row=False),
            "on_off_court": _process_dataframe(on_off_court_df, single_row=False),
            "shot_area_overall": _process_dataframe(shot_area_overall_df, single_row=False),
            "shot_area_on_court": _process_dataframe(shot_area_on_court_df, single_row=False),
            "shot_area_off_court": _process_dataframe(shot_area_off_court_df, single_row=False),
            "shot_distance_overall": _process_dataframe(shot_distance_overall_df, single_row=False),
            "shot_distance_on_court": _process_dataframe(shot_distance_on_court_df, single_row=False),
            "shot_distance_off_court": _process_dataframe(shot_distance_off_court_df, single_row=False),
            "vs_player_overall": _process_dataframe(vs_player_overall_df, single_row=False)
        }

        if return_dataframe:
            return format_response(response_data), dataframes
        return format_response(response_data)

    except Exception as api_error:
        logger.error(f"nba_api teamvsplayer failed: {api_error}", exc_info=True)
        # Use team_actual_name or vs_player_actual_name if available for better error context
        error_identifier_context = f"team '{team_actual_name if 'team_actual_name' in locals() else team_identifier}' vs player '{vs_player_actual_name if 'vs_player_actual_name' in locals() else vs_player_identifier}'"
        error_msg = Errors.TEAM_VS_PLAYER_API.format(identifier=error_identifier_context, error=str(api_error)) if hasattr(Errors, "TEAM_VS_PLAYER_API") else Errors.API_ERROR.format(error=str(api_error))
        if return_dataframe:
            return format_response(error=error_msg), dataframes
        return format_response(error=error_msg) 
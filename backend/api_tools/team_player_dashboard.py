import logging
import json
from typing import Optional, Dict, Any, Union, Tuple
import pandas as pd
from nba_api.stats.endpoints import teamplayerdashboard
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, LeagueID, MeasureTypeDetailedDefense
)
from ..config import settings
from ..core.errors import Errors
from .utils import format_response, _process_dataframe, find_team_id_or_error
from ..utils.validation import _validate_season_format, validate_date_format

logger = logging.getLogger(__name__)

_VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_VALID_PER_MODES = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
# Note: TeamPlayerDashboard uses MeasureTypeDetailedDefense for its MeasureType parameter
_VALID_MEASURE_TYPES = {getattr(MeasureTypeDetailedDefense, attr) for attr in dir(MeasureTypeDetailedDefense) if not attr.startswith('_') and isinstance(getattr(MeasureTypeDetailedDefense, attr), str)}
_VALID_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

def fetch_team_player_dashboard_logic(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.totals,
    measure_type: str = MeasureTypeDetailedDefense.base,
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    pace_adjust: str = "N", # Valid: Y, N
    period: int = 0,
    plus_minus: str = "N", # Valid: Y, N
    rank: str = "N", # Valid: Y, N
    vs_division_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    shot_clock_range_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    po_round_nullable: Optional[int] = None, # Playoff round
    outcome_nullable: Optional[str] = None, # Valid: W, L
    location_nullable: Optional[str] = None, # Valid: Home, Road
    league_id_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None, # Valid: First Half, Second Half, Overtime
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches team player dashboard statistics (PlayersSeasonTotals and TeamOverall) from the NBA API.

    Args:
        team_identifier: Name, abbreviation, or ID of the team.
        season: NBA season in YYYY-YY format.
        season_type: Type of season (e.g., 'Regular Season', 'Playoffs').
        per_mode: Statistical mode (e.g., 'PerGame', 'Totals').
        measure_type: Measure type (e.g., 'Base', 'Advanced'). Used by the API as MeasureTypeDetailedDefense.
        last_n_games: Number of most recent games to include.
        month: Filter by month (0 for all).
        opponent_team_id: Filter by opponent team ID.
        pace_adjust: Whether to adjust for pace ('Y' or 'N').
        period: Filter by period (0 for all).
        plus_minus: Whether to include plus/minus ('Y' or 'N').
        rank: Whether to include statistical ranks ('Y' or 'N').
        vs_division_nullable: Filter by division.
        vs_conference_nullable: Filter by conference.
        shot_clock_range_nullable: Filter by shot clock range.
        season_segment_nullable: Filter by season segment.
        po_round_nullable: Filter by playoff round.
        outcome_nullable: Filter by game outcome ('W' or 'L').
        location_nullable: Filter by game location ('Home' or 'Road').
        league_id_nullable: League ID.
        game_segment_nullable: Filter by game segment.
        date_from_nullable: Start date filter (YYYY-MM-DD).
        date_to_nullable: End date filter (YYYY-MM-DD).
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: A JSON string containing the team player dashboard data or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames {'players_season_totals': df, 'team_overall': df}.
    """
    dataframes = {}
    logger.info(f"Executing fetch_team_player_dashboard_logic for team '{team_identifier}', season {season}, measure_type {measure_type}, return_dataframe={return_dataframe}")

    # Parameter Validations
    if not team_identifier or not str(team_identifier).strip():
        error_msg = Errors.TEAM_IDENTIFIER_EMPTY
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    if not season or not _validate_season_format(season):
        error_msg = Errors.INVALID_SEASON_FORMAT.format(season=season)
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    if date_from_nullable and not validate_date_format(date_from_nullable):
        error_msg = Errors.INVALID_DATE_FORMAT.format(date=date_from_nullable)
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    if date_to_nullable and not validate_date_format(date_to_nullable):
        error_msg = Errors.INVALID_DATE_FORMAT.format(date=date_to_nullable)
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    if season_type not in _VALID_SEASON_TYPES:
        error_msg = Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_SEASON_TYPES)[:5]))
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    if per_mode not in _VALID_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_PER_MODES)[:5]))
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    if measure_type not in _VALID_MEASURE_TYPES: # Uses MeasureTypeDetailedDefense
        error_msg = Errors.INVALID_MEASURE_TYPE.format(value=measure_type, options=", ".join(list(_VALID_MEASURE_TYPES)[:5]))
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    if league_id_nullable and league_id_nullable not in _VALID_LEAGUE_IDS:
        error_msg = Errors.INVALID_LEAGUE_ID.format(value=league_id_nullable, options=", ".join(list(_VALID_LEAGUE_IDS)[:5]))
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    # Validate PaceAdjust, PlusMinus, Rank (Y/N)
    for param_name, param_value in [("pace_adjust", pace_adjust), ("plus_minus", plus_minus), ("rank", rank)]:
        if param_value not in ["Y", "N"]:
            error_msg = f"Invalid {param_name} value: '{param_value}'. Must be 'Y' or 'N'."
            if return_dataframe: return format_response(error=error_msg), dataframes
            return format_response(error=error_msg)
            
    # Validate Outcome (W/L)
    if outcome_nullable and outcome_nullable not in ["W", "L"]:
        error_msg = f"Invalid outcome_nullable value: '{outcome_nullable}'. Must be 'W' or 'L'."
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    # Validate Location (Home/Road)
    if location_nullable and location_nullable not in ["Home", "Road"]:
        error_msg = f"Invalid location_nullable value: '{location_nullable}'. Must be 'Home' or 'Road'."
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)
        
    # Validate GameSegment (First Half, Second Half, Overtime)
    if game_segment_nullable and game_segment_nullable not in ["First Half", "Second Half", "Overtime"]:
        error_msg = f"Invalid game_segment_nullable value: '{game_segment_nullable}'. Must be 'First Half', 'Second Half', or 'Overtime'."
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    try:
        team_id, team_actual_name = find_team_id_or_error(team_identifier)
    except Exception as e:
        logger.error(f"Error finding team '{team_identifier}': {e}", exc_info=True)
        if return_dataframe: return format_response(error=str(e)), dataframes
        return format_response(error=str(e))

    try:
        endpoint = teamplayerdashboard.TeamPlayerDashboard(
            team_id=team_id,
            season=season,
            season_type_all_star=season_type, # Corrected from season_type_playoffs
            per_mode_detailed=per_mode,
            measure_type_detailed_defense=measure_type, # Corrected param name
            last_n_games=last_n_games,
            month=month,
            opponent_team_id=opponent_team_id,
            pace_adjust=pace_adjust,
            period=period,
            plus_minus=plus_minus,
            rank=rank,
            vs_division_nullable=vs_division_nullable,
            vs_conference_nullable=vs_conference_nullable,
            shot_clock_range_nullable=shot_clock_range_nullable,
            season_segment_nullable=season_segment_nullable,
            po_round_nullable=po_round_nullable,
            outcome_nullable=outcome_nullable,
            location_nullable=location_nullable,
            league_id_nullable=league_id_nullable,
            game_segment_nullable=game_segment_nullable,
            date_from_nullable=date_from_nullable,
            date_to_nullable=date_to_nullable,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )

        players_season_totals_df = endpoint.players_season_totals.get_data_frame()
        team_overall_df = endpoint.team_overall.get_data_frame()

        if return_dataframe:
            dataframes = {
                "players_season_totals": players_season_totals_df,
                "team_overall": team_overall_df
            }

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
                "vs_division_nullable": vs_division_nullable,
                "vs_conference_nullable": vs_conference_nullable,
                "shot_clock_range_nullable": shot_clock_range_nullable,
                "season_segment_nullable": season_segment_nullable,
                "po_round_nullable": po_round_nullable,
                "outcome_nullable": outcome_nullable,
                "location_nullable": location_nullable,
                "league_id_nullable": league_id_nullable,
                "game_segment_nullable": game_segment_nullable,
                "date_from_nullable": date_from_nullable,
                "date_to_nullable": date_to_nullable
            },
            "players_season_totals": _process_dataframe(players_season_totals_df, single_row=False),
            "team_overall": _process_dataframe(team_overall_df, single_row=True) # TeamOverall is usually a single row
        }
        
        logger.info(f"Successfully fetched TeamPlayerDashboard for team_id {team_id}")
        if return_dataframe:
            return format_response(response_data), dataframes
        return format_response(response_data)

    except json.JSONDecodeError as jde:
        logger.error(f"NBA API JSONDecodeError for TeamPlayerDashboard, team '{team_actual_name}': {jde}", exc_info=True)
        error_msg = Errors.NBA_API_TIMEOUT_OR_DECODE_ERROR.format(endpoint_name="TeamPlayerDashboard", details=str(jde))
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)
    except Exception as api_error:
        logger.error(f"NBA API error for TeamPlayerDashboard, team '{team_actual_name}': {api_error}", exc_info=True)
        error_msg = Errors.TEAM_PLAYER_DASHBOARD_API.format(identifier=team_actual_name, error=str(api_error)) if hasattr(Errors, "TEAM_PLAYER_DASHBOARD_API") else f"API error for TeamPlayerDashboard: {str(api_error)}"
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg) 
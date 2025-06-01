import logging
import json
from typing import Optional, Dict, Any, Union, Tuple
import pandas as pd
from nba_api.stats.endpoints import teamplayeronoffdetails
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, LeagueID, MeasureTypeDetailedDefense # MeasureType is MeasureTypeDetailedDefense for this endpoint
)
from config import settings
from core.errors import Errors
from api_tools.utils import format_response, _process_dataframe, find_team_id_or_error
from utils.validation import _validate_season_format, validate_date_format

logger = logging.getLogger(__name__)

_VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_VALID_PER_MODES = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
_VALID_MEASURE_TYPES = {getattr(MeasureTypeDetailedDefense, attr) for attr in dir(MeasureTypeDetailedDefense) if not attr.startswith('_') and isinstance(getattr(MeasureTypeDetailedDefense, attr), str)}
_VALID_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

# Specific validation for nullable string choice parameters
_VALID_VS_DIVISIONS = {None, "", "Atlantic", "Central", "Northwest", "Pacific", "Southeast", "Southwest", "East", "West"}
_VALID_VS_CONFERENCES = {None, "", "East", "West"}
_VALID_SEASON_SEGMENTS = {None, "", "Post All-Star", "Pre All-Star"}
_VALID_OUTCOMES = {None, "", "W", "L"}
_VALID_LOCATIONS = {None, "", "Home", "Road"}
_VALID_GAME_SEGMENTS = {None, "", "First Half", "Overtime", "Second Half"}


def fetch_team_player_on_off_details_logic(
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
    vs_division_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    league_id_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches detailed on/off court statistics for players of a specific team.

    Retrieves three main data sets:
    - OverallTeamPlayerOnOffDetails: Summary stats for the team.
    - PlayersOffCourtTeamPlayerOnOffDetails: Team stats when specific players are OFF the court.
    - PlayersOnCourtTeamPlayerOnOffDetails: Team stats when specific players are ON the court.

    Args:
        team_identifier: Name, abbreviation, or ID of the team.
        season: NBA season in YYYY-YY format.
        season_type: Type of season (e.g., 'Regular Season', 'Playoffs').
        per_mode: Statistical mode (e.g., 'PerGame', 'Totals').
        measure_type: Measure type (e.g., 'Base', 'Advanced'). API uses MeasureTypeDetailedDefense.
        last_n_games: Filter by the last N games.
        month: Filter by month (1-12, 0 for all).
        opponent_team_id: Filter by opponent team ID (0 for all).
        pace_adjust: Adjust for pace ('Y' or 'N').
        period: Filter by period (0 for all, 1-4 for quarters, 5+ for OT).
        plus_minus: Include plus/minus data ('Y' or 'N').
        rank: Include rank data ('Y' or 'N').
        vs_division_nullable: Filter by opponent's division.
        vs_conference_nullable: Filter by opponent's conference.
        season_segment_nullable: Filter by season segment (e.g., 'Pre All-Star').
        outcome_nullable: Filter by game outcome ('W' or 'L').
        location_nullable: Filter by game location ('Home' or 'Road').
        league_id_nullable: League ID (e.g., '00' for NBA).
        game_segment_nullable: Filter by game segment (e.g., 'First Half').
        date_from_nullable: Start date (YYYY-MM-DD).
        date_to_nullable: End date (YYYY-MM-DD).
        return_dataframe: If True, returns a tuple: (JSON response, Dict of DataFrames).
                          Otherwise, returns JSON response string.

    Returns:
        str or Tuple[str, Dict[str, pd.DataFrame]]: JSON string or (JSON string, dict of DataFrames)
                                                    The dict of DataFrames will contain:
                                                    'overall': OverallTeamPlayerOnOffDetails
                                                    'off_court': PlayersOffCourtTeamPlayerOnOffDetails
                                                    'on_court': PlayersOnCourtTeamPlayerOnOffDetails
    """
    dataframes = {}
    logger.info(f"Executing fetch_team_player_on_off_details_logic for team '{team_identifier}', season {season}")

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

    if measure_type not in _VALID_MEASURE_TYPES:
        error_msg = Errors.INVALID_MEASURE_TYPE.format(value=measure_type, options=", ".join(list(_VALID_MEASURE_TYPES)[:5]))
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    if league_id_nullable and league_id_nullable not in _VALID_LEAGUE_IDS:
        error_msg = Errors.INVALID_LEAGUE_ID.format(value=league_id_nullable, options=", ".join(list(_VALID_LEAGUE_IDS)[:5]))
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    # Validate Y/N parameters
    for param_name, param_value in [("pace_adjust", pace_adjust), ("plus_minus", plus_minus), ("rank", rank)]:
        if param_value.upper() not in ["Y", "N"]:
            error_msg = f"Invalid {param_name} value: '{param_value}'. Must be 'Y' or 'N'."
            if return_dataframe: return format_response(error=error_msg), dataframes
            return format_response(error=error_msg)

    # Validate nullable choice parameters
    if vs_division_nullable not in _VALID_VS_DIVISIONS:
        error_msg = Errors.INVALID_DIVISION.format(value=vs_division_nullable, options=", ".join([opt for opt in _VALID_VS_DIVISIONS if opt][:3]))
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)
    if vs_conference_nullable not in _VALID_VS_CONFERENCES:
        error_msg = Errors.INVALID_CONFERENCE.format(value=vs_conference_nullable, options=", ".join([opt for opt in _VALID_VS_CONFERENCES if opt][:2]))
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)
    if season_segment_nullable not in _VALID_SEASON_SEGMENTS:
        error_msg = Errors.INVALID_SEASON_SEGMENT.format(value=season_segment_nullable, options=", ".join([opt for opt in _VALID_SEASON_SEGMENTS if opt][:2]))
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)
    if outcome_nullable not in _VALID_OUTCOMES:
        error_msg = Errors.INVALID_OUTCOME.format(value=outcome_nullable, options=", ".join([opt for opt in _VALID_OUTCOMES if opt][:2]))
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)
    if location_nullable not in _VALID_LOCATIONS:
        error_msg = Errors.INVALID_LOCATION.format(value=location_nullable, options=", ".join([opt for opt in _VALID_LOCATIONS if opt][:2]))
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)
    if game_segment_nullable not in _VALID_GAME_SEGMENTS:
        error_msg = Errors.INVALID_GAME_SEGMENT.format(value=game_segment_nullable, options=", ".join([opt for opt in _VALID_GAME_SEGMENTS if opt][:3]))
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)

    try:
        team_id_actual, team_actual_name = find_team_id_or_error(team_identifier)
    except Exception as ve: # Changed from ValueError to general Exception to catch TeamNotFoundError etc.
        logger.error(f"Error finding team '{team_identifier}': {ve}", exc_info=True)
        if return_dataframe: return format_response(error=str(ve)), dataframes
        return format_response(error=str(ve))

    try:
        api_params = {
            "team_id": team_id_actual,
            "season": season,
            "season_type_all_star": season_type, # API uses season_type_all_star
            "per_mode_detailed": per_mode,
            "measure_type_detailed_defense": measure_type, # API uses measure_type_detailed_defense
            "last_n_games": last_n_games,
            "month": month,
            "opponent_team_id": opponent_team_id,
            "pace_adjust": pace_adjust.upper(),
            "period": period,
            "plus_minus": plus_minus.upper(),
            "rank": rank.upper(),
            "vs_division_nullable": vs_division_nullable if vs_division_nullable else None, # Ensure empty strings become None
            "vs_conference_nullable": vs_conference_nullable if vs_conference_nullable else None,
            "season_segment_nullable": season_segment_nullable if season_segment_nullable else None,
            "outcome_nullable": outcome_nullable if outcome_nullable else None,
            "location_nullable": location_nullable if location_nullable else None,
            "league_id_nullable": league_id_nullable if league_id_nullable else None,
            "game_segment_nullable": game_segment_nullable if game_segment_nullable else None,
            "date_from_nullable": date_from_nullable if date_from_nullable else None,
            "date_to_nullable": date_to_nullable if date_to_nullable else None,
            "timeout": settings.DEFAULT_TIMEOUT_SECONDS
        }
        endpoint = teamplayeronoffdetails.TeamPlayerOnOffDetails(**api_params)

        overall_df = endpoint.overall_team_player_on_off_details.get_data_frame()
        off_court_df = endpoint.players_off_court_team_player_on_off_details.get_data_frame()
        on_court_df = endpoint.players_on_court_team_player_on_off_details.get_data_frame()

        if return_dataframe:
            dataframes = {
                "overall": overall_df,
                "off_court": off_court_df,
                "on_court": on_court_df
            }

        response_data = {
            "team_name": team_actual_name,
            "team_id": team_id_actual,
            "parameters": {k: v for k, v in api_params.items() if k != "timeout"}, # Exclude timeout for cleaner output
            "overall_team_player_on_off_details": _process_dataframe(overall_df, single_row=False),
            "players_off_court_team_player_on_off_details": _process_dataframe(off_court_df, single_row=False),
            "players_on_court_team_player_on_off_details": _process_dataframe(on_court_df, single_row=False)
        }
        
        logger.info(f"Successfully fetched TeamPlayerOnOffDetails for team_id {team_id_actual}")
        if return_dataframe:
            return format_response(response_data), dataframes
        return format_response(response_data)

    except json.JSONDecodeError as jde:
        logger.error(f"NBA API JSONDecodeError for TeamPlayerOnOffDetails, team '{team_actual_name}': {jde}", exc_info=True)
        error_msg = Errors.NBA_API_TIMEOUT_OR_DECODE_ERROR.format(endpoint_name="TeamPlayerOnOffDetails", details=str(jde))
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg)
    except Exception as api_error:
        logger.error(f"NBA API error for TeamPlayerOnOffDetails, team '{team_actual_name}': {api_error}", exc_info=True)
        # Attempt to use a specific error message if defined in Errors
        error_key_base = "TEAM_PLAYER_ON_OFF_DETAILS_API"
        specific_error_key = f"{error_key_base}_{type(api_error).__name__.upper()}"
        
        if hasattr(Errors, specific_error_key):
            error_msg = getattr(Errors, specific_error_key).format(identifier=team_actual_name, error=str(api_error))
        elif hasattr(Errors, error_key_base):
            error_msg = getattr(Errors, error_key_base).format(identifier=team_actual_name, error=str(api_error))
        else:
            error_msg = f"API error for TeamPlayerOnOffDetails team '{team_actual_name}': {str(api_error)}"
            
        if return_dataframe: return format_response(error=error_msg), dataframes
        return format_response(error=error_msg) 
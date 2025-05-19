"""
Handles fetching NBA league player on details data using the leagueplayerondetails endpoint.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
from typing import Optional, Dict, Union, Tuple
import pandas as pd
from functools import lru_cache

from nba_api.stats.endpoints import leagueplayerondetails
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed,
    MeasureTypeDetailedDefense, # Adjusted based on docs, likely MeasureTypeDetailed or similar
    LeagueID,
    # TeamID, # Not explicitly in nba_api.stats.library.parameters but a common type; team_id is passed as int
    GameSegmentNullable,
    LocationNullable,
    MonthNullable, # Not an enum, but a number
    OutcomeNullable,
    SeasonSegmentNullable,
    ConferenceNullable,
    DivisionNullable
)
from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response,
    # find_player_id_or_error, # Not directly needed as this is league/team focused
)
from ..utils.validation import _validate_season_format, validate_date_format
from ..utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Cache Directory Setup ---
PLAYER_ON_DETAILS_CSV_DIR = get_cache_dir("player_on_details")

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

def _get_csv_path_for_player_on_details(
    season: str,
    season_type: str,
    measure_type: str,
    per_mode: str,
    team_id: int
) -> str:
    """
    Generates a file path for saving player on details DataFrame as CSV.

    Args:
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        measure_type: The measure type (e.g., 'Base', 'Advanced')
        per_mode: The per mode (e.g., 'Totals', 'PerGame')
        team_id: The team ID

    Returns:
        Path to the CSV file
    """
    # Clean season type, measure type, and per mode for filename
    clean_season_type = season_type.replace(" ", "_").lower()
    clean_measure_type = measure_type.replace(" ", "_").lower()
    clean_per_mode = per_mode.replace(" ", "_").lower()

    filename = f"player_on_details_{season}_{clean_season_type}_{clean_measure_type}_{clean_per_mode}_team_{team_id}.csv"
    return get_cache_file_path(filename, "player_on_details")

# Module-level constants for validation sets
# These need to be carefully defined based on nba_api.stats.library.parameters
# and the leagueplayerondetails.md documentation.
_VALID_LPOD_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_VALID_LPOD_PER_MODES = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
# leagueplayerondetails.md shows MeasureType pattern: ^(Base)\|(Advanced)\|(Misc)\|(Four Factors)\|(Scoring)\|(Opponent)\|(Usage)\|(Defense)$
# This aligns well with MeasureTypeDetailed or MeasureTypeDetailedDefense
_VALID_LPOD_MEASURE_TYPES = {getattr(MeasureTypeDetailedDefense, attr) for attr in dir(MeasureTypeDetailedDefense) if not attr.startswith('_') and isinstance(getattr(MeasureTypeDetailedDefense, attr), str)}
_VALID_LPOD_PACE_ADJUST = {"Y", "N"}
_VALID_LPOD_PLUS_MINUS = {"Y", "N"}
_VALID_LPOD_RANK = {"Y", "N"}
_VALID_LPOD_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}
_VALID_LPOD_GAME_SEGMENTS = {val for val in GameSegmentNullable.__dict__.values() if isinstance(val, str) and val} | {None}
_VALID_LPOD_LOCATIONS = {val for val in LocationNullable.__dict__.values() if isinstance(val, str) and val} | {None}
_VALID_LPOD_OUTCOMES = {val for val in OutcomeNullable.__dict__.values() if isinstance(val, str) and val} | {None}
_VALID_LPOD_SEASON_SEGMENTS = {val for val in SeasonSegmentNullable.__dict__.values() if isinstance(val, str) and val} | {None}
_VALID_LPOD_VS_CONFERENCES = {val for val in ConferenceNullable.__dict__.values() if isinstance(val, str) and val} | {None}
_VALID_LPOD_VS_DIVISIONS = {val for val in DivisionNullable.__dict__.values() if isinstance(val, str) and val} | {None}


def fetch_league_player_on_details_logic(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    measure_type: str = MeasureTypeDetailedDefense.base,
    per_mode: str = PerModeDetailed.totals,
    team_id: int = 0, # TeamID is required by the endpoint, 0 often means all/league
    last_n_games: int = 0,
    month: int = 0, # 0 for all months
    opponent_team_id: int = 0, # 0 for all opponents
    pace_adjust: str = "N",
    plus_minus: str = "N",
    rank: str = "N",
    period: int = 0, # 0 for all periods
    vs_division_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    league_id_nullable: Optional[str] = LeagueID.nba, # Default to NBA
    game_segment_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches NBA league player on details data using the leagueplayerondetails endpoint.
    Provides DataFrame output capabilities.

    Args:
        season: Season in YYYY-YY format (e.g., "2023-24").
        season_type: Type of season (Regular Season, Playoffs, etc.).
        measure_type: Type of statistical measure (Base, Advanced, etc.).
        per_mode: Statistical mode (Totals, PerGame, etc.).
        team_id: Team ID to filter by.
        last_n_games: Filter by last N games.
        month: Filter by month (0 for all months).
        opponent_team_id: Filter by opponent team ID (0 for all opponents).
        pace_adjust: Whether to pace-adjust stats ("Y" or "N").
        plus_minus: Whether to include plus-minus stats ("Y" or "N").
        rank: Whether to include rank stats ("Y" or "N").
        period: Filter by period (0 for all periods).
        vs_division_nullable: Filter by opponent division.
        vs_conference_nullable: Filter by opponent conference.
        season_segment_nullable: Filter by season segment.
        outcome_nullable: Filter by outcome (W, L).
        location_nullable: Filter by location (Home, Road).
        league_id_nullable: League ID.
        game_segment_nullable: Filter by game segment.
        date_to_nullable: End date (YYYY-MM-DD).
        date_from_nullable: Start date (YYYY-MM-DD).
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string with league player on details data or an error message.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_league_player_on_details_logic for Season: {season}, TeamID: {team_id}, Measure: {measure_type}, return_dataframe: {return_dataframe}")

    # Store DataFrames if requested
    dataframes = {}

    if not _validate_season_format(season):
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

    # Parameter Validations
    if season_type not in _VALID_LPOD_SEASON_TYPES:
        error_response = format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_LPOD_SEASON_TYPES)[:5])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if per_mode not in _VALID_LPOD_PER_MODES:
        error_response = format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_LPOD_PER_MODES)[:5])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if measure_type not in _VALID_LPOD_MEASURE_TYPES:
        error_response = format_response(error=Errors.INVALID_MEASURE_TYPE.format(value=measure_type, options=", ".join(list(_VALID_LPOD_MEASURE_TYPES)[:5])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if pace_adjust.upper() not in _VALID_LPOD_PACE_ADJUST:
        error_response = format_response(error=Errors.INVALID_PACE_ADJUST.format(value=pace_adjust))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if plus_minus.upper() not in _VALID_LPOD_PLUS_MINUS:
        error_response = format_response(error=Errors.INVALID_PLUS_MINUS.format(value=plus_minus))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if rank.upper() not in _VALID_LPOD_RANK:
        error_response = format_response(error=Errors.INVALID_RANK.format(value=rank))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if league_id_nullable and league_id_nullable not in _VALID_LPOD_LEAGUE_IDS:
        error_response = format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id_nullable, options=", ".join(list(_VALID_LPOD_LEAGUE_IDS)[:3])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if team_id == 0: # As per docs, TeamID is required. If 0 is passed, it might imply league-wide, but API might reject.
        logger.warning("TeamID is 0, which might be interpreted as league-wide or could be an error by the API if a specific team is expected.")
        # Consider if an error should be returned if team_id is 0, based on API behavior.
        # For now, proceeding as the example URL uses TeamID=1610612739

    # Nullable enum validations
    if game_segment_nullable and game_segment_nullable not in _VALID_LPOD_GAME_SEGMENTS:
        error_response = format_response(error=Errors.INVALID_GAME_SEGMENT.format(value=game_segment_nullable, options=", ".join([s for s in _VALID_LPOD_GAME_SEGMENTS if s][:3])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if location_nullable and location_nullable not in _VALID_LPOD_LOCATIONS:
        error_response = format_response(error=Errors.INVALID_LOCATION.format(value=location_nullable, options=", ".join([s for s in _VALID_LPOD_LOCATIONS if s][:2])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if outcome_nullable and outcome_nullable not in _VALID_LPOD_OUTCOMES:
        error_response = format_response(error=Errors.INVALID_OUTCOME.format(value=outcome_nullable, options=", ".join([s for s in _VALID_LPOD_OUTCOMES if s][:2])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if season_segment_nullable and season_segment_nullable not in _VALID_LPOD_SEASON_SEGMENTS:
        error_response = format_response(error=Errors.INVALID_SEASON_SEGMENT.format(value=season_segment_nullable, options=", ".join([s for s in _VALID_LPOD_SEASON_SEGMENTS if s][:2])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if vs_conference_nullable and vs_conference_nullable not in _VALID_LPOD_VS_CONFERENCES:
        error_response = format_response(error=Errors.INVALID_CONFERENCE.format(value=vs_conference_nullable, options=", ".join([s for s in _VALID_LPOD_VS_CONFERENCES if s][:2])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if vs_division_nullable and vs_division_nullable not in _VALID_LPOD_VS_DIVISIONS:
        error_response = format_response(error=Errors.INVALID_DIVISION.format(value=vs_division_nullable, options=", ".join([s for s in _VALID_LPOD_VS_DIVISIONS if s][:3])))
        if return_dataframe:
            return error_response, dataframes
        return error_response


    try:
        logger.debug(f"Fetching leagueplayerondetails for TeamID: {team_id}, Season: {season}, Measure: {measure_type}")

        lpod_endpoint = leagueplayerondetails.LeaguePlayerOnDetails(
            season=season,
            season_type_all_star=season_type, # Mapped from season_type
            measure_type_detailed_defense=measure_type, # Mapped from measure_type
            per_mode_detailed=per_mode, # Mapped from per_mode
            team_id=team_id,
            last_n_games=last_n_games,
            month=month,
            opponent_team_id=opponent_team_id,
            pace_adjust=pace_adjust.upper(),
            plus_minus=plus_minus.upper(),
            rank=rank.upper(),
            period=period,
            vs_division_nullable=vs_division_nullable,
            vs_conference_nullable=vs_conference_nullable,
            season_segment_nullable=season_segment_nullable,
            outcome_nullable=outcome_nullable,
            location_nullable=location_nullable,
            league_id_nullable=league_id_nullable,
            game_segment_nullable=game_segment_nullable,
            date_to_nullable=date_to_nullable,
            date_from_nullable=date_from_nullable,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"leagueplayerondetails API call successful for TeamID: {team_id}, Season: {season}")

        # Main dataset from docs: PlayersOnCourtLeaguePlayerDetails
        details_df = lpod_endpoint.players_on_court_league_player_details.get_data_frame()

        # Store DataFrame if requested
        if return_dataframe:
            dataframes["league_player_on_details"] = details_df

            # Save to CSV if not empty
            if not details_df.empty:
                csv_path = _get_csv_path_for_player_on_details(
                    season=season,
                    season_type=season_type,
                    measure_type=measure_type,
                    per_mode=per_mode,
                    team_id=team_id
                )
                _save_dataframe_to_csv(details_df, csv_path)

        details_list = _process_dataframe(details_df, single_row=False)

        if details_list is None: # Check for processing errors
            logger.error(f"DataFrame processing failed for league player on details (TeamID: {team_id}, Season: {season}).")
            error_msg = Errors.LEAGUE_PLAYER_ON_DETAILS_PROCESSING.format(team_id=team_id, season=season)
            error_response = format_response(error=error_msg)
            if return_dataframe:
                return error_response, dataframes
            return error_response

        if details_df.empty: # Genuinely no data
            logger.warning(f"No league player on details data found for TeamID: {team_id}, Season: {season} with specified filters.")
            # Return empty list for the data key as per pattern
            data_payload = []
        else:
            data_payload = details_list

        result = {
            "parameters": {
                "season": season, "season_type": season_type, "measure_type": measure_type, "per_mode": per_mode,
                "team_id": team_id, "last_n_games": last_n_games, "month": month, "opponent_team_id": opponent_team_id,
                "pace_adjust": pace_adjust, "plus_minus": plus_minus, "rank": rank, "period": period,
                "vs_division_nullable": vs_division_nullable, "vs_conference_nullable": vs_conference_nullable,
                "season_segment_nullable": season_segment_nullable, "outcome_nullable": outcome_nullable,
                "location_nullable": location_nullable, "league_id_nullable": league_id_nullable,
                "game_segment_nullable": game_segment_nullable, "date_to_nullable": date_to_nullable,
                "date_from_nullable": date_from_nullable
            },
            "league_player_on_details": data_payload
        }

        # Add DataFrame info to the response if requested
        if return_dataframe:
            csv_path = _get_csv_path_for_player_on_details(
                season=season,
                season_type=season_type,
                measure_type=measure_type,
                per_mode=per_mode,
                team_id=team_id
            )
            relative_path = get_relative_cache_path(
                os.path.basename(csv_path),
                "player_on_details"
            )

            result["dataframe_info"] = {
                "message": "League player on details data has been converted to DataFrame and saved as CSV file",
                "dataframes": {
                    "league_player_on_details": {
                        "shape": list(details_df.shape) if not details_df.empty else [],
                        "columns": details_df.columns.tolist() if not details_df.empty else [],
                        "csv_path": relative_path
                    }
                }
            }

        logger.info(f"Successfully fetched league player on details for TeamID: {team_id}, Season: {season}")

        if return_dataframe:
            return format_response(data=result), dataframes
        return format_response(data=result)

    except ValueError as e:
        logger.warning(f"ValueError in fetch_league_player_on_details_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, dataframes
        return error_response
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_league_player_on_details_logic for TeamID {team_id}, Season {season}: {e}", exc_info=True)
        error_msg = Errors.LEAGUE_PLAYER_ON_DETAILS_UNEXPECTED.format(team_id=team_id, season=season, error=str(e))
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, dataframes
        return error_response
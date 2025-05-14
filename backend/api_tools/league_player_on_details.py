import logging
from typing import Optional
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
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response,
    # find_player_id_or_error, # Not directly needed as this is league/team focused
)
from backend.utils.validation import _validate_season_format, validate_date_format

logger = logging.getLogger(__name__)

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


@lru_cache(maxsize=settings.DEFAULT_LRU_CACHE_SIZE)
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
    date_from_nullable: Optional[str] = None
) -> str:
    logger.info(f"Executing fetch_league_player_on_details_logic for Season: {season}, TeamID: {team_id}, Measure: {measure_type}")

    if not _validate_season_format(season): return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if date_from_nullable and not validate_date_format(date_from_nullable): return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from_nullable))
    if date_to_nullable and not validate_date_format(date_to_nullable): return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to_nullable))
    
    # Parameter Validations
    if season_type not in _VALID_LPOD_SEASON_TYPES: return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_LPOD_SEASON_TYPES)[:5])))
    if per_mode not in _VALID_LPOD_PER_MODES: return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_LPOD_PER_MODES)[:5])))
    if measure_type not in _VALID_LPOD_MEASURE_TYPES: return format_response(error=Errors.INVALID_MEASURE_TYPE.format(value=measure_type, options=", ".join(list(_VALID_LPOD_MEASURE_TYPES)[:5])))
    if pace_adjust.upper() not in _VALID_LPOD_PACE_ADJUST: return format_response(error=Errors.INVALID_PACE_ADJUST.format(value=pace_adjust))
    if plus_minus.upper() not in _VALID_LPOD_PLUS_MINUS: return format_response(error=Errors.INVALID_PLUS_MINUS.format(value=plus_minus))
    if rank.upper() not in _VALID_LPOD_RANK: return format_response(error=Errors.INVALID_RANK.format(value=rank))
    if league_id_nullable and league_id_nullable not in _VALID_LPOD_LEAGUE_IDS: return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id_nullable, options=", ".join(list(_VALID_LPOD_LEAGUE_IDS)[:3])))
    if team_id == 0: # As per docs, TeamID is required. If 0 is passed, it might imply league-wide, but API might reject.
        logger.warning("TeamID is 0, which might be interpreted as league-wide or could be an error by the API if a specific team is expected.")
        # Consider if an error should be returned if team_id is 0, based on API behavior.
        # For now, proceeding as the example URL uses TeamID=1610612739

    # Nullable enum validations
    if game_segment_nullable and game_segment_nullable not in _VALID_LPOD_GAME_SEGMENTS: return format_response(error=Errors.INVALID_GAME_SEGMENT.format(value=game_segment_nullable, options=", ".join([s for s in _VALID_LPOD_GAME_SEGMENTS if s][:3])))
    if location_nullable and location_nullable not in _VALID_LPOD_LOCATIONS: return format_response(error=Errors.INVALID_LOCATION.format(value=location_nullable, options=", ".join([s for s in _VALID_LPOD_LOCATIONS if s][:2])))
    if outcome_nullable and outcome_nullable not in _VALID_LPOD_OUTCOMES: return format_response(error=Errors.INVALID_OUTCOME.format(value=outcome_nullable, options=", ".join([s for s in _VALID_LPOD_OUTCOMES if s][:2])))
    if season_segment_nullable and season_segment_nullable not in _VALID_LPOD_SEASON_SEGMENTS: return format_response(error=Errors.INVALID_SEASON_SEGMENT.format(value=season_segment_nullable, options=", ".join([s for s in _VALID_LPOD_SEASON_SEGMENTS if s][:2])))
    if vs_conference_nullable and vs_conference_nullable not in _VALID_LPOD_VS_CONFERENCES: return format_response(error=Errors.INVALID_CONFERENCE.format(value=vs_conference_nullable, options=", ".join([s for s in _VALID_LPOD_VS_CONFERENCES if s][:2])))
    if vs_division_nullable and vs_division_nullable not in _VALID_LPOD_VS_DIVISIONS: return format_response(error=Errors.INVALID_DIVISION.format(value=vs_division_nullable, options=", ".join([s for s in _VALID_LPOD_VS_DIVISIONS if s][:3])))


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

        details_list = _process_dataframe(details_df, single_row=False)

        if details_list is None: # Check for processing errors
            logger.error(f"DataFrame processing failed for league player on details (TeamID: {team_id}, Season: {season}).")
            error_msg = Errors.LEAGUE_PLAYER_ON_DETAILS_PROCESSING.format(team_id=team_id, season=season)
            return format_response(error=error_msg)

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
        logger.info(f"Successfully fetched league player on details for TeamID: {team_id}, Season: {season}")
        return format_response(data=result)

    except ValueError as e: 
        logger.warning(f"ValueError in fetch_league_player_on_details_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_league_player_on_details_logic for TeamID {team_id}, Season {season}: {e}", exc_info=True)
        error_msg = Errors.LEAGUE_PLAYER_ON_DETAILS_UNEXPECTED.format(team_id=team_id, season=season, error=str(e)) 
        return format_response(error=error_msg)
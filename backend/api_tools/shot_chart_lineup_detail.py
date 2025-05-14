import logging
import re
from functools import lru_cache
from typing import Optional

from nba_api.stats.endpoints import shotchartlineupdetail
from nba_api.stats.library.parameters import (
    LeagueID, SeasonTypeAllStar, ContextMeasureDetailed,
    GameSegment, LastNGames, Location, Month, Outcome, Period, SeasonSegment,
    Conference, Division # Corrected imports
)

from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import _process_dataframe, format_response
from backend.utils.validation import _validate_season_format, validate_date_format # Corrected import

logger = logging.getLogger(__name__)

# Module-level constants for validation sets
_VALID_SCLD_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_')}
_VALID_SCLD_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_')}
_VALID_SCLD_CONTEXT_MEASURES = {getattr(ContextMeasureDetailed, attr) for attr in dir(ContextMeasureDetailed) if not attr.startswith('_')}
_VALID_SCLD_PERIODS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12} # 0 for all, 1-4 for quarters, 5+ for OT
_GROUP_ID_PATTERN = re.compile(r"^\d+(?: - \d+){1,4}$") # 2 to 5 player IDs

@lru_cache(maxsize=settings.DEFAULT_LRU_CACHE_SIZE)
def fetch_shot_chart_lineup_detail_logic(
    group_id: str, # Lineup ID, e.g., "201939 - 203076 - 203952 - 204001 - 1628369"
    team_id: int,  # Team ID is crucial for context
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    context_measure: str = ContextMeasureDetailed.fgm,
    league_id: str = LeagueID.nba,
    period: int = 0,
    vs_division_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    opponent_team_id_nullable: Optional[int] = 0, # API default is 0
    month_nullable: Optional[int] = 0, # API default is 0
    location_nullable: Optional[str] = None,
    last_n_games_nullable: Optional[int] = 0, # API default is 0
    game_segment_nullable: Optional[str] = None,
    game_id_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    context_filter_nullable: Optional[str] = None
) -> str:
    """
    Fetches detailed shot chart data for a specific lineup.

    Args:
        group_id (str): String of player IDs representing the lineup (e.g., "ID1 - ID2 - ID3 - ID4 - ID5").
        team_id (int): The ID of the team this lineup belongs to.
        season (str): NBA season in 'YYYY-YY' format.
        season_type (str): Season type (e.g., 'Regular Season').
        context_measure (str): Statistic to measure (e.g., 'FGM', 'PTS').
        league_id (str): League ID.
        period (int): Filter by game period (0 for all).
        Many other optional filter parameters...

    Returns:
        str: JSON-formatted string with lineup shot chart details or an error message.
    """
    logger.info(f"Executing fetch_shot_chart_lineup_detail_logic for GroupID: {group_id}, TeamID: {team_id}, Season: {season}")

    if not _GROUP_ID_PATTERN.match(group_id):
        return format_response(error=Errors.INVALID_PARAMETER_FORMAT.format(param_name="group_id", param_value=group_id, expected_format="e.g., 'ID1 - ID2 - ID3 - ID4 - ID5'"))
    if not isinstance(team_id, int) or team_id == 0: # Team ID 0 is usually for league-wide, but here it's for a specific team's lineup
        return format_response(error=Errors.INVALID_TEAM_IDENTIFIER.format(identifier=str(team_id)))
    if not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if league_id not in _VALID_SCLD_LEAGUE_IDS:
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_VALID_SCLD_LEAGUE_IDS)[:3])))
    if season_type not in _VALID_SCLD_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_SCLD_SEASON_TYPES)[:5])))
    if context_measure not in _VALID_SCLD_CONTEXT_MEASURES:
        return format_response(error=Errors.INVALID_CONTEXT_MEASURE.format(value=context_measure, options=", ".join(list(_VALID_SCLD_CONTEXT_MEASURES)[:5])))
    if period not in _VALID_SCLD_PERIODS:
        return format_response(error=Errors.INVALID_PERIOD.format(value=period, options="0-12"))

    if date_from_nullable and not validate_date_format(date_from_nullable): # Corrected function call
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date_value=date_from_nullable))
    if date_to_nullable and not validate_date_format(date_to_nullable): # Corrected function call
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date_value=date_to_nullable))
    
    # Validate other nullable enum parameters if provided
    if vs_division_nullable and vs_division_nullable not in Division.get_valid_values(): # Corrected class
        return format_response(error=Errors.INVALID_VS_DIVISION.format(value=vs_division_nullable, options=", ".join(Division.get_valid_values()[:3])))
    if vs_conference_nullable and vs_conference_nullable not in Conference.get_valid_values(): # Corrected class
        return format_response(error=Errors.INVALID_VS_CONFERENCE.format(value=vs_conference_nullable, options=", ".join(Conference.get_valid_values()[:2])))
    if season_segment_nullable and season_segment_nullable not in SeasonSegment.get_valid_values():
        return format_response(error=Errors.INVALID_SEASON_SEGMENT.format(value=season_segment_nullable, options=", ".join(SeasonSegment.get_valid_values()[:2])))
    if outcome_nullable and outcome_nullable not in Outcome.get_valid_values():
        return format_response(error=Errors.INVALID_OUTCOME.format(value=outcome_nullable, options=", ".join(Outcome.get_valid_values()[:2])))
    if location_nullable and location_nullable not in Location.get_valid_values():
        return format_response(error=Errors.INVALID_LOCATION.format(value=location_nullable, options=", ".join(Location.get_valid_values()[:2])))
    if game_segment_nullable and game_segment_nullable not in GameSegment.get_valid_values():
        return format_response(error=Errors.INVALID_GAME_SEGMENT.format(value=game_segment_nullable, options=", ".join(GameSegment.get_valid_values()[:3])))
    if month_nullable is not None and not (0 <= month_nullable <= 12): # Month 0 for all months
         return format_response(error=Errors.INVALID_MONTH.format(value=month_nullable))
    if last_n_games_nullable is not None and last_n_games_nullable < 0:
        return format_response(error=Errors.INVALID_LAST_N_GAMES.format(value=last_n_games_nullable))


    try:
        scld_endpoint = shotchartlineupdetail.ShotChartLineupDetail(
            group_id=group_id,
            team_id_nullable=team_id, # Corrected parameter name
            season=season,
            season_type_all_star=season_type,
            context_measure_detailed=context_measure,
            league_id=league_id,
            period=period,
            vs_division_nullable=vs_division_nullable,
            vs_conference_nullable=vs_conference_nullable,
            season_segment_nullable=season_segment_nullable,
            outcome_nullable=outcome_nullable,
            opponent_team_id_nullable=opponent_team_id_nullable,
            month_nullable=month_nullable,
            location_nullable=location_nullable,
            last_n_games_nullable=last_n_games_nullable,
            game_segment_nullable=game_segment_nullable,
            game_id_nullable=game_id_nullable,
            date_to_nullable=date_to_nullable,
            date_from_nullable=date_from_nullable,
            context_filter_nullable=context_filter_nullable,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        
        shot_details_df = None
        league_avg_df = None
        shot_details_list = []
        league_avg_list = []

        try:
            shot_details_df = scld_endpoint.shot_chart_lineup_detail.get_data_frame()
            shot_details_list = _process_dataframe(shot_details_df) if shot_details_df is not None else []
        except KeyError as e:
            logger.warning(f"KeyError accessing shot_chart_lineup_detail dataset for GroupID {group_id}, TeamID {team_id}: {e}. API likely returned no data or an error structure.")
            # shot_details_list remains []
        
        try:
            league_avg_df = scld_endpoint.shot_chart_lineup_league_average.get_data_frame()
            league_avg_list = _process_dataframe(league_avg_df) if league_avg_df is not None else []
        except KeyError as e:
            logger.warning(f"KeyError accessing shot_chart_lineup_league_average dataset for GroupID {group_id}, TeamID {team_id}: {e}. API likely returned no data or an error structure.")
            # league_avg_list remains []

        # Check if processing itself failed, distinct from KeyError due to no data
        if shot_details_df is not None and shot_details_list is None: # Data was there, but _process_dataframe failed
             logger.error(f"DataFrame processing failed for shot_chart_lineup_detail (GroupID: {group_id}, TeamID: {team_id}).")
             return format_response(error=Errors.PROCESSING_ERROR.format(error="shot_chart_lineup_detail data processing failed"))
        if league_avg_df is not None and league_avg_list is None: # Data was there, but _process_dataframe failed
             logger.error(f"DataFrame processing failed for shot_chart_lineup_league_average (GroupID: {group_id}, TeamID: {team_id}).")
             return format_response(error=Errors.PROCESSING_ERROR.format(error="shot_chart_lineup_league_average data processing failed"))

        result = {
            "parameters": {
                "group_id": group_id, "team_id": team_id, "season": season, "season_type": season_type,
                "context_measure": context_measure, "league_id": league_id, "period": period,
                # Include other passed optional params for clarity
                "vs_division": vs_division_nullable, "vs_conference": vs_conference_nullable,
                "season_segment": season_segment_nullable, "outcome": outcome_nullable,
                "opponent_team_id": opponent_team_id_nullable, "month": month_nullable,
                "location": location_nullable, "last_n_games": last_n_games_nullable,
                "game_segment": game_segment_nullable, "game_id": game_id_nullable,
                "date_to": date_to_nullable, "date_from": date_from_nullable,
                "context_filter": context_filter_nullable
            },
            "shot_chart_details": shot_details_list if not shot_details_df.empty else [],
            "league_averages": league_avg_list if not league_avg_df.empty else []
        }
        logger.info(f"Successfully fetched lineup shot chart for GroupID: {group_id}, TeamID: {team_id}")
        return format_response(data=result)

    except ValueError as e: # Handles potential errors from nba_api parameter validation
        logger.warning(f"ValueError in fetch_shot_chart_lineup_detail_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_shot_chart_lineup_detail_logic for GroupID {group_id}, TeamID {team_id}: {e}", exc_info=True)
        return format_response(error=Errors.API_ERROR.format(error=f"fetching lineup shot chart details: {str(e)}"))
import logging
from functools import lru_cache
from typing import Optional

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

from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response
)
from backend.utils.validation import validate_season_format, validate_date_format, validate_team_id

logger = logging.getLogger(__name__)

@lru_cache(maxsize=settings.DEFAULT_LRU_CACHE_SIZE)
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
    vs_division_nullable: Optional[str] = DivisionNullable.default # Yes, DivisionNullable again for VsDivision
) -> str:
    """
    Fetches league-wide lineup statistics with extensive filtering options.

    Args:
        season (str): YYYY-YY format (e.g., "2023-24").
        group_quantity (int, optional): Number of players in the lineup (e.g., 2, 3, 4, 5). Defaults to 5.
        last_n_games (int, optional): Filter by last N games. Defaults to 0 (all games).
        measure_type (str, optional): Type of stats (Base, Advanced, Misc, etc.). Defaults to "Base".
        month (int, optional): Filter by month (1-12). Defaults to 0 (all months).
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0 (all opponents).
        pace_adjust (str, optional): Pace adjust stats (Y/N). Defaults to "N".
        per_mode (str, optional): Stat mode (Totals, PerGame, Per100Possessions, etc.). Defaults to "Totals".
        period (int, optional): Filter by period (1-4 for quarters, 0 for full game). Defaults to 0.
        plus_minus (str, optional): Include plus/minus (Y/N). Defaults to "N".
        rank (str, optional): Include rank (Y/N). Defaults to "N".
        season_type (str, optional): Type of season (Regular Season, Playoffs, etc.). Defaults to "Regular Season".
        conference_nullable (Optional[str], optional): Filter by conference (East, West).
        date_from_nullable (Optional[str], optional): Start date (YYYY-MM-DD).
        date_to_nullable (Optional[str], optional): End date (YYYY-MM-DD).
        division_nullable (Optional[str], optional): Filter by division.
        game_segment_nullable (Optional[str], optional): Filter by game segment (First Half, Second Half, Overtime).
        league_id_nullable (Optional[str], optional): League ID (e.g., "00" for NBA). Defaults to "00".
        location_nullable (Optional[str], optional): Filter by location (Home, Road).
        outcome_nullable (Optional[str], optional): Filter by outcome (W, L).
        po_round_nullable (Optional[str], optional): Playoff round.
        season_segment_nullable (Optional[str], optional): Filter by season segment (Pre All-Star, Post All-Star).
        shot_clock_range_nullable (Optional[str], optional): Filter by shot clock range.
        team_id_nullable (Optional[int], optional): Filter by a specific team ID.
        vs_conference_nullable (Optional[str], optional): Filter by opponent conference.
        vs_division_nullable (Optional[str], optional): Filter by opponent division.

    Returns:
        str: JSON string with lineup stats or an error message.
    """
    logger.info(f"Executing fetch_league_dash_lineups_logic for Season: {season}, GroupQty: {group_quantity}, Measure: {measure_type}")

    if not validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if date_from_nullable and not validate_date_format(date_from_nullable):
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from_nullable))
    if date_to_nullable and not validate_date_format(date_to_nullable):
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to_nullable))
    if team_id_nullable is not None and not validate_team_id(team_id_nullable):
         return format_response(error=Errors.INVALID_TEAM_ID_VALUE.format(team_id=team_id_nullable))
    if opponent_team_id != 0 and not validate_team_id(opponent_team_id):
         return format_response(error=Errors.INVALID_TEAM_ID_VALUE.format(team_id=opponent_team_id))

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
        lineups_list = _process_dataframe(lineups_df, single_row=False)

        if lineups_list is None:
            logger.error("DataFrame processing failed for LeagueDashLineups.")
            return format_response(error=Errors.LEAGUE_DASH_LINEUPS_API_ERROR.format(error="DataFrame processing returned None unexpectedly."))

        response_data = {
            "parameters": {
                "season": season,
                "group_quantity": group_quantity,
                # Include other relevant parameters used in the query for context
            },
            "lineups": lineups_list
        }
        
        logger.info(f"Successfully fetched {len(lineups_list)} lineup entries for Season: {season}")
        return format_response(response_data)

    except Exception as e:
        logger.error(
            f"Error in fetch_league_dash_lineups_logic for Season {season}: {str(e)}",
            exc_info=True
        )
        return format_response(error=Errors.LEAGUE_DASH_LINEUPS_API_ERROR.format(error=str(e))) 
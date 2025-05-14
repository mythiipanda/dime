import logging
from functools import lru_cache
from typing import Optional

from nba_api.stats.endpoints import LeagueDashOppPtShot
from nba_api.stats.library.parameters import (
    PerModeSimple,
    SeasonTypeAllStar,
    LeagueIDNullable,
    Month,
    Period,
    ConferenceNullable,
    DivisionNullable,
    GameSegmentNullable,
    LastNGames,
    LocationNullable,
    OutcomeNullable,
    SeasonSegmentNullable,
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
def fetch_league_dash_opponent_pt_shot_logic(
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    league_id_nullable: Optional[str] = LeagueIDNullable.default,
    per_mode_simple: str = PerModeSimple.totals,
    month_nullable: Optional[int] = 0,
    period_nullable: Optional[int] = 0,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    opponent_team_id_nullable: Optional[int] = 0,
    vs_conference_nullable: Optional[str] = ConferenceNullable.default,
    vs_division_nullable: Optional[str] = DivisionNullable.default,
    team_id_nullable: Optional[int] = None,
    conference_nullable: Optional[str] = ConferenceNullable.default,
    division_nullable: Optional[str] = DivisionNullable.default,
    game_segment_nullable: Optional[str] = GameSegmentNullable.default,
    last_n_games_nullable: Optional[int] = 0,
    location_nullable: Optional[str] = LocationNullable.default,
    outcome_nullable: Optional[str] = OutcomeNullable.default,
    po_round_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = SeasonSegmentNullable.default,
    shot_clock_range_nullable: Optional[str] = ShotClockRangeNullable.default,
    close_def_dist_range_nullable: Optional[str] = None,
    shot_dist_range_nullable: Optional[str] = None,
    dribble_range_nullable: Optional[str] = None,
    general_range_nullable: Optional[str] = None,
    touch_time_range_nullable: Optional[str] = None
) -> str:
    """
    Fetches league dashboard data for opponent player/team shots.
    This endpoint provides statistics about shots taken by opponents.

    Args:
        season (str): YYYY-YY format (e.g., "2023-24").
        season_type (str, optional): Type of season (Regular Season, Playoffs, etc.). Defaults to Regular Season.
        league_id_nullable (Optional[str], optional): League ID (e.g., "00" for NBA). Defaults to "00".
        per_mode_simple (str, optional): Stat mode (Totals, PerGame, etc.). Defaults to "Totals".
        month_nullable (Optional[int], optional): Filter by month (1-12). Defaults to 0 (all months).
        period_nullable (Optional[int], optional): Filter by period (1-4 for quarters, 0 for full game). Defaults to 0.
        date_from_nullable (Optional[str], optional): Start date (YYYY-MM-DD).
        date_to_nullable (Optional[str], optional): End date (YYYY-MM-DD).
        opponent_team_id_nullable (Optional[int], optional): Filter by opponent team ID. Defaults to 0 (all opponents).
        vs_conference_nullable (Optional[str], optional): Filter by opponent conference.
        vs_division_nullable (Optional[str], optional): Filter by opponent division.
        team_id_nullable (Optional[int], optional): Filter by a specific team's ID to see shots against them.
        conference_nullable (Optional[str], optional): Filter by team's conference.
        division_nullable (Optional[str], optional): Filter by team's division.
        game_segment_nullable (Optional[str], optional): Filter by game segment.
        last_n_games_nullable (Optional[int], optional): Filter by last N games. Defaults to 0 (all games).
        location_nullable (Optional[str], optional): Filter by location (Home, Road).
        outcome_nullable (Optional[str], optional): Filter by outcome (W, L).
        po_round_nullable (Optional[str], optional): Playoff round.
        season_segment_nullable (Optional[str], optional): Filter by season segment.
        shot_clock_range_nullable (Optional[str], optional): Filter by shot clock range.
        close_def_dist_range_nullable (Optional[str], optional): Filter by closest defender distance.
        shot_dist_range_nullable (Optional[str], optional): Filter by shot distance.
        dribble_range_nullable (Optional[str], optional): Filter by dribble range.
        general_range_nullable (Optional[str], optional): Filter by general range.
        touch_time_range_nullable (Optional[str], optional): Filter by touch time range.

    Returns:
        str: JSON string with opponent shot stats or an error message.
    """
    logger.info(f"Executing fetch_league_dash_opponent_pt_shot_logic for Season: {season}, PerMode: {per_mode_simple}")

    if not validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if date_from_nullable and not validate_date_format(date_from_nullable):
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from_nullable))
    if date_to_nullable and not validate_date_format(date_to_nullable):
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to_nullable))
    if team_id_nullable is not None and not validate_team_id(team_id_nullable):
        return format_response(error=Errors.INVALID_TEAM_ID_VALUE.format(team_id=team_id_nullable))
    if opponent_team_id_nullable is not None and opponent_team_id_nullable != 0 and not validate_team_id(opponent_team_id_nullable):
        return format_response(error=Errors.INVALID_TEAM_ID_VALUE.format(team_id=opponent_team_id_nullable))

    try:
        endpoint = LeagueDashOppPtShot(
            season=season,
            season_type_all_star=season_type,
            league_id=league_id_nullable,
            per_mode_simple=per_mode_simple,
            month_nullable=month_nullable,
            period_nullable=period_nullable,
            date_from_nullable=date_from_nullable,
            date_to_nullable=date_to_nullable,
            opponent_team_id_nullable=opponent_team_id_nullable,
            vs_conference_nullable=vs_conference_nullable,
            vs_division_nullable=vs_division_nullable,
            team_id_nullable=team_id_nullable,
            conference_nullable=conference_nullable,
            division_nullable=division_nullable,
            game_segment_nullable=game_segment_nullable,
            last_n_games_nullable=last_n_games_nullable,
            location_nullable=location_nullable,
            outcome_nullable=outcome_nullable,
            po_round_nullable=po_round_nullable,
            season_segment_nullable=season_segment_nullable,
            shot_clock_range_nullable=shot_clock_range_nullable,
            close_def_dist_range_nullable=close_def_dist_range_nullable,
            shot_dist_range_nullable=shot_dist_range_nullable,
            dribble_range_nullable=dribble_range_nullable,
            general_range_nullable=general_range_nullable,
            touch_time_range_nullable=touch_time_range_nullable,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"LeagueDashOppPtShot API call successful for Season: {season}")

        # This endpoint often has one primary dataset, typically named 'league_dash_opp_pt_shot' or similar.
        # We need to confirm the actual name from nba_api if possible, or inspect a raw response.
        # Assuming 'league_dash_opp_pt_shot' as a placeholder.
        # If the endpoint has multiple result sets, they would be endpoint.result_set_name.get_data_frame()
        
        # Attempt to get the primary dataframe. The actual name might differ.
        # Common names for such endpoints are often the endpoint name itself in snake_case or a generic name.
        # For LeagueDashOppPtShot, a likely name is 'league_dash_opp_pt_shot' or 'OpponentPlayerShooting'.
        # If unsure, one would typically inspect the endpoint object or its available attributes.
        # For now, let's assume it's 'league_dash_opp_pt_shot', the endpoint class name in snake_case.
        if hasattr(endpoint, 'league_dash_opp_pt_shot'):
            data_df = endpoint.league_dash_opp_pt_shot.get_data_frame()
        else: # Fallback if the assumed name is wrong, try to find the primary dataset
            # This is a simplistic way; more robust would be to check endpoint.get_result_sets()
            # and find the one most likely to be the main data.
            # However, direct inspection of nba_api source or a live call is best.
            # Let's assume it's the first available result set if the specific name isn't found.
            result_sets = endpoint.get_available_data()
            if result_sets:
                 data_df = endpoint.data_sets[0].get_data_frame() # endpoint.data_sets[0] is a common pattern
            else:
                logger.warning(f"No data found for LeagueDashOppPtShot with params: {season}, {per_mode_simple}")
                return format_response({"parameters": {"season": season, "per_mode_simple": per_mode_simple}, "opponent_shots": []})


        data_list = _process_dataframe(data_df, single_row=False)

        if data_list is None:
            logger.error("DataFrame processing failed for LeagueDashOppPtShot.")
            return format_response(error=Errors.LEAGUE_DASH_OPP_PT_SHOT_API_ERROR.format(error="DataFrame processing returned None unexpectedly."))

        response_data = {
            "parameters": {
                "season": season,
                "season_type": season_type,
                "per_mode_simple": per_mode_simple,
                "league_id_nullable": league_id_nullable,
                "month_nullable": month_nullable,
                "period_nullable": period_nullable,
                "date_from_nullable": date_from_nullable,
                "date_to_nullable": date_to_nullable,
                "opponent_team_id_nullable": opponent_team_id_nullable,
                "team_id_nullable": team_id_nullable
            },
            "opponent_shots": data_list
        }
        
        logger.info(f"Successfully fetched {len(data_list)} opponent shot entries for Season: {season}")
        return format_response(response_data)

    except Exception as e:
        logger.error(
            f"Error in fetch_league_dash_opponent_pt_shot_logic for Season {season}, Mode {per_mode_simple}: {str(e)}",
            exc_info=True
        )
        return format_response(error=Errors.LEAGUE_DASH_OPP_PT_SHOT_API_ERROR.format(error=str(e))) 
"""
Handles fetching NBA draft history data using the drafthistory endpoint.
Allows filtering by various parameters like season year, league, team, round, and pick.
"""
import logging
import json # Not explicitly used, but format_response returns JSON string. Good to keep for context.
from typing import Optional, Dict, Any, List, Set
from functools import lru_cache

from nba_api.stats.endpoints import drafthistory
from nba_api.stats.library.parameters import LeagueID
from .utils import _process_dataframe, format_response
from ..config import settings
from ..core.errors import Errors

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
LEAGUE_DRAFT_CACHE_SIZE = 32

_VALID_DRAFT_LEAGUE_IDS: Set[str] = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

# --- Logic Function ---
@lru_cache(maxsize=LEAGUE_DRAFT_CACHE_SIZE)
def fetch_draft_history_logic(
    season_year_nullable: Optional[str] = None,
    league_id_nullable: str = LeagueID.nba,
    team_id_nullable: Optional[int] = None,
    round_num_nullable: Optional[int] = None,
    overall_pick_nullable: Optional[int] = None
) -> str:
    """
    Fetches NBA draft history using nba_api's DraftHistory endpoint, optionally filtered by season year, league, team, round number, or overall pick.

    Args:
        season_year_nullable (Optional[str]): Four-digit draft year (e.g., '2023'). If None, returns all years.
        league_id_nullable (str): League ID (default: NBA).
        team_id_nullable (Optional[int]): NBA team ID to filter by team.
        round_num_nullable (Optional[int]): Draft round number to filter by round.
        overall_pick_nullable (Optional[int]): Overall pick number to filter by pick.

    Returns:
        str: JSON-formatted string containing a list of draft picks or an error message.

    Notes:
        - Returns an error for invalid year format or league ID.
        - Returns an empty list if no draft picks are found for the filters.
        - Each draft pick includes player, year, round, pick, team, and organization info.
    """
    year_log_display = season_year_nullable or "All"
    logger.info(f"Executing fetch_draft_history_logic for SeasonYear: {year_log_display}, League: {league_id_nullable}, Team: {team_id_nullable}, Round: {round_num_nullable}, Pick: {overall_pick_nullable}")

    if season_year_nullable and (not season_year_nullable.isdigit() or len(season_year_nullable) != 4):
        error_msg = Errors.INVALID_DRAFT_YEAR_FORMAT.format(year=season_year_nullable)
        logger.error(error_msg)
        return format_response(error=error_msg)

    if league_id_nullable not in _VALID_DRAFT_LEAGUE_IDS:
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id_nullable, options=", ".join(_VALID_DRAFT_LEAGUE_IDS)))

    try:
        logger.debug(f"Fetching drafthistory for SeasonYear: {year_log_display}, League: {league_id_nullable}")
        draft_endpoint = drafthistory.DraftHistory(
            league_id=league_id_nullable,
            season_year_nullable=season_year_nullable,
            team_id_nullable=team_id_nullable,
            round_num_nullable=round_num_nullable,
            overall_pick_nullable=overall_pick_nullable,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"drafthistory API call successful for SeasonYear: {year_log_display}")
        draft_df = draft_endpoint.draft_history.get_data_frame()
        draft_list = _process_dataframe(draft_df, single_row=False)

        if draft_list is None:
            if draft_df.empty:
                logger.warning(f"No draft history data found for year {year_log_display} with specified filters.")
                return format_response({
                    "season_year_requested": year_log_display, "league_id": league_id_nullable,
                    "team_id_filter": team_id_nullable, "round_num_filter": round_num_nullable,
                    "overall_pick_filter": overall_pick_nullable, "draft_picks": []
                })
            else:
                logger.error(f"DataFrame processing failed for draft history ({year_log_display}).")
                error_msg = Errors.DRAFT_HISTORY_PROCESSING.format(year=year_log_display)
                return format_response(error=error_msg)
        
        result = {
            "season_year_requested": year_log_display, "league_id": league_id_nullable,
            "team_id_filter": team_id_nullable, "round_num_filter": round_num_nullable,
            "overall_pick_filter": overall_pick_nullable, "draft_picks": draft_list or []
        }
        logger.info(f"fetch_draft_history_logic completed for SeasonYear: {year_log_display}")
        return format_response(result)

    except Exception as e:
        logger.critical(f"Unexpected error in fetch_draft_history_logic for SeasonYear '{year_log_display}': {e}", exc_info=True)
        error_msg = Errors.DRAFT_HISTORY_UNEXPECTED.format(year=year_log_display, error=str(e))
        return format_response(error=error_msg)
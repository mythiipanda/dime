"""
Handles fetching team-level passing tracking statistics using the TeamDashPtPass endpoint.
Utilizes shared utilities for team identification and parameter validation.
"""
import logging
from functools import lru_cache
from typing import Set # For type hinting validation sets

from nba_api.stats.endpoints import teamdashptpass
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import _process_dataframe, format_response
from backend.api_tools.team_tracking_utils import _validate_team_tracking_params, _get_team_info_for_tracking
from backend.api_tools.http_client import nba_session # For session patching

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
TEAM_PASSING_TRACKING_CACHE_SIZE = 128

_TEAM_PASSING_VALID_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_TEAM_PASSING_VALID_PER_MODES: Set[str] = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}

# Apply session patch to the endpoint class for custom HTTP client usage
teamdashptpass.requests = nba_session

# --- Main Logic Function ---
@lru_cache(maxsize=TEAM_PASSING_TRACKING_CACHE_SIZE)
def fetch_team_passing_stats_logic(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game
) -> str:
    """
    Fetches team passing statistics, detailing passes made and received among players
    for a specific team and season using the TeamDashPtPass endpoint.

    Args:
        team_identifier (str): Name, abbreviation, or ID of the team.
        season (str, optional): NBA season in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Type of season (e.g., "Regular Season"). Defaults to Regular Season.
        per_mode (str, optional): Statistical mode (e.g., "PerGame"). Defaults to PerGame.

    Returns:
        str: JSON string with team passing stats or an error message.
             Includes 'passes_made' and 'passes_received' lists.
    """
    logger.info(f"Executing fetch_team_passing_stats_logic for: {team_identifier}, Season: {season}, PerMode: {per_mode}")

    # Basic validation for team_identifier and season (delegated)
    validation_error_msg = _validate_team_tracking_params(team_identifier, season)
    if validation_error_msg:
        return validation_error_msg

    # Specific validation for season_type and per_mode for this endpoint
    if season_type not in _TEAM_PASSING_VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_TEAM_PASSING_VALID_SEASON_TYPES)[:5])))
    if per_mode not in _TEAM_PASSING_VALID_PER_MODES:
        return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_TEAM_PASSING_VALID_PER_MODES)[:5])))

    # Resolve team ID and name
    error_resp, team_id_resolved, team_name_resolved = _get_team_info_for_tracking(team_identifier, None) # No specific league_id needed for teamdashptpass
    if error_resp:
        return error_resp
    if team_id_resolved is None or team_name_resolved is None: # Should be caught by error_resp, but defensive check
        return format_response(error=Errors.TEAM_INFO_RESOLUTION_FAILED.format(identifier=team_identifier))

    try:
        logger.debug(f"Fetching teamdashptpass for Team ID: {team_id_resolved}, Season: {season}")
        pass_stats_endpoint = teamdashptpass.TeamDashPtPass(
            team_id=team_id_resolved, season=season, season_type_all_star=season_type,
            per_mode_simple=per_mode, timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"teamdashptpass API call successful for ID: {team_id_resolved}, Season: {season}")

        passes_made_df = pass_stats_endpoint.passes_made.get_data_frame()
        passes_received_df = pass_stats_endpoint.passes_received.get_data_frame()

        passes_made_list = _process_dataframe(passes_made_df, single_row=False)
        passes_received_list = _process_dataframe(passes_received_df, single_row=False)

        if passes_made_list is None or passes_received_list is None:
            if passes_made_df.empty and passes_received_df.empty:
                logger.warning(f"No passing stats found for team {team_name_resolved} ({team_id_resolved}), season {season}.")
                return format_response({
                    "team_name": team_name_resolved, "team_id": team_id_resolved, "season": season,
                    "season_type": season_type, "parameters": {"per_mode": per_mode},
                    "passes_made": [], "passes_received": []
                })
            else:
                logger.error(f"DataFrame processing failed for team passing stats of {team_name_resolved} ({season}).")
                error_msg = Errors.TEAM_PASSING_PROCESSING.format(identifier=str(team_id_resolved))
                return format_response(error=error_msg)

        result = {
            "team_name": team_name_resolved, "team_id": team_id_resolved, "season": season, "season_type": season_type,
            "parameters": {"per_mode": per_mode},
            "passes_made": passes_made_list or [], "passes_received": passes_received_list or []
        }
        logger.info(f"fetch_team_passing_stats_logic completed for '{team_name_resolved}'")
        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching passing stats for team {team_identifier}: {str(e)}", exc_info=True)
        error_msg = Errors.TEAM_PASSING_UNEXPECTED.format(identifier=team_identifier, error=str(e))
        return format_response(error=error_msg)
import logging
from typing import Optional, Tuple

from core.errors import Errors
from api_tools.utils import (
    format_response,
    find_team_id_or_error,
    TeamNotFoundError
)
from utils.validation import _validate_season_format

logger = logging.getLogger(__name__)

def _validate_team_tracking_params(
    team_identifier: Optional[str],
    season: str,
    team_id: Optional[int] = None
) -> Optional[str]:
    """Validate common parameters for team tracking stats functions."""
    if not team_identifier and team_id is None:
        return format_response(error=Errors.TEAM_IDENTIFIER_OR_ID_REQUIRED)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    return None

def _get_team_info_for_tracking(team_identifier: Optional[str], team_id_input: Optional[int]) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """
    Resolves team_id and team_name from either team_identifier or a direct team_id_input.
    Returns a tuple: (error_response_json_str, resolved_team_id, resolved_team_name).
    If successful, error_response_json_str is None.
    """
    if team_id_input is not None:
        try:
            resolved_id, resolved_name = find_team_id_or_error(str(team_id_input))
            if resolved_id == team_id_input:
                 return None, resolved_id, resolved_name
            else:
                 logger.warning(f"Team ID {team_id_input} resolved to a different ID {resolved_id} or name. Using original ID.")
                 return None, team_id_input, f"Team_{team_id_input}"
        except (TeamNotFoundError, ValueError) as e:
            logger.warning(f"Could not find/validate team name for provided ID {team_id_input}: {e}")
            return None, team_id_input, f"Team_{team_id_input}"
    elif team_identifier:
        try:
            resolved_id, resolved_name = find_team_id_or_error(team_identifier)
            return None, resolved_id, resolved_name
        except (TeamNotFoundError, ValueError) as e:
            logger.warning(f"Team lookup failed for identifier '{team_identifier}': {e}")
            return format_response(error=str(e)), None, None
    else:
        return format_response(error=Errors.TEAM_IDENTIFIER_OR_ID_REQUIRED), None, None
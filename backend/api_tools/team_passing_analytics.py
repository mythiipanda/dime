import logging
import json
from typing import Optional, Dict, List, Any
from functools import lru_cache

from nba_api.stats.endpoints import teamdashptpass
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    _validate_season_format,
    format_response,
    find_team_id_or_error,
    TeamNotFoundError
)

logger = logging.getLogger(__name__)

@lru_cache(maxsize=128)
def fetch_team_passing_stats_logic(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game
) -> str:
    """
    Fetches team passing statistics.
    (Docstring content remains largely the same as before, detailing args and return structure)
    """
    logger.info(f"Executing fetch_team_passing_stats_logic for: '{team_identifier}', Season: {season}, PerMode: {per_mode}")

    if not team_identifier or not str(team_identifier).strip():
        return format_response(error=Errors.TEAM_IDENTIFIER_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5])))

    VALID_PER_MODES = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}
    if per_mode not in VALID_PER_MODES:
        return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(VALID_PER_MODES)[:3])))

    try:
        team_id, team_actual_name = find_team_id_or_error(team_identifier)
        logger.debug(f"Fetching teamdashptpass for Team ID: {team_id}, Season: {season}, PerMode: {per_mode}")
        try:
            passing_stats_endpoint = teamdashptpass.TeamDashPtPass(
                team_id=team_id, season=season, season_type_all_star=season_type,
                per_mode_simple=per_mode, timeout=settings.DEFAULT_TIMEOUT_SECONDS
            )
            logger.debug(f"teamdashptpass API call successful for ID: {team_id}, Season: {season}")
            passes_made_df = passing_stats_endpoint.passes_made.get_data_frame()
            passes_received_df = passing_stats_endpoint.passes_received.get_data_frame()
        except Exception as api_error:
            logger.error(f"nba_api teamdashptpass failed for ID {team_id}, Season {season}: {api_error}", exc_info=True)
            error_msg = Errors.TEAM_PASSING_API.format(identifier=str(team_id), season=season, error=str(api_error))
            return format_response(error=error_msg)

        passes_made_list = _process_dataframe(passes_made_df, single_row=False)
        passes_received_list = _process_dataframe(passes_received_df, single_row=False)

        if passes_made_list is None or passes_received_list is None:
            if passes_made_df.empty and passes_received_df.empty:
                logger.warning(f"No passing stats found for team {team_actual_name} ({team_id}), season {season}.")
                passes_made_list, passes_received_list = [], []
            else: 
                logger.error(f"DataFrame processing failed for team passing stats of {team_actual_name} ({season}).")
                error_msg = Errors.TEAM_PASSING_PROCESSING.format(identifier=str(team_id), season=season)
                return format_response(error=error_msg)

        result = {
            "team_name": team_actual_name, "team_id": team_id, "season": season, "season_type": season_type,
            "parameters": {"per_mode": per_mode},
            "passes_made": passes_made_list or [],
            "passes_received": passes_received_list or []
        }
        logger.info(f"fetch_team_passing_stats_logic completed for '{team_actual_name}'")
        return format_response(result)

    except (TeamNotFoundError, ValueError) as lookup_error:
        logger.warning(f"Team lookup or validation failed for '{team_identifier}': {lookup_error}")
        return format_response(error=str(lookup_error))
    except Exception as unexpected_error:
        error_msg = Errors.TEAM_PASSING_UNEXPECTED.format(identifier=team_identifier, season=season, error=str(unexpected_error))
        logger.critical(error_msg, exc_info=True)
        return format_response(error=error_msg)
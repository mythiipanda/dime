import logging
import json
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from functools import lru_cache

from nba_api.stats.endpoints import (
    teamdashptpass,
    teamdashptreb,
    teamdashptshots
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed, # Used for validation reference, API might use PerModeSimple
    PerModeSimple # Explicitly import for clarity
)

from backend.config import DEFAULT_TIMEOUT, Errors, CURRENT_SEASON
from backend.api_tools.utils import (
    _process_dataframe,
    format_response,
    _validate_season_format,
    validate_date_format,
    find_team_id_or_error,
    TeamNotFoundError
)
from backend.api_tools.http_client import nba_session # For potential session patching

logger = logging.getLogger(__name__)

# Apply session patch if still needed (though direct requests.Session usage is generally preferred for new code)
# This is a workaround for potential issues in the nba_api library's default session handling.
teamdashptpass.requests = nba_session
teamdashptreb.requests = nba_session
teamdashptshots.requests = nba_session


# --- Helper Functions --- (Specific to this module or could be further centralized if used elsewhere)

def _validate_team_tracking_params(
    team_identifier: Optional[str],
    season: str,
    team_id: Optional[int] = None # Allow direct team_id input
) -> Optional[str]: # Returns error string if validation fails, None otherwise
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
        # If ID is provided, try to get the name for consistency in responses.
        # This relies on find_team_id_or_error to also work with IDs for name lookup.
        try:
            # Use find_team_id_or_error with the ID to get the canonical name.
            # This assumes find_team_id_or_error can take an int and return its name.
            # If not, a different lookup (e.g., static teams list) would be needed here.
            # For now, let's assume find_team_id_or_error handles this or we adapt it.
            # As find_team_id_or_error expects a string, we convert team_id_input.
            resolved_id, resolved_name = find_team_id_or_error(str(team_id_input))
            if resolved_id == team_id_input: # Ensure the ID resolved correctly
                 return None, resolved_id, resolved_name
            else: # Should not happen if ID is valid
                 logger.warning(f"Team ID {team_id_input} resolved to a different ID {resolved_id} or name. Using original ID.")
                 return None, team_id_input, f"Team_{team_id_input}" # Fallback name
        except (TeamNotFoundError, ValueError) as e:
            logger.warning(f"Could not find/validate team name for provided ID {team_id_input}: {e}")
            # Proceed with the provided ID, but name might be generic.
            return None, team_id_input, f"Team_{team_id_input}" # Fallback name
    elif team_identifier:
        try:
            resolved_id, resolved_name = find_team_id_or_error(team_identifier)
            return None, resolved_id, resolved_name
        except (TeamNotFoundError, ValueError) as e:
            logger.warning(f"Team lookup failed for identifier '{team_identifier}': {e}")
            return format_response(error=str(e)), None, None
    else:
        # This case should be caught by _validate_team_tracking_params
        return format_response(error=Errors.TEAM_IDENTIFIER_OR_ID_REQUIRED), None, None


# --- Logic Functions ---

@lru_cache(maxsize=128)
def fetch_team_passing_stats_logic(
    team_identifier: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game # API uses per_mode_simple for this endpoint
) -> str:
    """
    Fetches team passing statistics, detailing passes made and received among players for a specific team and season.

    Args:
        team_identifier (str): The team's name (e.g., "Denver Nuggets"), abbreviation (e.g., "DEN"), or ID (e.g., 1610612743).
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
                                Defaults to `CURRENT_SEASON`.
        season_type (str, optional): The type of season. Valid values from `SeasonTypeAllStar`
                                     (e.g., "Regular Season", "Playoffs", "Pre Season", "All Star").
                                     Defaults to "Regular Season".
        per_mode (str, optional): The statistical mode. Valid values from `PerModeSimple` (e.g., "PerGame", "Totals").
                                  The API endpoint `teamdashptpass` uses `PerModeSimple`. Defaults to "PerGame".

    Returns:
        str: JSON string containing team passing statistics.
             Expected dictionary structure passed to format_response:
             {
                 "team_name": str,
                 "team_id": int,
                 "season": str,
                 "season_type": str,
                 "parameters": {"per_mode": str},
                 "passes_made": [ // Stats for passes made by each player on the team
                     {
                         "PLAYER_ID": int, "PLAYER_NAME_LAST_FIRST": str, // Player making the pass
                         "PASS_TEAMMATE_PLAYER_ID": int, "PASS_TO": str, // Teammate receiving the pass
                         "FREQUENCY": float, "PASS": float, "AST": float, "FGM": float, "FGA": float, "FG_PCT": float, ...
                     }, ...
                 ],
                 "passes_received": [ // Stats for passes received by each player on the team
                     {
                         "PLAYER_ID": int, "PLAYER_NAME_LAST_FIRST": str, // Player receiving the pass
                         "PASS_TEAMMATE_PLAYER_ID": int, "PASS_FROM": str, // Teammate making the pass
                         "FREQUENCY": float, "PASS": float, "AST": float, "FGM": float, "FGA": float, "FG_PCT": float, ...
                     }, ...
                 ]
             }
             Returns empty lists if no data is found.
             Or an {'error': 'Error message'} object if a critical issue occurs.
    """
    logger.info(f"Executing fetch_team_passing_stats_logic for: {team_identifier}, Season: {season}, PerMode: {per_mode}")

    validation_error_msg = _validate_team_tracking_params(team_identifier, season)
    if validation_error_msg: return validation_error_msg

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(VALID_SEASON_TYPES)))

    VALID_PER_MODES = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}
    if per_mode not in VALID_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(VALID_PER_MODES))
        return format_response(error=error_msg)

    error_resp, team_id_resolved, team_name_resolved = _get_team_info_for_tracking(team_identifier, None)
    if error_resp: return error_resp
    if team_id_resolved is None or team_name_resolved is None: return format_response(error=Errors.TEAM_INFO_RESOLUTION_FAILED.format(identifier=team_identifier))

    try:
        logger.debug(f"Fetching teamdashptpass for Team ID: {team_id_resolved}, Season: {season}")
        pass_stats_endpoint = teamdashptpass.TeamDashPtPass(
            team_id=team_id_resolved, season=season, season_type_all_star=season_type,
            per_mode_simple=per_mode, timeout=DEFAULT_TIMEOUT
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

@lru_cache(maxsize=128)
def fetch_team_rebounding_stats_logic(
    team_identifier: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game, # API uses per_mode_simple
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Fetches team rebounding statistics, categorized by various factors like shot type,
    contest level, shot distance, and rebound distance.

    Args:
        team_identifier (str): The team's name, abbreviation, or ID (e.g., "Boston Celtics", "BOS", 1610612738).
        season (str, optional): The NBA season identifier in YYYY-YY format. Defaults to `CURRENT_SEASON`.
        season_type (str, optional): The type of season. Valid values from `SeasonTypeAllStar`. Defaults to "Regular Season".
        per_mode (str, optional): The statistical mode. Valid values from `PerModeSimple`. Defaults to "PerGame".
        opponent_team_id (int, optional): Filter stats against a specific opponent team ID. Defaults to 0 (all opponents).
        date_from (str, optional): Start date for filtering games (YYYY-MM-DD). Defaults to None.
        date_to (str, optional): End date for filtering games (YYYY-MM-DD). Defaults to None.

    Returns:
        str: JSON string containing team rebounding statistics splits.
             Expected dictionary structure passed to format_response:
             {
                 "team_id": int,
                 "team_name": str,
                 "season": str,
                 "season_type": str,
                 "parameters": {"per_mode": str, "opponent_team_id": int, "date_from": Optional[str], "date_to": Optional[str]},
                 "overall": { // Overall team rebounding stats
                     "TEAM_ID": int, "TEAM_NAME": str, "GP": int, "MIN": float,
                     "OREB": float, "DREB": float, "REB": float, "C_REB_PCT": Optional[float], ...
                 },
                 "by_shot_type": [ // Rebounding stats broken down by shot type faced by the team
                     {"SHOT_TYPE_DESCR": str, "OREB": float, "DREB": float, "REB": float, ...}, ...
                 ],
                 "by_contest": [ // Rebounding stats broken down by contest level on shots
                     {"CONTEST_TYPE": str, "OREB": float, "DREB": float, "REB": float, ...}, ...
                 ],
                 "by_shot_distance": [ // Rebounding stats broken down by distance of the shot
                     {"SHOT_DIST_RANGE": str, "OREB": float, "DREB": float, "REB": float, ...}, ...
                 ],
                 "by_rebound_distance": [ // Rebounding stats broken down by distance of the rebound
                     {"REB_DIST_RANGE": str, "OREB": float, "DREB": float, "REB": float, ...}, ...
                 ]
             }
             Returns empty dicts/lists if no data is found.
             Or an {'error': 'Error message'} object if a critical issue occurs.
    """
    logger.info(f"Executing fetch_team_rebounding_stats_logic for: {team_identifier}, Season: {season}, PerMode: {per_mode}")

    validation_error_msg = _validate_team_tracking_params(team_identifier, season)
    if validation_error_msg: return validation_error_msg
    if date_from and not validate_date_format(date_from): return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from))
    if date_to and not validate_date_format(date_to): return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to))

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(VALID_SEASON_TYPES)))

    VALID_PER_MODES = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}
    if per_mode not in VALID_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(VALID_PER_MODES))
        return format_response(error=error_msg)

    error_resp, team_id_resolved, team_name_resolved = _get_team_info_for_tracking(team_identifier, None)
    if error_resp: return error_resp
    if team_id_resolved is None or team_name_resolved is None: return format_response(error=Errors.TEAM_INFO_RESOLUTION_FAILED.format(identifier=team_identifier))

    try:
        logger.debug(f"Fetching teamdashptreb for Team ID: {team_id_resolved}, Season: {season}")
        reb_stats_endpoint = teamdashptreb.TeamDashPtReb(
            team_id=team_id_resolved, season=season, season_type_all_star=season_type,
            per_mode_simple=per_mode, opponent_team_id=opponent_team_id,
            date_from_nullable=date_from, date_to_nullable=date_to, timeout=DEFAULT_TIMEOUT
        )
        logger.debug(f"teamdashptreb API call successful for {team_name_resolved}")

        overall_df = reb_stats_endpoint.overall_rebounding.get_data_frame()
        shot_type_df = reb_stats_endpoint.shot_type_rebounding.get_data_frame()
        contested_df = reb_stats_endpoint.num_contested_rebounding.get_data_frame()
        distances_df = reb_stats_endpoint.shot_distance_rebounding.get_data_frame()
        reb_dist_df = reb_stats_endpoint.reb_distance_rebounding.get_data_frame()

        overall_data = _process_dataframe(overall_df, single_row=True)
        shot_type_list = _process_dataframe(shot_type_df, single_row=False)
        contested_list = _process_dataframe(contested_df, single_row=False)
        distances_list = _process_dataframe(distances_df, single_row=False)
        reb_dist_list = _process_dataframe(reb_dist_df, single_row=False)

        if all(data is None for data in [overall_data, shot_type_list, contested_list, distances_list, reb_dist_list]):
            if all(df.empty for df in [overall_df, shot_type_df, contested_df, distances_df, reb_dist_df]):
                logger.warning(f"No rebounding stats found for team {team_name_resolved} with given filters.")
                return format_response({
                    "team_id": team_id_resolved, "team_name": team_name_resolved, "season": season, "season_type": season_type,
                    "parameters": {"per_mode": per_mode, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to},
                    "overall": {}, "by_shot_type": [], "by_contest": [],
                    "by_shot_distance": [], "by_rebound_distance": []
                })
            else:
                logger.error(f"DataFrame processing failed for rebounding stats of {team_name_resolved}.")
                error_msg = Errors.TEAM_REBOUNDING_PROCESSING.format(identifier=str(team_id_resolved))
                return format_response(error=error_msg)

        result = {
            "team_id": team_id_resolved, "team_name": team_name_resolved, "season": season, "season_type": season_type,
            "parameters": {"per_mode": per_mode, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to},
            "overall": overall_data or {}, "by_shot_type": shot_type_list or [],
            "by_contest": contested_list or [], "by_shot_distance": distances_list or [],
            "by_rebound_distance": reb_dist_list or []
        }
        logger.info(f"fetch_team_rebounding_stats_logic completed for {team_name_resolved}")
        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching rebounding stats for team {team_identifier}: {str(e)}", exc_info=True)
        error_msg = Errors.TEAM_REBOUNDING_UNEXPECTED.format(identifier=team_identifier, error=str(e))
        return format_response(error=error_msg)

@lru_cache(maxsize=128)
def fetch_team_shooting_stats_logic(
    team_identifier: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game, # API uses per_mode_simple
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Fetches team shooting statistics, categorized by various factors like shot clock,
    number of dribbles, defender distance, and touch time.

    Args:
        team_identifier (str): The team's name, abbreviation, or ID (e.g., "Golden State Warriors", "GSW", 1610612744).
        season (str, optional): The NBA season identifier in YYYY-YY format. Defaults to `CURRENT_SEASON`.
        season_type (str, optional): The type of season. Valid values from `SeasonTypeAllStar`. Defaults to "Regular Season".
        per_mode (str, optional): The statistical mode. Valid values from `PerModeSimple`. Defaults to "PerGame".
        opponent_team_id (int, optional): Filter stats against a specific opponent team ID. Defaults to 0 (all opponents).
        date_from (str, optional): Start date for filtering games (YYYY-MM-DD). Defaults to None.
        date_to (str, optional): End date for filtering games (YYYY-MM-DD). Defaults to None.

    Returns:
        str: JSON string containing team shooting statistics splits.
             Expected dictionary structure passed to format_response:
             {
                 "team_id": int,
                 "team_name": str,
                 "season": str,
                 "season_type": str,
                 "parameters": {"per_mode": str, "opponent_team_id": int, "date_from": Optional[str], "date_to": Optional[str]},
                 "overall_shooting": { // Overall team shooting summary (first row of general_shooting)
                     "TEAM_ID": int, "TEAM_NAME": str, "SHOT_TYPE": "Overall", "GP": int, "MIN": float,
                     "FGM": float, "FGA": float, "FG_PCT": float, "FG3M": float, "FG3A": float, "FG3_PCT": float, ...
                 },
                 "general_shooting_splits": [ // Splits by shot type (e.g., Catch & Shoot, Pull Ups)
                     {"SHOT_TYPE": str, "FGA_FREQUENCY": float, "FGM": float, "FGA": float, "FG_PCT": float, ...}, ...
                 ],
                 "by_shot_clock": [ // Shooting splits by shot clock remaining
                     {"SHOT_CLOCK_RANGE": str, "FGA_FREQUENCY": float, "FGM": float, "FGA": float, "FG_PCT": float, ...}, ...
                 ],
                 "by_dribble": [ // Shooting splits by number of dribbles
                     {"DRIBBLE_RANGE": str, "FGA_FREQUENCY": float, "FGM": float, "FGA": float, "FG_PCT": float, ...}, ...
                 ],
                 "by_defender_distance": [ // Shooting splits by closest defender distance
                     {"CLOSE_DEF_DIST_RANGE": str, "FGA_FREQUENCY": float, "FGM": float, "FGA": float, "FG_PCT": float, ...}, ...
                 ],
                 "by_touch_time": [ // Shooting splits by touch time before shot
                     {"TOUCH_TIME_RANGE": str, "FGA_FREQUENCY": float, "FGM": float, "FGA": float, "FG_PCT": float, ...}, ...
                 ]
             }
             Returns empty dicts/lists if no data is found.
             Or an {'error': 'Error message'} object if a critical issue occurs.
    """
    logger.info(f"Executing fetch_team_shooting_stats_logic for: {team_identifier}, Season: {season}, PerMode: {per_mode}")

    validation_error_msg = _validate_team_tracking_params(team_identifier, season)
    if validation_error_msg: return validation_error_msg
    if date_from and not validate_date_format(date_from): return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from))
    if date_to and not validate_date_format(date_to): return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to))

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(VALID_SEASON_TYPES)))

    VALID_PER_MODES = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}
    if per_mode not in VALID_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(VALID_PER_MODES))
        return format_response(error=error_msg)

    error_resp, team_id_resolved, team_name_resolved = _get_team_info_for_tracking(team_identifier, None)
    if error_resp: return error_resp
    if team_id_resolved is None or team_name_resolved is None: return format_response(error=Errors.TEAM_INFO_RESOLUTION_FAILED.format(identifier=team_identifier))

    try:
        logger.debug(f"Fetching teamdashptshots for Team ID: {team_id_resolved}, Season: {season}")
        shot_stats_endpoint = teamdashptshots.TeamDashPtShots(
            team_id=team_id_resolved, season=season, season_type_all_star=season_type,
            per_mode_simple=per_mode, opponent_team_id=opponent_team_id,
            date_from_nullable=date_from, date_to_nullable=date_to, timeout=DEFAULT_TIMEOUT
        )
        logger.debug(f"teamdashptshots API call successful for {team_name_resolved}")

        general_df = shot_stats_endpoint.general_shooting.get_data_frame()
        overall_shooting_data = _process_dataframe(general_df.head(1) if not general_df.empty else pd.DataFrame(), single_row=True)
        general_splits_list = _process_dataframe(general_df.iloc[1:] if len(general_df) > 1 else pd.DataFrame(), single_row=False)
        
        shot_clock_list = _process_dataframe(shot_stats_endpoint.shot_clock_shooting.get_data_frame(), single_row=False)
        dribbles_list = _process_dataframe(shot_stats_endpoint.dribble_shooting.get_data_frame(), single_row=False)
        defender_list = _process_dataframe(shot_stats_endpoint.closest_defender_shooting.get_data_frame(), single_row=False)
        touch_time_list = _process_dataframe(shot_stats_endpoint.touch_time_shooting.get_data_frame(), single_row=False)

        if overall_shooting_data is None and not general_df.empty: # Check if processing failed on non-empty general_df
            logger.error(f"DataFrame processing failed for general shooting stats of {team_name_resolved}.")
            error_msg = Errors.TEAM_SHOOTING_PROCESSING.format(identifier=str(team_id_resolved))
            return format_response(error=error_msg)
        
        if general_df.empty: # No data at all from API for general shooting
             logger.warning(f"No shooting stats found for team {team_name_resolved} with given filters.")
             return format_response({
                 "team_id": team_id_resolved, "team_name": team_name_resolved, "season": season, "season_type": season_type,
                 "parameters": {"per_mode": per_mode, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to},
                 "overall_shooting": {}, "general_shooting_splits": [], "by_shot_clock": [],
                 "by_dribble": [], "by_defender_distance": [], "by_touch_time": []
             })

        result = {
            "team_id": team_id_resolved, "team_name": team_name_resolved, "season": season, "season_type": season_type,
            "parameters": {"per_mode": per_mode, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to},
            "overall_shooting": overall_shooting_data or {},
            "general_shooting_splits": general_splits_list or [],
            "by_shot_clock": shot_clock_list or [],
            "by_dribble": dribbles_list or [],
            "by_defender_distance": defender_list or [],
            "by_touch_time": touch_time_list or []
        }
        logger.info(f"fetch_team_shooting_stats_logic completed for {team_name_resolved}")
        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching shooting stats for team {team_identifier}: {str(e)}", exc_info=True)
        error_msg = Errors.TEAM_SHOOTING_UNEXPECTED.format(identifier=team_identifier, error=str(e))
        return format_response(error=error_msg)

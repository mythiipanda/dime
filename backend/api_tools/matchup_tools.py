import json
import logging
from datetime import datetime
import pandas as pd
from typing import Dict, Tuple, Any, Type
from functools import lru_cache

from nba_api.stats.endpoints import LeagueSeasonMatchups, MatchupsRollup
from nba_api.stats.library.parameters import SeasonTypeAllStar
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import format_response, _process_dataframe, find_player_id_or_error, PlayerNotFoundError # _validate_season_format moved
from backend.utils.validation import _validate_season_format
logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS_MATCHUPS = 3600 * 6 # Cache matchup data for 6 hours

# Module-level constant for valid season types
# LeagueSeasonMatchups endpoint uses season_type_playoffs which accepts Regular Season, Pre Season, Playoffs
_MATCHUP_VALID_SEASON_TYPES = {SeasonTypeAllStar.regular, SeasonTypeAllStar.preseason, SeasonTypeAllStar.playoffs}

@lru_cache(maxsize=128)
def get_cached_matchups_data(
    cache_key: Tuple,
    timestamp: str,
    endpoint_class: Type[Any],
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Cached wrapper for NBA API matchup-related endpoints (LeagueSeasonMatchups, MatchupsRollup).
    Uses a timestamp for time-based cache invalidation.

    Args:
        cache_key (Tuple): A tuple representing the core parameters for the API call,
                           used for `lru_cache` keying.
        timestamp (str): An ISO format timestamp string, typically for the current cache validity window,
                         used to manage cache invalidation.
        endpoint_class (Type[Any]): The specific NBA API endpoint class to instantiate (e.g., `LeagueSeasonMatchups`).
        **kwargs: Keyword arguments to be passed directly to the `endpoint_class` constructor.

    Returns:
        Dict[str, Any]: The raw dictionary response from the NBA API endpoint's `get_dict()` method.

    Raises:
        Exception: If the API call fails, to be handled by the caller.
    """
    logger.info(f"Cache miss/expiry for {endpoint_class.__name__} - fetching new data. Key components: {kwargs}")
    try:
        endpoint_instance = endpoint_class(**kwargs, timeout=settings.DEFAULT_TIMEOUT_SECONDS) # Changed
        return endpoint_instance.get_dict()
    except Exception as e:
        logger.error(f"{endpoint_class.__name__} API call failed: {e}", exc_info=True)
        raise e

@lru_cache(maxsize=128)
def fetch_league_season_matchups_logic(
    def_player_identifier: str, # Can be name or ID string
    off_player_identifier: str, # Can be name or ID string
    season: str = settings.CURRENT_NBA_SEASON, # Changed
    season_type: str = SeasonTypeAllStar.regular,
    bypass_cache: bool = False
) -> str:
    """
    Fetches season matchup statistics between two specific players (one defensive, one offensive) using nba_api's LeagueSeasonMatchups endpoint.
    Player identifiers can be names or IDs; they will be resolved to IDs.

    Args:
        def_player_identifier (str): The name or ID of the defensive player.
        off_player_identifier (str): The name or ID of the offensive player.
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24"). Defaults to CURRENT_SEASON.
        season_type (str, optional): The type of season. Valid values from SeasonTypeAllStar (e.g., "Regular Season", "Playoffs"). Defaults to "Regular Season".
        bypass_cache (bool, optional): If True, ignores cached data and fetches fresh data. Defaults to False.

    Returns:
        str: JSON-formatted string with matchup data or an error message. Structure includes player IDs/names, parameters, and a list of matchup stats.

    Notes:
        - Returns an error for missing/invalid player identifiers or season format.
        - Returns an empty list if no matchup data is found.
        - Each matchup includes detailed stats for the defensive vs offensive player pairing.
    """
    logger.info(f"Fetching season matchups: Def '{def_player_identifier}' vs Off '{off_player_identifier}' for {season}, Type: {season_type}")

    if not def_player_identifier or not off_player_identifier:
        return format_response(error=Errors.MISSING_PLAYER_IDENTIFIER)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    if season_type not in _MATCHUP_VALID_SEASON_TYPES: # Use module-level constant
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_MATCHUP_VALID_SEASON_TYPES)[:5]))) # Show some options

    try:
        def_player_id_resolved, def_player_name_resolved = find_player_id_or_error(def_player_identifier)
        off_player_id_resolved, off_player_name_resolved = find_player_id_or_error(off_player_identifier)
    except (PlayerNotFoundError, ValueError) as e:
        logger.warning(f"Player ID lookup failed for matchups: {e}")
        return format_response(error=str(e))

    cache_key_matchups = ("league_season_matchups", str(def_player_id_resolved), str(off_player_id_resolved), season, season_type)
    current_time_epoch = int(datetime.now().timestamp())
    timestamp_bucket = str(current_time_epoch // CACHE_TTL_SECONDS_MATCHUPS)
    
    api_params_matchups = {
        "def_player_id_nullable": str(def_player_id_resolved), # API expects string IDs
        "off_player_id_nullable": str(off_player_id_resolved),
        "season": season,
        "season_type_playoffs": season_type
    }

    try:
        response_dict_matchups: Dict[str, Any]
        endpoint_instance = None # Initialize to None

        if bypass_cache or season == settings.CURRENT_NBA_SEASON:
            logger.info(f"Fetching fresh season matchup data (Bypass: {bypass_cache}, Season: {season})")
            endpoint_instance = LeagueSeasonMatchups(**api_params_matchups, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
            response_dict_matchups = endpoint_instance.get_dict()
        else:
            response_dict_matchups = get_cached_matchups_data(
                cache_key=cache_key_matchups, timestamp=timestamp_bucket,
                endpoint_class=LeagueSeasonMatchups, **api_params_matchups
            )

        matchups_df = pd.DataFrame()
        # Try direct attribute access if endpoint_instance was created (i.e., not from cache that returns dict)
        if endpoint_instance and hasattr(endpoint_instance, 'season_matchups') and hasattr(endpoint_instance.season_matchups, 'get_data_frame'):
            matchups_df = endpoint_instance.season_matchups.get_data_frame()
            logger.debug(f"Successfully accessed 'season_matchups' dataset directly for Def {def_player_name_resolved} vs Off {off_player_name_resolved}.")
        else: # Fallback to parsing resultSets from response_dict_matchups (either from live get_dict() or cached dict)
            logger.warning("Attempting fallback to 'resultSets' for LeagueSeasonMatchups. Direct attribute access preferred if endpoint_instance was used.")
            result_set_data_fallback = None
            # response_dict_matchups will always be populated here, either from live call or cache
            if 'resultSets' in response_dict_matchups and isinstance(response_dict_matchups['resultSets'], list):
                for rs_item in response_dict_matchups['resultSets']:
                    if rs_item.get('name') == 'SeasonMatchups':
                        result_set_data_fallback = rs_item
                        break
                if not result_set_data_fallback and len(response_dict_matchups['resultSets']) > 0:
                    logger.warning("Dataset 'SeasonMatchups' not found by name, using first result set as fallback.")
                    result_set_data_fallback = response_dict_matchups['resultSets'][0]
            
            if result_set_data_fallback and result_set_data_fallback.get('rowSet') and result_set_data_fallback.get('headers'):
                matchups_df = pd.DataFrame(result_set_data_fallback['rowSet'], columns=result_set_data_fallback['headers'])

        if matchups_df.empty:
            logger.warning(f"No matchup data found (or DataFrame is empty) for Def {def_player_name_resolved} vs Off {off_player_name_resolved} in {season}.")
            return format_response({
                "def_player_id": def_player_id_resolved, "def_player_name": def_player_name_resolved,
                "off_player_id": off_player_id_resolved, "off_player_name": off_player_name_resolved,
                "parameters": {"season": season, "season_type": season_type}, "matchups": []
            })

        matchups_list = _process_dataframe(matchups_df, single_row=False)
        if matchups_list is None:
            logger.error(f"DataFrame processing failed for season matchups Def {def_player_name_resolved} vs Off {off_player_name_resolved} ({season}).")
            return format_response(error=Errors.MATCHUPS_PROCESSING)

        result_payload = {
            "def_player_id": def_player_id_resolved, "def_player_name": def_player_name_resolved,
            "off_player_id": off_player_id_resolved, "off_player_name": off_player_name_resolved,
            "parameters": {"season": season, "season_type": season_type},
            "matchups": matchups_list or []
        }
        logger.info(f"Successfully fetched season matchups for Def {def_player_name_resolved} vs Off {off_player_name_resolved}")
        return format_response(result_payload)

    except Exception as e:
        logger.error(f"Error fetching season matchups: {e}", exc_info=True)
        error_msg = Errors.MATCHUPS_API.format(error=str(e))
        return format_response(error=error_msg)

@lru_cache(maxsize=128)
def fetch_matchups_rollup_logic(
    def_player_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    bypass_cache: bool = False
) -> str:
    """
    Fetches matchup rollup statistics for a defensive player against all opponents,
    often categorized by the position of the offensive players they guarded.
    Player identifier can be a name or ID; it will be resolved to an ID.

    Args:
        def_player_identifier (str): The name or ID of the defensive player.
        season (str, optional): The NBA season identifier in YYYY-YY format. Defaults to `CURRENT_SEASON`.
        season_type (str, optional): The type of season. Valid values from `SeasonTypeAllStar`. Defaults to "Regular Season".
        bypass_cache (bool, optional): If True, ignores cached data. Defaults to False.

    Returns:
        str: JSON string with matchup rollup data.
             Expected dictionary structure passed to format_response:
             {
                 "def_player_id": int,
                 "def_player_name": str,
                 "parameters": {"season": str, "season_type": str},
                 "rollup": [ // List of rollup stats, often one entry per opponent position guarded
                     {
                         "POSITION": str, // e.g., "Guard", "Forward", "Center"
                         "DEF_PLAYER_ID": int, "DEF_PLAYER_NAME": str,
                         "GP": int, "MATCHUP_MIN": Optional[str],
                         "PLAYER_PTS": Optional[int], // Points scored by opponents in this category
                         "MATCHUP_FGM": Optional[int], "MATCHUP_FGA": Optional[int], "MATCHUP_FG_PCT": Optional[float],
                         ... // Other fields from MatchupsRollup endpoint
                     }, ...
                 ]
             }
             Returns {"rollup": []} if no data is found.
             Or an {'error': 'Error message'} object if a critical issue occurs.
    """
    logger.info(f"Fetching matchup rollup for Def Player: '{def_player_identifier}' in {season}, Type: {season_type}")

    if not def_player_identifier:
        return format_response(error=Errors.MISSING_PLAYER_IDENTIFIER)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    if season_type not in _MATCHUP_VALID_SEASON_TYPES: # Use module-level constant
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_MATCHUP_VALID_SEASON_TYPES)[:5]))) # Show some options

    try:
        def_player_id_resolved, def_player_name_resolved = find_player_id_or_error(def_player_identifier)
    except (PlayerNotFoundError, ValueError) as e:
        logger.warning(f"Player ID lookup failed for matchup rollup: {e}")
        return format_response(error=str(e))

    cache_key_rollup = ("matchups_rollup", str(def_player_id_resolved), season, season_type)
    current_time_epoch = int(datetime.now().timestamp())
    timestamp_bucket = str(current_time_epoch // CACHE_TTL_SECONDS_MATCHUPS)

    api_params_rollup = {
        "def_player_id_nullable": str(def_player_id_resolved),
        "season": season,
        "season_type_playoffs": season_type
    }

    try:
        response_dict_rollup: Dict[str, Any]
        endpoint_instance_rollup = None # Initialize to None

        if bypass_cache or season == settings.CURRENT_NBA_SEASON:
            logger.info(f"Fetching fresh matchup rollup data (Bypass: {bypass_cache}, Season: {season})")
            endpoint_instance_rollup = MatchupsRollup(**api_params_rollup, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
            response_dict_rollup = endpoint_instance_rollup.get_dict()
        else:
            response_dict_rollup = get_cached_matchups_data(
                cache_key=cache_key_rollup, timestamp=timestamp_bucket,
                endpoint_class=MatchupsRollup, **api_params_rollup
            )
        
        rollup_df = pd.DataFrame()
        # Try direct attribute access if endpoint_instance_rollup was created
        if endpoint_instance_rollup and hasattr(endpoint_instance_rollup, 'matchups_rollup') and hasattr(endpoint_instance_rollup.matchups_rollup, 'get_data_frame'):
            rollup_df = endpoint_instance_rollup.matchups_rollup.get_data_frame()
            logger.debug(f"Successfully accessed 'matchups_rollup' dataset directly for Def Player {def_player_name_resolved}.")
        else: # Fallback to parsing resultSets from response_dict_rollup
            logger.warning("Attempting fallback to 'resultSets' for MatchupsRollup. Direct attribute access preferred if endpoint_instance_rollup was used.")
            result_set_data_fallback = None
            if 'resultSets' in response_dict_rollup and isinstance(response_dict_rollup['resultSets'], list):
                for rs_item in response_dict_rollup['resultSets']:
                    if rs_item.get('name') == 'MatchupsRollup':
                        result_set_data_fallback = rs_item
                        break
                if not result_set_data_fallback and len(response_dict_rollup['resultSets']) > 0:
                    logger.warning("Dataset 'MatchupsRollup' not found by name, using first result set as fallback.")
                    result_set_data_fallback = response_dict_rollup['resultSets'][0]
            
            if result_set_data_fallback and result_set_data_fallback.get('rowSet') and result_set_data_fallback.get('headers'):
                rollup_df = pd.DataFrame(result_set_data_fallback['rowSet'], columns=result_set_data_fallback['headers'])

        if rollup_df.empty:
            logger.warning(f"No matchup rollup data found (or DataFrame is empty) for Def Player {def_player_name_resolved} in {season}.")
            return format_response({
                "def_player_id": def_player_id_resolved, "def_player_name": def_player_name_resolved,
                "parameters": {"season": season, "season_type": season_type}, "rollup": []
            })

        rollup_list = _process_dataframe(rollup_df, single_row=False)
        if rollup_list is None: # This check is now safe
            logger.error(f"DataFrame processing failed for matchup rollup Def {def_player_name_resolved} ({season}).")
            return format_response(error=Errors.MATCHUPS_ROLLUP_PROCESSING)

        result_payload = {
            "def_player_id": def_player_id_resolved, "def_player_name": def_player_name_resolved,
            "parameters": {"season": season, "season_type": season_type},
            "rollup": rollup_list or []
        }
        logger.info(f"Successfully fetched matchup rollup for Def Player {def_player_name_resolved}")
        return format_response(result_payload)

    except Exception as e:
        logger.error(f"Error fetching matchups rollup for Def Player {def_player_identifier}: {e}", exc_info=True)
        error_msg = Errors.MATCHUPS_ROLLUP_API.format(error=str(e))
        return format_response(error=error_msg)

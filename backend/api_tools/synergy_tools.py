import logging
from typing import Optional, Dict, Any, Tuple, Type
from functools import lru_cache
from datetime import datetime
import pandas as pd

from nba_api.stats.endpoints.synergyplaytypes import SynergyPlayTypes
from nba_api.stats.library.parameters import (
    LeagueID,
    PerModeSimple,
    PlayerOrTeamAbbreviation,
    SeasonTypeAllStar
)
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import format_response, _process_dataframe
from backend.utils.validation import _validate_season_format
logger = logging.getLogger(__name__)

VALID_PLAY_TYPES = {
    "Cut", "Handoff", "Isolation", "Misc", "OffScreen", "PostUp",
    "PRBallHandler", "PRRollman", "OffRebound", "SpotUp", "Transition"
}
VALID_TYPE_GROUPINGS = {"offensive", "defensive"}
CACHE_TTL_SECONDS_SYNERGY = 3600 * 4

@lru_cache(maxsize=128)
def get_cached_synergy_data(
    cache_key: Tuple, # Explicit cache_key for lru_cache
    timestamp: str,   # Explicit timestamp for lru_cache and logging
    endpoint_class: Type[SynergyPlayTypes],
    **api_kwargs: Any # Renamed to distinguish from cache params
) -> Dict[str, Any]:
    """
    Cached wrapper for the SynergyPlayTypes NBA API endpoint.
    Uses a timestamp for time-based cache invalidation.

    Args:
        cache_key (Tuple): A tuple representing the core parameters for the API call,
                           used for `lru_cache` keying.
        timestamp (str): An ISO format timestamp string, typically for the current cache validity window,
                         used to manage cache invalidation.
        endpoint_class (Type[SynergyPlayTypes]): The `SynergyPlayTypes` endpoint class from `nba_api.stats.endpoints`.
        **api_kwargs: Keyword arguments to be passed directly to the `SynergyPlayTypes` constructor.

    Returns:
        Dict[str, Any]: The raw dictionary response from the NBA API endpoint's `get_dict()` method.

    Raises:
        Exception: If the API call fails, to be handled by the caller.
    """
    logger.info(f"Cache miss/expiry for Synergy data - fetching new data. Timestamp: {timestamp}, Key components: {api_kwargs}")
    try:
        synergy_stats_endpoint = endpoint_class(**api_kwargs, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
        return synergy_stats_endpoint.get_dict()
    except Exception as e:
        logger.error(f"{endpoint_class.__name__} API call failed: {e}", exc_info=True)
        raise e

@lru_cache(maxsize=128)
def fetch_synergy_play_types_logic(
    league_id: str = LeagueID.nba,
    per_mode: str = PerModeSimple.per_game,
    player_or_team: str = PlayerOrTeamAbbreviation.team,
    season_type: str = SeasonTypeAllStar.regular,
    season: str = settings.CURRENT_NBA_SEASON,
    play_type_nullable: Optional[str] = None,
    type_grouping_nullable: Optional[str] = None,
    bypass_cache: bool = False
) -> str:
    """
    Fetches Synergy Sports play type statistics for all players or all teams in a league.
    A specific play_type is REQUIRED - the NBA API will return empty data for general queries.
    Valid play types include: "Cut", "Handoff", "Isolation", "Misc", "OffScreen", "PostUp",
    "PRBallHandler", "PRRollman", "OffRebound", "SpotUp", "Transition".

    The type_grouping parameter ("offensive" or "defensive") helps filter the context of the play types.
    Note: Certain combinations of parameters may still return empty data based on data availability.

    Args:
        league_id (str, optional): The league ID. Valid values from `LeagueID`. Defaults to "00" (NBA).
        per_mode (str, optional): The statistical mode. Valid values from `PerModeSimple` (e.g., "PerGame", "Totals").
                                  Defaults to "PerGame".
        player_or_team (str, optional): Fetch stats for 'P' (all Players) or 'T' (all Teams).
                                        Valid values from `PlayerOrTeamAbbreviation`. Defaults to "T" (Team).
                                        This does NOT filter for a specific player/team ID.
        season_type (str, optional): The type of season. Valid values from `SeasonTypeAllStar`.
                                     Defaults to "Regular Season".
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
                                Defaults to `CURRENT_SEASON`.
        play_type_nullable (str, optional): Specific play type to filter for.
                                            Valid values: "Cut", "Handoff", "Isolation", "Misc", "OffScreen",
                                            "PostUp", "PRBallHandler", "PRRollman", "OffRebound", "SpotUp", "Transition".
                                            Defaults to None (all play types).
        type_grouping_nullable (str, optional): Broad grouping of play types. Valid: "offensive", "defensive".
                                                Defaults to None.
        bypass_cache (bool, optional): If True, ignores cached data and fetches fresh data. Defaults to False.

    Returns:
        str: JSON string containing Synergy play type statistics.
             Expected dictionary structure passed to format_response:
             {
                 "parameters": {
                     "league_id": str, "per_mode": str, "player_or_team": str, "season_type": str,
                     "season": str, "play_type": Optional[str], "type_grouping": Optional[str]
                 },
                 "synergy_stats": [
                     {
                         // Common fields:
                         "SEASON_ID": str, "PLAYER_ID": Optional[int], "PLAYER_NAME": Optional[str],
                         "TEAM_ID": Optional[int], "TEAM_ABBREVIATION": Optional[str], "TEAM_NAME": Optional[str],
                         "PLAY_TYPE": str, "GP": Optional[int], "POSS_PCT": Optional[float], // Frequency
                         "PPP": Optional[float], // Points Per Possession
                         "FG_PCT": Optional[float], "EFG_PCT": Optional[float], "FT_FREQ": Optional[float],
                         "SF_FREQ": Optional[float], "AND_ONE_FREQ": Optional[float], "TOV_FREQ": Optional[float],
                         "SCORE_FREQ": Optional[float], "PERCENTILE": Optional[float],
                         "POSS": Optional[float], "PTS": Optional[float], "FGM": Optional[float], "FGA": Optional[float],
                         // ... other fields from SynergyPlayTypes endpoint
                     }, ...
                 ]
             }
             Often returns {"synergy_stats": []} due to external API behavior or no matching data.
             Or an {'error': 'Error message'} object if a critical issue occurs.
    """
    logger.info(f"Executing fetch_synergy_play_types_logic for season: {season}, type: {player_or_team}, play_type: {play_type_nullable}, grouping: {type_grouping_nullable}")

    if not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if play_type_nullable is None:
        return format_response(error=Errors.SYNERGY_PLAY_TYPE_REQUIRED.format(options=", ".join(VALID_PLAY_TYPES)))
    if play_type_nullable not in VALID_PLAY_TYPES:
        return format_response(error=Errors.INVALID_PLAY_TYPE.format(play_type=play_type_nullable, options=", ".join(VALID_PLAY_TYPES)))
    if type_grouping_nullable is not None and type_grouping_nullable not in VALID_TYPE_GROUPINGS:
        return format_response(error=Errors.INVALID_TYPE_GROUPING.format(type_grouping=type_grouping_nullable, options=", ".join(VALID_TYPE_GROUPINGS)))
    
    VALID_PLAYER_TEAM = {getattr(PlayerOrTeamAbbreviation, attr) for attr in dir(PlayerOrTeamAbbreviation) if not attr.startswith('_') and isinstance(getattr(PlayerOrTeamAbbreviation, attr), str)}
    if player_or_team not in VALID_PLAYER_TEAM:
        return format_response(error=Errors.INVALID_PLAYER_OR_TEAM_ABBREVIATION.format(value=player_or_team, valid_values=", ".join(VALID_PLAYER_TEAM)))
    VALID_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}
    if league_id not in VALID_LEAGUE_IDS:
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(VALID_LEAGUE_IDS)))
    VALID_PER_MODES = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}
    if per_mode not in VALID_PER_MODES:
        return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(VALID_PER_MODES)))
    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(VALID_SEASON_TYPES)))

    api_params_synergy = {
        "league_id": league_id, "per_mode_simple": per_mode,
        "player_or_team_abbreviation": player_or_team,
        "season_type_all_star": season_type, "season": season,
        "play_type_nullable": play_type_nullable, "type_grouping_nullable": type_grouping_nullable
    }
    cache_key_synergy = tuple(sorted(api_params_synergy.items())) # Consistent key from dict
    current_time_epoch = int(datetime.now().timestamp())
    timestamp_bucket = str(current_time_epoch // CACHE_TTL_SECONDS_SYNERGY)

    try:
        response_dict_synergy: Dict[str, Any]
        if bypass_cache:
            logger.info(f"Bypassing cache, fetching fresh Synergy data with params: {api_params_synergy}")
            synergy_endpoint = SynergyPlayTypes(**api_params_synergy, timeout=settings.DEFAULT_TIMEOUT_SECONDS) # Changed
            response_dict_synergy = synergy_endpoint.get_dict()
        else:
            response_dict_synergy = get_cached_synergy_data(
                cache_key=cache_key_synergy, timestamp=timestamp_bucket,
                endpoint_class=SynergyPlayTypes, **api_params_synergy
            )
    except KeyError as ke:
        logger.warning(f"KeyError ('{str(ke)}') encountered fetching Synergy data, likely due to unexpected API response format for params: {api_params_synergy}. Returning empty.")
        return format_response({
            "parameters": api_params_synergy,
            "synergy_stats": [],
            "message": f"Could not retrieve Synergy data due to an API response format issue (KeyError: {str(ke)})."
        })
    except Exception as e: # Catch other potential errors from get_cached_synergy_data or initial setup
        logger.error(f"Error fetching or processing Synergy play types before result set processing: {e}", exc_info=True)
        error_msg = Errors.SYNERGY_UNEXPECTED.format(error=str(e))
        return format_response(error=error_msg)

    try:
        result_set_data = None
        if 'resultSets' in response_dict_synergy and isinstance(response_dict_synergy['resultSets'], list):
            for rs_item in response_dict_synergy['resultSets']:
                if isinstance(rs_item, dict) and rs_item.get('name') == 'SynergyPlayType':
                    result_set_data = rs_item
                    break
            if not result_set_data and len(response_dict_synergy['resultSets']) > 0 and isinstance(response_dict_synergy['resultSets'][0], dict) :
                 result_set_data = response_dict_synergy['resultSets'][0]

        if not result_set_data or 'headers' not in result_set_data or 'rowSet' not in result_set_data:
            logger.warning(f"Could not find expected 'SynergyPlayType' data structure in API response for params: {api_params_synergy}. Response: {str(response_dict_synergy)[:500]}")
            return format_response({
                "parameters": api_params_synergy,
                "synergy_stats": [],
                "message": "No Synergy play type data found or response format was unexpected."
            })

        synergy_df = pd.DataFrame(result_set_data['rowSet'], columns=result_set_data['headers'])
        processed_synergy_data = _process_dataframe(synergy_df, single_row=False)

        if processed_synergy_data is None:
            if synergy_df.empty:
                 logger.warning(f"No Synergy play type data rows returned by API for params: {api_params_synergy}")
                 return format_response({"parameters": api_params_synergy, "synergy_stats": []})
            else:
                logger.error(f"DataFrame processing failed for Synergy stats with params: {api_params_synergy}")
                return format_response(error=Errors.SYNERGY_PROCESSING)
        
        logger.info(f"Successfully fetched and processed Synergy play type stats. Found {len(processed_synergy_data)} entries.")
        return format_response({"parameters": api_params_synergy, "synergy_stats": processed_synergy_data or []})

    except Exception as e: # Catch errors during result_set_data processing and DataFrame creation
        logger.error(f"Error processing Synergy play type result sets: {e}", exc_info=True)
        error_msg = Errors.SYNERGY_PROCESSING # More specific error if it's in this block
        return format_response(error=error_msg)

import logging
from functools import lru_cache

from nba_api.stats.endpoints import commonplayerinfo
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import _process_dataframe, format_response, find_player_id_or_error, PlayerNotFoundError

logger = logging.getLogger(__name__)

@lru_cache(maxsize=256)
def fetch_player_info_logic(player_name: str) -> str:
    logger.info(f"Executing fetch_player_info_logic for: '{player_name}'")
    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching commonplayerinfo for player ID: {player_id} ({player_actual_name})")
        try:
            info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
            logger.debug(f"commonplayerinfo API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api commonplayerinfo failed for ID {player_id}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_INFO_API.format(identifier=player_actual_name, error=str(api_error))
            return format_response(error=error_msg)

        player_info_dict = _process_dataframe(info_endpoint.common_player_info.get_data_frame(), single_row=True)
        headline_stats_dict = _process_dataframe(info_endpoint.player_headline_stats.get_data_frame(), single_row=True)
        available_seasons_list = _process_dataframe(info_endpoint.available_seasons.get_data_frame(), single_row=False) # Process new dataset

        # Check if any essential data processing failed
        if player_info_dict is None or headline_stats_dict is None or available_seasons_list is None:
            logger.error(f"DataFrame processing failed for {player_actual_name} (player_info: {player_info_dict is None}, headline_stats: {headline_stats_dict is None}, available_seasons: {available_seasons_list is None}).")
            error_msg = Errors.PLAYER_INFO_PROCESSING.format(identifier=player_actual_name)
            return format_response(error=error_msg)

        logger.info(f"fetch_player_info_logic completed for '{player_actual_name}'")
        return format_response({
            "player_info": player_info_dict or {}, # Ensure empty dict if None
            "headline_stats": headline_stats_dict or {}, # Ensure empty dict if None
            "available_seasons": available_seasons_list or [] # Ensure empty list if None
        })
    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_info_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_info_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_info_logic for '{player_name}': {e}", exc_info=True)
        error_msg = Errors.PLAYER_INFO_UNEXPECTED.format(identifier=player_name, error=str(e))
        return format_response(error=error_msg)

def get_player_headshot_url(player_id: int) -> str:
    if not isinstance(player_id, int) or player_id <= 0:
        logger.error(f"Invalid player_id for headshot URL: {player_id}")
        raise ValueError(f"Invalid player ID provided for headshot: {player_id}")
    return f"{settings.HEADSHOT_BASE_URL}/{player_id}.png"
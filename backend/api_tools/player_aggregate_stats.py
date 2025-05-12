import logging
import json
from functools import lru_cache
from typing import Optional
from nba_api.stats.library.parameters import SeasonTypeAllStar
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)
from backend.utils.validation import _validate_season_format
from backend.api_tools.player_common_info import fetch_player_info_logic
from backend.api_tools.player_career_data import fetch_player_career_stats_logic, fetch_player_awards_logic
from backend.api_tools.player_gamelogs import fetch_player_gamelog_logic

logger = logging.getLogger(__name__)

@lru_cache(maxsize=128)
def fetch_player_stats_logic(player_name: str, season: Optional[str] = None, season_type: str = SeasonTypeAllStar.regular) -> str:
    effective_season = season if season is not None else settings.CURRENT_NBA_SEASON
    logger.info(f"Executing fetch_player_stats_logic for: '{player_name}', Season for Gamelog: {effective_season}, Type: {season_type}")

    if not _validate_season_format(effective_season): # Validate the season that will be used
        error_msg = Errors.INVALID_SEASON_FORMAT.format(season=effective_season)
        return format_response(error=error_msg)
    
    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        error_msg = Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5]))
        logger.warning(error_msg)
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name) 

        results_json = {}
        logic_functions_config = {
            "info_and_headlines": (fetch_player_info_logic, [player_actual_name]),
            "career": (fetch_player_career_stats_logic, [player_actual_name]),
            "gamelog_for_season": (fetch_player_gamelog_logic, [player_actual_name, effective_season, season_type]),
            "awards_history": (fetch_player_awards_logic, [player_actual_name])
        }

        for key, (func, args) in logic_functions_config.items():
            result_str = func(*args)
            try:
                data = json.loads(result_str)
                if "error" in data:
                    logger.error(f"Error from {key} logic for {player_actual_name}: {data['error']}")
                    return result_str 
                results_json[key] = data
            except json.JSONDecodeError as parse_error:
                logger.error(f"Failed to parse JSON from {key} logic for {player_actual_name}: {parse_error}. Response: {result_str}")
                return format_response(error=f"Failed to process internal {key} results for {player_actual_name}.")

        info_data = results_json.get("info_and_headlines", {})
        career_data = results_json.get("career", {})
        gamelog_data = results_json.get("gamelog_for_season", {})
        awards_data = results_json.get("awards_history", {})

        logger.info(f"fetch_player_stats_logic completed for '{player_actual_name}'")
        return format_response({
            "player_name": player_actual_name,
            "player_id": player_id,
            "season_requested_for_gamelog": effective_season,
            "season_type_requested_for_gamelog": season_type,
            "info": info_data.get("player_info", {}),
            "headline_stats": info_data.get("headline_stats", {}),
            "available_seasons": info_data.get("available_seasons", []), # Include available seasons
            "career_stats": {
                "season_totals_regular_season": career_data.get("season_totals_regular_season", []),
                "career_totals_regular_season": career_data.get("career_totals_regular_season", {}),
                "season_totals_post_season": career_data.get("season_totals_post_season", []),
                "career_totals_post_season": career_data.get("career_totals_post_season", {})
            },
            "season_gamelog": gamelog_data.get("gamelog", []),
            "awards": awards_data.get("awards", [])
        })

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_stats_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e: 
        logger.warning(f"ValueError in fetch_player_stats_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_stats_logic for '{player_name}': {e}", exc_info=True)
        error_msg = Errors.PLAYER_STATS_UNEXPECTED.format(identifier=player_name, error=str(e))
        return format_response(error=error_msg)
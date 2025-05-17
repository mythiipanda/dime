"""
Handles fetching and processing player career statistics and awards information.
"""
import logging
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import playercareerstats, playerawards
from nba_api.stats.library.parameters import PerModeDetailed, PerMode36
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)

logger = logging.getLogger(__name__)

# Cache sizes
PLAYER_CAREER_STATS_CACHE_SIZE = 256
PLAYER_AWARDS_CACHE_SIZE = 256

# Module-level constant for valid PerMode values for career stats
_VALID_PER_MODES_CAREER = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
_VALID_PER_MODES_CAREER.update({getattr(PerMode36, attr) for attr in dir(PerMode36) if not attr.startswith('_') and isinstance(getattr(PerMode36, attr), str)})

@lru_cache(maxsize=PLAYER_CAREER_STATS_CACHE_SIZE)
def fetch_player_career_stats_logic(player_name: str, per_mode: str = PerModeDetailed.per_game) -> str:
    """
    Fetches player career statistics including regular season and postseason totals.

    Args:
        player_name (str): The name or ID of the player.
        per_mode (str, optional): The statistical mode (e.g., "PerGame", "Totals", "Per36").
                                  Defaults to "PerGame".

    Returns:
        str: A JSON string containing player career statistics, or an error message.
             Successful response structure:
             {
                 "player_name": "Player Name",
                 "player_id": 12345,
                 "per_mode_requested": "PerModeValue",
                 "data_retrieved_mode": "PerModeValue",
                 "season_totals_regular_season": [ { ... stats ... } ],
                 "career_totals_regular_season": { ... stats ... },
                 "season_totals_post_season": [ { ... stats ... } ],
                 "career_totals_post_season": { ... stats ... }
             }
    """
    logger.info(f"Executing fetch_player_career_stats_logic for: '{player_name}', Requested PerMode: {per_mode}")

    if per_mode not in _VALID_PER_MODES_CAREER:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_VALID_PER_MODES_CAREER)[:5]))
        logger.warning(error_msg) # Removed "Defaulting to PerGame for API call." as we return error.
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching playercareerstats for ID: {player_id} (PerMode '{per_mode}' requested)")
        try:
            career_endpoint = playercareerstats.PlayerCareerStats(player_id=player_id, per_mode36=per_mode, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
            logger.debug(f"playercareerstats API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api playercareerstats failed for ID {player_id}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_CAREER_STATS_API.format(identifier=player_actual_name, error=str(api_error))
            return format_response(error=error_msg)

        season_totals_rs_df = career_endpoint.season_totals_regular_season.get_data_frame()
        career_totals_rs_df = career_endpoint.career_totals_regular_season.get_data_frame()
        season_totals_ps_df = career_endpoint.season_totals_post_season.get_data_frame()
        career_totals_ps_df = career_endpoint.career_totals_post_season.get_data_frame()

        season_totals_cols = [
            'SEASON_ID', 'TEAM_ID', 'TEAM_ABBREVIATION', 'PLAYER_AGE', 'GP', 'GS',
            'MIN', 'FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT', 'FTM',
            'FTA', 'FT_PCT', 'OREB', 'DREB', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'PF', 'PTS'
        ]
        
        available_season_cols_rs = [col for col in season_totals_cols if col in season_totals_rs_df.columns]
        season_totals_regular_season = _process_dataframe(season_totals_rs_df.loc[:, available_season_cols_rs] if not season_totals_rs_df.empty and available_season_cols_rs else pd.DataFrame(), single_row=False)
        career_totals_regular_season = _process_dataframe(career_totals_rs_df, single_row=True)

        available_season_cols_ps = [col for col in season_totals_cols if col in season_totals_ps_df.columns]
        season_totals_post_season = _process_dataframe(season_totals_ps_df.loc[:, available_season_cols_ps] if not season_totals_ps_df.empty and available_season_cols_ps else pd.DataFrame(), single_row=False)
        career_totals_post_season = _process_dataframe(career_totals_ps_df, single_row=True)

        if season_totals_regular_season is None or career_totals_regular_season is None:
            logger.error(f"DataFrame processing failed for regular season career stats of {player_actual_name}.")
            error_msg = Errors.PLAYER_CAREER_STATS_PROCESSING.format(identifier=player_actual_name)
            return format_response(error=error_msg)
        
        logger.info(f"fetch_player_career_stats_logic completed for '{player_actual_name}'")
        return format_response({
            "player_name": player_actual_name, "player_id": player_id,
            "per_mode_requested": per_mode, # This is the validated per_mode
            "data_retrieved_mode": per_mode, # API was called with the validated per_mode
            "season_totals_regular_season": season_totals_regular_season or [],
            "career_totals_regular_season": career_totals_regular_season or {},
            "season_totals_post_season": season_totals_post_season or [],
            "career_totals_post_season": career_totals_post_season or {}
        })
    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_career_stats_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_career_stats_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_career_stats_logic for '{player_name}': {e}", exc_info=True)
        error_msg = Errors.PLAYER_CAREER_STATS_UNEXPECTED.format(identifier=player_name, error=str(e))
        return format_response(error=error_msg)

@lru_cache(maxsize=PLAYER_AWARDS_CACHE_SIZE)
def fetch_player_awards_logic(player_name: str) -> str:
    """
    Fetches a list of awards received by the player.

    Args:
        player_name (str): The name or ID of the player.

    Returns:
        str: A JSON string containing a list of player awards, or an error message.
             Successful response structure:
             {
                 "player_name": "Player Name",
                 "player_id": 12345,
                 "awards": [ { ... award details ... }, ... ]
             }
    """
    logger.info(f"Executing fetch_player_awards_logic for: '{player_name}'")
    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching playerawards for ID: {player_id}")
        try:
            awards_endpoint = playerawards.PlayerAwards(player_id=player_id, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
            logger.debug(f"playerawards API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api playerawards failed for ID {player_id}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_AWARDS_API.format(identifier=player_actual_name, error=str(api_error))
            return format_response(error=error_msg)

        awards_list = _process_dataframe(awards_endpoint.player_awards.get_data_frame(), single_row=False)

        if awards_list is None: 
            logger.error(f"DataFrame processing failed for awards of {player_actual_name}.")
            error_msg = Errors.PLAYER_AWARDS_PROCESSING.format(identifier=player_actual_name)
            return format_response(error=error_msg)

        logger.info(f"fetch_player_awards_logic completed for '{player_actual_name}'")
        return format_response({
            "player_name": player_actual_name,
            "player_id": player_id,
            "awards": awards_list 
        })
    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_awards_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_awards_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_awards_logic for '{player_name}': {e}", exc_info=True)
        error_msg = Errors.PLAYER_AWARDS_UNEXPECTED.format(identifier=player_name, error=str(e))
        return format_response(error=error_msg)
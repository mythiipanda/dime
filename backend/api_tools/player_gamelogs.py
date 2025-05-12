import logging
from functools import lru_cache
import pandas as pd

from nba_api.stats.endpoints import playergamelog
from nba_api.stats.library.parameters import SeasonTypeAllStar
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)
from backend.utils.validation import _validate_season_format

logger = logging.getLogger(__name__)

@lru_cache(maxsize=256)
def fetch_player_gamelog_logic(player_name: str, season: str, season_type: str = SeasonTypeAllStar.regular) -> str:
    logger.info(f"Executing fetch_player_gamelog_logic for: '{player_name}', Season: {season}, Type: {season_type}")

    if not season or not _validate_season_format(season):
        error_msg = Errors.INVALID_SEASON_FORMAT.format(season=season)
        return format_response(error=error_msg)

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        error_msg = Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5])) # Show some options
        logger.warning(error_msg)
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching playergamelog for ID: {player_id}, Season: {season}, Type: {season_type}")
        try:
            gamelog_endpoint = playergamelog.PlayerGameLog(
                player_id=player_id, season=season, season_type_all_star=season_type, timeout=settings.DEFAULT_TIMEOUT_SECONDS
            )
            logger.debug(f"playergamelog API call successful for ID: {player_id}, Season: {season}")
        except Exception as api_error:
            logger.error(f"nba_api playergamelog failed for ID {player_id}, Season {season}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_GAMELOG_API.format(identifier=player_actual_name, season=season, error=str(api_error))
            return format_response(error=error_msg)

        gamelog_df = gamelog_endpoint.get_data_frames()[0]
        if gamelog_df.empty:
            logger.warning(f"No gamelog data found for {player_actual_name} ({season}, {season_type}).")
            return format_response({
                "player_name": player_actual_name, "player_id": player_id, "season": season,
                "season_type": season_type, "gamelog": []
            })

        gamelog_cols = [
            'GAME_ID', 'GAME_DATE', 'MATCHUP', 'WL', 'MIN', 'FGM', 'FGA', 'FG_PCT',
            'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT', 'OREB', 'DREB',
            'REB', 'AST', 'STL', 'BLK', 'TOV', 'PF', 'PTS', 'PLUS_MINUS',
            'VIDEO_AVAILABLE' # Added VIDEO_AVAILABLE
        ]
        available_gamelog_cols = [col for col in gamelog_cols if col in gamelog_df.columns]
        gamelog_list = _process_dataframe(gamelog_df.loc[:, available_gamelog_cols] if available_gamelog_cols else pd.DataFrame(), single_row=False)


        if gamelog_list is None:
            logger.error(f"DataFrame processing failed for gamelog of {player_actual_name} ({season}).")
            error_msg = Errors.PLAYER_GAMELOG_PROCESSING.format(identifier=player_actual_name, season=season)
            return format_response(error=error_msg)

        logger.info(f"fetch_player_gamelog_logic completed for '{player_actual_name}', Season: {season}")
        return format_response({
            "player_name": player_actual_name, "player_id": player_id, "season": season,
            "season_type": season_type, "gamelog": gamelog_list
        })
    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_gamelog_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_gamelog_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_gamelog_logic for '{player_name}', Season {season}: {e}", exc_info=True)
        error_msg = Errors.PLAYER_GAMELOG_UNEXPECTED.format(identifier=player_name, season=season, error=str(e))
        return format_response(error=error_msg)
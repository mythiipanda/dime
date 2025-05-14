import logging
from functools import lru_cache

from nba_api.stats.endpoints import playerestimatedmetrics
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import _process_dataframe, format_response
from backend.utils.validation import _validate_season_format

logger = logging.getLogger(__name__)

# Module-level constants for validation sets
_VALID_PEM_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}
_VALID_PEM_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}

@lru_cache(maxsize=settings.DEFAULT_LRU_CACHE_SIZE)
def fetch_player_estimated_metrics_logic(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches player estimated metrics (E_OFF_RATING, E_DEF_RATING, E_NET_RATING, etc.)
    for a given season and season type using nba_api's PlayerEstimatedMetrics endpoint.

    Args:
        season (str): NBA season in 'YYYY-YY' format (e.g., '2023-24').
        season_type (str): Season type (e.g., 'Regular Season', 'Playoffs').
        league_id (str): League ID (default: NBA '00').

    Returns:
        str: JSON-formatted string with estimated metrics or an error message.
    """
    logger.info(f"Executing fetch_player_estimated_metrics_logic for Season: {season}, Season Type: {season_type}, League ID: {league_id}")

    if not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if league_id not in _VALID_PEM_LEAGUE_IDS:
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_VALID_PEM_LEAGUE_IDS)[:3])))
    if season_type not in _VALID_PEM_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_PEM_SEASON_TYPES)[:5])))

    try:
        pem_endpoint = playerestimatedmetrics.PlayerEstimatedMetrics(
            league_id=league_id,
            season=season,
            season_type=season_type, # Corrected parameter name
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        
        metrics_df = pem_endpoint.player_estimated_metrics.get_data_frame()
        
        metrics_list = _process_dataframe(metrics_df, single_row=False)

        if metrics_list is None:
            logger.error(f"DataFrame processing failed for player estimated metrics (Season: {season}, Type: {season_type}).")
            error_msg = Errors.PROCESSING_ERROR.format(error="player estimated metrics data processing failed") # Generic processing error
            return format_response(error=error_msg)

        if metrics_df.empty:
            logger.warning(f"No player estimated metrics data found for Season: {season}, Type: {season_type}.")
            data_payload = []
        else:
            data_payload = metrics_list
            
        result = {
            "parameters": {
                "season": season,
                "season_type": season_type,
                "league_id": league_id
            },
            "player_estimated_metrics": data_payload
        }
        logger.info(f"Successfully fetched player estimated metrics for Season: {season}, Type: {season_type}")
        return format_response(data=result)

    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_estimated_metrics_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_estimated_metrics_logic for Season {season}, Type {season_type}: {e}", exc_info=True)
        # Using a more generic error message as specific ones for this endpoint don't exist yet
        error_msg = Errors.API_ERROR.format(error=f"fetching player estimated metrics: {str(e)}")
        return format_response(error=error_msg)
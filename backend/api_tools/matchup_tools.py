import json
import logging
from nba_api.stats.endpoints import LeagueSeasonMatchups, MatchupsRollup
from nba_api.stats.library.parameters import SeasonTypeAllStar
from backend.config import CURRENT_SEASON, DEFAULT_TIMEOUT
from backend.api_tools.utils import format_response

logger = logging.getLogger(__name__)

def fetch_league_season_matchups_logic(
    def_player_id: str,
    off_player_id: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    """
    Fetches season matchups between two players.
    Returns JSON string with matchups data.
    """
    logger.info(f"Fetching season matchups between Def {def_player_id} and Off {off_player_id} for {season}, type {season_type}")
    try:
        endpoint = LeagueSeasonMatchups(
            def_player_id_nullable=def_player_id or "",
            off_player_id_nullable=off_player_id or "",
            season=season,
            season_type_playoffs=season_type,
            timeout=DEFAULT_TIMEOUT
        )
        df = endpoint.season_matchups.get_data_frame()
        matchups = df.to_dict(orient="records")
        result = {
            "season": season,
            "season_type": season_type,
            "def_player_id": def_player_id,
            "off_player_id": off_player_id,
            "matchups": matchups
        }
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error fetching season matchups: {e}", exc_info=True)
        return format_response(error=str(e))

def fetch_matchups_rollup_logic(
    def_player_id: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    """
    Fetches matchup rollup for a defensive player across opponents.
    Returns JSON string with rollup data.
    """
    logger.info(f"Fetching matchup rollup for Def {def_player_id} in {season}, type {season_type}")
    try:
        endpoint = MatchupsRollup(
            def_player_id_nullable=def_player_id or "",
            season=season,
            season_type_playoffs=season_type,
            timeout=DEFAULT_TIMEOUT
        )
        df = endpoint.matchups_rollup.get_data_frame()
        rollup = df.to_dict(orient="records")
        result = {
            "season": season,
            "season_type": season_type,
            "def_player_id": def_player_id,
            "rollup": rollup
        }
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error fetching matchups rollup: {e}", exc_info=True)
        return format_response(error=str(e))

import json
import logging
from typing import Optional
from nba_api.stats.endpoints.synergyplaytypes import SynergyPlayTypes
from nba_api.stats.library.http import NBAStatsHTTP
from nba_api.stats.library.parameters import (
    LeagueID,
    PerModeSimple,
    PlayerOrTeamAbbreviation,
    SeasonTypeAllStar,
    Season,
    PlayTypeNullable,
    TypeGroupingNullable
)
from backend.config import CURRENT_SEASON, DEFAULT_TIMEOUT
from backend.api_tools.utils import format_response

logger = logging.getLogger(__name__)

def fetch_synergy_play_types_logic(
    league_id: str = LeagueID.nba,
    per_mode: str = PerModeSimple.default,
    player_or_team: str = PlayerOrTeamAbbreviation.default,
    season_type: str = SeasonTypeAllStar.regular,
    season: str = CURRENT_SEASON,
    play_type: Optional[str] = None,
    type_grouping: Optional[str] = None
) -> str:
    """
    Fetch synergy play types stats for team or player.
    """
    logger.info(
        f"Fetching Synergy play types: league_id={league_id}, per_mode={per_mode}, "
        f"player_or_team={player_or_team}, season_type={season_type}, season={season}, "
        f"play_type={play_type}, type_grouping={type_grouping}"
    )
    # Build parameter map for direct API request
    params = {
        "LeagueID": league_id,
        "PerMode": per_mode,
        "PlayerOrTeam": player_or_team,
        "SeasonType": season_type,
        "SeasonYear": season,
        "PlayType": play_type or "",
        "TypeGrouping": type_grouping or ""
    }
    try:
        client = NBAStatsHTTP()
        response = client.send_api_request(endpoint="synergyplaytypes", parameters=params, timeout=DEFAULT_TIMEOUT)
        return response.get_response()
    except Exception as e:
        logger.error("Synergy API call failed: %s", e, exc_info=True)
        return format_response(error=str(e))

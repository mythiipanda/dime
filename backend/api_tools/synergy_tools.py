import json
import logging
from typing import Optional
from nba_api.stats.endpoints.synergyplaytypes import SynergyPlayTypes
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
    try:
        endpoint = SynergyPlayTypes(
            league_id=league_id,
            per_mode_simple=per_mode,
            player_or_team_abbreviation=player_or_team,
            season_type_all_star=season_type,
            season=season,
            play_type_nullable=play_type or PlayTypeNullable.default,
            type_grouping_nullable=type_grouping or TypeGroupingNullable.default,
            timeout=DEFAULT_TIMEOUT
        )
        df = endpoint.synergy_play_type.get_data_frame()
        data = df.to_dict(orient="records")
        result = {
            "league_id": league_id,
            "per_mode": per_mode,
            "player_or_team": player_or_team,
            "season_type": season_type,
            "season": season,
            "play_type": play_type,
            "type_grouping": type_grouping,
            "data": data
        }
        return json.dumps(result)
    except Exception as e:
        logger.error("Error fetching synergy play types: %s", e, exc_info=True)
        return format_response(error=str(e))

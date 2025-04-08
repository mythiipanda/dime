from fastapi import APIRouter, HTTPException
import json
import logging

from ..schemas import FetchRequest
from ..api_tools.player_tools import fetch_player_info_logic, fetch_player_gamelog_logic, fetch_player_career_stats_logic
from ..api_tools.team_tools import fetch_team_info_and_roster_logic
from ..api_tools.game_tools import fetch_league_games_logic
from nba_api.stats.library.parameters import PerMode36, SeasonTypeAllStar
from ..config import SUPPORTED_FETCH_TARGETS

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/fetch_data")
async def fetch_data(request: FetchRequest):
    target = request.target
    params = request.params
    logger.debug(f"Received /fetch_data request for target: {target}, params: {params}")
    tool_result_json = None

    if target not in SUPPORTED_FETCH_TARGETS:
        raise HTTPException(status_code=400, detail=f"Unsupported target '{target}'.")

    try:
        if target == "player_info":
            player_name = params.get("player_name")
            if not player_name:
                raise HTTPException(status_code=400, detail="Missing 'player_name'.")
            tool_result_json = fetch_player_info_logic(player_name)

        elif target == "player_gamelog":
            player_name = params.get("player_name")
            season = params.get("season")
            if not player_name or not season:
                raise HTTPException(status_code=400, detail="Missing 'player_name' or 'season'.")
            season_type = params.get("season_type", SeasonTypeAllStar.regular)
            tool_result_json = fetch_player_gamelog_logic(player_name, season, season_type)

        elif target == "team_info":
            team_identifier = params.get("team_identifier")
            if not team_identifier:
                raise HTTPException(status_code=400, detail="Missing 'team_identifier'.")
            season = params.get("season")
            tool_result_json = fetch_team_info_and_roster_logic(team_identifier, season)

        elif target == "player_career_stats":
            player_name = params.get("player_name")
            if not player_name:
                raise HTTPException(status_code=400, detail="Missing 'player_name'.")
            per_mode36 = params.get("per_mode36", PerMode36.per_game)
            tool_result_json = fetch_player_career_stats_logic(player_name, per_mode36)

        elif target == "find_games":
            player_or_team = params.get("player_or_team")
            player_id = params.get("player_id")
            team_id = params.get("team_id")
            date_from = params.get("date_from")
            date_to = params.get("date_to")
            if not player_or_team or player_or_team not in ['P', 'T']:
                raise HTTPException(status_code=400, detail="Missing or invalid 'player_or_team'.")
            if player_or_team == 'P' and player_id is None:
                raise HTTPException(status_code=400, detail="Missing 'player_id'.")
            if player_or_team == 'T' and team_id is None:
                raise HTTPException(status_code=400, detail="Missing 'team_id'.")
            tool_result_json = fetch_league_games_logic(
                player_or_team_abbreviation=player_or_team,
                player_id_nullable=player_id,
                team_id_nullable=team_id,
                season_nullable=None,
                season_type_nullable=None,
                league_id_nullable=None,
                date_from_nullable=date_from,
                date_to_nullable=date_to
            )

        if tool_result_json:
            try:
                tool_data = json.loads(tool_result_json)
                if isinstance(tool_data, dict):
                    if 'error' in tool_data:
                        error_message = tool_data['error']
                        raise HTTPException(status_code=500, detail=error_message)
                    return tool_data
                else:
                    raise HTTPException(status_code=500, detail="Unexpected data structure.")
            except json.JSONDecodeError:
                raise HTTPException(status_code=500, detail="Invalid JSON returned from tool.")
        else:
            raise HTTPException(status_code=500, detail="Tool returned no data.")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during /fetch_data for target={target}")
        raise HTTPException(status_code=500, detail=f"Data fetching error: {str(e)}")
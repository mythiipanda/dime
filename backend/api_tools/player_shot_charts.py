import logging
import os
from functools import lru_cache

from nba_api.stats.endpoints import shotchartdetail
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
from backend.api_tools.visualization import create_shotchart

logger = logging.getLogger(__name__)

# Module-level constant for valid season types
_VALID_SHOTCHART_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}

@lru_cache(maxsize=128)
def fetch_player_shotchart_logic(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    logger.info(f"Executing fetch_player_shotchart_logic for: '{player_name}', Season: {season}, Type: {season_type}")

    if not season or not _validate_season_format(season):
        error_msg = Errors.INVALID_SEASON_FORMAT.format(season=season)
        return format_response(error=error_msg)
    
    if season_type not in _VALID_SHOTCHART_SEASON_TYPES:
        error_msg = Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_SHOTCHART_SEASON_TYPES)[:5]))
        logger.warning(error_msg)
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching shotchartdetail for ID: {player_id}, Season: {season}, Type: {season_type}")
        try:
            shotchart_endpoint = shotchartdetail.ShotChartDetail(
                player_id=player_id, team_id=0, season_nullable=season,
                season_type_all_star=season_type, timeout=settings.DEFAULT_TIMEOUT_SECONDS, context_measure_simple='FGA'
            )
            logger.debug(f"shotchartdetail API call successful for ID: {player_id}")
            shots_df = shotchart_endpoint.shot_chart_detail.get_data_frame()
            league_avg_df = shotchart_endpoint.league_averages.get_data_frame()
        except Exception as api_error:
            logger.error(f"nba_api shotchartdetail failed for ID {player_id}, Season {season}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_SHOTCHART_API.format(identifier=player_actual_name, season=season, error=str(api_error))
            return format_response(error=error_msg)

        shots_data_list = _process_dataframe(shots_df, single_row=False)
        league_averages_list = _process_dataframe(league_avg_df, single_row=False)

        if shots_data_list is None or league_averages_list is None:
            logger.error(f"DataFrame processing failed for shot chart of {player_actual_name} (Season: {season})")
            error_msg = Errors.PLAYER_SHOTCHART_PROCESSING.format(identifier=player_actual_name, season=season)
            return format_response(error=error_msg)

        if not shots_data_list: 
            logger.warning(f"No shot data found for {player_actual_name} ({season}, {season_type}).")
            return format_response({
                "player_name": player_actual_name, "player_id": player_id, "season": season, "season_type": season_type,
                "overall_stats": {"total_shots": 0, "made_shots": 0, "field_goal_percentage": 0.0},
                "zone_breakdown": {}, "shot_data_summary": [], "league_averages": league_averages_list or [],
                "visualization_path": None, "visualization_error": None,
                "message": "No shot data found for the specified criteria."
            })

        zone_summary = {}
        total_shots = len(shots_data_list)
        made_shots = sum(1 for shot in shots_data_list if shot.get("SHOT_MADE_FLAG") == 1)

        for shot in shots_data_list:
            zone = shot.get("SHOT_ZONE_BASIC", "Unknown")
            if zone not in zone_summary:
                zone_summary[zone] = {"attempts": 0, "made": 0, "percentage": 0.0}
            zone_summary[zone]["attempts"] += 1
            if shot.get("SHOT_MADE_FLAG") == 1:
                zone_summary[zone]["made"] += 1
        for zone_stats in zone_summary.values():
            zone_stats["percentage"] = round(zone_stats["made"] / zone_stats["attempts"] * 100, 1) if zone_stats["attempts"] > 0 else 0.0

        overall_stats_for_viz = {
            "total_shots": total_shots, "made_shots": made_shots,
            "field_goal_percentage": round(made_shots / total_shots * 100, 1) if total_shots > 0 else 0.0
        }
        shot_summary_for_viz = { 
            "player_name": player_actual_name, "player_id": player_id, "season": season, "season_type": season_type,
            "overall_stats": overall_stats_for_viz, "zone_breakdown": zone_summary,
            "shot_locations": [{"x": s.get("LOC_X"), "y": s.get("LOC_Y"), "made": s.get("SHOT_MADE_FLAG") == 1, "zone": s.get("SHOT_ZONE_BASIC")} for s in shots_data_list]
        }

        visualization_path, visualization_error = None, None
        project_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(project_backend_dir, "output")
        
        try:
            os.makedirs(output_dir, exist_ok=True)
            visualization_path = create_shotchart(shot_summary_for_viz, output_dir)
            logger.info(f"Shot chart visualization created at: {visualization_path}")
        except Exception as viz_error:
            logger.error(f"Failed to create shot chart visualization for {player_actual_name}: {viz_error}", exc_info=True)
            visualization_error = str(viz_error)

        response_summary = {
            "player_name": player_actual_name, "player_id": player_id, "season": season, "season_type": season_type,
            "overall_stats": overall_stats_for_viz, "zone_breakdown": zone_summary,
            "shot_data_summary": shots_data_list, 
            "league_averages": league_averages_list or [],
            "visualization_path": visualization_path, "visualization_error": visualization_error
        }
        logger.info(f"fetch_player_shotchart_logic completed for '{player_actual_name}'")
        return format_response(response_summary)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_shotchart_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_shotchart_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_shotchart_logic for '{player_name}', Season {season}: {e}", exc_info=True)
        error_msg = Errors.PLAYER_SHOTCHART_UNEXPECTED.format(identifier=player_name, season=season, error=str(e))
        return format_response(error=error_msg)
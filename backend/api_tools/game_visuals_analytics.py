"""
Handles fetching game-level visual and analytical data, specifically
game-wide shot charts and win probability play-by-play.
"""
import logging
from functools import lru_cache
import pandas as pd
from typing import Set # For type hinting _VALID_WP_RUN_TYPES

from nba_api.stats.endpoints import (
    shotchartdetail,
    WinProbabilityPBP
)
from nba_api.stats.library.parameters import RunType
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response
)
from backend.utils.validation import validate_game_id_format

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
GAME_SHOTCHART_CACHE_SIZE = 64
GAME_WIN_PROB_CACHE_SIZE = 64
SHOTCHART_CONTEXT_MEASURE_GAME = "FGA"

_VALID_WP_RUN_TYPES: Set[str] = {"each play", "each second", "each poss"}

# --- Logic Functions ---
@lru_cache(maxsize=GAME_SHOTCHART_CACHE_SIZE)
def fetch_shotchart_logic(game_id: str) -> str:
    """
    Fetches shot chart data for all players in a specific NBA game.
    Data is sourced from the nba_api's ShotChartDetail endpoint.

    Args:
        game_id (str): NBA game ID (10-digit string).

    Returns:
        str: JSON-formatted string containing shot chart data grouped by team and league averages, or an error message.

    Notes:
        - Returns an error if the game_id is empty or invalid.
        - Returns an empty list for teams if no shot data is found.
        - Each shot includes player, period, time, type, made/missed, coordinates, and event info.
    """
    logger.info(f"Executing fetch_shotchart_logic for game ID: {game_id}")

    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)
    if not validate_game_id_format(game_id):
        return format_response(error=Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id))

    try:
        shotchart_endpoint = shotchartdetail.ShotChartDetail(
            game_id_nullable=game_id, team_id=0, player_id=0, # team_id=0 and player_id=0 for game-wide chart
            context_measure_simple=SHOTCHART_CONTEXT_MEASURE_GAME, season_nullable=None, # Season not needed for game-specific chart
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug(f"shotchartdetail API call successful for game {game_id}")

        shots_df = shotchart_endpoint.shot_chart_detail.get_data_frame()
        league_avg_df = shotchart_endpoint.league_averages.get_data_frame()

        shots_list = _process_dataframe(shots_df, single_row=False)
        league_avgs_list = _process_dataframe(league_avg_df, single_row=False)

        if shots_list is None or league_avgs_list is None:
            if shots_df.empty:
                logger.warning(f"No shot chart data found for game {game_id} from API.")
                return format_response({"game_id": game_id, "teams": [], "league_averages": league_avgs_list or []})
            else:
                logger.error(f"DataFrame processing failed for shot chart of game {game_id}")
                error_msg = Errors.SHOTCHART_PROCESSING.format(game_id=game_id)
                return format_response(error=error_msg)
        
        if not shots_list:
             logger.warning(f"No shot data processed for game {game_id}.")
             return format_response({"game_id": game_id, "teams": [], "league_averages": league_avgs_list or []})

        teams_data = {}
        for shot_item in shots_list:
            team_id_shot = shot_item.get("TEAM_ID")
            if team_id_shot is None: continue
            if team_id_shot not in teams_data:
                teams_data[team_id_shot] = {"team_name": shot_item.get("TEAM_NAME"), "team_id": team_id_shot, "shots": []}
            
            teams_data[team_id_shot]["shots"].append({
                "player": {"id": shot_item.get("PLAYER_ID"), "name": shot_item.get("PLAYER_NAME")},
                "period": shot_item.get("PERIOD"),
                "time_remaining": f"{shot_item.get('MINUTES_REMAINING', 0)}:{str(shot_item.get('SECONDS_REMAINING', 0)).zfill(2)}",
                "shot_type": shot_item.get("SHOT_TYPE"),
                "made": shot_item.get("SHOT_MADE_FLAG") == 1,
                "coordinates": {"x": shot_item.get("LOC_X"), "y": shot_item.get("LOC_Y")},
                "action_type": shot_item.get("ACTION_TYPE"),
                "shot_zone_basic": shot_item.get("SHOT_ZONE_BASIC"),
                "shot_zone_area": shot_item.get("SHOT_ZONE_AREA"),
                "shot_zone_range": shot_item.get("SHOT_ZONE_RANGE"),
                "shot_distance": shot_item.get("SHOT_DISTANCE"),
                "event_num": shot_item.get("GAME_EVENT_ID")
            })

        result = {"game_id": game_id, "teams": list(teams_data.values()), "league_averages": league_avgs_list or []}
        logger.info(f"fetch_shotchart_logic completed for game {game_id}")
        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching shot chart for game {game_id}: {str(e)}", exc_info=True)
        error_msg = Errors.SHOTCHART_API.format(game_id=game_id, error=str(e))
        return format_response(error=error_msg)

@lru_cache(maxsize=GAME_WIN_PROB_CACHE_SIZE)
def fetch_win_probability_logic(game_id: str, run_type: str = RunType.default) -> str:
    """
    Fetches win probability data for a specific NBA game.
    Data is sourced from the nba_api's WinProbabilityPBP endpoint.

    Args:
        game_id (str): NBA game ID (10-digit string).
        run_type (str): Run type for win probability calculation (e.g., 'each play', 'each second', 'each poss').

    Returns:
        str: JSON-formatted string containing game info and win probability PBP data, or an error message.

    Notes:
        - Returns an error if the game_id is empty or invalid, or if run_type is not supported.
        - Filters out win probability rows with missing EVENT_NUM.
        - Returns empty lists if no valid data is found.
    """
    logger.info(f"Executing fetch_win_probability_logic for game {game_id}, RunType: {run_type}")
    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)
    if not validate_game_id_format(game_id):
        return format_response(error=Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id))

    if run_type not in _VALID_WP_RUN_TYPES:
        return format_response(error=Errors.INVALID_RUN_TYPE.format(value=run_type, options=", ".join(list(_VALID_WP_RUN_TYPES)[:5])))

    try:
        wp_endpoint = WinProbabilityPBP(game_id=game_id, run_type=run_type, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
        logger.debug(f"WinProbabilityPBP API call successful for {game_id}")

        game_info_dict = _process_dataframe(wp_endpoint.game_info.get_data_frame(), single_row=True)
        
        win_prob_df = wp_endpoint.win_prob_p_bp.get_data_frame()
        win_probs_list = [] # Default to empty list
        if not win_prob_df.empty:
            if 'EVENT_NUM' in win_prob_df.columns:
                # Filter out rows where EVENT_NUM might be NaN or None, ensuring they are actual PBP events
                win_prob_df_filtered = win_prob_df[pd.notna(win_prob_df['EVENT_NUM'])]
                if not win_prob_df_filtered.empty:
                    win_probs_list = _process_dataframe(win_prob_df_filtered, single_row=False)
                else:
                    logger.warning(f"Win probability PBP data for game {game_id} had EVENT_NUM column but all values were NaN/None.")
            else:
                logger.warning(f"Win probability PBP data for game {game_id} is missing EVENT_NUM column. Data: {win_prob_df.head().to_dict()}")
        
        # Check if essential data processing failed or resulted in None for critical parts
        # game_info_dict can be {} if no game_info, win_probs_list can be [] if no valid PBP events
        if game_info_dict is None: # _process_dataframe failed for game_info
            logger.error(f"DataFrame processing failed for game_info of win probability for game {game_id}.")
            error_msg = Errors.PROCESSING_ERROR.format(error=f"game_info for win probability data for game {game_id}")
            return format_response(error=error_msg)        
        result = {"game_id": game_id, "game_info": game_info_dict or {}, "win_probability": win_probs_list or []}
        logger.info(f"Successfully fetched win probability for game {game_id}")
        return format_response(result)
    except Exception as e:
        logger.error(f"Error fetching win probability for {game_id}: {e}", exc_info=True)
        error_msg = Errors.WINPROBABILITY_API.format(game_id=game_id, error=str(e))
        return format_response(error=error_msg)
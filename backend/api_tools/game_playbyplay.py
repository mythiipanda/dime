import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import re
import pandas as pd
from functools import lru_cache

from nba_api.stats.endpoints import playbyplayv3 # Changed to V3
from nba_api.live.nba.endpoints import PlayByPlay as LivePlayByPlay
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response
)
from backend.utils.validation import validate_game_id_format

logger = logging.getLogger(__name__)

# --- Helper Functions ---

# _get_event_type is no longer needed as V3 provides actionType and subType
# _determine_team_from_tricode was unused and has been removed.

# --- Play-by-Play Functions ---

def _fetch_historical_playbyplay_logic(game_id: str, start_period: int = 0, end_period: int = 0) -> Dict[str, Any]:
    logger.info(f"Executing _fetch_historical_playbyplay_logic (V3) for game ID: {game_id}, periods {start_period}-{end_period}")
    pbp_endpoint = playbyplayv3.PlayByPlayV3( # Using V3
        game_id=game_id, start_period=start_period, end_period=end_period, timeout=settings.DEFAULT_TIMEOUT_SECONDS
    )
    pbp_df = pbp_endpoint.play_by_play.get_data_frame() # V3 uses camelCase
    video_df = pbp_endpoint.available_video.get_data_frame() # V3 uses camelCase 'videoAvailable'

    processed_plays = _process_dataframe(pbp_df, single_row=False)
    if processed_plays is None:
        if pbp_df.empty:
            logger.warning(f"No historical PBP data found for game {game_id} via API (V3).")
            processed_plays = []
        else:
            raise ValueError(f"Failed to process non-empty historical PBP (V3) DataFrame for game {game_id}")

    # V3 PBP actions include teamId and teamTricode for the team performing the action.
    # The live PBP logic uses game-level team info to determine home/away for actions.
    # For historical V3, we directly use the teamTricode provided with each action.

    periods_data = {}
    for play_item in processed_plays: # play_item keys are now camelCase
        period_num = play_item.get("period", 0)
        if period_num not in periods_data: periods_data[period_num] = []
        
        # V3 provides scoreHome and scoreAway
        score_home_v3 = play_item.get('scoreHome')
        score_away_v3 = play_item.get('scoreAway')
        score_str_v3 = f"{score_home_v3}-{score_away_v3}" if score_home_v3 is not None and score_away_v3 is not None else None

        # Historical V3 `description` is the main text. 
        # `teamTricode` in the action item refers to the team that performed the action.

        formatted_play = {
            "event_num": play_item.get("actionNumber"),
            "clock": play_item.get("clock", "").replace("PT", "").replace("M", ":").replace("S", "").split(".")[0], # Format PT11M58.00S to 11:58
            "score": score_str_v3,
            "team_tricode": play_item.get("teamTricode"), # Team performing action
            "person_id": play_item.get("personId"),
            "player_name": play_item.get("playerNameI"), # Or playerName
            "description": play_item.get("description"), # Main description
            "action_type": play_item.get("actionType"),
            "sub_type": play_item.get("subType"),
            "event_type": f"{play_item.get('actionType', '').upper()}_{play_item.get('subType', '').upper()}",
            "video_available": play_item.get("videoAvailable", False) # V3 has this per play
        }
        # Period filtering is handled by the API call parameters for V3
        periods_data[period_num].append(formatted_play)

    periods_list_final = [{"period": p_num, "plays": plays_list} for p_num, plays_list in sorted(periods_data.items())]
    # V3 AvailableVideo dataset also uses camelCase 'videoAvailable'
    has_overall_video = bool(video_df.iloc[0]['videoAvailable'] == 1) if not video_df.empty and 'videoAvailable' in video_df.columns else False

    return {
        "game_id": game_id, "has_video": has_overall_video, "source": "historical_v3",
        "filtered_periods": {"start": start_period, "end": end_period} if start_period > 0 or end_period > 0 else None,
        "periods": periods_list_final
    }

def _fetch_live_playbyplay_logic(game_id: str) -> Dict[str, Any]:
    logger.info(f"Executing _fetch_live_playbyplay_logic for game ID: {game_id}")
    live_pbp_endpoint = LivePlayByPlay(game_id=game_id)
    live_data_dict = live_pbp_endpoint.get_dict()
    raw_actions_list = live_data_dict.get('game', {}).get('actions', [])

    if not raw_actions_list:
        logger.warning(f"No live actions found for game {game_id}. Game might not be live or recently concluded.")
        raise ValueError("No live actions found, game may not be live.")

    periods_data = {}
    game_details_dict = live_data_dict.get('game', {})
    home_team_id_live = game_details_dict.get('homeTeam', {}).get('teamId')
    away_team_id_live = game_details_dict.get('awayTeam', {}).get('teamId')

    for action_item in raw_actions_list:
        period_num = action_item.get("period", 0)
        if period_num not in periods_data: periods_data[period_num] = []

        clock_raw_str = action_item.get("clock", "")
        match_obj = re.match(r"PT(\d+)M(\d+\.?\d*)S", clock_raw_str)
        clock_formatted_str = f"{match_obj.group(1)}:{match_obj.group(2).split('.')[0].zfill(2)}" if match_obj else clock_raw_str
        
        score_home = action_item.get('scoreHome')
        score_away = action_item.get('scoreAway')
        score_str_live = f"{score_home}-{score_away}" if score_home is not None and score_away is not None else None
        
        action_team_id_live = action_item.get('teamId')
        team_str_live = "home" if action_team_id_live == home_team_id_live else "away" if action_team_id_live == away_team_id_live else "neutral"

        formatted_play = {
            "event_num": action_item.get("actionNumber"), "clock": clock_formatted_str,
            "score": score_str_live, "team": team_str_live, # home, away, or neutral
            "description": action_item.get("description"), # Renamed from neutral_description
            "person_id": action_item.get("personId"),
            "player_name": action_item.get("playerNameI") or action_item.get("playerName"), # Prefer playerNameI if available
            "action_type": action_item.get("actionType"),
            "sub_type": action_item.get("subType"),
            "event_type": f"{action_item.get('actionType', '').upper()}_{action_item.get('subType', '').upper()}"
        }
        periods_data[period_num].append(formatted_play)

    periods_list_final = [{"period": p_num, "plays": plays_list} for p_num, plays_list in sorted(periods_data.items())]
    return {
        "game_id": game_id, "has_video": False, "source": "live",
        "filtered_periods": None,
        "periods": periods_list_final
    }

@lru_cache(maxsize=64)
def fetch_playbyplay_logic(game_id: str, start_period: int = 0, end_period: int = 0) -> str:
    logger.info(f"Executing fetch_playbyplay_logic for game ID: {game_id}, StartPeriod: {start_period}, EndPeriod: {end_period}")
    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)
    if not validate_game_id_format(game_id):
        return format_response(error=Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id))

    # If specific periods are requested, directly fetch historical data as live PBP typically doesn't support period filtering.
    if start_period != 0 or end_period != 0:
        logger.info(f"Period filters active ({start_period}-{end_period}), fetching historical PBP directly for game {game_id}.")
        try:
            result_dict = _fetch_historical_playbyplay_logic(game_id, start_period, end_period)
            logger.info(f"Historical PBP fetch successful for game {game_id} with period filters.")
            result_dict["parameters"] = {"start_period": start_period, "end_period": end_period, "note": "Filtered historical data."}
            return format_response(data=result_dict)
        except Exception as hist_fetch_error:
            logger.error(f"Historical PBP fetch failed for game {game_id} (with period filters): {hist_fetch_error}", exc_info=True)
            error_msg = Errors.PLAYBYPLAY_API.format(game_id=game_id, error=str(hist_fetch_error))
            return format_response(error=error_msg)
    else:
        # No period filters, attempt live PBP first, then fallback to historical.
        try:
            logger.debug(f"Attempting live PBP fetch for game {game_id} (no period filters).")
            result_dict = _fetch_live_playbyplay_logic(game_id)
            logger.info(f"Live PBP fetch successful for game {game_id}.")
            result_dict["parameters"] = {"start_period": 0, "end_period": 0, "note": "Live data; period filters not applied."}
            return format_response(data=result_dict)
        except ValueError as live_fetch_error: # Raised by _fetch_live_playbyplay_logic if no live actions
            logger.warning(f"Live PBP fetch failed for game {game_id} ({live_fetch_error}), attempting historical (no period filters).")
            try:
                result_dict = _fetch_historical_playbyplay_logic(game_id, 0, 0) # Fetch all periods for historical
                logger.info(f"Historical PBP fetch successful for game {game_id} (fallback).")
                result_dict["parameters"] = {"start_period": 0, "end_period": 0, "note": "Full historical data after live fallback."}
                return format_response(data=result_dict)
            except Exception as hist_fetch_error:
                logger.error(f"Historical PBP fetch (fallback) also failed for game {game_id}: {hist_fetch_error}", exc_info=True)
                error_msg = Errors.PLAYBYPLAY_API.format(game_id=game_id, error=str(hist_fetch_error))
                return format_response(error=error_msg)
        except Exception as e: # Catch other unexpected errors during the live attempt phase
            logger.error(f"Unexpected error during initial live PBP fetch attempt for game {game_id}: {e}", exc_info=True)
            error_msg = Errors.PLAYBYPLAY_API.format(game_id=game_id, error=str(e))
            return format_response(error=error_msg)
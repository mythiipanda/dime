import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import re # For parsing live clock
import pandas as pd
from functools import lru_cache
from nba_api.stats.endpoints import (
    playbyplay,
    shotchartdetail,
    leaguegamefinder,
    BoxScoreAdvancedV3,
    BoxScoreTraditionalV3,
    BoxScoreFourFactorsV3,
    BoxScoreUsageV3,
    BoxScoreDefensiveV2,
    WinProbabilityPBP
    # commonplayerinfo, playerdashptreb, playerdashptpass are not directly used here
)
from nba_api.live.nba.endpoints import PlayByPlay as LivePlayByPlay
from backend.config import DEFAULT_TIMEOUT, Errors, CURRENT_SEASON # CURRENT_SEASON not directly used here, but good for context
from nba_api.stats.library.parameters import EndPeriod, EndRange, RangeType, StartPeriod, StartRange, LeagueID, SeasonTypeAllStar
from backend.api_tools.utils import (
    _process_dataframe,
    format_response,
    # find_player_id_or_error, PlayerNotFoundError are not directly used here
    _validate_season_format,
    validate_date_format,
    validate_game_id_format
)

logger = logging.getLogger(__name__)

# --- Helper Functions ---

def _determine_play_team(row: Dict[str, Any]) -> str:
    """Helper function to determine which team the play belongs to for historical PBP."""
    if row.get("HOMEDESCRIPTION") is not None and row.get("VISITORDESCRIPTION") is None:
        return "home"
    elif row.get("VISITORDESCRIPTION") is not None and row.get("HOMEDESCRIPTION") is None:
        return "away"
    else:
        return "neutral"

def _get_event_type(event_code: Optional[int]) -> str:
    """Helper function to map historical PBP event codes to readable descriptions."""
    if event_code is None:
        return "UNKNOWN"
    event_types = {
        1: "FIELD_GOAL_MADE", 2: "FIELD_GOAL_MISSED", 3: "FREE_THROW",
        4: "REBOUND", 5: "TURNOVER", 6: "FOUL", 7: "VIOLATION",
        8: "SUBSTITUTION", 9: "TIMEOUT", 10: "JUMP_BALL", 11: "EJECTION",
        12: "START_PERIOD", 13: "END_PERIOD", 18: "INSTANT_REPLAY", 20: "STOPPAGE"
    }
    return event_types.get(event_code, "OTHER")

# --- Box Score Functions ---

@lru_cache(maxsize=128)
def fetch_boxscore_traditional_logic(
    game_id: str,
    start_period: int = StartPeriod.default, # Typically 0 for all
    end_period: int = EndPeriod.default,     # Typically 0 for all
    start_range: int = StartRange.default,   # Typically 0 for all
    end_range: int = EndRange.default,     # Typically 0 for all
    range_type: int = RangeType.default      # Typically 0 for all
) -> str:
    """
    Fetches detailed traditional box score data (V3) for a specific game,
    allowing filtering by period and/or time range within periods.

    Args:
        game_id (str): The 10-digit ID of the NBA game (e.g., "0022300161").
        start_period (int, optional): Start period filter (1-4 for quarters, 5+ for OT). Defaults to 0 (all periods).
        end_period (int, optional): End period filter. Defaults to 0 (all periods).
        start_range (int, optional): Start of time range in seconds from the start of the period (e.g., 0). Defaults to 0.
        end_range (int, optional): End of time range in seconds from the start of the period (e.g., 72000 for full game). Defaults to 0.
        range_type (int, optional): Type of range. Defaults to 0.

    Returns:
        str: JSON string containing traditional box score statistics.
             Expected dictionary structure passed to format_response:
             {
                 "game_id": str,
                 "parameters": {
                     "start_period": int, "end_period": int, "start_range": int, "end_range": int, "range_type": int,
                     "note": "Using BoxScoreTraditionalV3"
                 },
                 "teams": [ // List of team-level stats
                     {"gameId": str, "teamId": int, "teamName": str, "minutes": str, "fieldGoalsMade": int, ...}, ...
                 ],
                 "players": [ // List of player-level stats
                     {"gameId": str, "teamId": int, "personId": int, "firstName": str, "familyName": str, "minutes": str, "points": int, ...}, ...
                 ],
                 "starters_bench": [ // List of stats aggregated by starters vs. bench for each team
                     {"gameId": str, "teamId": int, "period": str, "startersBench": str ("Starters" or "Bench"), "points": int, ...}, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.info(f"Executing fetch_boxscore_traditional_logic (V3) for game ID: {game_id} with period filters {start_period}-{end_period}")

    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)
    if not validate_game_id_format(game_id):
        return format_response(error=Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id))

    try:
        boxscore = BoxScoreTraditionalV3(
            game_id=game_id, start_period=start_period, end_period=end_period,
            start_range=start_range, end_range=end_range, range_type=range_type,
            timeout=DEFAULT_TIMEOUT
        )
        logger.debug(f"BoxScoreTraditionalV3 API call successful for {game_id}")

        player_stats = _process_dataframe(boxscore.player_stats.get_data_frame(), single_row=False)
        team_stats = _process_dataframe(boxscore.team_stats.get_data_frame(), single_row=False)
        starters_bench_stats = _process_dataframe(boxscore.team_starter_bench_stats.get_data_frame(), single_row=False)

        if player_stats is None or team_stats is None or starters_bench_stats is None:
            logger.error(f"DataFrame processing failed for traditional boxscore of game {game_id}.")
            error_msg = Errors.PROCESSING_ERROR.format(error=f"traditional boxscore data for game {game_id}")
            return format_response(error=error_msg)

        result = {
            "game_id": game_id,
            "parameters": {
                "start_period": start_period, "end_period": end_period,
                "start_range": start_range, "end_range": end_range,
                "range_type": range_type, "note": "Using BoxScoreTraditionalV3"
            },
            "teams": team_stats or [],
            "players": player_stats or [],
            "starters_bench": starters_bench_stats or []
        }
        logger.info(f"fetch_boxscore_traditional_logic (V3) completed for game {game_id}")
        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching traditional boxscore (V3) for game {game_id}: {str(e)}", exc_info=True)
        error_msg = Errors.BOXSCORE_API.format(game_id=game_id, error=str(e))
        return format_response(error=error_msg)

@lru_cache(maxsize=128)
def fetch_boxscore_advanced_logic(game_id: str, end_period: int = 0, end_range: int = 0, start_period: int = 0, start_range: int = 0) -> str:
    """
    Fetches advanced box score data (V3) for a specific game, including metrics like Offensive/Defensive Rating, Pace, etc.
    Optionally filters by period or time range within periods.

    Args:
        game_id (str): The 10-digit ID of the NBA game (e.g., "0022300076").
        end_period (int, optional): End period filter (1-4 for quarters, 5+ for OT). Defaults to 0 (all periods).
        end_range (int, optional): End of time range in seconds from the start of the period. Defaults to 0.
        start_period (int, optional): Start period filter. Defaults to 0 (all periods).
        start_range (int, optional): Start of time range in seconds from the start of the period. Defaults to 0.

    Returns:
        str: JSON string containing advanced player and team stats.
             Expected dictionary structure passed to format_response:
             {
                 "game_id": str,
                 "parameters": {"start_period": int, "end_period": int, "start_range": int, "end_range": int},
                 "player_stats": [
                     {"gameId": str, "teamId": int, "personId": int, "firstName": str, "familyName": str, "minutes": str,
                      "offensiveRating": Optional[float], "defensiveRating": Optional[float], "netRating": Optional[float],
                      "assistPercentage": Optional[float], "assistToTurnover": Optional[float], "assistRatio": Optional[float],
                      "offensiveReboundPercentage": Optional[float], "defensiveReboundPercentage": Optional[float],
                      "reboundPercentage": Optional[float], "teamTurnoverPercentage": Optional[float], "effectiveFieldGoalPercentage": Optional[float],
                      "trueShootingPercentage": Optional[float], "usagePercentage": Optional[float], "pace": Optional[float],
                      "possessions": Optional[float], ...}, ...
                 ],
                 "team_stats": [
                     {"gameId": str, "teamId": int, "teamName": str, "minutes": str, "offensiveRating": Optional[float],
                      "defensiveRating": Optional[float], "netRating": Optional[float], ...}, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.info(f"Executing fetch_boxscore_advanced_logic (V3) for game ID: {game_id}")
    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)
    if not validate_game_id_format(game_id):
        return format_response(error=Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id))

    try:
        boxscore_adv = BoxScoreAdvancedV3(
            game_id=game_id, end_period=end_period, end_range=end_range,
            start_period=start_period, start_range=start_range, timeout=DEFAULT_TIMEOUT
        )
        logger.debug(f"BoxScoreAdvancedV3 API call successful for {game_id}")

        player_stats = _process_dataframe(boxscore_adv.player_stats.get_data_frame(), single_row=False)
        team_stats = _process_dataframe(boxscore_adv.team_stats.get_data_frame(), single_row=False)

        if player_stats is None or team_stats is None:
            logger.error(f"DataFrame processing failed for advanced boxscore of game {game_id}.")
            error_msg = Errors.PROCESSING_ERROR.format(error=f"advanced boxscore data for game {game_id}")
            return format_response(error=error_msg)

        result = {
            "game_id": game_id,
            "parameters": {"start_period": start_period, "end_period": end_period, "start_range": start_range, "end_range": end_range},
            "player_stats": player_stats or [],
            "team_stats": team_stats or []
        }
        logger.info(f"Successfully fetched advanced box score V3 for game {game_id}")
        return format_response(data=result)

    except IndexError as ie: # Can occur if API returns unexpected structure for certain games/filters
        logger.warning(f"IndexError during BoxScoreAdvancedV3 processing for game {game_id}: {ie}. Data likely unavailable.", exc_info=False)
        error_msg = Errors.DATA_NOT_FOUND + f" (Advanced box score data might be unavailable for game {game_id} with current filters)"
        return format_response(error=error_msg)
    except Exception as e:
        logger.error(f"Error during fetch_boxscore_advanced_logic for game {game_id}: {str(e)}", exc_info=True)
        error_msg = Errors.BOXSCORE_ADVANCED_API.format(game_id=game_id, error=str(e))
        return format_response(error=error_msg)

@lru_cache(maxsize=128)
def fetch_boxscore_four_factors_logic(
    game_id: str,
    start_period: int = 0,
    end_period: int = 0
) -> str:
    """
    Fetches box score Four Factors (V3) for a specific game, optionally filtered by periods.
    Four Factors: Effective FG%, Turnover %, Offensive Rebound %, Free Throw Rate.

    Args:
        game_id (str): The 10-digit ID of the NBA game (e.g., "0022300161").
        start_period (int, optional): Start period filter (1-4 for quarters, 5+ for OT). Defaults to 0 (all periods).
        end_period (int, optional): End period filter. Defaults to 0 (all periods).

    Returns:
        str: JSON string containing Four Factors box score data.
             Expected dictionary structure passed to format_response:
             {
                 "game_id": str,
                 "parameters": {"start_period": int, "end_period": int},
                 "player_stats": [
                     {"gameId": str, "teamId": int, "personId": int, "firstName": str, "familyName": str, "minutes": str,
                      "effectiveFieldGoalPercentage": Optional[float], "freeThrowAttemptRate": Optional[float],
                      "teamTurnoverPercentage": Optional[float], "offensiveReboundPercentage": Optional[float],
                      "opponentEffectiveFieldGoalPercentage": Optional[float], ...}, ...
                 ],
                 "team_stats": [
                     {"gameId": str, "teamId": int, "teamName": str, "minutes": str, "effectiveFieldGoalPercentage": Optional[float], ...}, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.info(f"Executing fetch_boxscore_four_factors_logic for game ID: {game_id}, periods {start_period}-{end_period}")

    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)
    if not validate_game_id_format(game_id):
        return format_response(error=Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id))

    try:
        boxscore = BoxScoreFourFactorsV3(
            game_id=game_id, start_period=start_period, end_period=end_period, timeout=DEFAULT_TIMEOUT
        )
        logger.debug(f"BoxScoreFourFactorsV3 API call successful for {game_id}")

        player_stats = _process_dataframe(boxscore.player_stats.get_data_frame(), single_row=False)
        team_stats = _process_dataframe(boxscore.team_stats.get_data_frame(), single_row=False)

        if player_stats is None or team_stats is None:
            logger.error(f"DataFrame processing failed for four factors boxscore of game {game_id}.")
            error_msg = Errors.PROCESSING_ERROR.format(error=f"four factors boxscore data for game {game_id}")
            return format_response(error=error_msg)

        result = {
            "game_id": game_id,
            "parameters": {"start_period": start_period, "end_period": end_period},
            "player_stats": player_stats or [],
            "team_stats": team_stats or []
        }
        logger.info(f"Successfully fetched four factors box score for game {game_id}")
        return format_response(result)

    except Exception as e:
        logger.error(f"Error in fetch_boxscore_four_factors_logic for game {game_id}: {str(e)}", exc_info=True)
        error_msg = Errors.BOXSCORE_FOURFACTORS_API.format(game_id=game_id, error=str(e))
        return format_response(error=error_msg)

@lru_cache(maxsize=128)
def fetch_boxscore_usage_logic(game_id: str) -> str:
    """
    Fetches box score usage statistics (V3) for a specific game, detailing player involvement when on the court.

    Args:
        game_id (str): The 10-digit ID of the NBA game (e.g., "0022300161").

    Returns:
        str: JSON string containing usage statistics for each player.
             Expected dictionary structure passed to format_response:
             {
                 "game_id": str,
                 "usage_stats": [
                     {"gameId": str, "teamId": int, "personId": int, "firstName": str, "familyName": str, "minutes": str,
                      "usagePercentage": Optional[float], "percentageFieldGoalsMade": Optional[float],
                      "percentageFieldGoalsAttempted": Optional[float], "percentageThreePointersMade": Optional[float],
                      "percentageThreePointersAttempted": Optional[float], "percentageFreeThrowsMade": Optional[float],
                      "percentageFreeThrowsAttempted": Optional[float], "percentageReboundsOffensive": Optional[float],
                      "percentageReboundsDefensive": Optional[float], "percentageReboundsTotal": Optional[float],
                      "percentageAssists": Optional[float], "percentageTurnovers": Optional[float],
                      "percentageSteals": Optional[float], "percentageBlocks": Optional[float],
                      "percentageBlocksAllowed": Optional[float], "percentagePersonalFouls": Optional[float],
                      "percentagePersonalFoulsDrawn": Optional[float], "percentagePoints": Optional[float]}, ...
                 ]
             }
             Returns {"usage_stats": []} if no data is found.
             Or an {'error': 'Error message'} object if a more significant issue occurs.
    """
    logger.info(f"Executing fetch_boxscore_usage_logic for game {game_id}")
    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)
    if not validate_game_id_format(game_id):
        return format_response(error=Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id))

    try:
        usage_endpoint = BoxScoreUsageV3(game_id=game_id, timeout=DEFAULT_TIMEOUT)
        usage_df = usage_endpoint.player_stats.get_data_frame()

        if usage_df.empty:
            logger.warning(f"No usage stats found for game {game_id} from API.")
            return format_response({"game_id": game_id, "usage_stats": []})

        usage_stats_list = _process_dataframe(usage_df, single_row=False)

        if usage_stats_list is None: # Should not happen if df was not empty, but defensive check
            logger.error(f"DataFrame processing failed for usage boxscore of game {game_id} despite non-empty API response.")
            error_msg = Errors.PROCESSING_ERROR.format(error=f"usage boxscore data for game {game_id}")
            return format_response(error=error_msg)

        result = {"game_id": game_id, "usage_stats": usage_stats_list}
        logger.info(f"Successfully fetched usage stats for game {game_id}")
        return format_response(result)
    except Exception as e:
        logger.error(f"Error fetching usage stats for {game_id}: {e}", exc_info=True)
        error_msg = Errors.BOXSCORE_USAGE_API.format(game_id=game_id, error=str(e))
        return format_response(error=error_msg)

@lru_cache(maxsize=128)
def fetch_boxscore_defensive_logic(game_id: str) -> str:
    """
    Fetches box score defensive statistics (V2) for a specific game, including matchup data.

    Args:
        game_id (str): The 10-digit ID of the NBA game (e.g., "0022300161").

    Returns:
        str: JSON string containing defensive statistics for each player.
             Expected dictionary structure passed to format_response:
             {
                 "game_id": str,
                 "defensive_stats": [
                     {"gameId": str, "teamId": int, "personId": int, "firstName": str, "familyName": str,
                      "comment": Optional[str], "jerseyNum": Optional[str], "matchupMinutes": Optional[str],
                      "partialPossessions": Optional[float], "switchesOn": Optional[int], "playerPoints": Optional[int],
                      "defensiveRebounds": Optional[int], "matchupAssists": Optional[int], "matchupTurnovers": Optional[int],
                      "steals": Optional[int], "blocks": Optional[int], "matchupFieldGoalsMade": Optional[int],
                      "matchupFieldGoalsAttempted": Optional[int], "matchupFieldGoalPercentage": Optional[float],
                      "matchupThreePointersMade": Optional[int], "matchupThreePointersAttempted": Optional[int],
                      "matchupThreePointerPercentage": Optional[float]}, ...
                 ]
             }
             Returns {"defensive_stats": []} if no data is found.
             Or an {'error': 'Error message'} object if a more significant issue occurs.
    """
    logger.info(f"Executing fetch_boxscore_defensive_logic for game {game_id}")
    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)
    if not validate_game_id_format(game_id):
        return format_response(error=Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id))

    try:
        defensive_endpoint = BoxScoreDefensiveV2(game_id=game_id, timeout=DEFAULT_TIMEOUT)
        defensive_df = defensive_endpoint.player_stats.get_data_frame()

        if defensive_df.empty:
            logger.warning(f"No defensive stats found for game {game_id} from API.")
            return format_response({"game_id": game_id, "defensive_stats": []})

        defensive_stats_list = _process_dataframe(defensive_df, single_row=False)

        if defensive_stats_list is None:
            logger.error(f"DataFrame processing failed for defensive boxscore of game {game_id} despite non-empty API response.")
            error_msg = Errors.PROCESSING_ERROR.format(error=f"defensive boxscore data for game {game_id}")
            return format_response(error=error_msg)

        result = {"game_id": game_id, "defensive_stats": defensive_stats_list}
        logger.info(f"Successfully fetched defensive stats for game {game_id}")
        return format_response(result)
    except Exception as e:
        logger.error(f"Error fetching defensive stats for {game_id}: {e}", exc_info=True)
        error_msg = Errors.BOXSCORE_DEFENSIVE_API.format(game_id=game_id, error=str(e))
        return format_response(error=error_msg)

# --- Play-by-Play Functions ---

def _fetch_historical_playbyplay_logic(game_id: str, start_period: int = 0, end_period: int = 0) -> Dict[str, Any]:
    """
    Internal helper to fetch and process play-by-play data for completed games.

    Args:
        game_id (str): The 10-digit ID of the game.
        start_period (int): Starting period filter.
        end_period (int): Ending period filter.

    Returns:
        Dict[str, Any]: Processed play-by-play data.
    
    Raises:
        Exception: If API call or processing fails.
    """
    logger.info(f"Executing _fetch_historical_playbyplay_logic for game ID: {game_id}, periods {start_period}-{end_period}")
    pbp_endpoint = playbyplay.PlayByPlay(
        game_id=game_id, start_period=start_period, end_period=end_period, timeout=DEFAULT_TIMEOUT
    )
    pbp_df = pbp_endpoint.play_by_play.get_data_frame()
    video_df = pbp_endpoint.available_video.get_data_frame()

    processed_plays = _process_dataframe(pbp_df, single_row=False)
    if processed_plays is None:
        if pbp_df.empty:
            logger.warning(f"No historical PBP data found for game {game_id} via API.")
            processed_plays = [] # Treat as empty if API returns no data
        else:
            raise ValueError(f"Failed to process non-empty historical PBP DataFrame for game {game_id}")

    periods_data = {}
    for play_item in processed_plays:
        period_num = play_item.get("PERIOD", 0)
        if period_num not in periods_data: periods_data[period_num] = []
        formatted_play = {
            "event_num": play_item.get("EVENTNUM"), "clock": play_item.get("PCTIMESTRING", ""),
            "score": play_item.get("SCORE"), "team": _determine_play_team(play_item),
            "home_description": play_item.get("HOMEDESCRIPTION"), "away_description": play_item.get("VISITORDESCRIPTION"),
            "neutral_description": play_item.get("NEUTRALDESCRIPTION"),
            "event_type": _get_event_type(play_item.get("EVENTMSGTYPE"))
        }
        # Apply period filtering if specified (though API should handle it, this is a safeguard)
        if (start_period == 0 and end_period == 0) or (start_period <= period_num <= end_period):
            periods_data[period_num].append(formatted_play)

    periods_list_final = [{"period": p_num, "plays": plays_list} for p_num, plays_list in sorted(periods_data.items())]
    has_video_available = bool(video_df.iloc[0][0] == 1) if not video_df.empty else False

    return {
        "game_id": game_id, "has_video": has_video_available, "source": "historical",
        "filtered_periods": {"start": start_period, "end": end_period} if start_period > 0 or end_period > 0 else None,
        "periods": periods_list_final
    }

def _fetch_live_playbyplay_logic(game_id: str) -> Dict[str, Any]:
    """
    Internal helper to fetch and process play-by-play data for potentially live games.

    Args:
        game_id (str): The 10-digit ID of the game.

    Returns:
        Dict[str, Any]: Processed live play-by-play data.

    Raises:
        ValueError: If no live actions are found (indicating game might not be live or recently finished).
        Exception: If API call or processing fails.
    """
    logger.info(f"Executing _fetch_live_playbyplay_logic for game ID: {game_id}")
    live_pbp_endpoint = LivePlayByPlay(game_id=game_id) # Live API might not have timeout
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

        clock_raw_str = action_item.get("clock", "") # Format: "PT05M12.3S"
        match_obj = re.match(r"PT(\d+)M(\d+\.?\d*)S", clock_raw_str)
        clock_formatted_str = f"{match_obj.group(1)}:{match_obj.group(2).split('.')[0].zfill(2)}" if match_obj else clock_raw_str
        
        score_home = action_item.get('scoreHome')
        score_away = action_item.get('scoreAway')
        score_str_live = f"{score_home}-{score_away}" if score_home is not None and score_away is not None else None
        
        action_team_id_live = action_item.get('teamId')
        team_str_live = "home" if action_team_id_live == home_team_id_live else "away" if action_team_id_live == away_team_id_live else "neutral"

        formatted_play = {
            "event_num": action_item.get("actionNumber"), "clock": clock_formatted_str,
            "score": score_str_live, "team": team_str_live,
            "neutral_description": action_item.get("description"), # Live PBP often uses a single description field
            "event_type": f"{action_item.get('actionType', '').upper()}_{action_item.get('subType', '').upper()}"
        }
        periods_data[period_num].append(formatted_play)

    periods_list_final = [{"period": p_num, "plays": plays_list} for p_num, plays_list in sorted(periods_data.items())]
    return {
        "game_id": game_id, "has_video": False, "source": "live", # Live PBP typically doesn't indicate video availability
        "filtered_periods": None, # Period filtering is not applied to live fetches
        "periods": periods_list_final
    }

@lru_cache(maxsize=64)
def fetch_playbyplay_logic(game_id: str, start_period: int = 0, end_period: int = 0) -> str:
    """
    Fetches play-by-play data for a specific game. It first attempts to get live data.
    If live data retrieval fails (e.g., game is not live or recently finished),
    it falls back to fetching historical play-by-play data.
    Period filtering (start_period, end_period) only applies to the historical data fallback.

    Args:
        game_id (str): The 10-digit ID of the NBA game (e.g., "0022300161").
        start_period (int, optional): Starting period filter (1-4 for quarters, 5+ for OT).
                                     Defaults to 0 (all periods). Applies only to historical fallback.
        end_period (int, optional): Ending period filter. Defaults to 0 (all periods).
                                    Applies only to historical fallback.

    Returns:
        str: JSON string containing play-by-play data.
             Expected dictionary structure passed to format_response:
             {
                 "game_id": str,
                 "source": str ("live" or "historical"),
                 "has_video": bool, // Indicates if video is available for historical plays
                 "parameters": {"start_period": int, "end_period": int, "note": Optional[str]},
                 "periods": [
                     {
                         "period": int,
                         "plays": [ // List of play objects
                             {"event_num": int, "clock": str, "score": Optional[str], "team": str ("home", "away", "neutral"),
                              "home_description": Optional[str], // For historical
                              "away_description": Optional[str], // For historical
                              "neutral_description": Optional[str], // For live, or historical if applicable
                              "event_type": str (e.g., "FIELD_GOAL_MADE", "TIMEOUT_REGULAR")}, ...
                         ]
                     }, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.info(f"Executing fetch_playbyplay_logic for game ID: {game_id}, StartPeriod: {start_period}, EndPeriod: {end_period}")
    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)
    if not validate_game_id_format(game_id):
        return format_response(error=Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id))

    try:
        logger.debug(f"Attempting live PBP fetch for game {game_id}")
        result_dict = _fetch_live_playbyplay_logic(game_id)
        logger.info(f"Live PBP fetch successful for game {game_id}")
        result_dict["parameters"] = {"start_period": 0, "end_period": 0, "note": "Period filter not applicable for live data."}
        return format_response(data=result_dict)
    except ValueError as live_fetch_error: # Specific error from _fetch_live_playbyplay_logic if no live actions
        logger.warning(f"Live PBP fetch failed for game {game_id} ({live_fetch_error}), attempting historical.")
        try:
            result_dict = _fetch_historical_playbyplay_logic(game_id, start_period, end_period)
            logger.info(f"Historical PBP fetch successful for game {game_id}")
            result_dict["parameters"] = {"start_period": start_period, "end_period": end_period}
            return format_response(data=result_dict)
        except Exception as hist_fetch_error:
            logger.error(f"Historical PBP fetch also failed for game {game_id}: {hist_fetch_error}", exc_info=True)
            error_msg = Errors.PLAYBYPLAY_API.format(game_id=game_id, error=str(hist_fetch_error))
            return format_response(error=error_msg)
    except Exception as e: # Catch any other unexpected errors during the initial live attempt
        logger.error(f"Unexpected error during initial live PBP fetch attempt for game {game_id}: {e}", exc_info=True)
        error_msg = Errors.PLAYBYPLAY_API.format(game_id=game_id, error=str(e)) # Generic PBP API error
        return format_response(error=error_msg)

@lru_cache(maxsize=64)
def fetch_shotchart_logic(game_id: str) -> str:
    """
    Fetches shot chart data for all players in a specific game.

    Args:
        game_id (str): The 10-digit ID of the NBA game (e.g., "0022300161").

    Returns:
        str: JSON string containing shot chart information for the game.
             Expected dictionary structure passed to format_response:
             {
                 "game_id": str,
                 "teams": [ // List of teams, each with their players' shots
                     {
                         "team_name": str,
                         "team_id": int,
                         "shots": [
                             {
                                 "player": {"id": int, "name": str},
                                 "period": int, "time_remaining": str (MM:SS), "shot_type": str,
                                 "made": bool, "coordinates": {"x": int, "y": int},
                                 "action_type": str, "shot_zone_basic": str, "shot_zone_area": str, "shot_zone_range": str,
                                 "shot_distance": int, "event_num": int
                             }, ...
                         ]
                     }, ...
                 ],
                 "league_averages": [ // League average shooting percentages by zone
                     {"GRID_TYPE": str, "SHOT_ZONE_BASIC": str, "SHOT_ZONE_AREA": str, "SHOT_ZONE_RANGE": str,
                      "FGM": int, "FGA": int, "FG_PCT": float}, ...
                 ]
             }
             Returns {"teams": [], "league_averages": []} if no shot data is found.
             Or an {'error': 'Error message'} object if a more significant issue occurs.
    """
    logger.info(f"Executing fetch_shotchart_logic for game ID: {game_id}")

    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)
    if not validate_game_id_format(game_id):
        return format_response(error=Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id))

    try:
        shotchart_endpoint = shotchartdetail.ShotChartDetail(
            game_id_nullable=game_id, team_id=0, player_id=0, # team_id=0 and player_id=0 fetches for all players in the game
            context_measure_simple="FGA", season_nullable=None, # Game specific, no season needed
            timeout=DEFAULT_TIMEOUT
        )
        logger.debug(f"shotchartdetail API call successful for game {game_id}")

        shots_df = shotchart_endpoint.shot_chart_detail.get_data_frame()
        league_avg_df = shotchart_endpoint.league_averages.get_data_frame()

        shots_list = _process_dataframe(shots_df, single_row=False)
        league_avgs_list = _process_dataframe(league_avg_df, single_row=False)

        if shots_list is None or league_avgs_list is None: # Check for processing error
            if shots_df.empty: # If API returned no shots, it's not a processing error per se
                logger.warning(f"No shot chart data found for game {game_id} from API.")
                return format_response({"game_id": game_id, "teams": [], "league_averages": league_avgs_list or []})
            else: # Processing failed on non-empty data
                logger.error(f"DataFrame processing failed for shot chart of game {game_id}")
                error_msg = Errors.SHOTCHART_PROCESSING.format(game_id=game_id)
                return format_response(error=error_msg)
        
        if not shots_list: # If processing was fine but list is empty (e.g. no shots in game, rare)
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
                "event_num": shot_item.get("GAME_EVENT_ID") # GAME_EVENT_ID is often the event number
            })

        result = {"game_id": game_id, "teams": list(teams_data.values()), "league_averages": league_avgs_list or []}
        logger.info(f"fetch_shotchart_logic completed for game {game_id}")
        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching shot chart for game {game_id}: {str(e)}", exc_info=True)
        error_msg = Errors.SHOTCHART_API.format(game_id=game_id, error=str(e))
        return format_response(error=error_msg)

@lru_cache(maxsize=32)
def fetch_league_games_logic(
    player_or_team_abbreviation: str = 'T',
    player_id_nullable: Optional[int] = None,
    team_id_nullable: Optional[int] = None,
    season_nullable: Optional[str] = None,
    season_type_nullable: Optional[str] = None, # e.g., SeasonTypeAllStar.regular
    league_id_nullable: Optional[str] = LeagueID.nba, # Default to NBA
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None
) -> str:
    """
    Fetches league games based on various filters like player, team, season, date range, or league.

    Args:
        player_or_team_abbreviation (str, optional): Specifies search by 'P' (Player) or 'T' (Team).
                                                     Valid values: "P", "T". Defaults to 'T'.
        player_id_nullable (Optional[int], optional): Player ID to filter games for. Required if `player_or_team_abbreviation` is 'P'.
        team_id_nullable (Optional[int], optional): Team ID to filter games for.
        season_nullable (Optional[str], optional): Season identifier in YYYY-YY format (e.g., "2023-24").
        season_type_nullable (Optional[str], optional): Type of season. Valid values from `SeasonTypeAllStar`
                                                        (e.g., "Regular Season", "Playoffs", "Pre Season", "All Star").
        league_id_nullable (Optional[str], optional): League ID. Valid values from `LeagueID` (e.g., "00" for NBA, "10" for WNBA, "20" for G-League).
                                                      Defaults to "00" (NBA).
        date_from_nullable (Optional[str], optional): Start date for game search range, in YYYY-MM-DD format.
        date_to_nullable (Optional[str], optional): End date for game search range, in YYYY-MM-DD format.

    Returns:
        str: JSON string containing a list of games matching the criteria.
             Expected dictionary structure passed to format_response:
             {
                 "games": [
                     {
                         "SEASON_ID": str, "TEAM_ID": Optional[int], "PLAYER_ID": Optional[int], "GAME_ID": str,
                         "GAME_DATE": str (YYYY-MM-DD), "MATCHUP": str (e.g., "LAL @ GSW"), "WL": Optional[str] ("W" or "L"),
                         "MIN": Optional[int], "PTS": Optional[int], "FGM": Optional[int], "FGA": Optional[int], "FG_PCT": Optional[float],
                         // ... many other stats depending on whether it's player or team game log data
                         "GAME_DATE_FORMATTED": str (YYYY-MM-DD) // Added for consistent date formatting
                     }, ...
                 ]
             }
             Returns {"games": []} if no games are found.
             Or an {'error': 'Error message'} object if an issue occurs.
             Note: Queries using only date ranges without other specific filters (like team/player/season)
             can be unreliable or very broad due to external API behavior.
    """
    logger.info(f"Executing fetch_league_games_logic with P/T: {player_or_team_abbreviation}, TeamID: {team_id_nullable}, PlayerID: {player_id_nullable}, Season: {season_nullable}, League: {league_id_nullable}")

    if player_or_team_abbreviation not in ['P', 'T']:
        return format_response(error=Errors.INVALID_PLAYER_TEAM_ABBREVIATION.format(value=player_or_team_abbreviation))
    if player_or_team_abbreviation == 'P' and player_id_nullable is None:
        return format_response(error=Errors.PLAYER_ID_REQUIRED_FOR_PLAYER_SEARCH)
    # team_id is not strictly required if other filters like season or date range are provided for a league-wide search.

    if season_nullable and not _validate_season_format(season_nullable):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season_nullable))
    if date_from_nullable and not validate_date_format(date_from_nullable):
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from_nullable))
    if date_to_nullable and not validate_date_format(date_to_nullable):
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to_nullable))
    
    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str) and attr != 'default'} # Exclude 'default' if it's not a valid API string
    if season_type_nullable is not None and season_type_nullable not in VALID_SEASON_TYPES and season_type_nullable != SeasonTypeAllStar.default : # Allow default value
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type_nullable, options=", ".join(VALID_SEASON_TYPES)))

    VALID_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}
    if league_id_nullable is not None and league_id_nullable not in VALID_LEAGUE_IDS:
         return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id_nullable, options=", ".join(VALID_LEAGUE_IDS)))


    try:
        game_finder_endpoint = leaguegamefinder.LeagueGameFinder(
            player_or_team_abbreviation=player_or_team_abbreviation,
            player_id_nullable=player_id_nullable,
            team_id_nullable=team_id_nullable,
            season_nullable=season_nullable,
            season_type_nullable=season_type_nullable,
            league_id_nullable=league_id_nullable,
            date_from_nullable=date_from_nullable,
            date_to_nullable=date_to_nullable,
            timeout=DEFAULT_TIMEOUT
        )
        logger.debug("leaguegamefinder API call successful.")
        games_df = game_finder_endpoint.league_game_finder_results.get_data_frame()

        if games_df.empty:
            logger.warning("No league games found for the specified filters.")
            return format_response({"games": []})

        # Limit broad league-wide results if no specific player, team, or season is provided
        # This helps prevent excessively large responses for very general queries.
        is_broad_query = all(param is None for param in [player_id_nullable, team_id_nullable, season_nullable]) and \
                         (date_from_nullable is not None or date_to_nullable is not None)
        
        if is_broad_query and len(games_df) > 200: # Arbitrary limit for broad date-only queries
             logger.info(f"Limiting broad league game list (date-filtered) to the top 200 games. Original count: {len(games_df)}")
             games_df = games_df.head(200)
        elif all(param is None for param in [player_id_nullable, team_id_nullable, season_nullable, season_type_nullable, date_from_nullable, date_to_nullable]) and len(games_df) > 200:
             # Limit very general queries (no filters at all)
             logger.info(f"Limiting very general league game list to the top 200 games. Original count: {len(games_df)}")
             games_df = games_df.head(200)


        games_list = _process_dataframe(games_df, single_row=False)
        if games_list is None:
            logger.error("Failed to process league games DataFrame.")
            return format_response(error=Errors.PROCESSING_ERROR.format(error="league games data"))

        for game_item in games_list: # Ensure consistent date formatting
            if 'GAME_DATE' in game_item and isinstance(game_item['GAME_DATE'], str):
                try:
                    # API returns date like "2023-10-24T00:00:00", we only need YYYY-MM-DD
                    parsed_date = datetime.strptime(game_item['GAME_DATE'].split('T')[0], '%Y-%m-%d')
                    game_item['GAME_DATE_FORMATTED'] = parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    game_item['GAME_DATE_FORMATTED'] = game_item['GAME_DATE'] # Fallback if parsing fails

        result = {"games": games_list}
        logger.info(f"fetch_league_games_logic found {len(games_list)} games matching criteria.")
        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching league games: {str(e)}", exc_info=True)
        error_msg = Errors.LEAGUE_GAMES_API.format(error=str(e))
        return format_response(error=error_msg)

@lru_cache(maxsize=64)
def fetch_win_probability_logic(game_id: str, run_type: str = "0") -> str: # run_type default is "0" from nba_api
    """
    Fetches win probability data points throughout a specific game.

    Args:
        game_id (str): The 10-digit ID of the NBA game (e.g., "0022300161").
        run_type (str, optional): Type of run for probability calculation. Defaults to "0" (standard).
                                  Refer to `nba_api.stats.library.parameters.RunType` for other potential values if needed.

    Returns:
        str: JSON string containing win probability data.
             Expected dictionary structure passed to format_response:
             {
                 "game_id": str,
                 "game_info": { // Basic game details from GameInfo dataset
                     "GAME_ID": str, "GAME_DATE": str, "HOME_TEAM_ID": int, "VISITOR_TEAM_ID": int, ...
                 },
                 "win_probability": [ // List of play-by-play events with associated win probabilities
                     {
                         "GAME_ID": str, "EVENT_NUM": int, "HOME_PCT": float, "VISITOR_PCT": float,
                         "HOME_PTS": int, "VISITOR_PTS": int, "DESCRIPTION": Optional[str],
                         "PCTIMESTRING": str, "PERIOD": int, ...
                     }, ...
                 ]
             }
             Returns empty game_info/win_probability if no data is found.
             Or an {'error': 'Error message'} object if a more significant issue occurs.
    """
    logger.info(f"Executing fetch_win_probability_logic for game {game_id}, RunType: {run_type}")
    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)
    if not validate_game_id_format(game_id):
        return format_response(error=Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id))

    try:
        wp_endpoint = WinProbabilityPBP(game_id=game_id, run_type=run_type, timeout=DEFAULT_TIMEOUT)
        logger.debug(f"WinProbabilityPBP API call successful for {game_id}")

        game_info_dict = _process_dataframe(wp_endpoint.game_info.get_data_frame(), single_row=True)
        win_probs_list = _process_dataframe(wp_endpoint.win_prob_p_bp.get_data_frame(), single_row=False)

        if game_info_dict is None or win_probs_list is None: # Check for processing error
            # Check if data was empty from API vs. processing failure
            if wp_endpoint.game_info.get_data_frame().empty and wp_endpoint.win_prob_p_bp.get_data_frame().empty:
                logger.warning(f"No win probability data found for game {game_id} from API.")
                return format_response({"game_id": game_id, "game_info": {}, "win_probability": []})
            else: # Processing failed on non-empty data
                logger.error(f"DataFrame processing failed for win probability of game {game_id}.")
                error_msg = Errors.PROCESSING_ERROR.format(error=f"win probability data for game {game_id}")
                return format_response(error=error_msg)
        
        result = {"game_id": game_id, "game_info": game_info_dict or {}, "win_probability": win_probs_list or []}
        logger.info(f"Successfully fetched win probability for game {game_id}")
        return format_response(result)
    except Exception as e:
        logger.error(f"Error fetching win probability for {game_id}: {e}", exc_info=True)
        error_msg = Errors.WINPROBABILITY_API.format(game_id=game_id, error=str(e))
        return format_response(error=error_msg)
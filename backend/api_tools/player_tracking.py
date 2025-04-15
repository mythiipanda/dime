"""
Enhanced player tracking API tools with comprehensive stats handling.
"""
import logging
import json
from typing import Dict, List, Optional, TypedDict, Union, Any

from nba_api.stats.endpoints import (
    commonplayerinfo,
    playerdashboardbyclutch,
    playerdashboardbyshootingsplits,
    playerdashptreb,
    playerdashptpass,
    playerdashptshots
)
from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID
from backend.config import DEFAULT_TIMEOUT, HEADSHOT_BASE_URL, ErrorMessages, CURRENT_SEASON
from backend.api_tools.utils import _process_dataframe, _validate_season_format, format_response
from backend.api_tools.player_tools import _find_player_id

logger = logging.getLogger(__name__)

class PlayerInfo(TypedDict):
    """Player basic information type."""
    person_id: int
    first_name: str
    last_name: str
    full_name: str
    position: str
    height: str
    weight: str
    jersey: str
    team_id: int
    team_name: str
    from_year: int
    to_year: int
    draft_year: str
    draft_position: str

class ReboundingStats(TypedDict):
    """Player rebounding statistics type."""
    total: int
    offensive: int
    defensive: int
    contested: int
    uncontested: int
    contested_pct: float
    frequency: Dict[str, float]
    by_shot_type: List[Dict]
    by_distance: List[Dict]

class PassingStats(TypedDict):
    """Player passing statistics type."""
    passes_made: List[Dict]
    passes_received: List[Dict]
    ast: int
    potential_ast: int
    ast_points: int
    frequency: Dict[str, float]

class ShootingStats(TypedDict):
    """Player shooting statistics type."""
    fga: int
    fgm: int
    fg_pct: float
    fg3a: int
    fg3m: int
    fg3_pct: float
    efg_pct: float
    by_shot_clock: List[Dict]
    by_dribble_count: List[Dict]
    by_touch_time: List[Dict]
    by_defender_distance: List[Dict]

def fetch_player_info_logic(player_name: str) -> str:
    """
    Fetch detailed player information.
    
    Args:
        player_name (str): Player's name
        
    Returns:
        str: JSON string containing:
        {
            "info": {basic player info},
            "headline_stats": {current season averages},
            "available_seasons": [list of seasons]
        }
    """
    logger.info(f"Executing fetch_player_info_logic for player: {player_name}")
    
    if not player_name:
        return json.dumps({"error": ErrorMessages.MISSING_REQUIRED_PARAMS})
        
    try:
        # Find player ID
        player_id, _ = _find_player_id(player_name)
        if player_id is None:
            return json.dumps({"error": ErrorMessages.PLAYER_NOT_FOUND.format(name=player_name)})
            
        player_info = commonplayerinfo.CommonPlayerInfo(
            player_id=player_id,
            timeout=DEFAULT_TIMEOUT
        )
        
        info = _process_dataframe(player_info.common_player_info.get_data_frame(), single_row=True)
        headline = _process_dataframe(player_info.player_headline_stats.get_data_frame(), single_row=True)
        seasons = _process_dataframe(player_info.available_seasons.get_data_frame(), single_row=False)
        
        if not all([info, headline, seasons]):
            return json.dumps({"error": ErrorMessages.DATA_PROCESSING_ERROR})
            
        result = {
            "info": info,
            "headline_stats": headline,
            "available_seasons": seasons
        }
        
        return json.dumps(result, default=str)
        
    except Exception as e:
        logger.error(f"Error fetching player info: {str(e)}", exc_info=True)
        return json.dumps({"error": f"Error fetching player info: {str(e)}"})

def fetch_player_rebounding_stats_logic(
    player_name: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    """
    Fetch detailed player rebounding statistics.
    
    Args:
        player_name (str): Player's name
        season (str): Season in YYYY-YY format
        season_type (str): Season type (regular/playoffs)
        
    Returns:
        str: JSON string containing:
        {
            "overall": {total rebounding stats},
            "by_shot_type": [2FG vs 3FG breakdowns],
            "by_contest": [contested vs uncontested],
            "by_distance": [distance ranges]
        }
    """
    logger.info(f"Executing fetch_player_rebounding_stats_logic for player: {player_name}")
    
    if not all([player_name, season]):
        return format_response(error=ErrorMessages.MISSING_REQUIRED_PARAMS)
        
    try:
        # Find player ID
        player_id, _ = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=ErrorMessages.PLAYER_NOT_FOUND.format(name=player_name))
            
        # Get player info to get team ID
        player_info = commonplayerinfo.CommonPlayerInfo(
            player_id=player_id,
            timeout=DEFAULT_TIMEOUT
        )
        info_df = _process_dataframe(player_info.common_player_info.get_data_frame(), single_row=True)
        if not info_df:
            return format_response(error=ErrorMessages.DATA_PROCESSING_ERROR)
            
        team_id = info_df.get("TEAM_ID")
        if not team_id:
            return format_response(error=ErrorMessages.TEAM_ID_NOT_FOUND)
        
        reb_stats = playerdashptreb.PlayerDashPtReb(
            player_id=player_id,
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            timeout=DEFAULT_TIMEOUT
        )
        
        overall = _process_dataframe(reb_stats.overall_rebounding.get_data_frame(), single_row=True)
        shot_type = _process_dataframe(reb_stats.shot_type_rebounding.get_data_frame(), single_row=False)
        contested = _process_dataframe(reb_stats.num_contested_rebounding.get_data_frame(), single_row=False)
        distances = _process_dataframe(reb_stats.shot_distance_rebounding.get_data_frame(), single_row=False)
        reb_dist = _process_dataframe(reb_stats.reb_distance_rebounding.get_data_frame(), single_row=False)
        
        if not all([overall, shot_type, contested, distances, reb_dist]):
            return format_response(error=ErrorMessages.DATA_PROCESSING_ERROR)
            
        result = {
            "overall": {
                "total": overall.get("REB", 0),
                "offensive": overall.get("OREB", 0),
                "defensive": overall.get("DREB", 0),
                "contested": overall.get("C_REB", 0),
                "uncontested": overall.get("UC_REB", 0),
                "contested_pct": overall.get("C_REB_PCT", 0)
            },
            "by_shot_type": shot_type,
            "by_contest": contested,
            "by_shot_distance": distances,
            "by_rebound_distance": reb_dist
        }
        
        return format_response(result)
        
    except Exception as e:
        logger.error(f"Error fetching rebounding stats: {str(e)}", exc_info=True)
        return format_response(error=f"Error fetching rebounding stats: {str(e)}")

def fetch_player_passing_stats_logic(
    player_name: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    """
    Fetch detailed player passing statistics.
    
    Args:
        player_name (str): Player's name
        season (str): Season in YYYY-YY format
        season_type (str): Season type (regular/playoffs)
        
    Returns:
        str: JSON string containing:
        {
            "passes_made": [pass details by recipient],
            "passes_received": [pass details by passer]
        }
    """
    logger.info(f"Executing fetch_player_passing_stats_logic for player: {player_name}")
    
    if not all([player_name, season]):
        return format_response(error=ErrorMessages.MISSING_REQUIRED_PARAMS)
        
    try:
        # Find player ID
        player_id, _ = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=ErrorMessages.PLAYER_NOT_FOUND.format(name=player_name))
            
        # Get player info to get team ID
        player_info = commonplayerinfo.CommonPlayerInfo(
            player_id=player_id,
            timeout=DEFAULT_TIMEOUT
        )
        info_df = _process_dataframe(player_info.common_player_info.get_data_frame(), single_row=True)
        if not info_df:
            return format_response(error=ErrorMessages.DATA_PROCESSING_ERROR)
            
        team_id = info_df.get("TEAM_ID")
        if not team_id:
            return format_response(error=ErrorMessages.TEAM_ID_NOT_FOUND)
        
        pass_stats = playerdashptpass.PlayerDashPtPass(
            player_id=player_id,
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            timeout=DEFAULT_TIMEOUT
        )
        
        made = _process_dataframe(pass_stats.passes_made.get_data_frame(), single_row=False)
        received = _process_dataframe(pass_stats.passes_received.get_data_frame(), single_row=False)
        
        if made is None or received is None:
            return format_response(error=ErrorMessages.DATA_PROCESSING_ERROR)
            
        # Process into more focused format
        processed_made = [{
            "to_player": pass_data.get("PASS_TO"),
            "frequency": pass_data.get("FREQUENCY"),
            "passes": pass_data.get("PASS"),
            "assists": pass_data.get("AST"),
            "shooting": {
                "fgm": pass_data.get("FGM"),
                "fga": pass_data.get("FGA"),
                "fg_pct": pass_data.get("FG_PCT"),
                "fg3m": pass_data.get("FG3M"),
                "fg3a": pass_data.get("FG3A"),
                "fg3_pct": pass_data.get("FG3_PCT")
            }
        } for pass_data in made]
        
        processed_received = [{
            "from_player": pass_data.get("PASS_FROM"),
            "frequency": pass_data.get("FREQUENCY"),
            "passes": pass_data.get("PASS"),
            "assists": pass_data.get("AST"),
            "shooting": {
                "fgm": pass_data.get("FGM"),
                "fga": pass_data.get("FGA"),
                "fg_pct": pass_data.get("FG_PCT"),
                "fg3m": pass_data.get("FG3M"),
                "fg3a": pass_data.get("FG3A"),
                "fg3_pct": pass_data.get("FG3_PCT")
            }
        } for pass_data in received]
        
        result = {
            "passes_made": processed_made,
            "passes_received": processed_received
        }
        
        return format_response(result)
        
    except Exception as e:
        logger.error(f"Error fetching passing stats: {str(e)}", exc_info=True)
        return format_response(error=f"Error fetching passing stats: {str(e)}")

def fetch_player_shots_tracking_logic(player_id: str) -> str:
    """
    Fetch player shots tracking statistics.
    
    Args:
        player_id (str): The NBA player ID
        
    Returns:
        str: JSON string containing player shots tracking statistics
    """
    logger.info(f"Fetching shots tracking stats for player: {player_id}")
    
    if not player_id:
        return format_response(error=ErrorMessages.PLAYER_ID_EMPTY)
    if not player_id.isdigit():
        return format_response(error=ErrorMessages.INVALID_PLAYER_ID_FORMAT.format(player_id=player_id))
        
    try:
        # Get player info to get team ID
        player_info = commonplayerinfo.CommonPlayerInfo(
            player_id=player_id,
            timeout=DEFAULT_TIMEOUT
        )
        info_df = _process_dataframe(player_info.common_player_info.get_data_frame(), single_row=True)
        if not info_df:
            return format_response(error=ErrorMessages.DATA_PROCESSING_ERROR)
            
        team_id = info_df.get("TEAM_ID")
        if not team_id:
            return format_response(error=ErrorMessages.TEAM_ID_NOT_FOUND)
        
        shot_stats = playerdashptshots.PlayerDashPtShots(
            player_id=player_id,
            team_id=team_id,
            timeout=DEFAULT_TIMEOUT
        )
        
        overall = _process_dataframe(shot_stats.overall.get_data_frame(), single_row=True)
        general = _process_dataframe(shot_stats.general_shooting.get_data_frame(), single_row=False)
        shot_clock = _process_dataframe(shot_stats.shot_clock_shooting.get_data_frame(), single_row=False)
        dribbles = _process_dataframe(shot_stats.dribble_shooting.get_data_frame(), single_row=False)
        defender = _process_dataframe(shot_stats.closest_defender_shooting.get_data_frame(), single_row=False)
        touch_time = _process_dataframe(shot_stats.touch_time_shooting.get_data_frame(), single_row=False)
        
        if not all([overall, general, shot_clock, dribbles, defender, touch_time]):
            return format_response(error=ErrorMessages.DATA_PROCESSING_ERROR)
            
        result = {
            "player_id": player_id,
            "team_id": team_id,
            "overall": {
                "fgm": overall.get("FGM", 0),
                "fga": overall.get("FGA", 0),
                "fg_pct": overall.get("FG_PCT", 0),
                "fg3m": overall.get("FG3M", 0),
                "fg3a": overall.get("FG3A", 0),
                "fg3_pct": overall.get("FG3_PCT", 0),
                "efg_pct": overall.get("EFG_PCT", 0)
            },
            "general": {
                type_data["SHOT_TYPE"].lower().replace(" ", "_"): {
                    "frequency": type_data.get("FGA_FREQUENCY", 0),
                    "fgm": type_data.get("FGM", 0),
                    "fga": type_data.get("FGA", 0),
                    "fg_pct": type_data.get("FG_PCT", 0),
                    "efg_pct": type_data.get("EFG_PCT", 0)
                }
                for type_data in general
            },
            "by_shot_clock": shot_clock,
            "by_dribbles": dribbles,
            "by_defender_distance": defender,
            "by_touch_time": touch_time
        }
        
        return format_response(result)
        
    except Exception as e:
        logger.error(f"Error fetching shooting stats: {str(e)}", exc_info=True)
        return format_response(error=f"Error fetching shooting stats: {str(e)}")

def fetch_player_clutch_stats_logic(player_name: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """Core logic to fetch player clutch stats."""
    logger.info(f"Executing fetch_player_clutch_stats_logic for: '{player_name}', Season: {season}, Type: {season_type}")
    if not player_name or not player_name.strip():
        return json.dumps({"error": ErrorMessages.PLAYER_NAME_EMPTY})
    if not season or not _validate_season_format(season):
        return json.dumps({"error": ErrorMessages.INVALID_SEASON_FORMAT.format(season=season)})

    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return json.dumps({"error": ErrorMessages.PLAYER_NOT_FOUND.format(name=player_name)})

        logger.debug(f"Fetching playerdashboardbyclutch for ID: {player_id}, Season: {season}")
        try:
            clutch_endpoint = playerdashboardbyclutch.PlayerDashboardByClutch(
                player_id=player_id,
                season=season,
                season_type_all_star=season_type,
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"playerdashboardbyclutch API call successful for ID: {player_id}, Season: {season}")
        except Exception as api_error:
            logger.error(f"nba_api playerdashboardbyclutch failed for ID {player_id}, Season {season}: {api_error}", exc_info=True)
            return json.dumps({"error": ErrorMessages.PLAYER_CLUTCH_STATS_API.format(name=player_actual_name, season=season, error=str(api_error))})

        overall_clutch = _process_dataframe(clutch_endpoint.overall_player_dashboard.get_data_frame(), single_row=True)
        last5min_clutch = _process_dataframe(clutch_endpoint.last5min_player_dashboard.get_data_frame(), single_row=True)

        if overall_clutch is None or last5min_clutch is None:
            logger.error(f"DataFrame processing failed for clutch stats of {player_actual_name} ({season}).")
            return json.dumps({"error": ErrorMessages.PLAYER_CLUTCH_STATS_PROCESSING.format(name=player_actual_name, season=season)})

        result = {
            "player_name": player_actual_name,
            "player_id": player_id,
            "season": season,
            "season_type": season_type,
            "overall_clutch": overall_clutch or {},
            "last5min_clutch": last5min_clutch or {}
        }
        logger.info(f"fetch_player_clutch_stats_logic completed for '{player_actual_name}', Season: {season}")
        return json.dumps(result, default=str)
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_clutch_stats_logic for '{player_name}', Season {season}: {e}", exc_info=True)
        return json.dumps({"error": ErrorMessages.PLAYER_CLUTCH_STATS_UNEXPECTED.format(name=player_name, season=season, error=str(e))})

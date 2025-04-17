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
from backend.config import DEFAULT_TIMEOUT, HEADSHOT_BASE_URL, Errors, CURRENT_SEASON
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

# Removed duplicate fetch_player_info_logic (exists in player_tools.py)

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
        return format_response(error=Errors.MISSING_REQUIRED_PARAMS)
        
    try:
        # Find player ID
        player_id, _ = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=Errors.PLAYER_NOT_FOUND.format(name=player_name))
            
        # Get player info to get team ID
        player_info = commonplayerinfo.CommonPlayerInfo(
            player_id=player_id,
            timeout=DEFAULT_TIMEOUT
        )
        info_df = _process_dataframe(player_info.common_player_info.get_data_frame(), single_row=True)
        if not info_df:
            return format_response(error=Errors.DATA_PROCESSING_ERROR)
            
        team_id = info_df.get("TEAM_ID")
        if not team_id:
            return format_response(error=Errors.TEAM_ID_NOT_FOUND)
        
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
            return format_response(error=Errors.DATA_PROCESSING_ERROR)
            
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
        return format_response(error=Errors.PLAYER_REBOUNDING_STATS_UNEXPECTED.format(name=player_name, error=str(e)))

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
        return format_response(error=Errors.MISSING_REQUIRED_PARAMS)
        
    try:
        # Find player ID
        player_id, _ = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=Errors.PLAYER_NOT_FOUND.format(name=player_name))
            
        # Get player info to get team ID
        player_info = commonplayerinfo.CommonPlayerInfo(
            player_id=player_id,
            timeout=DEFAULT_TIMEOUT
        )
        info_df = _process_dataframe(player_info.common_player_info.get_data_frame(), single_row=True)
        if not info_df:
            return format_response(error=Errors.DATA_PROCESSING_ERROR)
            
        team_id = info_df.get("TEAM_ID")
        if not team_id:
            return format_response(error=Errors.TEAM_ID_NOT_FOUND)
        
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
            return format_response(error=Errors.DATA_PROCESSING_ERROR)
            
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
        return format_response(error=Errors.PLAYER_PASSING_STATS_UNEXPECTED.format(name=player_name, error=str(e)))

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
        return format_response(error=Errors.PLAYER_ID_EMPTY)
    if not player_id.isdigit():
        return format_response(error=Errors.INVALID_PLAYER_ID_FORMAT.format(player_id=player_id))
        
    try:
        # Get player info to get team ID
        player_info = commonplayerinfo.CommonPlayerInfo(
            player_id=player_id,
            timeout=DEFAULT_TIMEOUT
        )
        info_df = _process_dataframe(player_info.common_player_info.get_data_frame(), single_row=True)
        if not info_df:
            return format_response(error=Errors.DATA_PROCESSING_ERROR)
            
        team_id = info_df.get("TEAM_ID")
        if not team_id:
            return format_response(error=Errors.TEAM_ID_NOT_FOUND)
        
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
            return format_response(error=Errors.DATA_PROCESSING_ERROR)
            
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
        return format_response(error=Errors.PLAYER_SHOOTING_STATS_UNEXPECTED.format(player_id=player_id, error=str(e)))

def fetch_player_clutch_stats_logic(
    player_name: str, 
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    measure_type: str = "Base",
    per_mode: str = "Totals",
    plus_minus: str = "N",
    pace_adjust: str = "N",
    rank: str = "N",
    shot_clock_range: str = None,
    game_segment: str = None,
    period: int = 0,
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    location: str = None,
    outcome: str = None,
    vs_conference: str = None,
    vs_division: str = None,
    season_segment: str = None,
    date_from: str = None,
    date_to: str = None
) -> str:
    """Core logic to fetch player clutch stats.
    
    Args:
        player_name (str): Player's name
        season (str): Season in YYYY-YY format
        season_type (str): Season type (Regular Season, Playoffs, etc.)
        measure_type (str): One of: Base, Advanced, Misc, Four Factors, Scoring, Opponent, Usage
        per_mode (str): One of: Totals, PerGame, MinutesPer, Per48, Per40, Per36, PerMinute, PerPossession, PerPlay, Per100Possessions, Per100Plays
        plus_minus (str): Include plus minus stats (Y/N)
        pace_adjust (str): Include pace adjusted stats (Y/N)
        rank (str): Include stat rankings (Y/N)
        shot_clock_range (str, optional): Shot clock range filter
        game_segment (str, optional): Game segment filter (First Half, Second Half, Overtime)
        period (int): Period filter (0 for all)
        last_n_games (int): Last N games filter
        month (int): Month filter (0 for all)
        opponent_team_id (int): Filter by opponent team
        location (str, optional): Home/Road filter
        outcome (str, optional): W/L filter
        vs_conference (str, optional): Conference filter
        vs_division (str, optional): Division filter
        season_segment (str, optional): Season segment filter
        date_from (str, optional): Start date filter
        date_to (str, optional): End date filter
    """
    logger.info(f"Executing fetch_player_clutch_stats_logic for: '{player_name}', Season: {season}")
    
    # Input validation
    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
        
    # Validate measure type
    valid_measure_types = ["Base", "Advanced", "Misc", "Four Factors", "Scoring", "Opponent", "Usage"]
    if measure_type not in valid_measure_types:
        return format_response(error=Errors.INVALID_MEASURE_TYPE)
        
    # Validate per mode
    valid_per_modes = ["Totals", "PerGame", "MinutesPer", "Per48", "Per40", "Per36", "PerMinute", "PerPossession", "PerPlay", "Per100Possessions", "Per100Plays"]
    if per_mode not in valid_per_modes:
        return format_response(error=Errors.INVALID_PER_MODE)
        
    # Validate Y/N parameters
    if plus_minus not in ["Y", "N"] or pace_adjust not in ["Y", "N"] or rank not in ["Y", "N"]:
        return format_response(error=Errors.INVALID_PLUS_MINUS)

    try:
        # Find player ID
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=Errors.PLAYER_NOT_FOUND.format(name=player_name))

        logger.debug(f"Fetching playerdashboardbyclutch for ID: {player_id}, Season: {season}")
        try:
            clutch_endpoint = playerdashboardbyclutch.PlayerDashboardByClutch(
                player_id=player_id,
                season=season,
                season_type_playoffs=season_type,
                measure_type_detailed=measure_type,
                per_mode_detailed=per_mode,
                plus_minus=plus_minus,
                pace_adjust=pace_adjust,
                rank=rank,
                shot_clock_range=shot_clock_range,
                game_segment_nullable=game_segment,
                period=period,
                last_n_games=last_n_games,
                month=month,
                opponent_team_id=opponent_team_id,
                location_nullable=location,
                outcome_nullable=outcome,
                vs_conference_nullable=vs_conference,
                vs_division_nullable=vs_division,
                season_segment_nullable=season_segment,
                date_from_nullable=date_from,
                date_to_nullable=date_to,
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"playerdashboardbyclutch API call successful for ID: {player_id}, Season: {season}")
        except Exception as api_error:
            logger.error(f"nba_api playerdashboardbyclutch failed for ID {player_id}, Season {season}: {api_error}", exc_info=True)
            return format_response(error=Errors.PLAYER_CAREER_STATS_API.format(name=player_actual_name, season=season, error=str(api_error)))

        # Get all clutch time period stats
        clutch_data = clutch_endpoint.get_dict()
        results = clutch_data.get('resultSets', [])
        processed_data = {}
        for result_set in results:
            name = result_set.get('name')
            headers = result_set.get('headers')
            row_set = result_set.get('rowSet')
            if name and headers and row_set:
                # Process only the specific clutch timeframes if needed, or overall
                # Example: Process 'OverallPlayerDashboard'
                if name == 'OverallPlayerDashboard' and len(row_set) > 0:
                    processed_data[name] = [dict(zip(headers, row)) for row in row_set]
                    # You might want to return just this specific part
                    # return format_response(data=processed_data[name][0]) # Return the first row if only one player's overall expected
        if not processed_data:
            logger.warning(f"No relevant clutch data sets found for {player_actual_name} in season {season}")
            # Return empty success or a specific message
            return format_response(data={})

        # Return all processed datasets or just the overall one
        # Example returning just the first row of Overall data if found
        overall_data = processed_data.get('OverallPlayerDashboard')
        if overall_data and len(overall_data) > 0:
            return format_response(data=overall_data[0])
        else:
            logger.warning(f"OverallPlayerDashboard data not found for {player_actual_name} in season {season}")
            return format_response(data={}) # Or return an error

    except Exception as e:
        api_error = e # Store the original exception
        logger.error(f"nba_api playerdashboardbyclutch failed for ID {player_id}, Season {season}: {e}")
        # Use suggested error constant name
        return format_response(error=Errors.PLAYER_CAREER_STATS_API.format(name=player_actual_name, season=season, error=str(api_error)))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_clutch_stats_logic for '{player_actual_name}', Season {season}: {e}")
        # Use suggested error constant name
        return format_response(error=Errors.PLAYER_CAREER_STATS_UNEXPECTED.format(name=player_actual_name, season=season, error=str(e)))

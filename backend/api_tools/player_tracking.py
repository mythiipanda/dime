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
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = "PerGame"
) -> str:
    """
    Fetch detailed player rebounding statistics.
    
    Args:
        player_name (str): Player's name
        season (str): Season in YYYY-YY format
        season_type (str): Season type (regular/playoffs)
        per_mode (str): One of: Totals, PerGame, MinutesPer, Per48, Per40, Per36, PerMinute, PerPossession, PerPlay, Per100Possessions, Per100Plays
        
    Returns:
        str: JSON string containing:
        {
            "overall": {total rebounding stats},
            "by_shot_type": [2FG vs 3FG breakdowns],
            "by_contest": [contested vs uncontested],
            "by_shot_distance": [distance ranges],
            "by_rebound_distance": [distance ranges],
            "parameters": {
                "season": season,
                "season_type": season_type,
                "per_mode": per_mode
            }
        }
    """
    logger.info(f"Executing fetch_player_rebounding_stats_logic for player: {player_name}, PerMode: {per_mode}")
    
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
            per_mode_simple=per_mode,
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
            "by_rebound_distance": reb_dist,
            "parameters": {
                "season": season,
                "season_type": season_type,
                "per_mode": per_mode
            }
        }
        
        return format_response(result)
        
    except Exception as e:
        logger.error(f"Error fetching rebounding stats: {str(e)}", exc_info=True)
        return format_response(error=Errors.PLAYER_REBOUNDING_STATS_UNEXPECTED.format(name=player_name, error=str(e)))

def fetch_player_passing_stats_logic(
    player_name: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = "PerGame"
) -> str:
    """
    Fetch detailed player passing statistics.
    
    Args:
        player_name (str): Player's name
        season (str): Season in YYYY-YY format
        season_type (str): Season type (regular/playoffs)
        per_mode (str): One of: Totals, PerGame, MinutesPer, Per48, Per40, Per36, PerMinute, PerPossession, PerPlay, Per100Possessions, Per100Plays
        
    Returns:
        str: JSON string containing:
        {
            "passes_made": [pass details by recipient],
            "passes_received": [pass details by passer],
            "parameters": {
                "season": season,
                "season_type": season_type,
                "per_mode": per_mode
            }
        }
    """
    logger.info(f"Executing fetch_player_passing_stats_logic for player: {player_name}, PerMode: {per_mode}")
    
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
            per_mode_simple=per_mode,
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
            "passes_received": processed_received,
            "parameters": {
                "season": season,
                "season_type": season_type,
                "per_mode": per_mode
            }
        }
        
        return format_response(result)
        
    except Exception as e:
        logger.error(f"Error fetching passing stats: {str(e)}", exc_info=True)
        return format_response(error=Errors.PLAYER_PASSING_STATS_UNEXPECTED.format(name=player_name, error=str(e)))

def fetch_player_shots_tracking_logic(
    player_id: str, 
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Fetch detailed player shooting stats using player ID, with optional filters.
    Args:
        player_id (str): Player's ID.
        season (str): Season identifier (e.g., "2023-24"). Defaults to current season.
        season_type (str): Type of season (e.g., "Regular Season", "Playoffs"). Defaults to "Regular Season".
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0 (all opponents).
        date_from (str, optional): Start date filter (YYYY-MM-DD). Defaults to None.
        date_to (str, optional): End date filter (YYYY-MM-DD). Defaults to None.
    Returns:
        str: JSON string containing shooting stats by various splits.
    """
    logger.info(
        f"Executing fetch_player_shots_tracking_logic for player ID: {player_id}, Season: {season}, "
        f"Type: {season_type}, Opponent: {opponent_team_id}, From: {date_from}, To: {date_to}"
    )
    
    if not player_id:
        return format_response(error=Errors.MISSING_REQUIRED_PARAMS)
        
    try:
        # Team ID is required by the endpoint, fetch it first
        player_info = commonplayerinfo.CommonPlayerInfo(
            player_id=player_id,
            timeout=DEFAULT_TIMEOUT
        )
        info_df = _process_dataframe(player_info.common_player_info.get_data_frame(), single_row=True)
        if not info_df or "TEAM_ID" not in info_df:
            logger.error(f"Could not retrieve team ID for player ID {player_id}")
            return format_response(error=Errors.TEAM_ID_NOT_FOUND)
        team_id = info_df.get("TEAM_ID")
        player_actual_name = info_df.get("DISPLAY_FIRST_LAST", f"Player_{player_id}")

        # Fetch shooting stats
        shooting_stats = playerdashptshots.PlayerDashPtShots(
            player_id=player_id,
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            opponent_team_id=opponent_team_id,
            date_from_nullable=date_from,
            date_to_nullable=date_to,
            # Add other relevant parameters here if needed
            timeout=DEFAULT_TIMEOUT
        )
        
        # Process different shooting splits
        general = _process_dataframe(shooting_stats.general_shooting.get_data_frame(), single_row=False)
        shot_clock = _process_dataframe(shooting_stats.shot_clock_shooting.get_data_frame(), single_row=False)
        dribbles = _process_dataframe(shooting_stats.dribble_shooting.get_data_frame(), single_row=False)
        touch_time = _process_dataframe(shooting_stats.touch_time_shooting.get_data_frame(), single_row=False)
        defender_dist = _process_dataframe(shooting_stats.closest_defender_shooting.get_data_frame(), single_row=False)
        defender_dist_10ft = _process_dataframe(shooting_stats.closest_defender_10ft_plus_shooting.get_data_frame(), single_row=False)

        if not general: # Check if at least general stats are available
             logger.warning(f"No general shooting stats found for player {player_id} with given filters.")
             # Allow returning partial data if other splits exist

        result = {
            "player_id": player_id,
            "player_name": player_actual_name,
            "team_id": team_id,
            "parameters": {
                "season": season,
                "season_type": season_type,
                "opponent_team_id": opponent_team_id,
                "date_from": date_from,
                "date_to": date_to
            },
            "general_shooting": general or [],
            "by_shot_clock": shot_clock or [],
            "by_dribble_count": dribbles or [],
            "by_touch_time": touch_time or [],
            "by_defender_distance": defender_dist or [],
            "by_defender_distance_10ft_plus": defender_dist_10ft or []
        }
        
        return format_response(result)
        
    except Exception as e:
        logger.error(f"Error fetching shots tracking stats for player ID {player_id}: {str(e)}", exc_info=True)
        return format_response(error=Errors.PLAYER_SHOT_TRACKING_UNEXPECTED.format(player_id=player_id, error=str(e)))

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
                shot_clock_range_nullable=shot_clock_range,
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
        
        # Target the specific clutch dataset
        clutch_dataset_name = 'Last5Min5PointPlayerDashboard' 
        clutch_stats = None

        for result_set in results:
            name = result_set.get('name')
            headers = result_set.get('headers')
            row_set = result_set.get('rowSet')
            
            # Check if this is the target clutch dataset
            if name == clutch_dataset_name and headers and row_set:
                # Process the clutch dataset
                if len(row_set) > 0:
                    # Assuming the first row contains the relevant aggregated stats
                    clutch_stats = dict(zip(headers, row_set[0])) 
                    break # Found the dataset, no need to continue loop

        if clutch_stats is None:
            logger.warning(f"'{clutch_dataset_name}' data not found for {player_actual_name} in season {season} with specified filters.")
            # Return empty success or a specific message
            return format_response(data={}, message=f"No clutch stats ({clutch_dataset_name}) found for the player with the specified parameters.")

        # Return the extracted clutch stats
        return format_response(data=clutch_stats)

    except Exception as e:
        # Keep existing exception handling
        api_error = e # Store the original exception
        logger.error(f"nba_api playerdashboardbyclutch failed for ID {player_id}, Season {season}: {e}", exc_info=True)
        # Use suggested error constant name
        return format_response(error=Errors.PLAYER_CAREER_STATS_API.format(name=player_actual_name, season=season, error=str(api_error)))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_clutch_stats_logic for '{player_actual_name}', Season {season}: {e}", exc_info=True)
        # Use suggested error constant name
        return format_response(error=Errors.PLAYER_CAREER_STATS_UNEXPECTED.format(name=player_actual_name, season=season, error=str(e)))

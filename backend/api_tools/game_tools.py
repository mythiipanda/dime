import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import re # For parsing live clock
from nba_api.stats.endpoints import boxscoretraditionalv2, playbyplay, shotchartdetail, leaguegamefinder
# Live PBP endpoint
from nba_api.live.nba.endpoints import PlayByPlay as LivePlayByPlay
# Endpoint to check game status (if needed)
from nba_api.live.nba.endpoints import scoreboard
from backend.config import DEFAULT_TIMEOUT, Errors
from backend.api_tools.utils import _process_dataframe, format_response

logger = logging.getLogger(__name__)

def _format_game_leader(leader_data: Dict) -> Dict:
    """Helper function to format game leader data"""
    return {
        "name": leader_data.get("name", ""),
        "stats": f"{leader_data.get('points', 0)} PTS, {leader_data.get('rebounds', 0)} REB, {leader_data.get('assists', 0)} AST"
    }

def fetch_boxscore_traditional_logic(game_id: str) -> str:
    """
    Fetches detailed box score data for a specific game.
    
    Args:
        game_id: NBA game ID
        
    Returns:
        JSON string containing box score statistics in an organized format
    """
    logger.info(f"Executing fetch_boxscore_traditional_logic for game ID: {game_id}")
    
    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)
    
    try:
        # Get boxscore data
        boxscore = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id)
        
        # Process player stats
        player_stats_raw = boxscore.player_stats.get_data_frame()
        player_stats = []
        
        if not player_stats_raw.empty:
            for _, row in player_stats_raw.iterrows():
                player = {
                    "player_id": row.get("PLAYER_ID"),
                    "name": row.get("PLAYER_NAME"),
                    "team": row.get("TEAM_ABBREVIATION"),
                    "position": row.get("START_POSITION", ""),
                    "minutes": row.get("MIN", "0"),
                    "points": row.get("PTS", 0),
                    "rebounds": {
                        "offensive": row.get("OREB", 0),
                        "defensive": row.get("DREB", 0),
                        "total": row.get("REB", 0)
                    },
                    "assists": row.get("AST", 0),
                    "steals": row.get("STL", 0),
                    "blocks": row.get("BLK", 0),
                    "turnovers": row.get("TO", 0),
                    "fouls": row.get("PF", 0),
                    "shooting": {
                        "fg": f"{row.get('FGM', 0)}-{row.get('FGA', 0)}",
                        "fg_pct": row.get("FG_PCT", 0.0),
                        "fg3": f"{row.get('FG3M', 0)}-{row.get('FG3A', 0)}",
                        "fg3_pct": row.get("FG3_PCT", 0.0),
                        "ft": f"{row.get('FTM', 0)}-{row.get('FTA', 0)}",
                        "ft_pct": row.get("FT_PCT", 0.0)
                    },
                    "plus_minus": row.get("PLUS_MINUS", 0)
                }
                player_stats.append(player)
        
        # Process team stats
        team_stats_raw = boxscore.team_stats.get_data_frame()
        team_stats = []
        
        if not team_stats_raw.empty:
            for _, row in team_stats_raw.iterrows():
                team = {
                    "team_id": row.get("TEAM_ID"),
                    "name": f"{row.get('TEAM_CITY', '')} {row.get('TEAM_NAME', '')}",
                    "abbreviation": row.get("TEAM_ABBREVIATION"),
                    "points": row.get("PTS", 0),
                    "rebounds": {
                        "offensive": row.get("OREB", 0),
                        "defensive": row.get("DREB", 0),
                        "total": row.get("REB", 0)
                    },
                    "assists": row.get("AST", 0),
                    "steals": row.get("STL", 0),
                    "blocks": row.get("BLK", 0),
                    "turnovers": row.get("TO", 0),
                    "fouls": row.get("PF", 0),
                    "shooting": {
                        "fg": f"{row.get('FGM', 0)}-{row.get('FGA', 0)}",
                        "fg_pct": round(row.get("FG_PCT", 0.0), 3),
                        "fg3": f"{row.get('FG3M', 0)}-{row.get('FG3A', 0)}",
                        "fg3_pct": round(row.get("FG3_PCT", 0.0), 3),
                        "ft": f"{row.get('FTM', 0)}-{row.get('FTA', 0)}",
                        "ft_pct": round(row.get("FT_PCT", 0.0), 3)
                    },
                    "plus_minus": row.get("PLUS_MINUS", 0)
                }
                team_stats.append(team)
        
        # Organize the starters/bench breakdown
        starters_bench_raw = boxscore.team_starter_bench_stats.get_data_frame()
        starters_bench = []
        
        if not starters_bench_raw.empty:
            for _, row in starters_bench_raw.iterrows():
                group = {
                    "team_id": row.get("TEAM_ID"),
                    "team_abbreviation": row.get("TEAM_ABBREVIATION"),
                    "group": row.get("STARTERS_BENCH"),
                    "minutes": row.get("MIN", "0"),
                    "points": row.get("PTS", 0),
                    "rebounds": row.get("REB", 0),
                    "assists": row.get("AST", 0)
                }
                starters_bench.append(group)
        
        # Combine all results
        result = {
            "game_id": game_id,
            "teams": team_stats,
            "players": player_stats,
            "starters_bench": starters_bench
        }
        
        logger.info(f"fetch_boxscore_traditional_logic completed for game {game_id}")
        return format_response(result)
        
    except Exception as e:
        logger.error(f"Error fetching boxscore for game {game_id}: {str(e)}", exc_info=True)
        return format_response(error=Errors.BOXSCORE_API.format(game_id=game_id, error=str(e)))

# Historical PBP endpoint
def _fetch_historical_playbyplay_logic(game_id: str, start_period: int = 0, end_period: int = 0) -> Dict[str, Any]:
    """Internal function to fetch PBP for completed games using stats.playbyplay."""
    logger.info(f"Executing _fetch_historical_playbyplay_logic for game ID: {game_id}")
    try:
        pbp = playbyplay.PlayByPlay(
            game_id=game_id,
            start_period=start_period,
            end_period=end_period
        )
        plays_raw = pbp.play_by_play.get_data_frame()
        periods = {}
        if not plays_raw.empty:
            for _, row in plays_raw.iterrows():
                period = row.get("PERIOD", 0)
                if period not in periods: periods[period] = []
                play = {
                    "event_num": row.get("EVENTNUM"),
                    "clock": row.get("PCTIMESTRING", ""), 
                    "score": row.get("SCORE"),
                    "margin": row.get("SCOREMARGIN"), 
                    "team": _determine_play_team(row),
                    "home_description": row.get("HOMEDESCRIPTION"),
                    "away_description": row.get("VISITORDESCRIPTION"),
                    "neutral_description": row.get("NEUTRALDESCRIPTION"), 
                    "event_type": _get_event_type(row.get("EVENTMSGTYPE"))
                }
                if (start_period == 0 and end_period == 0) or (start_period <= period <= end_period):
                    periods[period].append(play)
        periods_list = [{"period": p, "plays": periods[p]} for p in sorted(periods.keys())]
        result = {
            "game_id": game_id,
            "has_video": bool(pbp.available_video.get_data_frame().iloc[0][0] == 1) if not pbp.available_video.get_data_frame().empty else False,
            "source": "historical",
            "filtered_periods": {"start": start_period, "end": end_period} if start_period > 0 or end_period > 0 else None,
            "periods": periods_list
        }
        logger.info(f"_fetch_historical_playbyplay_logic completed for game {game_id}")
        return result
    except Exception as e:
        logger.error(f"Error in _fetch_historical_playbyplay_logic for game {game_id}: {str(e)}", exc_info=True)
        # Raise exception to be caught by the main function
        raise e

# Live Play-by-Play Logic
def _fetch_live_playbyplay_logic(game_id: str) -> Dict[str, Any]:
    """Internal function to fetch PBP for live games using live.PlayByPlay."""
    logger.info(f"Executing _fetch_live_playbyplay_logic for game ID: {game_id}")
    try:
        pbp = LivePlayByPlay(game_id=game_id)
        live_data = pbp.get_dict()
        raw_actions = live_data.get('game', {}).get('actions', [])
        
        # Check if game is live/has actions - if not, raise error to trigger fallback
        if not raw_actions: 
            logger.warning(f"No live actions found for game {game_id}. Assuming not live or finished.")
            raise ValueError("No live actions found, likely not a live game.")
        
        periods = {}
        game_details = live_data.get('game', {})
        home_team_id = game_details.get('homeTeam',{}).get('teamId')
        away_team_id = game_details.get('awayTeam',{}).get('teamId')

        for action in raw_actions:
            period = action.get("period", 0)
            if period not in periods: periods[period] = []
            
            # Format clock: PTMMSS.ms -> MM:SS
            clock_raw = action.get("clock", "")
            match = re.match(r"PT(\d+)M(\d+\.?\d*)S", clock_raw)
            clock_formatted = f"{match.group(1)}:{match.group(2).split('.')[0].zfill(2)}" if match else clock_raw
            
            # Format score
            score_str = f"{action.get('scoreHome', 0)}-{action.get('scoreAway', 0)}" if action.get('scoreHome') is not None else None
            
            # Determine team (basic based on teamId)
            action_team_id = action.get('teamId')
            team_str = "neutral"
            if action_team_id == home_team_id: team_str = "home"
            elif action_team_id == away_team_id: team_str = "away"

            play = {
                "event_num": action.get("actionNumber"),
                "clock": clock_formatted, 
                "score": score_str,
                "margin": None, # Live endpoint doesn't provide margin
                "team": team_str, 
                "home_description": None, # Live endpoint has one description
                "away_description": None,
                "neutral_description": action.get("description"), 
                # Live mapping needs refinement based on actionType/subType values
                "event_type": f"{action.get('actionType', '').upper()}_{action.get('subType', '').upper()}"
            }
            periods[period].append(play)
        
        periods_list = [{"period": p, "plays": periods[p]} for p in sorted(periods.keys())]
        result = {
            "game_id": game_id,
            "has_video": False, # Live endpoint doesn't seem to provide this
            "source": "live",
            "filtered_periods": None, # Live PBP doesn't support period filtering here
            "periods": periods_list
        }
        logger.info(f"_fetch_live_playbyplay_logic completed for game {game_id}")
        return result
    except Exception as e:
        logger.error(f"Error in _fetch_live_playbyplay_logic for game {game_id}: {str(e)}", exc_info=True)
        # Raise exception to be caught by the main function
        raise e

# Main Play-by-Play Logic Function
def fetch_playbyplay_logic(game_id: str) -> Dict[str, Any]:
    """
    Fetches play-by-play data, trying the live endpoint first and falling back to historical.
    Args:
        game_id: NBA game ID
    Returns:
        Dictionary containing organized play-by-play information.
    """
    if not game_id:
        return {"error": Errors.GAME_ID_EMPTY}
    
    try:
        # Attempt to fetch live data first
        logger.info(f"Attempting to fetch LIVE play-by-play for game {game_id}")
        live_pbp_data = _fetch_live_playbyplay_logic(game_id)
        # If live data indicates game is active (has periods/actions), return it
        if live_pbp_data and live_pbp_data.get("periods"): 
            return live_pbp_data
        # If live_pbp_data is None or has no periods, it might have failed or game not live
        # Error was already logged in _fetch_live_playbyplay_logic if it failed

    except Exception as live_err:
        # Log the error from the live attempt but continue to historical
        logger.warning(f"Live play-by-play fetch failed for game {game_id} (Error: {live_err}). Will attempt historical fetch.")
        
    # Fallback to historical data if live attempt fails or returns no actions
    try:
        logger.info(f"Fetching HISTORICAL play-by-play for game {game_id}")
        historical_pbp_data = _fetch_historical_playbyplay_logic(game_id)
        return historical_pbp_data
    except Exception as historical_err:
        logger.error(f"Both live and historical play-by-play fetches failed for game {game_id}: Live Error ({live_err}), Historical Error ({historical_err})", exc_info=True)
        return {"error": Errors.PLAYBYPLAY_API.format(game_id=game_id, error=str(historical_err))}

# Helper Functions (Keep original ones for historical endpoint)
def _determine_play_team(row):
    """Helper function to determine which team the play belongs to"""
    if row.get("HOMEDESCRIPTION") is not None and row.get("VISITORDESCRIPTION") is None:
        return "home"
    elif row.get("VISITORDESCRIPTION") is not None and row.get("HOMEDESCRIPTION") is None:
        return "away"
    else:
        return "neutral"

def _get_event_type(event_code):
    """Helper function to map event codes to readable descriptions"""
    event_types = {
        1: "FIELD_GOAL_MADE",
        2: "FIELD_GOAL_MISSED",
        3: "FREE_THROW",
        4: "REBOUND",
        5: "TURNOVER",
        6: "FOUL",
        7: "VIOLATION",
        8: "SUBSTITUTION",
        9: "TIMEOUT",
        10: "JUMP_BALL",
        11: "EJECTION",
        12: "START_PERIOD",
        13: "END_PERIOD",
        18: "INSTANT_REPLAY",
        20: "STOPPAGE"
    }
    return event_types.get(event_code, "OTHER")

def fetch_shotchart_logic(game_id: str) -> str:
    """
    Fetches shot chart data for a specific game.
    
    Args:
        game_id: NBA game ID
        
    Returns:
        JSON string containing organized shot chart information
    """
    logger.info(f"Executing fetch_shotchart_logic for game ID: {game_id}")
    
    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)
    
    try:
        # Get shot chart data - set team_id and player_id to 0 to get all shots
        shotchart = shotchartdetail.ShotChartDetail(
            game_id_nullable=game_id,
            team_id=0,
            player_id=0,
            context_measure_simple="FGA",
            season_nullable="2023-24"  # Using current season
        )
        
        # Process shot chart data
        shots_raw = shotchart.shot_chart_detail.get_data_frame()
        shots = []
        
        if not shots_raw.empty:
            for _, row in shots_raw.iterrows():
                shot = {
                    "player": {
                        "id": row.get("PLAYER_ID"),
                        "name": row.get("PLAYER_NAME")
                    },
                    "team": {
                        "id": row.get("TEAM_ID"),
                        "name": row.get("TEAM_NAME")
                    },
                    "period": row.get("PERIOD"),
                    "time_remaining": f"{row.get('MINUTES_REMAINING')}:{str(row.get('SECONDS_REMAINING')).zfill(2)}",
                    "shot_type": row.get("SHOT_TYPE"),
                    "shot_zone": {
                        "basic": row.get("SHOT_ZONE_BASIC"),
                        "area": row.get("SHOT_ZONE_AREA"),
                        "range": row.get("SHOT_ZONE_RANGE")
                    },
                    "distance": row.get("SHOT_DISTANCE"),
                    "coordinates": {
                        "x": row.get("LOC_X"),
                        "y": row.get("LOC_Y")
                    },
                    "made": row.get("SHOT_MADE_FLAG") == 1,
                    "action_type": row.get("ACTION_TYPE")
                }
                shots.append(shot)
        
        # Get league averages for zones
        league_avgs_raw = shotchart.league_averages.get_data_frame()
        league_avgs = []
        
        if not league_avgs_raw.empty:
            for _, row in league_avgs_raw.iterrows():
                zone = {
                    "zone_basic": row.get("SHOT_ZONE_BASIC"),
                    "zone_area": row.get("SHOT_ZONE_AREA"),
                    "zone_range": row.get("SHOT_ZONE_RANGE"),
                    "attempts": row.get("FGA"),
                    "made": row.get("FGM"),
                    "pct": row.get("FG_PCT")
                }
                league_avgs.append(zone)
        
        # Organize shots by team
        teams = {}
        for shot in shots:
            team_id = shot["team"]["id"]
            if team_id not in teams:
                teams[team_id] = {
                    "team_name": shot["team"]["name"],
                    "team_id": team_id,
                    "shots": []
                }
            teams[team_id]["shots"].append(shot)
        
        # Convert teams dict to a list
        teams_list = list(teams.values())
        
        # Final result
        result = {
            "game_id": game_id,
            "teams": teams_list,
            "league_averages": league_avgs
        }
        
        logger.info(f"fetch_shotchart_logic completed for game {game_id}")
        return format_response(result)
        
    except Exception as e:
        logger.error(f"Error fetching shot chart for game {game_id}: {str(e)}", exc_info=True)
        return format_response(error=Errors.SHOTCHART_API.format(game_id=game_id, error=str(e)))

def fetch_league_games_logic(
    player_or_team_abbreviation: str = 'T',
    player_id_nullable: Optional[int] = None,
    team_id_nullable: Optional[int] = None,
    season_nullable: Optional[str] = None,
    season_type_nullable: Optional[str] = None,
    league_id_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None
) -> str:
    """
    Fetches league games based on various filters.
    
    Args:
        player_or_team_abbreviation (str): Fetch games for 'P'layer or 'T'eam. Defaults to 'T'.
        player_id_nullable (Optional[int]): Player ID to filter by.
        team_id_nullable (Optional[int]): Team ID to filter by.
        season_nullable (Optional[str]): Season (e.g., "2023-24").
        season_type_nullable (Optional[str]): Season type (e.g., "Regular Season", "Playoffs").
        league_id_nullable (Optional[str]): League ID (e.g., "00" for NBA).
        date_from_nullable (Optional[str]): Start date filter (YYYY-MM-DD).
        date_to_nullable (Optional[str]): End date filter (YYYY-MM-DD).

    Returns:
        str: JSON string containing a list of games.
    """
    logger.info(f"Executing fetch_league_games_logic with filters: team_id={team_id_nullable}, player_id={player_id_nullable}, season={season_nullable}")
    
    try:
        game_finder = leaguegamefinder.LeagueGameFinder(
            player_or_team_abbreviation=player_or_team_abbreviation,
            player_id_nullable=player_id_nullable,
            team_id_nullable=team_id_nullable,
            season_nullable=season_nullable,
            season_type_nullable=season_type_nullable,
            league_id_nullable=league_id_nullable,
            date_from_nullable=date_from_nullable,
            date_to_nullable=date_to_nullable
        )
        
        games_df = game_finder.league_game_finder_results.get_data_frame()
        
        # Convert dataframe to list of dicts
        games_list = games_df.to_dict(orient='records') if not games_df.empty else []
        
        # Format dates for better readability if needed
        for game in games_list:
            if 'GAME_DATE' in game and isinstance(game['GAME_DATE'], str):
                try:
                    # Attempt to parse and reformat date
                    parsed_date = datetime.strptime(game['GAME_DATE'], '%Y-%m-%dT%H:%M:%S')
                    game['GAME_DATE_FORMATTED'] = parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    game['GAME_DATE_FORMATTED'] = game['GAME_DATE'] # Keep original if parsing fails

        result = {"games": games_list}
        logger.info(f"fetch_league_games_logic found {len(games_list)} games.")
        return format_response(result)
        
    except Exception as e:
        logger.error(f"Error fetching league games: {str(e)}", exc_info=True)
        return format_response(error=Errors.LEAGUE_GAMES_API.format(error=str(e)))
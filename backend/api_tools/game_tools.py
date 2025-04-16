import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from nba_api.live.nba.endpoints import scoreboard
from nba_api.stats.endpoints import boxscoretraditionalv2, playbyplay, shotchartdetail, leaguegamefinder
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

def fetch_playbyplay_logic(game_id: str, start_period: int = 0, end_period: int = 0) -> str:
    """
    Fetches play-by-play data for a specific game.
    
    Args:
        game_id: NBA game ID
        
    Returns:
        JSON string containing organized play-by-play information
    """
    logger.info(f"Executing fetch_playbyplay_logic for game ID: {game_id}")
    
    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)
    
    try:
        # Get play-by-play data
        pbp = playbyplay.PlayByPlay(
            game_id=game_id,
            start_period=start_period,
            end_period=end_period
        )
        
        # Process play-by-play data
        plays_raw = pbp.play_by_play.get_data_frame()
        
        # Initialize period quarters/data structure
        periods = {}
        
        if not plays_raw.empty:
            # First, organize plays by period
            for _, row in plays_raw.iterrows():
                period = row.get("PERIOD", 0)
                
                if period not in periods:
                    periods[period] = []
                
                # Format the play data
                play = {
                    "event_num": row.get("EVENTNUM"),
                    "clock": row.get("PCTIMESTRING", ""),
                    "score": row.get("SCORE", ""),
                    "margin": row.get("SCOREMARGIN", ""),
                    "team": _determine_play_team(row),
                    "home_description": row.get("HOMEDESCRIPTION", ""),
                    "away_description": row.get("VISITORDESCRIPTION", ""),
                    "neutral_description": row.get("NEUTRALDESCRIPTION", ""),
                    "event_type": _get_event_type(row.get("EVENTMSGTYPE"))
                }
                
                # Add the play to the appropriate period
                # Filter plays based on period if filters are set
                if (start_period == 0 and end_period == 0) or \
                   (start_period <= period <= end_period):
                    periods[period].append(play)
        
        # Convert periods dict to a list for better JSON ordering
        periods_list = [{"period": p, "plays": periods[p]} for p in sorted(periods.keys())]
        
        # Combine all results
        # Only include periods within the filtered range
        if start_period > 0 and end_period > 0:
            periods_list = [p for p in periods_list if start_period <= p["period"] <= end_period]

        result = {
            "game_id": game_id,
            "has_video": pbp.available_video.get_data_frame().iloc[0][0] == 1 if not pbp.available_video.get_data_frame().empty else False,
            "filtered_periods": {
                "start": start_period,
                "end": end_period
            } if start_period > 0 or end_period > 0 else None,
            "periods": periods_list
        }
        
        logger.info(f"fetch_playbyplay_logic completed for game {game_id}")
        return format_response(result)
        
    except Exception as e:
        logger.error(f"Error fetching play-by-play for game {game_id}: {str(e)}", exc_info=True)
        return format_response(error=Errors.PLAYBYPLAY_API.format(game_id=game_id, error=str(e)))

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
    Fetches games based on Player/Team ID and optional date range.
    
    Args:
        player_or_team_abbreviation (str): Search by 'P' (Player) or 'T' (Team). Defaults to 'T'.
        player_id_nullable (int, optional): Player ID. Required if player_or_team='P'.
        team_id_nullable (int, optional): Team ID. Required if player_or_team='T'.
        season_nullable (str, optional): Season.
        season_type_nullable (str, optional): Season Type.
        league_id_nullable (str, optional): League ID.
        date_from_nullable (str, optional): Start date filter (MM/DD/YYYY).
        date_to_nullable (str, optional): End date filter (MM/DD/YYYY).
        
    Returns:
        str: JSON string containing a list of found games or {'error': ...}.
    """
    logger.info(f"Executing fetch_league_games_logic with params: player_or_team={player_or_team_abbreviation}, player_id={player_id_nullable}, team_id={team_id_nullable}, date_from={date_from_nullable}, date_to={date_to_nullable}")
    
    try:
        # Validate required IDs
        if player_or_team_abbreviation == 'P' and player_id_nullable is None:
            return format_response(error=Errors.PLAYER_ID_REQUIRED)
        if player_or_team_abbreviation == 'T' and team_id_nullable is None:
            return format_response(error=Errors.TEAM_ID_REQUIRED)
        
        # Call LeagueGameFinder endpoint
        gamefinder = leaguegamefinder.LeagueGameFinder(
            player_or_team_abbreviation=player_or_team_abbreviation,
            player_id_nullable=player_id_nullable,
            team_id_nullable=team_id_nullable,
            season_nullable=season_nullable,
            season_type_nullable=season_type_nullable,
            league_id_nullable=league_id_nullable,
            date_from_nullable=date_from_nullable,
            date_to_nullable=date_to_nullable
        )
        
        # Extract game data
        games = gamefinder.league_game_finder_results.get_data_frame().to_dict('records')
        
        # Prepare result
        result = {"games": games}
        
        logger.info(f"fetch_league_games_logic completed. Found {len(games)} games.")
        return format_response(result)
        
    except Exception as e:
        logger.error(f"Error fetching games: {str(e)}", exc_info=True)
        return format_response(error=Errors.LEAGUE_GAMES_API.format(error=str(e)))
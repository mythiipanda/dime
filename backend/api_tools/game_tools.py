import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import re # For parsing live clock
from nba_api.stats.endpoints import boxscoretraditionalv2, playbyplay, shotchartdetail, leaguegamefinder, BoxScoreAdvancedV3, BoxScoreTraditionalV3
# Live PBP endpoint
from nba_api.live.nba.endpoints import PlayByPlay as LivePlayByPlay
# Endpoint to check game status (if needed)
from nba_api.live.nba.endpoints import scoreboard
from backend.config import DEFAULT_TIMEOUT, Errors
from backend.api_tools.utils import _process_dataframe, format_response
# Import relevant parameters
from nba_api.stats.library.parameters import EndPeriod, EndRange, RangeType, StartPeriod, StartRange

logger = logging.getLogger(__name__)

def _format_game_leader(leader_data: Dict) -> Dict:
    """Helper function to format game leader data"""
    return {
        "name": leader_data.get("name", ""),
        "stats": f"{leader_data.get('points', 0)} PTS, {leader_data.get('rebounds', 0)} REB, {leader_data.get('assists', 0)} AST"
    }

def fetch_boxscore_traditional_logic(
    game_id: str, 
    start_period: int = StartPeriod.default, # Use defaults from parameters library
    end_period: int = EndPeriod.default, 
    start_range: int = StartRange.default, 
    end_range: int = EndRange.default,
    range_type: int = RangeType.default
) -> str:
    """
    Fetches detailed traditional box score data using BoxScoreTraditionalV3.
    Allows filtering by period and/or time range within periods.
    
    Args:
        game_id: NBA game ID
        start_period: Start period filter (0 for default/all).
        end_period: End period filter (0 for default/all).
        start_range: Start range filter (0 for default/all).
        end_range: End range filter (0 for default/all).
        range_type: Range type filter (0 for default/all).
        
    Returns:
        JSON string containing box score statistics in an organized format.
    """
    logger.info(f"Executing fetch_boxscore_traditional_logic (V3) for game ID: {game_id}, StartPeriod: {start_period}, EndPeriod: {end_period}, StartRange: {start_range}, EndRange: {end_range}")
    
    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)
    
    try:
        # Use BoxScoreTraditionalV3 with period/range parameters
        boxscore = BoxScoreTraditionalV3(
            game_id=game_id,
            start_period=start_period,
            end_period=end_period,
            start_range=start_range,
            end_range=end_range,
            range_type=range_type,
            timeout=DEFAULT_TIMEOUT
        )
        logger.debug(f"BoxScoreTraditionalV3 API call successful for {game_id}")
        
        # --- Process V3 Data --- 
        
        # Process player stats (lambda function should be mostly correct based on docs)
        player_stats_raw = boxscore.player_stats.get_data_frame()
        logger.debug(f"Processing V3 player stats dataframe for {game_id}")
        player_stats = player_stats_raw.apply(
            lambda row: {
                "player_id": row.get("personId"),
                "name": f'{row.get("firstName", "")} {row.get("familyName", "")}',
                "team": row.get("teamTricode"), 
                "position": row.get("position", ""), 
                "comment": row.get("comment", ""), # Add comment if available
                "jerseyNum": row.get("jerseyNum", ""), # Add jersey number
                "minutes": row.get("minutes", "0"), 
                "points": row.get("points", 0),
                "rebounds": {"offensive": row.get("reboundsOffensive", 0), "defensive": row.get("reboundsDefensive", 0), "total": row.get("reboundsTotal", 0)},
                "assists": row.get("assists", 0), 
                "steals": row.get("steals", 0), 
                "blocks": row.get("blocks", 0),
                "turnovers": row.get("turnovers", 0), 
                "fouls": row.get("foulsPersonal", 0),
                "shooting": {
                    "fg": f'{row.get("fieldGoalsMade", 0)}-{row.get("fieldGoalsAttempted", 0)}', 
                    "fg_pct": row.get("fieldGoalsPercentage", 0.0),
                    "fg3": f'{row.get("threePointersMade", 0)}-{row.get("threePointersAttempted", 0)}', 
                    "fg3_pct": row.get("threePointersPercentage", 0.0),
                    "ft": f'{row.get("freeThrowsMade", 0)}-{row.get("freeThrowsAttempted", 0)}', 
                    "ft_pct": row.get("freeThrowsPercentage", 0.0)
                },
                "plus_minus": row.get("plusMinusPoints", 0)
            }, axis=1
        ).tolist() if not player_stats_raw.empty else []
        logger.debug(f"V3 Player stats processing complete for {game_id}")

        # Process team stats (lambda function should be mostly correct based on docs)
        team_stats_raw = boxscore.team_stats.get_data_frame()
        logger.debug(f"Processing V3 team stats dataframe for {game_id}")
        team_stats = team_stats_raw.apply(
            lambda row: {
                "team_id": row.get("teamId"), 
                "name": f'{row.get("teamCity", "")} {row.get("teamName", "")}',
                "abbreviation": row.get("teamTricode"), 
                "minutes": row.get("minutes", "0"), # Add minutes for team
                "points": row.get("points", 0),
                "rebounds": {"offensive": row.get("reboundsOffensive", 0), "defensive": row.get("reboundsDefensive", 0), "total": row.get("reboundsTotal", 0)},
                "assists": row.get("assists", 0), 
                "steals": row.get("steals", 0), 
                "blocks": row.get("blocks", 0),
                "turnovers": row.get("turnovers", 0), 
                "fouls": row.get("foulsPersonal", 0),
                "shooting": {
                    "fg": f'{row.get("fieldGoalsMade", 0)}-{row.get("fieldGoalsAttempted", 0)}', 
                    "fg_pct": round(row.get("fieldGoalsPercentage", 0.0), 3),
                    "fg3": f'{row.get("threePointersMade", 0)}-{row.get("threePointersAttempted", 0)}', 
                    "fg3_pct": round(row.get("threePointersPercentage", 0.0), 3),
                    "ft": f'{row.get("freeThrowsMade", 0)}-{row.get("freeThrowsAttempted", 0)}', 
                    "ft_pct": round(row.get("freeThrowsPercentage", 0.0), 3)
                },
                 "plus_minus": row.get("plusMinusPoints", 0)
            }, axis=1
        ).tolist() if not team_stats_raw.empty else []
        logger.debug(f"V3 Team stats processing complete for {game_id}")

        # Re-introduce processing for starters/bench stats
        starters_bench_raw = boxscore.team_starter_bench_stats.get_data_frame()
        logger.debug(f"Processing V3 team_starter_bench_stats dataframe for {game_id}")
        starters_bench = starters_bench_raw.apply(
            lambda row: {
                # Using V3 column names from docs
                "team_id": row.get("teamId"), 
                "team_abbreviation": row.get("teamTricode"), # Use Tricode for consistency
                "group": row.get("startersBench"), # Key V3 column
                "minutes": row.get("minutes", "0"),
                "points": row.get("points", 0),
                "rebounds": {"offensive": row.get("reboundsOffensive", 0), "defensive": row.get("reboundsDefensive", 0), "total": row.get("reboundsTotal", 0)},
                "assists": row.get("assists", 0), 
                "steals": row.get("steals", 0), 
                "blocks": row.get("blocks", 0),
                "turnovers": row.get("turnovers", 0), 
                "fouls": row.get("foulsPersonal", 0),
                 "shooting": {
                    "fg": f'{row.get("fieldGoalsMade", 0)}-{row.get("fieldGoalsAttempted", 0)}', 
                    "fg_pct": round(row.get("fieldGoalsPercentage", 0.0), 3),
                    "fg3": f'{row.get("threePointersMade", 0)}-{row.get("threePointersAttempted", 0)}', 
                    "fg3_pct": round(row.get("threePointersPercentage", 0.0), 3),
                    "ft": f'{row.get("freeThrowsMade", 0)}-{row.get("freeThrowsAttempted", 0)}', 
                    "ft_pct": round(row.get("freeThrowsPercentage", 0.0), 3)
                }
            }, axis=1
        ).tolist() if not starters_bench_raw.empty else []
        logger.debug(f"V3 Starters/Bench stats processing complete for {game_id}")
        
        # Combine V3 results, including starters/bench and updated params
        result = {
            "game_id": game_id,
            "parameters": { 
                "start_period": start_period,
                "end_period": end_period,
                "start_range": start_range,
                "end_range": end_range,
                "range_type": range_type,
                "note": "Using BoxScoreTraditionalV3"
            },
            "teams": team_stats,
            "players": player_stats,
            "starters_bench": starters_bench # Re-added
        }
        
        logger.info(f"fetch_boxscore_traditional_logic (V3) completed for game {game_id}")
        # Log the result dict before formatting
        logger.debug(f"Result dictionary before formatting for {game_id}: {json.dumps(result, default=str)[:1000]}...")
        # Original return call was correct
        return format_response(result)
        
    except Exception as e:
        logger.error(f"Error fetching boxscore (V3) for game {game_id}: {str(e)}", exc_info=True)
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
                "team": team_str,
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
def fetch_playbyplay_logic(game_id: str, start_period: int = 0, end_period: int = 0) -> str:
    """
    Fetches play-by-play data, trying the live endpoint first and falling back to historical.
    Period filtering only applies if historical data is used.
    Args:
        game_id: NBA game ID
        start_period (int, optional): Starting period filter (0 for all). Applies only to historical fallback.
        end_period (int, optional): Ending period filter (0 for all). Applies only to historical fallback.
    Returns:
        JSON string containing play-by-play data or error message.
    """
    logger.info(f"Executing fetch_playbyplay_logic for game ID: {game_id}, StartPeriod: {start_period}, EndPeriod: {end_period}")
    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)

    try:
        # Try live endpoint first
        logger.debug(f"Attempting live PBP fetch for game {game_id}")
        result = _fetch_live_playbyplay_logic(game_id)
        logger.info(f"Live PBP fetch successful for game {game_id}")
        result["parameters"] = {"start_period": 0, "end_period": 0, "note": "Period filter NA for live data"}
        return format_response(data=result)
    except ValueError as live_error: # Specific error raised if not live
        logger.warning(f"Live PBP fetch failed for game {game_id} ({live_error}), attempting historical.")
        try:
            # Fallback to historical endpoint, passing period filters
            result = _fetch_historical_playbyplay_logic(game_id, start_period, end_period)
            logger.info(f"Historical PBP fetch successful for game {game_id}")
            result["parameters"] = {"start_period": start_period, "end_period": end_period}
            return format_response(data=result)
        except Exception as hist_error:
            logger.error(f"Historical PBP fetch also failed for game {game_id}: {hist_error}", exc_info=True)
            return format_response(error=Errors.PBP_API.format(game_id=game_id, error=str(hist_error)))
    except Exception as e:
        logger.error(f"Unexpected error fetching PBP for game {game_id}: {e}", exc_info=True)
        return format_response(error=Errors.PBP_API.format(game_id=game_id, error=str(e)))

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
        
        # Process shot chart data using apply
        shots_raw = shotchart.shot_chart_detail.get_data_frame()
        shots = shots_raw.apply(
            lambda row: {
                "player": {"id": row.get("PLAYER_ID"), "name": row.get("PLAYER_NAME")},
                "team": {"id": row.get("TEAM_ID"), "name": row.get("TEAM_NAME")},
                "period": row.get("PERIOD"),
                "time_remaining": f"{row.get('MINUTES_REMAINING')}:{str(row.get('SECONDS_REMAINING')).zfill(2)}",
                "shot_type": row.get("SHOT_TYPE"),
                "shot_zone": {"basic": row.get("SHOT_ZONE_BASIC"), "area": row.get("SHOT_ZONE_AREA"), "range": row.get("SHOT_ZONE_RANGE")},
                "distance": row.get("SHOT_DISTANCE"),
                "coordinates": {"x": row.get("LOC_X"), "y": row.get("LOC_Y")},
                "made": row.get("SHOT_MADE_FLAG") == 1,
                "action_type": row.get("ACTION_TYPE")
            }, axis=1
        ).tolist() if not shots_raw.empty else []

        # Process league averages using apply
        league_avgs_raw = shotchart.league_averages.get_data_frame()
        league_avgs = league_avgs_raw.apply(
            lambda row: {
                "zone_basic": row.get("SHOT_ZONE_BASIC"), "zone_area": row.get("SHOT_ZONE_AREA"), "zone_range": row.get("SHOT_ZONE_RANGE"),
                "attempts": row.get("FGA"), "made": row.get("FGM"), "pct": row.get("FG_PCT")
            }, axis=1
        ).tolist() if not league_avgs_raw.empty else []
        
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

        if games_df.empty:
            logger.warning("No league games found for the specified filters.")
            return format_response({"games": []})

        # Select essential columns for game results
        essential_cols = [
            'GAME_ID', 'GAME_DATE_EST', 'MATCHUP', 'WL', 'PTS', 'FG_PCT',
            'FT_PCT', 'FG3_PCT', 'AST', 'REB', 'TOV', 'STL', 'BLK'
        ]
        # Ensure all essential columns exist in the DataFrame before selecting
        available_cols = [col for col in essential_cols if col in games_df.columns]
        games_df_selected = games_df.loc[:, available_cols]

        # If no specific filters are applied, limit the number of games returned
        if all(param is None for param in [player_id_nullable, team_id_nullable, season_nullable, season_type_nullable, date_from_nullable, date_to_nullable]):
             logger.info(f"Limiting league-wide game list to the top 200 games.")
             games_df_selected = games_df_selected.head(200) # Limit to the first 200 rows

        # Convert dataframe to list of dicts
        games_list = games_df_selected.to_dict(orient='records')

        # Format dates for better readability if needed (using GAME_DATE_EST which is already datetime-like)
        for game in games_list:
            if 'GAME_DATE_EST' in game and isinstance(game['GAME_DATE_EST'], str):
                try:
                    # Attempt to parse and reformat date
                    # Assuming GAME_DATE_EST is in a format like 'YYYY-MM-DDTHH:MM:SS'
                    parsed_date = datetime.fromisoformat(game['GAME_DATE_EST'].replace('Z', '+00:00')) # Handle potential 'Z' timezone
                    game['GAME_DATE_FORMATTED'] = parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    game['GAME_DATE_FORMATTED'] = game['GAME_DATE_EST'] # Keep original if parsing fails

        result = {"games": games_list}
        logger.info(f"fetch_league_games_logic found {len(games_list)} games.")
        return format_response(result)
        
    except Exception as e:
        logger.error(f"Error fetching league games: {str(e)}", exc_info=True)
        return format_response(error=Errors.LEAGUE_GAMES_API.format(error=str(e)))

# Advanced Box Score V3 Logic
def fetch_boxscore_advanced_logic(game_id: str, end_period: int = 0, end_range: int = 0, start_period: int = 0, start_range: int = 0) -> str:
    """
    Fetches advanced box score data using BoxScoreAdvancedV3 for a specific game.

    Args:
        game_id (str): The 10-digit ID of the game.
        end_period (int): End period filter (default 0).
        end_range (int): End range filter (default 0).
        start_period (int): Start period filter (default 0).
        start_range (int): Start range filter (default 0).

    Returns:
        str: JSON string containing advanced player and team stats or an error message.
    """
    logger.info(f"Executing fetch_boxscore_advanced_logic (V3) for game ID: {game_id}")
    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)

    try:
        # Use BoxScoreAdvancedV3 exclusively
        boxscore_adv = BoxScoreAdvancedV3(
            game_id=game_id,
            end_period=end_period,
            end_range=end_range,
            start_period=start_period,
            start_range=start_range,
            timeout=DEFAULT_TIMEOUT
        )
        logger.debug(f"BoxScoreAdvancedV3 API call successful for {game_id}")
        
        # Process player stats
        player_stats_df = boxscore_adv.player_stats.get_data_frame()
        logger.debug(f"Processing player stats dataframe for {game_id}")
        # Select essential columns for advanced player stats
        player_advanced_cols = [
            'personId', 'firstName', 'familyName', 'teamTricode', 'minutes',
            'efficiency', 'assistPercentage', 'assistRatio', 'assistToTurnover',
            'defensiveRating', 'effectiveFieldGoalPercentage', 'netRating',
            'offensiveRating', 'pace', 'playerEfficiencyRating', 'possessions',
            'trueShootingPercentage', 'turnoverRatio', 'usagePercentage'
        ]
        available_player_advanced_cols = [col for col in player_advanced_cols if col in player_stats_df.columns]
        player_stats = _process_dataframe(player_stats_df.loc[:, available_player_advanced_cols] if not player_stats_df.empty else player_stats_df)
        logger.debug(f"Player stats processing complete for {game_id}")
        
        # Process team stats
        team_stats_df = boxscore_adv.team_stats.get_data_frame()
        logger.debug(f"Processing team stats dataframe for {game_id}")
        # Select essential columns for advanced team stats
        team_advanced_cols = [
            'teamId', 'teamCity', 'teamName', 'teamTricode', 'minutes',
            'efficiency', 'assistPercentage', 'assistRatio', 'assistToTurnover',
            'defensiveRating', 'effectiveFieldGoalPercentage', 'netRating',
            'offensiveRating', 'pace', 'playerEfficiencyRating', 'possessions',
            'trueShootingPercentage', 'turnoverRatio', 'usagePercentage'
        ]
        available_team_advanced_cols = [col for col in team_advanced_cols if col in team_stats_df.columns]
        team_stats = _process_dataframe(team_stats_df.loc[:, available_team_advanced_cols] if not team_stats_df.empty else team_stats_df)
        logger.debug(f"Team stats processing complete for {game_id}")

        result = {
            "game_id": game_id,
            "parameters": {
                 "start_period": start_period,
                 "end_period": end_period,
                 "start_range": start_range,
                 "end_range": end_range
            },
            "player_stats": player_stats,
            "team_stats": team_stats
        }
        logger.info(f"Successfully fetched advanced box score V3 for game {game_id}")
        formatted_response = format_response(data=result)
        logger.debug(f"Formatted response for {game_id}: {formatted_response[:500]}...") # Log beginning of response
        return formatted_response

    # Catch specific IndexError which might indicate unavailable data for the game ID
    except IndexError as ie:
        logger.warning(f"IndexError during BoxScoreAdvancedV3 processing for game {game_id}: {ie}. Data likely unavailable.", exc_info=True)
        # Return a more specific error message
        error_msg = Errors.DATA_NOT_FOUND + f" (Advanced box score data might be unavailable for game {game_id})"
        error_response = format_response(error=error_msg)
        logger.error(f"Formatted specific error response for {game_id}: {error_response}")
        return error_response
    # Keep catching other potential exceptions
    except Exception as e:
        # Log the error *before* formatting the response
        logger.error(f"Error during fetch_boxscore_advanced_logic for game {game_id}: {str(e)}", exc_info=True)
        # Format the error response using the message from config.py
        error_response = format_response(error=Errors.BOXSCORE_ADVANCED_API.format(game_id=game_id, error=str(e)))
        logger.error(f"Formatted error response for {game_id}: {error_response}")
        return error_response

# Four Factors Box Score Logic
def fetch_boxscore_four_factors_logic(
    game_id: str,
    start_period: int = 0,
    end_period: int = 0
) -> str:
    """
    Fetches box score four factors (V3) for a specific game.

    The Four Factors are:
    1. Effective Field Goal Percentage (eFG%)
    2. Turnover Rate
    3. Offensive Rebounding Rate
    4. Free Throw Rate

    Args:
        game_id (str): The 10-digit ID of the game
        start_period (int): Starting period filter (0 for all)
        end_period (int): Ending period filter (0 for all)

    Returns:
        str: JSON string containing:
            - game_id (str)
            - parameters (dict): The period filters used
            - player_stats (list[dict]): Individual player four factors:
                - personId, firstName, familyName, teamTricode, position
                - minutes
                - effectiveFieldGoalPercentage, freeThrowAttemptRate
                - teamTurnoverPercentage, offensiveReboundPercentage
                - oppEffectiveFieldGoalPercentage, oppFreeThrowAttemptRate
                - oppTeamTurnoverPercentage, oppOffensiveReboundPercentage
            - team_stats (list[dict]): Team level four factors with same stats
            Or {'error': ...} if an error occurs
    """
    logger.info(f"Executing fetch_boxscore_four_factors_logic for game ID: {game_id}")

    if not game_id:
        return format_response(error=Errors.GAME_ID_EMPTY)

    try:
        from nba_api.stats.endpoints.boxscorefourfactorsv3 import BoxScoreFourFactorsV3

        boxscore = BoxScoreFourFactorsV3(
            game_id=game_id,
            start_period=start_period,
            end_period=end_period,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Process player stats
        player_stats_df = boxscore.player_stats.get_data_frame()
        player_cols = [
            'personId', 'firstName', 'familyName', 'teamTricode', 'position', 'minutes',
            'effectiveFieldGoalPercentage', 'freeThrowAttemptRate', 'teamTurnoverPercentage',
            'offensiveReboundPercentage', 'oppEffectiveFieldGoalPercentage',
            'oppFreeThrowAttemptRate', 'oppTeamTurnoverPercentage', 'oppOffensiveReboundPercentage'
        ]
        available_player_cols = [col for col in player_cols if col in player_stats_df.columns]
        player_stats = _process_dataframe(player_stats_df.loc[:, available_player_cols] if not player_stats_df.empty else player_stats_df)

        # Process team stats
        team_stats_df = boxscore.team_stats.get_data_frame()
        team_cols = [
            'teamId', 'teamCity', 'teamName', 'teamTricode', 'minutes',
            'effectiveFieldGoalPercentage', 'freeThrowAttemptRate', 'teamTurnoverPercentage',
            'offensiveReboundPercentage', 'oppEffectiveFieldGoalPercentage',
            'oppFreeThrowAttemptRate', 'oppTeamTurnoverPercentage', 'oppOffensiveReboundPercentage'
        ]
        available_team_cols = [col for col in team_cols if col in team_stats_df.columns]
        team_stats = _process_dataframe(team_stats_df.loc[:, available_team_cols] if not team_stats_df.empty else team_stats_df)

        result = {
            "game_id": game_id,
            "parameters": {
                "start_period": start_period,
                "end_period": end_period
            },
            "player_stats": player_stats,
            "team_stats": team_stats
        }

        logger.info(f"Successfully fetched four factors box score for game {game_id}")
        return format_response(result)

    except Exception as e:
        logger.error(f"Error in fetch_boxscore_four_factors_logic for game {game_id}: {str(e)}", exc_info=True)
        return format_response(error=Errors.BOXSCORE_API.format(game_id=game_id, error=str(e)))

# Usage Box Score Logic
def fetch_boxscore_usage_logic(game_id: str) -> str:
    """Fetches box score usage stats V3 data for a specific game."""
    logger.info(f"Executing fetch_boxscore_usage_logic for game {game_id}")
    try:
        from nba_api.stats.endpoints.boxscoreusagev3 import BoxScoreUsageV3
        usage = BoxScoreUsageV3(game_id=game_id, timeout=DEFAULT_TIMEOUT)
        df = usage.player_stats.get_data_frame()

        if df.empty:
            logger.warning(f"No usage stats found for game {game_id}.")
            return format_response({"game_id": game_id, "usage_stats": []})

        # Select essential columns for usage stats
        usage_cols = [
            'personId', 'firstName', 'familyName', 'teamTricode', 'minutes',
            'usagePercentage', 'teamPlayPercentage', 'playerPlayPercentage',
            'playerFoulOutPercentage'
        ]
        available_usage_cols = [col for col in usage_cols if col in df.columns]
        usage_stats = df.loc[:, available_usage_cols].to_dict('records')

        result = {"game_id": game_id, "usage_stats": usage_stats}
        return format_response(result)
    except Exception as e:
        logger.error(f"Error fetching usage stats for {game_id}: {e}", exc_info=True)
        return format_response(error=Errors.BOXSCORE_API.format(game_id=game_id, error=str(e)))

# Defensive Box Score Logic
def fetch_boxscore_defensive_logic(game_id: str) -> str:
    """Fetches box score defensive stats V2 data for a specific game."""
    logger.info(f"Executing fetch_boxscore_defensive_logic for game {game_id}")
    try:
        from nba_api.stats.endpoints.boxscoredefensivev2 import BoxScoreDefensiveV2
        dfend = BoxScoreDefensiveV2(game_id=game_id, timeout=DEFAULT_TIMEOUT)
        df = dfend.player_stats.get_data_frame()

        if df.empty:
            logger.warning(f"No defensive stats found for game {game_id}.")
            return format_response({"game_id": game_id, "defensive_stats": []})

        # Select essential columns for defensive stats
        defensive_cols = [
            'personId', 'firstName', 'familyName', 'teamTricode', 'minutes',
            'dreb', 'stl', 'blk', 'contestedShots', 'contestedShots2pt',
            'contestedShots3pt', 'deflections', 'chargesDrawn', 'screenAssists',
            'screenAssistPoints', 'looseBallsRecovered', 'looseBallsRecoveredOffensive',
            'looseBallsRecoveredDefensive', 'boxOuts', 'boxOutsOffensive',
            'boxOutsDefensive'
        ]
        available_defensive_cols = [col for col in defensive_cols if col in df.columns]
        defensive_stats = df.loc[:, available_defensive_cols].to_dict('records')

        result = {"game_id": game_id, "defensive_stats": defensive_stats}
        return format_response(result)
    except Exception as e:
        logger.error(f"Error fetching defensive stats for {game_id}: {e}", exc_info=True)
        return format_response(error=Errors.BOXSCORE_API.format(game_id=game_id, error=str(e)))

# Win Probability Logic
def fetch_win_probability_logic(game_id: str, run_type: str = "0") -> str:
    """Fetches win probability play-by-play data for a specific game."""
    logger.info(f"Executing fetch_win_probability_logic for game {game_id}")
    try:
        from nba_api.stats.endpoints.winprobabilitypbp import WinProbabilityPBP
        wp = WinProbabilityPBP(game_id=game_id, run_type=run_type, timeout=DEFAULT_TIMEOUT)
        info_df = wp.game_info.get_data_frame()
        prob_df = wp.win_prob_p_bp.get_data_frame()
        info = info_df.iloc[0].to_dict() if not info_df.empty else {}
        probs = prob_df.to_dict('records') if not prob_df.empty else []
        result = {"game_id": game_id, "game_info": info, "win_probability": probs}
        return format_response(result)
    except Exception as e:
        logger.error(f"Error fetching win probability for {game_id}: {e}", exc_info=True)
        return format_response(error=Errors.PBP_API.format(game_id=game_id, error=str(e)))
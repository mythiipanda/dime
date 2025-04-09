import logging
import json
import requests
from typing import Optional, Dict, Any
import pandas as pd
# Import new endpoints
from nba_api.stats.endpoints import leaguegamefinder, boxscoretraditionalv3, playbyplayv3, boxscoreadvancedv3, boxscorefourfactorsv3, shotchartdetail, hustlestatsboxscore # Added shotchartdetail and hustlestatsboxscore
from nba_api.stats.library.parameters import LeagueID, SeasonTypeNullable, SeasonNullable

from .utils import _process_dataframe
from config import DEFAULT_TIMEOUT, MAX_GAMES_TO_RETURN, ErrorMessages as Errors

logger = logging.getLogger(__name__)

def fetch_league_games_logic(
    player_or_team_abbreviation: str = 'T',
    player_id_nullable: Optional[int] = None,
    team_id_nullable: Optional[int] = None,
    season_nullable: Optional[SeasonNullable] = None,
    season_type_nullable: Optional[SeasonTypeNullable] = SeasonTypeNullable.regular,
    league_id_nullable: Optional[LeagueID] = LeagueID.nba,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None
) -> str:
    """
    Fetches games using LeagueGameFinder based on criteria.
    Returns JSON string.
    """
    logger.info(f"Executing fetch_league_games_logic with params: player/team={player_or_team_abbreviation}, player_id={player_id_nullable}, team_id={team_id_nullable}, season={season_nullable}, type={season_type_nullable}, league={league_id_nullable}, date_from={date_from_nullable}, date_to={date_to_nullable}")

    if player_or_team_abbreviation not in ['P', 'T']:
        return json.dumps({"error": Errors.INVALID_PLAYER_OR_TEAM})
    if player_or_team_abbreviation == 'P' and player_id_nullable is None:
        return json.dumps({"error": Errors.MISSING_PLAYER_ID})
    if player_or_team_abbreviation == 'T' and team_id_nullable is None:
        return json.dumps({"error": Errors.MISSING_TEAM_ID})

    try:
        game_finder = leaguegamefinder.LeagueGameFinder(
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
        logger.debug("LeagueGameFinder API call successful.")

        games_df = game_finder.league_game_finder_results.get_data_frame()
        total_games_found = len(games_df) if games_df is not None else 0

        if games_df is None or games_df.empty:
            games_list = []
        else:
            games_df_sorted = games_df.sort_values(by='GAME_DATE', ascending=False)
            games_df_limited = games_df_sorted.head(MAX_GAMES_TO_RETURN)
            games_list = _process_dataframe(games_df_limited, single_row=False)

        if games_list is None:
            logger.error(Errors.FIND_GAMES_PROCESSING)
            return json.dumps({"error": Errors.FIND_GAMES_PROCESSING})

        result = {
            "total_games_found": total_games_found,
            "games_returned": len(games_list),
            "games": games_list
        }
        logger.info(f"fetch_league_games_logic completed. Found {total_games_found} games, returning {len(games_list)}.")
        return json.dumps(result, default=str)

    except Exception as e:
        logger.critical(Errors.FIND_GAMES_UNEXPECTED.format(error=str(e)), exc_info=True)
        return json.dumps({"error": Errors.FIND_GAMES_UNEXPECTED.format(error=str(e))})

def fetch_boxscore_traditional_logic(game_id: str) -> str:
    """
    Fetches traditional box score stats (V3) for a specific game.
    Returns JSON string with player and team stats.
    """
    logger.info(f"Executing fetch_boxscore_traditional_logic for game_id: '{game_id}'")
    if not game_id or not game_id.strip():
        return json.dumps({"error": Errors.GAME_ID_EMPTY}) # Need to add this error message
    if not game_id.isdigit() or len(game_id) != 10:
         return json.dumps({"error": Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id)}) # Need to add this error message

    try:
        logger.debug(f"Fetching boxscoretraditionalv3 for game ID: {game_id}")
        try:
            boxscore_endpoint = boxscoretraditionalv3.BoxScoreTraditionalV3(
                game_id=game_id,
                # Default values for range/period seem okay for full game stats
                start_period='0',
                end_period='0',
                start_range='0',
                end_range='0',
                range_type='0',
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"boxscoretraditionalv3 API call successful for game ID: {game_id}")
        except Exception as api_error:
            logger.error(f"nba_api boxscoretraditionalv3 failed for game ID {game_id}: {api_error}", exc_info=True)
            return json.dumps({"error": Errors.BOXSCORE_API.format(game_id=game_id, error=str(api_error))}) # Need to add this error message

        player_stats_list = _process_dataframe(boxscore_endpoint.player_stats.get_data_frame(), single_row=False)
        team_stats_list = _process_dataframe(boxscore_endpoint.team_stats.get_data_frame(), single_row=False) # Should be 2 rows (teams)

        if player_stats_list is None or team_stats_list is None:
            logger.error(f"DataFrame processing failed for boxscore of game {game_id}.")
            return json.dumps({"error": Errors.BOXSCORE_PROCESSING.format(game_id=game_id)}) # Need to add this error message

        result = {
            "game_id": game_id,
            "player_stats": player_stats_list or [],
            "team_stats": team_stats_list or []
        }
        logger.info(f"fetch_boxscore_traditional_logic completed for game ID: {game_id}")
        return json.dumps(result, default=str)

    except Exception as e:
        logger.critical(f"Unexpected error in fetch_boxscore_traditional_logic for game ID '{game_id}': {e}", exc_info=True)
        return json.dumps({"error": Errors.BOXSCORE_UNEXPECTED.format(game_id=game_id, error=str(e))}) # Need to add this error message

def fetch_playbyplay_logic(game_id: str, start_period: int = 0, end_period: int = 0) -> str:
    """
    Fetches play-by-play data (V3) for a specific game, optionally filtered by period.
    Returns JSON string.
    """
    logger.info(f"Executing fetch_playbyplay_logic for game_id: '{game_id}', StartPeriod: {start_period}, EndPeriod: {end_period}")
    if not game_id or not game_id.strip():
        return json.dumps({"error": Errors.GAME_ID_EMPTY})
    if not game_id.isdigit() or len(game_id) != 10:
         return json.dumps({"error": Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id)})

    # Ensure periods are strings for the API call
    start_period_str = str(start_period)
    end_period_str = str(end_period)

    try:
        logger.debug(f"Fetching playbyplayv3 for game ID: {game_id}, Start: {start_period_str}, End: {end_period_str}")
        try:
            pbp_endpoint = playbyplayv3.PlayByPlayV3(
                game_id=game_id,
                start_period=start_period_str,
                end_period=end_period_str,
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"playbyplayv3 API call successful for game ID: {game_id}")
        except Exception as api_error:
            logger.error(f"nba_api playbyplayv3 failed for game ID {game_id}: {api_error}", exc_info=True)
            return json.dumps({"error": Errors.PLAYBYPLAY_API.format(game_id=game_id, error=str(api_error))}) # Need to add this error message

        # The main data is in the 'actions' attribute
        pbp_list = _process_dataframe(pbp_endpoint.play_by_play.get_data_frame(), single_row=False)

        if pbp_list is None:
            logger.error(f"DataFrame processing failed for play-by-play of game {game_id}.")
            return json.dumps({"error": Errors.PLAYBYPLAY_PROCESSING.format(game_id=game_id)}) # Need to add this error message

        result = {
            "game_id": game_id,
            "start_period_requested": start_period,
            "end_period_requested": end_period,
            "actions": pbp_list or []
        }
        logger.info(f"fetch_playbyplay_logic completed for game ID: {game_id}")
        return json.dumps(result, default=str)

    except Exception as e:
        logger.critical(f"Unexpected error in fetch_playbyplay_logic for game ID '{game_id}': {e}", exc_info=True)
        return json.dumps({"error": Errors.PLAYBYPLAY_UNEXPECTED.format(game_id=game_id, error=str(e))}) # Need to add this error message

def fetch_boxscore_advanced_logic(game_id: str) -> str:
    """
    Fetches advanced box score stats (V3) for a specific game.
    Returns JSON string with player and team stats.
    """
    logger.info(f"Executing fetch_boxscore_advanced_logic for game_id: '{game_id}'")
    if not game_id or not game_id.strip():
        return json.dumps({"error": Errors.GAME_ID_EMPTY})
    if not game_id.isdigit() or len(game_id) != 10:
         return json.dumps({"error": Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id)})

    try:
        logger.debug(f"Fetching boxscoreadvancedv3 for game ID: {game_id}")
        try:
            boxscore_endpoint = boxscoreadvancedv3.BoxScoreAdvancedV3(
                game_id=game_id,
                # Default values for range/period seem okay for full game stats
                start_period='0',
                end_period='0',
                start_range='0',
                end_range='0',
                range_type='0',
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"boxscoreadvancedv3 API call successful for game ID: {game_id}")
        except Exception as api_error:
            logger.error(f"nba_api boxscoreadvancedv3 failed for game ID {game_id}: {api_error}", exc_info=True)
            # Use specific error message for advanced boxscore API failure
            return json.dumps({"error": Errors.BOXSCORE_ADVANCED_API.format(game_id=game_id, error=str(api_error))}) # Need to add this error message

        player_stats_list = _process_dataframe(boxscore_endpoint.player_stats.get_data_frame(), single_row=False)
        team_stats_list = _process_dataframe(boxscore_endpoint.team_stats.get_data_frame(), single_row=False) # Should be 2 rows (teams)

        if player_stats_list is None or team_stats_list is None:
            logger.error(f"DataFrame processing failed for advanced boxscore of game {game_id}.")
            # Use specific error message for advanced boxscore processing failure
            return json.dumps({"error": Errors.BOXSCORE_ADVANCED_PROCESSING.format(game_id=game_id)}) # Need to add this error message

        result = {
            "game_id": game_id,
            "player_stats_advanced": player_stats_list or [],
            "team_stats_advanced": team_stats_list or []
        }
        logger.info(f"fetch_boxscore_advanced_logic completed for game ID: {game_id}")
        return json.dumps(result, default=str)

    except Exception as e:
        logger.critical(f"Unexpected error in fetch_boxscore_advanced_logic for game ID '{game_id}': {e}", exc_info=True)
        # Use specific error message for unexpected advanced boxscore errors
        return json.dumps({"error": Errors.BOXSCORE_ADVANCED_UNEXPECTED.format(game_id=game_id, error=str(e))}) # Need to add this error message

def fetch_boxscore_fourfactors_logic(game_id: str) -> str:
    """
    Fetches Four Factors box score stats (V3) for a specific game.
    Returns JSON string with player and team stats.
    """
    logger.info(f"Executing fetch_boxscore_fourfactors_logic for game_id: '{game_id}'")
    if not game_id or not game_id.strip():
        return json.dumps({"error": Errors.GAME_ID_EMPTY})
    if not game_id.isdigit() or len(game_id) != 10:
         return json.dumps({"error": Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id)})

    try:
        logger.debug(f"Fetching boxscorefourfactorsv3 for game ID: {game_id}")
        try:
            boxscore_endpoint = boxscorefourfactorsv3.BoxScoreFourFactorsV3(
                game_id=game_id,
                # Default values for range/period seem okay for full game stats
                start_period='0',
                end_period='0',
                start_range='0',
                end_range='0',
                range_type='0',
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"boxscorefourfactorsv3 API call successful for game ID: {game_id}")
        except Exception as api_error:
            logger.error(f"nba_api boxscorefourfactorsv3 failed for game ID {game_id}: {api_error}", exc_info=True)
            # Use specific error message for four factors API failure
            return json.dumps({"error": Errors.BOXSCORE_FOURFACTORS_API.format(game_id=game_id, error=str(api_error))}) # Need to add this error message

        player_stats_list = _process_dataframe(boxscore_endpoint.player_stats.get_data_frame(), single_row=False)
        team_stats_list = _process_dataframe(boxscore_endpoint.team_stats.get_data_frame(), single_row=False) # Should be 2 rows (teams)

        if player_stats_list is None or team_stats_list is None:
            logger.error(f"DataFrame processing failed for four factors boxscore of game {game_id}.")
            # Use specific error message for four factors processing failure
            return json.dumps({"error": Errors.BOXSCORE_FOURFACTORS_PROCESSING.format(game_id=game_id)}) # Need to add this error message

        result = {
            "game_id": game_id,
            "player_stats_fourfactors": player_stats_list or [],
            "team_stats_fourfactors": team_stats_list or []
        }
        logger.info(f"fetch_boxscore_fourfactors_logic completed for game ID: {game_id}")
        return json.dumps(result, default=str)

    except Exception as e:
        logger.critical(f"Unexpected error in fetch_boxscore_fourfactors_logic for game ID '{game_id}': {e}", exc_info=True)
        # Use specific error message for unexpected four factors errors
        return json.dumps({"error": Errors.BOXSCORE_FOURFACTORS_UNEXPECTED.format(game_id=game_id, error=str(e))}) # Need to add this error message

def fetch_game_boxscore_logic(game_id: str) -> str:
    """
    Fetches box score data for a specific game.
    Args:
        game_id (str): The ID of the game to fetch box score data for
    Returns:
        str: JSON string containing box score data or error message
    """
    logger.info(f"Executing fetch_game_boxscore_logic for game_id: '{game_id}'")
    
    # Validate game_id
    if not game_id:
        return json.dumps({"error": Errors.GAME_ID_EMPTY})
    if not game_id.isdigit() or len(game_id) != 10:
        return json.dumps({"error": Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id)})
    
    try:
        # Fetch box score data
        boxscore = boxscoretraditionalv3.BoxScoreTraditionalV3(
            game_id=game_id,
            start_period='0',
            end_period='0',
            start_range='0',
            end_range='0',
            range_type='0',
            timeout=DEFAULT_TIMEOUT
        )
        
        # Get normalized data
        data = boxscore.get_normalized_dict()
        if not data:
            return json.dumps({"error": f"No boxscore data found for game {game_id}"})
        
        # Extract player and team stats
        player_stats = data.get('PlayerStats', [])
        team_stats = data.get('TeamStats', [])
        
        if not team_stats or len(team_stats) != 2:
            return json.dumps({"error": f"Invalid team stats data for game {game_id}"})
        
        # Organize players by team
        home_team = team_stats[0]
        away_team = team_stats[1]
        
        home_team_id = str(home_team.get('teamId', ''))
        away_team_id = str(away_team.get('teamId', ''))
        
        # Format player stats
        home_players = []
        away_players = []
        
        for player in player_stats:
            player_team_id = str(player.get('teamId', ''))
            formatted_player = {
                "player_id": str(player.get('personId', '')),
                "player_name": player.get('name', ''),
                "team_id": player_team_id,
                "minutes": player.get('minutes', '0'),
                "points": player.get('points', 0),
                "rebounds": player.get('reboundsTotal', 0),
                "assists": player.get('assists', 0),
                "steals": player.get('steals', 0),
                "blocks": player.get('blocks', 0),
                "turnovers": player.get('turnovers', 0),
                "fouls": player.get('foulsPersonal', 0),
                "fg_made": player.get('fieldGoalsMade', 0),
                "fg_attempted": player.get('fieldGoalsAttempted', 0),
                "fg_pct": player.get('fieldGoalsPercentage', 0),
                "fg3_made": player.get('threePointersMade', 0),
                "fg3_attempted": player.get('threePointersAttempted', 0),
                "fg3_pct": player.get('threePointersPercentage', 0),
                "ft_made": player.get('freeThrowsMade', 0),
                "ft_attempted": player.get('freeThrowsAttempted', 0),
                "ft_pct": player.get('freeThrowsPercentage', 0)
            }
            
            if player_team_id == home_team_id:
                home_players.append(formatted_player)
            elif player_team_id == away_team_id:
                away_players.append(formatted_player)
        
        result = {
            "game_id": game_id,
            "home_team": {
                "team_id": home_team_id,
                "team_name": home_team.get('teamCity', '') + ' ' + home_team.get('teamName', ''),
                "players": home_players
            },
            "away_team": {
                "team_id": away_team_id,
                "team_name": away_team.get('teamCity', '') + ' ' + away_team.get('teamName', ''),
                "players": away_players
            }
        }
        
        return json.dumps(result)
        
    except requests.exceptions.Timeout:
        logger.error(f"Request timed out for game ID: {game_id}")
        return json.dumps({
            "error": f"Request timed out for game ID: {game_id}",
            "timeout": True
        })
    except Exception as e:
        logger.error(f"Error in fetch_game_boxscore_logic: {str(e)}", exc_info=True)
        if "404" in str(e):
            return json.dumps({"error": f"Game not found: {game_id}"})
        return json.dumps({
            "error": f"Unexpected error retrieving box score data: {str(e)}"
        })

def fetch_game_shotchart_logic(game_id: str, team_id: str = None) -> str:
    """
    Fetches shot chart data for a specific game, optionally filtered by team.
    Args:
        game_id (str): The ID of the game to fetch shot chart data for
        team_id (str, optional): The ID of the team to filter shots for
    Returns:
        str: JSON string containing shot chart data or error message
    """
    logger.info(f"Executing fetch_game_shotchart_logic for game_id: '{game_id}', team_id: '{team_id}'")
    
    # Validate game_id
    if not game_id:
        return json.dumps({"error": Errors.GAME_ID_EMPTY})
    if not game_id.isdigit() or len(game_id) != 10:
        return json.dumps({"error": Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id)})
    
    try:
        # Fetch shot chart data
        shot_chart = shotchartdetail.ShotChartDetail(
            team_id=0,  # 0 means all teams
            player_id=0,  # 0 means all players
            game_id_nullable=game_id,
            context_measure_simple='FGA',  # Field Goal Attempts
            season_nullable='',  # Not needed when specifying game_id
            timeout=DEFAULT_TIMEOUT
        )
        
        # Get normalized data
        data = shot_chart.get_normalized_dict()
        if not data:
            return json.dumps({"error": f"No shot chart data found for game {game_id}"})
        
        # Extract shot data
        shots = data.get('Shot_Chart_Detail', [])
        if not shots:
            return json.dumps({"error": f"No shots found for game {game_id}"})
        
        # Format shots
        formatted_shots = []
        for shot in shots:
            shot_team_id = str(shot.get('TEAM_ID', ''))
            
            # Filter by team_id if specified
            if team_id and shot_team_id != team_id:
                continue
                
            formatted_shot = {
                "team_id": shot_team_id,
                "player_id": str(shot.get('PLAYER_ID', '')),
                "player_name": shot.get('PLAYER_NAME', ''),
                "period": shot.get('PERIOD', 0),
                "minutes_remaining": shot.get('MINUTES_REMAINING', 0),
                "seconds_remaining": shot.get('SECONDS_REMAINING', 0),
                "action_type": shot.get('ACTION_TYPE', ''),
                "shot_type": shot.get('SHOT_TYPE', ''),
                "shot_zone": shot.get('SHOT_ZONE_BASIC', ''),
                "shot_distance": shot.get('SHOT_DISTANCE', 0),
                "x_coordinate": shot.get('LOC_X', 0),
                "y_coordinate": shot.get('LOC_Y', 0),
                "made_shot": shot.get('SHOT_MADE_FLAG', 0) == 1,
                "game_event_id": str(shot.get('GAME_EVENT_ID', '')),
                "shot_attempted_flag": shot.get('SHOT_ATTEMPTED_FLAG', 0) == 1
            }
            formatted_shots.append(formatted_shot)
        
        result = {
            "game_id": game_id,
            "team_id": team_id if team_id else "all",
            "total_shots": len(formatted_shots),
            "shots": formatted_shots
        }
        
        return json.dumps(result)
        
    except requests.exceptions.Timeout:
        logger.error(f"Request timed out for game ID: {game_id}")
        return json.dumps({
            "error": f"Request timed out for game ID: {game_id}",
            "timeout": True
        })
    except Exception as e:
        logger.error(f"Error in fetch_game_shotchart_logic: {str(e)}", exc_info=True)
        if "404" in str(e):
            return json.dumps({"error": f"Game not found: {game_id}"})
        return json.dumps({
            "error": f"Unexpected error retrieving shot chart data: {str(e)}"
        })

def fetch_game_hustle_stats_logic(game_id: str) -> str:
    """
    Fetches hustle stats for a specific game.
    Args:
        game_id (str): The ID of the game to fetch hustle stats for
    Returns:
        str: JSON string containing hustle stats or error message
    """
    logger.info(f"Executing fetch_game_hustle_stats_logic for game_id: '{game_id}'")
    
    # Validate game_id
    if not game_id:
        return json.dumps({"error": Errors.GAME_ID_EMPTY})
    if not game_id.isdigit() or len(game_id) != 10:
        return json.dumps({"error": f"Invalid game ID format: {game_id}. Expected 10 digits."})
    
    try:
        # Fetch hustle stats
        hustle_stats = hustlestatsboxscore.HustleStatsBoxScore(
            game_id=game_id,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Get player and team hustle stats
        player_stats_df = hustle_stats.hustle_stats_player_box_score.get_data_frame()
        team_stats_df = hustle_stats.hustle_stats_team_box_score.get_data_frame()
        
        if player_stats_df is None or player_stats_df.empty or team_stats_df is None or team_stats_df.empty:
            return json.dumps({"error": f"No hustle stats found for game {game_id}"})
        
        # Process data frames
        player_stats = _process_dataframe(player_stats_df, single_row=False)
        team_stats = _process_dataframe(team_stats_df, single_row=False)
        
        if not player_stats or not team_stats or len(team_stats) != 2:
            return json.dumps({"error": f"Invalid hustle stats format for game {game_id}"})
        
        # Organize players by team
        home_team = team_stats[0]
        away_team = team_stats[1]
        
        home_players = [p for p in player_stats if p["TEAM_ID"] == home_team["TEAM_ID"]]
        away_players = [p for p in player_stats if p["TEAM_ID"] == away_team["TEAM_ID"]]
        
        result = {
            "game_id": game_id,
            "home_team": {
                "team_id": home_team["TEAM_ID"],
                "team_name": home_team.get("TEAM_NAME", ""),
                "players": home_players
            },
            "away_team": {
                "team_id": away_team["TEAM_ID"],
                "team_name": away_team.get("TEAM_NAME", ""),
                "players": away_players
            }
        }
        
        return json.dumps(result)
        
    except requests.exceptions.Timeout:
        logger.error(f"Request timed out for game ID: {game_id}")
        return json.dumps({
            "error": f"Request timed out for game ID: {game_id}",
            "timeout": True
        })
    except Exception as e:
        logger.error(f"Error in fetch_game_hustle_stats_logic: {str(e)}", exc_info=True)
        return json.dumps({
            "error": f"Invalid game ID: {game_id}. {str(e)}"
        })

def fetch_game_playbyplay_logic(game_id: str, period: Optional[int] = None) -> str:
    """
    Fetches play-by-play data for a specific game.
    Args:
        game_id (str): The ID of the game to fetch play-by-play data for
        period (Optional[int]): If provided, only return plays from this period
    Returns:
        str: JSON string containing play-by-play data or error message
    """
    logger.info(f"Executing fetch_game_playbyplay_logic for game_id: '{game_id}', period: {period}")
    
    # Validate game_id
    if not game_id:
        return json.dumps({"error": Errors.GAME_ID_EMPTY})
    if not game_id.isdigit() or len(game_id) != 10:
        return json.dumps({"error": Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id)})
    
    try:
        # Fetch play-by-play data
        pbp = playbyplayv3.PlayByPlayV3(
            game_id=game_id,
            start_period='0',  # Get all periods
            end_period='0',
            timeout=DEFAULT_TIMEOUT
        )
        
        # Get the data frame
        pbp_df = pbp.get_normalized_dict()
        
        if not pbp_df or 'PlayByPlay' not in pbp_df:
            return json.dumps({"error": f"No play-by-play data found for game ID: {game_id}"})
        
        plays = pbp_df['PlayByPlay']
        
        # Calculate total periods and overtime periods
        max_period = max(int(play.get('period', 0)) for play in plays)
        overtime_periods = max(0, max_period - 4)
        
        # Filter by period if specified
        if period is not None:
            if period < 1 or period > max_period:
                return json.dumps({"error": f"No play-by-play data found for period {period}"})
            plays = [play for play in plays if int(play.get('period', 0)) == period]
            if not plays:
                return json.dumps({"error": f"No play-by-play data found for period {period}"})
        
        # Format plays
        formatted_plays = []
        for play in plays:
            formatted_play = {
                "GAME_ID": play.get('gameId', game_id),
                "PERIOD": int(play.get('period', 0)),
                "PCTIMESTRING": play.get('clock', ''),
                "HOMEDESCRIPTION": play.get('homeDescription', ''),
                "NEUTRALDESCRIPTION": play.get('neutralDescription', ''),
                "VISITORDESCRIPTION": play.get('visitorDescription', ''),
                "SCORE": play.get('score', ''),
                "SCOREMARGIN": play.get('scoreMargin', '')
            }
            formatted_plays.append(formatted_play)
        
        result = {
            "game_id": game_id,
            "total_periods": max_period,
            "overtime_periods": overtime_periods,
            "plays": formatted_plays
        }
        
        return json.dumps(result)
        
    except requests.exceptions.Timeout:
        logger.error(f"Request timed out for game ID: {game_id}")
        return json.dumps({
            "error": f"Request timed out for game ID: {game_id}",
            "timeout": True
        })
    except Exception as e:
        logger.error(f"Error in fetch_game_playbyplay_logic: {str(e)}", exc_info=True)
        return json.dumps({
            "error": f"Unexpected error retrieving play-by-play data: {str(e)}"
        })
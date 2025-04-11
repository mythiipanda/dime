import logging
import json
import requests
from typing import Optional, Dict, Any, List, Union
import pandas as pd
# Import new endpoints
from nba_api.stats.endpoints import leaguegamefinder, boxscoretraditionalv3, playbyplayv3, boxscoreadvancedv3, boxscorefourfactorsv3, shotchartdetail, hustlestatsboxscore # Added shotchartdetail and hustlestatsboxscore
from nba_api.stats.library.parameters import LeagueID, SeasonTypeNullable, SeasonNullable

from .utils import _process_dataframe
from config import DEFAULT_TIMEOUT, MAX_GAMES_TO_RETURN, ErrorMessages as Errors

logger = logging.getLogger(__name__)

def get_season_from_game_id(game_id: str) -> str:
    """
    Extract the season from a game ID.
    NBA game IDs are in the format: XXYYZZZZZ where:
    - XX is the season type (00=preseason, 00=regular season, 00=playoffs)
    - YY is the season year (e.g., 23=2023-24)
    - ZZZZZ is the game number
    """
    if not game_id or len(game_id) != 10:
        return ''
    
    season_year = int(game_id[1:3])  # Extract YY part
    if season_year >= 0 and season_year <= 99:
        # Convert YY to full season format (e.g., 23 -> 2023-24)
        full_year = 2000 + season_year
        return f"{full_year}-{str(full_year + 1)[-2:]}"
    return ''

def _process_dataframe(df: pd.DataFrame, single_row: bool = True) -> Union[Dict, List[Dict]]:
    """
    Convert a pandas DataFrame to a dictionary or list of dictionaries with standardized column names.
    """
    # Convert column names to lowercase
    df.columns = df.columns.str.lower()
    
    # Define column mappings
    column_map = {
        'player_id': 'person_id',
        'player_name': 'player_name',
        'team_id': 'team_id',
        'min': 'minutes',
        'pts': 'points',
        'reb': 'rebounds',
        'ast': 'assists',
        'stl': 'steals',
        'blk': 'blocks',
        'tov': 'turnovers',
        'pf': 'fouls',
        'fgm': 'fg_made',
        'fga': 'fg_attempted',
        'fg_pct': 'fg_pct',
        'fg3m': 'fg3_made',
        'fg3a': 'fg3_attempted',
        'fg3_pct': 'fg3_pct',
        'ftm': 'ft_made',
        'fta': 'ft_attempted',
        'ft_pct': 'ft_pct'
    }
    
    # Rename columns that exist in the DataFrame
    existing_columns = {old: new for old, new in column_map.items() if old in df.columns}
    df = df.rename(columns=existing_columns)
    
    # Convert to dictionary/list
    if single_row:
        return df.iloc[0].to_dict() if not df.empty else {}
    else:
        return df.to_dict(orient='records')

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
    Fetch boxscore data for a specific game.
    """
    try:
        if not game_id:
            return handle_api_error("EmptyGameId")
            
        if not validate_game_id_format(game_id):
            return handle_api_error("InvalidGameId")

        boxscore = retry_on_timeout(lambda: BoxScore(game_id=game_id))
        player_stats = boxscore.player_stats.get_data_frame()
        team_stats = boxscore.team_stats.get_data_frame()
        
        if player_stats.empty or team_stats.empty:
            return handle_api_error("NoDataFound", f"No boxscore data found for game {game_id}")
            
        if "TEAM_ID" not in player_stats.columns or "TEAM_ID" not in team_stats.columns:
            return handle_api_error("MissingTeamId")

        # Convert TEAM_ID to string type for consistent comparison
        player_stats["TEAM_ID"] = player_stats["TEAM_ID"].astype(str)
        team_stats["TEAM_ID"] = team_stats["TEAM_ID"].astype(str)
        
        # Get home and away team IDs
        home_team_id = str(team_stats.iloc[0]["TEAM_ID"])
        away_team_id = str(team_stats.iloc[1]["TEAM_ID"])
        
        # Filter players by team
        home_players = player_stats[player_stats["TEAM_ID"] == home_team_id]
        away_players = player_stats[player_stats["TEAM_ID"] == away_team_id]
        
        response = {
            "home_team": {
                "team_stats": json.loads(team_stats[team_stats["TEAM_ID"] == home_team_id].to_json(orient="records"))[0],
                "player_stats": json.loads(home_players.to_json(orient="records"))
            },
            "away_team": {
                "team_stats": json.loads(team_stats[team_stats["TEAM_ID"] == away_team_id].to_json(orient="records"))[0],
                "player_stats": json.loads(away_players.to_json(orient="records"))
            }
        }
        
        return format_response(response)
        
    except requests.exceptions.Timeout:
        return handle_api_error("Timeout", f"Request timed out while fetching boxscore for game {game_id}")
    except Exception as e:
        return handle_api_error("APIError", f"Error fetching boxscore data: {str(e)}")

def fetch_game_shotchart_logic(game_id: str, team_id: str = None) -> str:
    """
    Fetches shot chart data for a specific game, optionally filtered by team.
    Returns JSON string with shot locations and details.
    """
    logger.info(f"Executing fetch_game_shotchart_logic for game_id: '{game_id}', team_id: '{team_id}'")
    
    if not game_id or not game_id.strip():
        return json.dumps({"error": Errors.GAME_ID_EMPTY})
    if not game_id.isdigit() or len(game_id) != 10:
        return json.dumps({"error": Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id)})
    if team_id and (not team_id.isdigit() or len(team_id) > 10):
        return json.dumps({"error": f"Invalid team_id format: {team_id}"})

    try:
        shotchart = shotchartdetail.ShotChartDetail(
            team_id=team_id or '0',
            player_id='0',
            game_id_nullable=game_id,
            context_measure_simple='FGA',
            season_nullable=get_season_from_game_id(game_id),
            timeout=DEFAULT_TIMEOUT
        )
        
        shots_df = shotchart.get_data_frames()[0]
        
        if shots_df.empty:
            return json.dumps({"error": f"No shot chart data found for game {game_id}"})
            
        # Validate required columns
        required_columns = ['GAME_ID', 'TEAM_ID', 'PLAYER_NAME', 'LOC_X', 'LOC_Y', 'SHOT_MADE_FLAG']
        missing_columns = [col for col in required_columns if col not in shots_df.columns]
        if missing_columns:
            return json.dumps({"error": f"Invalid shot chart data format. Missing columns: {', '.join(missing_columns)}"})
            
        # Filter by team_id if provided
        if team_id:
            shots_df = shots_df[shots_df['TEAM_ID'].astype(str) == str(team_id)]
            if shots_df.empty:
                return json.dumps({"error": f"No shots found for team {team_id} in game {game_id}"})
        
        # Process shot data
        shots_list = []
        for _, shot in shots_df.iterrows():
            shot_data = {
                "game_id": str(shot['GAME_ID']),
                "team_id": str(shot['TEAM_ID']),
                "player_name": shot['PLAYER_NAME'],
                "x": float(shot['LOC_X']),
                "y": float(shot['LOC_Y']),
                "made": bool(shot['SHOT_MADE_FLAG']),
                "period": int(shot.get('PERIOD', 0)),
                "minutes_remaining": int(shot.get('MINUTES_REMAINING', 0)),
                "seconds_remaining": int(shot.get('SECONDS_REMAINING', 0)),
                "shot_type": shot.get('ACTION_TYPE', ''),
                "shot_zone": shot.get('SHOT_ZONE_BASIC', ''),
                "shot_distance": float(shot.get('SHOT_DISTANCE', 0))
            }
            shots_list.append(shot_data)
            
        result = {
            "game_id": game_id,
            "team_id": team_id if team_id else "all",
            "total_shots": len(shots_list),
            "shots": shots_list
        }
        
        return json.dumps(result, default=str)
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout error fetching shot chart for game {game_id}")
        return json.dumps({"error": f"Request timeout while fetching shot chart data for game {game_id}"})
    except Exception as e:
        logger.error(f"Error fetching shot chart for game {game_id}: {str(e)}")
        return json.dumps({"error": f"Failed to retrieve shot chart data for game {game_id}: {str(e)}"})

def fetch_game_hustle_stats_logic(game_id: str) -> str:
    """
    Fetches hustle stats for a specific game.
    Returns JSON string with detailed hustle statistics for teams and players.
    """
    logger.info(f"Executing fetch_game_hustle_stats_logic for game_id: '{game_id}'")
    
    if not game_id or not game_id.strip():
        return json.dumps({"error": Errors.GAME_ID_EMPTY})
    if not game_id.isdigit() or len(game_id) != 10:
        return json.dumps({"error": Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id)})

    try:
        hustle_stats = hustlestatsboxscore.HustleStatsBoxScore(
            game_id=game_id,
            timeout=DEFAULT_TIMEOUT
        )
        
        player_stats_df = hustle_stats.hustle_stats_player_box_score.get_data_frame()
        team_stats_df = hustle_stats.hustle_stats_team_box_score.get_data_frame()
        
        if player_stats_df.empty or team_stats_df.empty:
            return json.dumps({"error": f"No hustle stats found for game {game_id}"})
            
        # Validate required columns
        player_required_columns = ['GAME_ID', 'TEAM_ID', 'PLAYER_NAME', 'MINUTES']
        team_required_columns = ['GAME_ID', 'TEAM_ID', 'TEAM_NAME']
        
        missing_player_columns = [col for col in player_required_columns if col not in player_stats_df.columns]
        missing_team_columns = [col for col in team_required_columns if col not in team_stats_df.columns]
        
        if missing_player_columns or missing_team_columns:
            errors = []
            if missing_player_columns:
                errors.append(f"Missing player columns: {', '.join(missing_player_columns)}")
            if missing_team_columns:
                errors.append(f"Missing team columns: {', '.join(missing_team_columns)}")
            return json.dumps({"error": f"Invalid hustle stats format. {' '.join(errors)}"})
        
        # Process team stats
        if len(team_stats_df) != 2:
            return json.dumps({"error": f"Invalid team stats data: expected 2 teams, found {len(team_stats_df)}"})
            
        home_team_id = str(team_stats_df.iloc[0]['TEAM_ID'])
        away_team_id = str(team_stats_df.iloc[1]['TEAM_ID'])
        
        # Process player stats by team
        home_players_df = player_stats_df[player_stats_df['TEAM_ID'].astype(str) == home_team_id]
        away_players_df = player_stats_df[player_stats_df['TEAM_ID'].astype(str) == away_team_id]
        
        # Convert to dictionaries with proper formatting
        home_team_stats = _process_dataframe(team_stats_df.iloc[[0]], single_row=True)
        away_team_stats = _process_dataframe(team_stats_df.iloc[[1]], single_row=True)
        home_players_list = _process_dataframe(home_players_df, single_row=False)
        away_players_list = _process_dataframe(away_players_df, single_row=False)
        
        result = {
            "game_id": game_id,
            "home_team": {
                "team_id": home_team_id,
                "team_name": home_team_stats.get('team_name', ''),
                "team_stats": {k: v for k, v in home_team_stats.items() if k not in ['team_id', 'team_name', 'game_id']},
                "players": home_players_list
            },
            "away_team": {
                "team_id": away_team_id,
                "team_name": away_team_stats.get('team_name', ''),
                "team_stats": {k: v for k, v in away_team_stats.items() if k not in ['team_id', 'team_name', 'game_id']},
                "players": away_players_list
            }
        }
        
        return json.dumps(result, default=str)
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout error fetching hustle stats for game {game_id}")
        return json.dumps({"error": f"Request timeout while fetching hustle stats for game {game_id}"})
    except Exception as e:
        logger.error(f"Error fetching hustle stats for game {game_id}: {str(e)}")
        return json.dumps({"error": f"Failed to retrieve hustle stats for game {game_id}: {str(e)}"})

def fetch_game_playbyplay_logic(game_id: str, period: Optional[int] = None) -> str:
    """
    Fetches play-by-play data for a specific game.
    Returns JSON string with detailed play-by-play information.
    """
    logger.info(f"Executing fetch_game_playbyplay_logic for game_id: '{game_id}', period: {period}")
    
    if not game_id or not game_id.strip():
        return json.dumps({"error": Errors.GAME_ID_EMPTY})
    if not game_id.isdigit() or len(game_id) != 10:
        return json.dumps({"error": Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id)})
    if period is not None and not isinstance(period, int):
        return json.dumps({"error": f"Invalid period format: {period}. Expected an integer."})

    try:
        pbp = playbyplayv3.PlayByPlayV3(
            game_id=game_id,
            start_period='0',
            end_period='0',
            timeout=DEFAULT_TIMEOUT
        )
        
        pbp_df = pbp.play_by_play.get_data_frame()
        
        if pbp_df.empty:
            return json.dumps({"error": f"No play-by-play data found for game {game_id}"})
            
        # Validate required columns
        required_columns = ['PERIOD', 'PCTIMESTRING', 'SCORE', 'SCOREMARGIN', 'EVENTMSGTYPE']
        missing_columns = [col for col in required_columns if col not in pbp_df.columns]
        if missing_columns:
            return json.dumps({"error": f"Invalid play-by-play data format. Missing columns: {', '.join(missing_columns)}"})
        
        # Calculate game information
        max_period = int(pbp_df['PERIOD'].max())
        overtime_periods = max(0, max_period - 4)
        
        # Filter by period if specified
        if period is not None:
            if period < 1 or period > max_period:
                return json.dumps({"error": f"Invalid period {period}. Game has {max_period} periods."})
            pbp_df = pbp_df[pbp_df['PERIOD'] == period]
            if pbp_df.empty:
                return json.dumps({"error": f"No plays found for period {period}"})
        
        # Process plays
        plays_list = []
        for _, play in pbp_df.iterrows():
            play_data = {
                "game_id": str(play.get('GAME_ID', game_id)),
                "event_num": int(play.get('EVENTNUM', 0)),
                "event_type": int(play.get('EVENTMSGTYPE', 0)),
                "period": int(play['PERIOD']),
                "play_clock": play['PCTIMESTRING'],
                "home_description": play.get('HOMEDESCRIPTION', ''),
                "neutral_description": play.get('NEUTRALDESCRIPTION', ''),
                "visitor_description": play.get('VISITORDESCRIPTION', ''),
                "score": play.get('SCORE', ''),
                "score_margin": play.get('SCOREMARGIN', ''),
                "person1_type": int(play.get('PERSON1TYPE', 0)),
                "player1_id": str(play.get('PLAYER1_ID', '')),
                "player1_name": play.get('PLAYER1_NAME', ''),
                "player1_team_id": str(play.get('PLAYER1_TEAM_ID', '')),
                "player2_id": str(play.get('PLAYER2_ID', '')),
                "player2_name": play.get('PLAYER2_NAME', ''),
                "player2_team_id": str(play.get('PLAYER2_TEAM_ID', '')),
                "player3_id": str(play.get('PLAYER3_ID', '')),
                "player3_name": play.get('PLAYER3_NAME', ''),
                "player3_team_id": str(play.get('PLAYER3_TEAM_ID', ''))
            }
            plays_list.append(play_data)
            
        result = {
            "game_id": game_id,
            "total_periods": max_period,
            "overtime_periods": overtime_periods,
            "period_filtered": period is not None,
            "period": period if period is not None else "all",
            "total_plays": len(plays_list),
            "plays": plays_list
        }
        
        return json.dumps(result, default=str)
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout error fetching play-by-play for game {game_id}")
        return json.dumps({"error": f"Request timeout while fetching play-by-play data for game {game_id}"})
    except Exception as e:
        logger.error(f"Error fetching play-by-play for game {game_id}: {str(e)}")
        return json.dumps({"error": f"Failed to retrieve play-by-play data for game {game_id}: {str(e)}"})
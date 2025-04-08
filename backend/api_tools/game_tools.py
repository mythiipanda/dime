import logging
import json
from typing import Optional
import pandas as pd
# Import new endpoints
from nba_api.stats.endpoints import leaguegamefinder, boxscoretraditionalv3, playbyplayv3
from nba_api.stats.library.parameters import LeagueID, SeasonTypeNullable, SeasonNullable

from .utils import _process_dataframe
from ..config import DEFAULT_TIMEOUT, MAX_GAMES_TO_RETURN, ErrorMessages as Errors

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
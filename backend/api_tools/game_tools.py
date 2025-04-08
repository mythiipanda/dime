import logging
import json
from typing import Optional
import pandas as pd
from nba_api.stats.endpoints import leaguegamefinder
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
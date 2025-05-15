import logging
from typing import Optional
from datetime import datetime
from functools import lru_cache
from nba_api.stats.endpoints import leaguegamefinder
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response
)
from backend.utils.validation import _validate_season_format, validate_date_format # Import from new location


logger = logging.getLogger(__name__)

# Module-level constants for validation
_VALID_GAME_FINDER_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str) and attr != 'default'}
_VALID_GAME_FINDER_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

@lru_cache(maxsize=32)
def fetch_league_games_logic(
    player_or_team_abbreviation: str = 'T',
    player_id_nullable: Optional[int] = None,
    team_id_nullable: Optional[int] = None,
    season_nullable: Optional[str] = None,
    season_type_nullable: Optional[str] = None, 
    league_id_nullable: Optional[str] = LeagueID.nba, 
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None
) -> str:
    """
    Fetches NBA league games using the nba_api's LeagueGameFinder endpoint with common filters.

    Args:
        player_or_team_abbreviation (str): 'P' for player or 'T' for team queries. Default is 'T'.
        player_id_nullable (Optional[int]): NBA player ID for player-specific queries.
        team_id_nullable (Optional[int]): NBA team ID for team-specific queries.
        season_nullable (Optional[str]): NBA season in 'YYYY-YY' format (e.g., '2022-23').
        season_type_nullable (Optional[str]): Season type (e.g., 'Regular Season', 'Playoffs').
        league_id_nullable (Optional[str]): League ID (default: NBA).
        date_from_nullable (Optional[str]): Start date in 'YYYY-MM-DD' format.
        date_to_nullable (Optional[str]): End date in 'YYYY-MM-DD' format.

    Returns:
        str: JSON-formatted string containing a list of games or an error message.

    Notes:
        - Returns a specific error for unsupported date-only queries.
        - Limits broad queries to 200 results for efficiency.
        - Formats game dates as 'GAME_DATE_FORMATTED' in the output.
    """
    logger.info(f"Executing fetch_league_games_logic with P/T: {player_or_team_abbreviation}, TeamID: {team_id_nullable}, PlayerID: {player_id_nullable}, Season: {season_nullable}, League: {league_id_nullable}")

    if player_or_team_abbreviation not in ['P', 'T']:
        return format_response(error=Errors.INVALID_PLAYER_OR_TEAM_ABBREVIATION.format(value=player_or_team_abbreviation))
    if player_or_team_abbreviation == 'P' and player_id_nullable is None:
        return format_response(error=Errors.PLAYER_ID_REQUIRED) # Corrected error attribute

    # Check for date-only queries which are unreliable for leaguegamefinder
    if date_from_nullable and date_to_nullable and \
       not season_nullable and not player_id_nullable and not team_id_nullable:
        logger.warning("Attempted date-only query for leaguegamefinder, which is unsupported.")
        return format_response(error=Errors.DATE_ONLY_GAME_FINDER_UNSUPPORTED)

    if season_nullable and not _validate_season_format(season_nullable):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season_nullable))
    if date_from_nullable and not validate_date_format(date_from_nullable):
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_from_nullable))
    if date_to_nullable and not validate_date_format(date_to_nullable):
        return format_response(error=Errors.INVALID_DATE_FORMAT.format(date=date_to_nullable))

    if season_type_nullable is not None and season_type_nullable not in _VALID_GAME_FINDER_SEASON_TYPES and season_type_nullable != SeasonTypeAllStar.default : # Using module-level constant
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type_nullable, options=", ".join(_VALID_GAME_FINDER_SEASON_TYPES)))

    if league_id_nullable is not None and league_id_nullable not in _VALID_GAME_FINDER_LEAGUE_IDS: # Using module-level constant
         return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id_nullable, options=", ".join(_VALID_GAME_FINDER_LEAGUE_IDS)))

    try:
        logger.debug(f"Attempting to call LeagueGameFinder with P/T: {player_or_team_abbreviation}, PlayerID: {player_id_nullable}, TeamID: {team_id_nullable}, Season: {season_nullable}, SeasonType: {season_type_nullable}, League: {league_id_nullable}, DateFrom: {date_from_nullable}, DateTo: {date_to_nullable}")
        game_finder_endpoint = leaguegamefinder.LeagueGameFinder(
            player_or_team_abbreviation=player_or_team_abbreviation,
            player_id_nullable=player_id_nullable,
            team_id_nullable=team_id_nullable,
            season_nullable=season_nullable,
            season_type_nullable=season_type_nullable,
            league_id_nullable=league_id_nullable,
            date_from_nullable=date_from_nullable,
            date_to_nullable=date_to_nullable,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug("leaguegamefinder API call successful.")
        games_df = game_finder_endpoint.league_game_finder_results.get_data_frame()

        if games_df.empty:
            logger.warning("No league games found for the specified filters.")
            return format_response({"games": []})

        is_broad_query = all(param is None for param in [player_id_nullable, team_id_nullable, season_nullable]) and \
                         (date_from_nullable is not None or date_to_nullable is not None)
        
        if is_broad_query and len(games_df) > 200:
             logger.info(f"Limiting broad league game list (date-filtered) to the top 200 games. Original count: {len(games_df)}")
             games_df = games_df.head(200)
        elif all(param is None for param in [player_id_nullable, team_id_nullable, season_nullable, season_type_nullable, date_from_nullable, date_to_nullable]) and len(games_df) > 200:
             logger.info(f"Limiting very general league game list to the top 200 games. Original count: {len(games_df)}")
             games_df = games_df.head(200)

        games_list = _process_dataframe(games_df, single_row=False)
        if games_list is None:
            logger.error("Failed to process league games DataFrame.")
            return format_response(error=Errors.PROCESSING_ERROR.format(error="league games data"))

        for game_item in games_list:
            if 'GAME_DATE' in game_item and isinstance(game_item['GAME_DATE'], str):
                try:
                    parsed_date = datetime.strptime(game_item['GAME_DATE'].split('T')[0], '%Y-%m-%d')
                    game_item['GAME_DATE_FORMATTED'] = parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    game_item['GAME_DATE_FORMATTED'] = game_item['GAME_DATE']

        result = {"games": games_list}
        logger.info(f"fetch_league_games_logic found {len(games_list)} games matching criteria.")
        return format_response(result)

    except Exception as e:
        logger.error(f"Error fetching league games: {str(e)}", exc_info=True)
        error_msg = Errors.LEAGUE_GAMES_API.format(error=str(e))
        return format_response(error=error_msg)
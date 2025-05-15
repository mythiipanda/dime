import logging
import pandas as pd # Add pandas import for date filtering
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

@lru_cache(maxsize=32) # Consider if caching is still appropriate with post-fetch filtering, or if cache key needs adjustment
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

    if season_nullable and not _validate_season_format(season_nullable, league_id=league_id_nullable): # Pass league_id
        # The error message might need to be more dynamic if it's league-dependent,
        # but for now, the existing error message is generic enough.
        # Or, create a new error like INVALID_SEASON_FORMAT_FOR_LEAGUE
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
        # Store original date filters and temporarily remove them for the initial API call
        # to avoid potential API instability with date range parameters.
        original_date_from = date_from_nullable
        original_date_to = date_to_nullable
        
        api_date_from_nullable = None
        api_date_to_nullable = None

        # Heuristic: If only team and dates are provided, or team, season and dates,
        # it's safer to fetch by team/season first and then filter by date.
        # If it's a player query with dates, the API might handle it better, but for safety,
        # we can apply the same logic.
        # The main goal is to avoid sending date_from/date_to if they are the *primary* or *problematic* filters.
        # The existing DATE_ONLY_GAME_FINDER_UNSUPPORTED check handles cases with *only* dates.
        # This change addresses cases where dates are combined with other params but might still cause issues.

        logger.debug(f"Attempting to call LeagueGameFinder with P/T: {player_or_team_abbreviation}, PlayerID: {player_id_nullable}, TeamID: {team_id_nullable}, Season: {season_nullable}, SeasonType: {season_type_nullable}, League: {league_id_nullable}, API DateFrom: {api_date_from_nullable}, API DateTo: {api_date_to_nullable}")
        game_finder_endpoint = leaguegamefinder.LeagueGameFinder(
            player_or_team_abbreviation=player_or_team_abbreviation,
            player_id_nullable=player_id_nullable,
            team_id_nullable=team_id_nullable,
            season_nullable=season_nullable,
            season_type_nullable=season_type_nullable,
            league_id_nullable=league_id_nullable,
            date_from_nullable=api_date_from_nullable, # Use None for initial fetch
            date_to_nullable=api_date_to_nullable,   # Use None for initial fetch
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        logger.debug("leaguegamefinder API call successful.")
        games_df = game_finder_endpoint.league_game_finder_results.get_data_frame()

        if games_df.empty:
            logger.warning("No league games found from initial API call.")
            return format_response({"games": []})

        # Apply date filtering post-fetch if original date filters were provided
        if original_date_from or original_date_to:
            logger.info(f"Applying post-fetch date filtering: From {original_date_from}, To {original_date_to}")
            try:
                # Ensure GAME_DATE is in datetime format for comparison
                games_df['GAME_DATE_DT'] = pd.to_datetime(games_df['GAME_DATE']).dt.date
                if original_date_from:
                    from_date = datetime.strptime(original_date_from, '%Y-%m-%d').date()
                    games_df = games_df[games_df['GAME_DATE_DT'] >= from_date]
                if original_date_to:
                    to_date = datetime.strptime(original_date_to, '%Y-%m-%d').date()
                    games_df = games_df[games_df['GAME_DATE_DT'] <= to_date]
                
                games_df = games_df.drop(columns=['GAME_DATE_DT']) # Clean up temporary column
                
                if games_df.empty:
                    logger.warning("No league games found after post-fetch date filtering.")
                    return format_response({"games": []})
            except Exception as e:
                logger.error(f"Error during post-fetch date filtering: {str(e)}", exc_info=True)
                # Potentially return error or proceed with unfiltered data if filtering fails critically
                return format_response(error=Errors.PROCESSING_ERROR.format(error=f"date filtering: {str(e)}"))


        is_broad_query = all(param is None for param in [player_id_nullable, team_id_nullable, season_nullable]) and \
                         (original_date_from is not None or original_date_to is not None) # Check original dates
        
        # Limit results for broad queries or very general queries
        # This logic might need adjustment based on whether date filtering happened before or after this check.
        # For now, assume it's applied to the potentially date-filtered (or pre-date-filtered) set.
        if is_broad_query and len(games_df) > 200: # This condition might be redundant if date filtering is now post-fetch
             logger.info(f"Limiting broad league game list (potentially date-filtered) to the top 200 games. Original count: {len(games_df)}")
             games_df = games_df.head(200)
        # Check for very general queries (no specific player, team, season, or dates initially sent to API)
        elif all(param is None for param in [player_id_nullable, team_id_nullable, season_nullable, season_type_nullable, original_date_from, original_date_to]) and len(games_df) > 200:
             logger.info(f"Limiting very general league game list to the top 200 games. Original count: {len(games_df)}")
             games_df = games_df.head(200)

        games_list = _process_dataframe(games_df, single_row=False)
        if games_list is None:
            logger.error("Failed to process league games DataFrame.")
            return format_response(error=Errors.PROCESSING_ERROR.format(error="league games data"))

        for game_item in games_list:
            if 'GAME_DATE' in game_item and isinstance(game_item['GAME_DATE'], str):
                try:
                    # The GAME_DATE from nba_api is usually like '2023-10-24T00:00:00'
                    # We want to ensure it's formatted as 'YYYY-MM-DD'
                    parsed_date = datetime.fromisoformat(game_item['GAME_DATE'].split('T')[0])
                    game_item['GAME_DATE_FORMATTED'] = parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                     # Fallback if parsing fails, though it shouldn't if GAME_DATE is standard
                    game_item['GAME_DATE_FORMATTED'] = game_item['GAME_DATE'].split('T')[0]


        result = {"games": games_list}
        logger.info(f"fetch_league_games_logic found {len(games_list)} games matching criteria after all filters.")
        return format_response(result)

    except Exception as e:
        # Check if the error is a JSONDecodeError, which is the original problem
        if "Expecting value: line 1 column 1 (char 0)" in str(e):
            logger.error(f"JSONDecodeError from NBA API (LeagueGameFinder): {str(e)}", exc_info=True)
            error_msg = Errors.JSON_PROCESSING_ERROR # Use a more specific error if the API returns bad JSON
        else:
            logger.error(f"Error fetching league games: {str(e)}", exc_info=True)
            error_msg = Errors.LEAGUE_GAMES_API.format(error=str(e))
        return format_response(error=error_msg)
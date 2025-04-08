import logging
import json
from typing import Optional
import pandas as pd
# Import new endpoints
from nba_api.stats.endpoints import leaguestandingsv3, scoreboardv2, drafthistory, leagueleaders
# Import necessary parameters
from nba_api.stats.library.parameters import LeagueID, SeasonType, PerMode48, Scope, StatCategoryAbbreviation, SeasonTypeAllStar
from datetime import datetime # Import datetime for default date

from .utils import _process_dataframe
from ..config import DEFAULT_TIMEOUT, ErrorMessages as Errors
from ..config import CURRENT_SEASON # Import CURRENT_SEASON

logger = logging.getLogger(__name__)

def fetch_league_standings_logic(
    season: str = CURRENT_SEASON,
    season_type: str = SeasonType.regular, # V3 only supports Regular Season
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches league standings (V3) for a specific season.
    Returns JSON string.
    """
    logger.info(f"Executing fetch_league_standings_logic for Season: {season}, Type: {season_type}, League: {league_id}")

    # Validate season format (reuse from player_tools or utils if available, assuming utils for now)
    # from .utils import _validate_season_format # Assuming this exists or will be added
    # if not season or not _validate_season_format(season):
    #     return json.dumps({"error": Errors.INVALID_SEASON_FORMAT.format(season=season)})

    # V3 endpoint specifically mentions only Regular Season works
    if season_type != SeasonType.regular:
        logger.warning(f"LeagueStandingsV3 only supports 'Regular Season'. Forcing season_type to '{SeasonType.regular}'.")
        season_type = SeasonType.regular

    try:
        logger.debug(f"Fetching leaguestandingsv3 for Season: {season}, League: {league_id}")
        try:
            standings_endpoint = leaguestandingsv3.LeagueStandingsV3(
                league_id=league_id,
                season=season,
                season_type=season_type, # Will always be Regular Season here
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"leaguestandingsv3 API call successful for Season: {season}")
        except Exception as api_error:
            logger.error(f"nba_api leaguestandingsv3 failed for Season {season}: {api_error}", exc_info=True)
            return json.dumps({"error": Errors.STANDINGS_API.format(season=season, error=str(api_error))}) # Need to add this error message

        standings_list = _process_dataframe(standings_endpoint.standings.get_data_frame(), single_row=False)

        if standings_list is None:
            logger.error(f"DataFrame processing failed for standings ({season}).")
            return json.dumps({"error": Errors.STANDINGS_PROCESSING.format(season=season)}) # Need to add this error message

        result = {
            "season": season,
            "league_id": league_id,
            "standings": standings_list or []
        }
        logger.info(f"fetch_league_standings_logic completed for Season: {season}")
        return json.dumps(result, default=str)

    except Exception as e:
        logger.critical(f"Unexpected error in fetch_league_standings_logic for Season '{season}': {e}", exc_info=True)
        return json.dumps({"error": Errors.STANDINGS_UNEXPECTED.format(season=season, error=str(e))}) # Need to add this error message

def fetch_scoreboard_logic(
    game_date: str = datetime.today().strftime('%Y-%m-%d'), # Default to today
    league_id: str = LeagueID.nba,
    day_offset: int = 0
) -> str:
    """
    Fetches scoreboard details (V2) for a specific date.
    Returns JSON string with game headers, line scores, etc.
    """
    logger.info(f"Executing fetch_scoreboard_logic for Date: {game_date}, League: {league_id}, Offset: {day_offset}")

    # Basic date validation (can be enhanced)
    try:
        datetime.strptime(game_date, '%Y-%m-%d')
    except ValueError:
        logger.error(f"Invalid game_date format: {game_date}. Expected YYYY-MM-DD.")
        return json.dumps({"error": Errors.INVALID_DATE_FORMAT.format(date=game_date)}) # Need to add this error message

    try:
        logger.debug(f"Fetching scoreboardv2 for Date: {game_date}, League: {league_id}, Offset: {day_offset}")
        try:
            scoreboard_endpoint = scoreboardv2.ScoreboardV2(
                game_date=game_date,
                league_id=league_id,
                day_offset=str(day_offset), # API expects string offset
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"scoreboardv2 API call successful for Date: {game_date}")
        except Exception as api_error:
            logger.error(f"nba_api scoreboardv2 failed for Date {game_date}: {api_error}", exc_info=True)
            return json.dumps({"error": Errors.SCOREBOARD_API.format(date=game_date, error=str(api_error))}) # Need to add this error message

        # Extract key dataframes, simplify output
        game_header = _process_dataframe(scoreboard_endpoint.game_header.get_data_frame(), single_row=False)
        line_score = _process_dataframe(scoreboard_endpoint.line_score.get_data_frame(), single_row=False)
        # Optional: Add more dataframes if needed (e.g., series_standings, last_meeting)
        # east_conf_standings = _process_dataframe(scoreboard_endpoint.east_conf_standings_by_day.get_data_frame(), single_row=False)
        # west_conf_standings = _process_dataframe(scoreboard_endpoint.west_conf_standings_by_day.get_data_frame(), single_row=False)

        if game_header is None or line_score is None:
             logger.error(f"DataFrame processing failed for scoreboard ({game_date}).")
             return json.dumps({"error": Errors.SCOREBOARD_PROCESSING.format(date=game_date)}) # Need to add this error message

        result = {
            "game_date": game_date,
            "game_header": game_header or [],
            "line_score": line_score or [],
            # "east_standings": east_conf_standings or [], # Example if added
            # "west_standings": west_conf_standings or []  # Example if added
        }
        logger.info(f"fetch_scoreboard_logic completed for Date: {game_date}")
        return json.dumps(result, default=str)

    except Exception as e:
        logger.critical(f"Unexpected error in fetch_scoreboard_logic for Date '{game_date}': {e}", exc_info=True)
        return json.dumps({"error": Errors.SCOREBOARD_UNEXPECTED.format(date=game_date, error=str(e))}) # Need to add this error message

def fetch_draft_history_logic(
    season_year: Optional[str] = None, # YYYY format
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches draft history, optionally filtered by season year.
    Returns JSON string.
    """
    logger.info(f"Executing fetch_draft_history_logic for SeasonYear: {season_year}, League: {league_id}")

    # Basic validation for season_year format (YYYY)
    if season_year and (not season_year.isdigit() or len(season_year) != 4):
        logger.error(f"Invalid season_year format: {season_year}. Expected YYYY.")
        return json.dumps({"error": Errors.INVALID_DRAFT_YEAR_FORMAT.format(year=season_year)}) # Need to add this error message

    try:
        logger.debug(f"Fetching drafthistory for SeasonYear: {season_year}, League: {league_id}")
        try:
            draft_endpoint = drafthistory.DraftHistory(
                league_id=league_id,
                season_year_nullable=season_year, # API uses season_year_nullable
                # Other filters like round_num_nullable, team_id_nullable exist but not exposed for simplicity
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"drafthistory API call successful for SeasonYear: {season_year}")
        except Exception as api_error:
            logger.error(f"nba_api drafthistory failed for SeasonYear {season_year}: {api_error}", exc_info=True)
            return json.dumps({"error": Errors.DRAFT_HISTORY_API.format(year=season_year or 'All', error=str(api_error))}) # Need to add this error message

        draft_list = _process_dataframe(draft_endpoint.draft_history.get_data_frame(), single_row=False)

        if draft_list is None:
            logger.error(f"DataFrame processing failed for draft history ({season_year or 'All'}).")
            return json.dumps({"error": Errors.DRAFT_HISTORY_PROCESSING.format(year=season_year or 'All')}) # Need to add this error message

        result = {
            "season_year_requested": season_year or "All",
            "league_id": league_id,
            "draft_picks": draft_list or []
        }
        logger.info(f"fetch_draft_history_logic completed for SeasonYear: {season_year or 'All'}")
        return json.dumps(result, default=str)

    except Exception as e:
        logger.critical(f"Unexpected error in fetch_draft_history_logic for SeasonYear '{season_year or 'All'}': {e}", exc_info=True)
        return json.dumps({"error": Errors.DRAFT_HISTORY_UNEXPECTED.format(year=season_year or 'All', error=str(e))}) # Need to add this error message

def fetch_league_leaders_logic(
    stat_category: str = StatCategoryAbbreviation.pts,
    season: str = CURRENT_SEASON,
    season_type_all_star: str = SeasonTypeAllStar.regular,
    per_mode48: str = PerMode48.per_game,
    scope: str = Scope.s,
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches league leaders for a specific stat category and season.
    Returns JSON string.
    """
    logger.info(f"Executing fetch_league_leaders_logic for Stat: {stat_category}, Season: {season}")

    # Basic validation (can be expanded)
    valid_stats = [getattr(StatCategoryAbbreviation, attr) for attr in dir(StatCategoryAbbreviation) if not attr.startswith('_')]
    if stat_category not in valid_stats:
         logger.error(f"Invalid stat_category: {stat_category}. Valid options: {valid_stats}")
         return json.dumps({"error": Errors.INVALID_STAT_CATEGORY.format(stat=stat_category)})

    try:
        logger.debug(f"Fetching leagueleaders for Stat: {stat_category}, Season: {season}")
        try:
            leaders_endpoint = leagueleaders.LeagueLeaders(
                league_id=league_id,
                per_mode48=per_mode48,
                scope=scope,
                season=season,
                season_type_all_star=season_type_all_star,
                stat_category_abbreviation=stat_category,
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"leagueleaders API call successful for Stat: {stat_category}, Season: {season}")
        except Exception as api_error:
            logger.error(f"nba_api leagueleaders failed for Stat {stat_category}, Season {season}: {api_error}", exc_info=True)
            return json.dumps({"error": Errors.LEAGUE_LEADERS_API.format(stat=stat_category, season=season, error=str(api_error))}) # Need to add

        leaders_list = _process_dataframe(leaders_endpoint.league_leaders.get_data_frame(), single_row=False)

        if leaders_list is None:
            logger.error(f"DataFrame processing failed for league leaders ({stat_category}, {season}).")
            return json.dumps({"error": Errors.LEAGUE_LEADERS_PROCESSING.format(stat=stat_category, season=season)}) # Need to add

        result = {
            "stat_category_abbreviation": stat_category,
            "season": season,
            "season_type_all_star": season_type_all_star,
            "per_mode48": per_mode48,
            "scope": scope,
            "league_id": league_id,
            "leaders": leaders_list or []
        }
        logger.info(f"fetch_league_leaders_logic completed for Stat: {stat_category}, Season: {season}")
        return json.dumps(result, default=str)

    except Exception as e:
        logger.critical(f"Unexpected error in fetch_league_leaders_logic for Stat '{stat_category}', Season '{season}': {e}", exc_info=True)
        return json.dumps({"error": Errors.LEAGUE_LEADERS_UNEXPECTED.format(stat=stat_category, season=season, error=str(e))}) # Need to add
import logging
import json
from typing import Optional
import pandas as pd
# Import new endpoints
from nba_api.stats.endpoints import leaguestandingsv3, scoreboardv2, drafthistory, leagueleaders, leaguedashlineups, leaguehustlestatsplayer
# Import necessary parameters
from nba_api.stats.library.parameters import LeagueID, SeasonType, PerMode48, Scope, StatCategoryAbbreviation, SeasonTypeAllStar, MeasureTypeDetailedDefense, PerMode36, Season
from datetime import datetime # Import datetime for default date

from .utils import _process_dataframe
from ..config import DEFAULT_TIMEOUT, ErrorMessages as Errors
from ..config import CURRENT_SEASON # Import CURRENT_SEASON

logger = logging.getLogger(__name__)

def fetch_league_standings_logic(
    season: str,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    """
    Fetches league standings for a specific season and season type.
    Returns JSON string with standings data.
    """
    logger.info(f"Executing fetch_league_standings_logic for season: {season}, type: {season_type}")
    
    try:
        standings = leaguestandingsv3.LeagueStandingsV3(
            season=season,
            season_type=season_type,
            timeout=DEFAULT_TIMEOUT
        )
        
        standings_df = standings.standings.get_data_frame()
        if standings_df.empty:
            return json.dumps({
                "season": season,
                "season_type": season_type,
                "standings": []
            })
        
        standings_list = _process_dataframe(standings_df, single_row=False)
        
        result = {
            "season": season,
            "season_type": season_type,
            "standings": standings_list
        }
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"Error in fetch_league_standings_logic: {str(e)}", exc_info=True)
        return json.dumps({"error": f"Unexpected error retrieving league standings: {str(e)}"})

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
    season: str,
    stat_category: str = "PTS",
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerMode36.per_game
) -> str:
    """
    Fetches league leaders for a specific statistical category.
    Returns JSON string with leaders data.
    """
    logger.info(f"Executing fetch_league_leaders_logic for season: {season}, category: {stat_category}")
    
    try:
        leaders = leagueleaders.LeagueLeaders(
            season=season,
            stat_category_abbreviation=stat_category,
            season_type_all_star=season_type,
            per_mode48=per_mode,
            timeout=DEFAULT_TIMEOUT
        )
        
        leaders_df = leaders.league_leaders.get_data_frame()
        if leaders_df.empty:
            return json.dumps({
                "season": season,
                "stat_category": stat_category,
                "season_type": season_type,
                "leaders": []
            })
        
        leaders_list = _process_dataframe(leaders_df, single_row=False)
        
        result = {
            "season": season,
            "stat_category": stat_category,
            "season_type": season_type,
            "leaders": leaders_list
        }
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"Error in fetch_league_leaders_logic: {str(e)}", exc_info=True)
        return json.dumps({"error": f"Unexpected error retrieving league leaders: {str(e)}"})

def fetch_league_lineups_logic(
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    measure_type: str = MeasureTypeDetailedDefense.base,
    per_mode: str = PerMode36.per_game
) -> str:
    """
    Fetches league lineup statistics.
    Returns JSON string with lineup data.
    """
    logger.info(f"Executing fetch_league_lineups_logic for season: {season}")
    
    try:
        lineups = leaguedashlineups.LeagueDashLineups(
            season=season,
            season_type_all_star=season_type,
            measure_type_detailed_defense=measure_type,
            per_mode48=per_mode,
            timeout=DEFAULT_TIMEOUT
        )
        
        lineups_df = lineups.league_dash_lineups.get_data_frame()
        if lineups_df.empty:
            return json.dumps({
                "season": season,
                "season_type": season_type,
                "lineups": []
            })
        
        lineups_list = _process_dataframe(lineups_df, single_row=False)
        
        result = {
            "season": season,
            "season_type": season_type,
            "lineups": lineups_list
        }
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"Error in fetch_league_lineups_logic: {str(e)}", exc_info=True)
        return json.dumps({"error": f"Unexpected error retrieving league lineups: {str(e)}"})

def fetch_league_hustle_stats_logic(
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerMode36.per_game
) -> str:
    """
    Fetches league-wide hustle statistics.
    Returns JSON string with hustle stats data.
    """
    logger.info(f"Executing fetch_league_hustle_stats_logic for season: {season}")
    
    try:
        hustle_stats = leaguehustlestatsplayer.LeagueHustleStatsPlayer(
            season=season,
            season_type_all_star=season_type,
            per_mode48=per_mode,
            timeout=DEFAULT_TIMEOUT
        )
        
        hustle_stats_df = hustle_stats.league_hustle_stats_player.get_data_frame()
        if hustle_stats_df.empty:
            return json.dumps({
                "season": season,
                "season_type": season_type,
                "hustle_stats": []
            })
        
        hustle_stats_list = _process_dataframe(hustle_stats_df, single_row=False)
        
        result = {
            "season": season,
            "season_type": season_type,
            "hustle_stats": hustle_stats_list
        }
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"Error in fetch_league_hustle_stats_logic: {str(e)}", exc_info=True)
        return json.dumps({"error": f"Unexpected error retrieving league hustle stats: {str(e)}"})
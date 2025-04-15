import logging
import json
from typing import Optional
import pandas as pd
# Import new endpoints
from nba_api.stats.endpoints import leaguestandingsv3, scoreboardv2, drafthistory, leagueleaders, leaguedashlineups, leaguehustlestatsplayer
# Import necessary parameters
from nba_api.stats.library.parameters import LeagueID, SeasonType, PerMode48, Scope, StatCategoryAbbreviation, SeasonTypeAllStar, MeasureTypeDetailedDefense, PerMode36, Season
from datetime import datetime # Import datetime for default date

from backend.api_tools.utils import _process_dataframe
from backend.config import DEFAULT_TIMEOUT, ErrorMessages as Errors, CURRENT_SEASON

logger = logging.getLogger(__name__)

def fetch_league_standings_logic(
    season: Optional[str] = None,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    """
    Fetches league standings for a specific season and season type.
    Returns JSON string with standings data.
    """
    # Use CURRENT_SEASON as default if season is None
    season = season or CURRENT_SEASON
    logger.info(f"Executing fetch_league_standings_logic for season: {season}, type: {season_type}")
    
    try:
        standings = leaguestandingsv3.LeagueStandingsV3(
            season=season,
            season_type=season_type,
            timeout=DEFAULT_TIMEOUT
        )
        
        standings_df = standings.standings.get_data_frame()
        if standings_df.empty:
            logger.warning(f"No standings data found for season {season}")
            return json.dumps({
                "standings": []
            })
        
        # Process the DataFrame to match frontend expectations
        processed_standings = []
        for _, row in standings_df.iterrows():
            try:
                standing = {
                    "TeamID": int(row["TeamID"]),
                    "TeamName": f"{row['TeamCity']} {row['TeamName']}".strip(),
                    "Conference": row["Conference"],
                    "PlayoffRank": int(row["PlayoffRank"]),
                    "WinPct": float(row["WinPCT"]),
                    "GB": float(row.get("ConferenceGamesBack", 0)),
                    "L10": row["L10"],
                    "STRK": row["strCurrentStreak"],
                    # Additional fields that match the frontend TeamStanding interface
                    "WINS": int(row["WINS"]),
                    "LOSSES": int(row["LOSSES"]),
                    "HOME": row["HOME"],
                    "ROAD": row["ROAD"],
                    "Division": row["Division"],
                    "ClinchIndicator": row.get("ClinchIndicator", ""),
                    "DivisionRank": int(row["DivisionRank"]),
                    "ConferenceRecord": row["ConferenceRecord"],
                    "DivisionRecord": row["DivisionRecord"]
                }
                processed_standings.append(standing)
            except (ValueError, KeyError) as e:
                logger.error(f"Error processing standing row: {e}", exc_info=True)
                continue
        
        # Sort standings by conference and playoff rank
        processed_standings.sort(key=lambda x: (x["Conference"], x["PlayoffRank"]))
        
        result = {
            "standings": processed_standings
        }
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"Error in fetch_league_standings_logic: {str(e)}", exc_info=True)
        error_msg = str(e) if isinstance(e, Exception) else "Unknown error"
        return json.dumps({
            "error": Errors.STANDINGS_API.format(season=season, error=error_msg)
        })

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

        # Handle cases where DataFrames might be empty (e.g., no games on that date)
        if game_header is None:
            logger.warning(f"No game header data found for scoreboard ({game_date}).")
            game_header = []
        if line_score is None:
            logger.warning(f"No line score data found for scoreboard ({game_date}).")
            line_score = []

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
        
        lineups_df = lineups.lineups.get_data_frame()
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
        
        hustle_stats_df = hustle_stats.hustle_stats_player.get_data_frame()
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
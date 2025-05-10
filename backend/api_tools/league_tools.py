import logging
import json
from typing import Optional, Dict, Any, List
import pandas as pd
from functools import lru_cache
from datetime import datetime # Removed timedelta as it's not used
import requests

from nba_api.stats.endpoints import leaguestandingsv3, drafthistory, leagueleaders
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar, PerMode48, Scope, StatCategoryAbbreviation
from backend.api_tools.utils import _process_dataframe, format_response, _validate_season_format # Removed unused validate_date_format, validate_game_id_format
from backend.config import DEFAULT_TIMEOUT, Errors, CURRENT_SEASON

logger = logging.getLogger(__name__)

# CACHE_DURATION constant is not directly used by lru_cache time-based invalidation here,
# but get_cached_standings uses a timestamp trick for hourly invalidation.

@lru_cache(maxsize=32)
def get_cached_standings(season: str, season_type: str, timestamp: str) -> pd.DataFrame:
    """
    Cached wrapper for `nba_api.stats.endpoints.leaguestandingsv3.LeagueStandingsV3`.
    The `timestamp` parameter is used to force cache invalidation approximately every hour,
    as `lru_cache` itself doesn't have time-based expiry.

    Args:
        season (str): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
        season_type (str): The type of season (e.g., "Regular Season", "Playoffs").
        timestamp (str): An ISO format timestamp string, typically for the current hour, used to manage cache expiry.

    Returns:
        pd.DataFrame: A DataFrame containing standings data, or an empty DataFrame if the API call fails.
    """
    logger.info(f"Cache miss or expiry for standings - fetching new data for season {season}, type {season_type} (timestamp: {timestamp})")
    try:
        standings_endpoint = leaguestandingsv3.LeagueStandingsV3(
            season=season,
            season_type=season_type, # API expects season_type, not season_type_all_star
            timeout=DEFAULT_TIMEOUT
        )
        return standings_endpoint.standings.get_data_frame()
    except Exception as e:
        logger.error(f"API call failed in get_cached_standings for season {season}, type {season_type}: {e}", exc_info=True)
        return pd.DataFrame()

@lru_cache(maxsize=64)
def fetch_league_standings_logic(
    season: Optional[str] = None,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    """
    Fetches league standings for a specific season and season type.
    Uses an hourly-invalidating cache for the raw API call.

    Args:
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
                                Defaults to `CURRENT_SEASON` from config.
        season_type (str, optional): The type of season. Valid values from `SeasonTypeAllStar`
                                     (e.g., "Regular Season", "Playoffs", "Pre Season", "All Star").
                                     Defaults to "Regular Season".

    Returns:
        str: JSON string with standings data.
             Expected dictionary structure passed to format_response:
             {
                 "standings": [
                     {
                         "LeagueID": str, "SeasonID": str, "TeamID": int, "TeamCity": str, "TeamName": str,
                         "TeamSlug": str, "Conference": str, "ConferenceRecord": str (e.g., "30-10"),
                         "PlayoffRank": int, "ClinchIndicator": Optional[str] (e.g., " - e", " - x"),
                         "Division": str, "DivisionRecord": str, "DivisionRank": int,
                         "WINS": int, "LOSSES": int, "WinPCT": float, "LeagueRank": Optional[int],
                         "Record": str (e.g., "50-32"), "HOME": str, "ROAD": str, "L10": str,
                         "Last10Home": str, "Last10Road": str, "OT": str, "LastMeeting": Optional[str],
                         "NextMeeting": Optional[str], ... // Other fields from LeagueStandingsV3
                     }, ...
                 ]
             }
             Returns {"standings": []} if no data is found.
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    effective_season = season or CURRENT_SEASON
    logger.info(f"Executing fetch_league_standings_logic for season: {effective_season}, type: {season_type}")

    if not _validate_season_format(effective_season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=effective_season))

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(VALID_SEASON_TYPES)))

    try:
        # Generate a timestamp for the current hour to manage cache invalidation
        current_hour_timestamp = datetime.now().replace(minute=0, second=0, microsecond=0).isoformat()
        standings_df = get_cached_standings(effective_season, season_type, current_hour_timestamp)

        if standings_df.empty:
            # This block attempts a direct check if the cached function returned empty,
            # to differentiate between "no data from API" and "cache function error".
            try:
                quick_check_endpoint = leaguestandingsv3.LeagueStandingsV3(season=effective_season, season_type=season_type, timeout=5)
                if quick_check_endpoint.standings.get_data_frame().empty:
                    logger.warning(f"No standings data found for season {effective_season}, type {season_type} from API.")
                    return format_response({"standings": []})
                else: # Should ideally not be reached if cache returned empty due to no data
                    logger.error(f"Standings processing failed after cache miss for season {effective_season}, but direct check found data.")
                    error_msg = Errors.LEAGUE_STANDINGS_PROCESSING.format(season=effective_season)
                    return format_response(error=error_msg)
            except Exception as api_check_error: # Error during the quick check itself
                logger.error(f"API error during standings quick check for season {effective_season}: {api_check_error}", exc_info=True)
                error_msg = Errors.LEAGUE_STANDINGS_API.format(season=effective_season, error=str(api_check_error))
                return format_response(error=error_msg)

        processed_standings = _process_dataframe(standings_df, single_row=False)
        
        # Log raw processed data before modifications for debugging PCT/GB
        if processed_standings:
            logger.debug(f"Raw processed standings data (first 2 teams) for {effective_season}, type {season_type}: {json.dumps(processed_standings[:2], indent=2)}")
        elif standings_df.empty:
            logger.debug(f"Standings DataFrame was empty from API for {effective_season}, type {season_type}.")
        else: # processed_standings is None but standings_df was not empty
            logger.error(f"Standings DataFrame processing failed for {effective_season}, type {season_type}, though API returned data.")


        if processed_standings is None: # Error during _process_dataframe
            logger.error(f"DataFrame processing failed for standings ({effective_season}).")
            error_msg = Errors.LEAGUE_STANDINGS_PROCESSING.format(season=effective_season)
            return format_response(error=error_msg)

        # Add a 'GB' field based on 'ConferenceGamesBack' for frontend compatibility
        # Also ensure WinPct is explicitly cast to float if it's not already.
        for team_data in processed_standings:
            gb_value = team_data.get('ConferenceGamesBack')
            if isinstance(gb_value, (int, float)):
                team_data['GB'] = gb_value
            elif isinstance(gb_value, str) and gb_value.strip() == '-': # API might send '-' for leader
                 team_data['GB'] = 0.0 # Treat as 0.0 for leader, frontend util can format to '-'
            elif gb_value is None:
                 team_data['GB'] = None # Pass null if API provides null
            else: # Attempt to convert if it's a string number, otherwise null
                try:
                    team_data['GB'] = float(gb_value)
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert ConferenceGamesBack '{gb_value}' to float for team {team_data.get('TeamID')}. Setting GB to null.")
                    team_data['GB'] = None
            
            # Ensure WinPct is a float, default to 0.0 if missing or cannot be converted
            try:
                win_pct_val = team_data.get('WinPCT') # Corrected case to WinPCT
                team_data['WinPct'] = float(win_pct_val) if win_pct_val is not None else 0.0 # Keep lowercase 'c' for the key being set for frontend
            except (ValueError, TypeError):
                logger.warning(f"Could not convert WinPCT '{team_data.get('WinPCT')}' to float for team {team_data.get('TeamID')}. Defaulting to 0.0.")
                team_data['WinPct'] = 0.0 # Keep lowercase 'c' for the key being set
            
            # Map strCurrentStreak to STRK for frontend
            team_data['STRK'] = team_data.get('strCurrentStreak', '') # Default to empty string if not present
        
        processed_standings.sort(key=lambda x: (x.get("Conference", ""), x.get("PlayoffRank", 99)))
        logger.info(f"Successfully fetched and processed standings for season {effective_season}, type {season_type}.")
        return format_response({"standings": processed_standings})

    except Exception as e:
        logger.error(f"Unexpected error in fetch_league_standings_logic for season {effective_season}: {str(e)}", exc_info=True)
        error_msg = Errors.LEAGUE_STANDINGS_UNEXPECTED.format(season=effective_season, error=str(e))
        return format_response(error=error_msg)

@lru_cache(maxsize=32)
def fetch_draft_history_logic(
    season_year_nullable: Optional[str] = None,
    league_id_nullable: str = LeagueID.nba,
    team_id_nullable: Optional[int] = None,
    round_num_nullable: Optional[int] = None,
    overall_pick_nullable: Optional[int] = None
) -> str:
    """
    Fetches NBA draft history, optionally filtered by season year, league, team, round number, or overall pick.

    Args:
        season_year_nullable (str, optional): The draft year in YYYY format (e.g., "2023").
                                              If None, fetches data for all available draft years (can be large).
        league_id_nullable (str, optional): The league ID. Valid values from `LeagueID` (e.g., "00" for NBA).
                                            Defaults to "00" (NBA).
        team_id_nullable (int, optional): Filter by the ID of the drafting team. Defaults to None (no team filter).
        round_num_nullable (int, optional): Filter by draft round number (e.g., 1 or 2). Defaults to None.
        overall_pick_nullable (int, optional): Filter by the overall pick number in the draft. Defaults to None.

    Returns:
        str: JSON string containing a list of draft picks.
             Expected dictionary structure passed to format_response:
             {
                 "season_year_requested": str, // "All" if season_year_nullable was None
                 "league_id": str,
                 "team_id_filter": Optional[int],
                 "round_num_filter": Optional[int],
                 "overall_pick_filter": Optional[int],
                 "draft_picks": [
                     {
                         "PERSON_ID": int, "PLAYER_NAME": str, "SEASON": str (YYYY), "ROUND_NUMBER": int,
                         "ROUND_PICK": int, "OVERALL_PICK": int, "DRAFT_TYPE": str, "TEAM_ID": int,
                         "TEAM_CITY": str, "TEAM_NAME": str, "TEAM_ABBREVIATION": str,
                         "ORGANIZATION": str, "ORGANIZATION_TYPE": str, "PLAYER_PROFILE_FLAG": Optional[int], ...
                     }, ...
                 ]
             }
             Returns {"draft_picks": []} if no data is found for the criteria.
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    year_log_display = season_year_nullable or "All"
    logger.info(f"Executing fetch_draft_history_logic for SeasonYear: {year_log_display}, League: {league_id_nullable}, Team: {team_id_nullable}, Round: {round_num_nullable}, Pick: {overall_pick_nullable}")

    if season_year_nullable and (not season_year_nullable.isdigit() or len(season_year_nullable) != 4):
        error_msg = Errors.INVALID_DRAFT_YEAR_FORMAT.format(year=season_year_nullable)
        logger.error(error_msg)
        return format_response(error=error_msg)

    VALID_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}
    if league_id_nullable not in VALID_LEAGUE_IDS:
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id_nullable, options=", ".join(VALID_LEAGUE_IDS)))

    try:
        logger.debug(f"Fetching drafthistory for SeasonYear: {year_log_display}, League: {league_id_nullable}")
        draft_endpoint = drafthistory.DraftHistory(
            league_id=league_id_nullable, # API expects league_id
            season_year_nullable=season_year_nullable,
            team_id_nullable=team_id_nullable,
            round_num_nullable=round_num_nullable,
            overall_pick_nullable=overall_pick_nullable,
            timeout=DEFAULT_TIMEOUT
        )
        logger.debug(f"drafthistory API call successful for SeasonYear: {year_log_display}")
        draft_df = draft_endpoint.draft_history.get_data_frame()
        draft_list = _process_dataframe(draft_df, single_row=False)

        if draft_list is None: # Error during processing
            if draft_df.empty: # API returned no data
                logger.warning(f"No draft history data found for year {year_log_display} with specified filters.")
                # Return empty list, not an error, if API simply found no matches
                return format_response({
                    "season_year_requested": year_log_display, "league_id": league_id_nullable,
                    "team_id_filter": team_id_nullable, "round_num_filter": round_num_nullable,
                    "overall_pick_filter": overall_pick_nullable, "draft_picks": []
                })
            else: # Processing failed on non-empty data
                logger.error(f"DataFrame processing failed for draft history ({year_log_display}).")
                error_msg = Errors.DRAFT_HISTORY_PROCESSING.format(year=year_log_display)
                return format_response(error=error_msg)
        
        result = {
            "season_year_requested": year_log_display, "league_id": league_id_nullable,
            "team_id_filter": team_id_nullable, "round_num_filter": round_num_nullable,
            "overall_pick_filter": overall_pick_nullable, "draft_picks": draft_list or []
        }
        logger.info(f"fetch_draft_history_logic completed for SeasonYear: {year_log_display}")
        return format_response(result)

    except Exception as e:
        logger.critical(f"Unexpected error in fetch_draft_history_logic for SeasonYear '{year_log_display}': {e}", exc_info=True)
        error_msg = Errors.DRAFT_HISTORY_UNEXPECTED.format(year=year_log_display, error=str(e))
        return format_response(error=error_msg)

@lru_cache(maxsize=128)
def fetch_league_leaders_logic(
    season: str,
    stat_category: str = StatCategoryAbbreviation.pts,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerMode48.per_game,
    league_id: str = LeagueID.nba,
    scope: str = Scope.s, # S = Season, RS = Regular Season, A = All Players (Rookies, Sophomores, etc.)
    top_n: int = 10
) -> str:
    """
    Fetches league leaders for a specific statistical category, season, and other criteria.
    Includes a direct HTTP request attempt for debugging potential 'resultSet' issues with the NBA API.

    Args:
        season (str): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
        stat_category (str, optional): The statistical category abbreviation. Valid values from `StatCategoryAbbreviation`
                                     (e.g., "PTS", "REB", "AST", "STL", "BLK", "FG_PCT", "FG3_PCT", "FT_PCT", "EFF").
                                     Defaults to "PTS".
        season_type (str, optional): The type of season. Valid values from `SeasonTypeAllStar`
                                     (e.g., "Regular Season", "Playoffs", "Pre Season", "All Star").
                                     Defaults to "Regular Season".
        per_mode (str, optional): The statistical mode. Valid values from `PerMode48` (e.g., "PerGame", "Totals", "Per48").
                                  Defaults to "PerGame".
        league_id (str, optional): The league ID. Valid values from `LeagueID` (e.g., "00" for NBA).
                                   Defaults to "00" (NBA).
        scope (str, optional): The scope of the player search. Valid values from `Scope` (e.g., "S" for Season, "RS" for Regular Season, "A" for All Players, "Rookies").
                               Defaults to "S".
        top_n (int, optional): The number of top players to return. Defaults to 10. Max usually 200-250 by API.

    Returns:
        str: JSON string containing a list of league leaders.
             Expected dictionary structure passed to format_response:
             {
                 "leaders": [
                     {
                         "PLAYER_ID": int, "RANK": int, "PLAYER": str, "TEAM_ID": int, "TEAM": str, // Team abbreviation
                         "GP": int, "MIN": float, // Minutes per game or total depending on per_mode
                         stat_category: float // The actual stat value, e.g., "PTS": 25.5
                         // Other stats might be included by the API depending on the category
                     }, ...
                 ]
             }
             Returns {"leaders": []} if no data is found.
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.info(f"Executing fetch_league_leaders_logic for season: {season}, category: {stat_category}, type: {season_type}, per_mode: {per_mode}, scope: {scope}, top_n: {top_n}")

    if not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if not isinstance(top_n, int) or top_n <= 0: # top_n must be positive
        logger.warning(f"Invalid top_n value '{top_n}'. Must be a positive integer. Defaulting to 10.")
        top_n = 10
    
    # Validate other parameters against nba_api library constants
    VALID_STAT_CATEGORIES = {getattr(StatCategoryAbbreviation, attr) for attr in dir(StatCategoryAbbreviation) if not attr.startswith('_')}
    if stat_category not in VALID_STAT_CATEGORIES:
        return format_response(error=Errors.INVALID_STAT_CATEGORY.format(value=stat_category, options=", ".join(VALID_STAT_CATEGORIES)))
    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(VALID_SEASON_TYPES)))
    VALID_PER_MODES = {getattr(PerMode48, attr) for attr in dir(PerMode48) if not attr.startswith('_') and isinstance(getattr(PerMode48, attr), str)}
    if per_mode not in VALID_PER_MODES:
        return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(VALID_PER_MODES)))
    VALID_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}
    if league_id not in VALID_LEAGUE_IDS:
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(VALID_LEAGUE_IDS)))
    VALID_SCOPES = {getattr(Scope, attr) for attr in dir(Scope) if not attr.startswith('_') and isinstance(getattr(Scope, attr), str)}
    if scope not in VALID_SCOPES:
        return format_response(error=Errors.INVALID_SCOPE.format(value=scope, options=", ".join(VALID_SCOPES)))


    # Direct HTTP Request for Debugging (Optional, can be removed if stable)
    stats_url = "https://stats.nba.com/stats/leagueleaders"
    http_params = {
        "LeagueID": league_id, "PerMode": per_mode, "Scope": scope,
        "Season": season, "SeasonType": season_type, "StatCategory": stat_category,
    }
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://stats.nba.com/', 'Accept': 'application/json'}
    raw_response_status_for_log = None

    try: # Attempt with nba_api library first
        logger.debug(f"Calling leagueleaders.LeagueLeaders with params: {http_params}")
        leaders_endpoint = leagueleaders.LeagueLeaders(
            league_id=league_id, per_mode48=per_mode, scope=scope, season=season,
            season_type_all_star=season_type, stat_category_abbreviation=stat_category,
            timeout=DEFAULT_TIMEOUT
        )
        leaders_df = leaders_endpoint.league_leaders.get_data_frame()
        logger.debug(f"nba_api leagueleaders call successful for {stat_category} ({season})")

    except KeyError as ke: # Specifically catch KeyError related to 'resultSet'
        if 'resultSet' in str(ke):
            logger.error(f"KeyError 'resultSet' using nba_api for {stat_category} ({season}). NBA API response likely malformed.", exc_info=True)
            # Attempt direct request to log more info
            try:
                response = requests.get(stats_url, headers=headers, params=http_params, timeout=5) # Shorter timeout for debug
                raw_response_status_for_log = response.status_code
                logger.debug(f"Direct HTTP debug request status: {raw_response_status_for_log}, Response (first 500): {response.text[:500]}")
            except Exception as direct_req_err:
                logger.error(f"Direct HTTP debug request failed: {direct_req_err}")
            error_msg = Errors.LEAGUE_LEADERS_API_KEY_ERROR.format(stat=stat_category, season=season) + f" (Direct status: {raw_response_status_for_log or 'N/A'})"
            return format_response(error=error_msg)
        else:
            raise ke # Re-raise other KeyErrors
    except Exception as api_error: # Catch other nba_api errors
        logger.error(f"nba_api leagueleaders failed for {stat_category} ({season}): {api_error}", exc_info=True)
        error_msg = Errors.LEAGUE_LEADERS_API.format(stat=stat_category, season=season, error=str(api_error))
        return format_response(error=error_msg)

    if leaders_df.empty:
        logger.warning(f"No league leaders data found via nba_api for {stat_category} ({season}).")
        return format_response({"leaders": []})

    # Ensure the requested stat_category column exists, plus common columns
    expected_cols = ['PLAYER_ID', 'RANK', 'PLAYER', 'TEAM_ID', 'TEAM', 'GP', 'MIN']
    if stat_category not in leaders_df.columns: # If the specific stat_category isn't a column, it's an issue
        logger.error(f"Stat category '{stat_category}' not found in league leaders DataFrame columns: {list(leaders_df.columns)}")
        # This might indicate an issue with the API not returning the stat as expected for the given params
        return format_response(error=Errors.LEAGUE_LEADERS_PROCESSING.format(stat=stat_category, season=season) + f" - Stat column '{stat_category}' missing.")

    available_cols = [col for col in expected_cols if col in leaders_df.columns]
    if stat_category not in available_cols : # Add if not already present (it should be after above check)
        available_cols.append(stat_category)
    
    # Ensure unique columns if stat_category is already in expected_cols (e.g. MIN)
    final_cols = []
    for col in available_cols:
        if col not in final_cols:
            final_cols.append(col)

    leaders_list = _process_dataframe(leaders_df.loc[:, final_cols], single_row=False)

    if leaders_list is None:
        logger.error(f"DataFrame processing failed for league leaders {stat_category} ({season}).")
        error_msg = Errors.LEAGUE_LEADERS_PROCESSING.format(stat=stat_category, season=season)
        return format_response(error=error_msg)

    if top_n > 0: # Apply top_n slicing
        leaders_list = leaders_list[:top_n]

    logger.info(f"fetch_league_leaders_logic completed for {stat_category} ({season}) using nba_api, found {len(leaders_list)} leaders.")
    return format_response({"leaders": leaders_list})

    # The outer try/except Exception as e block was removed as specific errors are handled above.
    # If any other exception occurs, it will be a 500 from FastAPI.

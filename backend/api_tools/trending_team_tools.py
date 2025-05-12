import logging
import json
from datetime import datetime
from typing import Any, Tuple
from functools import lru_cache

from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID
from backend.api_tools.league_standings import fetch_league_standings_logic
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import format_response
from backend.utils.validation import _validate_season_format
logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS_TRENDING_TEAMS = 3600 * 4 # Cache standings for trending teams for 4 hours

# Module-level constants for validation
_TRENDING_TEAMS_VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_TRENDING_TEAMS_VALID_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

@lru_cache(maxsize=16) # Cache a few common season/type combinations
def get_cached_standings_for_trending_teams( # Renamed for clarity
    cache_key: Tuple, # e.g., (season, season_type, league_id)
    timestamp: str,   # Timestamp for TTL invalidation (e.g., hourly bucket)
    **kwargs: Any      # Parameters for fetch_league_standings_logic
) -> str:
    """
    Cached wrapper for `fetch_league_standings_logic`, used by `fetch_top_teams_logic`.
    Uses a timestamp for time-based cache invalidation.

    Args:
        cache_key (Tuple): A tuple representing the core parameters for fetching standings
                           (e.g., (season, season_type, league_id)), used for `lru_cache` keying.
        timestamp (str): An ISO format timestamp string, typically for the current cache validity window (e.g., every 4 hours),
                         used to manage cache invalidation.
        **kwargs: Keyword arguments to be passed directly to `fetch_league_standings_logic`
                  (e.g., `season`, `season_type`, `league_id`).

    Returns:
        str: The JSON string result from `fetch_league_standings_logic`.

    Raises:
        Exception: If `fetch_league_standings_logic` fails, to be handled by the caller.
    """
    logger.info(f"Cache miss/expiry for standings (trending_teams) - fetching new data. Key components: {kwargs.get('season')}, {kwargs.get('season_type')}, League: {kwargs.get('league_id')}")
    try:
        # Prepare arguments specifically for fetch_league_standings_logic
        standings_logic_args = {
            "season": kwargs.get("season"),
            "season_type": kwargs.get("season_type"),
            "league_id": kwargs.get("league_id") # Ensure league_id is passed through
        }
        # Filter out None values to rely on defaults in fetch_league_standings_logic if not provided
        standings_logic_args = {k: v for k, v in standings_logic_args.items() if v is not None}
        
        return fetch_league_standings_logic(**standings_logic_args)
    except Exception as e:
        logger.error(f"fetch_league_standings_logic failed within get_cached_standings_for_trending_teams (Season: {kwargs.get('season')}, Type: {kwargs.get('season_type')}): {e}", exc_info=True)
        raise e

@lru_cache(maxsize=64) # Cache the final processed list of top teams
def fetch_top_teams_logic(
    season: str = settings.CURRENT_NBA_SEASON, # Changed
    season_type: str = SeasonTypeAllStar.regular,
    league_id: str = LeagueID.nba, # Added league_id parameter
    top_n: int = 5,
    bypass_cache: bool = False
) -> str:
    """
    Fetches the top N performing teams based on win percentage for a given season, season type, and league.
    It utilizes cached league standings data.

    Args:
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
                                Defaults to `CURRENT_SEASON`.
        season_type (str, optional): The type of season. Valid values from `SeasonTypeAllStar`
                                     (e.g., "Regular Season", "Playoffs"). Defaults to "Regular Season".
        league_id (str, optional): The league ID. Valid values from `LeagueID` (e.g., "00" for NBA).
                                   Defaults to "00" (NBA).
        top_n (int, optional): The number of top teams to return. Must be a positive integer. Defaults to 5.
        bypass_cache (bool, optional): If True, ignores cached standings data and fetches fresh data.
                                       Defaults to False.

    Returns:
        str: JSON string with top teams data.
             Expected dictionary structure passed to format_response:
             {
                 "season": str,
                 "season_type": str,
                 "league_id": str,
                 "requested_top_n": int,
                 "top_teams": [ // List of team objects, sorted by WinPct descending
                     {
                         "TeamID": int,
                         "TeamName": str,
                         "Conference": Optional[str],
                         "PlayoffRank": Optional[int],
                         "WinPct": Optional[float],
                         "WINS": Optional[int],
                         "LOSSES": Optional[int]
                         // Other fields from standings like Record, L10 might be included if essential_fields is expanded
                     }, ...
                 ]
             }
             Returns {"top_teams": []} if no standings data is available or no teams are found.
             Or an {'error': 'Error message'} object if a critical issue occurs.
    """
    logger.info(f"Executing fetch_top_teams_logic for season: {season}, type: {season_type}, league: {league_id}, top_n: {top_n}")

    if not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if not isinstance(top_n, int) or top_n < 1:
        error_msg = Errors.INVALID_TOP_N.format(value=top_n)
        return format_response(error=error_msg)

    if season_type not in _TRENDING_TEAMS_VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_TRENDING_TEAMS_VALID_SEASON_TYPES)[:5])))
    
    if league_id not in _TRENDING_TEAMS_VALID_LEAGUE_IDS:
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_TRENDING_TEAMS_VALID_LEAGUE_IDS)[:3])))


    cache_key_for_standings = (season, season_type, league_id) # Key for fetching standings
    current_time_epoch = int(datetime.now().timestamp())
    timestamp_bucket_for_standings = str(current_time_epoch // CACHE_TTL_SECONDS_TRENDING_TEAMS)

    try:
        standings_params = {"season": season, "season_type": season_type, "league_id": league_id} # league_id for fetch_league_standings_logic
        
        standings_json_str: str
        if bypass_cache:
            logger.info(f"Bypassing cache, fetching fresh standings data for {season}, type {season_type}, league {league_id}")
            standings_json_str = fetch_league_standings_logic(**standings_params)
        else:
            standings_json_str = get_cached_standings_for_trending_teams(
                cache_key=cache_key_for_standings,
                timestamp=timestamp_bucket_for_standings,
                **standings_params
            )
        
        try:
            standings_data = json.loads(standings_json_str)
        except json.JSONDecodeError as json_err:
            logger.error(f"Failed to decode JSON from standings logic: {json_err}. Response (first 500): {standings_json_str[:500]}")
            error_msg = Errors.PROCESSING_ERROR.format(error="invalid JSON format from standings data")
            return format_response(error=error_msg)

        if isinstance(standings_data, dict) and "error" in standings_data:
            logger.error(f"Error received from fetch_league_standings_logic: {standings_data['error']}")
            return standings_json_str # Propagate the error JSON

        standings_list = standings_data.get("standings", [])
        if not standings_list:
            logger.warning(f"No standings data available to determine top teams for {season}, type {season_type}, league {league_id}.")
            return format_response({
                "season": season, "season_type": season_type, "league_id": league_id,
                "requested_top_n": top_n, "top_teams": []
            })

        try:
            standings_sorted_list = sorted(
                standings_list,
                key=lambda x: float(x.get("WinPct", 0.0) or 0.0), # Handle None or empty string for WinPct
                reverse=True
            )
        except (ValueError, TypeError) as sort_err:
            logger.warning(f"Error sorting standings by WinPct: {sort_err}. Proceeding with unsorted top N from original list.")
            standings_sorted_list = standings_list # Fallback to original list

        top_teams_list = []
        # Define essential fields to extract for each top team
        essential_fields = ["TeamID", "TeamName", "Conference", "PlayoffRank", "WinPct", "WINS", "LOSSES", "Record", "LeagueRank"]
        for team_data in standings_sorted_list[:top_n]:
            top_team_info = {field: team_data.get(field) for field in essential_fields if field in team_data}
            top_teams_list.append(top_team_info)

        result_payload = {
            "season": season, "season_type": season_type, "league_id": league_id,
            "requested_top_n": top_n, "top_teams": top_teams_list
        }
        logger.info(f"Successfully determined top {len(top_teams_list)} teams for {season}, type {season_type}, league {league_id}.")
        return format_response(result_payload)

    except Exception as e:
        logger.error(f"Unexpected error in fetch_top_teams_logic: {e}", exc_info=True)
        error_msg = Errors.TRENDING_TEAMS_UNEXPECTED.format(error=str(e))
        return format_response(error=error_msg)

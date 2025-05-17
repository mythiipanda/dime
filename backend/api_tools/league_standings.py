"""
Handles fetching and processing NBA league standings data.
"""
import logging
import json
from typing import Optional, Dict, Any, List, Set
import pandas as pd
# import numpy as np # Not strictly needed if _process_dataframe handles numpy types
from functools import lru_cache
from datetime import datetime, date

from nba_api.stats.endpoints import leaguestandingsv3
from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID
from backend.api_tools.utils import format_response, _process_dataframe # Import _process_dataframe
from backend.utils.validation import _validate_season_format
from backend.config import settings
from backend.core.errors import Errors

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
LEAGUE_STANDINGS_RAW_CACHE_SIZE = 32
LEAGUE_STANDINGS_PROCESSED_CACHE_SIZE = 64
DEFAULT_PLAYOFF_RANK_SORT = 99

_VALID_LEAGUE_STANDINGS_SEASON_TYPES: Set[str] = {SeasonTypeAllStar.regular, SeasonTypeAllStar.preseason}
_VALID_LEAGUE_IDS_FOR_STANDINGS: Set[str] = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

# Columns to extract and their order for the final response
_STANDINGS_COLUMNS_TO_KEEP = [
    'TeamID', 'TeamCity', 'TeamName', 'TeamSlug',
    'Conference', 'ConferenceRecord', 'PlayoffRank',
    'ClinchIndicator',
    'Division', 'DivisionRecord', 'DivisionRank',
    'WINS', 'LOSSES', 'WinPCT', 'LeagueRank', 'Record',
    'HOME', 'ROAD', 'L10',
    'strCurrentStreak', 'ConferenceGamesBack', 'DivisionGamesBack',
    'PointsPG', 'OppPointsPG', 'DiffPointsPG',
    'ClinchedConferenceTitle', 'ClinchedDivisionTitle',
    'ClinchedPlayoffBirth', 'ClinchedPlayIn'
]

# --- Helper Functions ---
@lru_cache(maxsize=LEAGUE_STANDINGS_RAW_CACHE_SIZE)
def get_cached_standings(season: str, season_type: str, league_id: str, timestamp: str) -> pd.DataFrame:
    """
    Cached wrapper for nba_api's LeagueStandingsV3 endpoint.

    Args:
        season: NBA season in 'YYYY-YY' format.
        season_type: Season type (e.g., 'Regular Season').
        league_id: League ID (e.g., '00' for NBA).
        timestamp: ISO-formatted timestamp for cache invalidation.

    Returns:
        pd.DataFrame: DataFrame with league standings.

    Raises:
        Exception: If the API call fails.
    """
    logger.info(f"Cache miss/expiry for standings - fetching for {season}, {season_type}, {league_id} (ts: {timestamp})")
    try:
        standings_endpoint = leaguestandingsv3.LeagueStandingsV3(
            season=season, season_type=season_type, league_id=league_id,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        return standings_endpoint.standings.get_data_frame()
    except Exception as e:
        logger.error(f"API call failed in get_cached_standings for {season}, {season_type}, {league_id}: {e}", exc_info=True)
        raise

def _enrich_standings_records(standings_records: List[Dict[str, Any]]) -> None:
    """
    Enriches processed standings records with 'GB', 'WinPct', and 'STRK' fields.
    Modifies the list in place.
    """
    for team_data in standings_records:
        gb_value = team_data.get('ConferenceGamesBack')
        if isinstance(gb_value, (int, float)):
            team_data['GB'] = gb_value
        elif isinstance(gb_value, str) and gb_value.strip() == '-':
            team_data['GB'] = 0.0
        elif gb_value is None:
            team_data['GB'] = None # Explicitly set to None
        else:
            try:
                team_data['GB'] = float(gb_value)
            except (ValueError, TypeError):
                logger.warning(f"Could not convert ConferenceGamesBack '{gb_value}' to float for team {team_data.get('TeamID')}. Setting GB to None.")
                team_data['GB'] = None
        
        try:
            win_pct_val = team_data.get('WinPCT') # Original column name
            team_data['WinPct'] = float(win_pct_val) if win_pct_val is not None else 0.0
        except (ValueError, TypeError):
            logger.warning(f"Could not convert WinPCT '{team_data.get('WinPCT')}' to float for team {team_data.get('TeamID')}. Defaulting to 0.0.")
            team_data['WinPct'] = 0.0
        
        team_data['STRK'] = team_data.get('strCurrentStreak', '')


# --- Main Logic Function ---
@lru_cache(maxsize=LEAGUE_STANDINGS_PROCESSED_CACHE_SIZE)
def fetch_league_standings_logic(
    season: Optional[str] = None,
    season_type: str = SeasonTypeAllStar.regular,
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches and processes league standings for a specific season, type, and league.

    Args:
        season: NBA season in 'YYYY-YY' format. Defaults to current.
        season_type: Season type. Defaults to 'Regular Season'.
        league_id: League ID. Defaults to NBA.

    Returns:
        JSON string of team standings or an error message.
    """
    effective_season = season or settings.CURRENT_NBA_SEASON
    logger.info(f"Executing fetch_league_standings_logic for season: {effective_season}, type: {season_type}, league: {league_id}")

    if not _validate_season_format(effective_season): # Assuming league_id is not needed for basic season format validation here
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=effective_season))
    if season_type not in _VALID_LEAGUE_STANDINGS_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_LEAGUE_STANDINGS_SEASON_TYPES)[:5])))
    if league_id not in _VALID_LEAGUE_IDS_FOR_STANDINGS:
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_VALID_LEAGUE_IDS_FOR_STANDINGS)[:3])))

    try:
        current_hour_timestamp = datetime.now().replace(minute=0, second=0, microsecond=0).isoformat()
        standings_df = get_cached_standings(effective_season, season_type, league_id, current_hour_timestamp)

        if standings_df.empty:
            logger.warning(f"No standings data found for {effective_season}, {season_type}, {league_id} from API.")
            return format_response({"standings": [], "league_id_processed": league_id})

        cols_to_extract = [col for col in _STANDINGS_COLUMNS_TO_KEEP if col in standings_df.columns]
        if not cols_to_extract:
            logger.error(f"None of the expected columns for standings processing found for {effective_season}, {season_type}, {league_id}.")
            return format_response(error=Errors.LEAGUE_STANDINGS_PROCESSING.format(season=effective_season, season_type=season_type))

        # Use the utility _process_dataframe on the sliced DataFrame
        sliced_df = standings_df[cols_to_extract]
        processed_standings = _process_dataframe(sliced_df, single_row=False)

        if processed_standings is None: # _process_dataframe returned None due to an internal error
            logger.error(f"DataFrame processing with _process_dataframe failed for standings ({effective_season}, Type: {season_type}, League: {league_id}).")
            return format_response(error=Errors.LEAGUE_STANDINGS_PROCESSING.format(season=effective_season, season_type=season_type))
        
        if not processed_standings and not sliced_df.empty: # Should not happen if _process_dataframe is robust
             logger.error(f"_process_dataframe resulted in empty list for non-empty sliced_df for standings ({effective_season}, Type: {season_type}, League: {league_id}).")
             return format_response(error=Errors.LEAGUE_STANDINGS_PROCESSING.format(season=effective_season, season_type=season_type))

        _enrich_standings_records(processed_standings)
        
        # Sort by Conference, then by PlayoffRank
        processed_standings.sort(key=lambda x: (x.get("Conference", ""), x.get("PlayoffRank", DEFAULT_PLAYOFF_RANK_SORT)))
        
        logger.info(f"Successfully fetched and processed standings for {effective_season}, {season_type}, {league_id}.")
        return format_response({"standings": processed_standings, "league_id_processed": league_id})

    except Exception as e: # Catches API errors from get_cached_standings or other unexpected errors
        logger.error(f"Unexpected error in fetch_league_standings_logic for {effective_season}, {season_type}, {league_id}: {str(e)}", exc_info=True)
        # Determine if it was an API error from get_cached_standings or a processing error
        # For simplicity, using a general error message here. More specific handling could be added.
        error_msg = Errors.LEAGUE_STANDINGS_UNEXPECTED.format(season=effective_season, season_type=season_type, error=str(e))
        return format_response(error=error_msg)
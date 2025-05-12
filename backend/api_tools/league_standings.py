import logging
import json
from typing import Optional, Dict, Any, List
import pandas as pd
import numpy as np # For np.integer, np.floating, np.bool_
from functools import lru_cache
from datetime import datetime, date # Ensure date is imported

from nba_api.stats.endpoints import leaguestandingsv3
from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID
from backend.api_tools.utils import format_response # _process_dataframe will be replaced by custom logic here
from backend.utils.validation import _validate_season_format
from backend.config import settings
from backend.core.errors import Errors

logger = logging.getLogger(__name__)

# Module-level constant for valid season types, specific to LeagueStandingsV3
_VALID_LEAGUE_STANDINGS_SEASON_TYPES = {SeasonTypeAllStar.regular, SeasonTypeAllStar.preseason} # As per API docs for V3

_VALID_LEAGUE_IDS_FOR_STANDINGS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

@lru_cache(maxsize=32)
def get_cached_standings(season: str, season_type: str, league_id: str, timestamp: str) -> pd.DataFrame:
    """
    Cached wrapper for nba_api's LeagueStandingsV3 endpoint. Fetches league standings for a given season, season type, and league.

    Args:
        season (str): NBA season in 'YYYY-YY' format (e.g., '2022-23').
        season_type (str): Season type (e.g., 'Regular Season', 'Pre Season').
        league_id (str): League ID (e.g., '00' for NBA).
        timestamp (str): ISO-formatted timestamp to force cache invalidation (typically hourly).

    Returns:
        pd.DataFrame: DataFrame containing league standings data.

    Raises:
        Exception: If the API call fails.
    """
    logger.info(f"Cache miss or expiry for standings - fetching new data for season {season}, type {season_type}, league {league_id} (timestamp: {timestamp})")
    try:
        standings_endpoint = leaguestandingsv3.LeagueStandingsV3(
            season=season,
            season_type=season_type,
            league_id=league_id,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        return standings_endpoint.standings.get_data_frame()
    except Exception as e:
        logger.error(f"API call failed in get_cached_standings for season {season}, type {season_type}, league {league_id}: {e}", exc_info=True)
        raise # Re-raise the exception to be handled by the caller

@lru_cache(maxsize=64)
def fetch_league_standings_logic(
    season: Optional[str] = None,
    season_type: str = SeasonTypeAllStar.regular,
    league_id: str = LeagueID.nba # Add league_id parameter
) -> str:
    """
    Fetches league standings for a specific season, season type, and league using nba_api's LeagueStandingsV3 endpoint.
    Applies custom DataFrame processing and returns a JSON-formatted string with standings data.

    Args:
        season (Optional[str]): NBA season in 'YYYY-YY' format. Defaults to current season from settings.
        season_type (str): Season type (e.g., 'Regular Season', 'Pre Season'). Defaults to 'Regular Season'.
        league_id (str): League ID (e.g., '00' for NBA). Defaults to NBA.

    Returns:
        str: JSON-formatted string containing a list of team standings or an error message.

    Notes:
        - Uses an hourly-invalidating cache for the raw API call.
        - Returns an error for invalid season format, season type, or league ID.
        - Custom processing extracts and normalizes key columns for frontend consumption.
    """
    effective_season = season or settings.CURRENT_NBA_SEASON
    logger.info(f"Executing fetch_league_standings_logic for season: {effective_season}, type: {season_type}, league: {league_id}")

    if not _validate_season_format(effective_season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=effective_season))

    if season_type not in _VALID_LEAGUE_STANDINGS_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_VALID_LEAGUE_STANDINGS_SEASON_TYPES)[:5])))
    
    if league_id not in _VALID_LEAGUE_IDS_FOR_STANDINGS:
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_VALID_LEAGUE_IDS_FOR_STANDINGS)[:3])))

    try:
        current_hour_timestamp = datetime.now().replace(minute=0, second=0, microsecond=0).isoformat()
        standings_df = get_cached_standings(effective_season, season_type, league_id, current_hour_timestamp) # This will now raise on API error

        # Diagnostic logs for raw DataFrame can be removed or commented out now that processing is stable
        # if standings_df is not None and not standings_df.empty:
        #     logger.debug(f"Standings DataFrame for {effective_season}, {season_type}, {league_id} BEFORE processing:")
        #     try:
        #         import io
        #         buffer = io.StringIO()
        #         standings_df.info(verbose=True, show_counts=True, buf=buffer)
        #         logger.debug(f"standings_df.info():\n{buffer.getvalue()}")
        #         logger.debug(f"standings_df.head().to_dict():\n{standings_df.head().to_dict()}")
        #     except Exception as df_info_err:
        #         logger.error(f"Error getting standings_df info: {df_info_err}")
        # elif standings_df is not None and standings_df.empty:
        #     logger.debug(f"Standings DataFrame for {effective_season}, {season_type}, {league_id} is EMPTY from API/cache.")
        # else:
        #     logger.error(f"Standings DataFrame for {effective_season}, {season_type}, {league_id} is None unexpectedly.")

        # If standings_df is empty, it means the API call was successful but returned no data.
        if standings_df.empty:
            logger.warning(f"No standings data found for season {effective_season}, type {season_type}, league {league_id} from API.")
            return format_response({"standings": [], "league_id_processed": league_id})

        # Define a comprehensive set of columns to extract for the standings response
        cols_to_keep = [
            'TeamID', 'TeamCity', 'TeamName', 'TeamSlug',
            'Conference', 'ConferenceRecord', 'PlayoffRank',
            'ClinchIndicator', # e.g., ' - e', ' - x', ' - pi'
            'Division', 'DivisionRecord', 'DivisionRank',
            'WINS', 'LOSSES', 'WinPCT', 'LeagueRank', 'Record',
            'HOME', 'ROAD', 'L10',
            'strCurrentStreak', 'ConferenceGamesBack', 'DivisionGamesBack',
            'PointsPG', 'OppPointsPG', 'DiffPointsPG', # Added these as they are generally useful
            'ClinchedConferenceTitle', 'ClinchedDivisionTitle',
            'ClinchedPlayoffBirth', 'ClinchedPlayIn'
        ]
        # Custom processing for standings DataFrame to avoid generic _process_dataframe issues
        processed_standings = []
        cols_to_extract_from_df = [col for col in cols_to_keep if col in standings_df.columns]
        if not cols_to_extract_from_df:
            logger.error(f"None of the expected columns for standings processing were found in the DataFrame for {effective_season}, {season_type}, {league_id}.")
            error_msg = Errors.LEAGUE_STANDINGS_PROCESSING.format(season=effective_season, season_type=season_type)
            return format_response(error=error_msg)

        try:
            for index, row_series in standings_df.iterrows(): # Iterate over the original standings_df
                record = {}
                for col_name in cols_to_extract_from_df:
                    value = row_series.get(col_name)
                    try:
                        if pd.isna(value):
                            record[col_name] = None
                        elif isinstance(value, np.integer):
                            record[col_name] = int(value)
                        elif isinstance(value, np.floating):
                            record[col_name] = float(value)
                        elif isinstance(value, np.bool_):
                            record[col_name] = bool(value)
                        elif isinstance(value, (datetime, date, pd.Timestamp)): # pd.Timestamp for safety
                            record[col_name] = value.isoformat()
                        elif isinstance(value, (int, float, bool, str)):
                            record[col_name] = value
                        else:
                            record[col_name] = str(value)
                    except Exception as cell_err:
                        logger.warning(f"Error converting cell for standings col '{col_name}', value '{value}': {cell_err}. Setting to None.")
                        record[col_name] = None
                processed_standings.append(record)
        except Exception as iter_err:
            logger.error(f"Error during standings DataFrame iteration or custom processing: {iter_err}", exc_info=True)
            error_msg = Errors.LEAGUE_STANDINGS_PROCESSING.format(season=effective_season, season_type=season_type)
            return format_response(error=error_msg)

        if not processed_standings and not standings_df.empty:
            logger.error(f"Custom DataFrame processing resulted in empty list for non-empty standings_df ({effective_season}, Type: {season_type}, League: {league_id}). This indicates a processing logic error.")
            error_msg = Errors.LEAGUE_STANDINGS_PROCESSING.format(season=effective_season, season_type=season_type)
            return format_response(error=error_msg)
        elif processed_standings:
            logger.debug(f"Custom processed standings data (first 2 teams) for {effective_season}, type {season_type}, league {league_id}: {json.dumps(processed_standings[:2], indent=2)}")

        for team_data in processed_standings:
            gb_value = team_data.get('ConferenceGamesBack')
            if isinstance(gb_value, (int, float)):
                team_data['GB'] = gb_value
            elif isinstance(gb_value, str) and gb_value.strip() == '-':
                 team_data['GB'] = 0.0
            elif gb_value is None:
                 team_data['GB'] = None
            else:
                try:
                    team_data['GB'] = float(gb_value)
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert ConferenceGamesBack '{gb_value}' to float for team {team_data.get('TeamID')}. Setting GB to null.")
                    team_data['GB'] = None
            
            try:
                win_pct_val = team_data.get('WinPCT')
                team_data['WinPct'] = float(win_pct_val) if win_pct_val is not None else 0.0
            except (ValueError, TypeError):
                logger.warning(f"Could not convert WinPCT '{team_data.get('WinPCT')}' to float for team {team_data.get('TeamID')}. Defaulting to 0.0.")
                team_data['WinPct'] = 0.0
            
            team_data['STRK'] = team_data.get('strCurrentStreak', '')
        
        processed_standings.sort(key=lambda x: (x.get("Conference", ""), x.get("PlayoffRank", 99)))
        logger.info(f"Successfully fetched and processed standings for season {effective_season}, type {season_type}, league {league_id}.")
        return format_response({"standings": processed_standings, "league_id_processed": league_id}) # Include league_id in response for clarity

    except Exception as e:
        logger.error(f"Unexpected error in fetch_league_standings_logic for season {effective_season}, type {season_type}, league {league_id}: {str(e)}", exc_info=True)
        error_msg = Errors.LEAGUE_STANDINGS_UNEXPECTED.format(season=effective_season, season_type=season_type, error=str(e)) # league_id not in this error msg
        return format_response(error=error_msg)
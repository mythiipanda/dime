import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from nba_api.stats.endpoints import LeagueSeasonMatchups, MatchupsRollup
from nba_api.stats.library.parameters import SeasonTypeAllStar
from backend.config import CURRENT_SEASON, DEFAULT_TIMEOUT, Errors
from backend.api_tools.utils import format_response, _process_dataframe

logger = logging.getLogger(__name__)

# Cache structure: (result_json, timestamp)
_matchups_cache: Dict[str, Tuple[str, datetime]] = {}
# Cache for 1 hour for historical data
CACHE_TTL = 3600

def _validate_matchup_params(player_id: str, season: str) -> Optional[str]:
    """Validate matchup parameters."""
    if not player_id:
        return format_response(error=Errors.MISSING_PLAYER_ID)
    if not season:
        return format_response(error=Errors.MISSING_SEASON)
    if len(player_id) > 10:  # NBA player IDs are typically shorter
        return format_response(error=Errors.INVALID_PLAYER_ID.format(id=player_id))
    return None

def _get_cache_key(def_player_id: str, off_player_id: Optional[str], season: str, season_type: str) -> str:
    """Generate cache key for matchup data."""
    return f"{def_player_id}_{off_player_id or 'all'}_{season}_{season_type}"

def fetch_league_season_matchups_logic(
    def_player_id: str,
    off_player_id: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    bypass_cache: bool = False
) -> str:
    """
    Fetches season matchups between two players.
    
    Args:
        def_player_id (str): Defensive player ID
        off_player_id (str): Offensive player ID
        season (str): Season in YYYY-YY format
        season_type (str): Type of season (regular, playoffs)
        bypass_cache (bool): Whether to bypass cache for the request
        
    Returns:
        str: JSON string with matchups data
    """
    logger.info(f"Fetching season matchups between Def {def_player_id} and Off {off_player_id} for {season}")
    
    # Validate parameters
    validation_error = _validate_matchup_params(def_player_id, season)
    if validation_error:
        return validation_error
    
    # Check cache for historical seasons
    cache_key = _get_cache_key(def_player_id, off_player_id, season, season_type)
    if not bypass_cache and season != CURRENT_SEASON and cache_key in _matchups_cache:
        cached_data, cache_time = _matchups_cache[cache_key]
        if datetime.now() - cache_time < timedelta(seconds=CACHE_TTL):
            logger.info("Returning cached matchup data")
            return cached_data
    
    try:
        endpoint = LeagueSeasonMatchups(
            def_player_id_nullable=def_player_id,
            off_player_id_nullable=off_player_id,
            season=season,
            season_type_playoffs=season_type,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Select essential columns for matchups
        essential_cols = [
            'GAME_ID', 'MATCHUP', 'OFF_PLAYER_NAME', 'DEF_PLAYER_NAME',
            'PARTIAL_POSS', 'PLAYER_PTS', 'PLAYER_FGM', 'PLAYER_FGA', 'PLAYER_FG3M',
            'PLAYER_FG3A', 'MATCHUP_MIN', 'MATCHUP_FGM', 'MATCHUP_FGA', 'MATCHUP_FG3M',
            'MATCHUP_FG3A', 'MATCHUP_TOV', 'HELP_BLK', 'HELP_FGM', 'HELP_FGA'
        ]
        
        df = endpoint.season_matchups.get_data_frame()
        matchups = _process_dataframe(df.loc[:, [col for col in essential_cols if col in df.columns]], single_row=False)
        
        result = {
            "def_player_id": def_player_id,
            "off_player_id": off_player_id,
            "matchups": matchups or []
        }
        
        json_result = json.dumps(result)
        
        # Cache result for historical seasons
        if season != CURRENT_SEASON:
            _matchups_cache[cache_key] = (json_result, datetime.now())
            
        return json_result
        
    except Exception as e:
        logger.error(f"Error fetching season matchups: {e}", exc_info=True)
        return format_response(error=Errors.MATCHUPS_API.format(error=str(e)))

def fetch_matchups_rollup_logic(
    def_player_id: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    bypass_cache: bool = False
) -> str:
    """
    Fetches matchup rollup for a defensive player across opponents.
    
    Args:
        def_player_id (str): Defensive player ID
        season (str): Season in YYYY-YY format
        season_type (str): Type of season (regular, playoffs)
        bypass_cache (bool): Whether to bypass cache for the request
        
    Returns:
        str: JSON string with rollup data
    """
    logger.info(f"Fetching matchup rollup for Def {def_player_id} in {season}")
    
    # Validate parameters
    validation_error = _validate_matchup_params(def_player_id, season)
    if validation_error:
        return validation_error
    
    # Check cache for historical seasons
    cache_key = _get_cache_key(def_player_id, None, season, season_type)
    if not bypass_cache and season != CURRENT_SEASON and cache_key in _matchups_cache:
        cached_data, cache_time = _matchups_cache[cache_key]
        if datetime.now() - cache_time < timedelta(seconds=CACHE_TTL):
            logger.info("Returning cached rollup data")
            return cached_data
    
    try:
        endpoint = MatchupsRollup(
            def_player_id_nullable=def_player_id,
            season=season,
            season_type_playoffs=season_type,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Select essential columns for rollup
        essential_cols = [
            'OFF_PLAYER_ID', 'OFF_PLAYER_NAME', 'GP', 'MATCHUP_MIN',
            'PARTIAL_POSS', 'PLAYER_PTS', 'PLAYER_FGM', 'PLAYER_FGA',
            'PLAYER_FG3M', 'PLAYER_FG3A', 'MATCHUP_FGM', 'MATCHUP_FGA',
            'MATCHUP_FG3M', 'MATCHUP_FG3A', 'MATCHUP_TOV', 'MATCHUP_HELP_BLK'
        ]
        
        df = endpoint.matchups_rollup.get_data_frame()
        rollup = _process_dataframe(df.loc[:, [col for col in essential_cols if col in df.columns]], single_row=False)
        
        result = {
            "def_player_id": def_player_id,
            "rollup": rollup or []
        }
        
        json_result = json.dumps(result)
        
        # Cache result for historical seasons
        if season != CURRENT_SEASON:
            _matchups_cache[cache_key] = (json_result, datetime.now())
            
        return json_result
        
    except Exception as e:
        logger.error(f"Error fetching matchups rollup: {e}", exc_info=True)
        return format_response(error=Errors.MATCHUPS_ROLLUP_API.format(error=str(e)))

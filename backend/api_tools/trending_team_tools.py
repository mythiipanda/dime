import logging
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
from nba_api.stats.library.parameters import SeasonTypeAllStar
from backend.api_tools.league_tools import fetch_league_standings_logic
from backend.config import CURRENT_SEASON, Errors
from backend.api_tools.utils import format_response

logger = logging.getLogger(__name__)

# Cache structure: (result_json, timestamp)
_standings_cache: Dict[str, Tuple[str, datetime]] = {}
# Cache TTL in seconds (15 minutes, since standings could change after games)
CACHE_TTL = 900

def _validate_top_teams_params(season: str, top_n: int) -> Optional[str]:
    """Validate parameters for fetching top teams."""
    if not season:
        return format_response(error=Errors.MISSING_SEASON)
    if top_n < 1:
        return format_response(error=Errors.INVALID_TOP_N.format(value=top_n))
    # Validate season format (YYYY-YY)
    if not re.match(r'^\d{4}-\d{2}$', season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    return None

def _get_cache_key(season: str, season_type: str, top_n: int) -> str:
    """Generate cache key for top teams data."""
    return f"{season}_{season_type}_{top_n}"

def fetch_top_teams_logic(
    season: str = "",
    season_type: str = SeasonTypeAllStar.regular,
    top_n: int = 5,
    bypass_cache: bool = False
) -> str:
    """
    Fetch top performing teams by win percentage for a given season.
    
    Args:
        season (str): Season in YYYY-YY format
        season_type (str): Type of season (regular, playoffs)
        top_n (int): Number of top teams to return
        bypass_cache (bool): Whether to bypass cache for the request
        
    Returns:
        str: JSON string with top teams data
    """
    # Use default season if not provided
    if not season:
        season = CURRENT_SEASON
    
    # Validate parameters
    validation_error = _validate_top_teams_params(season, top_n)
    if validation_error:
        return validation_error
    
    # Check cache
    cache_key = _get_cache_key(season, season_type, top_n)
    if not bypass_cache and cache_key in _standings_cache:
        cached_data, cache_time = _standings_cache[cache_key]
        if datetime.now() - cache_time < timedelta(seconds=CACHE_TTL):
            logger.info("Returning cached top teams data")
            return cached_data
    
    try:
        standings_json = fetch_league_standings_logic(season, season_type)
        data = json.loads(standings_json)
        standings = data.get("standings", [])
        
        # Sort by WinPct descending, handle missing or invalid values
        try:
            standings_sorted = sorted(
                standings,
                key=lambda x: float(x.get("WinPct", 0) or 0),  # Handle None/empty values
                reverse=True
            )
        except Exception as e:
            logger.warning(f"Error sorting standings by WinPct: {e}")
            standings_sorted = standings
        
        # Select only essential fields for top teams
        essential_fields = ["TeamCity", "TeamName", "TeamID", "Conference", "WinPct", "W", "L", "ConfRank"]
        top = []
        for team in standings_sorted[:top_n]:
            top_team = {field: team.get(field) for field in essential_fields if field in team}
            top.append(top_team)
        
        result = {
            "top_teams": top
        }
        
        json_result = json.dumps(result)
        
        # Update cache
        _standings_cache[cache_key] = (json_result, datetime.now())
        
        return json_result
        
    except Exception as e:
        logger.error(f"Error fetching top teams: {e}", exc_info=True)
        return format_response(error=Errors.LEAGUE_STANDINGS_API.format(season=season, error=str(e)))

import json
import logging
import time
import re # Import regex module
from typing import Optional, Dict, Any
from nba_api.stats.endpoints.synergyplaytypes import SynergyPlayTypes
# Removed unused import: from nba_api.stats.library.http import NBAStatsHTTP
from nba_api.stats.library.parameters import (
    LeagueID,
    PerModeSimple,
    PlayerOrTeamAbbreviation,
    SeasonTypeAllStar,
    Season,
    PlayTypeNullable,
    TypeGroupingNullable
)
from backend.config import CURRENT_SEASON, DEFAULT_TIMEOUT
from backend.api_tools.utils import format_response
from backend.api_tools.errors import Errors # Import the Errors class

logger = logging.getLogger(__name__)

# Cache dictionary and TTL (1 hour)
_synergy_cache: Dict[tuple, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 3600

def fetch_synergy_play_types_logic(
    league_id: str = LeagueID.nba,
    per_mode: str = PerModeSimple.default,
    player_or_team: str = PlayerOrTeamAbbreviation.default,
    season_type: str = SeasonTypeAllStar.regular,
    season: str = CURRENT_SEASON,
    play_type: Optional[str] = None,
    type_grouping: Optional[str] = None,
    bypass_cache: bool = False
) -> str:
    """
    Fetch synergy play types stats for team or player, with caching.
    """
    logger.info(
        f"Fetching Synergy play types: league_id={league_id}, per_mode={per_mode}, "
        f"player_or_team={player_or_team}, season_type={season_type}, season={season}, "
        f"play_type={play_type}, type_grouping={type_grouping}, bypass_cache={bypass_cache}"
    )

    # --- Input Validation ---
    # Validate season format (YYYY-YY or YYYY)
    if not re.match(r'^(\d{4}-\d{2}|\d{4})$', season):
        logger.error(f"Invalid season format: {season}. Expected YYYY-YY or YYYY.")
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season)) # Access via Errors class

    # Validate play_type if provided
    valid_play_types = {"Cut", "Handoff", "Isolation", "Misc", "OffScreen", "Postup", "PRBallHandler", "PRRollman", "OffRebound", "Spotup", "Transition"}
    if play_type is not None and play_type not in valid_play_types:
        logger.error(f"Invalid play type: {play_type}")
        return format_response(error=Errors.INVALID_PLAY_TYPE.format(play_type=play_type)) # Access via Errors class

    # Validate type_grouping if provided
    valid_type_groupings = {"offensive", "defensive"}
    if type_grouping is not None and type_grouping not in valid_type_groupings:
        logger.error(f"Invalid type grouping: {type_grouping}")
        return format_response(error=Errors.INVALID_TYPE_GROUPING.format(type_grouping=type_grouping)) # Access via Errors class
    # --- End Input Validation ---


    # --- Cache Check ---
    cache_key = (league_id, per_mode, player_or_team, season_type, season, play_type, type_grouping)
    current_time = time.time()

    if not bypass_cache and cache_key in _synergy_cache:
        cached_entry = _synergy_cache[cache_key]
        if current_time - cached_entry['timestamp'] < CACHE_TTL_SECONDS:
            logger.info(f"Returning cached Synergy data for key: {cache_key}")
            return cached_entry['data']
        else:
            logger.info(f"Cache expired for key: {cache_key}")
            del _synergy_cache[cache_key] # Remove expired entry
    # --- End Cache Check ---

    try:
        logger.info(f"Fetching fresh Synergy data for key: {cache_key}")
        synergy_stats = SynergyPlayTypes(
            league_id=league_id,
            per_mode_simple=per_mode,
            player_or_team_abbreviation=player_or_team,
            season_type_all_star=season_type,
            season=season,
            play_type_nullable=play_type,
            type_grouping_nullable=type_grouping,
            timeout=DEFAULT_TIMEOUT
        )
        response_dict = synergy_stats.get_dict()

        # Extract the relevant data set (assuming 'SynergyPlayType' is the target)
        # nba_api often returns data in 'resultSets', a list of dicts.
        # Each dict has 'name', 'headers', 'rowSet'.
        result_set = None
        if 'resultSets' in response_dict and isinstance(response_dict['resultSets'], list):
            for rs in response_dict['resultSets']:
                if rs.get('name') == 'SynergyPlayType':
                    result_set = rs
                    break
            # Fallback if named set not found, assume first set if only one exists
            if not result_set and len(response_dict['resultSets']) == 1:
                 result_set = response_dict['resultSets'][0]

        if not result_set or 'headers' not in result_set or 'rowSet' not in result_set:
             logger.warning("Could not find expected 'SynergyPlayType' data structure in response.")
             # Return the raw response if structure is unexpected
             return json.dumps(response_dict)

        headers = result_set['headers']
        rows = result_set['rowSet']

        # Define essential columns
        essential_columns = [
            'PLAY_TYPE', 'TYPE_GROUPING', 'PERCENTILE', 'GP', 'POSS_PCT',
            'PPP', 'FG_PCT', 'EFG_PCT', 'SCORE_POSS_PCT', 'TOV_POSS_PCT',
            'POSS', 'PTS'
        ]
        # Add player or team specific columns
        if player_or_team == PlayerOrTeamAbbreviation.player:
            essential_columns.extend(['PLAYER_ID', 'PLAYER_NAME', 'TEAM_ID', 'TEAM_ABBREVIATION']) # Player also has team info
        else: # Team
            essential_columns.extend(['TEAM_ID', 'TEAM_ABBREVIATION', 'TEAM_NAME'])


        # Filter data
        filtered_data = []
        # Ensure headers are available before creating col_indices
        available_headers = set(headers)
        valid_essential_columns = [col for col in essential_columns if col in available_headers]

        if not valid_essential_columns:
             logger.warning("None of the essential columns found in headers.")
             return json.dumps(response_dict) # Return raw if no essential columns match

        col_indices = {col: headers.index(col) for col in valid_essential_columns}

        if not col_indices:
             logger.warning("None of the essential columns found in headers.")
             return json.dumps(response_dict) # Return raw if no essential columns match

        for row in rows:
            filtered_row = {col: row[idx] for col, idx in col_indices.items()}
            filtered_data.append(filtered_row)

        # Return filtered data as JSON string
        result_json = json.dumps(filtered_data)

        # Store fresh data in cache
        _synergy_cache[cache_key] = {'data': result_json, 'timestamp': current_time}
        logger.info(f"Cached fresh Synergy data for key: {cache_key}")

        return result_json

    except Exception as e:
        logger.error("Synergy API call failed during processing: %s", e, exc_info=True)
        return format_response(error=str(e))

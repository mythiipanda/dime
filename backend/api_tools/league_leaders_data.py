import logging
from functools import lru_cache
import requests

from nba_api.stats.endpoints import leagueleaders
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar, PerMode48, Scope, StatCategoryAbbreviation
from backend.api_tools.utils import _process_dataframe, format_response
from backend.utils.validation import _validate_season_format
from backend.config import settings
from backend.core.errors import Errors

logger = logging.getLogger(__name__)

# Module-level constants for validation sets
_VALID_STAT_CATEGORIES_LEADERS = {getattr(StatCategoryAbbreviation, attr) for attr in dir(StatCategoryAbbreviation) if not attr.startswith('_')}
_VALID_SEASON_TYPES_LEADERS = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
_VALID_PER_MODES_LEADERS = {getattr(PerMode48, attr) for attr in dir(PerMode48) if not attr.startswith('_') and isinstance(getattr(PerMode48, attr), str)}
_VALID_LEAGUE_IDS_LEADERS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}
_VALID_SCOPES_LEADERS = {getattr(Scope, attr) for attr in dir(Scope) if not attr.startswith('_') and isinstance(getattr(Scope, attr), str)}

@lru_cache(maxsize=128)
def fetch_league_leaders_logic(
    season: str,
    stat_category: str = StatCategoryAbbreviation.pts,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerMode48.per_game,
    league_id: str = LeagueID.nba,
    scope: str = Scope.s,
    top_n: int = 10
) -> str:
    """
    Fetches league leaders for a specific statistical category, season, and other criteria using nba_api's LeagueLeaders endpoint.

    Args:
        season (str): NBA season in 'YYYY-YY' format (e.g., '2022-23').
        stat_category (str): Statistical category abbreviation (e.g., 'PTS', 'AST').
        season_type (str): Season type (e.g., 'Regular Season', 'Playoffs').
        per_mode (str): Per mode (e.g., 'PerGame', 'Totals', 'Per48').
        league_id (str): League ID (default: NBA).
        scope (str): Scope of the leaders (e.g., 'S' for season, 'RS' for regular season, 'Rookies').
        top_n (int): Number of top leaders to return (default: 10).

    Returns:
        str: JSON-formatted string containing a list of league leaders or an error message.

    Notes:
        - Returns an error for invalid parameters or API errors.
        - Returns an empty list if no leaders are found for the criteria.
        - Each leader includes player, rank, team, games played, minutes, and the requested stat.
    """
    logger.info(f"Executing fetch_league_leaders_logic for season: {season}, category: {stat_category}, type: {season_type}, per_mode: {per_mode}, scope: {scope}, top_n: {top_n}")

    if not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    if not isinstance(top_n, int) or top_n <= 0:
        logger.warning(f"Invalid top_n value '{top_n}'. Must be a positive integer. Defaulting to 10.")
        top_n = 10
    
    if stat_category not in _VALID_STAT_CATEGORIES_LEADERS:
        return format_response(error=Errors.INVALID_STAT_CATEGORY.format(value=stat_category, options=", ".join(_VALID_STAT_CATEGORIES_LEADERS)))
    if season_type not in _VALID_SEASON_TYPES_LEADERS:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(_VALID_SEASON_TYPES_LEADERS)))
    if per_mode not in _VALID_PER_MODES_LEADERS:
        return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(_VALID_PER_MODES_LEADERS)))
    if league_id not in _VALID_LEAGUE_IDS_LEADERS:
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(_VALID_LEAGUE_IDS_LEADERS)))
    if scope not in _VALID_SCOPES_LEADERS:
        return format_response(error=Errors.INVALID_SCOPE.format(value=scope, options=", ".join(_VALID_SCOPES_LEADERS)))

    stats_url = "https://stats.nba.com/stats/leagueleaders"
    http_params = {
        "LeagueID": league_id, "PerMode": per_mode, "Scope": scope,
        "Season": season, "SeasonType": season_type, "StatCategory": stat_category,
    }
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://stats.nba.com/', 'Accept': 'application/json'}
    raw_response_status_for_log = None

    try:
        logger.debug(f"Calling leagueleaders.LeagueLeaders with params: {http_params}")
        leaders_endpoint = leagueleaders.LeagueLeaders(
            league_id=league_id, per_mode48=per_mode, scope=scope, season=season,
            season_type_all_star=season_type, stat_category_abbreviation=stat_category,
            timeout=settings.DEFAULT_TIMEOUT_SECONDS
        )
        leaders_df = leaders_endpoint.league_leaders.get_data_frame()
        logger.debug(f"nba_api leagueleaders call successful for {stat_category} ({season})")

    except KeyError as ke:
        if 'resultSet' in str(ke):
            logger.error(f"KeyError 'resultSet' using nba_api for {stat_category} ({season}). NBA API response likely malformed.", exc_info=True)
            try:
                response = requests.get(stats_url, headers=headers, params=http_params, timeout=5)
                raw_response_status_for_log = response.status_code
                logger.debug(f"Direct HTTP debug request status: {raw_response_status_for_log}, Response (first 500): {response.text[:500]}")
            except Exception as direct_req_err:
                logger.error(f"Direct HTTP debug request failed: {direct_req_err}")
            error_msg = Errors.LEAGUE_LEADERS_API_KEY_ERROR.format(stat=stat_category, season=season) + f" (Direct status: {raw_response_status_for_log or 'N/A'})"
            return format_response(error=error_msg)
        else:
            raise ke
    except Exception as api_error:
        logger.error(f"nba_api leagueleaders failed for {stat_category} ({season}): {api_error}", exc_info=True)
        error_msg = Errors.LEAGUE_LEADERS_API.format(stat_category=stat_category, season=season, error=str(api_error)) # Changed stat to stat_category
        return format_response(error=error_msg)

    if leaders_df.empty:
        logger.warning(f"No league leaders data found via nba_api for {stat_category} ({season}).")
        return format_response({"leaders": []})

    expected_cols = ['PLAYER_ID', 'RANK', 'PLAYER', 'TEAM_ID', 'TEAM', 'GP', 'MIN']
    if stat_category not in leaders_df.columns:
        logger.error(f"Stat category '{stat_category}' not found in league leaders DataFrame columns: {list(leaders_df.columns)}")
        return format_response(error=Errors.LEAGUE_LEADERS_PROCESSING.format(stat_category=stat_category, season=season) + f" - Stat column '{stat_category}' missing.") # Corrected placeholder

    available_cols = [col for col in expected_cols if col in leaders_df.columns]
    if stat_category not in available_cols:
        available_cols.append(stat_category)
    
    final_cols = []
    for col in available_cols:
        if col not in final_cols:
            final_cols.append(col)

    leaders_list = _process_dataframe(leaders_df.loc[:, final_cols], single_row=False)
    if leaders_list is None:
        logger.error(f"DataFrame processing failed for league leaders {stat_category} ({season}).")
        error_msg = Errors.LEAGUE_LEADERS_PROCESSING.format(stat_category=stat_category, season=season) # Corrected placeholder key
        return format_response(error=error_msg)


    if top_n > 0:
        leaders_list = leaders_list[:top_n]

    logger.info(f"fetch_league_leaders_logic completed for {stat_category} ({season}) using nba_api, found {len(leaders_list)} leaders.")
    return format_response({"leaders": leaders_list})
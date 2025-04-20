import logging
import json
from typing import Optional, List
from agno.tools import tool
from nba_api.stats.endpoints import (
    leaguedashplayerstats, playerestimatedmetrics, teamestimatedmetrics, commonplayerinfo, 
    playerprofilev2, teaminfocommon, commonteamroster, playercareerstats, teamdetails
)
from backend.utils.data_processing import (
    process_player_stats, process_player_metrics, process_team_metrics, 
    process_player_info, process_team_info, process_roster_data, process_player_career_stats,
    process_team_details
)
from backend.utils.cache import cache_data, get_cached_data
import datetime

# Import only the necessary constants for default values, use standard types in hints
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, PerMode36, LeagueID, PerMode48, Scope, MeasureTypeDetailedDefense, RunType,
    PerModeSimple, PlayerOrTeamAbbreviation
)
from backend.config import CURRENT_SEASON
from backend.api_tools.utils import format_response


# Import logic functions from the specific backend.api_tools modules
from backend.api_tools.player_tools import (
    fetch_player_info_logic,
    fetch_player_gamelog_logic,
    fetch_player_career_stats_logic,
    fetch_player_awards_logic,
    fetch_player_shotchart_logic,
    fetch_player_defense_logic,
    fetch_player_hustle_stats_logic,
    fetch_player_profile_logic,
    fetch_player_stats_logic
)
from backend.api_tools.team_tools import (
    fetch_team_info_and_roster_logic,
    fetch_team_lineups_logic,
    fetch_team_stats_logic, # Now importing the logic function
)
from backend.api_tools.game_tools import (
    fetch_boxscore_traditional_logic,
    fetch_playbyplay_logic,
    fetch_league_games_logic, # Used by find_games
    fetch_shotchart_logic,
    fetch_boxscore_advanced_logic,
    fetch_boxscore_four_factors_logic,
    fetch_boxscore_usage_logic,
    fetch_boxscore_defensive_logic,
    fetch_win_probability_logic
)
from backend.api_tools.league_tools import (
    fetch_league_standings_logic,
    fetch_scoreboard_logic,
    fetch_draft_history_logic,
    fetch_league_leaders_logic
)
from backend.api_tools.player_tracking import (
    fetch_player_clutch_stats_logic,
    fetch_player_passing_stats_logic,
    fetch_player_shots_tracking_logic,
    fetch_player_rebounding_stats_logic
)
from backend.api_tools.team_tracking import (
    fetch_team_passing_stats_logic,
    fetch_team_shooting_stats_logic,
    fetch_team_rebounding_stats_logic
)
from backend.api_tools.scoreboard.scoreboard_tools import fetch_scoreboard_data_logic
# New logic imports for live odds and player insights
from backend.api_tools.odds_tools import fetch_odds_data_logic
from backend.api_tools.analyze import analyze_player_stats_logic
from backend.api_tools.trending_tools import fetch_top_performers_logic  # Trending tools
from backend.api_tools.trending_team_tools import fetch_top_teams_logic  # Trending team tools
from backend.api_tools.matchup_tools import fetch_league_season_matchups_logic, fetch_matchups_rollup_logic
from backend.api_tools.synergy_tools import fetch_synergy_play_types_logic

logger = logging.getLogger(__name__)

# Helper function to generate cache key
def generate_cache_key(func_name: str, *args, **kwargs) -> str:
    key_parts = [func_name]
    key_parts.extend(map(str, args))
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return "_".join(key_parts)

# --- Agno Tool Functions (Wrappers for Logic) ---

# Player Tools
@tool
def get_player_info(player_name: str) -> str:
    """
    Fetches basic player information and headline stats. Returns JSON string.
    Args: player_name (str): Full name of the player.
    Returns: str: JSON string containing player info/stats or {'error': ...}.
    """
    cache_key = generate_cache_key("get_player_info", player_name)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_player_info' called for '{player_name}'")
    result = fetch_player_info_logic(player_name)
    cache_data(cache_key, result) # Add result to cache
    return result

@tool
def get_player_gamelog(player_name: str, season: str, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches the game log for a player and season. Returns JSON string.
    Args:
        player_name (str): Full name of the player.
        season (str): Season identifier (e.g., "2023-24").
        season_type (str): 'Regular Season', 'Playoffs', etc. Defaults to Regular Season.
    Returns: str: JSON string containing game log data or {'error': ...}.
    """
    cache_key = generate_cache_key("get_player_gamelog", player_name, season, season_type=season_type)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_player_gamelog' called for '{player_name}', season '{season}', type '{season_type}'")
    valid_season_types = [st for st in dir(SeasonTypeAllStar) if not st.startswith('_') and isinstance(getattr(SeasonTypeAllStar, st), str)]
    if season_type not in valid_season_types:
        logger.warning(f"Invalid season_type '{season_type}' in tool wrapper. Logic function should handle default.")

    result = fetch_player_gamelog_logic(player_name, season, season_type)
    cache_data(cache_key, result)
    return result

@tool
def get_player_career_stats(player_name: str, per_mode36: str = PerMode36.per_game) -> str:
    """
    Fetches player career statistics (Regular Season). Returns JSON string.
    Args:
        player_name (str): Full name of the player.
        per_mode36 (str): Stat mode ('PerGame', 'Totals', 'Per36', etc.). Defaults to 'PerGame'.
    Returns: str: JSON string containing career stats data or {'error': ...}.
    """
    cache_key = generate_cache_key("get_player_career_stats", player_name, per_mode36=per_mode36)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_player_career_stats' called for '{player_name}', per_mode36 '{per_mode36}'")
    valid_per_modes = [getattr(PerMode36, attr) for attr in dir(PerMode36) if not attr.startswith('_') and isinstance(getattr(PerMode36, attr), str)]
    if per_mode36 not in valid_per_modes:
         logger.warning(f"Invalid per_mode36 '{per_mode36}' in tool wrapper. Logic function should handle default.")

    result = fetch_player_career_stats_logic(player_name, per_mode36)
    cache_data(cache_key, result)
    return result

@tool
def get_player_awards(player_name: str) -> str:
    """
    Fetches the awards won by a specific player. Returns JSON string.
    Args: player_name (str): Full name of the player.
    Returns: str: JSON string containing a list of awards or {'error': ...}.
    """
    cache_key = generate_cache_key("get_player_awards", player_name)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_player_awards' called for '{player_name}'")
    result = fetch_player_awards_logic(player_name)
    cache_data(cache_key, result)
    return result

@tool
def get_player_shotchart(
    player_name: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    """
    Fetches detailed shot chart data for a player, including shot locations and shooting percentages.
    Args:
        player_name (str): Full name of the player
        season (str): Season identifier (e.g., "2023-24"). Defaults to current season.
        season_type (str): "Regular Season" or "Playoffs". Defaults to Regular Season.
    Returns:
        str: JSON string containing:
            - Shot locations (x, y coordinates)
            - Shot outcomes (made/missed)
            - Shot types
            - Shooting percentages by zone
            - League average comparisons
    """
    cache_key = generate_cache_key("get_player_shotchart", player_name, season=season, season_type=season_type)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool get_player_shotchart called for {player_name}, season {season}")
    result = fetch_player_shotchart_logic(
        player_name=player_name,
        season=season,
        season_type=season_type
    )
    cache_data(cache_key, result)
    return result

@tool
def get_player_defense_stats(
    player_name: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> str:
    """
    Fetches detailed defensive statistics for a player.
    Args:
        player_name (str): Full name of the player
        season (str): Season identifier (e.g., "2023-24"). Defaults to current season.
        season_type (str): "Regular Season" or "Playoffs". Defaults to Regular Season.
        per_mode (str): Statistics reporting mode ("PerGame", "Totals", etc.)
    Returns:
        str: JSON string containing:
            - Defensive matchup data
            - Points allowed per possession
            - Defensive field goal percentage allowed
            - Blocks and steals
            - Defensive impact metrics
    """
    cache_key = generate_cache_key("get_player_defense_stats", player_name, season=season, season_type=season_type, per_mode=per_mode)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool get_player_defense_stats called for {player_name}, season {season}")
    result = fetch_player_defense_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    cache_data(cache_key, result)
    return result

# Player Tracking Tools
@tool
def get_player_clutch_stats(
    player_name: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    """
    Fetches player stats in clutch situations. Returns JSON string.
    Args:
        player_name (str): Full name of the player.
        season (str): Season identifier (e.g., '2023-24').
        season_type (str): 'Regular Season', 'Playoffs', etc. Defaults to Regular Season.
    Returns: str: JSON string containing clutch stats or {'error': ...}.
    """
    cache_key = generate_cache_key("get_player_clutch_stats", player_name, season, season_type=season_type)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_player_clutch_stats' called for '{player_name}', season '{season}', type '{season_type}'")
    result_dict = fetch_player_clutch_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type
    )
    result_str = json.dumps(result_dict, default=str)
    cache_data(cache_key, result_str)
    return result_str

@tool
def get_player_passing_stats(
    player_name: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    """
    Fetches player passing tracking stats. Returns JSON string.
    Args:
        player_name (str): Full name of the player
        season (str): Season identifier (e.g., "2023-24")
        season_type (str): 'Regular Season', 'Playoffs', etc. Defaults to Regular Season
    Returns: str: JSON string containing player passing statistics
    """
    cache_key = generate_cache_key("get_player_passing_stats", player_name, season, season_type=season_type)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool get_player_passing_stats called for {player_name}, season {season}")
    result = fetch_player_passing_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type
    )
    cache_data(cache_key, result)
    return result

@tool
def get_player_rebounding_stats(
    player_name: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    """
    Fetches player rebounding tracking stats. Returns JSON string.
    Args:
        player_name (str): Full name of the player
        season (str): Season identifier (e.g., "2023-24")
        season_type (str): 'Regular Season', 'Playoffs', etc. Defaults to Regular Season
    Returns: str: JSON string containing player rebounding statistics
    """
    cache_key = generate_cache_key("get_player_rebounding_stats", player_name, season, season_type=season_type)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool get_player_rebounding_stats called for {player_name}, season {season}")
    result = fetch_player_rebounding_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type
    )
    cache_data(cache_key, result)
    return result

@tool
def get_player_shots_tracking(player_id: str) -> str:
    """
    Fetches player shot tracking stats using the player's ID. Returns JSON string.
    Args:
        player_id (str): The NBA player ID.
    Returns: str: JSON string containing shot tracking stats or {'error': ...}.
    """
    # Note: This assumes shot tracking for a player_id is relatively stable, maybe refresh seasonally?
    cache_key = generate_cache_key("get_player_shots_tracking", player_id)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_player_shots_tracking' called for player_id '{player_id}'")
    result = fetch_player_shots_tracking_logic(player_id=player_id)
    cache_data(cache_key, result)
    return result


# Team Tools
@tool
def get_team_info_and_roster(team_identifier: str, season: str = CURRENT_SEASON) -> str:
    """
    Fetches team information, ranks, roster, and coaches. Returns JSON string.
    Args:
        team_identifier (str): Team name, abbreviation, or ID (e.g., "LAL").
        season (str): Season identifier (e.g., "2023-24"). Defaults to current.
    Returns: str: JSON string containing team data or {'error': ...}.
    """
    cache_key = generate_cache_key("get_team_info_and_roster", team_identifier, season=season)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_team_info_and_roster' called for '{team_identifier}', season '{season}'")
    result = fetch_team_info_and_roster_logic(team_identifier, season)
    cache_data(cache_key, result)
    return result

@tool
def get_team_stats(
    team_identifier: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    measure_type: str = MeasureTypeDetailedDefense.base, # Check if this is the right default category
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches comprehensive team statistics using the underlying logic function.

    Args:
        team_identifier (str): Team name, abbreviation, or ID.
        season (str): NBA season in format 'YYYY-YY'. Defaults to current.
        season_type (str): Season type (Regular Season, Playoffs). Defaults to Regular Season.
        per_mode (str): Per mode for stats (PerGame, Totals). Defaults to PerGame.
        measure_type (str): Measure type for dashboard stats (Base, Advanced). Defaults to Base.
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0.
        date_from (str, optional): Start date filter (YYYY-MM-DD). Defaults to None.
        date_to (str, optional): End date filter (YYYY-MM-DD). Defaults to None.
        league_id (str): League ID (NBA, WNBA, G-League). Defaults to NBA.

    Returns:
        str: JSON string containing team statistics or error message.
    """
    cache_key = generate_cache_key("get_team_stats", team_identifier, season=season, season_type=season_type, per_mode=per_mode, measure_type=measure_type, opponent_team_id=opponent_team_id, date_from=date_from, date_to=date_to, league_id=league_id)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_team_stats' called for '{team_identifier}', season '{season}'")
    result = fetch_team_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        opponent_team_id=opponent_team_id,
        date_from=date_from,
        date_to=date_to,
        league_id=league_id
    )
    cache_data(cache_key, result)
    return result

# Team Tracking Tools
@tool
def get_team_passing_stats(
    team_identifier: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> str:
    """
    Fetches team passing tracking stats (passes between players). Returns JSON string.
    Args:
        team_identifier: Name, abbreviation or ID of the team (e.g., "Lakers" or "LAL")
        season: Season to get data for, in format "YYYY-YY" (e.g., "2022-23")
        season_type: "Regular Season", "Playoffs", etc. Defaults to Regular Season.
        per_mode: Mode of stats, like "PerGame" or "Totals". Check if logic uses this.
    Returns:
        String JSON with passing statistics for the team
    """
    cache_key = generate_cache_key("get_team_passing_stats", team_identifier, season, season_type=season_type, per_mode=per_mode)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool get_team_passing_stats called for {team_identifier}, season {season}")
    result = fetch_team_passing_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    cache_data(cache_key, result)
    return result

@tool
def get_team_shooting_stats(
    team_identifier: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> str:
    """
    Fetches team shooting tracking stats. Returns JSON string.
    Args:
        team_identifier: Name, abbreviation or ID of the team (e.g., "Lakers" or "LAL")
        season: Season to get data for, in format "YYYY-YY" (e.g., "2022-23")
        season_type: "Regular Season", "Playoffs", etc. Defaults to Regular Season.
        per_mode: Mode of stats, like "PerGame" or "Totals". Check if logic uses this.
    Returns:
        String JSON with shooting statistics for the team
    """
    cache_key = generate_cache_key("get_team_shooting_stats", team_identifier, season, season_type=season_type, per_mode=per_mode)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool get_team_shooting_stats called for {team_identifier}, season {season}")
    result = fetch_team_shooting_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    cache_data(cache_key, result)
    return result

@tool
def get_team_lineups(
    team_id: Optional[int] = None,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    month: int = 0,
    date_from: str = None,
    date_to: str = None,
    opponent_team_id: int = 0,
    vs_conference: str = None,
    vs_division: str = None,
    game_segment: str = None,
    period: int = 0,
    last_n_games: int = 0
) -> str:
    """
    Fetches detailed lineup statistics with various filtering options.
    Args:
        team_id: Optional NBA team ID. If None, returns all team lineups.
        season: Season identifier (e.g., "2023-24"). Defaults to current.
        season_type: Season type (e.g., "Regular Season", "Playoffs").
        per_mode: Stats calculation mode (e.g., "PerGame", "Totals").
        month: Filter by month (0 for all).
        date_from: Start date filter (YYYY-MM-DD).
        date_to: End date filter (YYYY-MM-DD).
        opponent_team_id: Filter by opponent (0 for all).
        vs_conference: Filter by conference.
        vs_division: Filter by division.
        game_segment: Filter by game segment.
        period: Filter by period (0 for all).
        last_n_games: Filter by last N games (0 for all).
    Returns:
        str: JSON string with detailed lineup statistics including:
            - Basic stats (minutes, points, +/-)
            - Shooting stats (FG%, 3P%, FT%)
            - Advanced metrics (Off/Def Rating, Pace, TS%)
            - Player combinations
    """
    cache_key = generate_cache_key("get_team_lineups", team_id=team_id, season=season, season_type=season_type, per_mode=per_mode, month=month, date_from=date_from, date_to=date_to, opponent_team_id=opponent_team_id, vs_conference=vs_conference, vs_division=vs_division, game_segment=game_segment, period=period, last_n_games=last_n_games)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool get_team_lineups called for season {season}")
    result = fetch_team_lineups_logic(
        team_id=team_id,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        month=month,
        date_from=date_from,
        date_to=date_to,
        opponent_team_id=opponent_team_id,
        vs_conference=vs_conference,
        vs_division=vs_division,
        game_segment=game_segment,
        period=period,
        last_n_games=last_n_games
    )
    cache_data(cache_key, result)
    return result

def get_team_rebounding_stats(
    team_identifier: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> str:
    """
    Fetches team rebounding tracking stats. Returns JSON string.
    Args:
        team_identifier: Name, abbreviation or ID of the team (e.g., "Lakers" or "LAL")
        season: Season to get data for, in format "YYYY-YY" (e.g., "2022-23")
        season_type: "Regular Season", "Playoffs", etc. Defaults to Regular Season.
        per_mode: Mode of stats, like "PerGame" or "Totals". Check if logic uses this.
    Returns:
        String JSON with rebounding statistics for the team
    """
    cache_key = generate_cache_key("get_team_rebounding_stats", team_identifier, season, season_type=season_type, per_mode=per_mode)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool get_team_rebounding_stats called for {team_identifier}, season {season}")
    result = fetch_team_rebounding_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    cache_data(cache_key, result)
    return result


# Game/League Tools
@tool
def find_games(
    player_or_team: str = 'T',
    player_id: Optional[int] = None,
    team_id: Optional[int] = None,
    season: Optional[str] = None,
    season_type: Optional[str] = None,
    league_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Finds games based on Player/Team ID and optional filters. Returns JSON string.
    You MUST provide either player_id (if player_or_team='P') or team_id (if player_or_team='T').

    Args:
        player_or_team (str): Search by 'P' (Player) or 'T' (Team). Defaults to 'T'.
        player_id (int, optional): Player ID. Required if player_or_team='P'.
        team_id (int, optional): Team ID. Required if player_or_team='T'.
        season (str, optional): Season identifier (e.g., "2023-24").
        season_type (str, optional): Season type (e.g., "Regular Season", "Playoffs").
        league_id (str, optional): League ID (e.g., "00" for NBA).
        date_from (str, optional): Start date filter (MM/DD/YYYY).
        date_to (str, optional): End date filter (MM/DD/YYYY).

    Returns:
        str: JSON string containing a list of found games or {'error': ...}.
    """
    # Cache find_games results
    cache_key = generate_cache_key("find_games", player_or_team=player_or_team, player_id=player_id, team_id=team_id, season=season, season_type=season_type, league_id=league_id, date_from=date_from, date_to=date_to)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool 'find_games' called with params: player_or_team={player_or_team}, player_id={player_id}, team_id={team_id}, date_from={date_from}, date_to={date_to}")
    if player_or_team == 'P' and player_id is None:
        return format_response(error="player_id is required when player_or_team='P'.")
    if player_or_team == 'T' and team_id is None:
        return format_response(error="team_id is required when player_or_team='T'.")

    result = fetch_league_games_logic(
        player_or_team_abbreviation=player_or_team,
        player_id_nullable=player_id,
        team_id_nullable=team_id,
        season_nullable=season,
        season_type_nullable=season_type,
        league_id_nullable=league_id,
        date_from_nullable=date_from,
        date_to_nullable=date_to
    )
    cache_data(cache_key, result)
    return result

@tool
def get_boxscore_traditional(game_id: str) -> str:
    """
    Fetches the traditional box score (V3) for a specific game. Returns JSON string.
    Args: game_id (str): The 10-digit ID of the game.
    Returns: str: JSON string containing player and team stats or {'error': ...}.
    """
    cache_key = generate_cache_key("get_boxscore_traditional", game_id)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'. Returning cached result.")
        logger.debug(f"Cached result content for '{cache_key}': {cached_result}")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_boxscore_traditional' called for game_id '{game_id}'")
    # Log the exact parameters being passed to the logic function
    logger.info(f"--> EXACT PARAMS for fetch_boxscore_traditional_logic: game_id='{game_id}'")
    result_dict = fetch_boxscore_traditional_logic(game_id)
    # result_dict might be a string here if the logic function returns formatted JSON directly
    # Let's log what we get back from the logic function
    logger.debug(f"Raw result from fetch_boxscore_traditional_logic for {game_id} (type {type(result_dict)}): {str(result_dict)[:500]}...")
    
    # Ensure we handle potential errors returned as dicts from the logic layer if it changes
    if isinstance(result_dict, dict) and 'error' in result_dict:
        logger.warning(f"Logic function returned error dict for {game_id}: {result_dict['error']}")
        # Convert error dict to JSON string for return
        result_str = json.dumps(result_dict)
    elif isinstance(result_dict, str):
         # If logic returns JSON string directly (as assumed previously)
         result_str = result_dict
         # Optionally parse to check for error before caching (like in advanced)
         try:
             parsed_data = json.loads(result_str)
             if isinstance(parsed_data, dict) and 'error' in parsed_data:
                 logger.warning(f"Logic function returned error JSON for {game_id}: {parsed_data['error']}")
                 # Don't cache errors
                 cache_data(cache_key, result_str) # Cache anyway? Or skip caching errors?
                                                  # Let's skip caching errors here for consistency
                 logger.debug(f"Tool 'get_boxscore_traditional' returning error string to agent framework (len={len(result_str)}): {result_str[:500]}...")
                 return result_str # Return error string
         except json.JSONDecodeError:
             logger.error(f"Logic function returned non-JSON string for {game_id}: {result_str[:500]}...")
             # Handle non-JSON string case if necessary, maybe return as error? 
             # For now, proceed assuming it *should* be JSON if not error dict
             pass # Fall through to caching attempt
             
    else: # Should ideally be JSON string or error dict, but handle unexpected types
        logger.warning(f"Unexpected type returned by logic function for {game_id}: {type(result_dict)}. Attempting dump.")
        try:
            result_str = json.dumps(result_dict, default=str)
        except Exception as dump_err:
            logger.error(f"Failed to dump unexpected result type to JSON for {game_id}: {dump_err}")
            result_str = format_response(error=f"Internal error processing boxscore for {game_id}")

    # Log the final string being returned *after* potential conversion/error checks
    logger.debug(f"Tool 'get_boxscore_traditional' returning string to agent framework (len={len(result_str)}): {result_str[:500]}...")
    
    # Refined Caching Check: Only cache if it's likely valid data
    try:
        parsed_for_cache = json.loads(result_str)
        if not (isinstance(parsed_for_cache, dict) and 'error' in parsed_for_cache):
            logger.debug(f"Caching successful result for {cache_key}")
            cache_data(cache_key, result_str)
        else:
            logger.warning(f"Result for {cache_key} is an error, not caching: {result_str[:500]}...")
    except json.JSONDecodeError:
        logger.error(f"Final result string for {cache_key} is not valid JSON, not caching: {result_str[:500]}...")
        
    return result_str

@tool
def get_league_standings(season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular, league_id: str = LeagueID.nba) -> str:
    """
    Fetches league standings (conference, division) for a specific season and type.

    Args:
        season (str): Season identifier (e.g., "2023-24"). Defaults to current season.
        season_type (str): Season type ('Regular Season', 'Playoffs'). Defaults to Regular Season.

    Returns:
        str: JSON string containing a list of teams in the standings, sorted by conference/rank, each with:
            - TeamID, TeamName, Conference, PlayoffRank, WinPct, GB (Games Back)
            - L10 (Last 10 games record), STRK (Current Streak)
            - WINS, LOSSES, HOME (Home record), ROAD (Away record)
            - Division, ClinchIndicator, DivisionRank
            - ConferenceRecord, DivisionRecord
            - Or {'standings': []} if no data, or {'error': ...} if an error occurs.
    """
    # Cache standings based on parameters. Assumes cache has some eviction/TTL or manual clearing.
    cache_key = generate_cache_key("get_league_standings", season=season, season_type=season_type)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_league_standings' called for season '{season}', type '{season_type}', league '{league_id}'")
    result = fetch_league_standings_logic(season=season, season_type=season_type)
    cache_data(cache_key, result)
    return result

@tool
def get_scoreboard(game_date: Optional[str] = None, league_id: str = LeagueID.nba, day_offset: int = 0) -> str:
    """
    Fetches the scoreboard for a specific date, league, and day offset.

    Args:
        game_date (str, optional): Date in YYYY-MM-DD format. Defaults to today if None.
        league_id (str, optional): League ID ('00'=NBA, '10'=WNBA, '20'=G-League). Defaults to '00'.
        day_offset (int, optional): Day offset from game_date (e.g., -1 for previous day). Defaults to 0.

    Returns:
        str: JSON string containing scoreboard data:
            - game_date (str): Date queried.
            - game_header (list[dict]): List of games for the date, each with:
                - GAME_DATE_EST, GAME_SEQUENCE, GAME_ID, GAME_STATUS_ID, GAME_STATUS_TEXT
                - HOME_TEAM_ID, AWAY_TEAM_ID, NATL_TV_BROADCASTER_ABBREVIATION, LIVE_PERIOD, LIVE_PC_TIME
            - line_score (list[dict]): List of line scores for each game, including:
                - GAME_ID, TEAM_ID, TEAM_ABBREVIATION, TEAM_CITY_NAME, TEAM_WINS_LOSSES
                - PTS_QTR1, PTS_QTR2, PTS_QTR3, PTS_QTR4, PTS_OT1..10, PTS (Total)
            - Or {'error': ...} if an error occurs.
    """
    # Use today's date if None is provided
    # Recalculate final_game_date here as it's used in the cache key and logic call
    final_game_date = game_date or datetime.date.today().strftime('%Y-%m-%d') # Use date instead of datetime

    cache_key = generate_cache_key("get_scoreboard", game_date=final_game_date, league_id=league_id, day_offset=day_offset)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result
    
    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_scoreboard' called for date '{final_game_date}', league '{league_id}', offset '{day_offset}'")
    result = fetch_scoreboard_logic(game_date=final_game_date, league_id=league_id, day_offset=day_offset)
    cache_data(cache_key, result)
    return result

@tool
def get_play_by_play(
    game_id: str,
    start_period: int = 0,
    end_period: int = 0
) -> str:
    """
    Fetches the play-by-play data for a specific game ID.
    Attempts to fetch live data first, falls back to historical if live fails.
    Period filtering only applies if the game is finished and historical data is used.

    Args:
        game_id (str): The 10-digit ID of the game.
        start_period (int, optional): Starting period filter (1-4, or 5+ for OT). Defaults to 0 (all). 
                                     Only applies when fetching historical data.
        end_period (int, optional): Ending period filter (1-4, or 5+ for OT). Defaults to 0 (all).
                                     Only applies when fetching historical data.

    Returns: 
        str: JSON string containing play-by-play data:
            - game_id (str)
            - source (str): "live" or "historical"
            - parameters (dict): Filters applied (start_period, end_period).
            - periods (list[dict]): List of periods, each containing:
                - period (int)
                - plays (list[dict]): List of plays in the period, each with:
                    - event_num, clock, score, margin (hist only), team, home/away/neutral_description, event_type.
            - has_video (bool, historical only)
            - Or {'error': ...} if an error occurs.
    """
    # Only cache if the game is likely finished (logic determines source)
    # Let's cache based on game_id and periods for historical results.
    # We need the logic function to return an indicator if it used historical data.
    # For now, we'll call the logic first and cache only if source is 'historical'.

    logger.debug(f"Tool 'get_play_by_play' called for game_id '{game_id}', periods '{start_period}'-'{end_period}'")

    # Generate potential cache key first
    cache_key = generate_cache_key("get_play_by_play", game_id, start_period=start_period, end_period=end_period)
    
    # Check cache *only* if we assume this call *might* be for historical data
    # A better approach might be to check game status first, but let's proceed simply
    cached_result = get_cached_data(cache_key)
    if cached_result:
         try:
             cached_data = json.loads(cached_result)
             # Check if the cached data confirms it was historical
             if cached_data.get("source") == "historical":
                 logger.debug(f"Cache hit for historical play-by-play '{cache_key}'")
                 return cached_result
             else:
                 logger.debug(f"Cache hit for '{cache_key}', but was not historical. Fetching fresh.")
         except json.JSONDecodeError:
             logger.warning(f"Could not parse cached JSON for '{cache_key}'. Fetching fresh.")
             # Proceed to fetch fresh data

    # Cache miss or non-historical cache hit
    logger.debug(f"Fetching play-by-play for '{game_id}' (potential cache miss or live data needed)")
    result_str = fetch_playbyplay_logic(game_id=game_id, start_period=start_period, end_period=end_period)

    # Cache the result ONLY if the source was historical
    try:
        result_data = json.loads(result_str)
        if result_data.get("source") == "historical":
            logger.debug(f"Caching historical play-by-play result for '{cache_key}'")
            cache_data(cache_key, result_str)
        else:
            logger.debug(f"Not caching non-historical play-by-play for game '{game_id}'")
    except json.JSONDecodeError:
        logger.error(f"Could not parse play-by-play result JSON for game '{game_id}'. Not caching.")
    except Exception as e:
         logger.error(f"Error processing play-by-play result for caching: {e}")

    return result_str


@tool
def get_draft_history(
    season_year: Optional[str] = None, # YYYY format
    league_id: str = LeagueID.nba,
    round_num: Optional[int] = None,
    team_id: Optional[int] = None,
    overall_pick: Optional[int] = None
) -> str:
    """
    Fetches draft history, optionally filtered by season year, league, round, team, or overall pick.

    Args:
        season_year (str, optional): Draft year in YYYY format. Defaults to all years if None.
        league_id (str, optional): League ID ('00'=NBA, '10'=WNBA, '20'=G-League). Defaults to '00'.
        round_num (int, optional): Filter by draft round number.
        team_id (int, optional): Filter by drafting team ID.
        overall_pick (int, optional): Filter by overall pick number.

    Returns:
        str: JSON string containing:
            - parameters (dict): Filters applied.
            - draft_picks (list[dict]): List of draft picks matching the criteria, each with:
                - PERSON_ID, PLAYER_NAME, SEASON, ROUND_NUMBER, ROUND_PICK, OVERALL_PICK
                - TEAM_ID, TEAM_CITY, TEAM_NAME, ORGANIZATION, ORGANIZATION_TYPE
            - Or {'draft_picks': []} if no data, or {'error': ...} if an error occurs.
    """
    cache_key = generate_cache_key("get_draft_history", season_year=season_year, league_id=league_id, round_num=round_num, team_id=team_id, overall_pick=overall_pick)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(
        f"Cache miss for '{cache_key}'. Tool 'get_draft_history' called for Year: {season_year}, League: {league_id}, "
        f"Round: {round_num}, Team: {team_id}, Pick: {overall_pick}"
    )
    result = fetch_draft_history_logic(
        season_year=season_year,
        league_id=league_id,
        round_num=round_num,
        team_id=team_id,
        overall_pick=overall_pick
    )
    cache_data(cache_key, result)
    return result

@tool
def get_league_leaders(
    stat_category: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerMode48.per_game,
    league_id: str = LeagueID.nba,
    scope: str = Scope.s,
    top_n: int = 10
) -> str:
    """
    Fetches league leaders for a specific statistical category, season, and type.

    Args:
        stat_category (str): The stat category abbreviation (e.g., 'PTS', 'AST', 'REB', 'BLK', 'STL'). 
                             See nba_api.stats.library.parameters.StatCategoryAbbreviation for options.
        season (str): Season identifier (e.g., "2023-24"). Defaults to current season.
        season_type (str): Season type ('Regular Season', 'Playoffs'). Defaults to Regular Season.
        per_mode (str): Stat mode ('PerGame', 'Totals', etc.). Defaults to PerGame.
                        See nba_api.stats.library.parameters.PerMode48 for options.
        league_id (str, optional): League ID ('00'=NBA, '10'=WNBA, '20'=G-League). Defaults to '00'.
        scope (str, optional): Scope of players ('All Players', 'Rookies'). Defaults to 'All Players'.
                           See nba_api.stats.library.parameters.Scope for options.

    Returns:
        str: JSON string containing:
            - season, stat_category, season_type, per_mode, league_id, scope # Parameters used
            - leaders (list[dict]): List of league leaders, each with:
                - PlayerID, RANK, PLAYER, TEAM_ID, TEAM, GP, MIN, FGM, FGA, FG_PCT, ... (stats vary by category)
            - Or {'leaders': []} if no data, or {'error': ...} if an error occurs.
    """
    cache_key = generate_cache_key("get_league_leaders", stat_category, season=season, season_type=season_type, per_mode=per_mode, league_id=league_id, scope=scope, top_n=top_n)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(
        f"Cache miss for '{cache_key}'. Tool 'get_league_leaders' called for Cat: {stat_category}, Season: {season}, Type: {season_type}, "
        f"Mode: {per_mode}, League: {league_id}, Scope: {scope}, TopN: {top_n}"
    )
    result = fetch_league_leaders_logic(
        season=season,
        stat_category=stat_category,
        season_type=season_type,
        per_mode=per_mode,
        league_id=league_id,
        scope=scope,
        top_n=top_n
    )
    cache_data(cache_key, result)
    return result

@tool
def get_player_hustle_stats(
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    player_name: Optional[str] = None,
    team_id: Optional[int] = None,
    league_id: str = LeagueID.nba,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Fetches player hustle statistics (deflections, loose balls recovered, charges drawn, etc.).
    Can be filtered league-wide or by specific player or team.

    Args:
        season (str): Season identifier (e.g., "2023-24"). Defaults to current season.
        season_type (str): Season type ('Regular Season', 'Playoffs'). Defaults to Regular Season.
        per_mode (str): Stat mode ('PerGame', 'Totals', etc.). Defaults to PerGame.
        player_name (str, optional): Filter by player name. Returns only this player's stats.
        team_id (int, optional): Filter by team ID. Returns stats for players on this team.
                              (Note: Provide player_name OR team_id, not both usually).
        league_id (str, optional): League ID ('00'=NBA, '10'=WNBA, '20'=G-League). Defaults to '00'.
        date_from (str, optional): Start date filter (YYYY-MM-DD).
        date_to (str, optional): End date filter (YYYY-MM-DD).

    Returns:
        str: JSON string containing:
            - parameters (dict): Filters applied.
            - hustle_stats (list[dict]): List of players and their hustle stats:
                - player (dict): {id, name, team}
                - games_played, minutes
                - defensive_stats (dict): charges_drawn, contested_shots (total/3pt/2pt), deflections.
                - loose_ball_stats (dict): recovered (total/off/def).
                - screen_stats (dict): screen_assists, screen_assist_points.
                - box_out_stats (dict): box_outs (total/off/def).
            - Or {'hustle_stats': []} if no data matches filters, or {'error': ...} if an error occurs.
    """
    cache_key = generate_cache_key("get_player_hustle_stats", season=season, season_type=season_type, per_mode=per_mode, player_name=player_name, team_id=team_id, league_id=league_id, date_from=date_from, date_to=date_to)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(
        f"Cache miss for '{cache_key}'. Tool 'get_player_hustle_stats' called for Season: {season}, Type: {season_type}, Mode: {per_mode}, "
        f"Player: {player_name}, Team: {team_id}, League: {league_id}"
    )
    result = fetch_player_hustle_stats_logic(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        player_name=player_name,
        team_id=team_id,
        league_id=league_id,
        date_from=date_from,
        date_to=date_to
    )
    cache_data(cache_key, result)
    return result

@tool
def get_player_profile(player_name: str, per_mode: str = PerModeDetailed.per_game) -> str:
    """
    Fetches a comprehensive player profile, including basic info, career/season highs, 
    next game details, and career/season totals across different season types (Regular, Post, etc.).

    Args:
        player_name (str): Full name of the player.
        per_mode (str): Stat mode ('PerGame', 'Totals', 'Per36', etc.) to apply to stats where applicable.
                        Defaults to 'PerGame'. See PerModeDetailed for options.

    Returns:
        str: JSON string containing the player profile:
            - player_name (str), player_id (int)
            - player_info (dict): Basic info from commonplayerinfo (team, position, height, weight, etc.).
            - per_mode_requested (str): The per_mode used for the request.
            - career_highs (dict): Player's career high stats (PTS, REB, AST, etc.).
            - season_highs (dict): Player's current season high stats.
            - next_game (dict): Details about the player's next scheduled game.
            - career_totals (dict): Career totals broken down by season type:
                - regular_season (dict)
                - post_season (dict)
                - all_star (dict)
                - preseason (dict)
                - college (dict)
            - season_totals (dict): Season totals broken down by season type:
                - regular_season (list[dict])
                - post_season (list[dict])
                - all_star (list[dict])
                - preseason (list[dict])
                - college (list[dict])
            - Or {'error': ...} if an error occurs.
    """
    # Player profile combines info, career, season stats - good candidate for caching
    cache_key = generate_cache_key("get_player_profile", player_name, per_mode=per_mode)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool get_player_profile called for {player_name}, per_mode {per_mode}")
    result = fetch_player_profile_logic(player_name, per_mode)
    cache_data(cache_key, result)
    return result

@tool
def get_player_aggregate_stats(player_name: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches an aggregated set of player statistics including basic info, career stats, 
    current season game log, and awards.

    Args:
        player_name (str): Full name of the player.
        season (str): Season identifier for the game log (e.g., "2023-24"). Defaults to current season.
        season_type (str): Season type for the game log ("Regular Season", "Playoffs"). Defaults to Regular Season.

    Returns:
        str: JSON string containing combined player stats:
            - player_name (str), player_id (int)
            - season (str), season_type (str) # Params used for gamelog part
            - info (dict): Basic player info.
            - headline_stats (dict): Key current season stats (PTS, AST, REB).
            - career_stats (dict): 
                - season_totals (list[dict])
                - career_totals (dict)
            - current_season (dict): 
                - gamelog (list[dict])
            - awards (list[dict])
            - Or {"error": ...} if any of the underlying data fetches fail.
    """
    # Caching aggregate stats based on player, season, and type
    cache_key = generate_cache_key("get_player_aggregate_stats", player_name, season=season, season_type=season_type)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool \"get_player_aggregate_stats\" called for {player_name}, season {season}, type {season_type}")
    
    # Need to import fetch_player_stats_logic from player_tools
    from backend.api_tools.player_tools import fetch_player_stats_logic
    
    result = fetch_player_stats_logic(player_name=player_name, season=season, season_type=season_type)
    cache_data(cache_key, result)
    return result

@tool
def get_top_performers(category: str = "PTS", season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerMode48.per_game, top_n: int = 5) -> str:
    """
    Gets the top N players for a specific statistical category in a given season/type.

    Args:
        category (str): Stat category abbreviation (e.g., 'PTS', 'AST', 'REB'). Defaults to 'PTS'.
                        See nba_api.stats.library.parameters.StatCategoryAbbreviation for options.
        season (str): Season identifier (e.g., "2023-24"). Defaults to current season.
        season_type (str): Season type ('Regular Season', 'Playoffs'). Defaults to Regular Season.
        per_mode (str): Stat mode ('PerGame', 'Totals', etc.). Defaults to PerGame.
                        See nba_api.stats.library.parameters.PerMode48 for options.
        top_n (int): Number of top players to return. Defaults to 5.

    Returns:
        str: JSON string containing a list of the top N performers for the category, each with:
            - PlayerID, RANK, PLAYER, TEAM_ID, TEAM, GP, MIN, and the specified stat category value.
            - Or {'error': ...} if league leaders data cannot be fetched or processed.
    """
    # Cache top performers based on all parameters
    cache_key = generate_cache_key("get_top_performers", category=category, season=season, season_type=season_type, per_mode=per_mode, top_n=top_n)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_top_performers' called for Cat: {category}, Season: {season}, Type: {season_type}, Mode: {per_mode}, Top: {top_n}")
    try:
        # Call get_league_leaders to get the full list
        # Note: get_league_leaders is now cached itself, so this call might hit the cache
        leaders_json = get_league_leaders(
            stat_category=category,
            season=season,
            season_type=season_type,
            per_mode=per_mode
            # league_id and scope defaults are usually fine for this use case
        )
        
        leaders_data = json.loads(leaders_json)
        
        if "error" in leaders_data:
            logger.error(f"Error fetching league leaders for top performers: {leaders_data['error']}")
            # Don't cache errors
            return leaders_json # Return the original error
            
        leaders_list = leaders_data.get("leaders", [])
        
        if not leaders_list:
            logger.warning(f"No league leaders found for category '{category}' in {season}")
            result_str = json.dumps({"top_performers": []}) # Return empty list
            cache_data(cache_key, result_str) # Cache the empty result
            return result_str
            
        # Sort by rank (already done by API, but double-check just in case)
        # leaders_list.sort(key=lambda x: x.get('RANK', 999))
        
        # Get the top N
        top_performers_list = leaders_list[:top_n]
        
        result_str = json.dumps({"top_performers": top_performers_list})
        cache_data(cache_key, result_str) # Cache the successful result
        return result_str
        
    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to parse league leaders JSON: {json_err}")
        return json.dumps({"error": f"Failed to process league leaders data: {json_err}"})
    except Exception as e:
        logger.error(f"Error getting top performers for {category}: {e}", exc_info=True)
        return json.dumps({"error": f"Unexpected error getting top performers: {str(e)}"})

@tool
def get_top_teams(season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular, league_id: str = LeagueID.nba, top_n: int = 5) -> str:
    """
    Gets the top N teams based on league standings for a given season/type.

    Args:
        season (str): Season identifier (e.g., "2023-24"). Defaults to current season.
        season_type (str): Season type ('Regular Season', 'Playoffs'). Defaults to Regular Season.
        league_id (str, optional): League ID ('00'=NBA, '10'=WNBA, '20'=G-League). Defaults to '00'.
        top_n (int): Number of top teams to return (per conference). Defaults to 5.

    Returns:
        str: JSON string containing a list of the top N teams per conference based on PlayoffRank, each with:
            - TeamID, TeamName, Conference, PlayoffRank, WinPct, GB, L10, STRK, WINS, LOSSES, etc.
            - Or {'error': ...} if standings data cannot be fetched or processed.
    """
    # Cache top teams based on parameters
    cache_key = generate_cache_key("get_top_teams", season=season, season_type=season_type, league_id=league_id, top_n=top_n)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_top_teams' called for Season: {season}, Type: {season_type}, League: {league_id}, Top: {top_n}")
    try:
        # Call get_league_standings (which is now cached)
        standings_json = get_league_standings(
            season=season, 
            season_type=season_type,
            league_id=league_id
        )
        
        standings_data = json.loads(standings_json)
        
        if "error" in standings_data:
            logger.error(f"Error fetching league standings for top teams: {standings_data['error']}")
            # Don't cache errors from dependencies
            return standings_json # Return original error
            
        standings_list = standings_data.get("standings", [])
        
        if not standings_list:
            logger.warning(f"No standings data found for {season}, type {season_type}")
            result_str = json.dumps({"top_teams": []})
            cache_data(cache_key, result_str) # Cache empty result
            return result_str
            
        # Standings are already sorted by Conference, then PlayoffRank in the logic function
        # We just need to take the top N from each conference
        
        east_teams = [team for team in standings_list if team.get("Conference") == "East"][:top_n]
        west_teams = [team for team in standings_list if team.get("Conference") == "West"][:top_n]
        
        top_teams_list = east_teams + west_teams
        
        # Optional: Re-sort overall if desired, though per-conference top N is common
        # top_teams_list.sort(key=lambda x: x.get('PlayoffRank', 99))

        result_str = json.dumps({"top_teams": top_teams_list})
        cache_data(cache_key, result_str) # Cache successful result
        return result_str

    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to parse league standings JSON: {json_err}")
        return json.dumps({"error": f"Failed to process league standings data: {json_err}"})
    except Exception as e:
        logger.error(f"Error getting top teams for {season}: {e}", exc_info=True)
        return json.dumps({"error": f"Unexpected error getting top teams: {str(e)}"})

@tool
def get_player_insights(player_name: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerModeDetailed.per_game, league_id: str = LeagueID.nba) -> str:
    """
    Fetches overall player dashboard stats for a given season, type, and mode.
    NOTE: This tool currently returns overall stats for the specified period, 
    not deep analysis or year-over-year trends, despite the name 'insights'.
    The underlying endpoint (PlayerDashboardByYearOverYear) contains YOY data.

    Args:
        player_name (str): Full name of the player.
        season (str): Season identifier (e.g., "2023-24"). Defaults to current season.
        season_type (str): Season type ('Regular Season', 'Playoffs'). Defaults to Regular Season.
        per_mode (str): Stat mode ('PerGame', 'Totals', etc.). Defaults to PerGame.
        league_id (str, optional): League ID ('00'=NBA, '10'=WNBA, '20'=G-League). Defaults to '00'.

    Returns:
        str: JSON string containing overall dashboard stats:
            - player_name, player_id, season, season_type, per_mode, league_id # Parameters
            - overall_dashboard_stats (list[dict]): Typically a single-element list containing the overall stats 
              for the player in the specified period (GP, W, L, W_PCT, MIN, FGM, FGA, ..., PLUS_MINUS).
            - Or {'error': ...} if an error occurs.
    """
    # Cache player dashboard stats based on parameters
    cache_key = generate_cache_key("get_player_insights", player_name, season=season, season_type=season_type, per_mode=per_mode, league_id=league_id)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(
        f"Cache miss for '{cache_key}'. Tool 'get_player_insights' called for Player: {player_name}, Season: {season}, Type: {season_type}, "
        f"Mode: {per_mode}, League: {league_id}"
    )
    result = analyze_player_stats_logic(
        player_name=player_name, 
        season=season, 
        season_type=season_type,
        per_mode=per_mode,
        league_id=league_id
    )
    cache_data(cache_key, result)
    return result

@tool
def get_live_odds() -> str:
    """
    Fetches live betting odds for today's NBA games.
    
    Args:
        None
        
    Returns:
        str: JSON string containing a list of today's games and their odds:
            - games (list[dict]): Each game object likely contains:
                - gameId, startTime, gameStatus, homeTeam, awayTeam
                - odds (list[dict]): List of odds from different providers, each with:
                    - provider, type (e.g., moneyline, spread, total), value, odds, etc.
            - Or {'error': ...} if fetching odds fails.
    """
    # DO NOT CACHE LIVE ODDS
    logger.debug("Tool 'get_live_odds' called - Not Caching Live Data")
    # Logic function returns a dict, format_response converts to JSON string
    return format_response(fetch_odds_data_logic())

@tool
def get_game_shotchart(
    game_id: str, 
    team_id: Optional[int] = None, 
    player_id: Optional[int] = None,
    season: Optional[str] = None, # Often redundant if game_id is provided
    season_type: Optional[str] = None # Often redundant if game_id is provided
) -> str:
    """
    Fetches shot chart details for a specific game, optionally filtered by team or player.

    Args:
        game_id (str): The 10-digit ID of the game.
        team_id (int, optional): Filter shots for a specific team in the game.
        player_id (int, optional): Filter shots for a specific player in the game.
        season (str, optional): Season identifier (e.g., "2023-24"). Usually inferred from game_id.
        season_type (str, optional): Season type ("Regular Season", "Playoffs"). Usually inferred.

    Returns:
        str: JSON string containing:
            - parameters (dict): Filters applied (currently only game_id).
            - shot_chart_detail (list[dict]): List of individual shots with details like:
                - GAME_ID, TEAM_ID, PLAYER_ID, PLAYER_NAME
                - EVENT_TYPE (Made Shot, Missed Shot)
                - ACTION_TYPE, SHOT_TYPE, SHOT_ZONE_BASIC, SHOT_ZONE_AREA, SHOT_ZONE_RANGE
                - SHOT_DISTANCE, LOC_X, LOC_Y, SHOT_ATTEMPTED_FLAG, SHOT_MADE_FLAG
            - league_averages (list[dict]): League average shooting percentages by zone for comparison.
            - Or {"error": ...} if an error occurs.
    """
    # Cache game shot charts based on game_id and filters (although filters aren't implemented yet)
    cache_key = generate_cache_key("get_game_shotchart", game_id, team_id=team_id, player_id=player_id, season=season, season_type=season_type)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result

    logger.debug(f"Cache miss for '{cache_key}'. Tool \"get_game_shotchart\" called for game \"{game_id}\", team \"{team_id}\", player \"{player_id}\"")
    
    # The logic function fetch_shotchart_logic currently only takes game_id.
    # TODO: Enhance fetch_shotchart_logic in game_tools.py to accept team_id, player_id, season, season_type
    # and pass them to the shotchartdetail endpoint.
    if team_id or player_id or season or season_type:
        logger.warning("Team, player, season, or type filters for get_game_shotchart are not yet implemented in the underlying logic function.")

    # Logic function should be imported at the top now.
    result = fetch_shotchart_logic(game_id=game_id)
    cache_data(cache_key, result)
    return result

# --- Matchup Tools ---
@tool
def get_season_matchups(def_player_id: str, off_player_id: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches season matchups between two players.
    """
    return fetch_league_season_matchups_logic(def_player_id, off_player_id, season, season_type)

@tool
def get_matchups_rollup(def_player_id: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches matchup rollup for a defensive player across opponents.
    """
    return fetch_matchups_rollup_logic(def_player_id, season, season_type)

# --- Synergy Play Types ---
@tool
def get_synergy_play_types(
    league_id: str = LeagueID.nba,
    per_mode: str = PerModeSimple.default,
    player_or_team_abbreviation: str = PlayerOrTeamAbbreviation.default,
    season_type: str = SeasonTypeAllStar.regular,
    season: str = CURRENT_SEASON,
    play_type: Optional[str] = None,
    type_grouping: Optional[str] = None
) -> str:
    """
    Fetch synergy play types stats for team or player.
    """
    return fetch_synergy_play_types_logic(league_id, per_mode, player_or_team_abbreviation, season_type, season, play_type, type_grouping)

# --- Analyze Player Stats ---
@tool
def get_player_analysis(
    player_name: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    league_id: str = LeagueID.nba
) -> str:
    """
    Analyzes player stats year-over-year.
    """
    return analyze_player_stats_logic(player_name, season, season_type, per_mode, league_id)

# --- Game Analytics Extensions ---
@tool
def get_boxscore_advanced(game_id: str, end_period: int = 0, end_range: int = 0, start_period: int = 0, start_range: int = 0) -> str:
    """
    Fetches advanced box score V3 data for a specific game.
    """
    cache_key = generate_cache_key("get_boxscore_advanced", game_id, end_period, end_range, start_period, start_range)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result
    log_limit = 500
    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_boxscore_advanced' called for game_id '{game_id}'")
    # Calls the logic function, which returns a JSON string (either data or error)
    result = fetch_boxscore_advanced_logic(game_id, end_period, end_range, start_period, start_range)
    try:
        # Attempt to parse the result JSON
        result_data = json.loads(result)
        # Only cache if it doesn't contain a top-level 'error' key
        if not (isinstance(result_data, dict) and 'error' in result_data):
            logger.debug(f"Caching successful result for {cache_key}")
            cache_data(cache_key, result) 
        else:
            logger.warning(f"Result for {cache_key} is an error, not caching: {result}")
    except json.JSONDecodeError:
        # If the result isn't valid JSON, definitely don't cache it
        logger.error(f"Result for {cache_key} is not valid JSON, not caching: {result[:log_limit]}...")
        
    # Return the result regardless of whether it was cached
    return result

@tool
def get_boxscore_four_factors(game_id: str, start_period: int = 0, end_period: int = 0) -> str:
    """Fetches box score four factors V3 data for a specific game."""
    cache_key = generate_cache_key("get_boxscore_four_factors", game_id, start_period, end_period)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result
    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_boxscore_four_factors' called for game_id '{game_id}'")
    result = fetch_boxscore_four_factors_logic(game_id, start_period, end_period)
    cache_data(cache_key, result)
    return result

@tool
def get_boxscore_usage(game_id: str) -> str:
    """Fetches box score usage stats V3 data for a specific game."""
    cache_key = generate_cache_key("get_boxscore_usage", game_id)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result
    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_boxscore_usage' called for game_id '{game_id}'")
    result = fetch_boxscore_usage_logic(game_id)
    cache_data(cache_key, result)
    return result

@tool
def get_boxscore_defensive(game_id: str) -> str:
    """Fetches box score defensive stats V2 data for a specific game."""
    cache_key = generate_cache_key("get_boxscore_defensive", game_id)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result
    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_boxscore_defensive' called for game_id '{game_id}'")
    result = fetch_boxscore_defensive_logic(game_id)
    cache_data(cache_key, result)
    return result

@tool
def get_win_probability(game_id: str, run_type: str = RunType.default) -> str:
    """Fetches win probability play-by-play data for a specific game."""
    cache_key = generate_cache_key("get_win_probability", game_id, run_type)
    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for '{cache_key}'")
        return cached_result
    logger.debug(f"Cache miss for '{cache_key}'. Tool 'get_win_probability' called for game_id '{game_id}'")
    result = fetch_win_probability_logic(game_id, run_type)
    cache_data(cache_key, result)
    return result

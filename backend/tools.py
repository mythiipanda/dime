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
    SeasonTypeAllStar, PerModeDetailed, PerMode36, LeagueID, PerMode48
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
    fetch_player_profile_logic
)
from backend.api_tools.team_tools import (
    fetch_team_info_and_roster_logic,
    fetch_team_lineups_logic,
    # fetch_team_stats_logic, # Logic exists but no corresponding tool wrapper defined
)
from backend.api_tools.game_tools import (
    fetch_boxscore_traditional_logic,
    fetch_playbyplay_logic,
    fetch_league_games_logic # Used by find_games
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

logger = logging.getLogger(__name__)

# --- Agno Tool Functions (Wrappers for Logic) ---

# Player Tools
@tool
def get_player_info(player_name: str) -> str:
    """
    Fetches basic player information and headline stats. Returns JSON string.
    Args: player_name (str): Full name of the player.
    Returns: str: JSON string containing player info/stats or {'error': ...}.
    """
    logger.debug(f"Tool 'get_player_info' called for '{player_name}'")
    return fetch_player_info_logic(player_name)

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
    logger.debug(f"Tool 'get_player_gamelog' called for '{player_name}', season '{season}', type '{season_type}'")
    valid_season_types = [st for st in dir(SeasonTypeAllStar) if not st.startswith('_') and isinstance(getattr(SeasonTypeAllStar, st), str)]
    if season_type not in valid_season_types:
        logger.warning(f"Invalid season_type '{season_type}' in tool wrapper. Logic function should handle default.")
    return fetch_player_gamelog_logic(player_name, season, season_type)

@tool
def get_player_career_stats(player_name: str, per_mode36: str = PerMode36.per_game) -> str:
    """
    Fetches player career statistics (Regular Season). Returns JSON string.
    Args:
        player_name (str): Full name of the player.
        per_mode36 (str): Stat mode ('PerGame', 'Totals', 'Per36', etc.). Defaults to 'PerGame'.
    Returns: str: JSON string containing career stats data or {'error': ...}.
    """
    logger.debug(f"Tool 'get_player_career_stats' called for '{player_name}', per_mode36 '{per_mode36}'")
    valid_per_modes = [getattr(PerMode36, attr) for attr in dir(PerMode36) if not attr.startswith('_') and isinstance(getattr(PerMode36, attr), str)]
    if per_mode36 not in valid_per_modes:
         logger.warning(f"Invalid per_mode36 '{per_mode36}' in tool wrapper. Logic function should handle default.")
    return fetch_player_career_stats_logic(player_name, per_mode36)

@tool
def get_player_awards(player_name: str) -> str:
    """
    Fetches the awards won by a specific player. Returns JSON string.
    Args: player_name (str): Full name of the player.
    Returns: str: JSON string containing a list of awards or {'error': ...}.
    """
    logger.debug(f"Tool 'get_player_awards' called for '{player_name}'")
    return fetch_player_awards_logic(player_name)

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
    logger.debug(f"Tool get_player_shotchart called for {player_name}, season {season}")
    return fetch_player_shotchart_logic(
        player_name=player_name,
        season=season,
        season_type=season_type
    )

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
    logger.debug(f"Tool get_player_defense_stats called for {player_name}, season {season}")
    return fetch_player_defense_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )

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
    logger.debug(f"Tool 'get_player_clutch_stats' called for '{player_name}', season '{season}', type '{season_type}'")
    result = fetch_player_clutch_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type
    )
    return json.dumps(result, default=str)

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
    logger.debug(f"Tool get_player_passing_stats called for {player_name}, season {season}")
    return fetch_player_passing_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type
    )

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
    logger.debug(f"Tool get_player_rebounding_stats called for {player_name}, season {season}")
    return fetch_player_rebounding_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type
    )

@tool
def get_player_shots_tracking(player_id: str) -> str:
    """
    Fetches player shot tracking stats using the player's ID. Returns JSON string.
    Args:
        player_id (str): The NBA player ID.
    Returns: str: JSON string containing shot tracking stats or {'error': ...}.
    """
    logger.debug(f"Tool 'get_player_shots_tracking' called for player_id '{player_id}'")
    return fetch_player_shots_tracking_logic(player_id=player_id)


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
    logger.debug(f"Tool 'get_team_info_and_roster' called for '{team_identifier}', season '{season}'")
    return fetch_team_info_and_roster_logic(team_identifier, season)

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
    logger.debug(f"Tool get_team_passing_stats called for {team_identifier}, season {season}")
    return fetch_team_passing_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )

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
    logger.debug(f"Tool get_team_shooting_stats called for {team_identifier}, season {season}")
    return fetch_team_shooting_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )

@tool
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
    logger.debug(f"Tool get_team_lineups called for season {season}")
    return fetch_team_lineups_logic(
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
    logger.debug(f"Tool get_team_rebounding_stats called for {team_identifier}, season {season}")
    return fetch_team_rebounding_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )


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
    logger.debug(f"Tool 'find_games' called with params: player_or_team={player_or_team}, player_id={player_id}, team_id={team_id}, date_from={date_from}, date_to={date_to}")
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
    return result

@tool
def get_boxscore_traditional(game_id: str) -> str:
    """
    Fetches the traditional box score (V3) for a specific game. Returns JSON string.
    Args: game_id (str): The 10-digit ID of the game.
    Returns: str: JSON string containing player and team stats or {'error': ...}.
    """
    logger.debug(f"Tool 'get_boxscore_traditional' called for game_id '{game_id}'")
    result = fetch_boxscore_traditional_logic(game_id)
    return json.dumps(result, default=str)

@tool
def get_league_standings(season: str = CURRENT_SEASON) -> str:
    """
    Fetches the league standings (V3) for a specific season (Regular Season only). Returns JSON string.
    Args: season (str): Season identifier (e.g., "2023-24"). Defaults to current.
    Returns: str: JSON string containing standings data or {'error': ...}.
    """
    logger.debug(f"Tool 'get_league_standings' called for season '{season}'")
    return fetch_league_standings_logic(season=season)

@tool
def get_scoreboard(game_date: Optional[str] = None) -> str:
    """Fetches NBA scoreboard data for a specific date, including status, scores, and basic info.
    Args:
        game_date (str, optional): Date in YYYY-MM-DD format. Defaults to today if None.
    Returns:
        str: JSON string containing scoreboard data or {'error': ...}.
    """
    logger.debug(f"Tool 'get_scoreboard' called for date: {game_date or 'today'}")
    # The logic function handles date validation and returns a dict
    result_dict = fetch_scoreboard_data_logic(game_date=game_date)
    return format_response(data=result_dict) # format_response handles dict -> JSON string and errors

@tool
def get_playbyplay(game_id: str, start_period: int = 0, end_period: int = 0) -> str:
    """
    Fetches the play-by-play data (V3) for a specific game. Returns JSON string.
    Args:
        game_id (str): The 10-digit ID of the game.
        start_period (int): Optional starting period filter (0 for all). Defaults to 0.
        end_period (int): Optional ending period filter (0 for all). Defaults to 0.
    Returns: str: JSON string containing play-by-play actions or {'error': ...}.
    """
    logger.debug(f"Tool 'get_playbyplay' called for game_id '{game_id}', start '{start_period}', end '{end_period}'")
    return fetch_playbyplay_logic(game_id=game_id, start_period=start_period, end_period=end_period)

@tool
def get_draft_history(season_year: Optional[str] = None) -> str:
    """
    Fetches the NBA draft history, optionally filtered by year. Returns JSON string.
    Args: season_year (str, optional): Optional year filter (YYYY format). If None, fetches all history.
    Returns: str: JSON string containing draft picks or {'error': ...}.
    """
    logger.debug(f"Tool 'get_draft_history' called for year '{season_year or 'All'}'")
    return fetch_draft_history_logic(season_year=season_year)

@tool
def get_league_leaders(
    stat_category: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerMode36.per_game
) -> str:
    """
    Fetches league leaders for a specific statistical category. Returns JSON string.
    Args:
        stat_category (str): Statistical category (e.g., "PTS", "AST", "REB")
        season (str): Season identifier (e.g., "2023-24")
        season_type (str): Season type (e.g., "Regular Season", "Playoffs")
        per_mode (str): Mode of stats (e.g., "PerGame", "Totals")
    Returns: str: JSON string containing league leaders data
    """
    logger.debug(f"Tool get_league_leaders called for stat: {stat_category}, season: {season}")
    return fetch_league_leaders_logic(
        season=season,
        stat_category=stat_category,
        season_type=season_type,
        per_mode=per_mode
    )

@tool
def get_player_hustle_stats(
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> str:
    """
    Fetches players' hustle stats like deflections, loose balls recovered, screen assists etc.
    Args:
        season (str): Season identifier (e.g., "2023-24")
        season_type (str): Season type (e.g., "Regular Season", "Playoffs")
        per_mode (str): Mode of stats (e.g., "PerGame", "Totals")
    Returns:
        str: JSON string containing hustle statistics for all players:
            - Defensive stats (charges drawn, contested shots, deflections)
            - Loose ball recoveries (offensive/defensive)
            - Screen assists and points
            - Box outs (offensive/defensive)
    """
    logger.debug(f"Tool get_player_hustle_stats called for season {season}")
    return fetch_player_hustle_stats_logic(
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )

@tool
def get_player_profile(player_name: str, per_mode: str = PerModeDetailed.per_game) -> str:
    """
    Fetches a comprehensive player profile including career totals, season totals, highs, and next game info.
    Args:
        player_name (str): Full name of the player.
        per_mode (str): Stat mode ('PerGame', 'Totals', 'Per36', etc.). Defaults to 'PerGame'.
    Returns:
        str: JSON string containing detailed player profile data or {'error': ...}.
    """
    logger.debug(f"Tool get_player_profile called for '{player_name}', per_mode '{per_mode}'")
    valid_per_modes = [getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)]
    if per_mode not in valid_per_modes:
         logger.warning(f"Invalid per_mode '{per_mode}' in tool wrapper. Logic function should handle default.")
         # Let the logic function handle the default value assignment
    return fetch_player_profile_logic(player_name=player_name, per_mode=per_mode)

@tool
def get_top_performers(category: str = "PTS", season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular, top_n: int = 5) -> str:
    """
    Fetch top n performers for a stat category in a season.
    Returns JSON string with top performers.
    """
    logger.debug(f"Tool 'get_top_performers' called for category '{category}', season '{season}', type '{season_type}', top_n {top_n}")
    return fetch_top_performers_logic(category, season, season_type, top_n)

@tool
def get_top_teams(season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular, top_n: int = 5) -> str:
    """
    Fetch top performing teams by win percentage for a season.
    Returns JSON string with top teams.
    """
    logger.debug(f"Tool 'get_top_teams' called for season '{season}', season_type '{season_type}', top_n {top_n}")
    return fetch_top_teams_logic(season, season_type, top_n)


@tool
def get_player_insights(player_name: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Provides analysis and insights for a player's statistics over their career.
    Returns: str: JSON string containing analysis and insights or {'error': ...}.
    """
    logger.debug(f"Tool 'get_player_insights' called for '{player_name}', season '{season}', season_type '{season_type}'")
    return analyze_player_stats_logic(player_name, season, season_type)

@tool
def get_live_odds() -> str:
    """
    Fetches live betting odds for NBA games. Returns JSON string.
    """
    logger.debug("Tool 'get_live_odds' called")
    result = fetch_odds_data_logic()
    return format_response(data=result)

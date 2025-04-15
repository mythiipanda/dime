import logging
import json
from typing import Optional
from agno.tools import tool

# Import only the necessary constants for default values, use standard types in hints
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, PerMode36, LeagueID, PerMode48
)
from config import CURRENT_SEASON
from api_tools.utils import format_response


# Import logic functions from the specific api_tools modules
from api_tools.player_tools import (
    fetch_player_info_logic,
    fetch_player_gamelog_logic,
    fetch_player_career_stats_logic,
    fetch_player_awards_logic
)
from api_tools.team_tools import (
    fetch_team_info_and_roster_logic,
    # fetch_team_stats_logic, # Logic exists but no corresponding tool wrapper defined
)
from api_tools.game_tools import (
    fetch_boxscore_traditional_logic,
    fetch_playbyplay_logic,
    fetch_league_games_logic # Used by find_games
)
from api_tools.league_tools import (
    fetch_league_standings_logic,
    fetch_scoreboard_logic,
    fetch_draft_history_logic,
    fetch_league_leaders_logic
)
from api_tools.player_tracking import (
    fetch_player_clutch_stats_logic,
    fetch_player_passing_stats_logic,
    # Removed incorrect import comment
    fetch_player_shots_tracking_logic, # Correct function for shot tracking
    fetch_player_rebounding_stats_logic
)
from api_tools.team_tracking import (
    fetch_team_passing_stats_logic,
    fetch_team_shooting_stats_logic,
    fetch_team_rebounding_stats_logic
)


logger = logging.getLogger(__name__)

# --- Agno Tool Functions (Wrappers for Logic) ---

# Player Tools
@tool
def get_player_info(player_name: str) -> str: # Return type hint is now correct
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
    # Validation can be handled within the logic function or kept here if preferred
    valid_season_types = [st for st in dir(SeasonTypeAllStar) if not st.startswith('_') and isinstance(getattr(SeasonTypeAllStar, st), str)]
    if season_type not in valid_season_types:
        logger.warning(f"Invalid season_type '{season_type}' in tool wrapper. Logic function should handle default.")
        # Let logic handle default if invalid: season_type = SeasonTypeAllStar.regular
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
    # Validation can be handled within the logic function
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

# Player Tracking Tools
@tool
def get_player_clutch_stats(
    player_name: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular
    # Add other relevant params based on fetch_player_clutch_stats_logic signature if needed
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
    # Assuming fetch_player_clutch_stats_logic takes these params. Adjust if necessary.
    result = fetch_player_clutch_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type
        # Pass other params here if the logic function requires them
    )
    return json.dumps(result, default=str) # Serialize result

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
    # Logic function fetch_player_shots_tracking_logic expects only player_id
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
    team_identifier: str, # Changed from team_name for consistency
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game # Check if logic func uses this
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
    # Ensure logic function signature matches parameters passed
    return fetch_team_passing_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode  # Logic function accepts this
    )

@tool
def get_team_shooting_stats(
    team_identifier: str, # Changed from team_name for consistency
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game # Check if logic func uses this
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
    # Ensure logic function signature matches parameters passed
    return fetch_team_shooting_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode  # Logic function accepts this
    )

@tool
def get_team_rebounding_stats(
    team_identifier: str, # Changed from team_name for consistency
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game # Check if logic func uses this
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
    # Ensure logic function signature matches parameters passed
    return fetch_team_rebounding_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode  # Logic function accepts this
    )


# Game/League Tools
@tool
def find_games(
    player_or_team: str = 'T',
    player_id: Optional[int] = None,
    team_id: Optional[int] = None,
    season: Optional[str] = None, # Re-enabled based on logic function
    season_type: Optional[str] = None, # Re-enabled based on logic function
    league_id: Optional[str] = None, # Re-enabled based on logic function
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
    # Basic validation for required IDs
    if player_or_team == 'P' and player_id is None:
        return format_response(error="player_id is required when player_or_team='P'.")
    if player_or_team == 'T' and team_id is None:
        return format_response(error="team_id is required when player_or_team='T'.")

    # Call logic function with all parameters
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
    return json.dumps(result, default=str) # Serialize result

@tool
def get_league_standings(season: str = CURRENT_SEASON) -> str:
    """
    Fetches the league standings (V3) for a specific season (Regular Season only). Returns JSON string.
    Args: season (str): Season identifier (e.g., "2023-24"). Defaults to current.
    Returns: str: JSON string containing standings data or {'error': ...}.
    """
    logger.debug(f"Tool 'get_league_standings' called for season '{season}'")
    # Logic function handles default season type and league ID
    return fetch_league_standings_logic(season=season)

@tool
def get_scoreboard(game_date: str = None, day_offset: int = 0) -> str:
    """
    Fetches the scoreboard (V2) for a specific date. Returns JSON string.
    Args:
        game_date (str): Date string (YYYY-MM-DD). Defaults to today if None.
        day_offset (int): Offset from game_date (e.g., -1 for yesterday). Defaults to 0.
    Returns: str: JSON string containing scoreboard data or {'error': ...}.
    """
    logger.debug(f"Tool 'get_scoreboard' called for date '{game_date}', offset '{day_offset}'")
    # Logic function handles default date if game_date is None
    return fetch_scoreboard_logic(game_date=game_date, day_offset=day_offset)

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
def get_draft_history(season_year: Optional[str] = None) -> str: # Made season_year optional explicitly
    """
    Fetches the NBA draft history, optionally filtered by year. Returns JSON string.
    Args: season_year (str, optional): Optional year filter (YYYY format). If None, fetches all history.
    Returns: str: JSON string containing draft picks or {'error': ...}.
    """
    logger.debug(f"Tool 'get_draft_history' called for year '{season_year or 'All'}'")
    # Logic function handles default league ID
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

import logging
import json
import time
from agno.tools import tool
# Import only the necessary constants for default values, use standard types in hints
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, PerMode36, LeagueID, PerMode48

# Import logic functions from the new modules
from .api_tools.player_tools import (
    fetch_player_info_logic,
    fetch_player_gamelog_logic,
    fetch_player_career_stats_logic,
    fetch_player_awards_logic, # Import new logic function
    _find_player_id
)
from .api_tools.team_tools import (
    fetch_team_info_and_roster_logic,
    _find_team_id,
    # CURRENT_SEASON # Removed: Import from config
)
from .config import CURRENT_SEASON # Import from config
from .api_tools.game_tools import (
    fetch_league_games_logic,
    fetch_boxscore_traditional_logic,
    fetch_playbyplay_logic # Import new logic function
)
# Import from new league_tools module
from .api_tools.league_tools import fetch_league_standings_logic, fetch_scoreboard_logic, fetch_draft_history_logic, fetch_league_leaders_logic

logger = logging.getLogger(__name__)

# --- Agno Tool Functions (Decorated Wrappers) ---

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
        logger.warning(f"Invalid season_type '{season_type}' in tool wrapper. Using default '{SeasonTypeAllStar.regular}'.")
        season_type = SeasonTypeAllStar.regular
    return fetch_player_gamelog_logic(player_name, season, season_type)

@tool
def get_team_info_and_roster(team_identifier: str, season: str = CURRENT_SEASON) -> str:
    """
    Fetches team information, ranks, roster, and coaches. Returns JSON string.
    Args:
        team_identifier (str): Team name or abbreviation (e.g., "LAL").
        season (str): Season identifier (e.g., "2023-24"). Defaults to current.
    Returns: str: JSON string containing team data or {'error': ...}.
    """
    logger.debug(f"Tool 'get_team_info_and_roster' called for '{team_identifier}', season '{season}'")
    return fetch_team_info_and_roster_logic(team_identifier, season)

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
         logger.warning(f"Invalid per_mode36 '{per_mode36}' in tool wrapper. Logic function will use default.")
    return fetch_player_career_stats_logic(player_name, per_mode36)

@tool
# Simplified signature further: Removed season, season_type, league_id
def find_games(
    player_or_team: str = 'T',
    player_id: int = None, # Reverted type hint
    team_id: int = None, # Reverted type hint
    date_from: str = None, # Reverted type hint
    date_to: str = None # Reverted type hint
) -> str:
    """
    Finds games based on Player/Team ID and optional date range. Returns JSON string.
    You MUST provide either player_id (if player_or_team='P') or team_id (if player_or_team='T').
    Filtering by season, season_type, league_id is temporarily disabled.

    Args:
        player_or_team (str): Search by 'P' (Player) or 'T' (Team). Defaults to 'T'.
        player_id (int): Required if player_or_team='P'. Omit or pass None otherwise.
        team_id (int): Required if player_or_team='T'. Omit or pass None otherwise.
        date_from (str): Optional start date filter (MM/DD/YYYY).
        date_to (str): Optional end date filter (MM/DD/YYYY).

    Returns:
        str: JSON string containing a list of found games or {'error': ...}.
    """
    logger.debug(f"Tool 'find_games' called with params: player_or_team={player_or_team}, player_id={player_id}, team_id={team_id}, date_from={date_from}, date_to={date_to}")
    # Basic validation for required IDs
    if player_or_team == 'P' and player_id is None:
        return json.dumps({"error": "player_id is required when player_or_team='P'."})
    if player_or_team == 'T' and team_id is None:
        return json.dumps({"error": "team_id is required when player_or_team='T'."})

    # Call logic function, passing None for the removed parameters
    return fetch_league_games_logic(
        player_or_team_abbreviation=player_or_team,
        player_id_nullable=player_id,
        team_id_nullable=team_id,
        season_nullable=None, # Pass None for removed params
        season_type_nullable=None, # Pass None
        league_id_nullable=None, # Pass None
        date_from_nullable=date_from,
        date_to_nullable=date_to
    )

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
def get_boxscore_traditional(game_id: str) -> str:
    """
    Fetches the traditional box score (V3) for a specific game. Returns JSON string.
    Args: game_id (str): The 10-digit ID of the game.
    Returns: str: JSON string containing player and team stats or {'error': ...}.
    """
    logger.debug(f"Tool 'get_boxscore_traditional' called for game_id '{game_id}'")
    return fetch_boxscore_traditional_logic(game_id)

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
def get_draft_history(season_year: str = None) -> str:
    """
    Fetches the NBA draft history, optionally filtered by year. Returns JSON string.
    Args: season_year (str): Optional year filter (YYYY format). If None, fetches all history.
    Returns: str: JSON string containing draft picks or {'error': ...}.
    """
    logger.debug(f"Tool 'get_draft_history' called for year '{season_year or 'All'}'")
    # Logic function handles default league ID
    return fetch_draft_history_logic(season_year=season_year)

@tool
def get_league_leaders(
    stat_category: str,
    season: str = CURRENT_SEASON,
    season_type_all_star: str = SeasonTypeAllStar.regular,
    per_mode48: str = PerMode48.per_game
) -> str:
    """
    Fetches league leaders for a specific stat category and season. Returns JSON string.
    Args:
        stat_category (str): Stat category abbreviation (e.g., 'PTS', 'REB', 'AST', 'STL', 'BLK', 'FG_PCT', 'FT_PCT', 'FG3_PCT', 'EFF').
        season (str): Season identifier (e.g., "2023-24"). Defaults to current.
        season_type_all_star (str): 'Regular Season', 'Playoffs', etc. Defaults to Regular Season.
        per_mode48 (str): Stat mode ('PerGame', 'Totals', 'Per48', etc.). Defaults to 'PerGame'.
    Returns: str: JSON string containing league leaders or {'error': ...}.
    """
    logger.debug(f"Tool 'get_league_leaders' called for stat '{stat_category}', season '{season}', type '{season_type_all_star}', mode '{per_mode48}'")
    # Logic function handles default scope and league ID
    return fetch_league_leaders_logic(
        stat_category=stat_category,
        season=season,
        season_type_all_star=season_type_all_star,
        per_mode48=per_mode48
    )


# --- Example Usage Block (for direct execution testing of logic) ---
if __name__ == "__main__":
    # This block now tests the imported logic functions directly
    logging.basicConfig(level=logging.DEBUG)
    print("\n--- Running Tool Logic Examples (Directly from tools.py) ---")

    # ... (previous tests remain here) ...
    print("\n[Test Case 1: LeBron James Info]")
    start_time = time.time()
    lebron_info_str = fetch_player_info_logic("LeBron James")
    lebron_info = json.loads(lebron_info_str)
    end_time = time.time()
    print(f"Result (took {end_time - start_time:.2f}s):")
    # print(json.dumps(lebron_info, indent=2, default=str)) # Commented out for brevity
    assert 'error' not in lebron_info

    print("\n[Test Case 5: LeBron James Game Log (2023-24)]")
    start_time = time.time()
    lebron_log_str = fetch_player_gamelog_logic("LeBron James", "2023-24")
    lebron_log = json.loads(lebron_log_str)
    end_time = time.time()
    print(f"Result (took {end_time - start_time:.2f}s):")
    if 'gamelog' in lebron_log: print(f"  Games Found: {len(lebron_log['gamelog'])}")
    else: print(json.dumps(lebron_log, indent=2, default=str))
    assert 'error' not in lebron_log

    print("\n[Test Case 8: Lakers Info & Roster (Default Season)]")
    start_time = time.time()
    lakers_info_str = fetch_team_info_and_roster_logic("LAL")
    lakers_info = json.loads(lakers_info_str)
    end_time = time.time()
    print(f"Result (took {end_time - start_time:.2f}s):")
    if 'error' not in lakers_info: print(f"  Roster Size: {len(lakers_info.get('roster', []))}")
    else: print(json.dumps(lakers_info, indent=2, default=str))
    assert 'error' not in lakers_info

    print("\n[Test Case 11: LeBron James Career Stats (PerGame)]")
    start_time = time.time()
    lebron_career_str = fetch_player_career_stats_logic("LeBron James", PerMode36.per_game)
    lebron_career = json.loads(lebron_career_str)
    end_time = time.time()
    print(f"Result (took {end_time - start_time:.2f}s):")
    if 'error' not in lebron_career: print(f"  Seasons Found: {len(lebron_career.get('season_totals_regular_season', []))}")
    else: print(json.dumps(lebron_career, indent=2, default=str))
    assert 'error' not in lebron_career

    print("\n[Test Case 15: Find Lakers Games (No Filters)]")
    try:
        from .api_tools.team_tools import _find_team_id as find_team_id_helper
        lakers_id_test = find_team_id_helper("LAL")
        if lakers_id_test:
            start_time = time.time()
            # Call logic directly without filters that were removed from tool signature
            lakers_games_str = fetch_league_games_logic(team_id_nullable=lakers_id_test, player_or_team_abbreviation='T')
            lakers_games = json.loads(lakers_games_str)
            end_time = time.time()
            print(f"Result (took {end_time - start_time:.2f}s):")
            if 'games' in lakers_games: print(f"  Games Found: {len(lakers_games['games'])}")
            else: print(json.dumps(lakers_games, indent=2, default=str))
            assert 'error' not in lakers_games
        else:
            print("Skipping Lakers games test - could not find team ID.")
    except ImportError:
         print("Skipping Lakers games test - could not import helper.")


    print("\n--- Tool Logic Examples Complete ---")
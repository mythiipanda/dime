import logging
import json
import time
from agno.tools import tool
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed

# Import logic functions from the new modules
from api_tools.player_tools import (
    fetch_player_info_logic,
    fetch_player_gamelog_logic,
    fetch_player_career_stats_logic
)
from api_tools.team_tools import (
    fetch_team_info_and_roster_logic,
    CURRENT_SEASON
)

logger = logging.getLogger(__name__)

# --- Agno Tool Functions (Decorated Wrappers) ---

@tool
def get_player_info(player_name: str) -> str: # Changed return type hint to str
    """
    Fetches basic player information and headline stats. Returns JSON string.
    Args: player_name (str): Full name of the player.
    Returns: str: JSON string containing player info/stats or {'error': ...}.
    """
    logger.debug(f"Tool 'get_player_info' called for '{player_name}'")
    return fetch_player_info_logic(player_name)

@tool
def get_player_gamelog(player_name: str, season: str, season_type: str = SeasonTypeAllStar.regular) -> str: # Changed return type hint to str
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
def get_team_info_and_roster(team_identifier: str, season: str = CURRENT_SEASON) -> str: # Changed return type hint to str
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
def get_player_career_stats(player_name: str, per_mode: str = PerModeDetailed.per_game) -> str: # Changed return type hint to str
    """
    Fetches player career statistics (Regular Season). Returns JSON string.
    Args:
        player_name (str): Full name of the player.
        per_mode (str): Stat mode ('PerGame', 'Totals', etc.). Defaults to 'PerGame'.
    Returns: str: JSON string containing career stats data or {'error': ...}.
    """
    logger.debug(f"Tool 'get_player_career_stats' called for '{player_name}', per_mode '{per_mode}'")
    # Corrected PerMode Validation: Check against actual values
    valid_per_modes = [getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)]
    if per_mode not in valid_per_modes:
         logger.warning(f"Invalid per_mode '{per_mode}' in tool wrapper. Using default '{PerModeDetailed.per_game}'.")
         per_mode = PerModeDetailed.per_game
         # Don't return error here, let the logic function handle default or potentially error if needed
    return fetch_player_career_stats_logic(player_name, per_mode)


# --- Example Usage Block (for direct execution testing of logic) ---
if __name__ == "__main__":
    # This block now tests the imported logic functions directly
    # It helps verify the core functionality without involving the @tool decorator issues

    print("\n--- Running Tool Logic Examples (Directly from tools.py) ---")

    # --- Player Info ---
    print("\n[Test Case 1: LeBron James Info]")
    start_time = time.time()
    lebron_info_str = fetch_player_info_logic("LeBron James") # Returns JSON string
    lebron_info = json.loads(lebron_info_str) # Parse JSON for assertion
    end_time = time.time()
    print(f"Result (took {end_time - start_time:.2f}s):")
    print(json.dumps(lebron_info, indent=2, default=str))
    assert 'error' not in lebron_info

    # --- Player Gamelog ---
    print("\n[Test Case 5: LeBron James Game Log (2023-24)]")
    start_time = time.time()
    lebron_log_str = fetch_player_gamelog_logic("LeBron James", "2023-24") # Returns JSON string
    lebron_log = json.loads(lebron_log_str) # Parse JSON
    end_time = time.time()
    print(f"Result (took {end_time - start_time:.2f}s):")
    if 'gamelog' in lebron_log: print(f"  Games Found: {len(lebron_log['gamelog'])}")
    else: print(json.dumps(lebron_log, indent=2, default=str))
    assert 'error' not in lebron_log

    # --- Team Info & Roster ---
    print("\n[Test Case 8: Lakers Info & Roster (Default Season)]")
    start_time = time.time()
    lakers_info_str = fetch_team_info_and_roster_logic("LAL") # Returns JSON string
    lakers_info = json.loads(lakers_info_str) # Parse JSON
    end_time = time.time()
    print(f"Result (took {end_time - start_time:.2f}s):")
    if 'error' not in lakers_info: print(f"  Roster Size: {len(lakers_info.get('roster', []))}")
    else: print(json.dumps(lakers_info, indent=2, default=str))
    assert 'error' not in lakers_info

    # --- Player Career Stats ---
    print("\n[Test Case 11: LeBron James Career Stats (PerGame)]")
    start_time = time.time()
    lebron_career_str = fetch_player_career_stats_logic("LeBron James", PerModeDetailed.per_game) # Returns JSON string
    lebron_career = json.loads(lebron_career_str) # Parse JSON
    end_time = time.time()
    print(f"Result (took {end_time - start_time:.2f}s):")
    if 'error' not in lebron_career: print(f"  Seasons Found: {len(lebron_career.get('season_totals_regular_season', []))}")
    else: print(json.dumps(lebron_career, indent=2, default=str))
    assert 'error' not in lebron_career

    print("\n--- Tool Logic Examples Complete ---")
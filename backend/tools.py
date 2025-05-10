import logging
import json
from typing import Optional, List
from agno.tools import tool
# Caching is now handled by @lru_cache in the api_tools logic functions.

# Import only the necessary constants for default values, use standard types in hints
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, PerMode36, LeagueID, PerMode48, Scope, RunType,
    PerModeSimple, PlayerOrTeamAbbreviation
    # MeasureTypeDetailedDefense removed as it's not directly used for default in get_team_stats wrapper
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
    fetch_team_stats_logic,
)
from backend.api_tools.game_tools import (
    fetch_boxscore_traditional_logic,
    fetch_playbyplay_logic,
    fetch_league_games_logic,
    fetch_shotchart_logic, # Renamed in wrapper to get_game_shotchart
    fetch_boxscore_advanced_logic,
    fetch_boxscore_four_factors_logic,
    fetch_boxscore_usage_logic,
    fetch_boxscore_defensive_logic,
    fetch_win_probability_logic
)
from backend.api_tools.league_tools import (
    fetch_league_standings_logic,
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
from backend.api_tools.odds_tools import fetch_odds_data_logic
from backend.api_tools.analyze import analyze_player_stats_logic
from backend.api_tools.trending_tools import fetch_top_performers_logic
from backend.api_tools.trending_team_tools import fetch_top_teams_logic
from backend.api_tools.matchup_tools import fetch_league_season_matchups_logic, fetch_matchups_rollup_logic
from backend.api_tools.synergy_tools import fetch_synergy_play_types_logic

logger = logging.getLogger(__name__)

# --- Agno Tool Functions (Wrappers for Logic) ---

# Player Tools
@tool
def get_player_info(player_name: str) -> str:
    """
    Fetches basic player information, including biographical details and headline career statistics.

    Args:
        player_name (str): The full name of the player (e.g., "LeBron James").

    Returns:
        str: JSON string containing player information and headline stats.
             Expected structure:
             {
                 "player_info": {
                     "PERSON_ID": int, "FIRST_NAME": str, "LAST_NAME": str, "DISPLAY_FIRST_LAST": str,
                     "BIRTHDATE": str (YYYY-MM-DDTHH:MM:SS), "SCHOOL": str, "COUNTRY": str, "HEIGHT": str,
                     "WEIGHT": str, "SEASON_EXP": int, "JERSEY": str, "POSITION": str,
                     "ROSTERSTATUS": str, "TEAM_ID": int, "TEAM_NAME": str, "TEAM_ABBREVIATION": str,
                     "FROM_YEAR": int, "TO_YEAR": int, ...
                 },
                 "headline_stats": {
                     "PLAYER_ID": int, "PLAYER_NAME": str, "TimeFrame": str (e.g., "2023-24"),
                     "PTS": float, "AST": float, "REB": float, "PIE": float, ...
                 }
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_player_info' called for '{player_name}'")
    result = fetch_player_info_logic(player_name)
    return result

@tool
def get_player_gamelog(player_name: str, season: str, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches the game-by-game statistics for a specific player in a given season and season type.

    Args:
        player_name (str): The full name of the player (e.g., "Jayson Tatum").
        season (str): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
        season_type (str, optional): The type of season. Valid values: "Regular Season", "Playoffs", "Pre Season", "All Star".
                                     Defaults to "Regular Season".

    Returns:
        str: JSON string containing a list of game log entries.
             Expected structure:
             {
                 "player_name": str,
                 "player_id": int,
                 "season": str,
                 "season_type": str,
                 "gamelog": [
                     {
                         "GAME_DATE": str (e.g., "Apr 11, 2025"), "MATCHUP": str (e.g., "BOS vs. CHA"), "WL": str ("W" or "L"),
                         "MIN": int, "FGM": int, "FGA": int, "FG_PCT": float, "FG3M": int, "FG3A": int, "FG3_PCT": float,
                         "FTM": int, "FTA": int, "FT_PCT": float, "OREB": int, "DREB": int, "REB": int, "AST": int,
                         "STL": int, "BLK": int, "TOV": int, "PF": int, "PTS": int, "PLUS_MINUS": int, ...
                     }, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_player_gamelog' called for '{player_name}', season '{season}', type '{season_type}'")
    result = fetch_player_gamelog_logic(player_name, season, season_type)
    return result

@tool
def get_player_career_stats(player_name: str, per_mode: str = PerMode36.per_game) -> str:
    """
    Fetches player career statistics, including Regular Season and Playoffs if available, aggregated by season.
    The tool returns all available career phases; filter for "Playoffs" data from the results if needed.
    Do NOT try to pass a 'season_type' argument to this tool.

    Args:
        player_name (str): The full name of the player (e.g., "Kevin Durant").
        per_mode (str, optional): The statistical mode. Valid values: "PerGame", "Totals", "Per36".
                                  Defaults to "PerGame".

    Returns:
        str: JSON string containing career statistics data, broken down by season for different phases.
             Expected structure:
             {
                 "player_name": str,
                 "player_id": int,
                 "per_mode_requested": str,
                 "data_retrieved_mode": str,
                 "season_totals_regular_season": [ { "SEASON_ID": str, ... } ],
                 "career_totals_regular_season": { ... },
                 "season_totals_post_season": [ { "SEASON_ID": str, ... } ], // Present if playoff data exists
                 "career_totals_post_season": { ... } // Present if playoff data exists
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_player_career_stats' called for '{player_name}', per_mode '{per_mode}'")
    result = fetch_player_career_stats_logic(player_name, per_mode)
    return result

@tool
def get_player_awards(player_name: str) -> str:
    """
    Fetches a list of awards won by a specific player throughout their career.

    Args:
        player_name (str): The full name of the player (e.g., "Michael Jordan").

    Returns:
        str: JSON string containing a list of awards.
             Expected structure:
             {
                 "player_name": str,
                 "player_id": int,
                 "awards": [
                     {
                         "DESCRIPTION": str (e.g., "All-Defensive Team"), "SEASON": str (e.g., "1987-88"),
                         "TEAM": str, "ALL_NBA_TEAM_NUMBER": str, ...
                     }, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_player_awards' called for '{player_name}'")
    result = fetch_player_awards_logic(player_name)
    return result

@tool
def get_player_shotchart(
    player_name: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    """
    Fetches detailed shot chart data for a player for a specific season and season type.
    This includes shot locations, outcomes, types, and shooting percentages by zone,
    along with a path to a generated visualization if successful.

    Args:
        player_name (str): The full name of the player (e.g., "Damian Lillard").
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
                                Defaults to the current season.
        season_type (str, optional): The type of season. Valid values: "Regular Season", "Playoffs".
                                     Defaults to "Regular Season".

    Returns:
        str: JSON string containing shot chart data and visualization path.
             Expected structure:
             {
                 "player_name": str,
                 "player_id": int,
                 "season": str,
                 "season_type": str,
                 "overall_stats": {"total_shots": int, "made_shots": int, "field_goal_percentage": float},
                 "zone_breakdown": {
                     "Zone Name (e.g., Mid-Range)": {"attempts": int, "made": int, "percentage": float}, ...
                 },
                 "shot_data_summary": [
                     {"SHOT_ZONE_BASIC": str, "SHOT_ZONE_AREA": str, "FGM": int, "FGA": int, "FG_PCT": float}, ...
                 ],
                 "visualization_path": Optional[str], // Path to the generated shot chart image, or null
                 "message": Optional[str] // e.g., "No shot data found..."
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_player_shotchart' called for {player_name}, season {season}, type {season_type}")
    result = fetch_player_shotchart_logic(
        player_name=player_name,
        season=season,
        season_type=season_type
    )
    return result

@tool
def get_player_defense_stats(
    player_name: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> str:
    """
    Fetches detailed defensive statistics for a player, including opponent shooting percentages when guarded.

    Args:
        player_name (str): The full name of the player (e.g., "Marcus Smart").
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2022-23").
                                Defaults to the current season.
        season_type (str, optional): The type of season. Valid values: "Regular Season", "Playoffs".
                                     Defaults to "Regular Season".
        per_mode (str, optional): The statistical mode. Valid values from PerModeDetailed (e.g., "PerGame", "Totals").
                                  Defaults to "PerGame".

    Returns:
        str: JSON string containing defensive statistics.
             Expected structure:
             {
                 "player_name": str,
                 "player_id": int,
                 "parameters": { "season": str, "season_type": str, "per_mode_requested": str, ... },
                 "summary": {
                     "games_played": int,
                     "overall_defense": {"field_goal_percentage_allowed": float, ...},
                     "three_point_defense": {"frequency": float, ...}, ...
                 },
                 "detailed_defense_stats": [
                     {"DEFENSE_CATEGORY": str, "GP": int, "FREQ": float, "DFGM": float, ...}, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_player_defense_stats' called for {player_name}, season {season}, per_mode {per_mode}")
    result = fetch_player_defense_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    return result

# Player Tracking Tools
@tool
def get_player_clutch_stats(
    player_name: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    measure_type: str = "Base",
    per_mode: str = "Totals"
) -> str:
    """
    Fetches player statistics in clutch situations (e.g., last 5 minutes of a close game).

    Args:
        player_name (str): The full name of the player (e.g., "DeMar DeRozan").
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24"). Defaults to current season.
        season_type (str, optional): The type of season. Valid values: "Regular Season", "Playoffs".
                                     Defaults to "Regular Season".
        measure_type (str, optional): The category of stats. Valid: "Base", "Advanced", "Misc", "Four Factors", "Scoring", "Opponent", "Usage".
                                      Defaults to "Base".
        per_mode (str, optional): The statistical mode. Valid values from PerModeDetailed (e.g., "Totals", "PerGame").
                                  Defaults to "Totals".

    Returns:
        str: JSON string containing clutch statistics.
             Expected structure:
             {
                 "player_name": str,
                 "player_id": int,
                 "parameters": { "season": str, "season_type": str, "measure_type": str, "per_mode": str, ... },
                 "clutch_stats": [
                     {"GROUP_VALUE": str (e.g., season), "GP": int, "W": int, "L": int, "W_PCT": float, "MIN": float, "PTS": float, ...}, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_player_clutch_stats' called for '{player_name}', season '{season}', type '{season_type}', measure '{measure_type}', mode '{per_mode}'")
    result = fetch_player_clutch_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode
    )
    return result

@tool
def get_player_passing_stats(
    player_name: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game
) -> str:
    """
    Fetches player passing tracking statistics, including passes made and received.

    Args:
        player_name (str): The full name of the player (e.g., "Nikola Jokic").
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24"). Defaults to current season.
        season_type (str, optional): The type of season. Valid values: "Regular Season", "Playoffs".
                                     Defaults to "Regular Season".
        per_mode (str, optional): The statistical mode. Valid values: "PerGame", "Totals".
                                  Defaults to "PerGame".

    Returns:
        str: JSON string containing player passing statistics.
             Expected structure:
             {
                 "player_name": str,
                 "player_id": int,
                 "parameters": { "season": str, "season_type": str, "per_mode": str },
                 "passes_made": [
                     {"PASS_TO": str, "FREQUENCY": float, "PASS": float, "AST": float, "FGM": float, ...}, ...
                 ],
                 "passes_received": [
                     {"PASS_FROM": str, "FREQUENCY": float, "PASS": float, "AST": float, "FGM": float, ...}, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_player_passing_stats' called for {player_name}, season {season}, type {season_type}, mode {per_mode}")
    result = fetch_player_passing_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    return result

@tool
def get_player_rebounding_stats(
    player_name: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game
) -> str:
    """
    Fetches player rebounding tracking statistics, categorized by shot type, contest, and distance.

    Args:
        player_name (str): The full name of the player (e.g., "Domantas Sabonis").
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24"). Defaults to current season.
        season_type (str, optional): The type of season. Valid values: "Regular Season", "Playoffs".
                                     Defaults to "Regular Season".
        per_mode (str, optional): The statistical mode. Valid values: "PerGame", "Totals".
                                  Defaults to "PerGame".

    Returns:
        str: JSON string containing player rebounding statistics.
             Expected structure:
             {
                 "player_name": str,
                 "player_id": int,
                 "parameters": { "season": str, "season_type": str, "per_mode": str },
                 "overall": {"OREB": float, "DREB": float, "REB": float, "C_REB_PCT": float, ...},
                 "by_shot_type": [ {"SHOT_TYPE_DESCR": str, "OREB": float, "DREB": float, ...}, ... ],
                 "by_contest": [ {"CONTEST_TYPE": str, "OREB": float, "DREB": float, ...}, ... ],
                 "by_shot_distance": [ {"SHOT_DIST_RANGE": str, "OREB": float, "DREB": float, ...}, ... ],
                 "by_rebound_distance": [ {"REB_DIST_RANGE": str, "OREB": float, "DREB": float, ...}, ... ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_player_rebounding_stats' called for {player_name}, season {season}, type {season_type}, mode {per_mode}")
    result = fetch_player_rebounding_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    return result

@tool
def get_player_shots_tracking(player_name: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches detailed player shooting statistics, categorized by various factors like shot clock, dribbles, and defender distance.

    Args:
        player_name (str): The full name of the NBA player (e.g., "LeBron James").
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
                                Defaults to the current season.
        season_type (str, optional): The type of season. Valid values: "Regular Season", "Playoffs".
                                     Defaults to "Regular Season".

    Returns:
        str: JSON string containing detailed shot tracking statistics.
             Expected structure:
             {
                 "player_id": int,
                 "player_name": str,
                 "team_id": int,
                 "parameters": { "season": str, "season_type": str, "opponent_team_id": int, ... },
                 "general_shooting": [ {"SHOT_TYPE": str, "FGA_FREQUENCY": float, "FGM": int, "FGA": int, "FG_PCT": float, ...}, ... ],
                 "by_shot_clock": [ {"SHOT_CLOCK_RANGE": str, "FGA_FREQUENCY": float, ...}, ... ],
                 "by_dribble_count": [ {"DRIBBLE_RANGE": str, "FGA_FREQUENCY": float, ...}, ... ],
                 "by_touch_time": [ {"TOUCH_TIME_RANGE": str, "FGA_FREQUENCY": float, ...}, ... ],
                 "by_defender_distance": [ {"CLOSE_DEF_DIST_RANGE": str, "FGA_FREQUENCY": float, ...}, ... ],
                 "by_defender_distance_10ft_plus": [ {"CLOSE_DEF_DIST_RANGE": str, "FGA_FREQUENCY": float, ...}, ... ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_player_shots_tracking' called for player_name '{player_name}', season '{season}', type '{season_type}'")
    result = fetch_player_shots_tracking_logic(player_name=player_name, season=season, season_type=season_type)
    return result

# Team Tools
@tool
def get_team_info_and_roster(team_identifier: str, season: str = CURRENT_SEASON) -> str:
    """
    Fetches comprehensive team information including basic details, conference/division ranks,
    historical performance, current season roster, and coaching staff.

    Args:
        team_identifier (str): The team's name (e.g., "Los Angeles Lakers"), abbreviation (e.g., "LAL"), or ID (e.g., 1610612747).
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
                                Defaults to the current season.

    Returns:
        str: JSON string containing detailed team data.
             Expected structure:
             {
                 "team_id": int,
                 "team_name": str,
                 "season": str,
                 "info": { "TEAM_CITY": str, "TEAM_CONFERENCE": str, "TEAM_DIVISION": str, "W": int, "L": int, "PCT": float, ... },
                 "ranks": { "CONF_RANK": int, "DIV_RANK": int, ... },
                 "roster": [ {"PLAYER_ID": int, "PLAYER_NAME": str, "POSITION": str, "JERSEY": str, ...}, ... ],
                 "coaches": [ {"PERSON_ID": int, "COACH_NAME": str, "COACH_TYPE": str, ...}, ... ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_team_info_and_roster' called for '{team_identifier}', season '{season}'")
    result = fetch_team_info_and_roster_logic(team_identifier, season)
    return result

@tool
def get_team_stats(
    team_identifier: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    measure_type: str = "Base", # Defaulting to "Base" as it's a common one.
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches comprehensive team statistics for a given season, with various filtering options.

    Args:
        team_identifier (str): The team's name, abbreviation, or ID (e.g., "GSW").
        season (str, optional): The NBA season in YYYY-YY format (e.g., "2023-24"). Defaults to current season.
        season_type (str, optional): The type of season. Valid values: "Regular Season", "Playoffs", "Pre Season".
                                     Defaults to "Regular Season".
        per_mode (str, optional): The statistical mode. Valid values from PerModeDetailed (e.g., "PerGame", "Totals").
                                  Defaults to "PerGame".
        measure_type (str, optional): The category of stats. Valid: "Base", "Advanced", "Misc", "Four Factors", "Scoring", "Opponent", "Usage".
                                      Defaults to "Base".
        opponent_team_id (int, optional): Filter stats against a specific opponent team ID. Defaults to 0 (all opponents).
        date_from (str, optional): Start date for filtering games (YYYY-MM-DD). Defaults to None.
        date_to (str, optional): End date for filtering games (YYYY-MM-DD). Defaults to None.
        league_id (str, optional): The league ID. Valid: "00" (NBA), "10" (WNBA), "20" (G-League).
                                   Defaults to "00" (NBA).

    Returns:
        str: JSON string containing team statistics.
             Expected structure:
             {
                 "team_id": int,
                 "team_name": str,
                 "parameters": { "season": str, "season_type": str, "per_mode": str, "measure_type": str, ... },
                 "current_stats": { // Stats for the specified season and filters
                     "GP": int, "W": int, "L": int, "W_PCT": float, "MIN": float,
                     // Fields vary based on measure_type (e.g., FGM, FGA for "Base"; OFF_RATING for "Advanced")
                     ...
                 },
                 "historical_stats": [ // May be present if current_stats fails and fallback occurs
                     {"TEAM_ID": int, "YEAR": str, "GP": int, "WINS": int, ...}, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_team_stats' called for '{team_identifier}', season '{season}', measure '{measure_type}'")
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
    return result

# Team Tracking Tools
@tool
def get_team_passing_stats(
    team_identifier: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game
) -> str:
    """
    Fetches team passing tracking statistics, detailing passes made and received between players.

    Args:
        team_identifier (str): The team's name, abbreviation, or ID (e.g., "DEN" for Denver Nuggets).
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
                                Defaults to the current season.
        season_type (str, optional): The type of season. Valid values: "Regular Season", "Playoffs".
                                     Defaults to "Regular Season".
        per_mode (str, optional): The statistical mode. Valid values: "PerGame", "Totals".
                                  Defaults to "PerGame".

    Returns:
        str: JSON string containing team passing statistics.
             Expected structure:
             {
                 "team_name": str,
                 "team_id": int,
                 "season": str,
                 "season_type": str,
                 "parameters": {"per_mode": str},
                 "passes_made": [
                     {"PASS_FROM": str, "PASS_TEAMMATE_PLAYER_ID": int, "FREQUENCY": float, "PASS": float, "AST": float, ...}, ...
                 ],
                 "passes_received": [
                     {"PASS_TO": str, "PASS_TEAMMATE_PLAYER_ID": int, "FREQUENCY": float, "PASS": float, "AST": float, ...}, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_team_passing_stats' called for {team_identifier}, season {season}, mode {per_mode}")
    result = fetch_team_passing_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    return result

@tool
def get_team_shooting_stats(
    team_identifier: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game
) -> str:
    """
    Fetches team shooting tracking statistics, categorized by various factors like shot clock, dribbles, and defender distance.

    Args:
        team_identifier (str): The team's name, abbreviation, or ID (e.g., "GSW").
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
                                Defaults to the current season.
        season_type (str, optional): The type of season. Valid values: "Regular Season", "Playoffs", "Pre Season".
                                     Defaults to "Regular Season".
        per_mode (str, optional): The statistical mode. Valid values: "PerGame", "Totals".
                                  Defaults to "PerGame".

    Returns:
        str: JSON string containing team shooting statistics.
             Expected structure:
             {
                 "team_id": int,
                 "team_name": str,
                 "season": str,
                 "season_type": str,
                 "parameters": { "per_mode": str, "opponent_team_id": int, ... },
                 "overall_shooting": { "SHOT_TYPE": "Totals", "FGM": float, "FGA": float, "FG_PCT": float, ... },
                 "general_shooting_splits": [ {"SHOT_TYPE": str, "FGA_FREQUENCY": float, "FGM": float, ...}, ... ],
                 "by_shot_clock": [ {"SHOT_CLOCK_RANGE": str, "FGA_FREQUENCY": float, ...}, ... ],
                 "by_dribble": [ {"DRIBBLE_RANGE": str, "FGA_FREQUENCY": float, ...}, ... ],
                 "by_defender_distance": [ {"CLOSE_DEF_DIST_RANGE": str, "FGA_FREQUENCY": float, ...}, ... ],
                 "by_touch_time": [ {"TOUCH_TIME_RANGE": str, "FGA_FREQUENCY": float, ...}, ... ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_team_shooting_stats' called for {team_identifier}, season {season}, mode {per_mode}")
    result = fetch_team_shooting_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    return result

@tool
def get_team_rebounding_stats(
    team_identifier: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game
) -> str:
    """
    Fetches team rebounding tracking statistics, categorized by shot type, contest, and distance.

    Args:
        team_identifier (str): The team's name, abbreviation, or ID (e.g., "BOS").
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
                                Defaults to the current season.
        season_type (str, optional): The type of season. Valid values: "Regular Season", "Playoffs".
                                     Defaults to "Regular Season".
        per_mode (str, optional): The statistical mode. Valid values: "PerGame", "Totals".
                                  Defaults to "PerGame".

    Returns:
        str: JSON string containing team rebounding statistics.
             Expected structure:
             {
                 "team_id": int,
                 "team_name": str,
                 "season": str,
                 "season_type": str,
                 "parameters": { "per_mode": str, "opponent_team_id": int, ... },
                 "overall": {"OREB": float, "DREB": float, "REB": float, "C_REB_PCT": float, ...},
                 "by_shot_type": [ {"SHOT_TYPE_DESCR": str, "OREB": float, "DREB": float, ...}, ... ],
                 "by_contest": [ {"CONTEST_TYPE": str, "OREB": float, "DREB": float, ...}, ... ],
                 "by_shot_distance": [ {"SHOT_DIST_RANGE": str, "OREB": float, "DREB": float, ...}, ... ],
                 "by_rebound_distance": [ {"REB_DIST_RANGE": str, "OREB": float, "DREB": float, ...}, ... ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_team_rebounding_stats' called for {team_identifier}, season {season}, mode {per_mode}")
    result = fetch_team_rebounding_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    return result

# Game/League Tools
@tool
def find_games(
    player_or_team: str = 'T',
    player_id: Optional[int] = None,
    team_id: Optional[int] = None,
    season: Optional[str] = None,
    season_type: Optional[str] = None,
    league_id: Optional[str] = LeagueID.nba,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Finds games based on various criteria such as player, team, season, date range, or league.
    Note: You MUST provide either player_id (if player_or_team='P') or team_id (if player_or_team='T'),
    OR a season/date range for a broader league-wide search.

    Args:
        player_or_team (str, optional): Specifies whether to search by 'P' (Player) or 'T' (Team).
                                        Valid values: "P", "T". Defaults to 'T'.
        player_id (int, optional): The ID of the player to find games for. Required if player_or_team='P'.
        team_id (int, optional): The ID of the team to find games for. Can be used if player_or_team='T'.
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
        season_type (str, optional): The type of season. Valid values: "Regular Season", "Playoffs", "Pre Season", "All Star".
        league_id (str, optional): The league ID. Valid: "00" (NBA), "10" (WNBA), "20" (G-League).
                                   Defaults to "00" (NBA).
        date_from (str, optional): Start date for the game search range, in YYYY-MM-DD format.
        date_to (str, optional): End date for the game search range, in YYYY-MM-DD format.

    Returns:
        str: JSON string containing a list of found games.
             Each game object typically includes:
             {
                 "GAME_ID": str, "GAME_DATE": str (YYYY-MM-DD), "MATCHUP": str, "WL": str,
                 "PTS": int, "FGM": int, "FGA": int, "FG_PCT": float, ... // Player or Team stats for that game
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'find_games' called with params: player_or_team={player_or_team}, player_id={player_id}, team_id={team_id}, season={season}, date_from={date_from}, date_to={date_to}")
    # Validation for player_id/team_id based on player_or_team is handled by the logic function.
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
def get_boxscore_traditional(game_id: str, start_period: int = 0, end_period: int = 0) -> str:
    """
    Fetches the traditional box score (V3) for a specific game, optionally filtered by periods.

    Args:
        game_id (str): The 10-digit ID of the game (e.g., "0022300161").
        start_period (int, optional): The starting period for the box score (1-4, or 5+ for OT). Defaults to 0 (all periods).
        end_period (int, optional): The ending period for the box score (1-4, or 5+ for OT). Defaults to 0 (all periods).

    Returns:
        str: JSON string containing traditional box score data.
             Expected structure:
             {
                 "game_id": str,
                 "parameters": { "start_period": int, "end_period": int, ... },
                 "teams": [ // Team-level stats
                     {"teamId": int, "teamName": str, "fieldGoalsMade": int, ...}, ...
                 ],
                 "players": [ // Player-level stats
                     {"personId": int, "firstName": str, "familyName": str, "minutes": str, "points": int, ...}, ...
                 ],
                 "starters_bench": [ // Stats aggregated by starters vs bench
                     {"teamId": int, "period": str, "startersBench": str, "points": int, ...}, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_boxscore_traditional' called for game_id '{game_id}', periods {start_period}-{end_period}")
    result = fetch_boxscore_traditional_logic(game_id, start_period=start_period, end_period=end_period)
    return result

@tool
def get_league_standings(season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches league standings (conference, division) for a specific season and type.
    Note: The `league_id` parameter is available in the underlying logic but defaults to NBA ("00") and is not exposed in this simplified tool wrapper.

    Args:
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
                                Defaults to the current season.
        season_type (str, optional): The type of season. Valid values: "Regular Season", "Playoffs", "Pre Season", "All Star".
                                     Defaults to "Regular Season".

    Returns:
        str: JSON string containing a list of teams in the standings, sorted by conference/rank.
             Each team object includes: TeamID, TeamName, Conference, PlayoffRank, WINS, LOSSES, WinPCT, GB, etc.
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_league_standings' called for season '{season}', type '{season_type}'")
    result = fetch_league_standings_logic(season=season, season_type=season_type)
    return result

@tool
def get_scoreboard(game_date: Optional[str] = None) -> str:
    """
    Fetches the scoreboard for a specific date, showing all games played or scheduled for that day in the NBA.
    Note: `league_id` and `day_offset` are handled by the underlying logic defaulting to NBA and current day if not specified.

    Args:
        game_date (str, optional): The date for the scoreboard in YYYY-MM-DD format.
                                   Defaults to the current date if None.

    Returns:
        str: JSON string containing scoreboard data.
             Expected structure:
             {
                 "gameDate": str (YYYY-MM-DD),
                 "games": [
                     {
                         "gameId": str, "gameStatus": int, "gameStatusText": str, "period": int,
                         "homeTeam": {"teamId": int, "teamTricode": str, "score": int, ...},
                         "awayTeam": {"teamId": int, "teamTricode": str, "score": int, ...}, ...
                     }, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    final_game_date = game_date or datetime.date.today().strftime('%Y-%m-%d')
    logger.debug(f"Tool 'get_scoreboard' called for date '{final_game_date}'")
    result = fetch_scoreboard_data_logic(game_date=final_game_date)
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
        game_id (str): The 10-digit ID of the game (e.g., "0022300161").
        start_period (int, optional): Starting period filter (1-4, or 5+ for OT). Defaults to 0 (all periods).
                                     Only applies when fetching historical data.
        end_period (int, optional): Ending period filter (1-4, or 5+ for OT). Defaults to 0 (all periods).
                                     Only applies when fetching historical data.

    Returns:
        str: JSON string containing play-by-play data.
             Expected structure:
             {
                 "game_id": str,
                 "source": str ("live" or "historical"),
                 "periods": [
                     {
                         "period": int,
                         "plays": [
                             {"event_num": int, "clock": str, "score": Optional[str], "team": str,
                              "home_description": Optional[str], "away_description": Optional[str],
                              "neutral_description": Optional[str], "event_type": str}, ...
                         ]
                     }, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_play_by_play' called for game_id '{game_id}', periods '{start_period}'-'{end_period}'")
    result_str = fetch_playbyplay_logic(game_id=game_id, start_period=start_period, end_period=end_period)
    return result_str

@tool
def get_draft_history(
    season_year: Optional[str] = None,
    league_id: str = LeagueID.nba,
    round_num: Optional[int] = None,
    team_id: Optional[int] = None,
    overall_pick: Optional[int] = None
) -> str:
    """
    Fetches NBA draft history, optionally filtered by season year, league, round, team, or overall pick.

    Args:
        season_year (str, optional): The draft year in YYYY format (e.g., "2023"). Defaults to all available years if None.
        league_id (str, optional): The league ID. Valid: "00" (NBA), "10" (WNBA), "20" (G-League).
                                   Defaults to "00" (NBA).
        round_num (int, optional): Filter by draft round number (e.g., 1 or 2).
        team_id (int, optional): Filter by the ID of the drafting team.
        overall_pick (int, optional): Filter by the overall pick number in the draft.

    Returns:
        str: JSON string containing a list of draft picks.
             Expected structure:
             {
                 "season_year_requested": str, // "All" if season_year was None
                 "league_id": str,
                 "draft_picks": [
                     {
                         "PERSON_ID": int, "PLAYER_NAME": str, "SEASON": str (YYYY), "ROUND_NUMBER": int,
                         "OVERALL_PICK": int, "TEAM_ABBREVIATION": str, "ORGANIZATION": str, ...
                     }, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(
        f"Tool 'get_draft_history' called for Year: {season_year}, League: {league_id}, "
        f"Round: {round_num}, Team: {team_id}, Pick: {overall_pick}"
    )
    result = fetch_draft_history_logic(
        season_year_nullable=season_year,
        league_id_nullable=league_id,
        round_num_nullable=round_num,
        team_id_nullable=team_id,
        overall_pick_nullable=overall_pick
    )
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
        stat_category (str): The statistical category abbreviation (e.g., "PTS", "REB", "AST", "STL", "BLK", "FG_PCT").
                             Refer to `nba_api.stats.library.parameters.StatCategoryAbbreviation` for all valid options.
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
                                Defaults to the current season.
        season_type (str, optional): The type of season. Valid values: "Regular Season", "Playoffs", "Pre Season", "All Star".
                                     Defaults to "Regular Season".
        per_mode (str, optional): The statistical mode. Valid values from `PerMode48` (e.g., "PerGame", "Totals", "Per48").
                                  Defaults to "PerGame".
        league_id (str, optional): The league ID. Valid: "00" (NBA), "10" (WNBA), "20" (G-League).
                                   Defaults to "00" (NBA).
        scope (str, optional): The scope of the search. Valid values from `Scope` (e.g., "S" for Season, "RS" for Regular Season, "A" for All Players).
                               Defaults to "S".
        top_n (int, optional): The number of top players to return. Defaults to 10.

    Returns:
        str: JSON string containing a list of league leaders.
             Expected structure:
             {
                 "leaders": [
                     {"PLAYER_ID": int, "RANK": int, "PLAYER": str, "TEAM_ID": int, "TEAM": str,
                      "GP": int, "MIN": float, stat_category: float}, ... // stat_category will be the actual stat name
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(
        f"Tool 'get_league_leaders' called for Cat: {stat_category}, Season: {season}, Type: {season_type}, "
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
    Fetches player or league-wide hustle statistics (e.g., contested shots, deflections, charges drawn).
    Can be filtered by player, team, season, and date range.

    Args:
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
                                Defaults to the current season.
        season_type (str, optional): The type of season. Valid values: "Regular Season", "Playoffs", "Pre Season".
                                     Defaults to "Regular Season".
        per_mode (str, optional): The statistical mode. Valid values from PerModeDetailed (e.g., "PerGame", "Totals", "PerMinute").
                                  Defaults to "PerGame".
        player_name (str, optional): The full name of the player to filter for. Defaults to None (league-wide).
        team_id (int, optional): The ID of the team to filter for. Defaults to None (league-wide).
        league_id (str, optional): The league ID. Valid: "00" (NBA). Defaults to "00".
        date_from (str, optional): Start date for filtering (YYYY-MM-DD). Defaults to None.
        date_to (str, optional): End date for filtering (YYYY-MM-DD). Defaults to None.

    Returns:
        str: JSON string containing hustle statistics.
             Expected structure:
             {
                 "parameters": { "season": str, "season_type": str, "per_mode": str, ... },
                 "hustle_stats": [
                     {"PLAYER_NAME": str, "TEAM_ABBREVIATION": str, "MIN": float, "CONTESTED_SHOTS": float,
                      "DEFLECTIONS": float, "CHARGES_DRAWN": float, ...}, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(
        f"Tool 'get_player_hustle_stats' called for Season: {season}, Type: {season_type}, Mode: {per_mode}, "
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
    return result

@tool
def get_player_profile(player_name: str, per_mode: str = PerModeDetailed.per_game) -> str:
    """
    Fetches a comprehensive player profile, including biographical information, career stats,
    next game details, and season highlights.

    Args:
        player_name (str): The full name of the player (e.g., "Giannis Antetokounmpo").
        per_mode (str, optional): The statistical mode for career stats. Valid values from PerModeDetailed
                                  (e.g., "PerGame", "Totals", "Per36"). Defaults to "PerGame".

    Returns:
        str: JSON string containing the player's profile.
             Expected structure:
             {
                 "player_name": str,
                 "player_id": int,
                 "player_info": { "PERSON_ID": int, "FIRST_NAME": str, "LAST_NAME": str, "TEAM_NAME": str, ... },
                 "career_summary": { "GP": int, "PTS": float, "REB": float, "AST": float, ... },
                 "season_highs": { "PTS": int, "REB": int, "AST": int, "GAME_DATE_PTS": str, ... },
                 "career_highs": { "PTS": int, "REB": int, "AST": int, "GAME_DATE_PTS": str, ... },
                 "next_game": { "GAME_ID": str, "GAME_DATE": str, "HOME_TEAM_ABBREVIATION": str, ... }
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_player_profile' called for {player_name}, per_mode {per_mode}")
    result = fetch_player_profile_logic(player_name, per_mode)
    return result

@tool
def get_player_aggregate_stats(player_name: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches an aggregated set of player statistics for a specific season, including various dashboard views.
    This tool provides a broad overview of a player's performance.

    Args:
        player_name (str): The full name of the player (e.g., "Trae Young").
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
                                Defaults to the current season.
        season_type (str, optional): The type of season. Valid values: "Regular Season", "Playoffs".
                                     Defaults to "Regular Season".

    Returns:
        str: JSON string containing aggregated player statistics.
             Expected structure:
             {
                 "player_name": str, "player_id": int, "season": str, "season_type": str, "per_mode": str,
                 "overall_dashboard_stats": { "GP": int, "W_PCT": float, "FGM": float, "PTS": float, ... },
                 "location_dashboard_stats": [ {"GROUP_VALUE": "Home/Road", "GP": int, "PTS": float, ...}, ... ],
                 // ... other dashboard splits
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_player_aggregate_stats' called for {player_name}, season {season}, type {season_type}")
    result = fetch_player_stats_logic(player_name=player_name, season=season, season_type=season_type)
    return result

@tool
def get_top_performers(category: str = "PTS", season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerMode48.per_game, top_n: int = 5) -> str:
    """
    Gets the top N players for a specific statistical category in a given season and season type.

    Args:
        category (str, optional): The statistical category abbreviation (e.g., "PTS", "AST", "REB"). Defaults to "PTS".
        season (str, optional): The NBA season identifier in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Type of season ("Regular Season", "Playoffs", etc.). Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode ("PerGame", "Totals", etc.). Defaults to "PerGame".
        top_n (int, optional): The number of top performers to return. Defaults to 5.

    Returns:
        str: JSON string containing the top performers.
             Expected structure:
             {
                 "season": str, "stat_category": str, "season_type": str,
                 "top_performers": [ {"PLAYER_ID": int, "RANK": int, "PLAYER": str, "TEAM": str, category: float}, ... ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_top_performers' called for Cat: {category}, Season: {season}, Type: {season_type}, Mode: {per_mode}, Top: {top_n}")
    result = fetch_top_performers_logic(
        category=category,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        top_n=top_n
    )
    return result

@tool
def get_top_teams(season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular, top_n: int = 5) -> str:
    """
    Gets the top N teams based on league standings for a given season and season type.

    Args:
        season (str, optional): The NBA season identifier in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Type of season ("Regular Season", "Playoffs", etc.). Defaults to "Regular Season".
        top_n (int, optional): The number of top teams to return based on win percentage. Defaults to 5.

    Returns:
        str: JSON string containing the top teams.
             Expected structure:
             {
                 "top_teams": [ {"TeamID": int, "TeamName": str, "Conference": str, "PlayoffRank": int, "WINS": int, ...}, ... ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_top_teams' called for Season: {season}, Type: {season_type}, Top: {top_n}")
    result = fetch_top_teams_logic(
        season=season,
        season_type=season_type,
        top_n=top_n
    )
    return result

@tool
def get_player_insights(player_name: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerModeDetailed.per_game, league_id: str = LeagueID.nba) -> str:
    """
    Fetches overall player dashboard statistics for a given season, type, and mode, providing insights into performance.
    This is a wrapper around `analyze_player_stats_logic`.

    Args:
        player_name (str): The full name of the player (e.g., "Stephen Curry").
        season (str, optional): The NBA season identifier in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Type of season ("Regular Season", "Playoffs"). Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode ("PerGame", "Totals", etc.). Defaults to "PerGame".
        league_id (str, optional): League ID ("00" for NBA). Defaults to "00".

    Returns:
        str: JSON string containing player dashboard statistics.
             Expected structure similar to `get_player_aggregate_stats`.
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(
        f"Tool 'get_player_insights' called for Player: {player_name}, Season: {season}, Type: {season_type}, "
        f"Mode: {per_mode}, League: {league_id}"
    )
    result = analyze_player_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        league_id=league_id
    )
    return result

@tool
def get_live_odds() -> str:
    """
    Fetches live betting odds for today's NBA games from various bookmakers.
    This tool does not take any arguments as it always fetches current live odds.

    Returns:
        str: JSON string containing a list of today's games and their odds.
             Expected structure:
             {
                 "games": [
                     {
                         "gameId": str, "homeTeamId": str, "awayTeamId": str,
                         "markets": [ // Betting markets (e.g., moneyline, spread)
                             {"name": str, "books": [ // Bookmakers
                                 {"name": str, "outcomes": [ // Odds
                                     {"type": str, "odds": str}, ...
                                 ]}, ...
                             ]}, ...
                         ]
                     }, ...
                 ]
             }
             Or an {'error': 'Error message'} object if fetching odds fails.
    """
    logger.debug("Tool 'get_live_odds' called - Not Caching Live Data")
    # fetch_odds_data_logic already returns a JSON string via format_response
    return fetch_odds_data_logic()

@tool
def get_game_shotchart(game_id: str) -> str:
    """
    Fetches shot chart details for all players in a specific game.

    Args:
        game_id (str): The 10-digit ID of the game (e.g., "0022300161").

    Returns:
        str: JSON string containing shot chart data for the game.
             Expected structure:
             {
                 "game_id": str,
                 "teams": [
                     {
                         "team_name": str, "team_id": int,
                         "shots": [
                             {"player": {"id": int, "name": str}, "period": int, "time_remaining": str,
                              "shot_type": str, "made": bool, "coordinates": {"x": int, "y": int}}, ...
                         ]
                     }, ...
                 ],
                 "league_averages": [
                     {"SHOT_ZONE_BASIC": str, "SHOT_ZONE_AREA": str, "FG_PCT": float}, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_game_shotchart' called for game '{game_id}'")
    result = fetch_shotchart_logic(game_id=game_id) # fetch_shotchart_logic is the underlying function
    return result

# --- Matchup Tools ---
@tool
def get_season_matchups(def_player_id: str, off_player_id: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches head-to-head matchup statistics between a defensive player and an offensive player for a specific season.

    Args:
        def_player_id (str): The ID of the defensive player.
        off_player_id (str): The ID of the offensive player.
        season (str, optional): The NBA season identifier in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Type of season ("Regular Season", "Playoffs"). Defaults to "Regular Season".

    Returns:
        str: JSON string containing matchup statistics.
             Expected structure:
             {
                 "def_player_id": str, "off_player_id": str,
                 "matchups": [ {"OFF_PLAYER_NAME": str, "DEF_PLAYER_NAME": str, "GP": int, "MATCHUP_MIN": str, ...}, ... ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_season_matchups' called for Def: {def_player_id}, Off: {off_player_id}, Season: {season}")
    return fetch_league_season_matchups_logic(def_player_id, off_player_id, season, season_type)

@tool
def get_matchups_rollup(def_player_id: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches a rollup of matchup statistics for a defensive player against all opponents in a specific season,
    categorized by the position of the offensive player.

    Args:
        def_player_id (str): The ID of the defensive player.
        season (str, optional): The NBA season identifier in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Type of season ("Regular Season", "Playoffs"). Defaults to "Regular Season".

    Returns:
        str: JSON string containing matchup rollup statistics.
             Expected structure:
             {
                 "def_player_id": str,
                 "rollup": [ // List of stats, one entry per opponent position guarded
                     {"POSITION": str (e.g., "C", "F", "G"), "DEF_PLAYER_NAME": str, "GP": int, "MATCHUP_MIN": str, ...}, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_matchups_rollup' called for Def: {def_player_id}, Season: {season}")
    return fetch_matchups_rollup_logic(def_player_id, season, season_type)

# --- Synergy Play Types ---
@tool
def get_synergy_play_types(
    league_id: str = LeagueID.nba,
    per_mode: str = PerModeSimple.per_game,
    player_or_team_abbreviation: str = PlayerOrTeamAbbreviation.team,
    season_type: str = SeasonTypeAllStar.regular,
    season: str = CURRENT_SEASON,
    play_type: Optional[str] = None,
    type_grouping: Optional[str] = None
) -> str:
    """
    Fetches Synergy Sports play type statistics for either all players or all teams in a league.
    Can be filtered by specific play type or type grouping (offensive/defensive).
    Note: This endpoint often returns empty data from the NBA API for many general queries.

    Args:
        league_id (str, optional): League ID. Valid: "00" (NBA). Defaults to "00".
        per_mode (str, optional): Statistical mode. Valid: "PerGame", "Totals". Defaults to "PerGame".
        player_or_team_abbreviation (str, optional): Fetch for 'P' (all Players) or 'T' (all Teams). Defaults to 'T'.
                                                   This does NOT filter for a specific player/team ID.
        season_type (str, optional): Type of season ("Regular Season", "Playoffs"). Defaults to "Regular Season".
        season (str, optional): NBA season in YYYY-YY format. Defaults to current season.
        play_type (str, optional): Specific play type (e.g., "Isolation", "Transition", "Spotup").
                                   Valid values: "Cut", "Handoff", "Isolation", "Misc", "OffScreen", "Postup",
                                   "PRBallHandler", "PRRollman", "OffRebound", "Spotup", "Transition".
                                   Defaults to None (all play types).
        type_grouping (str, optional): Broad grouping ("offensive", "defensive"). Defaults to None.

    Returns:
        str: JSON string containing Synergy play type statistics.
             Expected structure:
             {
                 "synergy_stats": [
                     {"PLAYER_ID": Optional[int], "PLAYER_NAME": Optional[str], // If player_or_team_abbreviation='P'
                      "TEAM_ID": Optional[int], "TEAM_ABBREVIATION": Optional[str], // If player_or_team_abbreviation='T'
                      "PLAY_TYPE": str, "PERCENTILE": float, "PPP": float, "POSS": float, ...}, ...
                 ]
             }
             Often returns {"synergy_stats": []} due to external API behavior.
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_synergy_play_types' called for League: {league_id}, Mode: {per_mode}, P/T: {player_or_team_abbreviation}, Season: {season}")
    # The logic function fetch_synergy_play_types_logic returns a dict, but the tool needs to return a string.
    # The previous version did str(result), which is not ideal for JSON.
    # Assuming fetch_synergy_play_types_logic itself now calls format_response.
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
    Provides an analysis of a player's statistics, often comparing across seasons or providing dashboard views.
    This is a wrapper around `analyze_player_stats_logic`.

    Args:
        player_name (str): The full name of the player (e.g., "Stephen Curry").
        season (str, optional): The primary NBA season for analysis in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Type of season ("Regular Season", "Playoffs"). Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode for dashboard stats ("PerGame", "Totals", etc.). Defaults to "PerGame".
        league_id (str, optional): League ID ("00" for NBA). Defaults to "00".

    Returns:
        str: JSON string containing player analysis and dashboard statistics.
             Expected structure similar to `get_player_aggregate_stats`.
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_player_analysis' called for Player: {player_name}, Season: {season}")
    return analyze_player_stats_logic(player_name, season, season_type, per_mode, league_id)

# --- Game Analytics Extensions ---
@tool
def get_boxscore_advanced(game_id: str, start_period: int = 0, end_period: int = 0, start_range: int = 0, end_range: int = 0) -> str:
    """
    Fetches advanced box score (V3) data for a specific game, including metrics like Offensive/Defensive Rating, Pace, etc.
    Optionally filters by period or time range within periods.

    Args:
        game_id (str): The 10-digit ID of the game (e.g., "0022300076").
        start_period (int, optional): Start period filter (1-4, or 5+ for OT). Defaults to 0 (all periods).
        end_period (int, optional): End period filter (1-4, or 5+ for OT). Defaults to 0 (all periods).
        start_range (int, optional): Start of time range in seconds from start of period. Defaults to 0.
        end_range (int, optional): End of time range in seconds from start of period. Defaults to 0.

    Returns:
        str: JSON string containing advanced box score data.
             Expected structure:
             {
                 "game_id": str,
                 "parameters": { "start_period": int, "end_period": int, ... },
                 "player_stats": [ {"personId": int, "minutes": str, "offensiveRating": float, ...}, ... ],
                 "team_stats": [ {"teamId": int, "minutes": str, "offensiveRating": float, ...}, ... ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_boxscore_advanced' called for game_id '{game_id}'")
    result = fetch_boxscore_advanced_logic(game_id, end_period=end_period, end_range=end_range, start_period=start_period, start_range=start_range)
    return result

@tool
def get_boxscore_four_factors(game_id: str, start_period: int = 0, end_period: int = 0) -> str:
    """
    Fetches box score Four Factors (Effective FG%, Turnover %, Offensive Rebound %, Free Throw Rate)
    for a specific game (V3), optionally filtered by periods.

    Args:
        game_id (str): The 10-digit ID of the game (e.g., "0022300161").
        start_period (int, optional): Start period filter (1-4, or 5+ for OT). Defaults to 0 (all periods).
        end_period (int, optional): End period filter (1-4, or 5+ for OT). Defaults to 0 (all periods).

    Returns:
        str: JSON string containing Four Factors box score data.
             Expected structure:
             {
                 "game_id": str,
                 "parameters": { "start_period": int, "end_period": int },
                 "player_stats": [ {"personId": int, "minutes": str, "effectiveFieldGoalPercentage": float, ...}, ... ],
                 "team_stats": [ {"teamId": int, "minutes": str, "effectiveFieldGoalPercentage": float, ...}, ... ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_boxscore_four_factors' called for game_id '{game_id}', periods {start_period}-{end_period}")
    result = fetch_boxscore_four_factors_logic(game_id, start_period=start_period, end_period=end_period)
    return result

@tool
def get_boxscore_usage(game_id: str) -> str:
    """
    Fetches box score usage statistics (V3) for a specific game, detailing player involvement when on the court.

    Args:
        game_id (str): The 10-digit ID of the game (e.g., "0022300161").

    Returns:
        str: JSON string containing usage statistics for each player.
             Expected structure:
             {
                 "game_id": str,
                 "usage_stats": [ {"personId": int, "minutes": str, "usagePercentage": float, ...}, ... ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_boxscore_usage' called for game_id '{game_id}'")
    result = fetch_boxscore_usage_logic(game_id)
    return result

@tool
def get_boxscore_defensive(game_id: str) -> str:
    """
    Fetches box score defensive statistics (V2) for a specific game, including matchup data.

    Args:
        game_id (str): The 10-digit ID of the game (e.g., "0022300161").

    Returns:
        str: JSON string containing defensive statistics for each player.
             Expected structure:
             {
                 "game_id": str,
                 "defensive_stats": [ {"personId": int, "matchupMinutes": str, "playerPoints": int, ...}, ... ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_boxscore_defensive' called for game_id '{game_id}'")
    result = fetch_boxscore_defensive_logic(game_id)
    return result

@tool
def get_win_probability(game_id: str, run_type: str = RunType.default) -> str:
    """
    Fetches win probability data throughout a specific game.

    Args:
        game_id (str): The 10-digit ID of the game (e.g., "0022300161").
        run_type (str, optional): Type of run for probability calculation. Defaults to "0" (standard).

    Returns:
        str: JSON string containing win probability data points.
             Expected structure:
             {
                 "game_id": str,
                 "game_info": { /* Basic game details */ },
                 "win_probability": [ // List of PBP events with win probability
                     {"GAME_ID": str, "EVENT_NUM": int, "HOME_PCT": float, "VISITOR_PCT": float, ...}, ...
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    logger.debug(f"Tool 'get_win_probability' called for game_id '{game_id}'")
    result = fetch_win_probability_logic(game_id, run_type)
    return result

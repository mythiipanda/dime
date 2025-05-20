"""
This module provides a toolkit of miscellaneous functions exposed as agent tools,
primarily focusing on player matchups and game odds. These tools wrap specific
logic functions from `backend.api_tools`.
"""
import logging
import json # Added for potential DataFrame handling in new tools
from typing import Optional, List
from agno.tools import tool
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PlayerOrTeamAbbreviation,
    LeagueID,
    PerModeSimple,
    PerMode48,
    Scope,
    RunType
)
from backend.config import settings
from backend.utils.path_utils import get_relative_cache_path # For DataFrame saving

# Import specific logic functions for misc tools
from backend.api_tools.matchup_tools import fetch_matchups_rollup_logic
from backend.api_tools.odds_tools import fetch_odds_data_logic
from backend.api_tools.game_playbyplay import fetch_playbyplay_logic # For get_historical_playbyplay and get_live_playbyplay
from backend.api_tools.game_boxscores import (\
    fetch_boxscore_hustle_logic, \
    fetch_boxscore_misc_logic, \
    fetch_boxscore_scoring_logic\
)
from backend.api_tools.game_visuals_analytics import fetch_shotchart_logic, fetch_win_probability_logic # For get_shotchart, get_win_probability
from backend.api_tools.synergy_tools import fetch_synergy_play_types_logic # For get_synergy_play_types
from backend.api_tools.trending_tools import fetch_top_performers_logic # For get_top_performers
from backend.api_tools.scoreboard_tools import fetch_scoreboard_data_logic # For get_scoreboard_data
from backend.api_tools.league_draft import fetch_draft_history_logic # For get_draft_history
from backend.api_tools.playoff_series import fetch_common_playoff_series_logic # For get_common_playoff_series
from backend.api_tools.game_finder import fetch_league_games_logic

logger = logging.getLogger(__name__)

@tool
def get_matchups_rollup(
    def_player_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    bypass_cache: bool = False # Added to match underlying logic
) -> str:
    """
    Fetches a rollup of matchup statistics for a defensive player against all opponents for a specific season.

    Args:
        def_player_identifier (str): The name or ID of the defensive player.
        season (str, optional): The NBA season identifier in YYYY-YY format. Defaults to current season.
        season_type (str, optional): The type of season. Defaults to "Regular Season".
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`.
        bypass_cache (bool, optional): If True, bypasses any caching. Defaults to False.

    Returns:
        str: JSON string containing matchup rollup statistics, showing how various offensive players
             performed when guarded by the specified defensive player.
    """
    logger.debug(f"Tool 'get_matchups_rollup' called for Def: {def_player_identifier}, Season: {season}, Type: {season_type}")
    return fetch_matchups_rollup_logic(
        def_player_identifier=def_player_identifier,
        season=season,
        season_type=season_type,
        bypass_cache=bypass_cache
    )

@tool
def get_game_odds(
    bypass_cache: bool = False,
    as_dataframe: bool = False
) -> str:
    """
    Fetches live betting odds for today's NBA games.

    Args:
        bypass_cache (bool, optional): If True, ignores any cached data and fetches fresh data.
                                       Defaults to False.
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string containing odds data. If as_dataframe=True, the JSON response
             will include additional information about the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_game_odds' called, bypass_cache={bypass_cache}, as_dataframe={as_dataframe}")
    return fetch_odds_data_logic(bypass_cache=bypass_cache, return_dataframe=as_dataframe)

# --- Tools moved here or newly defined for misc_tools ---

@tool
def get_historical_playbyplay(
    game_id: str,
    start_period: int = 0, # Corresponds to fetch_playbyplay_logic
    end_period: int = 0,   # Corresponds to fetch_playbyplay_logic
    event_types: Optional[List[str]] = None, # New parameter, maps to fetch_playbyplay_logic
    player_name: Optional[str] = None,       # New parameter, maps to fetch_playbyplay_logic
    person_id: Optional[int] = None,         # New parameter, maps to fetch_playbyplay_logic
    team_id: Optional[int] = None,           # New parameter, maps to fetch_playbyplay_logic
    team_tricode: Optional[str] = None,      # New parameter, maps to fetch_playbyplay_logic
    as_dataframe: bool = False
) -> str:
    """
    Fetches historical play-by-play data for a specific game.
    This tool now uses the unified fetch_playbyplay_logic which can handle historical data.

    Args:
        game_id (str): The ID of the game (e.g., "0022300001").
        start_period (int, optional): The starting period of the game to fetch. Defaults to 0 (all periods).
        end_period (int, optional): The ending period of the game to fetch. Defaults to 0 (all periods).
        event_types (Optional[List[str]], optional): Filter by specific event types (e.g., ['SHOT', 'REBOUND']).
        player_name (Optional[str], optional): Filter by player name.
        person_id (Optional[int], optional): Filter by player ID.
        team_id (Optional[int], optional): Filter by team ID.
        team_tricode (Optional[str], optional): Filter by team tricode.
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string containing play-by-play data. If as_dataframe=True, the JSON response
             will include additional information about the DataFrames and CSV files.
    """
    logger.debug(
        f"Tool 'get_historical_playbyplay' called for game_id {game_id}, "
        f"start_period={start_period}, end_period={end_period}, event_types={event_types}, "
        f"player_name='{player_name}', person_id={person_id}, team_id={team_id}, "
        f"team_tricode='{team_tricode}', as_dataframe={as_dataframe}"
    )
    # Call the unified fetch_playbyplay_logic function
    return fetch_playbyplay_logic(
        game_id=game_id,
        start_period=start_period,
        end_period=end_period,
        event_types=event_types,
        player_name=player_name,
        person_id=person_id,
        team_id=team_id,
        team_tricode=team_tricode,
        return_dataframe=as_dataframe  # Pass as_dataframe to return_dataframe
    )

@tool
def get_live_playbyplay(
    game_id: str,
    event_types: Optional[List[str]] = None, # Parameter from fetch_playbyplay_logic
    player_name: Optional[str] = None,       # Parameter from fetch_playbyplay_logic
    person_id: Optional[int] = None,         # Parameter from fetch_playbyplay_logic
    team_id: Optional[int] = None,           # Parameter from fetch_playbyplay_logic
    team_tricode: Optional[str] = None,      # Parameter from fetch_playbyplay_logic
    as_dataframe: bool = False
) -> str:
    """
    Fetches live play-by-play data for an ongoing game.
    This tool uses the unified fetch_playbyplay_logic which attempts to get live data first.

    Args:
        game_id (str): The ID of the game (e.g., "0022300001").
        event_types (Optional[List[str]], optional): Filter by specific event types (e.g., ['SHOT', 'REBOUND']).
        player_name (Optional[str], optional): Filter by player name.
        person_id (Optional[int], optional): Filter by player ID.
        team_id (Optional[int], optional): Filter by team ID.
        team_tricode (Optional[str], optional): Filter by team tricode.
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string containing live play-by-play data. If as_dataframe=True, the JSON response
             will include additional information about the DataFrames and CSV files.
    """
    logger.debug(
        f"Tool 'get_live_playbyplay' called for game_id {game_id}, "
        f"event_types={event_types}, player_name='{player_name}', person_id={person_id}, "
        f"team_id={team_id}, team_tricode='{team_tricode}', as_dataframe={as_dataframe}"
    )
    # Call the unified fetch_playbyplay_logic function.
    # It will attempt to fetch live data if available for the game_id.
    # start_period and end_period are typically 0 for live full game PBP.
    return fetch_playbyplay_logic(
        game_id=game_id,
        start_period=0, # For live, usually implies all available periods
        end_period=0,   # For live, usually implies all available periods
        event_types=event_types,
        player_name=player_name,
        person_id=person_id,
        team_id=team_id,
        team_tricode=team_tricode,
        return_dataframe=as_dataframe
    )

@tool
def get_boxscore_hustle(game_id: str, as_dataframe: bool = False) -> str:
    """
    Fetches hustle stats from a game's boxscore (BoxScoreHustleV2).
    """
    logger.debug(f"Tool 'get_boxscore_hustle' for game_id {game_id}, as_dataframe={as_dataframe}")
    return fetch_boxscore_hustle_logic(game_id=game_id, return_dataframe=as_dataframe)

@tool
def get_boxscore_misc(game_id: str, as_dataframe: bool = False) -> str:
    """
    Fetches miscellaneous stats from a game's boxscore (BoxScoreMiscV3).
    """
    logger.debug(f"Tool 'get_boxscore_misc' for game_id {game_id}, as_dataframe={as_dataframe}")
    return fetch_boxscore_misc_logic(game_id=game_id, return_dataframe=as_dataframe)

@tool
def get_boxscore_scoring(game_id: str, as_dataframe: bool = False) -> str:
    """
    Fetches scoring-specific stats from a game's boxscore (BoxScoreScoringV3).
    """
    logger.debug(f"Tool 'get_boxscore_scoring' for game_id {game_id}, as_dataframe={as_dataframe}")
    return fetch_boxscore_scoring_logic(game_id=game_id, return_dataframe=as_dataframe)

@tool
def get_shotchart(
    game_id: Optional[str] = None, \
    player_id: Optional[int] = None, \
    team_id: Optional[int] = None,\
    season: Optional[str] = None, # YYYY-YY
    season_type: str = SeasonTypeAllStar.regular, # Default for player/team context
    context_measure: str = "FGA", # Example, see ShotChartDetail params
    as_dataframe: bool = False
) -> str:
    """
    Fetches shot chart data. Can be for a game, player, or team. Specify context via parameters.
    If game_id is provided, it's game-specific. If player_id/team_id and season, it's for that entity in that season.

    Args:
        game_id (Optional[str]): Game ID for game-specific shot chart.
        player_id (Optional[int]): Player ID for player-specific shot chart (requires season).
        team_id (Optional[int]): Team ID for team-specific shot chart (requires season).
        season (Optional[str]): Season (YYYY-YY) if fetching for player/team.
        season_type (str): Season type.
        context_measure (str): Context measure for the shot chart data.
        as_dataframe (bool): If True, returns pandas DataFrame.

    Returns:
        str: JSON string with shot chart data.
    """
    logger.debug(f"Tool 'get_shotchart' called with game_id={game_id}, player_id={player_id}, team_id={team_id}, season={season}")
    # Logic needs to handle different params for ShotChartDetail vs. ShotChartLineupDetail etc.
    # This is a simplified wrapper; underlying fetch_shotchart_logic needs to be robust.
    return fetch_shotchart_logic(\
        game_id=game_id, \
        player_id=player_id, \
        team_id=team_id, \
        season_year=season, # Assuming fetch_shotchart_logic can take season_year
        season_type=season_type,\
        context_measure_simple=context_measure, # Assuming mapping
        return_dataframe=as_dataframe\
    )

@tool
def get_synergy_play_types(
    play_type: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    player_or_team_abbreviation: str = PlayerOrTeamAbbreviation.team,
    league_id: str = LeagueID.nba,
    per_mode: str = PerModeSimple.per_game,
    type_grouping: str = "Offensive",
    player_id_nullable: Optional[int] = None,
    team_id_nullable: Optional[int] = None,
    as_dataframe: bool = False
) -> str:
    """
    Fetches Synergy Sports play type statistics for players or teams.
    """
    logger.debug(f"Tool 'get_synergy_play_types' called for play_type {play_type}")
    return fetch_synergy_play_types_logic(\
        league_id=league_id, per_mode=per_mode, \
        player_or_team=player_or_team_abbreviation, \
        season_type=season_type, season=season, \
        play_type_nullable=play_type, \
        type_grouping_nullable=type_grouping,\
        player_id_nullable=player_id_nullable, \
        team_id_nullable=team_id_nullable,\
        return_dataframe=as_dataframe\
    )

@tool
def get_top_performers(
    category: str = "PTS",
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerMode48.per_game,
    scope: str = Scope.s,
    league_id: str = LeagueID.nba,
    top_n: int = 10, # Changed from 5 to 10 to match common use
    as_dataframe: bool = False
) -> str:
    """
    Gets the top N players for a specific statistical category.
    """
    logger.debug(f"Tool 'get_top_performers' for category {category}, top {top_n}")
    return fetch_top_performers_logic(\
        category=category, season=season, season_type=season_type, \
        per_mode=per_mode, scope=scope, league_id=league_id, top_n=top_n,\
        return_dataframe=as_dataframe\
    )

@tool
def get_scoreboard_data(
    game_date: Optional[str] = None, # YYYY-MM-DD format
    league_id: str = "00", # Using LeagueID.nba equivalent directly
    day_offset: int = 0,
    bypass_cache: bool = False,
    as_dataframe: bool = False
) -> str:
    """
    Fetches scoreboard data for a specific date (or today if not provided).
    This tool was previously named get_live_scoreboard in some contexts.
    Uses fetch_scoreboard_data_logic which handles both live (for today) and static (for other dates) data.

    Args:
        game_date (Optional[str], optional): The date for the scoreboard in YYYY-MM-DD format.
            Defaults to the current date if None.
        league_id (str, optional): The league ID (e.g., "00" for NBA). Defaults to "00".
        day_offset (int, optional): Offset from the game_date. Defaults to 0.
        bypass_cache (bool, optional): If True, bypasses any caching. Defaults to False.
        as_dataframe (bool, optional): If True, returns pandas DataFrame. Defaults to False.

    Returns:
        str: JSON string with scoreboard data.
    """
    logger.debug(
        f"Tool 'get_scoreboard_data' called for Date: {game_date}, League: {league_id}, "
        f"Offset: {day_offset}, BypassCache: {bypass_cache}, AsDataframe: {as_dataframe}"
    )
    return fetch_scoreboard_data_logic(
        game_date=game_date,
        league_id=league_id,
        day_offset=day_offset,
        bypass_cache=bypass_cache,
        return_dataframe=as_dataframe
    )

@tool
def get_win_probability(
    game_id: str,
    run_type: str = RunType.default,
    as_dataframe: bool = False
) -> str:
    """
    Fetches win probability data for a specific game.
    """
    logger.debug(f"Tool 'get_win_probability' for game_id {game_id}, as_dataframe={as_dataframe}")
    return fetch_win_probability_logic(game_id=game_id, run_type=run_type, return_dataframe=as_dataframe)

@tool(cache_results=True, cache_ttl=86400)
def get_draft_history(
    season_year_nullable: Optional[str] = None, # YYYY format
    league_id_nullable: str = LeagueID.nba,
    team_id_nullable: Optional[int] = None,
    round_num_nullable: Optional[int] = None,
    overall_pick_nullable: Optional[int] = None,
    as_dataframe: bool = False # Added for consistency
) -> str:
    """
    Fetches NBA draft history.
    """
    logger.debug(f"Tool 'get_draft_history' called for Year: {season_year_nullable}")
    return fetch_draft_history_logic(\
        season_year_nullable=season_year_nullable,\
        league_id_nullable=league_id_nullable,\
        round_num_nullable=round_num_nullable,\
        team_id_nullable=team_id_nullable,\
        overall_pick_nullable=overall_pick_nullable,\
        return_dataframe=as_dataframe\
    )

@tool(cache_results=True, cache_ttl=86400)
def get_common_playoff_series(
    season: str, # YYYY format for this endpoint (e.g., "2023" for 2023-24 playoffs)
    league_id: str = LeagueID.nba,
    series_id: Optional[str] = None, # e.g., "0042300201"
    as_dataframe: bool = False # Added for consistency
) -> str:
    """
    Fetches common playoff series information.
    """
    logger.debug(f"Tool 'get_common_playoff_series' for season {season}, series_id {series_id}")
    return fetch_common_playoff_series_logic(\
        season=season, league_id=league_id, series_id=series_id, return_dataframe=as_dataframe\
    )
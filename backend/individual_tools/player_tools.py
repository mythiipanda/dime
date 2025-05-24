from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import tool
from agno.utils.log import logger

# Player specific stats logic functions
from ..api_tools.analyze import analyze_player_stats_logic
from ..api_tools.player_aggregate_stats import fetch_player_stats_logic
from ..api_tools.player_career_data import fetch_player_career_stats_logic, fetch_player_awards_logic
from ..api_tools.player_clutch import fetch_player_clutch_stats_logic
from ..api_tools.player_common_info import fetch_player_info_logic, get_player_headshot_url as get_player_headshot_url_logic
from ..api_tools.player_dashboard_game import fetch_player_dashboard_game_splits_logic
from ..api_tools.player_dashboard_general import fetch_player_dashboard_general_splits_logic
from ..api_tools.player_dashboard_lastn import fetch_player_dashboard_lastn_games_logic
from ..api_tools.player_dashboard_shooting import fetch_player_dashboard_shooting_splits_logic
from ..api_tools.player_fantasy_profile import fetch_player_fantasy_profile_logic
from ..api_tools.player_fantasy_profile_bar_graph import fetch_player_fantasy_profile_bar_graph_logic
from ..api_tools.player_gamelogs import fetch_player_gamelog_logic
from ..api_tools.player_game_streak_finder import fetch_player_game_streak_finder_logic
from ..api_tools.player_passing import fetch_player_passing_stats_logic
from ..api_tools.player_rebounding import fetch_player_rebounding_stats_logic
from ..api_tools.player_shooting_tracking import fetch_player_shots_tracking_logic
from ..api_tools.player_career_by_college import fetch_player_career_by_college_logic

from ..config import settings
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, LeagueID, MeasureTypeDetailedDefense,
    PerModeSimple, PerMode36, MeasureTypeDetailed, MeasureTypeBase, PerModeTime
)

@tool
def analyze_player_dashboard_stats(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    league_id: str = LeagueID.nba,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches a player's overall dashboard statistics for a specified season and type.
    Primarily returns 'OverallPlayerDashboard' data from the PlayerDashboardByYearOverYear endpoint.

    Args:
        player_name (str): Full name or ID of the player (e.g., "LeBron James", "2544").
        season (str, optional): NBA season in YYYY-YY format (e.g., "2023-24").
                                Defaults to the current NBA season defined in `settings`.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        return_dataframe (bool, optional): If True, returns (JSON response, {'overall_dashboard': DataFrame}). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, {'overall_dashboard': DataFrame}).
    """
    logger.info(f"Tool: analyze_player_dashboard_stats called for {player_name}, season {season}")
    return analyze_player_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        league_id=league_id,
        return_dataframe=return_dataframe
    )

@tool
def get_player_aggregate_stats(
    player_name: str,
    season: Optional[str] = None,
    season_type: str = SeasonTypeAllStar.regular,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Aggregates various player statistics including common info, career stats,
    game logs for a specified season, and awards history.

    Args:
        player_name (str): The name or ID of the player.
        season (Optional[str], optional): The season for which to fetch game logs (YYYY-YY format). Defaults to current season.
        season_type (str, optional): The type of season for game logs. Defaults to "Regular Season".
        return_dataframe (bool, optional): If True, returns (JSON response, Dict of DataFrames). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, Dict of DataFrames).
    """
    logger.info(f"Tool: get_player_aggregate_stats called for {player_name}, gamelog season {season or settings.CURRENT_NBA_SEASON}")
    return fetch_player_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        return_dataframe=return_dataframe
    )

@tool
def get_player_career_stats(
    player_name: str,
    per_mode: str = PerModeDetailed.per_game,
    league_id_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player career statistics including regular season and postseason totals.

    Args:
        player_name (str): The name or ID of the player.
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
        league_id_nullable (Optional[str], optional): League ID to filter (e.g., "00" for NBA). Defaults to None.
        return_dataframe (bool, optional): If True, returns (JSON response, Dict of DataFrames). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, Dict of DataFrames).
    """
    logger.info(f"Tool: get_player_career_stats called for {player_name}, per_mode {per_mode}")
    return fetch_player_career_stats_logic(
        player_name=player_name,
        per_mode=per_mode,
        league_id_nullable=league_id_nullable,
        return_dataframe=return_dataframe
    )

@tool
def get_player_awards(
    player_name: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches a list of awards received by the specified player.

    Args:
        player_name (str): The name or ID of the player.
        return_dataframe (bool, optional): If True, returns (JSON response, {'awards': DataFrame}). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, {'awards': DataFrame}).
    """
    logger.info(f"Tool: get_player_awards called for {player_name}")
    return fetch_player_awards_logic(
        player_name=player_name,
        return_dataframe=return_dataframe
    )

@tool
def get_player_clutch_stats(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    measure_type: str = MeasureTypeDetailed.base,
    per_mode: str = PerModeDetailed.totals,
    league_id: Optional[str] = "00",
    plus_minus: str = "N",
    pace_adjust: str = "N",
    rank: str = "N",
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    period: int = 0,
    shot_clock_range_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player statistics in clutch situations.

    Args:
        player_name (str): Name or ID of the player.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        measure_type (str, optional): Type of stats. Defaults to "Base".
        per_mode (str, optional): Statistical mode. Defaults to "Totals".
        league_id (Optional[str], optional): League ID. Defaults to "00".
        plus_minus (str, optional): Include plus-minus. Defaults to "N".
        pace_adjust (str, optional): Pace adjust stats. Defaults to "N".
        rank (str, optional): Include rank. Defaults to "N".
        last_n_games (int, optional): Filter by last N games. Defaults to 0.
        month (int, optional): Filter by month (1-12). Defaults to 0.
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0.
        period (int, optional): Filter by period. Defaults to 0.
        shot_clock_range_nullable (Optional[str], optional): Filter by shot clock range.
        game_segment_nullable (Optional[str], optional): Filter by game segment.
        location_nullable (Optional[str], optional): Filter by game location.
        outcome_nullable (Optional[str], optional): Filter by game outcome.
        vs_conference_nullable (Optional[str], optional): Filter by opponent's conference.
        vs_division_nullable (Optional[str], optional): Filter by opponent's division.
        season_segment_nullable (Optional[str], optional): Filter by season segment.
        date_from_nullable (Optional[str], optional): Start date YYYY-MM-DD.
        date_to_nullable (Optional[str], optional): End date YYYY-MM-DD.
        return_dataframe (bool, optional): If True, returns (JSON response, Dict of DataFrames). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, Dict of DataFrames).
    """
    logger.info(f"Tool: get_player_clutch_stats called for {player_name}, season {season}")
    return fetch_player_clutch_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode,
        league_id=league_id,
        plus_minus=plus_minus,
        pace_adjust=pace_adjust,
        rank=rank,
        last_n_games=last_n_games,
        month=month,
        opponent_team_id=opponent_team_id,
        period=period,
        shot_clock_range_nullable=shot_clock_range_nullable,
        game_segment_nullable=game_segment_nullable,
        location_nullable=location_nullable,
        outcome_nullable=outcome_nullable,
        vs_conference_nullable=vs_conference_nullable,
        vs_division_nullable=vs_division_nullable,
        season_segment_nullable=season_segment_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        return_dataframe=return_dataframe
    )

@tool
def get_player_common_info(
    player_name: str,
    league_id_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches common biographical and team information for a player.

    Args:
        player_name (str): The name or ID of the player.
        league_id_nullable (Optional[str], optional): League ID. Defaults to None.
        return_dataframe (bool, optional): If True, returns (JSON, {'player_info': DataFrame, 'headline_stats': DataFrame}). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, Dict of DataFrames).
    """
    logger.info(f"Tool: get_player_common_info called for {player_name}")
    return fetch_player_info_logic(
        player_name=player_name,
        league_id_nullable=league_id_nullable,
        return_dataframe=return_dataframe
    )

@tool
def get_player_headshot_image_url(
    player_id: int # Changed from str to int as per original logic
) -> str:
    """
    Gets the direct URL for a player's headshot image.

    Args:
        player_id (int): The ID of the player.

    Returns:
        str: The URL of the player's headshot image, or an error message/empty string.
    """
    logger.info(f"Tool: get_player_headshot_image_url called for player_id {player_id}")
    # Assuming get_player_headshot_url_logic is the correctly imported function
    return get_player_headshot_url_logic(player_id=player_id)


@tool
def get_player_dashboard_by_game_splits(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season", # Defaulting to string literal for simplicity
    measure_type: str = "Base",
    per_mode: str = "Totals",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player dashboard statistics segmented by various game splits (e.g., location, outcome).

    Args:
        player_name (str): Name or ID of the player.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        measure_type (str, optional): Type of stats. Defaults to "Base".
        per_mode (str, optional): Statistical mode. Defaults to "Totals".
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, Dict of DataFrames).
    """
    logger.info(f"Tool: get_player_dashboard_by_game_splits for {player_name}, season {season}")
    return fetch_player_dashboard_game_splits_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode,
        return_dataframe=return_dataframe
    )

@tool
def get_player_dashboard_by_general_splits(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    measure_type: str = "Base",
    per_mode: str = "Totals",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player dashboard statistics segmented by general splits (e.g., month, day of week).

    Args:
        player_name (str): Name or ID of the player.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        measure_type (str, optional): Type of stats. Defaults to "Base".
        per_mode (str, optional): Statistical mode. Defaults to "Totals".
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, Dict of DataFrames).
    """
    logger.info(f"Tool: get_player_dashboard_by_general_splits for {player_name}, season {season}")
    return fetch_player_dashboard_general_splits_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode,
        return_dataframe=return_dataframe
    )

@tool
def get_player_dashboard_by_last_n_games(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    measure_type: str = "Base",
    per_mode: str = "Totals",
    return_dataframe: bool = False # Added, assuming logic function supports it
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player dashboard statistics based on performance in the last N games.

    Args:
        player_name (str): Name or ID of the player.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        measure_type (str, optional): Type of stats. Defaults to "Base".
        per_mode (str, optional): Statistical mode. Defaults to "Totals".
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames). Defaults to False.


    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, Dict of DataFrames).
    """
    logger.info(f"Tool: get_player_dashboard_by_last_n_games for {player_name}, season {season}")
    # Assuming the logic function handles these parameters
    return fetch_player_dashboard_lastn_games_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode,
        return_dataframe=return_dataframe
    )

@tool
def get_player_dashboard_by_shooting_splits(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    measure_type: str = "Base",
    per_mode: str = "Totals",
    return_dataframe: bool = False # Added, assuming logic function supports it
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player dashboard statistics segmented by various shooting splits.

    Args:
        player_name (str): Name or ID of the player.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        measure_type (str, optional): Type of stats. Defaults to "Base".
        per_mode (str, optional): Statistical mode. Defaults to "Totals".
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, Dict of DataFrames).
    """
    logger.info(f"Tool: get_player_dashboard_by_shooting_splits for {player_name}, season {season}")
    return fetch_player_dashboard_shooting_splits_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode,
        return_dataframe=return_dataframe
    )

@tool
def get_player_fantasy_profile(
    player_id: str, 
    season: str = settings.CURRENT_NBA_SEASON,
    season_type_playoffs: str = SeasonTypeAllStar.regular,
    measure_type_base: str = MeasureTypeBase.base,
    per_mode36: str = PerMode36.totals,
    league_id_nullable: str = "",
    pace_adjust_no: str = "N",
    plus_minus_no: str = "N",
    rank_no: str = "N",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches a player's fantasy basketball profile data.

    Args:
        player_id (str): ID of the player.
        season (str, optional): NBA season. Defaults to current season.
        season_type_playoffs (str, optional): Season type. Defaults to "Regular Season".
        measure_type_base (str, optional): Type of stats. Defaults to "Base".
        per_mode36 (str, optional): Statistical mode. Defaults to "Totals".
        league_id_nullable (str, optional): League ID. Defaults to "".
        pace_adjust_no (str, optional): Pace adjust stats. Defaults to "N".
        plus_minus_no (str, optional): Include plus-minus. Defaults to "N".
        rank_no (str, optional): Include rank. Defaults to "N".
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, Dict of DataFrames).
    """
    logger.info(f"Tool: get_player_fantasy_profile for player_id {player_id}, season {season}")
    return fetch_player_fantasy_profile_logic(
        player_id=player_id,
        season=season,
        season_type_playoffs=season_type_playoffs,
        measure_type_base=measure_type_base,
        per_mode36=per_mode36,
        league_id_nullable=league_id_nullable,
        pace_adjust_no=pace_adjust_no,
        plus_minus_no=plus_minus_no,
        rank_no=rank_no,
        return_dataframe=return_dataframe
    )

@tool
def get_player_fantasy_profile_bar_graph(
    player_id: str,
    season: str = settings.CURRENT_NBA_SEASON,
    league_id_nullable: str = "",
    season_type_all_star_nullable: str = "",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches data suitable for generating a bar graph of a player's fantasy profile.

    Args:
        player_id (str): ID of the player.
        season (str, optional): NBA season. Defaults to current season.
        league_id_nullable (str, optional): League ID. Defaults to "".
        season_type_all_star_nullable (str, optional): Season type. Defaults to "".
        return_dataframe (bool, optional): If True, returns (JSON, {'fantasy_profile_bar_graph': DataFrame}). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, {'fantasy_profile_bar_graph': DataFrame}).
    """
    logger.info(f"Tool: get_player_fantasy_profile_bar_graph for player_id {player_id}, season {season}")
    return fetch_player_fantasy_profile_bar_graph_logic(
        player_id=player_id,
        season=season,
        league_id_nullable=league_id_nullable,
        season_type_all_star_nullable=season_type_all_star_nullable,
        return_dataframe=return_dataframe
    )

@tool
def get_player_gamelog(
    player_name: str,
    season: str, # Made non-optional as gamelogs are usually season-specific
    season_type: str = SeasonTypeAllStar.regular,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches the game-by-game statistics for a player in a specific season.

    Args:
        player_name (str): Name or ID of the player.
        season (str): NBA season (YYYY-YY format).
        season_type (str, optional): Season type. Defaults to "Regular Season".
        return_dataframe (bool, optional): If True, returns (JSON, {'gamelog': DataFrame}). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, {'gamelog': DataFrame}).
    """
    logger.info(f"Tool: get_player_gamelog for {player_name}, season {season}, type {season_type}")
    return fetch_player_gamelog_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        return_dataframe=return_dataframe
    )

@tool
def get_player_game_streaks(
    player_id_nullable: str = "", # Changed from player_name for consistency with endpoint
    season_nullable: str = "",
    season_type_nullable: str = "",
    league_id_nullable: str = "",
    active_streaks_only_nullable: str = "",
    location_nullable: str = "",
    outcome_nullable: str = "",
    gt_pts_nullable: str = "", # Example stat-specific filter
    # ... add other specific stat filters like gt_ast_nullable, gt_reb_nullable etc. if needed
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Finds various game streaks for a player based on specified criteria.

    Args:
        player_id_nullable (str, optional): ID of the player. Defaults to "".
        season_nullable (str, optional): NBA season. Defaults to "".
        season_type_nullable (str, optional): Season type. Defaults to "".
        league_id_nullable (str, optional): League ID. Defaults to "".
        active_streaks_only_nullable (str, optional): Filter for active streaks only ("Y" or "N"). Defaults to "".
        location_nullable (str, optional): Filter by game location. Defaults to "".
        outcome_nullable (str, optional): Filter by game outcome. Defaults to "".
        gt_pts_nullable (str, optional): Filter for games with points greater than this value. Defaults to "".
        return_dataframe (bool, optional): If True, returns (JSON, {'streaks': DataFrame}). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, {'streaks': DataFrame}).
    """
    logger.info(f"Tool: get_player_game_streaks for player_id {player_id_nullable or 'any'}")
    # Construct a dictionary for other_filters to pass to the logic function
    other_filters = {
        "gt_pts_nullable": gt_pts_nullable,
        # Add other stat filters here if they are implemented in the logic function
    }
    return fetch_player_game_streak_finder_logic(
        player_id_nullable=player_id_nullable,
        season_nullable=season_nullable,
        season_type_nullable=season_type_nullable,
        league_id_nullable=league_id_nullable,
        active_streaks_only_nullable=active_streaks_only_nullable,
        location_nullable=location_nullable,
        outcome_nullable=outcome_nullable,
        other_filters=other_filters, # Pass other filters as a dictionary
        return_dataframe=return_dataframe
    )

@tool
def get_player_passing_stats(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    last_n_games: int = 0,
    league_id: str = "00",
    month: int = 0,
    opponent_team_id: int = 0,
    vs_division_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches detailed passing statistics for a player.

    Args:
        player_name (str): Name or ID of the player.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
        last_n_games (int, optional): Filter by last N games. Defaults to 0.
        league_id (str, optional): League ID. Defaults to "00".
        month (int, optional): Filter by month. Defaults to 0.
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0.
        vs_division_nullable (Optional[str], optional): Filter by opponent's division.
        vs_conference_nullable (Optional[str], optional): Filter by opponent's conference.
        season_segment_nullable (Optional[str], optional): Filter by season segment.
        outcome_nullable (Optional[str], optional): Filter by game outcome.
        location_nullable (Optional[str], optional): Filter by game location.
        date_to_nullable (Optional[str], optional): End date YYYY-MM-DD.
        date_from_nullable (Optional[str], optional): Start date YYYY-MM-DD.
        return_dataframe (bool, optional): If True, returns (JSON, {'passing_stats': DataFrame}). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, {'passing_stats': DataFrame}).
    """
    logger.info(f"Tool: get_player_passing_stats for {player_name}, season {season}")
    return fetch_player_passing_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        last_n_games=last_n_games,
        league_id=league_id,
        month=month,
        opponent_team_id=opponent_team_id,
        vs_division_nullable=vs_division_nullable,
        vs_conference_nullable=vs_conference_nullable,
        season_segment_nullable=season_segment_nullable,
        outcome_nullable=outcome_nullable,
        location_nullable=location_nullable,
        date_to_nullable=date_to_nullable,
        date_from_nullable=date_from_nullable,
        return_dataframe=return_dataframe
    )

@tool
def get_player_rebounding_stats(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    last_n_games: int = 0,
    league_id: str = "00",
    month: int = 0,
    opponent_team_id: int = 0,
    period: int = 0, # Added period as it's often available for rebounding
    vs_division_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches detailed rebounding statistics for a player.

    Args:
        player_name (str): Name or ID of the player.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
        last_n_games (int, optional): Filter by last N games. Defaults to 0.
        league_id (str, optional): League ID. Defaults to "00".
        month (int, optional): Filter by month. Defaults to 0.
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0.
        period (int, optional): Filter by period. Defaults to 0.
        vs_division_nullable (Optional[str], optional): Filter by opponent's division.
        vs_conference_nullable (Optional[str], optional): Filter by opponent's conference.
        season_segment_nullable (Optional[str], optional): Filter by season segment.
        outcome_nullable (Optional[str], optional): Filter by game outcome.
        location_nullable (Optional[str], optional): Filter by game location.
        game_segment_nullable (Optional[str], optional): Filter by game segment.
        date_to_nullable (Optional[str], optional): End date YYYY-MM-DD.
        date_from_nullable (Optional[str], optional): Start date YYYY-MM-DD.
        return_dataframe (bool, optional): If True, returns (JSON, {'rebounding_stats': DataFrame}). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, {'rebounding_stats': DataFrame}).
    """
    logger.info(f"Tool: get_player_rebounding_stats for {player_name}, season {season}")
    return fetch_player_rebounding_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        last_n_games=last_n_games,
        league_id=league_id,
        month=month,
        opponent_team_id=opponent_team_id,
        period=period,
        vs_division_nullable=vs_division_nullable,
        vs_conference_nullable=vs_conference_nullable,
        season_segment_nullable=season_segment_nullable,
        outcome_nullable=outcome_nullable,
        location_nullable=location_nullable,
        game_segment_nullable=game_segment_nullable,
        date_to_nullable=date_to_nullable,
        date_from_nullable=date_from_nullable,
        return_dataframe=return_dataframe
    )

@tool
def get_player_shooting_tracking_stats(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.totals, # Defaulting to Totals as it's common for shot tracking
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    last_n_games: int = 0,
    league_id: str = "00",
    month: int = 0,
    period: int = 0,
    vs_division_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches detailed shooting tracking statistics for a player (makes, misses, locations, types).

    Args:
        player_name (str): Name or ID of the player.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "Totals".
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0.
        date_from (Optional[str], optional): Start date YYYY-MM-DD.
        date_to (Optional[str], optional): End date YYYY-MM-DD.
        last_n_games (int, optional): Filter by last N games. Defaults to 0.
        league_id (str, optional): League ID. Defaults to "00".
        month (int, optional): Filter by month. Defaults to 0.
        period (int, optional): Filter by period. Defaults to 0.
        vs_division_nullable (Optional[str], optional): Filter by opponent's division.
        vs_conference_nullable (Optional[str], optional): Filter by opponent's conference.
        season_segment_nullable (Optional[str], optional): Filter by season segment.
        outcome_nullable (Optional[str], optional): Filter by game outcome.
        location_nullable (Optional[str], optional): Filter by game location.
        game_segment_nullable (Optional[str], optional): Filter by game segment.
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames for different shot types). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, Dict of DataFrames).
    """
    logger.info(f"Tool: get_player_shooting_tracking_stats for {player_name}, season {season}")
    return fetch_player_shots_tracking_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        opponent_team_id=opponent_team_id,
        date_from=date_from,
        date_to=date_to,
        last_n_games=last_n_games,
        league_id=league_id,
        month=month,
        period=period,
        vs_division_nullable=vs_division_nullable,
        vs_conference_nullable=vs_conference_nullable,
        season_segment_nullable=season_segment_nullable,
        outcome_nullable=outcome_nullable,
        location_nullable=location_nullable,
        game_segment_nullable=game_segment_nullable,
        return_dataframe=return_dataframe
    )

@tool
def get_player_career_stats_by_college(
    college: str,
    league_id: str = "00",
    per_mode_simple: str = PerModeSimple.totals,
    season_type_all_star: str = SeasonTypeAllStar.regular,
    season_nullable: str = "", # Optional: filter by a specific season
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches career statistics for all players from a specific college.

    Args:
        college (str): Name of the college.
        league_id (str, optional): League ID. Defaults to "00".
        per_mode_simple (str, optional): Statistical mode. Defaults to "Totals".
        season_type_all_star (str, optional): Season type. Defaults to "Regular Season".
        season_nullable (str, optional): Specific season to filter for. Defaults to "" (all applicable seasons).
        return_dataframe (bool, optional): If True, returns (JSON, {'career_stats_by_college': DataFrame}). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, {'career_stats_by_college': DataFrame}).
    """
    logger.info(f"Tool: get_player_career_stats_by_college for college {college}")
    return fetch_player_career_by_college_logic(
        college=college,
        league_id=league_id,
        per_mode_simple=per_mode_simple,
        season_type_all_star=season_type_all_star,
        season_nullable=season_nullable,
        return_dataframe=return_dataframe
    ) 
from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import tool
from agno.utils.log import logger

# Advanced Analytics logic functions
from ..api_tools.advanced_metrics import fetch_player_advanced_analysis_logic
from ..api_tools.player_shot_charts import fetch_player_shotchart_logic # Individual player shot chart data
from ..api_tools.advanced_shot_charts import process_shot_data_for_visualization as generate_advanced_shot_chart_visual_logic
from ..api_tools.player_comparison import compare_player_shots as compare_player_shots_visual_logic # Visual shot chart comparison

from ..config import settings
from nba_api.stats.library.parameters import SeasonTypeAllStar # Used in default args
from ..api_tools.advanced_player_metrics import calculate_advanced_player_metrics as calculate_advanced_player_metrics_logic

@tool
def get_player_advanced_analysis(
    player_name: str,
    season: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches advanced metrics, RAPTOR-style ratings, skill grades, and similar players.
    Args:
        player_name (str): Full name or ID of the player.
        season (Optional[str]): YYYY-YY format (e.g., "2023-24"). Defaults to current season.
        return_dataframe (bool): If True, returns (JSON, Dict of DataFrames). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    effective_season = season if season is not None else settings.CURRENT_NBA_SEASON
    logger.info(f"Tool: get_player_advanced_analysis for {player_name}, season {effective_season}")
    return fetch_player_advanced_analysis_logic(
        player_name=player_name,
        season=effective_season, # Pass the resolved season
        return_dataframe=return_dataframe
    )

@tool
def get_player_shot_chart_data(
    player_name: str,
    season: Optional[str] = None,
    season_type: str = SeasonTypeAllStar.regular,
    context_measure: str = "FGA",
    last_n_games: int = 0,
    league_id: str = "00",
    month: int = 0,
    opponent_team_id: int = 0,
    period: int = 0,
    vs_division_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    game_id_nullable: Optional[str] = None,
    player_position_nullable: Optional[str] = None,
    rookie_year_nullable: Optional[str] = None,
    context_filter_nullable: Optional[str] = None,
    clutch_time_nullable: Optional[str] = None,
    ahead_behind_nullable: Optional[str] = None,
    point_diff_nullable: Optional[str] = None, # In toolkit, this was string, API might expect int
    position_nullable: Optional[str] = None,
    range_type_nullable: Optional[str] = None, # API might use specific int constants
    start_period_nullable: Optional[str] = None, # API might use specific int constants
    start_range_nullable: Optional[str] = None, # API might use specific int constants
    end_period_nullable: Optional[str] = None, # API might use specific int constants
    end_range_nullable: Optional[str] = None, # API might use specific int constants
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches detailed shot chart data for a player.
    Args:
        player_name (str): Full name or ID of the player.
        season (Optional[str]): YYYY-YY format. Defaults to current season.
        season_type (str): E.g., "Regular Season", "Playoffs". Defaults to "Regular Season".
        context_measure (str): Stat for API context (e.g., "FGA"). Defaults to "FGA".
        last_n_games (int): Filter by last N games. Defaults to 0 (all).
        league_id (str): League ID. Defaults to "00".
        month (int): Month filter. Defaults to 0.
        opponent_team_id (int): Opponent team ID. Defaults to 0.
        period (int): Period filter. Defaults to 0.
        vs_division_nullable (Optional[str]): Filter by division.
        vs_conference_nullable (Optional[str]): Filter by conference.
        season_segment_nullable (Optional[str]): Filter by season segment.
        outcome_nullable (Optional[str]): Filter by game outcome.
        location_nullable (Optional[str]): Filter by game location.
        game_segment_nullable (Optional[str]): Filter by game segment.
        date_to_nullable (Optional[str]): End date filter.
        date_from_nullable (Optional[str]): Start date filter.
        game_id_nullable (Optional[str]): Game ID filter.
        player_position_nullable (Optional[str]): Player position filter.
        rookie_year_nullable (Optional[str]): Rookie year filter.
        context_filter_nullable (Optional[str]): Additional context filter.
        clutch_time_nullable (Optional[str]): Clutch time filter.
        ahead_behind_nullable (Optional[str]): Ahead/behind filter.
        point_diff_nullable (Optional[str]): Point difference filter.
        position_nullable (Optional[str]): Player position (detailed) filter.
        range_type_nullable (Optional[str]): Range type for period/time filters.
        start_period_nullable (Optional[str]): Start period for range filters.
        start_range_nullable (Optional[str]): Start range (time) for range filters.
        end_period_nullable (Optional[str]): End period for range filters.
        end_range_nullable (Optional[str]): End range (time) for range filters.
        return_dataframe (bool): If True, returns (JSON, Dict of DataFrames). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    effective_season = season if season is not None else settings.CURRENT_NBA_SEASON
    logger.info(f"Tool: get_player_shot_chart_data for {player_name}, season {effective_season}")
    return fetch_player_shotchart_logic(
        player_name=player_name, season=effective_season, season_type=season_type,
        context_measure=context_measure, last_n_games=last_n_games, league_id=league_id, month=month,
        opponent_team_id=opponent_team_id, period=period, vs_division_nullable=vs_division_nullable,
        vs_conference_nullable=vs_conference_nullable, season_segment_nullable=season_segment_nullable,
        outcome_nullable=outcome_nullable, location_nullable=location_nullable,
        game_segment_nullable=game_segment_nullable, date_to_nullable=date_to_nullable,
        date_from_nullable=date_from_nullable, game_id_nullable=game_id_nullable,
        player_position_nullable=player_position_nullable, rookie_year_nullable=rookie_year_nullable,
        context_filter_nullable=context_filter_nullable, clutch_time_nullable=clutch_time_nullable,
        ahead_behind_nullable=ahead_behind_nullable, point_diff_nullable=point_diff_nullable,
        position_nullable=position_nullable, range_type_nullable=range_type_nullable, 
        start_period_nullable=start_period_nullable, start_range_nullable=start_range_nullable, 
        end_period_nullable=end_period_nullable, end_range_nullable=end_range_nullable,
        return_dataframe=return_dataframe
    )

@tool
def generate_player_advanced_shot_chart_visualization(
    player_name: str,
    season: Optional[str] = None,
    season_type: str = SeasonTypeAllStar.regular, # Corrected default from toolkit
    chart_type: str = "scatter",
    output_format: str = "base64",
    use_cache: bool = True,
    return_dataframe: bool = False 
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]]:
    """
    Generates an advanced shot chart visualization for a player.
    Args:
        player_name (str): Name or ID of the player.
        season (Optional[str]): YYYY-YY format. Defaults to current season.
        season_type (str): E.g., "Regular Season". Defaults to "Regular Season".
        chart_type (str): "scatter", "heatmap", "hexbin", "animated", "frequency", "distance". Defaults to "scatter".
        output_format (str): "base64" or "file". Defaults to "base64".
        use_cache (bool): Use cached visualizations. Defaults to True.
        return_dataframe (bool): If True, also returns underlying shot DataFrames. Defaults to False.
    Returns:
        Union[Dict[str, Any], Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]]: Visualization dict or (Viz dict, DF dict).
    """
    effective_season = season if season is not None else settings.CURRENT_NBA_SEASON
    logger.info(f"Tool: generate_player_advanced_shot_chart_visualization for {player_name}, chart: {chart_type}, season: {effective_season}")
    return generate_advanced_shot_chart_visual_logic(
        player_name=player_name,
        season=effective_season,
        season_type=season_type,
        chart_type=chart_type,
        output_format=output_format,
        use_cache=use_cache,
        return_dataframe=return_dataframe
    )

@tool
def calculate_comprehensive_advanced_player_metrics(
    player_id: int,
    current_season: int = settings.CURRENT_NBA_SEASON_YEAR, # Assuming settings has CURRENT_NBA_SEASON_YEAR
    include_projections: bool = True,
    return_dataframe: bool = False
) -> Union[Dict[str, Any], Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Calculates comprehensive advanced metrics for a player using EPM/DARKO methodology.
    Includes multi-season RAPM, age/experience adjustments, historical progression,
    and predictive projections.

    Args:
        player_id (int): The NBA API player ID.
        current_season (int, optional): Current season year (e.g., 2024 for 2024-25).
                                        Defaults to the current NBA season year from settings.
        include_projections (bool, optional): Whether to include future projections. Defaults to True.
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames). Defaults to False.

    Returns:
        Union[Dict[str, Any], Tuple[str, Dict[str, pd.DataFrame]]]: Dictionary with advanced metrics
                                                                     or tuple with JSON and DataFrames.
    """
    logger.info(f"Tool: calculate_comprehensive_advanced_player_metrics for player {player_id}, season {current_season}")
    return calculate_advanced_player_metrics_logic(
        player_id=player_id,
        current_season=current_season,
        include_projections=include_projections,
        return_dataframe=return_dataframe
    )

@tool
def compare_players_shot_charts_visualization(
    player_names: List[str],
    season: Optional[str] = None,
    season_type: str = SeasonTypeAllStar.regular, # Corrected default from toolkit
    output_format: str = "base64",
    chart_type: str = "scatter",
    context_measure: str = "FGA",
    return_dataframe: bool = False
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]]:
    """
    Compares shot charts visually for multiple players (2 to 4).
    Args:
        player_names (List[str]): List of 2 to 4 player names or IDs.
        season (Optional[str]): YYYY-YY format. Defaults to current season.
        season_type (str): E.g., "Regular Season". Defaults to "Regular Season".
        output_format (str): "base64" or "file". Defaults to "base64".
        chart_type (str): "scatter", "heatmap", "zones". Defaults to "scatter".
        context_measure (str): Context measure for data. Defaults to "FGA".
        return_dataframe (bool): If True, also returns underlying shot DataFrames. Defaults to False.
    Returns:
        Union[Dict[str, Any], Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]]: Visualization dict or (Viz dict, DF dict).
    """
    effective_season = season if season is not None else settings.CURRENT_NBA_SEASON
    logger.info(f"Tool: compare_players_shot_charts_visualization for {player_names}, chart: {chart_type}, season: {effective_season}")
    return compare_player_shots_visual_logic(
        player_names=player_names,
        season=effective_season,
        season_type=season_type,
        output_format=output_format,
        chart_type=chart_type,
        context_measure=context_measure,
        return_dataframe=return_dataframe
    )
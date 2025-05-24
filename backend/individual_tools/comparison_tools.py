from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import tool # Import tool decorator
from agno.utils.log import logger

# Comparison specific stats logic functions
# Assuming these imports will be relative to the new file's location or handled by PYTHONPATH
from ..api_tools.player_compare import fetch_player_compare_logic
from ..api_tools.teamvsplayer import fetch_teamvsplayer_logic
from ..api_tools.matchup_tools import fetch_league_season_matchups_logic, fetch_matchups_rollup_logic # Player vs Player Season and Defensive Rollup
from ..api_tools.player_comparison import compare_player_shots as compare_player_shots_visual_logic # Visual shot chart comparison

from ..config import settings
from nba_api.stats.library.parameters import (
    SeasonTypePlayoffs, PerModeDetailed, MeasureTypeDetailedDefense,
    SeasonTypeAllStar # For matchup_tools
)

@tool
def compare_players_stats(
    player_id_list: List[str], # Typically 2 to 5 players
    vs_player_id_list: Optional[List[str]] = None, # Optional for direct comparison without a "vs" context
    season: str = settings.CURRENT_NBA_SEASON,
    season_type_playoffs: str = SeasonTypePlayoffs.regular,
    per_mode_detailed: str = PerModeDetailed.totals,
    measure_type_detailed_defense: str = MeasureTypeDetailedDefense.base,
    league_id_nullable: str = "", # Can be "" for NBA, or "00", "10"
    last_n_games: int = 0,
    pace_adjust: str = "N", # "Y" or "N"
    plus_minus: str = "N",  # "Y" or "N"
    rank: str = "N",        # "Y" or "N"
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Compares statistical performance between a list of players, optionally against another list of players.
    Fetches data using the PlayerCompare endpoint.

    Args:
        player_id_list (List[str]): A list of player IDs (as strings) for the primary group of players to compare.
                                    Typically 2 to 5 players.
        vs_player_id_list (Optional[List[str]], optional): A list of player IDs (as strings) for the comparison group.
                                                           If None, players in `player_id_list` are compared against each other or their averages.
                                                           Defaults to None.
        season (str, optional): NBA season in YYYY-YY format. Defaults to current season.
        season_type_playoffs (str, optional): Type of season. Defaults to "Regular Season".
                                              Possible values from SeasonTypePlayoffs enum (e.g., "Regular Season", "Playoffs").
        per_mode_detailed (str, optional): Statistical mode. Defaults to "Totals".
                                           Possible values from PerModeDetailed enum (e.g., "PerGame", "Per100Possessions").
        measure_type_detailed_defense (str, optional): Type of stats. Defaults to "Base".
                                                       Possible values from MeasureTypeDetailedDefense enum (e.g., "Base", "Advanced").
        league_id_nullable (str, optional): League ID. Defaults to "" (usually implies NBA "00").
                                            Possible values: "00" (NBA), "10" (WNBA), "" (default/NBA).
        last_n_games (int, optional): Filter by last N games. Defaults to 0 (all games).
        pace_adjust (str, optional): Pace adjust stats ("Y" or "N"). Defaults to "N".
        plus_minus (str, optional): Include plus-minus ("Y" or "N"). Defaults to "N".
        rank (str, optional): Include rank ("Y" or "N"). Defaults to "N".
        return_dataframe (bool, optional): If True, returns a tuple (JSON response, dictionary of DataFrames).
                                           Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
            If return_dataframe=False: JSON string with player comparison data or an error message.
            If return_dataframe=True: Tuple (json_string, dataframes_dict).
    """
    logger.info(f"Tool: compare_players_stats called for players {player_id_list} vs {vs_player_id_list or 'overall'}")
    vs_player_tuple = tuple(vs_player_id_list) if vs_player_id_list is not None else tuple()
    player_tuple = tuple(player_id_list)

    return fetch_player_compare_logic(
        vs_player_id_list=vs_player_tuple,
        player_id_list=player_tuple,
        season=season,
        season_type_playoffs=season_type_playoffs,
        per_mode_detailed=per_mode_detailed,
        measure_type_detailed_defense=measure_type_detailed_defense,
        league_id_nullable=league_id_nullable,
        last_n_games=last_n_games,
        pace_adjust=pace_adjust,
        plus_minus=plus_minus,
        rank=rank,
        return_dataframe=return_dataframe
    )

@tool
def get_team_vs_player_comparison(
    team_identifier: str,
    vs_player_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.totals,
    measure_type: str = MeasureTypeDetailedDefense.base,
    player_identifier: Optional[str] = None,
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    pace_adjust: str = "N",
    period: int = 0,
    plus_minus: str = "N",
    rank: str = "N",
    vs_division_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    league_id_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches detailed statistics for a team when a specific opposing player is on/off the court.
    Optionally, can further analyze the impact of one of the team's own players in this context.

    Args:
        team_identifier (str): Name, abbreviation, or ID of the team.
        vs_player_identifier (str): Name or ID of the opposing player to analyze against.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "Totals".
        measure_type (str, optional): Type of stats. Defaults to "Base".
        player_identifier (Optional[str], optional): Player on the primary team to analyze their on/off impact.
        last_n_games (int, optional): Filter by last N games. Defaults to 0.
        month (int, optional): Filter by month (1-12). Defaults to 0.
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0.
        pace_adjust (str, optional): Pace adjust stats. Defaults to "N".
        period (int, optional): Filter by period. Defaults to 0.
        plus_minus (str, optional): Include plus-minus. Defaults to "N".
        rank (str, optional): Include rank. Defaults to "N".
        vs_division_nullable (Optional[str], optional): Filter by opponent's division.
        vs_conference_nullable (Optional[str], optional): Filter by opponent's conference.
        season_segment_nullable (Optional[str], optional): Filter by season segment.
        outcome_nullable (Optional[str], optional): Filter by game outcome ('W' or 'L').
        location_nullable (Optional[str], optional): Filter by game location ('Home' or 'Road').
        league_id_nullable (Optional[str], optional): League ID.
        game_segment_nullable (Optional[str], optional): Filter by game segment.
        date_from_nullable (Optional[str], optional): Start date YYYY-MM-DD.
        date_to_nullable (Optional[str], optional): End date YYYY-MM-DD.
        return_dataframe (bool, optional): If True, returns (JSON response, DataFrames). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_team_vs_player_comparison called for team {team_identifier} vs player {vs_player_identifier}")
    return fetch_teamvsplayer_logic(
        team_identifier=team_identifier,
        vs_player_identifier=vs_player_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        player_identifier=player_identifier,
        last_n_games=last_n_games,
        month=month,
        opponent_team_id=opponent_team_id,
        pace_adjust=pace_adjust,
        period=period,
        plus_minus=plus_minus,
        rank=rank,
        vs_division_nullable=vs_division_nullable,
        vs_conference_nullable=vs_conference_nullable,
        season_segment_nullable=season_segment_nullable,
        outcome_nullable=outcome_nullable,
        location_nullable=location_nullable,
        league_id_nullable=league_id_nullable,
        game_segment_nullable=game_segment_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        return_dataframe=return_dataframe
    )

@tool
def get_player_vs_player_season_matchups(
    def_player_identifier: str,
    off_player_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    bypass_cache: bool = False,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches season-long head-to-head matchup statistics between two specific players.

    Args:
        def_player_identifier (str): Name or ID of the defensive player.
        off_player_identifier (str): Name or ID of the offensive player.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        bypass_cache (bool, optional): Ignore cached API data. Defaults to False.
        return_dataframe (bool, optional): If True, returns (JSON response, {'matchups': DataFrame}). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, {'matchups': DataFrame}).
    """
    logger.info(f"Tool: get_player_vs_player_season_matchups for Def: {def_player_identifier} vs Off: {off_player_identifier}")
    return fetch_league_season_matchups_logic(
        def_player_identifier=def_player_identifier,
        off_player_identifier=off_player_identifier,
        season=season,
        season_type=season_type,
        bypass_cache=bypass_cache,
        return_dataframe=return_dataframe
    )

@tool
def get_player_defensive_matchup_rollup(
    def_player_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    bypass_cache: bool = False,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches a defensive player's matchup statistics rolled up against all offensive players they've guarded.

    Args:
        def_player_identifier (str): Name or ID of the defensive player.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        bypass_cache (bool, optional): Ignore cached API data. Defaults to False.
        return_dataframe (bool, optional): If True, returns (JSON response, {'matchups_rollup': DataFrame}). Defaults to False.

    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, {'matchups_rollup': DataFrame}).
    """
    logger.info(f"Tool: get_player_defensive_matchup_rollup for Def: {def_player_identifier}")
    return fetch_matchups_rollup_logic(
        def_player_identifier=def_player_identifier,
        season=season,
        season_type=season_type,
        bypass_cache=bypass_cache,
        return_dataframe=return_dataframe
    )

@tool
def compare_player_shot_charts_visual(
    player_names: List[str], # List of 2 to 4 player names or IDs
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    output_format: str = "base64", # "base64" or "file"
    chart_type: str = "scatter", # "scatter", "heatmap", "zones"
    context_measure: str = "FGA",
    return_dataframe: bool = False # For the underlying shot data, not the image itself
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]]:
    """
    Generates and compares visual shot charts for a list of players.
    Returns image data (e.g., base64 string) and optionally underlying shot DataFrames.

    Args:
        player_names (List[str]): List of 2 to 4 player names or IDs.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        output_format (str, optional): Format for image output ("base64" or "file"). Defaults to "base64".
        chart_type (str, optional): Type of chart ("scatter", "heatmap", "zones"). Defaults to "scatter".
        context_measure (str, optional): Statistic to contextualize shots (e.g., "FGA", "PTS"). Defaults to "FGA".
        return_dataframe (bool, optional): If True, also returns underlying shot data as DataFrames. Defaults to False.

    Returns:
        Union[Dict[str, Any], Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]]:
            Dictionary containing image data and potentially file paths or error messages.
            If return_dataframe=True, also returns a dictionary of DataFrames.
            Example success (output_format="base64"):
            {{
                "status": "success",
                "player_charts": {{
                    "PlayerName1": {{ "image_base64": "...", "chart_type": "scatter" }},
                    "PlayerName2": {{ "image_base64": "...", "chart_type": "scatter" }}
                }},
                "comparison_chart": {{ "image_base64": "...", "chart_type": "scatter_comparison" }} (if applicable)
            }}
    """
    logger.info(f"Tool: compare_player_shot_charts_visual for players: {player_names}")
    # The visual comparison function likely handles its own dataframe retrieval if needed for plotting
    # and might return image data directly or paths to saved files.
    # The `return_dataframe` here refers to whether the *underlying shot data* used to create the charts should be returned.

    # Note: The original compare_player_shots_visual was an alias.
    # We assume compare_player_shots_visual_logic handles the parameters correctly.
    result = compare_player_shots_visual_logic(
        player_identifiers=player_names, # The logic function might expect 'player_identifiers'
        season=season,
        season_type=season_type,
        output_format=output_format,
        chart_type=chart_type,
        context_measure=context_measure,
        return_dataframe=return_dataframe
    )

    # Ensure the result structure is consistent.
    # If return_dataframe is True, the logic function should return a tuple (response_dict, dataframes_dict)
    # If return_dataframe is False, it should return just the response_dict
    if return_dataframe:
        if isinstance(result, tuple) and len(result) == 2:
            return result
        elif isinstance(result, dict): # If logic function didn't return dataframes, return empty dict for them
            return result, {}
        else:
            logger.error(f"Unexpected return type from compare_player_shots_visual_logic when return_dataframe=True: {type(result)}")
            return {"status": "error", "message": "Internal error processing visual shot chart data."}, {}
    else:
        if isinstance(result, dict):
            return result
        elif isinstance(result, tuple) and len(result) > 0 and isinstance(result[0], dict): # If it returned dataframes unexpectedly
            logger.warning("compare_player_shots_visual_logic returned dataframes when return_dataframe=False. Returning only dict.")
            return result[0]
        else:
            logger.error(f"Unexpected return type from compare_player_shots_visual_logic when return_dataframe=False: {type(result)}")
            return {"status": "error", "message": "Internal error processing visual shot chart data."} 
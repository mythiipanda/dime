from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import Toolkit
from agno.utils.log import logger

# Comparison specific stats logic functions
from ..api_tools.player_compare import fetch_player_compare_logic
from ..api_tools.teamvsplayer import fetch_teamvsplayer_logic
from ..api_tools.matchup_tools import fetch_league_season_matchups_logic, fetch_matchups_rollup_logic # Player vs Player Season and Defensive Rollup
from ..api_tools.player_comparison import compare_player_shots as compare_player_shots_visual # Visual shot chart comparison

from ..config import settings
from nba_api.stats.library.parameters import (
    SeasonTypePlayoffs, PerModeDetailed, MeasureTypeDetailedDefense,
    SeasonTypeAllStar # For matchup_tools
)


class ComparisonToolkit(Toolkit):
    def __init__(self, **kwargs):
        tools = [
            self.compare_players_stats,
            self.get_team_vs_player_comparison,
            self.get_player_vs_player_season_matchups,
            self.get_player_defensive_matchup_rollup,
            self.compare_player_shot_charts_visual,
        ]
        super().__init__(name="comparison_toolkit", tools=tools, **kwargs)

    def compare_players_stats(
        self,
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
                    Expected success structure:
                    {{
                        "parameters": {{...api parameters used...}},
                        "data_sets": {{
                            "OverallComparison": [{{ "GROUP_SET": "Overall", "DESCRIPTION": "Player A vs Player B", "MIN": float, "PTS": float, ... (many other stats) ... }}],
                            "IndividualComparison": [{{ "PLAYER_ID": int, "PLAYER_NAME": str, "MIN": float, "PTS": float, ... (many other stats) ... }}]
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys: "OverallComparison", "IndividualComparison".
                    CSV cache paths for each DataFrame included in json_string under 'dataframe_info'.
        """
        logger.info(f"ComparisonToolkit: compare_players_stats called for players {player_id_list} vs {vs_player_id_list or 'overall'}")
        # The logic function expects tuples for lru_cache
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

    def get_team_vs_player_comparison(
        self,
        team_identifier: str,
        vs_player_identifier: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular, # API uses season_type_playoffs
        per_mode: str = PerModeDetailed.totals,
        measure_type: str = MeasureTypeDetailedDefense.base,
        player_identifier: Optional[str] = None, # Player on the specified team to analyze their on/off court impact vs opponent
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
        Optionally, can further analyze the impact of one of the team's own players in this context using `player_identifier`.

        Args:
            team_identifier (str): Name, abbreviation, or ID of the team.
            vs_player_identifier (str): Name or ID of the opposing player to analyze against.
            season (str, optional): NBA season in YYYY-YY format. Defaults to current season.
            season_type (str, optional): Type of season. Defaults to "Regular Season".
                                         Possible values from SeasonTypePlayoffs enum.
            per_mode (str, optional): Statistical mode. Defaults to "Totals".
                                      Possible values from PerModeDetailed enum.
            measure_type (str, optional): Type of stats. Defaults to "Base".
                                          Possible values from MeasureTypeDetailedDefense enum.
            player_identifier (Optional[str], optional): Name or ID of a player on the primary `team_identifier` team.
                                                         If provided, stats will show the team's performance vs. `vs_player_identifier`
                                                         when this specific `player_identifier` is on/off the court.
            last_n_games (int, optional): Filter by last N games. Defaults to 0.
            month (int, optional): Filter by month (1-12). Defaults to 0.
            opponent_team_id (int, optional): Filter by opponent team ID (different from vs_player_id). Defaults to 0.
            pace_adjust (str, optional): Pace adjust stats ("Y" or "N"). Defaults to "N".
            period (int, optional): Filter by period. Defaults to 0.
            plus_minus (str, optional): Include plus-minus ("Y" or "N"). Defaults to "N".
            rank (str, optional): Include rank ("Y" or "N"). Defaults to "N".
            vs_division_nullable (Optional[str], optional): Filter by opponent's division.
            vs_conference_nullable (Optional[str], optional): Filter by opponent's conference.
            season_segment_nullable (Optional[str], optional): Filter by season segment.
            outcome_nullable (Optional[str], optional): Filter by game outcome ('W' or 'L').
            location_nullable (Optional[str], optional): Filter by game location ('Home' or 'Road').
            league_id_nullable (Optional[str], optional): League ID.
            game_segment_nullable (Optional[str], optional): Filter by game segment.
            date_from_nullable (Optional[str], optional): Start date YYYY-MM-DD.
            date_to_nullable (Optional[str], optional): End date YYYY-MM-DD.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, dictionary of DataFrames).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with team vs player comparison data or an error message.
                    Expected success structure:
                    {{
                        "team_name": str, "team_id": int, "vs_player_name": str, "vs_player_id": int,
                        "parameters": {{...api parameters used...}},
                        "overall": [{{ ... team's overall stats in games involving vs_player ... }}],
                        "on_off_court": [{{ ... team's stats when vs_player is ON/OFF court ... }}],
                        "shot_area_overall": [{{ ... team's shooting by area in games involving vs_player ... }}],
                        "shot_area_on_court": [{{ ... team's shooting by area when vs_player is ON court ... }}],
                        "shot_area_off_court": [{{ ... team's shooting by area when vs_player is OFF court ... }}],
                        "shot_distance_overall": [{{ ... team's shooting by distance ... }}],
                        "shot_distance_on_court": [{{ ... team's shooting by distance when vs_player is ON court ... }}],
                        "shot_distance_off_court": [{{ ... team's shooting by distance when vs_player is OFF court ... }}],
                        "vs_player_overall": [{{ ... direct stats of vs_player against the team ... }}]
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys: "overall", "on_off_court", "shot_area_overall", etc.
                    CSV cache paths for each DataFrame included in json_string under 'dataframe_info'.
        """
        logger.info(f"ComparisonToolkit: get_team_vs_player_comparison called for team {team_identifier} vs player {vs_player_identifier}")
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

    def get_player_vs_player_season_matchups(
        self,
        def_player_identifier: str,
        off_player_identifier: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular, # API uses season_type_playoffs
        bypass_cache: bool = False,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches season-long head-to-head matchup statistics between two specific players.
        Details how the offensive player performed when guarded by the defensive player.

        Args:
            def_player_identifier (str): Name or ID of the defensive player.
            off_player_identifier (str): Name or ID of the offensive player.
            season (str, optional): NBA season in YYYY-YY format. Defaults to current season.
            season_type (str, optional): Type of season. Defaults to "Regular Season".
                                         Possible values from SeasonTypeAllStar enum (e.g., "Regular Season", "Playoffs", "Preseason").
            bypass_cache (bool, optional): If True, ignores cached raw data for the API call. Defaults to False.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'matchups': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with player vs. player matchup data or an error message.
                    Expected success structure:
                    {{
                        "def_player_id": int, "def_player_name": str,
                        "off_player_id": int, "off_player_name": str,
                        "parameters": {{"season": str, "season_type": str}},
                        "matchups": [
                            {{
                                "MATCHUP_MIN": float, "PARTIAL_POSS": float, "PLAYER_PTS": int, // Offensive player's points
                                "OPP_PLAYER_PTS": int, // Defensive player's points (contextual, usually 0 in this direct matchup view)
                                "FGM": int, "FGA": int, "FG_PCT": float, // Offensive player's shooting when guarded by defensive player
                                "FG3M": int, "FG3A": int, "FG3_PCT": float,
                                // ... other matchup stats like AST, TOV, BLK, STL ...
                            }}
                        ]
                    }}
                If return_dataframe=True: Tuple (json_string, {{'matchups': pd.DataFrame}}).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"ComparisonToolkit: get_player_vs_player_season_matchups called for Def: {def_player_identifier} vs Off: {off_player_identifier}")
        return fetch_league_season_matchups_logic(
            def_player_identifier=def_player_identifier,
            off_player_identifier=off_player_identifier,
            season=season,
            season_type=season_type,
            bypass_cache=bypass_cache,
            return_dataframe=return_dataframe
        )

    def get_player_defensive_matchup_rollup(
        self,
        def_player_identifier: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular, # API uses season_type_playoffs
        bypass_cache: bool = False,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches matchup rollup statistics for a defensive player. This shows how various offensive players
        performed when guarded by the specified defensive player over a season.

        Args:
            def_player_identifier (str): Name or ID of the defensive player.
            season (str, optional): NBA season in YYYY-YY format. Defaults to current season.
            season_type (str, optional): Type of season. Defaults to "Regular Season".
                                         Possible values from SeasonTypeAllStar enum (e.g., "Regular Season", "Playoffs", "Preseason").
            bypass_cache (bool, optional): If True, ignores cached raw data for the API call. Defaults to False.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'rollup': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with defensive matchup rollup data or an error message.
                    Expected success structure:
                    {{
                        "def_player_id": int, "def_player_name": str,
                        "parameters": {{"season": str, "season_type": str}},
                        "rollup": [
                            {{
                                "OFF_PLAYER_ID": int, "OFF_PLAYER_NAME": str, "MATCHUP_MIN": float,
                                "PARTIAL_POSS": float, "FGM": int, "FGA": int, "FG_PCT": float, ...
                                // Stats reflect how the OFF_PLAYER performed against the DEF_PLAYER
                            }}
                        ]
                    }}
                If return_dataframe=True: Tuple (json_string, {{'rollup': pd.DataFrame}}).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"ComparisonToolkit: get_player_defensive_matchup_rollup called for Def Player: {def_player_identifier}")
        return fetch_matchups_rollup_logic(
            def_player_identifier=def_player_identifier,
            season=season,
            season_type=season_type,
            bypass_cache=bypass_cache,
            return_dataframe=return_dataframe
        )

    def compare_player_shot_charts_visual(
        self,
        player_names: List[str], # List of 2 to 4 player names or IDs
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = "Regular Season",
        output_format: str = "base64", # "base64" or "file"
        chart_type: str = "scatter", # "scatter", "heatmap", "zones"
        context_measure: str = "FGA",
        return_dataframe: bool = False
    ) -> Union[Dict[str, Any], Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]]:
        """
        Compares shot charts visually for multiple players (2 to 4 players).
        Generates scatter plots, heatmaps, or zone efficiency bar charts for comparison.

        Args:
            player_names (List[str]): List of 2 to 4 player names or IDs to compare.
            season (str, optional): NBA season in YYYY-YY format. Defaults to current season.
            season_type (str, optional): Type of season. Defaults to "Regular Season".
                                         Possible: "Regular Season", "Playoffs", "Pre Season", "All Star".
            output_format (str, optional): Output format for the visualization.
                                           Defaults to "base64". Possible: "base64", "file".
            chart_type (str, optional): Type of comparison chart. Defaults to "scatter".
                                        Possible: "scatter", "heatmap", "zones".
            context_measure (str, optional): Context measure for shot chart data fetching (e.g., "FGA", "FGM").
                                             Defaults to "FGA".
            return_dataframe (bool, optional): If True, also returns underlying shot DataFrames for each player
                                               and a combined zone breakdown DataFrame. Defaults to False.

        Returns:
            Union[Dict[str, Any], Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: Dictionary containing visualization data (e.g., "image_data" or "file_path") and metadata.
                    Example for base64 scatter comparison:
                    {{
                        "image_data": "data:image/png;base64,...",
                        "chart_type": "comparison_scatter" // or comparison_heatmap, comparison_zones
                    }}
                If return_dataframe=True: Tuple (visualization_dict, dataframes_dict).
                    dataframes_dict keys: `shots_{{player_id}}` and `league_avg_{{player_id}}` for each player,
                                          and `zone_breakdown` for combined zone stats.
                    CSV cache paths for these DataFrames included in visualization_dict under 'dataframe_info'.
        """
        logger.info(f"ComparisonToolkit: compare_player_shot_charts_visual called for players: {player_names}, chart: {chart_type}")
        return compare_player_shots_visual(
            player_names=player_names,
            season=season,
            season_type=season_type,
            output_format=output_format,
            chart_type=chart_type,
            context_measure=context_measure,
            return_dataframe=return_dataframe
        )
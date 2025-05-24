from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import Toolkit
from agno.utils.log import logger

# Advanced Analytics logic functions
from ..api_tools.advanced_metrics import fetch_player_advanced_analysis_logic
from ..api_tools.player_shot_charts import fetch_player_shotchart_logic # Individual player shot chart
from ..api_tools.advanced_shot_charts import process_shot_data_for_visualization as generate_advanced_shot_chart_visual
from ..api_tools.player_comparison import compare_player_shots as compare_player_shots_visual # Visual shot chart comparison


from ..config import settings
from nba_api.stats.library.parameters import SeasonTypeAllStar

class AdvancedAnalyticsToolkit(Toolkit):
    def __init__(self, **kwargs):
        tools = [
            self.get_player_advanced_analysis,
            self.get_player_shot_chart_data,
            self.generate_player_advanced_shot_chart_visualization,
            self.compare_players_shot_charts_visualization,
        ]
        super().__init__(name="advanced_analytics_toolkit", tools=tools, **kwargs)

    def get_player_advanced_analysis(
        self,
        player_name: str,
        season: Optional[str] = None,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches advanced metrics, RAPTOR-style ratings (if available), skill grades,
        and similar players for a specified player.

        Args:
            player_name (str): The full name or ID of the player to analyze.
            season (Optional[str], optional): The NBA season in YYYY-YY format (e.g., "2023-24").
                                              If None, uses the current season defined in settings.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, dictionary of DataFrames).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with advanced analysis or an error.
                    Expected success structure:
                    {{
                        "player_name": str, "player_id": int,
                        "advanced_metrics": {{
                            // RAPTOR metrics if available (e.g., RAPTOR_OFFENSE, RAPTOR_DEFENSE, WAR, ELO_RATING)
                            // OR Fallback metrics (e.g., ORTG, DRTG, NETRTG, USG_PCT, NBA_PLUS, ELO_RATING)
                        }},
                        "skill_grades": {{
                            "perimeter_shooting": str, "interior_scoring": str, "playmaking": str, ... (grades A+ to F)
                        }},
                        "similar_players": [
                            {{"player_id": int, "player_name": str, "similarity_score": float}}, ...
                        ]
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys depend on RAPTOR availability:
                    - If RAPTOR: 'raptor_metrics', 'skill_grades', 'similar_players', 'basic_stats', 'player_basic_stats'.
                    - Else (Fallback): 'advanced_metrics', 'skill_grades', 'similar_players'.
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"AdvancedAnalyticsToolkit: get_player_advanced_analysis called for {player_name}, season {season or settings.CURRENT_NBA_SEASON}")
        return fetch_player_advanced_analysis_logic(
            player_name=player_name,
            season=season,
            return_dataframe=return_dataframe
        )

    def get_player_shot_chart_data(
        self,
        player_name: str,
        season: Optional[str] = None,
        season_type: str = SeasonTypeAllStar.regular,
        context_measure: str = "FGA", # Field Goal Attempts
        last_n_games: int = 0,
        return_dataframe: bool = False,
        # Include all other optional params from fetch_player_shotchart_logic
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
        point_diff_nullable: Optional[str] = None,
        position_nullable: Optional[str] = None,
        range_type_nullable: Optional[str] = None,
        start_period_nullable: Optional[str] = None,
        start_range_nullable: Optional[str] = None,
        end_period_nullable: Optional[str] = None,
        end_range_nullable: Optional[str] = None
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches detailed shot chart data for a specified player, including shot locations and zone analysis.
        This tool returns the raw data; for a generated image, use `generate_player_advanced_shot_chart_visualization`.

        Args:
            player_name (str): The full name or ID of the player.
            season (Optional[str], optional): NBA season in YYYY-YY format. Defaults to current season.
            season_type (str, optional): Type of season. Defaults to "Regular Season".
                                         Possible: "Regular Season", "Playoffs", "Pre Season", "All Star".
            context_measure (str, optional): Statistical measure for API context. Defaults to "FGA".
                                             Possible: "FGA", "FGM", "FG_PCT", etc.
            last_n_games (int, optional): Filter by last N games. Defaults to 0 (all games).
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.
            league_id (str, optional): League ID. Defaults to "00".
            month (int, optional): Month filter. Defaults to 0.
            opponent_team_id (int, optional): Opponent team ID. Defaults to 0.
            period (int, optional): Period filter. Defaults to 0.
            // ... (other optional filters from the logic function signature)

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with shot chart data, zone analysis, and overall stats.
                    Expected success structure:
                    {{
                        "player_name": str, "player_id": int, "team_name": str, "team_id": int,
                        "season": str, "season_type": str,
                        "shots": [{{ "x": float, "y": float, "made": bool, "value": int, "shot_type": str, "shot_zone": str, ... }}],
                        "zones": [{{ "zone": str, "attempts": int, "made": int, "percentage": float, "leaguePercentage": float, ... }}],
                        "overall_stats": {{ "total_shots": int, "made_shots": int, "field_goal_percentage": float }},
                        "visualization_path": Optional[str], // Path if generated by underlying logic, usually None for this data-focused tool
                        "visualization_error": Optional[str]
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys: 'shots' (processed), 'zones', 'raw_shots' (from API), 'league_averages'.
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"AdvancedAnalyticsToolkit: get_player_shot_chart_data called for {player_name}, season {season or settings.CURRENT_NBA_SEASON}")
        return fetch_player_shotchart_logic(
            player_name=player_name, season=season, season_type=season_type,
            context_measure=context_measure, last_n_games=last_n_games, return_dataframe=return_dataframe,
            league_id=league_id, month=month, opponent_team_id=opponent_team_id, period=period,
            vs_division_nullable=vs_division_nullable, vs_conference_nullable=vs_conference_nullable,
            season_segment_nullable=season_segment_nullable, outcome_nullable=outcome_nullable,
            location_nullable=location_nullable, game_segment_nullable=game_segment_nullable,
            date_to_nullable=date_to_nullable, date_from_nullable=date_from_nullable,
            game_id_nullable=game_id_nullable, player_position_nullable=player_position_nullable,
            rookie_year_nullable=rookie_year_nullable, context_filter_nullable=context_filter_nullable,
            clutch_time_nullable=clutch_time_nullable, ahead_behind_nullable=ahead_behind_nullable,
            point_diff_nullable=point_diff_nullable, position_nullable=position_nullable,
            range_type_nullable=range_type_nullable, start_period_nullable=start_period_nullable,
            start_range_nullable=start_range_nullable, end_period_nullable=end_period_nullable,
            end_range_nullable=end_range_nullable
        )

    def generate_player_advanced_shot_chart_visualization(
        self,
        player_name: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = "Regular Season",
        chart_type: str = "scatter", # "scatter", "heatmap", "hexbin", "animated", "frequency", "distance"
        output_format: str = "base64", # "base64" or "file"
        use_cache: bool = True,
        return_dataframe: bool = False # For underlying shot data
    ) -> Union[Dict[str, Any], Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]]:
        """
        Generates an advanced shot chart visualization for a player (scatter, heatmap, hexbin, animated, frequency, or distance chart).
        The visualization is returned as base64 encoded data or a file path.

        Args:
            player_name (str): Name or ID of the player.
            season (str, optional): NBA season in YYYY-YY format. Defaults to current season.
            season_type (str, optional): Type of season. Defaults to "Regular Season".
                                         Possible: "Regular Season", "Playoffs", "Pre Season", "All Star".
            chart_type (str, optional): Type of chart to create. Defaults to "scatter".
                                        Possible: "scatter", "heatmap", "hexbin", "animated", "frequency", "distance".
            output_format (str, optional): Output format for the visualization. Defaults to "base64".
                                           Possible: "base64", "file".
            use_cache (bool, optional): Whether to use cached visualizations if available. Defaults to True.
            return_dataframe (bool, optional): If True, also returns the underlying shot DataFrames ('shots', 'league_averages')
                                               used to generate the visualization. Defaults to False.

        Returns:
            Union[Dict[str, Any], Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: Dictionary containing visualization data or an error message.
                    Example for base64 scatter:
                    {{
                        "image_data": "data:image/png;base64,...", // or "animation_data" for GIF
                        "chart_type": "scatter"
                    }}
                    Example for file output:
                    {{
                        "file_path": "/path/to/shotchart_player_season.png",
                        "chart_type": "scatter"
                    }}
                If return_dataframe=True: Tuple (visualization_dict, dataframes_dict).
                    dataframes_dict keys: 'shots', 'league_averages'.
                    CSV cache paths for these DataFrames included in visualization_dict under 'dataframe_info'.
        """
        logger.info(f"AdvancedAnalyticsToolkit: generate_player_advanced_shot_chart_visualization called for {player_name}, chart_type: {chart_type}")
        return generate_advanced_shot_chart_visual(
            player_name=player_name,
            season=season,
            season_type=season_type,
            chart_type=chart_type,
            output_format=output_format,
            use_cache=use_cache,
            return_dataframe=return_dataframe
        )

    def compare_players_shot_charts_visualization(
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
            output_format (str, optional): Output format ("base64" or "file"). Defaults to "base64".
            chart_type (str, optional): Type of comparison chart ("scatter", "heatmap", "zones"). Defaults to "scatter".
            context_measure (str, optional): Context measure for shot chart data fetching. Defaults to "FGA".
            return_dataframe (bool, optional): If True, also returns underlying shot DataFrames for each player
                                               and a combined zone breakdown DataFrame. Defaults to False.

        Returns:
            Union[Dict[str, Any], Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: Dictionary containing visualization data or an error message.
                    Example for base64 scatter comparison:
                    {{
                        "image_data": "data:image/png;base64,...",
                        "chart_type": "comparison_scatter" // or comparison_heatmap, comparison_zones
                    }}
                If return_dataframe=True: Tuple (visualization_dict, dataframes_dict).
                    dataframes_dict keys: `shots_{player_id}` and `league_avg_{player_id}` for each player,
                                          and `zone_breakdown` for combined zone stats.
                    CSV cache paths for these DataFrames included in visualization_dict under 'dataframe_info'.
        """
        logger.info(f"AdvancedAnalyticsToolkit: compare_players_shot_charts_visualization called for players: {player_names}, chart_type: {chart_type}")
        return compare_player_shots_visual(
            player_names=player_names,
            season=season,
            season_type=season_type,
            output_format=output_format,
            chart_type=chart_type,
            context_measure=context_measure,
            return_dataframe=return_dataframe
        )
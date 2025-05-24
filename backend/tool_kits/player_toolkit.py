from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import Toolkit
from agno.utils.log import logger

# Player specific stats logic functions
from ..api_tools.analyze import analyze_player_stats_logic
from ..api_tools.player_aggregate_stats import fetch_player_stats_logic
from ..api_tools.player_career_data import fetch_player_career_stats_logic, fetch_player_awards_logic
from ..api_tools.player_clutch import fetch_player_clutch_stats_logic
from ..api_tools.player_common_info import fetch_player_info_logic, get_player_headshot_url
from ..api_tools.player_dashboard_game import fetch_player_dashboard_game_splits_logic
from ..api_tools.player_dashboard_general import fetch_player_dashboard_general_splits_logic
from ..api_tools.player_dashboard_lastn import fetch_player_dashboard_lastn_games_logic
from ..api_tools.player_dashboard_shooting import fetch_player_dashboard_shooting_splits_logic
# Note: player_estimated_metrics.py contains league-wide data. Player-specific estimated metrics are part of advanced_metrics.py.
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


class PlayerToolkit(Toolkit):
    def __init__(self, **kwargs):
        tools = [
            self.analyze_player_dashboard_stats,
            self.get_player_aggregate_stats,
            self.get_player_career_stats,
            self.get_player_awards,
            self.get_player_clutch_stats,
            self.get_player_common_info,
            self.get_player_headshot_image_url,
            self.get_player_dashboard_by_game_splits,
            self.get_player_dashboard_by_general_splits,
            self.get_player_dashboard_by_last_n_games,
            self.get_player_dashboard_by_shooting_splits,
            self.get_player_fantasy_profile,
            self.get_player_fantasy_profile_bar_graph,
            self.get_player_gamelog,
            self.get_player_game_streaks,
            self.get_player_passing_stats,
            self.get_player_rebounding_stats,
            self.get_player_shooting_tracking_stats,
            self.get_player_career_stats_by_college,
        ]
        super().__init__(name="player_toolkit", tools=tools, **kwargs)

    def analyze_player_dashboard_stats(
        self,
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
            season_type (str, optional): Type of season.
                                         Defaults to "Regular Season".
                                         Possible values: "Regular Season", "Playoffs", "Pre Season".
            per_mode (str, optional): Statistical mode.
                                      Defaults to "PerGame".
                                      Possible values from PerModeDetailed enum (e.g., "PerGame", "Totals", "Per36", "Per100Possessions").
            league_id (str, optional): League ID.
                                       Defaults to "00" (NBA).
                                       Possible values from LeagueID enum (e.g., "00" for NBA, "10" for WNBA, "20" for G-League).
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'overall_dashboard': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string of overall dashboard stats or error.
                    Expected success structure:
                    {{
                        "player_name": str, "player_id": int, "season": str, "season_type": str,
                        "per_mode": str, "league_id": str,
                        "overall_dashboard_stats": {{
                            "GROUP_SET": str, "PLAYER_ID": int, "PLAYER_NAME": str, "GP": int,
                            "W": int, "L": int, "W_PCT": float, "MIN": float, "FGM": float, "FGA": float,
                            "FG_PCT": float, "FG3M": float, "FG3A": float, "FG3_PCT": float,
                            "FTM": float, "FTA": float, "FT_PCT": float, "OREB": float, "DREB": float,
                            "REB": float, "AST": float, "TOV": float, "STL": float, "BLK": float,
                            "BLKA": float, "PF": float, "PFD": float, "PTS": float, "PLUS_MINUS": float,
                            "NBA_FANTASY_PTS": Optional[float], "DD2": Optional[int], "TD3": Optional[int],
                            ... (other rank fields might be present) ...
                        }}
                    }}
                    Returns {{"overall_dashboard_stats": {{}}}} if no data.
                If return_dataframe=True: Tuple (json_string, {{'overall_dashboard': pd.DataFrame}}).
                    DataFrame contains detailed dashboard stats for the player.
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: analyze_player_dashboard_stats called for {player_name}, season {season}")
        return analyze_player_stats_logic(
            player_name=player_name,
            season=season,
            season_type=season_type,
            per_mode=per_mode,
            league_id=league_id,
            return_dataframe=return_dataframe
        )

    def get_player_aggregate_stats(
        self,
        player_name: str,
        season: Optional[str] = None, # Season for game log part
        season_type: str = SeasonTypeAllStar.regular, # Season type for game log part
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Aggregates various player statistics including common info, career stats,
        game logs for a specified season, and awards history.

        Args:
            player_name (str): The name or ID of the player.
            season (Optional[str], optional): The season for which to fetch game logs (YYYY-YY format).
                                              Defaults to the current NBA season if None.
            season_type (str, optional): The type of season for game logs.
                                         Defaults to "Regular Season".
                                         Possible values: "Regular Season", "Playoffs", "Pre Season", "All Star".
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, Dict of DataFrames).
                                               DataFrames include 'player_info', 'headline_stats', 'available_seasons',
                                               'season_totals_regular_season', 'career_totals_regular_season',
                                               'season_totals_post_season', 'career_totals_post_season',
                                               'gamelog', 'awards'.
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string of aggregated player stats or error.
                    Expected success structure:
                    {{
                        "player_name": str, "player_id": int,
                        "season_requested_for_gamelog": str,
                        "season_type_requested_for_gamelog": str,
                        "info": {{ ... (player biographical data, team, position, etc.) ... }},
                        "headline_stats": {{ ... (PTS, REB, AST for current season) ... }},
                        "available_seasons": [{{ "SEASON_ID": str, ... }}],
                        "career_stats": {{
                            "season_totals_regular_season": [{{ ... regular season stats per season ... }}],
                            "career_totals_regular_season": {{ ... career aggregate regular season stats ... }},
                            "season_totals_post_season": [{{ ... post-season stats per season ... }}],
                            "career_totals_post_season": {{ ... career aggregate post-season stats ... }}
                        }},
                        "season_gamelog": [{{ ... game log data for specified season and type ... }}],
                        "awards": [{{ ... award details like DESCRIPTION, SEASON, TYPE ... }}]
                    }}
                If return_dataframe=True: Tuple (json_string, Dict of DataFrames).
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: get_player_aggregate_stats called for {player_name}, gamelog season {season or settings.CURRENT_NBA_SEASON}")
        return fetch_player_stats_logic(
            player_name=player_name,
            season=season,
            season_type=season_type,
            return_dataframe=return_dataframe
        )

    def get_player_career_stats(
        self,
        player_name: str,
        per_mode: str = PerModeDetailed.per_game,
        league_id_nullable: Optional[str] = None,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches player career statistics including regular season and postseason totals, broken down by season and career.

        Args:
            player_name (str): The name or ID of the player.
            per_mode (str, optional): Statistical mode for career/season stats.
                                      Defaults to "PerGame".
                                      Possible values from PerModeDetailed or PerMode36 enums (e.g., "PerGame", "Totals", "Per36").
            league_id_nullable (Optional[str], optional): League ID to filter data (e.g., "00" for NBA).
                                                         Defaults to None (all applicable leagues for the player).
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, dictionary of DataFrames).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: A JSON string containing player career statistics or an error message.
                    Expected success structure:
                    {{
                        "player_name": str, "player_id": int, "per_mode_requested": str,
                        "data_retrieved_mode": str, "league_id": Optional[str],
                        "season_totals_regular_season": [{{ "SEASON_ID": str, "TEAM_ABBREVIATION": str, "PTS": float, ... }}],
                        "career_totals_regular_season": {{ "PLAYER_ID": int, "GP": int, "PTS": float, ... }},
                        "season_totals_post_season": [{{ ... similar to regular season totals ... }}],
                        "career_totals_post_season": {{ ... similar to career regular season totals ... }}
                    }}
                If return_dataframe=True: A tuple (json_string, dataframes_dict).
                    dataframes_dict keys: 'season_totals_regular_season', 'career_totals_regular_season',
                                          'season_totals_post_season', 'career_totals_post_season'.
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: get_player_career_stats called for {player_name}, per_mode {per_mode}")
        return fetch_player_career_stats_logic(
            player_name=player_name,
            per_mode=per_mode,
            league_id_nullable=league_id_nullable,
            return_dataframe=return_dataframe
        )

    def get_player_awards(
        self,
        player_name: str,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches a list of awards received by the specified player throughout their career.

        Args:
            player_name (str): The name or ID of the player.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'awards': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: A JSON string containing a list of player awards or an error message.
                    Expected success structure:
                    {{
                        "player_name": str, "player_id": int,
                        "awards": [
                            {{
                                "DESCRIPTION": str, "ALL_NBA_TEAM_NUMBER": Optional[int],
                                "SEASON": str, "MONTH": Optional[int], "WEEK": Optional[int],
                                "CONFERENCE": Optional[str], "TYPE": str, "SUBTYPE1": Optional[str],
                                "PLAYER_ID": int, "PERSON_ID": int, "TEAM": str, "AWARD_ID": str
                            }},
                            ...
                        ]
                    }}
                If return_dataframe=True: A tuple (json_string, {{'awards': pd.DataFrame}}).
                    The DataFrame contains detailed information for each award.
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: get_player_awards called for {player_name}")
        return fetch_player_awards_logic(
            player_name=player_name,
            return_dataframe=return_dataframe
        )

    def get_player_clutch_stats(
        self,
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
        Fetches player clutch performance statistics using the PlayerDashboardByClutch endpoint.
        Various clutch scenarios are returned as different data sets within the response.

        Args:
            player_name (str): Name or ID of the player.
            season (str, optional): Season YYYY-YY. Defaults to current NBA season.
            season_type (str, optional): Season type. Defaults to "Regular Season".
                                         Possible values from SeasonTypeAllStar enum: "Regular Season", "Playoffs", "Pre Season".
            measure_type (str, optional): Type of stats. Defaults to "Base".
                                          Possible values from MeasureTypeDetailed enum (e.g., "Base", "Advanced", "Scoring").
            per_mode (str, optional): Statistical mode. Defaults to "Totals".
                                      Possible values from PerModeDetailed enum.
            league_id (Optional[str], optional): League ID. Defaults to "00" (NBA).
            plus_minus (str, optional): Flag for plus-minus stats ("Y" or "N"). Defaults to "N".
            pace_adjust (str, optional): Flag for pace adjustment ("Y" or "N"). Defaults to "N".
            rank (str, optional): Flag for ranking ("Y" or "N"). Defaults to "N".
            last_n_games (int, optional): Filter by last N games. Defaults to 0 (all games).
            month (int, optional): Filter by month (1-12). Defaults to 0 (all months).
            opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0 (all opponents).
            period (int, optional): Filter by period (e.g., 1, 2, 3, 4 for quarters, 0 for all). Defaults to 0.
            shot_clock_range_nullable (Optional[str], optional): Filter by shot clock range (e.g., '24-22', '4-0 Very Late').
            game_segment_nullable (Optional[str], optional): Filter by game segment (e.g., 'First Half', 'Overtime').
            location_nullable (Optional[str], optional): Filter by location ('Home' or 'Road').
            outcome_nullable (Optional[str], optional): Filter by game outcome ('W' or 'L').
            vs_conference_nullable (Optional[str], optional): Filter by opponent conference (e.g., 'East', 'West').
            vs_division_nullable (Optional[str], optional): Filter by opponent division (e.g., 'Atlantic', 'Pacific').
            season_segment_nullable (Optional[str], optional): Filter by season segment (e.g., 'Post All-Star').
            date_from_nullable (Optional[str], optional): Start date filter (YYYY-MM-DD).
            date_to_nullable (Optional[str], optional): End date filter (YYYY-MM-DD).
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, dictionary of DataFrames).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with clutch stats dashboards or an error message.
                    Expected success structure:
                    {{
                        "player_name": str, "player_id": int,
                        "parameters_used": {{ ... api parameters ...}},
                        "data_sets": {{
                            "OverallPlayerDashboard": [{{ ... stats ... }}],
                            "Last5Min5PtPlayerDashboard": [{{ ... stats ... }}],
                            "Last3Min5PtPlayerDashboard": [{{ ... stats ... }}],
                            "Last1Min5PtPlayerDashboard": [{{ ... stats ... }}],
                            "Last30Sec3PtPlayerDashboard": [{{ ... stats ... }}],
                            "Last10Sec3PtPlayerDashboard": [{{ ... stats ... }}],
                            "Last5MinPlusMinus5PtPlayerDashboard": [{{ ... stats ... }}],
                            "Last1MinPlusMinus5PtPlayerDashboard": [{{ ... stats ... }}]
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys match the dataset names listed above.
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: get_player_clutch_stats called for {player_name}")
        return fetch_player_clutch_stats_logic(
            player_name, season, season_type, measure_type, per_mode, league_id,
            plus_minus, pace_adjust, rank, last_n_games, month, opponent_team_id, period,
            shot_clock_range_nullable, game_segment_nullable, location_nullable,
            outcome_nullable, vs_conference_nullable, vs_division_nullable,
            season_segment_nullable, date_from_nullable, date_to_nullable, return_dataframe
        )

    def get_player_common_info(
        self,
        player_name: str,
        league_id_nullable: Optional[str] = None,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches common player information, headline stats, and available seasons.

        Args:
            player_name (str): Name or ID of the player.
            league_id_nullable (Optional[str], optional): League ID to filter results (e.g., "00" for NBA).
                                                         Defaults to None.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, dictionary of DataFrames).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: A JSON string containing player info, headline stats, and available seasons.
                    Expected success structure:
                    {{
                        "player_info": {{ "PERSON_ID": int, "DISPLAY_FIRST_LAST": str, "TEAM_NAME": str, ... }},
                        "headline_stats": {{ "PLAYER_ID": int, "PTS": float, "REB": float, "AST": float, ... }},
                        "available_seasons": [{{ "SEASON_ID": str, "PLAYER_ID": int }}]
                    }}
                If return_dataframe=True: A tuple (json_string, dataframes_dict).
                    dataframes_dict keys: 'player_info', 'headline_stats', 'available_seasons'.
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: get_player_common_info called for {player_name}")
        return fetch_player_info_logic(
            player_name=player_name,
            league_id_nullable=league_id_nullable,
            return_dataframe=return_dataframe
        )

    def get_player_headshot_image_url(
        self,
        player_id: int
    ) -> str:
        """
        Constructs the URL for a player's headshot image.

        Args:
            player_id (int): The unique ID of the player.

        Returns:
            str: The URL string for the player's headshot.
                 Example: "https://ak-static.cms.nba.com/wp-content/uploads/headshots/nba/latest/260x190/{player_id}.png"
                 Returns an error string if player_id is invalid.
        """
        logger.info(f"PlayerToolkit: get_player_headshot_image_url called for player_id {player_id}")
        try:
            return get_player_headshot_url(player_id=player_id)
        except ValueError as e:
            return str(e) # Return error message as string

    def get_player_dashboard_by_game_splits(
        self,
        player_name: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = "Regular Season",
        measure_type: str = "Base",
        per_mode: str = "Totals",
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches player dashboard statistics by game splits (Overall, ByHalf, ByPeriod, ByScoreMargin, ByActualMargin).

        Args:
            player_name (str): Name or ID of the player.
            season (str, optional): Season YYYY-YY. Defaults to current NBA season.
            season_type (str, optional): Season type. Defaults to "Regular Season".
                                         Possible values: "Regular Season", "Playoffs", "Pre Season", "All Star".
            measure_type (str, optional): Statistical category. Defaults to "Base".
                                          Possible values from MeasureTypeDetailed enum.
            per_mode (str, optional): Per mode for stats. Defaults to "Totals".
                                      Possible values from PerModeDetailed enum.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, dictionary of DataFrames).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with dashboard data or error.
                    Expected success structure:
                    {{
                        "player_name": str, "player_id": int, "parameters": {{...}},
                        "data_sets": {{
                            "OverallPlayerDashboard": [{{ ... stats ... }}],
                            "ByHalfPlayerDashboard": [{{ ... stats ... }}],
                            "ByPeriodPlayerDashboard": [{{ ... stats ... }}],
                            "ByScoreMarginPlayerDashboard": [{{ ... stats ... }}],
                            "ByActualMarginPlayerDashboard": [{{ ... stats ... }}]
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys match the dataset names listed above.
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: get_player_dashboard_by_game_splits called for {player_name}")
        return fetch_player_dashboard_game_splits_logic(
            player_name=player_name,
            season=season,
            season_type=season_type,
            measure_type=measure_type,
            per_mode=per_mode,
            return_dataframe=return_dataframe
        )

    def get_player_dashboard_by_general_splits(
        self,
        player_name: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = "Regular Season",
        measure_type: str = "Base",
        per_mode: str = "Totals",
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches player dashboard statistics by general splits (Location, Wins/Losses, Month, Pre/Post All-Star, Days Rest, Starting Position).

        Args:
            player_name (str): Name or ID of the player.
            season (str, optional): Season YYYY-YY. Defaults to current NBA season.
            season_type (str, optional): Season type. Defaults to "Regular Season".
            measure_type (str, optional): Statistical category. Defaults to "Base".
            per_mode (str, optional): Per mode for stats. Defaults to "Totals".
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, dictionary of DataFrames).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with dashboard data or error.
                    Expected success structure:
                    {{
                        "player_name": str, "player_id": int, "parameters": {{...}},
                        "data_sets": {{
                            "OverallPlayerDashboard": [{{ ... stats ... }}],
                            "LocationPlayerDashboard": [{{ ... stats ... }}],
                            // ... other general split dashboards
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    DataFrames dict keys match the dataset names.
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: get_player_dashboard_by_general_splits called for {player_name}")
        return fetch_player_dashboard_general_splits_logic(
            player_name=player_name,
            season=season,
            season_type=season_type,
            measure_type=measure_type,
            per_mode=per_mode,
            return_dataframe=return_dataframe
        )

    def get_player_dashboard_by_last_n_games(
        self,
        player_name: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = "Regular Season",
        measure_type: str = "Base",
        per_mode: str = "Totals",
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches player dashboard statistics by last N games splits (Overall, Last 5, Last 10, Last 15, Last 20, GameNumber).

        Args:
            player_name (str): Name or ID of the player.
            season (str, optional): Season YYYY-YY. Defaults to current NBA season.
            season_type (str, optional): Season type. Defaults to "Regular Season".
            measure_type (str, optional): Statistical category. Defaults to "Base".
            per_mode (str, optional): Per mode for stats. Defaults to "Totals".
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, dictionary of DataFrames).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with dashboard data or error.
                    Expected success structure:
                    {{
                        "player_name": str, "player_id": int, "parameters": {{...}},
                        "data_sets": {{
                            "OverallPlayerDashboard": [{{ ... stats ... }}],
                            "Last5PlayerDashboard": [{{ ... stats ... }}],
                            // ... other LastNGames split dashboards
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    DataFrames dict keys match the dataset names.
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: get_player_dashboard_by_last_n_games called for {player_name}")
        return fetch_player_dashboard_lastn_games_logic(
            player_name=player_name,
            season=season,
            season_type=season_type,
            measure_type=measure_type,
            per_mode=per_mode,
            return_dataframe=return_dataframe
        )

    def get_player_dashboard_by_shooting_splits(
        self,
        player_name: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = "Regular Season",
        measure_type: str = "Base",
        per_mode: str = "Totals",
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches player dashboard statistics by shooting splits (Shot Type, Shot Area, Shot Distance, Assisted/Unassisted).

        Args:
            player_name (str): Name or ID of the player.
            season (str, optional): Season YYYY-YY. Defaults to current NBA season.
            season_type (str, optional): Season type. Defaults to "Regular Season".
            measure_type (str, optional): Statistical category. Defaults to "Base".
            per_mode (str, optional): Per mode for stats. Defaults to "Totals".
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, dictionary of DataFrames).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with dashboard data or error.
                    Expected success structure:
                    {{
                        "player_name": str, "player_id": int, "parameters": {{...}},
                        "data_sets": {{
                            "OverallPlayerDashboard": [{{ ... stats ... }}],
                            "Shot5FTPlayerDashboard": [{{ ... stats ... }}], // Stats for shots 0-5ft, 5-9ft, etc.
                            "ShotAreaPlayerDashboard": [{{ ... stats by court area ... }}],
                            "ShotTypePlayerDashboard": [{{ ... stats by shot type (jump, layup) ... }}],
                            // ... other shooting split dashboards
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    DataFrames dict keys match the dataset names.
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: get_player_dashboard_by_shooting_splits called for {player_name}")
        return fetch_player_dashboard_shooting_splits_logic(
            player_name=player_name,
            season=season,
            season_type=season_type,
            measure_type=measure_type,
            per_mode=per_mode,
            return_dataframe=return_dataframe
        )

    def get_player_fantasy_profile(
        self,
        player_id: str, # PlayerFantasyProfile endpoint uses player_id directly
        season: str = settings.CURRENT_NBA_SEASON,
        season_type_playoffs: str = SeasonTypeAllStar.regular,
        measure_type_base: str = MeasureTypeBase.base, # API uses MeasureTypeBase
        per_mode36: str = PerMode36.totals, # API uses PerMode36
        league_id_nullable: str = "",
        pace_adjust_no: str = "N",
        plus_minus_no: str = "N",
        rank_no: str = "N",
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches player fantasy profile data, including overall, location-based, last N games, days rest, and vs opponent stats.

        Args:
            player_id (str): The NBA Player ID.
            season (str, optional): Season YYYY-YY. Defaults to current NBA season.
            season_type_playoffs (str, optional): Season type. Defaults to "Regular Season".
                                                 Possible values from SeasonTypePlayoffs enum.
            measure_type_base (str, optional): Measure type. Defaults to "Base".
                                               Possible values from MeasureTypeBase enum (typically just "Base").
            per_mode36 (str, optional): Per mode. Defaults to "Totals".
                                        Possible values from PerMode36 enum (e.g., "Totals", "PerGame", "Per36Minutes").
            league_id_nullable (str, optional): League ID. Defaults to "" (NBA).
            pace_adjust_no (str, optional): Pace adjust flag ("Y" or "N"). Defaults to "N".
            plus_minus_no (str, optional): Plus-minus flag ("Y" or "N"). Defaults to "N".
            rank_no (str, optional): Rank flag ("Y" or "N"). Defaults to "N".
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, dictionary of DataFrames).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with player fantasy profile data or an error message.
                    Expected success structure:
                    {{
                        "parameters": {{...}},
                        "data_sets": {{
                            "Overall": [{{ ... stats ... }}],
                            "Location": [{{ ... stats by Home/Road ... }}],
                            "LastNGames": [{{ ... stats for last N games segments ... }}],
                            "DaysRest": [{{ ... stats by days rest ... }}],
                            "VsOpponent": [{{ ... stats vs specific opponents ... }}]
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys: "Overall", "Location", "LastNGames", "DaysRest", "VsOpponent".
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: get_player_fantasy_profile called for player ID {player_id}")
        return fetch_player_fantasy_profile_logic(
            player_id=player_id, season=season, season_type_playoffs=season_type_playoffs,
            measure_type_base=measure_type_base, per_mode36=per_mode36,
            league_id_nullable=league_id_nullable, pace_adjust_no=pace_adjust_no,
            plus_minus_no=plus_minus_no, rank_no=rank_no, return_dataframe=return_dataframe
        )

    def get_player_fantasy_profile_bar_graph(
        self,
        player_id: str, # PlayerFantasyProfileBarGraph endpoint uses player_id directly
        season: str = settings.CURRENT_NBA_SEASON,
        league_id_nullable: str = "",
        season_type_all_star_nullable: str = "", # API Param is season_type_all_star_nullable
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches player fantasy profile data optimized for bar graph visualization, including season and recent game stats.

        Args:
            player_id (str): The NBA Player ID.
            season (str, optional): Season YYYY-YY. Defaults to current NBA season.
            league_id_nullable (str, optional): League ID. Defaults to "" (NBA).
            season_type_all_star_nullable (str, optional): Season type. Defaults to "".
                                                          Possible values from SeasonTypeAllStar enum or "".
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, dictionary of DataFrames).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with player fantasy profile bar graph data or an error message.
                    Expected success structure:
                    {{
                        "parameters": {{...}},
                        "data_sets": {{
                            "SeasonStats": [{{ "PLAYER_ID": int, "PLAYER_NAME": str, "TEAM_ABBREVIATION": str, "FAN_DUEL_PTS": float, ... }}],
                            "RecentStats": [{{ ... similar structure for recent games ... }}]
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys: "SeasonStats", "RecentStats".
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: get_player_fantasy_profile_bar_graph called for player ID {player_id}")
        return fetch_player_fantasy_profile_bar_graph_logic(
            player_id=player_id, season=season, league_id_nullable=league_id_nullable,
            season_type_all_star_nullable=season_type_all_star_nullable, return_dataframe=return_dataframe
        )

    def get_player_gamelog(
        self,
        player_name: str,
        season: str,
        season_type: str = SeasonTypeAllStar.regular,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches player game logs for a specified player, season, and season type.

        Args:
            player_name (str): Name or ID of the player.
            season (str): NBA season YYYY-YY (e.g., "2023-24"). This is mandatory.
            season_type (str, optional): Season type. Defaults to "Regular Season".
                                         Possible values from SeasonTypeAllStar enum: "Regular Season", "Playoffs", "Pre Season", "All Star".
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'gamelog': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: A JSON string containing a list of game logs or an error message.
                    Expected success structure:
                    {{
                        "player_name": str, "player_id": int, "season": str, "season_type": str,
                        "gamelog": [
                            {{
                                "GAME_ID": str, "GAME_DATE": str, "MATCHUP": str, "WL": str,
                                "MIN": int, "FGM": int, ... (other standard box score stats) ..., "PLUS_MINUS": float
                            }},
                            ...
                        ]
                    }}
                If return_dataframe=True: A tuple (json_string, {{'gamelog': pd.DataFrame}}).
                    The DataFrame contains detailed stats for each game.
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: get_player_gamelog called for {player_name}, season {season}")
        return fetch_player_gamelog_logic(
            player_name=player_name,
            season=season,
            season_type=season_type,
            return_dataframe=return_dataframe
        )

    def get_player_game_streaks(
        self,
        player_id_nullable: str = "",
        season_nullable: str = "",
        season_type_nullable: str = "", # From PlayerGameStreakFinder params
        league_id_nullable: str = "",
        active_streaks_only_nullable: str = "",
        location_nullable: str = "",
        outcome_nullable: str = "",
        gt_pts_nullable: str = "", # Example of a stat-specific filter
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches player game streak data. Can be used for a specific player or league-wide.

        Args:
            player_id_nullable (str, optional): Player ID to filter for specific player streaks. Defaults to "" (league-wide).
            season_nullable (str, optional): Season YYYY-YY. Defaults to "" (all seasons).
            season_type_nullable (str, optional): Season type. Defaults to "".
                                                 Possible: "Regular Season", "Playoffs", "".
            league_id_nullable (str, optional): League ID. Defaults to "" (NBA "00").
                                                Possible: "00", "10" (WNBA), "".
            active_streaks_only_nullable (str, optional): Filter for active streaks ("Y" or "N"). Defaults to "".
            location_nullable (str, optional): Filter by game location ("Home", "Road"). Defaults to "".
            outcome_nullable (str, optional): Filter by game outcome ("W", "L"). Defaults to "".
            gt_pts_nullable (str, optional): Filter for streaks where points scored were greater than this value. Defaults to "".
                                             Other stat filters like gt_reb_nullable, gt_ast_nullable, etc., also exist.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'PlayerGameStreakFinder': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with player game streak data or an error message.
                    Expected success structure:
                    {{
                        "parameters": {{...}},
                        "data_sets": {{
                            "PlayerGameStreakFinder": [
                                {{
                                    "PLAYER_NAME_LAST_FIRST": str, "PLAYER_ID": int, "GAMESTREAK": int,
                                    "STARTDATE": str, "ENDDATE": str, "ACTIVESTREAK": str,
                                    "NUMSEASONS": int, "LASTSEASON": str, "FIRSTSEASON": str
                                }}, ...
                            ]
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, {{'PlayerGameStreakFinder': pd.DataFrame}}).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: get_player_game_streaks called for player ID '{player_id_nullable or 'all players'}'")
        return fetch_player_game_streak_finder_logic(
            player_id_nullable=player_id_nullable, season_nullable=season_nullable,
            season_type_nullable=season_type_nullable, league_id_nullable=league_id_nullable,
            active_streaks_only_nullable=active_streaks_only_nullable,
            location_nullable=location_nullable, outcome_nullable=outcome_nullable,
            gt_pts_nullable=gt_pts_nullable, return_dataframe=return_dataframe
        )

    def get_player_passing_stats(
        self,
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
        Fetches player passing statistics (passes made and received) for a given season.
        Requires resolving player's team_id for the specified season.

        Args:
            player_name (str): Name or ID of the player.
            season (str, optional): Season YYYY-YY. Defaults to current NBA season.
            season_type (str, optional): Season type. Defaults to "Regular Season".
            per_mode (str, optional): Statistical mode. Defaults to "PerGame".
                                      Possible values from PerModeSimple enum.
            last_n_games (int, optional): Filter by last N games. Defaults to 0.
            league_id (str, optional): League ID. Defaults to "00" (NBA).
            month (int, optional): Filter by month (1-12). Defaults to 0.
            opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0.
            vs_division_nullable (Optional[str], optional): Filter by opponent division.
            vs_conference_nullable (Optional[str], optional): Filter by opponent conference.
            season_segment_nullable (Optional[str], optional): Filter by season segment.
            outcome_nullable (Optional[str], optional): Filter by game outcome.
            location_nullable (Optional[str], optional): Filter by game location.
            date_to_nullable (Optional[str], optional): End date YYYY-MM-DD.
            date_from_nullable (Optional[str], optional): Start date YYYY-MM-DD.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, DataFrames dict).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with player passing stats or an error message.
                    Expected success structure:
                    {{
                        "player_name": str, "player_id": int, "parameters": {{...}},
                        "passes_made": [{{ "PASS_TEAMMATE_PLAYER_ID": int, "PLAYER_NAME_LAST_FIRST": str, "PASSES": int, ... }}],
                        "passes_received": [{{ "PASS_TEAMMATE_PLAYER_ID": int, "PLAYER_NAME_LAST_FIRST": str, "PASSES": int, ... }}]
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys: 'passes_made', 'passes_received'.
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: get_player_passing_stats called for {player_name}")
        return fetch_player_passing_stats_logic(
            player_name, season, season_type, per_mode, last_n_games, league_id, month,
            opponent_team_id, vs_division_nullable, vs_conference_nullable, season_segment_nullable,
            outcome_nullable, location_nullable, date_to_nullable, date_from_nullable, return_dataframe
        )

    def get_player_rebounding_stats(
        self,
        player_name: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular,
        per_mode: str = PerModeSimple.per_game,
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
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches player rebounding statistics, broken down by categories like shot type, contest level,
        shot distance, and rebound distance. Requires resolving player's team_id.

        Args:
            player_name (str): Name or ID of the player.
            season (str, optional): Season YYYY-YY. Defaults to current.
            season_type (str, optional): Season type. Defaults to "Regular Season".
            per_mode (str, optional): Statistical mode. Defaults to "PerGame".
            // ... (other args from original docstring for fetch_player_rebounding_stats_logic) ...
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames).
                JSON structure includes 'overall', 'by_shot_type', 'by_contest', 'by_shot_distance', 'by_rebound_distance'.
                DataFrames dict keys match these categories.
                CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: get_player_rebounding_stats called for {player_name}")
        return fetch_player_rebounding_stats_logic(
            player_name, season, season_type, per_mode, last_n_games, league_id, month,
            opponent_team_id, period, vs_division_nullable, vs_conference_nullable,
            season_segment_nullable, outcome_nullable, location_nullable, game_segment_nullable,
            date_to_nullable, date_from_nullable, return_dataframe
        )

    def get_player_shooting_tracking_stats(
        self,
        player_name: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular,
        per_mode: str = PerModeSimple.totals,
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
        Fetches player shooting tracking statistics (general, by shot clock, dribble, touch time, defender distance).
        Requires resolving player's team_id.

        Args:
            player_name (str): Name or ID of the player.
            season (str, optional): Season YYYY-YY. Defaults to current.
            season_type (str, optional): Season type. Defaults to "Regular Season".
            per_mode (str, optional): Statistical mode. Defaults to "Totals".
            // ... (other args from original docstring for fetch_player_shots_tracking_logic) ...
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames).
                JSON structure includes 'general_shooting', 'by_shot_clock', etc.
                DataFrames dict keys match these categories.
                CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: get_player_shooting_tracking_stats called for {player_name}")
        return fetch_player_shots_tracking_logic(
            player_name, season, season_type, per_mode, opponent_team_id, date_from, date_to,
            last_n_games, league_id, month, period, vs_division_nullable, vs_conference_nullable,
            season_segment_nullable, outcome_nullable, location_nullable, game_segment_nullable, return_dataframe
        )

    def get_player_career_stats_by_college(
        self,
        college: str,
        league_id: str = "00",
        per_mode_simple: str = PerModeSimple.totals,
        season_type_all_star: str = SeasonTypeAllStar.regular,
        season_nullable: str = "",
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches career statistics for all NBA/WNBA players from a specific college.

        Args:
            college (str): The name of the college (e.g., "Duke", "Kentucky"). This is required.
            league_id (str, optional): League ID. Defaults to "00" (NBA). Possible: "00", "10" (WNBA).
            per_mode_simple (str, optional): Statistical mode. Defaults to "Totals". Possible: "Totals", "PerGame".
            season_type_all_star (str, optional): Season type for stats. Defaults to "Regular Season". Possible: "Regular Season", "Playoffs", "All Star".
            season_nullable (str, optional): Specific season YYYY-YY to filter for, or "" for all seasons. Defaults to "".
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'PlayerCareerByCollege': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with player career stats by college or an error message.
                    Expected success structure:
                    {{
                        "parameters": {{...}},
                        "data_sets": {{
                            "PlayerCareerByCollege": [
                                {{
                                    "PLAYER_ID": int, "PLAYER_NAME": str, "COLLEGE": str,
                                    "GP": int, "MIN": float, "PTS": float, ... (other career stats) ...
                                }}, ...
                            ]
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, {{'PlayerCareerByCollege': pd.DataFrame}}).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"PlayerToolkit: get_player_career_stats_by_college called for college {college}")
        return fetch_player_career_by_college_logic(
            college=college,
            league_id=league_id,
            per_mode_simple=per_mode_simple,
            season_type_all_star=season_type_all_star,
            season_nullable=season_nullable,
            return_dataframe=return_dataframe
        )
from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import Toolkit
from agno.utils.log import logger

# Draft Combine and History logic functions
from ..api_tools.draft_combine_drill_results import fetch_draft_combine_drill_results_logic as fetch_combine_drill_results_actual_logic
from ..api_tools.draft_combine_drills import fetch_draft_combine_drills_logic # Old, potentially redundant name?
from ..api_tools.draft_combine_nonshooting import fetch_draft_combine_nonshooting_logic
from ..api_tools.draft_combine_player_anthro import fetch_draft_combine_player_anthro_logic
from ..api_tools.draft_combine_spot_shooting import fetch_draft_combine_spot_shooting_logic
from ..api_tools.draft_combine_stats import fetch_draft_combine_stats_logic # Comprehensive combine stats
from ..api_tools.league_draft import fetch_draft_history_logic # General draft history

from nba_api.stats.library.parameters import LeagueID

class DraftCombineToolkit(Toolkit):
    def __init__(self, **kwargs):
        tools = [
            self.get_draft_combine_drill_results,
            self.get_draft_combine_non_stationary_shooting_stats,
            self.get_draft_combine_player_anthropometrics,
            self.get_draft_combine_spot_shooting_stats,
            self.get_comprehensive_draft_combine_stats,
            self.get_nba_draft_history,
        ]
        super().__init__(name="draft_combine_toolkit", tools=tools, **kwargs)

    def get_draft_combine_drill_results(
        self,
        league_id: str = "00", # Typically NBA "00"
        season_year: str = "2024", # YYYY format
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches NBA Draft Combine athletic drill results data for a specific season year.
        Includes metrics like vertical leap, agility times, sprint times, and bench press.

        Args:
            league_id (str, optional): League ID. Defaults to "00" (NBA).
                                       Possible values from LeagueID enum (e.g., "00" for NBA, "10" for WNBA).
            season_year (str, optional): Season year in YYYY format (e.g., "2023" for the 2023 draft combine).
                                         Defaults to "2024".
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'DraftCombineDrillResults': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with draft combine drill results or an error message.
                    Expected success structure:
                    {{
                        "parameters": {{"league_id": str, "season_year": str}},
                        "data_sets": {{
                            "DraftCombineDrillResults": [
                                {{
                                    "PLAYER_ID": int, "PLAYER_NAME": str, "POSITION": str,
                                    "STANDING_VERTICAL_LEAP": Optional[float], "MAX_VERTICAL_LEAP": Optional[float],
                                    "LANE_AGILITY_TIME": Optional[float], "MODIFIED_LANE_AGILITY_TIME": Optional[float],
                                    "THREE_QUARTER_SPRINT": Optional[float], "BENCH_PRESS": Optional[int]
                                    // ... other potential columns like DRAFT_PICK ...
                                }}, ...
                            ]
                            // Might have other keys like "DraftCombineDrillResults_1" if API returns multiple tables.
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, {{'DraftCombineDrillResults': pd.DataFrame, ...}}).
                    The DataFrame contains detailed drill results for each player at the combine.
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"DraftCombineToolkit: get_draft_combine_drill_results called for season_year: {season_year}, league_id: {league_id}")
        # Using the more explicitly named logic function
        return fetch_combine_drill_results_actual_logic(
            league_id=league_id,
            season_year=season_year,
            return_dataframe=return_dataframe
        )

    def get_draft_combine_non_stationary_shooting_stats(
        self,
        season_year: str, # YYYY format
        league_id: str = "00",
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches draft combine non-stationary shooting data for a specific season year.
        Includes off-dribble and on-the-move shooting metrics from various distances.

        Args:
            season_year (str): Season year in YYYY format (e.g., "2023"). This is required.
            league_id (str, optional): League ID. Defaults to "00" (NBA).
                                       Possible: "00" (NBA), "10" (WNBA), "20" (G-League).
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'Results': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with non-stationary shooting data or error.
                    Expected success structure:
                    {{
                        "parameters": {{"season_year": str, "league_id": str}},
                        "data_sets": {{
                            "Results": [ // Often 'Results' or specific like 'DraftCombineNonStationaryShooting'
                                {{
                                    "PLAYER_ID": int, "PLAYER_NAME": str,
                                    "OFF_DRIB_FIFTEEN_BREAK_LEFT_MADE": Optional[int],
                                    "OFF_DRIB_FIFTEEN_BREAK_LEFT_ATTEMPT": Optional[int],
                                    "OFF_DRIB_FIFTEEN_BREAK_LEFT_PCT": Optional[float],
                                    // ... many other columns for different non-stationary shooting drills ...
                                }}, ...
                            ]
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, {{'Results': pd.DataFrame}} or similar key).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"DraftCombineToolkit: get_draft_combine_non_stationary_shooting_stats for year {season_year}")
        return fetch_draft_combine_nonshooting_logic(
            season_year=season_year,
            league_id=league_id,
            return_dataframe=return_dataframe
        )

    def get_draft_combine_player_anthropometrics(
        self,
        season_year: str, # YYYY format
        league_id: str = "00",
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches draft combine player anthropometric (physical measurement) data for a specific season year.
        Includes height (with/without shoes), weight, wingspan, standing reach, body fat %, hand length/width.

        Args:
            season_year (str): Season year in YYYY format (e.g., "2023"). This is required.
            league_id (str, optional): League ID. Defaults to "00" (NBA).
                                       Possible: "00" (NBA), "10" (WNBA), "20" (G-League).
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'Results': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with player anthropometric data or error.
                    Expected success structure:
                    {{
                        "parameters": {{"season_year": str, "league_id": str}},
                        "data_sets": {{
                            "Results": [ // Often 'Results' or specific like 'DraftCombinePlayerAnthro'
                                {{
                                    "PLAYER_ID": int, "PLAYER_NAME": str, "POSITION": str,
                                    "HEIGHT_WO_SHOES": Optional[float], "HEIGHT_W_SHOES": Optional[float],
                                    "WEIGHT": Optional[str], "WINGSPAN": Optional[float],
                                    "STANDING_REACH": Optional[float], "BODY_FAT_PCT": Optional[float],
                                    "HAND_LENGTH": Optional[float], "HAND_WIDTH": Optional[float]
                                }}, ...
                            ]
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, {{'Results': pd.DataFrame}} or similar key).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"DraftCombineToolkit: get_draft_combine_player_anthropometrics for year {season_year}")
        return fetch_draft_combine_player_anthro_logic(
            season_year=season_year,
            league_id=league_id,
            return_dataframe=return_dataframe
        )

    def get_draft_combine_spot_shooting_stats(
        self,
        season_year: str, # YYYY format
        league_id: str = "00",
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches draft combine spot-up shooting data for a specific season year.
        Includes shooting metrics from 15-foot, college range, and NBA range from various spots.

        Args:
            season_year (str): Season year in YYYY format (e.g., "2023"). This is required.
            league_id (str, optional): League ID. Defaults to "00" (NBA).
                                       Possible: "00" (NBA), "10" (WNBA), "20" (G-League).
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'Results': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with spot shooting data or error.
                    Expected success structure:
                    {{
                        "parameters": {{"season_year": str, "league_id": str}},
                        "data_sets": {{
                            "Results": [ // Often 'Results' or specific like 'DraftCombineSpotShooting'
                                {{
                                    "PLAYER_ID": int, "PLAYER_NAME": str,
                                    "FIFTEEN_CORNER_LEFT_MADE": Optional[int],
                                    "FIFTEEN_CORNER_LEFT_ATTEMPT": Optional[int],
                                    "FIFTEEN_CORNER_LEFT_PCT": Optional[float],
                                    // ... many other columns for different spot shooting drills ...
                                }}, ...
                            ]
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, {{'Results': pd.DataFrame}} or similar key).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"DraftCombineToolkit: get_draft_combine_spot_shooting_stats for year {season_year}")
        return fetch_draft_combine_spot_shooting_logic(
            season_year=season_year,
            league_id=league_id,
            return_dataframe=return_dataframe
        )

    def get_comprehensive_draft_combine_stats(
        self,
        season_year: str, # YYYY-YY format or "All Time"
        league_id: str = "00",
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches comprehensive draft combine statistics for a specific season or all time.
        Includes anthropometrics, physical testing, and shooting stats.

        Args:
            season_year (str): Season year in YYYY-YY format (e.g., "2022-23") or "All Time". This is required.
            league_id (str, optional): League ID. Defaults to "00" (NBA).
                                       Possible: "00" (NBA), "10" (WNBA), "20" (G-League).
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'DraftCombineStats': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with comprehensive combine stats or error.
                    Expected success structure:
                    {{
                        "parameters": {{"season_year": str, "league_id": str}},
                        "data_sets": {{
                            "DraftCombineStats": [ // Or a similar key if API names it differently
                                {{
                                    "PLAYER_ID": int, "PLAYER_NAME": str, "POSITION": str,
                                    "HEIGHT_WO_SHOES": Optional[float], "WEIGHT": Optional[str],
                                    "WINGSPAN": Optional[float], "STANDING_VERTICAL_LEAP": Optional[float],
                                    // ... many other columns including shooting stats ...
                                }}, ...
                            ]
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, {{'DraftCombineStats': pd.DataFrame}} or similar key).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"DraftCombineToolkit: get_comprehensive_draft_combine_stats for season {season_year}")
        return fetch_draft_combine_stats_logic(
            season_year=season_year,
            league_id=league_id,
            return_dataframe=return_dataframe
        )

    def get_nba_draft_history(
        self,
        season_year_nullable: Optional[str] = None, # YYYY format
        league_id_nullable: str = LeagueID.nba,
        team_id_nullable: Optional[int] = None,
        round_num_nullable: Optional[int] = None,
        overall_pick_nullable: Optional[int] = None,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches NBA draft history, filterable by year, league, team, round, or overall pick.

        Args:
            season_year_nullable (Optional[str], optional): Four-digit draft year (e.g., '2023').
                                                            If None, returns all years. Defaults to None.
            league_id_nullable (str, optional): League ID. Defaults to "00" (NBA).
                                                Possible from LeagueID enum.
            team_id_nullable (Optional[int], optional): NBA team ID to filter by team. Defaults to None.
            round_num_nullable (Optional[int], optional): Draft round number to filter by round. Defaults to None.
            overall_pick_nullable (Optional[int], optional): Overall pick number to filter by pick. Defaults to None.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'draft_history': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with draft history or an error message.
                    Expected success structure:
                    {{
                        "season_year_requested": str, "league_id": str,
                        "team_id_filter": Optional[int], "round_num_filter": Optional[int],
                        "overall_pick_filter": Optional[int],
                        "draft_picks": [
                            {{
                                "PERSON_ID": int, "PLAYER_NAME": str, "SEASON": str,
                                "ROUND_NUMBER": int, "ROUND_PICK": int, "OVERALL_PICK": int,
                                "TEAM_ID": int, "TEAM_CITY": str, "TEAM_NAME": str,
                                "TEAM_ABBREVIATION": str, "ORGANIZATION": str, "ORGANIZATION_TYPE": str
                            }}, ...
                        ]
                    }}
                If return_dataframe=True: Tuple (json_string, {{'draft_history': pd.DataFrame}}).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"DraftCombineToolkit: get_nba_draft_history for year {season_year_nullable or 'All'}")
        return fetch_draft_history_logic(
            season_year_nullable=season_year_nullable,
            league_id_nullable=league_id_nullable,
            team_id_nullable=team_id_nullable,
            round_num_nullable=round_num_nullable,
            overall_pick_nullable=overall_pick_nullable,
            return_dataframe=return_dataframe
        )
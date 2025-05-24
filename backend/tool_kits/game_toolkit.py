from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import Toolkit
from agno.utils.log import logger

# Game specific stats logic functions
from ..api_tools.game_boxscores import (
    fetch_boxscore_traditional_logic,
    fetch_boxscore_advanced_logic,
    fetch_boxscore_four_factors_logic,
    fetch_boxscore_usage_logic,
    fetch_boxscore_defensive_logic,
    fetch_boxscore_summary_logic,
    fetch_boxscore_misc_logic,
    fetch_boxscore_playertrack_logic,
    fetch_boxscore_scoring_logic,
    fetch_boxscore_hustle_logic
)
from ..api_tools.game_boxscore_matchups import fetch_game_boxscore_matchups_logic
from ..api_tools.game_playbyplay import fetch_playbyplay_logic
from ..api_tools.game_rotation import fetch_game_rotation_logic
from ..api_tools.game_visuals_analytics import fetch_shotchart_logic as fetch_game_shotchart_logic, fetch_win_probability_logic # Alias to avoid name clash

from ..config import settings # Not directly used here but good for consistency
from nba_api.stats.library.parameters import (
    EndPeriod, EndRange, RangeType, StartPeriod, StartRange, RunType
)


class GameToolkit(Toolkit):
    def __init__(self, **kwargs):
        tools = [
            self.get_game_boxscore_traditional,
            self.get_game_boxscore_advanced,
            self.get_game_boxscore_four_factors,
            self.get_game_boxscore_usage,
            self.get_game_boxscore_defensive,
            self.get_game_boxscore_summary,
            self.get_game_boxscore_misc,
            self.get_game_boxscore_player_tracking,
            self.get_game_boxscore_scoring,
            self.get_game_boxscore_hustle,
            self.get_game_boxscore_matchups,
            self.get_game_play_by_play,
            self.get_game_rotation_data,
            self.get_game_shotchart_data, # For overall game shot chart
            self.get_game_win_probability,
        ]
        super().__init__(name="game_toolkit", tools=tools, **kwargs)

    def get_game_boxscore_traditional(
        self,
        game_id: str,
        start_period: int = StartPeriod.default,
        end_period: int = EndPeriod.default,
        start_range: int = StartRange.default,
        end_range: int = EndRange.default,
        range_type: int = RangeType.default,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches Traditional Box Score data (V3) for a given game_id.
        Includes team stats, player stats, and starter/bench breakdowns.

        Args:
            game_id (str): The 10-digit ID of the game.
            start_period (int, optional): Starting period number (1-4 for quarters, 0 for full game). Defaults to 0.
            end_period (int, optional): Ending period number (1-4 for quarters, 0 for full game). Defaults to 0.
            start_range (int, optional): Starting range in seconds from start of game (e.g., 0). Defaults to StartRange.default.
            end_range (int, optional): Ending range in seconds from start of game (e.g., 28800 for full game). Defaults to EndRange.default.
            range_type (int, optional): Type of range. Defaults to RangeType.default.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, dictionary of DataFrames).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string containing the traditional boxscore data or an error.
                    Expected success structure:
                    {{
                        "game_id": str,
                        "teams": [{{ ... team stats ... }}],
                        "players": [{{ ... player stats ... }}],
                        "starters_bench": [{{ ... team starter/bench breakdown ... }}],
                        "parameters": {{ ... applied filters ... }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys: "teams", "players", "starters_bench".
                    CSV cache paths for each DataFrame included in json_string under 'dataframe_info'.
        """
        logger.info(f"GameToolkit: get_game_boxscore_traditional called for game_id {game_id}")
        return fetch_boxscore_traditional_logic(
            game_id=game_id, start_period=start_period, end_period=end_period,
            start_range=start_range, end_range=end_range, range_type=range_type,
            return_dataframe=return_dataframe
        )

    def get_game_boxscore_advanced(
        self,
        game_id: str,
        start_period: int = StartPeriod.default,
        end_period: int = EndPeriod.default,
        start_range: int = StartRange.default,
        end_range: int = EndRange.default,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches Advanced Box Score data (V3) for a given game_id.
        Includes advanced metrics like Offensive/Defensive Rating, PIE, USG%, etc. for players and teams.

        Args:
            game_id (str): The 10-digit ID of the game.
            start_period (int, optional): Starting period. Defaults to 0 (full game).
            end_period (int, optional): Ending period. Defaults to 0 (full game).
            start_range (int, optional): Start range in seconds. Defaults to StartRange.default.
            end_range (int, optional): End range in seconds. Defaults to EndRange.default.
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with advanced boxscore data or error.
                    Expected success structure:
                    {{
                        "game_id": str,
                        "player_stats": [{{ ... advanced player stats ... }}],
                        "team_stats": [{{ ... advanced team stats ... }}],
                        "parameters": {{ ... applied filters ... }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys: "player_stats", "team_stats".
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"GameToolkit: get_game_boxscore_advanced called for game_id {game_id}")
        return fetch_boxscore_advanced_logic(
            game_id=game_id, start_period=start_period, end_period=end_period,
            start_range=start_range, end_range=end_range, return_dataframe=return_dataframe
        )

    def get_game_boxscore_four_factors(
        self,
        game_id: str,
        start_period: int = StartPeriod.default,
        end_period: int = EndPeriod.default,
        return_dataframe: bool = False # start_range and end_range are not in logic signature, assuming not used
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches Four Factors Box Score data (V3) for a given game_id.
        Includes eFG%, FTA Rate, TOV%, OREB% for players and teams.

        Args:
            game_id (str): The 10-digit ID of the game.
            start_period (int, optional): Starting period. Defaults to 0 (full game).
            end_period (int, optional): Ending period. Defaults to 0 (full game).
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with four factors boxscore data or error.
                If return_dataframe=True: Tuple (json_string, dataframes_dict {{'player_stats': df, 'team_stats': df}}).
                CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"GameToolkit: get_game_boxscore_four_factors called for game_id {game_id}")
        return fetch_boxscore_four_factors_logic(
            game_id=game_id, start_period=start_period, end_period=end_period,
            return_dataframe=return_dataframe
        )

    def get_game_boxscore_usage(
        self,
        game_id: str,
        return_dataframe: bool = False # Other period/range filters not in logic signature
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches Usage Box Score data (V3) for a given game_id.
        Includes USG%, %FGM, %AST, %REB, etc. for players and teams.

        Args:
            game_id (str): The 10-digit ID of the game.
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with usage boxscore data or error.
                If return_dataframe=True: Tuple (json_string, dataframes_dict {{'player_usage_stats': df, 'team_usage_stats': df}}).
                CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"GameToolkit: get_game_boxscore_usage called for game_id {game_id}")
        return fetch_boxscore_usage_logic(
            game_id=game_id, return_dataframe=return_dataframe
        )

    def get_game_boxscore_defensive(
        self,
        game_id: str,
        return_dataframe: bool = False # Other period/range filters not in logic signature
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches Defensive Box Score data (V2) for a given game_id.
        Includes stats like DREB, STL, BLK, opponent FG% when player is on court.

        Args:
            game_id (str): The 10-digit ID of the game.
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with defensive boxscore data or error.
                If return_dataframe=True: Tuple (json_string, dataframes_dict {{'player_defensive_stats': df, 'team_defensive_stats': df}}).
                CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"GameToolkit: get_game_boxscore_defensive called for game_id {game_id}")
        return fetch_boxscore_defensive_logic(
            game_id=game_id, return_dataframe=return_dataframe
        )

    def get_game_boxscore_summary(
        self,
        game_id: str,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches a comprehensive summary box score (V2) for a given game_id.
        Includes game info, line score, officials, inactive players, etc.

        Args:
            game_id (str): The 10-digit ID of the game.
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with game summary data or error.
                If return_dataframe=True: Tuple (json_string, dataframes_dict with multiple keys like 'game_info', 'line_score', etc.).
                CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"GameToolkit: get_game_boxscore_summary called for game_id {game_id}")
        return fetch_boxscore_summary_logic(
            game_id=game_id, return_dataframe=return_dataframe
        )

    def get_game_boxscore_misc(
        self,
        game_id: str,
        start_period: int = StartPeriod.default,
        end_period: int = EndPeriod.default,
        start_range: int = StartRange.default,
        end_range: int = EndRange.default,
        range_type: int = RangeType.default,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches Miscellaneous Box Score data (V3) for a given game_id.
        Includes points off turnovers, second chance points, fast break points, points in paint, etc.

        Args:
            game_id (str): The 10-digit ID of the game.
            // ... (other args from fetch_boxscore_misc_logic)
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with miscellaneous boxscore data or error.
                If return_dataframe=True: Tuple (json_string, dataframes_dict {{'player_stats': df, 'team_stats': df}}).
                CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"GameToolkit: get_game_boxscore_misc called for game_id {game_id}")
        return fetch_boxscore_misc_logic(
            game_id=game_id, start_period=start_period, end_period=end_period,
            start_range=start_range, end_range=end_range, range_type=range_type,
            return_dataframe=return_dataframe
        )

    def get_game_boxscore_player_tracking(
        self,
        game_id: str,
        return_dataframe: bool = False # Other period/range filters not in logic signature
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches Player Tracking Box Score data (V3) for a given game_id.
        Includes metrics like speed, distance, touches, passes, etc.

        Args:
            game_id (str): The 10-digit ID of the game.
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with player tracking boxscore data or error.
                If return_dataframe=True: Tuple (json_string, dataframes_dict {{'player_stats': df, 'team_stats': df}}).
                CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"GameToolkit: get_game_boxscore_player_tracking called for game_id {game_id}")
        return fetch_boxscore_playertrack_logic(
            game_id=game_id, return_dataframe=return_dataframe
        )

    def get_game_boxscore_scoring(
        self,
        game_id: str,
        start_period: int = StartPeriod.default,
        end_period: int = EndPeriod.default,
        start_range: int = StartRange.default,
        end_range: int = EndRange.default,
        range_type: int = RangeType.default,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches Scoring Box Score data (V3) for a given game_id.
        Includes detailed scoring breakdowns (e.g., %PTS from 2PT, %PTS from FT, %PTS Off TOV).

        Args:
            game_id (str): The 10-digit ID of the game.
            // ... (other args from fetch_boxscore_scoring_logic)
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with scoring boxscore data or error.
                If return_dataframe=True: Tuple (json_string, dataframes_dict {{'player_stats': df, 'team_stats': df}}).
                CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"GameToolkit: get_game_boxscore_scoring called for game_id {game_id}")
        return fetch_boxscore_scoring_logic(
            game_id=game_id, start_period=start_period, end_period=end_period,
            start_range=start_range, end_range=end_range, range_type=range_type,
            return_dataframe=return_dataframe
        )

    def get_game_boxscore_hustle(
        self,
        game_id: str,
        return_dataframe: bool = False # Other period/range filters not in logic signature
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches Hustle Box Score data (V2) for a given game_id.
        Includes metrics like contested shots, deflections, charges drawn, screen assists.

        Args:
            game_id (str): The 10-digit ID of the game.
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with hustle boxscore data or error.
                If return_dataframe=True: Tuple (json_string, dataframes_dict {{'player_stats': df, 'team_stats': df}}).
                CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"GameToolkit: get_game_boxscore_hustle called for game_id {game_id}")
        return fetch_boxscore_hustle_logic(
            game_id=game_id, return_dataframe=return_dataframe
        )

    def get_game_boxscore_matchups(
        self,
        game_id: str,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches player matchup data for a given game using BoxScoreMatchupsV3 endpoint.
        Provides detailed player-vs-player matchup statistics.

        Args:
            game_id (str): The 10-digit ID of the game.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'matchups': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with matchup data or an error.
                    Expected success structure:
                    {{
                        "game_id": str,
                        "matchups": [{{ "GAME_ID": str, "DEF_PLAYER_ID": int, "DEF_PLAYER_NAME": str, "OFF_PLAYER_ID": int, "OFF_PLAYER_NAME": str, "MATCHUP_MIN": float, "PARTIAL_POSS": float, "PLAYER_PTS": int, ... }}],
                        "parameters": {{ "note": "Using BoxScoreMatchupsV3" }}
                    }}
                If return_dataframe=True: Tuple (json_string, {{'matchups': pd.DataFrame}}).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"GameToolkit: get_game_boxscore_matchups called for game_id {game_id}")
        return fetch_game_boxscore_matchups_logic(
            game_id=game_id, return_dataframe=return_dataframe
        )

    def get_game_play_by_play(
        self,
        game_id: str,
        start_period: int = 0,
        end_period: int = 0,
        event_types: Optional[List[str]] = None,
        player_name: Optional[str] = None,
        person_id: Optional[int] = None,
        team_id: Optional[int] = None,
        team_tricode: Optional[str] = None,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches play-by-play data for a game. Attempts live data first if no period filters
        are applied, otherwise falls back to or directly uses historical data (PlayByPlayV3).
        Provides granular filtering options.

        Args:
            game_id (str): The 10-digit ID of the game.
            start_period (int, optional): Starting period filter (1-4, 0 for all). Defaults to 0.
            end_period (int, optional): Ending period filter (1-4, 0 for all). Defaults to 0.
            event_types (Optional[List[str]], optional): List of event types to filter by (e.g., ['SHOT', 'REBOUND']).
                                                        Common types: SHOT, REBOUND, TURNOVER, FOUL, FREE_THROW, SUBSTITUTION, TIMEOUT, JUMP_BALL, BLOCK, STEAL, VIOLATION.
            player_name (Optional[str], optional): Filter plays by player name (case-insensitive partial match).
            person_id (Optional[int], optional): Filter plays by player ID.
            team_id (Optional[int], optional): Filter plays by team ID.
            team_tricode (Optional[str], optional): Filter plays by team tricode (e.g., 'LAL', 'BOS').
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with PBP data or error.
                    Expected success structure:
                    {{
                        "game_id": str, "has_video": bool, "source": str ("live" or "historical_v3"),
                        "filtered_periods": Optional[Dict], "filters_applied": Optional[Dict],
                        "periods": [
                            {{
                                "period": int,
                                "plays": [
                                    {{
                                        "event_num": int, "clock": str, "score": Optional[str],
                                        "team_tricode": Optional[str], "person_id": Optional[int],
                                        "player_name": Optional[str], "description": str,
                                        "action_type": str, "sub_type": Optional[str],
                                        "event_type": str (e.g., "SHOT_MADE"), "video_available": Optional[bool]
                                    }}, ...
                                ]
                            }}, ...
                        ]
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys: 'play_by_play', and 'available_video' (if source is historical_v3).
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"GameToolkit: get_game_play_by_play called for game_id {game_id}")
        return fetch_playbyplay_logic(
            game_id=game_id, start_period=start_period, end_period=end_period,
            event_types=event_types, player_name=player_name, person_id=person_id,
            team_id=team_id, team_tricode=team_tricode, return_dataframe=return_dataframe
        )

    def get_game_rotation_data(
        self,
        game_id: str,
        league_id: str = "00", # LeagueID is a parameter for GameRotation
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches game rotation data, including player in/out times and performance during stints.

        Args:
            game_id (str): The 10-digit ID of the game.
            league_id (str, optional): League ID. Defaults to "00" (NBA). Possible: "00", "10" (WNBA).
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with game rotation data or error.
                    Expected success structure:
                    {{
                        "parameters": {{"game_id": str, "league_id": str}},
                        "data_sets": {{
                            "GameRotation": [ // Player rotation stints
                                {{
                                    "GAME_ID": str, "TEAM_ID": int, "PERSON_ID": int,
                                    "PLAYER_FIRST": str, "PLAYER_LAST": str,
                                    "IN_TIME_REAL": float, "OUT_TIME_REAL": float,
                                    "PLAYER_PTS": int, "PT_DIFF": int, "USG_PCT": float, ...
                                }}
                            ],
                            "AvailableRotation": [ // Team-level rotation availability summary (often similar to GameRotation but aggregated)
                                {{ ... similar structure to GameRotation but for team totals ... }}
                            ]
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys: "GameRotation", "AvailableRotation".
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"GameToolkit: get_game_rotation_data called for game_id {game_id}")
        return fetch_game_rotation_logic(
            game_id=game_id, league_id=league_id, return_dataframe=return_dataframe
        )

    def get_game_shotchart_data(
        self,
        game_id: str,
        team_id_nullable: Optional[int] = None, # Team ID to filter shots for that team
        player_id_nullable: Optional[int] = None, # Player ID to filter shots for that player
        # ... other filters from fetch_shotchart_logic in game_visuals_analytics.py
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches shot chart data for all players in a specific NBA game.
        Can be filtered by team or player.

        Args:
            game_id (str): The 10-digit ID of the game.
            team_id_nullable (Optional[int], optional): Filter shots by a specific team ID. Defaults to None (all teams).
            player_id_nullable (Optional[int], optional): Filter shots by a specific player ID. Defaults to None (all players).
            // ... (other optional filters like period, shot_type, zone_basic, etc.)
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with game-wide shot chart data or error.
                    Expected success structure (if not filtered by player/team, it's a list of shots):
                    {{
                        "game_id": str, "teams": [{{team_id, team_name, shots: [...]}}], "league_averages": [...]
                        // If filtered, might be more specific. The logic in game_visuals_analytics.py handles this.
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict contains 'shots' and 'league_averages'. If filtered, 'shots' reflects filtered data.
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"GameToolkit: get_game_shotchart_data called for game_id {game_id}")
        # Note: The underlying logic function expects player_name, not player_id for primary lookup,
        # but the game_visuals_analytics.py version is designed for game-wide or filtered.
        # Here we assume game_id is primary, and player/team IDs are for filtering that game's data.
        return fetch_game_shotchart_logic(
            game_id=game_id,
            team_id=team_id_nullable, # Pass through directly
            player_id=player_id_nullable, # Pass through directly
            # Pass other relevant filters from signature if added to logic function
            return_dataframe=return_dataframe
        )

    def get_game_win_probability(
        self,
        game_id: str,
        run_type: str = RunType.default,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches win probability data play-by-play for a specific NBA game.

        Args:
            game_id (str): The 10-digit ID of the game.
            run_type (str, optional): Run type for win probability calculation.
                                      Defaults to "each play".
                                      Possible: "each play", "each second", "each poss".
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with game info and win probability PBP data or error.
                    Expected success structure:
                    {{
                        "game_id": str,
                        "game_info": {{ "GAME_ID": str, "GAME_DATE_EST": str, "HOME_TEAM_ID": int, ... }},
                        "win_probability": [
                            {{
                                "EVENT_NUM": int, "PCTIMESTRING": str, "HOME_PCT": float, "VISITOR_PCT": float,
                                "HOME_PTS": int, "VISITOR_PTS": int, "HOME_POSS_IND": int, ...
                            }}
                        ],
                        "run_type": str
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict {{'game_info': df, 'win_probability': df}}).
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"GameToolkit: get_game_win_probability called for game_id {game_id}")
        return fetch_win_probability_logic(
            game_id=game_id, run_type=run_type, return_dataframe=return_dataframe
        )
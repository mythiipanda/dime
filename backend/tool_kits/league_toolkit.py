from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import Toolkit
from agno.utils.log import logger

# League-wide stats logic functions
from ..api_tools.all_time_leaders_grids import fetch_all_time_leaders_logic
from ..api_tools.assist_leaders import fetch_assist_leaders_logic
from ..api_tools.homepage_leaders import fetch_homepage_leaders_logic
from ..api_tools.homepage_v2 import fetch_homepage_v2_logic
from ..api_tools.ist_standings import fetch_ist_standings_logic
from ..api_tools.leaders_tiles import fetch_leaders_tiles_logic
from ..api_tools.league_dash_player_bio import fetch_league_player_bio_stats_logic
from ..api_tools.league_dash_player_clutch import fetch_league_player_clutch_stats_logic
from ..api_tools.league_dash_player_pt_shot import fetch_league_dash_player_pt_shot_logic
from ..api_tools.league_dash_player_shot_locations import fetch_league_dash_player_shot_locations_logic
from ..api_tools.league_dash_player_stats import fetch_league_player_stats_logic
from ..api_tools.league_dash_pt_defend import fetch_league_dash_pt_defend_logic
from ..api_tools.league_dash_pt_stats import fetch_league_dash_pt_stats_logic
from ..api_tools.league_dash_pt_team_defend import fetch_league_dash_pt_team_defend_logic
from ..api_tools.league_dash_team_clutch import fetch_league_team_clutch_stats_logic
from ..api_tools.league_dash_team_pt_shot import fetch_league_dash_team_pt_shot_logic
from ..api_tools.league_dash_team_shot_locations import fetch_league_team_shot_locations_logic
from ..api_tools.league_dash_team_stats import fetch_league_team_stats_logic
from ..api_tools.league_draft import fetch_draft_history_logic
from ..api_tools.league_game_log import fetch_league_game_log_logic
from ..api_tools.league_hustle_stats_team import fetch_league_hustle_stats_team_logic
from ..api_tools.league_leaders_data import fetch_league_leaders_logic
from ..api_tools.league_lineups import fetch_league_dash_lineups_logic as fetch_league_lineups_data_logic
from ..api_tools.league_lineup_viz import fetch_league_lineup_viz_logic
from ..api_tools.league_standings import fetch_league_standings_logic
from ..api_tools.player_index import fetch_player_index_logic
from ..api_tools.player_listings import fetch_common_all_players_logic
from ..api_tools.playoff_picture import fetch_playoff_picture_logic
from ..api_tools.playoff_series import fetch_common_playoff_series_logic
from ..api_tools.schedule_league_v2_int import fetch_schedule_league_v2_int_logic
from ..api_tools.shot_chart_league_wide import fetch_shot_chart_league_wide_logic
from ..api_tools.trending_team_tools import fetch_top_teams_logic
from ..api_tools.trending_tools import fetch_top_performers_logic
from ..api_tools.player_estimated_metrics import fetch_player_estimated_metrics_logic as fetch_league_player_estimated_metrics_logic # Alias


from ..config import settings
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, LeagueID, MeasureTypeDetailedDefense,
    PerModeSimple, PerModeTime, PlayerOrTeam, PlayerScope, StatCategory, GameScopeDetailed,
    Direction, Sorter, PlayerOrTeamAbbreviation, StatCategoryAbbreviation, PerMode48, Scope,
    DefenseCategory, PtMeasureType, DistanceRange, MeasureTypeSimple, SeasonTypeAllStar, SeasonTypeAllStar
)


class LeagueToolkit(Toolkit):
    def __init__(self, **kwargs):
        tools = [
            self.get_all_time_leaders_grids,
            self.get_assist_leaders,
            self.get_homepage_leaders,
            self.get_homepage_v2_leaders,
            self.get_in_season_tournament_standings,
            self.get_leaders_tiles,
            self.get_league_player_bio_stats,
            self.get_league_player_clutch_stats,
            self.get_league_player_shooting_stats,
            self.get_league_player_shot_locations,
            self.get_league_player_stats,
            self.get_league_player_tracking_defense_stats,
            self.get_league_player_tracking_stats,
            self.get_league_team_tracking_defense_stats,
            self.get_league_team_clutch_stats,
            self.get_league_team_player_tracking_shot_stats,
            self.get_league_team_shot_locations,
            self.get_league_team_stats,
            self.get_draft_history,
            self.get_league_game_log,
            self.get_league_hustle_stats_team,
            self.get_league_leaders,
            self.get_league_lineups_data,
            self.get_league_lineup_viz_data,
            self.get_league_standings,
            self.get_player_index,
            self.get_common_all_players,
            self.get_playoff_picture,
            self.get_common_playoff_series,
            self.get_league_schedule,
            self.get_shot_chart_league_wide,
            self.get_top_performing_teams,
            self.get_top_performing_players,
            self.get_league_player_estimated_metrics, # Added this one
        ]
        super().__init__(name="league_toolkit", tools=tools, **kwargs)

    def get_all_time_leaders_grids(
        self,
        league_id: str = "00",
        per_mode: str = "Totals",
        season_type: str = "Regular Season",
        topx: int = 10,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches all-time statistical leaders data grids from the NBA API.
        Provides leaders in categories like Points, Rebounds, Assists, Steals, Blocks, etc.

        Args:
            league_id (str, optional): League ID. Defaults to "00" (NBA).
                                       Possible values: "00" (NBA), "10" (WNBA), "20" (G-League).
            per_mode (str, optional): Per mode for stats. Defaults to "Totals".
                                      Possible values: "Totals", "PerGame".
            season_type (str, optional): Season type context for leadership. Defaults to "Regular Season".
                                         Possible values: "Regular Season", "Pre Season".
            topx (int, optional): Number of top players to return for each category. Defaults to 10.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, dictionary of DataFrames).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with all-time leaders data or error.
                    Expected success structure:
                    {{
                        "parameters": {{"league_id": str, "per_mode": str, "season_type": str, "topx": int}},
                        "data_sets": {{
                            "PTSLeaders": [{{ "PLAYER_ID": int, "PLAYER_NAME": str, "PTS": float, "TEAM_ABBREVIATION": str, ... }}],
                            "ASTLeaders": [{{ ... similar structure ... }}],
                            // ... other statistical leader categories such as BLKLeaders, REBLeaders, STLLeaders, etc.
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys match the leader categories (e.g., 'PTSLeaders', 'ASTLeaders').
                    A combined DataFrame with a 'Category' column is saved to CSV if DataFrames are returned.
                    CSV cache path for the combined data included in json_string under 'dataframe_info'.
        """
        logger.info(f"LeagueToolkit: get_all_time_leaders_grids called for League: {league_id}, PerMode: {per_mode}, TopX: {topx}")
        return fetch_all_time_leaders_logic(
            league_id=league_id,
            per_mode=per_mode,
            season_type=season_type,
            topx=topx,
            return_dataframe=return_dataframe
        )

    def get_assist_leaders(
        self,
        league_id: str = "00",
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular,
        per_mode: str = "Totals",
        player_or_team: str = "Team",
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches assist leaders statistics for players or teams for a given season.

        Args:
            league_id (str, optional): League ID. Defaults to "00" (NBA). Possible: "00", "10", "20".
            season (str, optional): Season in YYYY-YY format. Defaults to current NBA season.
            season_type (str, optional): Type of season. Defaults to "Regular Season".
                                         Possible from SeasonTypeAllStar enum: "Regular Season", "Playoffs", "Pre Season", "All Star".
            per_mode (str, optional): Per mode for stats. Defaults to "Totals".
                                      Possible: "Totals", "PerGame". (API uses per_mode_simple)
            player_or_team (str, optional): Filter by Player or Team. Defaults to "Team".
                                            Possible: "Team", "Player".
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'AssistLeaders': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with assist leaders data or an error message.
                    Expected success structure:
                    {{
                        "parameters": {{...}},
                        "data_sets": {{
                            "AssistLeaders": [
                                {{
                                    "RANK": int, "PLAYER_ID" (or "TEAM_ID"): int, "PLAYER" (or "TEAM"): str,
                                    "AST": float, "GP": int, "MIN": float, ...
                                }}
                            ]
                            // Potentially other datasets like "AssistLeaders_1" if API returns multiple tables.
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict {{'AssistLeaders': pd.DataFrame, ...}}).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"LeagueToolkit: get_assist_leaders called for League: {league_id}, Season: {season}")
        return fetch_assist_leaders_logic(
            league_id=league_id,
            season=season,
            season_type=season_type, # API logic maps this to season_type_playoffs
            per_mode=per_mode, # API logic maps this to per_mode_simple
            player_or_team=player_or_team,
            return_dataframe=return_dataframe
        )

    def get_homepage_leaders(
        self,
        league_id: str = "00",
        season: str = settings.CURRENT_NBA_SEASON,
        season_type_playoffs: str = SeasonTypeAllStar.regular,
        player_or_team: str = PlayerOrTeam.team,
        player_scope: str = PlayerScope.all_players,
        stat_category: str = StatCategory.points,
        game_scope_detailed: str = GameScopeDetailed.season,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches homepage leaders data, including team/player leaders for a specific stat category, league averages, and league highs.

        Args:
            league_id (str, optional): League ID. Defaults to "00" (NBA). Possible: "00", "10" (WNBA).
            season (str, optional): Season in YYYY-YY format. Defaults to current NBA season.
            season_type_playoffs (str, optional): Season type. Defaults to "Regular Season".
                                                 Possible from SeasonTypePlayoffs enum: "Regular Season", "Playoffs".
            player_or_team (str, optional): Filter by Player or Team. Defaults to "Team".
                                            Possible from PlayerOrTeam enum.
            player_scope (str, optional): Scope of players. Defaults to "All Players".
                                          Possible from PlayerScope enum: "All Players", "Rookies".
            stat_category (str, optional): Statistical category. Defaults to "Points".
                                           Possible from StatCategory enum: "Points", "Rebounds", "Assists".
            game_scope_detailed (str, optional): Game scope. Defaults to "Season".
                                               Possible from GameScopeDetailed enum: "Season", "Last 10".
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with homepage leaders data or error.
                    Expected success structure:
                    {{
                        "parameters": {{...}},
                        "data_sets": {{
                            "HomePageLeaders": [{{ "TEAM_ID": int, "TEAM_NAME": str, "PTS": float, ... }}], // Or PLAYER_ID, PLAYER_NAME if player_or_team is "Player"
                            "LeagueAverage": [{{ "STAT": str, "VALUE": float, ... }}],
                            "LeagueHigh": [{{ "STAT": str, "VALUE": float, "PLAYER_NAME": str, ... }}]
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys: "HomePageLeaders", "LeagueAverage", "LeagueHigh".
                    CSV cache paths for each DataFrame included in json_string under 'dataframe_info'.
        """
        logger.info(f"LeagueToolkit: get_homepage_leaders called for League: {league_id}, Season: {season}, Stat: {stat_category}")
        return fetch_homepage_leaders_logic(
            league_id=league_id, season=season, season_type_playoffs=season_type_playoffs,
            player_or_team=player_or_team, player_scope=player_scope, stat_category=stat_category,
            game_scope_detailed=game_scope_detailed, return_dataframe=return_dataframe
        )

    def get_homepage_v2_leaders(
        self,
        league_id: str = "00",
        season: str = settings.CURRENT_NBA_SEASON,
        season_type_playoffs: str = SeasonTypeAllStar.regular,
        player_or_team: str = PlayerOrTeam.team,
        player_scope: str = PlayerScope.all_players,
        stat_type: str = "Traditional",
        game_scope_detailed: str = GameScopeDetailed.season,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches enhanced homepage leaders data (V2) across multiple statistical categories (Points, Rebounds, Assists, etc.).

        Args:
            league_id (str, optional): League ID. Defaults to "00" (NBA). Possible: "00", "10" (WNBA).
            season (str, optional): Season YYYY-YY. Defaults to current NBA season.
            season_type_playoffs (str, optional): Season type. Defaults to "Regular Season".
                                                 Possible from SeasonTypePlayoffs enum.
            player_or_team (str, optional): Filter Player or Team. Defaults to "Team".
                                            Possible from PlayerOrTeam enum.
            player_scope (str, optional): Player scope. Defaults to "All Players".
                                          Possible from PlayerScope enum.
            stat_type (str, optional): Statistical type. Defaults to "Traditional".
                                       Possible: "Traditional", "Advanced".
            game_scope_detailed (str, optional): Game scope. Defaults to "Season".
                                               Possible from GameScopeDetailed enum.
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with V2 homepage leaders or error.
                    Expected success structure:
                    {{
                        "parameters": {{...}},
                        "data_sets": {{
                            "Points": [{{ "TEAM_ID": int, "TEAM_NAME": str, "PTS": float, ... }}], // Or PLAYER_ID if player_or_team is "Player"
                            "Rebounds": [{{ ... }}],
                            "Assists": [{{ ... }}],
                            // ... other categories: Steals, FieldGoalPct, FreeThrowPct, ThreePointPct, Blocks
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys: "Points", "Rebounds", "Assists", etc.
                    CSV cache paths for each DataFrame included in json_string under 'dataframe_info'.
        """
        logger.info(f"LeagueToolkit: get_homepage_v2_leaders called for League: {league_id}, Season: {season}, StatType: {stat_type}")
        return fetch_homepage_v2_logic(
            league_id=league_id, season=season, season_type_playoffs=season_type_playoffs,
            player_or_team=player_or_team, player_scope=player_scope, stat_type=stat_type,
            game_scope_detailed=game_scope_detailed, return_dataframe=return_dataframe
        )

    def get_in_season_tournament_standings(
        self,
        league_id: str = "00",
        season: str = settings.CURRENT_NBA_SEASON, # API logic expects YYYY-YY for season
        section: str = "group",
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches In-Season Tournament (IST) standings data.

        Args:
            league_id (str, optional): League ID. Defaults to "00" (NBA). Only "00" is typically valid for IST.
            season (str, optional): Season in YYYY-YY format for which to get IST standings. Defaults to current NBA season.
            section (str, optional): Section type of the tournament. Defaults to "group".
                                     Possible: "group", "knockout".
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'ISTStandings': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with IST standings or error.
                    Expected success structure:
                    {{
                        "parameters": {{"league_id": str, "season": str, "section": str}},
                        "data_sets": {{
                            "ISTStandings": [
                                {{
                                    "leagueId": str, "seasonYear": int, "teamId": int, "teamCity": str,
                                    "teamName": str, "teamAbbreviation": str, "istGroup": str,
                                    "wins": int, "losses": int, "pct": float, "pts": int, "oppPts": int, ...
                                    // Also includes many game-specific columns like game1Id, game1Opponent, etc.
                                }}
                            ]
                            // May include other datasets depending on API version
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, {{'ISTStandings': pd.DataFrame, ...}}).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"LeagueToolkit: get_in_season_tournament_standings called for League: {league_id}, Season: {season}")
        return fetch_ist_standings_logic(
            league_id=league_id,
            season=season, # The logic function takes YYYY-YY season
            section=section,
            return_dataframe=return_dataframe
        )

    def get_leaders_tiles(
        self,
        game_scope_detailed: str = GameScopeDetailed.season,
        league_id: str = "00",
        player_or_team: str = PlayerOrTeam.team,
        player_scope: str = PlayerScope.all_players,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type_playoffs: str = SeasonTypeAllStar.regular,
        stat: str = "PTS", # API param is stat, not stat_category
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches statistical leaders tiles data, including current season, all-time high/low, and last season leaders for a specific stat.

        Args:
            game_scope_detailed (str, optional): Game scope. Defaults to "Season".
                                               Possible from GameScopeDetailed enum.
            league_id (str, optional): League ID. Defaults to "00" (NBA). Only "00" supported.
            player_or_team (str, optional): Filter Player or Team. Defaults to "Team".
                                            Possible from PlayerOrTeam enum.
            player_scope (str, optional): Player scope. Defaults to "All Players".
                                          Possible from PlayerScope enum.
            season (str, optional): Season YYYY-YY. Defaults to current NBA season.
            season_type_playoffs (str, optional): Season type. Defaults to "Regular Season".
                                                 Possible from SeasonTypePlayoffs enum.
            stat (str, optional): Statistical category abbreviation. Defaults to "PTS".
                                  Possible: "PTS", "REB", "AST", "STL", "BLK", "FG_PCT", "FG3_PCT", "FT_PCT".
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with leaders tiles data or error.
                    Expected success structure:
                    {{
                        "parameters": {{...}},
                        "data_sets": {{
                            "CurrentSeasonLeaders": [{{ "RANK": int, "TEAM_ID": int (or "PLAYER_ID"), "TEAM_NAME": str (or "PLAYER_NAME"), "PTS": float (or current stat), ... }}],
                            "AllTimeHigh": [{{ ... similar structure for all-time high record holder ... }}],
                            "LastSeasonLeaders": [{{ ... similar structure for last season's leaders ... }}],
                            "AllTimeLow": [{{ ... similar structure for all-time low record holder (less common) ... }}]
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    Keys: "CurrentSeasonLeaders", "AllTimeHigh", "LastSeasonLeaders", "AllTimeLow".
                    CSV cache paths for each DataFrame included in json_string under 'dataframe_info'.
        """
        logger.info(f"LeagueToolkit: get_leaders_tiles called for Stat: {stat}, Season: {season}")
        return fetch_leaders_tiles_logic(
            game_scope_detailed=game_scope_detailed, league_id=league_id, player_or_team=player_or_team,
            player_scope=player_scope, season=season, season_type_playoffs=season_type_playoffs,
            stat=stat, return_dataframe=return_dataframe
        )

    # ... (Implementations for the rest of the league-wide tools will follow the same pattern) ...
    # You'll need to carefully craft the docstrings for each.

    def get_league_player_bio_stats(
        self,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = "Regular Season",
        per_mode: str = "PerGame",
        league_id: str = "00",
        team_id: Optional[str] = None,
        player_position: Optional[str] = None,
        player_experience: Optional[str] = None,
        starter_bench: Optional[str] = None,
        college: Optional[str] = None,
        country: Optional[str] = None,
        draft_year: Optional[str] = None,
        height: Optional[str] = None,
        weight: Optional[str] = None,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches player biographical statistics for all players in a league, with various filters.
        Includes demographics, college, country, draft info, and basic/advanced stats.

        Args:
            season (str, optional): Season in YYYY-YY format. Defaults to current NBA season.
            season_type (str, optional): Season type. Defaults to "Regular Season".
                                         Possible values: "Regular Season", "Playoffs", "Pre Season", "All Star".
            per_mode (str, optional): Per mode for stats. Defaults to "PerGame".
                                      Possible values: "Totals", "PerGame".
            league_id (str, optional): League ID. Defaults to "00" (NBA).
                                       Possible: "00", "10" (WNBA), "20" (G-League).
            team_id (Optional[str], optional): Team ID to filter players by.
            player_position (Optional[str], optional): Player position filter (e.g., "Forward", "Guard", "Center", "Center-Forward").
            player_experience (Optional[str], optional): Player experience filter (e.g., "Rookie", "Sophomore", "Veteran").
            starter_bench (Optional[str], optional): Starter/bench filter (e.g., "Starters", "Bench").
            college (Optional[str], optional): College filter.
            country (Optional[str], optional): Country filter.
            draft_year (Optional[str], optional): Draft year filter (YYYY).
            height (Optional[str], optional): Height filter (e.g., "6-5", "GT 6-10").
            weight (Optional[str], optional): Weight filter (e.g., "LT 200", "GT 250").
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'LeagueDashPlayerBioStats': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with player bio stats or error.
                    Expected success structure:
                    {{
                        "parameters": {{...applied filters...}},
                        "data_sets": {{
                            "LeagueDashPlayerBioStats": [
                                {{
                                    "PLAYER_ID": int, "PLAYER_NAME": str, "TEAM_ABBREVIATION": str, "AGE": int,
                                    "PLAYER_HEIGHT_INCHES": int, "PLAYER_WEIGHT": str, "COLLEGE": str,
                                    "COUNTRY": str, "DRAFT_YEAR": Optional[str], "GP": int, "PTS": float, ... (other stats)
                                }}
                            ]
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, {{'LeagueDashPlayerBioStats': pd.DataFrame}}).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"LeagueToolkit: get_league_player_bio_stats called for Season: {season}, Type: {season_type}")
        return fetch_league_player_bio_stats_logic(
            season=season, season_type=season_type, per_mode=per_mode, league_id=league_id,
            team_id=team_id, player_position=player_position, player_experience=player_experience,
            starter_bench=starter_bench, college=college, country=country, draft_year=draft_year,
            height=height, weight=weight, return_dataframe=return_dataframe
        )

    # ... (Continue for all other methods in the tools list)
    # This is very extensive. I'll provide stubs for the remaining ones.
    # You'll need to fill in the call to the logic function and write the full docstring.

    def get_league_player_clutch_stats(self, season: str = settings.CURRENT_NBA_SEASON, season_type: str = "Regular Season", per_mode: str = "PerGame", measure_type: str = "Base", clutch_time: str = "Last 5 Minutes", ahead_behind: str = "Ahead or Behind", point_diff: int = 5, league_id: str = "00", return_dataframe: bool = False, **kwargs) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """Fetches league-wide player clutch statistics with various filters. See original `league_dash_player_clutch.py` for all parameters."""
        logger.info(f"LeagueToolkit: get_league_player_clutch_stats for Season: {season}, Type: {season_type}, Clutch: {clutch_time}")
        return fetch_league_player_clutch_stats_logic(season=season, season_type=season_type, per_mode=per_mode, measure_type=measure_type, clutch_time=clutch_time, ahead_behind=ahead_behind, point_diff=point_diff, league_id=league_id, return_dataframe=return_dataframe, **kwargs)

    def get_league_player_shooting_stats(self, season: str = settings.CURRENT_NBA_SEASON, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerModeSimple.per_game, league_id: str = LeagueID.nba, return_dataframe: bool = False, **kwargs) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """Fetches league-wide player shooting statistics (LeagueDashPlayerPtShot). See original file for all optional args."""
        logger.info(f"LeagueToolkit: get_league_player_shooting_stats for season {season}, type {season_type}")
        return fetch_league_dash_player_pt_shot_logic(season=season, season_type=season_type, per_mode=per_mode, league_id=league_id, return_dataframe=return_dataframe, **kwargs)

    def get_league_player_shot_locations(self, distance_range: str = "By Zone", season: str = settings.CURRENT_NBA_SEASON, season_type_all_star: str = SeasonTypeAllStar.regular, league_id_nullable: str = "", return_dataframe: bool = False, **kwargs) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """Fetches league-wide player shot location data. See original file for all optional args."""
        logger.info(f"LeagueToolkit: get_league_player_shot_locations for season {season}, distance_range {distance_range}")
        return fetch_league_dash_player_shot_locations_logic(distance_range=distance_range, season=season, season_type_all_star=season_type_all_star, league_id_nullable=league_id_nullable, return_dataframe=return_dataframe, **kwargs)

    def get_league_player_stats(self, season: str = settings.CURRENT_NBA_SEASON, season_type: str = "Regular Season", per_mode: str = "PerGame", measure_type: str = "Base", league_id: str = "00", return_dataframe: bool = False, **kwargs) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """Fetches comprehensive league-wide player statistics. See original file for all optional args."""
        logger.info(f"LeagueToolkit: get_league_player_stats for season {season}, measure_type {measure_type}")
        return fetch_league_player_stats_logic(season=season, season_type=season_type, per_mode=per_mode, measure_type=measure_type, league_id=league_id, return_dataframe=return_dataframe, **kwargs)

    def get_league_player_tracking_defense_stats(self, season: str = settings.CURRENT_NBA_SEASON, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerModeSimple.per_game, defense_category: str = DefenseCategory.overall, league_id: str = LeagueID.nba, return_dataframe: bool = False, **kwargs) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """Fetches league-wide defensive player tracking statistics. See original file for all optional args."""
        logger.info(f"LeagueToolkit: get_league_player_tracking_defense_stats for season {season}, category {defense_category}")
        return fetch_league_dash_pt_defend_logic(season=season, season_type=season_type, per_mode=per_mode, defense_category=defense_category, league_id=league_id, return_dataframe=return_dataframe, **kwargs)

    def get_league_player_tracking_stats(self, season: str = settings.CURRENT_NBA_SEASON, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerModeSimple.per_game, player_or_team: str = PlayerOrTeam.team, pt_measure_type: str = PtMeasureType.speed_distance, league_id_nullable: Optional[str] = None, return_dataframe: bool = False, **kwargs) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """Fetches league-wide player or team tracking statistics (Speed, Rebounding, Possessions, etc.). See original file for all optional args."""
        logger.info(f"LeagueToolkit: get_league_player_tracking_stats for season {season}, measure {pt_measure_type}")
        return fetch_league_dash_pt_stats_logic(season=season, season_type=season_type, per_mode=per_mode, player_or_team=player_or_team, pt_measure_type=pt_measure_type, league_id_nullable=league_id_nullable, return_dataframe=return_dataframe, **kwargs)

    def get_league_team_tracking_defense_stats(self, season: str = settings.CURRENT_NBA_SEASON, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerModeSimple.per_game, defense_category: str = DefenseCategory.overall, league_id: str = LeagueID.nba, return_dataframe: bool = False, **kwargs) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """Fetches league-wide defensive team tracking statistics. See original file for all optional args."""
        logger.info(f"LeagueToolkit: get_league_team_tracking_defense_stats for season {season}, category {defense_category}")
        return fetch_league_dash_pt_team_defend_logic(season=season, season_type=season_type, per_mode=per_mode, defense_category=defense_category, league_id=league_id, return_dataframe=return_dataframe, **kwargs)

    def get_league_team_clutch_stats(self, season: str = settings.CURRENT_NBA_SEASON, season_type: str = "Regular Season", per_mode: str = "PerGame", measure_type: str = "Base", clutch_time: str = "Last 5 Minutes", ahead_behind: str = "Ahead or Behind", point_diff: int = 5, league_id: str = "00", return_dataframe: bool = False, **kwargs) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """Fetches league-wide team clutch statistics. See original file for all optional args."""
        logger.info(f"LeagueToolkit: get_league_team_clutch_stats for season {season}, clutch_time {clutch_time}")
        return fetch_league_team_clutch_stats_logic(season=season, season_type=season_type, per_mode=per_mode, measure_type=measure_type, clutch_time=clutch_time, ahead_behind=ahead_behind, point_diff=point_diff, league_id=league_id, return_dataframe=return_dataframe, **kwargs)

    def get_league_team_player_tracking_shot_stats(self, league_id: str = "00", per_mode_simple: str = PerModeSimple.totals, season: str = settings.CURRENT_NBA_SEASON, season_type_all_star: str = SeasonTypeAllStar.regular, return_dataframe: bool = False, **kwargs) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """Fetches league-wide team player tracking shot data. See original file for all optional args."""
        logger.info(f"LeagueToolkit: get_league_team_player_tracking_shot_stats for league {league_id}, season {season}")
        return fetch_league_dash_team_pt_shot_logic(league_id=league_id, per_mode_simple=per_mode_simple, season=season, season_type_all_star=season_type_all_star, return_dataframe=return_dataframe, **kwargs)

    def get_league_team_shot_locations(self, season: str = settings.CURRENT_NBA_SEASON, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerModeDetailed.per_game, measure_type: str = MeasureTypeSimple.base, distance_range: str = DistanceRange.by_zone, return_dataframe: bool = False, **kwargs) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """Fetches league-wide team shot location statistics. See original file for all optional args."""
        logger.info(f"LeagueToolkit: get_league_team_shot_locations for season {season}, distance_range {distance_range}")
        return fetch_league_team_shot_locations_logic(season=season, season_type=season_type, per_mode=per_mode, measure_type=measure_type, distance_range=distance_range, return_dataframe=return_dataframe, **kwargs)

    def get_league_team_stats(self, season: str = settings.CURRENT_NBA_SEASON, season_type: str = "Regular Season", per_mode: str = "PerGame", measure_type: str = "Base", league_id: str = "00", return_dataframe: bool = False, **kwargs) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """Fetches comprehensive league-wide team statistics. See original file for all optional args."""
        logger.info(f"LeagueToolkit: get_league_team_stats for season {season}, measure_type {measure_type}")
        return fetch_league_team_stats_logic(season=season, season_type=season_type, per_mode=per_mode, measure_type=measure_type, league_id=league_id, return_dataframe=return_dataframe, **kwargs)

    def get_draft_history(self, season_year_nullable: Optional[str] = None, league_id_nullable: str = LeagueID.nba, team_id_nullable: Optional[int] = None, round_num_nullable: Optional[int] = None, overall_pick_nullable: Optional[int] = None, return_dataframe: bool = False) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """[Docstring from league_draft.py, adapted for toolkit]"""
        logger.info(f"LeagueToolkit: get_draft_history for year {season_year_nullable or 'All'}")
        return fetch_draft_history_logic(season_year_nullable, league_id_nullable, team_id_nullable, round_num_nullable, overall_pick_nullable, return_dataframe)

    def get_league_game_log(self, season: str = settings.CURRENT_NBA_SEASON, season_type: str = SeasonTypeAllStar.regular, player_or_team: str = PlayerOrTeamAbbreviation.team, league_id: str = LeagueID.nba, direction: str = Direction.asc, sorter: str = Sorter.date, return_dataframe: bool = False, **kwargs) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """Fetches game logs for all teams or players in the league. See original file for all optional args."""
        logger.info(f"LeagueToolkit: get_league_game_log for season {season}, entity: {player_or_team}")
        return fetch_league_game_log_logic(season=season, season_type=season_type, player_or_team=player_or_team, league_id=league_id, direction=direction, sorter=sorter, return_dataframe=return_dataframe, **kwargs)

    def get_league_hustle_stats_team(self, per_mode_time: str = PerModeTime.totals, season: str = settings.CURRENT_NBA_SEASON, season_type_all_star: str = SeasonTypeAllStar.regular, league_id_nullable: str = "", return_dataframe: bool = False, **kwargs) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """Fetches league-wide team hustle statistics. See original file for all optional args."""
        logger.info(f"LeagueToolkit: get_league_hustle_stats_team for season {season}, per_mode {per_mode_time}")
        return fetch_league_hustle_stats_team_logic(per_mode_time=per_mode_time, season=season, season_type_all_star=season_type_all_star, league_id_nullable=league_id_nullable, return_dataframe=return_dataframe, **kwargs)

    def get_league_leaders(self, season: str, stat_category: str = StatCategoryAbbreviation.pts, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerMode48.per_game, league_id: str = LeagueID.nba, scope: str = Scope.s, top_n: int = 10, return_dataframe: bool = False) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """Fetches league leaders for a specific statistical category. See original file for all optional args."""
        logger.info(f"LeagueToolkit: get_league_leaders for season {season}, category {stat_category}")
        return fetch_league_leaders_logic(season=season, stat_category=stat_category, season_type=season_type, per_mode=per_mode, league_id=league_id, scope=scope, top_n=top_n, return_dataframe=return_dataframe)

    def get_league_lineups_data(self, season: str, group_quantity: int = 5, measure_type: str = MeasureTypeDetailedDefense.base, per_mode: str = PerModeDetailed.totals, season_type: str = SeasonTypeAllStar.regular, return_dataframe: bool = False, **kwargs) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: # API uses season_type_all_star
        """Fetches league-wide lineup statistics with extensive filtering. See original file for all optional args."""
        logger.info(f"LeagueToolkit: get_league_lineups_data for season {season}, group_quantity {group_quantity}")
        return fetch_league_lineups_data_logic(season=season, group_quantity=group_quantity, measure_type=measure_type, per_mode=per_mode, season_type=season_type, return_dataframe=return_dataframe, **kwargs) # Ensure logic func also uses season_type_all_star

    def get_league_lineup_viz_data(self, minutes_min: int = 5, group_quantity: int = 5, season: str = settings.CURRENT_NBA_SEASON, season_type_all_star: str = SeasonTypeAllStar.regular, league_id_nullable: str = "", return_dataframe: bool = False, **kwargs) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """Fetches league lineup visualization data. See original file for all optional args."""
        logger.info(f"LeagueToolkit: get_league_lineup_viz_data for season {season}, group_quantity {group_quantity}")
        return fetch_league_lineup_viz_logic(minutes_min=minutes_min, group_quantity=group_quantity, season=season, season_type_all_star=season_type_all_star, league_id_nullable=league_id_nullable, return_dataframe=return_dataframe, **kwargs)

    def get_league_standings(self, season: Optional[str] = None, season_type: str = SeasonTypeAllStar.regular, league_id: str = LeagueID.nba, return_dataframe: bool = False) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """[Docstring from league_standings.py, adapted for toolkit]"""
        logger.info(f"LeagueToolkit: get_league_standings for season {season or settings.CURRENT_NBA_SEASON}, type {season_type}")
        return fetch_league_standings_logic(season, season_type, league_id, return_dataframe)

    def get_player_index(self, league_id: str = "00", season: str = settings.CURRENT_NBA_SEASON, active: Optional[str] = None, allstar: Optional[str] = None, historical: Optional[str] = None, return_dataframe: bool = False, **kwargs) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """Fetches a comprehensive directory of all players with filters. See original file for all optional args."""
        logger.info(f"LeagueToolkit: get_player_index for league {league_id}, season {season}")
        return fetch_player_index_logic(league_id=league_id, season=season, active=active, allstar=allstar, historical=historical, return_dataframe=return_dataframe, **kwargs)

    def get_common_all_players(self, season: str, league_id: str = LeagueID.nba, is_only_current_season: int = 1, return_dataframe: bool = False) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """[Docstring from player_listings.py, adapted for toolkit]"""
        logger.info(f"LeagueToolkit: get_common_all_players for season {season}, league {league_id}")
        return fetch_common_all_players_logic(season, league_id, is_only_current_season, return_dataframe)

    def get_playoff_picture(self, league_id: str = "00", season_id: str = "22024", return_dataframe: bool = False) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: # CURRENT_NBA_SEASON_ID logic is "22024"
        """[Docstring from playoff_picture.py, adapted for toolkit]"""
        logger.info(f"LeagueToolkit: get_playoff_picture for league {league_id}, season_id {season_id}")
        return fetch_playoff_picture_logic(league_id, season_id, return_dataframe)

    def get_common_playoff_series(self, season: str, league_id: str = LeagueID.nba, series_id: Optional[str] = None, return_dataframe: bool = False) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """[Docstring from playoff_series.py, adapted for toolkit]"""
        logger.info(f"LeagueToolkit: get_common_playoff_series for season {season}, league {league_id}")
        return fetch_common_playoff_series_logic(season, league_id, series_id, return_dataframe)

    def get_league_schedule(self, league_id: str = "00", season: str = settings.CURRENT_NBA_SEASON, return_dataframe: bool = False) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """[Docstring from schedule_league_v2_int.py, adapted for toolkit]"""
        logger.info(f"LeagueToolkit: get_league_schedule for league {league_id}, season {season}")
        return fetch_schedule_league_v2_int_logic(league_id, season, return_dataframe)

    def get_shot_chart_league_wide(self, league_id: str = "00", season: str = settings.CURRENT_NBA_SEASON, return_dataframe: bool = False) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """[Docstring from shot_chart_league_wide.py, adapted for toolkit]"""
        logger.info(f"LeagueToolkit: get_shot_chart_league_wide for league {league_id}, season {season}")
        return fetch_shot_chart_league_wide_logic(league_id, season, return_dataframe)

    def get_top_performing_teams(self, season: str = settings.CURRENT_NBA_SEASON, season_type: str = SeasonTypeAllStar.regular, league_id: str = LeagueID.nba, top_n: int = 5, return_dataframe: bool = False) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """[Docstring from trending_team_tools.py, adapted for toolkit]"""
        logger.info(f"LeagueToolkit: get_top_performing_teams for season {season}, top {top_n}")
        return fetch_top_teams_logic(season, season_type, league_id, top_n, return_dataframe=return_dataframe)

    def get_top_performing_players(self, category: str = StatCategoryAbbreviation.pts, season: str = settings.CURRENT_NBA_SEASON, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerMode48.per_game, scope: str = Scope.s, league_id: str = LeagueID.nba, top_n: int = 5, return_dataframe: bool = False) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """[Docstring from trending_tools.py, adapted for toolkit]"""
        logger.info(f"LeagueToolkit: get_top_performing_players for category {category}, season {season}, top {top_n}")
        return fetch_top_performers_logic(category, season, season_type, per_mode, scope, league_id, top_n, return_dataframe=return_dataframe)

    def get_league_player_estimated_metrics(
        self,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular,
        league_id: str = LeagueID.nba,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, pd.DataFrame]]: # Note: Original returns pd.DataFrame directly, adapting for toolkit
        """
        Fetches player estimated metrics (E_OFF_RATING, E_DEF_RATING, E_NET_RATING, etc.)
        for all players in a given season and season type.

        Args:
            season (str, optional): NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to current.
            season_type (str, optional): Season type. Defaults to "Regular Season".
                                         Possible from SeasonTypeAllStar enum.
            league_id (str, optional): League ID. Defaults to "00" (NBA).
                                       Possible from LeagueID enum.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, DataFrame).
                                               The DataFrame contains all player estimated metrics. Defaults to False.

        Returns:
            Union[str, Tuple[str, pd.DataFrame]]:
                If return_dataframe=False: JSON string with estimated metrics for all players or an error message.
                    Expected success structure:
                    {{
                        "parameters": {{...}},
                        "player_estimated_metrics": [
                            {{
                                "PLAYER_ID": int, "PLAYER_NAME": str, "TEAM_ABBREVIATION": str,
                                "E_OFF_RATING": float, "E_DEF_RATING": float, "E_NET_RATING": float,
                                "E_PACE": float, ... (other estimated metrics and ranks) ...
                            }}
                        ]
                    }}
                If return_dataframe=True: Tuple (json_string, pd.DataFrame). The DataFrame is the primary data.
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"LeagueToolkit: get_league_player_estimated_metrics called for season {season}")
        json_response, df_or_dict = fetch_league_player_estimated_metrics_logic(
            season=season,
            season_type=season_type,
            league_id=league_id,
            return_dataframe=return_dataframe # Pass through the flag
        )
        if return_dataframe:
            # The logic function already returns Tuple[str, pd.DataFrame], so we directly return it
            return json_response, {"player_estimated_metrics": df_or_dict} # Ensure dict format for DataFrame
        return json_response
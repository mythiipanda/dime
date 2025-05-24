from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import Toolkit
from agno.utils.log import logger

# Team specific stats logic functions
from ..api_tools.team_dash_lineups import fetch_team_lineups_logic
from ..api_tools.team_dash_pt_shots import fetch_team_dash_pt_shots_logic
from ..api_tools.league_dash_pt_team_defend import fetch_league_dash_pt_team_defend_logic # Note: Logic function name implies league but can be filtered by team
from ..api_tools.team_dashboard_shooting import fetch_team_dashboard_shooting_splits_logic
from ..api_tools.team_details import fetch_team_details_logic
from ..api_tools.team_estimated_metrics import fetch_team_estimated_metrics_logic # Note: This is league-wide but returns data per team
from ..api_tools.team_game_logs import fetch_team_game_logs_logic
from ..api_tools.team_general_stats import fetch_team_stats_logic
from ..api_tools.team_historical_leaders import fetch_team_historical_leaders_logic
from ..api_tools.team_history import fetch_common_team_years_logic # Note: This is league-wide team history, not for a single team
from ..api_tools.team_info_roster import fetch_team_info_and_roster_logic
from ..api_tools.team_passing_analytics import fetch_team_passing_stats_logic
from ..api_tools.team_player_dashboard import fetch_team_player_dashboard_logic
from ..api_tools.team_player_on_off_details import fetch_team_player_on_off_details_logic
from ..api_tools.teamplayeronoffsummary import fetch_teamplayeronoffsummary_logic
from ..api_tools.team_rebounding_tracking import fetch_team_rebounding_stats_logic
from ..api_tools.team_shooting_tracking import fetch_team_shooting_stats_logic
from ..api_tools.teamvsplayer import fetch_teamvsplayer_logic
from ..api_tools.franchise_history import fetch_franchise_history_logic # League-wide but team-centric context
from ..api_tools.franchise_leaders import fetch_franchise_leaders_logic
from ..api_tools.franchise_players import fetch_franchise_players_logic


from ..config import settings
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, LeagueID, MeasureTypeDetailedDefense,
    PerModeSimple, PerModeTime, DefenseCategory
)


class TeamToolkit(Toolkit):
    def __init__(self, **kwargs):
        tools = [
            self.get_team_lineup_stats,
            self.get_team_player_tracking_shot_stats,
            self.get_team_player_tracking_defense_stats, # Renamed from league_dash_pt_team_defend
            self.get_team_dashboard_shooting_splits,
            self.get_team_details,
            self.get_league_team_estimated_metrics, # Note: league-wide but returns per-team data
            self.get_team_game_logs,
            self.get_team_general_stats,
            self.get_team_historical_leaders,
            self.get_common_team_years, # Note: league-wide team history
            self.get_team_info_and_roster,
            self.get_team_passing_stats,
            self.get_team_player_dashboard_stats,
            self.get_team_player_on_off_details,
            self.get_team_player_on_off_summary,
            self.get_team_rebounding_tracking_stats,
            self.get_team_shooting_tracking_stats,
            self.get_team_vs_player_stats,
            self.get_league_franchise_history, # League-wide but can be viewed in team context
            self.get_franchise_leaders, # Specific to a team
            self.get_franchise_players, # Specific to a team
        ]
        super().__init__(name="team_toolkit", tools=tools, **kwargs)

    def get_team_lineup_stats(
        self,
        team_identifier: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular,
        measure_type: str = MeasureTypeDetailedDefense.base,
        per_mode: str = PerModeDetailed.totals,
        group_quantity: int = 5,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches team lineup statistics, providing insights into performance of different player combinations.
        Data includes overall team stats when specific lineups are on the court and the lineups themselves.

        Args:
            team_identifier (str): Name, abbreviation, or ID of the team.
            season (str, optional): NBA season in YYYY-YY format (e.g., "2023-24"). Defaults to current season.
            season_type (str, optional): Type of season. Defaults to "Regular Season".
                                         Possible values from SeasonTypeAllStar enum (e.g., "Regular Season", "Playoffs").
            measure_type (str, optional): Statistical category. Defaults to "Base".
                                          Possible values from MeasureTypeDetailedDefense enum (e.g., "Base", "Advanced", "Scoring").
            per_mode (str, optional): Per mode for stats. Defaults to "Totals".
                                      Possible values from PerModeDetailed enum (e.g., "PerGame", "Per100Possessions").
            group_quantity (int, optional): Number of players in the lineup (2-5). Defaults to 5.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'Lineups': df, 'Overall': df}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with lineups data or error.
                    Expected success structure:
                    {{
                        "team_name": str, "team_id": int, "parameters": {{...}},
                        "data_sets": {{
                            "Lineups": [{{ "GROUP_ID": str, "GROUP_NAME": str, "TEAM_ABBREVIATION": str, "GP": int, "MIN": float, "PTS": float, ... }}],
                            "Overall": [{{ "GROUP_SET": str, "GP": int, "MIN": float, "PTS": float, ... }}] // Team's overall stats for context
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys: 'Lineups', 'Overall'.
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_team_lineup_stats called for {team_identifier}, season {season}")
        return fetch_team_lineups_logic(
            team_identifier=team_identifier,
            season=season,
            season_type=season_type,
            measure_type=measure_type,
            per_mode=per_mode,
            group_quantity=group_quantity,
            return_dataframe=return_dataframe
        )

    def get_team_player_tracking_shot_stats(
        self,
        team_identifier: str, # TeamDashPtShots requires a team_id
        season: str = settings.CURRENT_NBA_SEASON,
        season_type_all_star: str = SeasonTypeAllStar.regular,
        per_mode_simple: str = PerModeSimple.totals,
        league_id: str = LeagueID.nba, # Parameter from endpoint
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches team-level player tracking shot statistics (e.g., overall shooting, 2pt/3pt frequencies and percentages).
        This endpoint (TeamDashPtShots) is specific to a team.

        Args:
            team_identifier (str): Name, abbreviation, or ID of the team. This is required.
            season (str, optional): Season in YYYY-YY format. Defaults to current NBA season.
            season_type_all_star (str, optional): Season type. Defaults to "Regular Season".
                                                 Possible from SeasonTypeAllStar enum.
            per_mode_simple (str, optional): Per mode for stats. Defaults to "Totals".
                                             Possible from PerModeSimple enum (e.g., "Totals", "PerGame").
            league_id (str, optional): League ID. Defaults to "00" (NBA).
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'TeamPtShot': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with team player tracking shot stats or error.
                    Expected success structure:
                    {{
                        "parameters": {{...}},
                        "data_sets": {{
                            "TeamPtShot": [ // List of shot types (Overall, Catch and Shoot, Pullups, etc.) for the team
                                {{
                                    "TEAM_ID": int, "TEAM_NAME": str, "SHOT_TYPE": str,
                                    "FGA_FREQUENCY": float, "FGM": int, "FGA": int, "FG_PCT": float,
                                    "EFG_PCT": float, "FG2A_FREQUENCY": float, ...
                                }}
                            ]
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, {{'TeamPtShot': pd.DataFrame}}).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_team_player_tracking_shot_stats called for {team_identifier}, season {season}")
        # The logic function `fetch_team_dash_pt_shots_logic` expects team_id as string.
        # We first resolve team_identifier to team_id.
        try:
            team_id_val, _ = find_team_id_or_error(team_identifier)
        except Exception as e:
            logger.error(f"Error finding team ID for '{team_identifier}': {e}", exc_info=True)
            error_response = format_response(error=str(e))
            if return_dataframe:
                return error_response, {}
            return error_response

        return fetch_team_dash_pt_shots_logic(
            team_id=str(team_id_val), # Ensure it's passed as string if required by underlying
            season=season,
            season_type_all_star=season_type_all_star,
            per_mode_simple=per_mode_simple,
            league_id=league_id, # Passed as league_id in logic
            return_dataframe=return_dataframe
        )

    def get_team_player_tracking_defense_stats(
        self,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular,
        per_mode: str = PerModeSimple.per_game,
        defense_category: str = DefenseCategory.overall,
        league_id: str = LeagueID.nba,
        team_identifier_nullable: Optional[str] = None, # To filter for a specific team
        # ... other filters from fetch_league_dash_pt_team_defend_logic
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches defensive team tracking statistics. Can be league-wide or filtered for a specific team.
        Shows how teams perform when defending shots in different categories (Overall, 3 Pointers, etc.).

        Args:
            season (str, optional): Season YYYY-YY. Defaults to current.
            season_type (str, optional): Season type. Defaults to "Regular Season".
            per_mode (str, optional): Statistical mode. Defaults to "PerGame".
            defense_category (str, optional): Defense category. Defaults to "Overall".
                                              Possible from DefenseCategory enum (e.g., "Overall", "3 Pointers", "Less Than 6Ft").
            league_id (str, optional): League ID. Defaults to "00" (NBA).
            team_identifier_nullable (Optional[str], optional): Name, abbreviation, or ID of a specific team to filter for.
                                                                If None, returns league-wide data.
            // ... (other optional filters like conference_nullable, date_from_nullable, etc. as in the logic function)
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'pt_team_defend': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with defensive team tracking stats or error.
                    Expected success structure:
                    {{
                        "parameters": {{...}},
                        "pt_team_defend": [
                            {{
                                "TEAM_ID": int, "TEAM_NAME": str, "GP": int, "FREQ": float,
                                "D_FGM": float, "D_FGA": float, "D_FG_PCT": float,
                                "NORMAL_FG_PCT": float, "PCT_PLUSMINUS": float, ...
                            }}
                        ]
                    }}
                If return_dataframe=True: Tuple (json_string, {{'pt_team_defend': pd.DataFrame}}).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_team_player_tracking_defense_stats called for season {season}, team: {team_identifier_nullable or 'League-wide'}")
        team_id_val_nullable = None
        if team_identifier_nullable:
            try:
                team_id_val_nullable, _ = find_team_id_or_error(team_identifier_nullable)
            except Exception as e:
                logger.warning(f"Could not resolve team_identifier '{team_identifier_nullable}' for defense stats: {e}")
                # Proceed with None or handle error as appropriate

        return fetch_league_dash_pt_team_defend_logic(
            season=season,
            season_type=season_type,
            per_mode=per_mode,
            defense_category=defense_category,
            league_id=league_id,
            team_id_nullable=str(team_id_val_nullable) if team_id_val_nullable else None, # API expects string or None
            # Pass through other relevant optional filters here
            return_dataframe=return_dataframe
        )

    def get_team_dashboard_shooting_splits(
        self,
        team_identifier: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = "Regular Season",
        measure_type: str = "Base",
        per_mode: str = "Totals",
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches team dashboard statistics by shooting splits (Shot Type, Shot Area, Shot Distance, Assisted/Unassisted).

        Args:
            team_identifier (str): Name, abbreviation, or ID of the team.
            season (str, optional): Season YYYY-YY. Defaults to current NBA season.
            season_type (str, optional): Season type. Defaults to "Regular Season".
                                         Possible values: "Regular Season", "Playoffs", "Pre Season", "All Star".
            measure_type (str, optional): Statistical category. Defaults to "Base".
                                          Possible values from MeasureTypeDetailedDefense enum (Note: API uses this for team shooting splits too).
            per_mode (str, optional): Per mode for stats. Defaults to "Totals".
                                      Possible values from PerModeDetailed enum.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, dictionary of DataFrames).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with dashboard data or error.
                    Expected success structure:
                    {{
                        "team_name": str, "team_id": int, "parameters": {{...}},
                        "data_sets": {{
                            "OverallTeamDashboard": [{{ ... team overall stats ... }}],
                            "Shot5FTTeamDashboard": [{{ ... stats by 5ft ranges ... }}],
                            "ShotAreaTeamDashboard": [{{ ... stats by court area ... }}],
                            "ShotTypeTeamDashboard": [{{ ... stats by shot type (jump, layup) ... }}],
                            "AssitedShotTeamDashboard": [{{ ... stats for assisted shots ... }}],
                            "AssistedBy": [{{ ... stats on who assisted shots for this team ... }}] // Note: This dataset is for players assisting team shots.
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys match the dataset names.
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_team_dashboard_shooting_splits called for {team_identifier}")
        return fetch_team_dashboard_shooting_splits_logic(
            team_identifier=team_identifier,
            season=season,
            season_type=season_type,
            measure_type=measure_type,
            per_mode=per_mode,
            return_dataframe=return_dataframe
        )

    def get_team_details(
        self,
        team_id: str, # TeamDetails endpoint requires team_id as string
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches comprehensive team details including info, history, social media, championships, retired players, and HOF players.

        Args:
            team_id (str): The NBA Team ID (e.g., "1610612739" for Cleveland Cavaliers). This is required.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, dictionary of DataFrames).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with team details or an error message.
                    Expected success structure:
                    {{
                        "parameters": {{"team_id": str}},
                        "data_sets": {{
                            "TeamInfo": [{{ ... basic team details ... }}],
                            "TeamHistory": [{{ ... historical team names/years ... }}],
                            "SocialMediaAccounts": [{{ ... social media links ... }}],
                            "Championships": [{{ ... championship years ... }}],
                            "ConferenceChampionships": [{{ ... conference championship years ... }}],
                            "DivisionChampionships": [{{ ... division championship years ... }}],
                            "RetiredPlayers": [{{ ... retired player details ... }}],
                            "HallOfFamePlayers": [{{ ... HOF player details ... }}]
                        }}
                    }}
                If return_dataframe=True: Tuple (json_string, dataframes_dict).
                    dataframes_dict keys: "TeamInfo", "TeamHistory", etc.
                    CSV cache paths included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_team_details called for team ID {team_id}")
        return fetch_team_details_logic(
            team_id=team_id,
            return_dataframe=return_dataframe
        )

    # ... (Continue for other team-related tools)
    def get_league_team_estimated_metrics(
        self,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular,
        league_id: str = LeagueID.nba,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches team estimated metrics (E_OFF_RATING, E_DEF_RATING, etc.) for ALL teams in a given season.

        Args:
            season (str, optional): NBA season YYYY-YY. Defaults to current.
            season_type (str, optional): Season type. Defaults to "Regular Season". Possible: "Regular Season", "Playoffs", "Pre Season".
            league_id (str, optional): League ID. Defaults to "00" (NBA). Possible: "00", "10", "".
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, pd.DataFrame]]: JSON string or (JSON, DataFrame).
            JSON includes 'team_estimated_metrics' list for all teams.
            DataFrame key: 'team_estimated_metrics'.
            CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_league_team_estimated_metrics called for season {season}")
        return fetch_team_estimated_metrics_logic(
            season=season,
            season_type=season_type,
            league_id=league_id,
            return_dataframe=return_dataframe
        )

    def get_team_game_logs(
        self,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = "Regular Season",
        per_mode: str = "PerGame",
        measure_type: str = "Base",
        team_id: str = "",
        date_from: str = "",
        date_to: str = "",
        # ... (other params from original logic function)
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches team game logs for a specific team or league-wide.

        Args:
            season (str, optional): Season YYYY-YY. Defaults to current.
            season_type (str, optional): Season type. Defaults to "Regular Season".
            per_mode (str, optional): Per mode. Defaults to "PerGame".
            measure_type (str, optional): Measure type. Defaults to "Base".
            team_id (str, optional): Team ID to filter. Defaults to "" (league-wide).
            date_from (str, optional): Start date MM/DD/YYYY. Defaults to "".
            date_to (str, optional): End date MM/DD/YYYY. Defaults to "".
            // ... (include other relevant optional args here like league_id, location, outcome etc.)
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame).
            JSON includes 'data_sets' with key like 'TeamGameLogs'.
            DataFrame dict key: 'TeamGameLogs'.
            CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_team_game_logs called for season {season}, team ID: {team_id or 'League-wide'}")
        return fetch_team_game_logs_logic(
            season=season, season_type=season_type, per_mode=per_mode, measure_type=measure_type,
            team_id=team_id, date_from=date_from, date_to=date_to,
            # Pass other relevant parameters from the signature
            return_dataframe=return_dataframe
        )

    def get_team_general_stats(
        self,
        team_identifier: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular,
        per_mode: str = PerModeDetailed.per_game,
        measure_type: str = MeasureTypeDetailedDefense.base,
        # ... (other params from original logic function)
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches comprehensive team statistics: current season dashboard stats and historical year-by-year performance.

        Args:
            team_identifier (str): Name, abbreviation, or ID of the team.
            season (str, optional): Season for dashboard stats YYYY-YY. Defaults to current.
            season_type (str, optional): Season type for dashboard. Defaults to "Regular Season".
            per_mode (str, optional): Per mode for dashboard. Defaults to "PerGame".
            measure_type (str, optional): Measure type for dashboard. Defaults to "Base".
            // ... (include other relevant optional args like league_id, opponent_team_id etc.)
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames).
            JSON includes 'current_season_dashboard_stats' and 'historical_year_by_year_stats'.
            DataFrames dict keys: 'dashboard', 'historical'.
            CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_team_general_stats called for {team_identifier}, season {season}")
        return fetch_team_stats_logic(
            team_identifier=team_identifier, season=season, season_type=season_type,
            per_mode=per_mode, measure_type=measure_type,
            # Pass other relevant parameters from the signature
            return_dataframe=return_dataframe
        )

    def get_team_historical_leaders(
        self,
        team_identifier: str,
        season_id: str, # e.g., "22022" for 2022-23 season
        league_id: str = LeagueID.nba,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches historical career leaders for a specific team as of a given season_id.

        Args:
            team_identifier (str): Name, abbreviation, or ID of the team.
            season_id (str): The 5-digit season ID (e.g., "22022" for the 2022-23 season).
                             This specifies the point in time for historical leaders.
            league_id (str, optional): League ID. Defaults to "00" (NBA).
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame).
            JSON includes 'career_leaders_by_team' list.
            DataFrame dict key: 'career_leaders_by_team'.
        """
        logger.info(f"TeamToolkit: get_team_historical_leaders for team {team_identifier}, season_id {season_id}")
        return fetch_team_historical_leaders_logic(
            team_identifier=team_identifier,
            season_id=season_id,
            league_id=league_id,
            return_dataframe=return_dataframe
        )

    def get_common_team_years(
        self,
        league_id: str = LeagueID.nba,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches a list of all team years for a given league, indicating the range of seasons each team existed.
        This is a league-wide utility but useful in team contexts for historical data.

        Args:
            league_id (str, optional): League ID. Defaults to "00" (NBA). Possible: "00", "10", "20".
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame).
            JSON includes 'team_years' list.
            DataFrame dict key: 'team_years'.
            CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_common_team_years called for league {league_id}")
        return fetch_common_team_years_logic(
            league_id=league_id,
            return_dataframe=return_dataframe
        )

    def get_team_info_and_roster(
        self,
        team_identifier: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular,
        league_id: str = LeagueID.nba,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches comprehensive team information: basic details, ranks, roster, and coaches.

        Args:
            team_identifier (str): Name, abbreviation, or ID of the team.
            season (str, optional): Season YYYY-YY. Defaults to current.
            season_type (str, optional): Season type. Defaults to "Regular Season".
            league_id (str, optional): League ID. Defaults to "00" (NBA).
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames).
            JSON includes 'info', 'ranks', 'roster', 'coaches'.
            DataFrames dict keys: 'team_info', 'team_ranks', 'roster', 'coaches'.
            CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_team_info_and_roster called for {team_identifier}, season {season}")
        return fetch_team_info_and_roster_logic(
            team_identifier=team_identifier, season=season, season_type=season_type,
            league_id=league_id, return_dataframe=return_dataframe
        )

    def get_team_passing_stats(
        self,
        team_identifier: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular,
        per_mode: str = PerModeSimple.per_game,
        # ... other params from original logic function
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches team passing statistics (passes made and received).

        Args:
            team_identifier (str): Name, abbreviation, or ID of the team.
            season (str, optional): Season YYYY-YY. Defaults to current.
            season_type (str, optional): Season type. Defaults to "Regular Season".
            per_mode (str, optional): Statistical mode. Defaults to "PerGame".
            // ... (include other relevant optional args like league_id, opponent_team_id etc.)
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames).
            JSON includes 'passes_made' and 'passes_received' lists.
            DataFrames dict keys: 'passes_made', 'passes_received'.
            CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_team_passing_stats called for {team_identifier}, season {season}")
        return fetch_team_passing_stats_logic(
            team_identifier=team_identifier, season=season, season_type=season_type,
            per_mode=per_mode, # Pass other relevant params from signature
            return_dataframe=return_dataframe
        )

    def get_team_player_dashboard_stats(
        self,
        team_identifier: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular,
        per_mode: str = PerModeDetailed.totals,
        measure_type: str = MeasureTypeDetailedDefense.base,
        # ... other params from original logic function
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches team player dashboard statistics (PlayersSeasonTotals and TeamOverall).

        Args:
            team_identifier (str): Name, abbreviation, or ID of the team.
            season (str, optional): Season YYYY-YY. Defaults to current.
            season_type (str, optional): Season type. Defaults to "Regular Season".
            per_mode (str, optional): Per mode. Defaults to "Totals".
            measure_type (str, optional): Measure type. Defaults to "Base".
            // ... (include other relevant optional args like league_id, opponent_team_id etc.)
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames).
            JSON includes 'players_season_totals' and 'team_overall'.
            DataFrames dict keys: 'players_season_totals', 'team_overall'.
        """
        logger.info(f"TeamToolkit: get_team_player_dashboard_stats for {team_identifier}, season {season}")
        return fetch_team_player_dashboard_logic(
            team_identifier=team_identifier, season=season, season_type=season_type,
            per_mode=per_mode, measure_type=measure_type,
            # Pass other relevant parameters
            return_dataframe=return_dataframe
        )

    def get_team_player_on_off_details(
        self,
        team_identifier: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular,
        per_mode: str = PerModeDetailed.totals,
        measure_type: str = MeasureTypeDetailedDefense.base,
        # ... other params from original logic function
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches detailed on/off court statistics for players of a specific team.
        Retrieves 'OverallTeamPlayerOnOffDetails', 'PlayersOffCourtTeamPlayerOnOffDetails', and 'PlayersOnCourtTeamPlayerOnOffDetails'.

        Args:
            team_identifier (str): Name, abbreviation, or ID of the team.
            season (str, optional): Season YYYY-YY. Defaults to current.
            season_type (str, optional): Season type. Defaults to "Regular Season".
            per_mode (str, optional): Statistical mode. Defaults to "Totals".
            measure_type (str, optional): Measure type. Defaults to "Base". (API uses MeasureTypeDetailedDefense).
            // ... (include other relevant optional args like league_id, opponent_team_id, date_from, date_to, etc.)
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames).
            JSON structure includes keys for each dataset (overall, off_court, on_court).
            DataFrames dict keys: 'overall', 'off_court', 'on_court'.
            CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_team_player_on_off_details called for {team_identifier}, season {season}")
        return fetch_team_player_on_off_details_logic(
            team_identifier=team_identifier, season=season, season_type=season_type,
            per_mode=per_mode, measure_type=measure_type,
            # Pass other relevant parameters
            return_dataframe=return_dataframe
        )

    def get_team_player_on_off_summary(
        self,
        team_identifier: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type_all_star: str = SeasonTypeAllStar.regular,
        per_mode_detailed: str = PerModeDetailed.totals,
        measure_type_detailed_defense: str = MeasureTypeDetailedDefense.base,
        # ... other params from original logic function
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches team player on/off summary statistics.
        Includes 'OverallTeamPlayerOnOffSummary', 'PlayersOffCourtTeamPlayerOnOffSummary', 'PlayersOnCourtTeamPlayerOnOffSummary'.

        Args:
            team_identifier (str): Name, abbreviation, or ID of the team.
            season (str, optional): Season YYYY-YY. Defaults to current.
            season_type_all_star (str, optional): Season type. Defaults to "Regular Season".
            per_mode_detailed (str, optional): Per mode. Defaults to "Totals".
            measure_type_detailed_defense (str, optional): Measure type. Defaults to "Base".
            // ... (include other relevant optional args from the logic function)
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames).
            DataFrames dict keys: 'overall', 'off_court', 'on_court'.
            CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_team_player_on_off_summary for {team_identifier}, season {season}")
        return fetch_teamplayeronoffsummary_logic(
            team_identifier=team_identifier, season=season, season_type_all_star=season_type_all_star,
            per_mode_detailed=per_mode_detailed, measure_type_detailed_defense=measure_type_detailed_defense,
            # Pass other relevant parameters
            return_dataframe=return_dataframe
        )

    def get_team_rebounding_tracking_stats(
        self,
        team_identifier: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular,
        per_mode: str = PerModeSimple.per_game,
        # ... other params from original logic function
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches team-level rebounding tracking statistics (overall, by shot type, contest, shot distance, rebound distance).

        Args:
            team_identifier (str): Name, abbreviation, or ID of the team.
            season (str, optional): Season YYYY-YY. Defaults to current.
            season_type (str, optional): Season type. Defaults to "Regular Season".
            per_mode (str, optional): Statistical mode. Defaults to "PerGame".
            // ... (include other relevant optional args from the logic function)
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames).
            JSON includes 'overall', 'by_shot_type', 'by_contest', etc.
            DataFrames dict keys match these categories.
            CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_team_rebounding_tracking_stats for {team_identifier}, season {season}")
        return fetch_team_rebounding_stats_logic(
            team_identifier=team_identifier, season=season, season_type=season_type,
            per_mode=per_mode, # Pass other relevant parameters
            return_dataframe=return_dataframe
        )

    def get_team_shooting_tracking_stats(
        self,
        team_identifier: str,
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular,
        per_mode: str = PerModeSimple.per_game,
        # ... other params from original logic function
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches team-level shooting tracking statistics (general, by shot clock, dribble, defender distance, touch time).

        Args:
            team_identifier (str): Name, abbreviation, or ID of the team.
            season (str, optional): Season YYYY-YY. Defaults to current.
            season_type (str, optional): Season type. Defaults to "Regular Season".
            per_mode (str, optional): Statistical mode. Defaults to "PerGame".
            // ... (include other relevant optional args from the logic function)
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames).
            JSON includes 'overall_shooting', 'general_shooting_splits', 'by_shot_clock', etc.
            DataFrames dict keys match these categories.
            CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_team_shooting_tracking_stats for {team_identifier}, season {season}")
        return fetch_team_shooting_stats_logic(
            team_identifier=team_identifier, season=season, season_type=season_type,
            per_mode=per_mode, # Pass other relevant parameters
            return_dataframe=return_dataframe
        )

    def get_team_vs_player_stats(
        self,
        team_identifier: str,
        vs_player_identifier: str, # Name or ID of opposing player
        season: str = settings.CURRENT_NBA_SEASON,
        season_type: str = SeasonTypeAllStar.regular,
        per_mode: str = PerModeDetailed.totals,
        measure_type: str = MeasureTypeDetailedDefense.base,
        # ... other params from original logic function
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches detailed statistics for a team when a specific opposing player is on/off the court.
        Includes overall team performance, player's performance against the team, and shot breakdowns.

        Args:
            team_identifier (str): Name, abbreviation, or ID of the team.
            vs_player_identifier (str): Name or ID of the opposing player to analyze against.
            season (str, optional): Season YYYY-YY. Defaults to current.
            season_type (str, optional): Season type. Defaults to "Regular Season".
            per_mode (str, optional): Statistical mode. Defaults to "Totals".
            measure_type (str, optional): Measure type. Defaults to "Base".
            // ... (include other relevant optional args like league_id, date_from, location etc.)
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames).
            JSON includes 'overall', 'on_off_court', 'shot_area_overall', 'vs_player_overall', etc.
            DataFrames dict keys match these categories.
            CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_team_vs_player_stats for team {team_identifier} vs player {vs_player_identifier}, season {season}")
        return fetch_teamvsplayer_logic(
            team_identifier=team_identifier, vs_player_identifier=vs_player_identifier,
            season=season, season_type=season_type, per_mode=per_mode, measure_type=measure_type,
            # Pass other relevant parameters
            return_dataframe=return_dataframe
        )

    def get_league_franchise_history(
        self,
        league_id: str = "00",
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches franchise history data for ALL teams in a league, including current and defunct teams.

        Args:
            league_id (str, optional): League ID. Defaults to "00" (NBA). Possible: "00", "10" (WNBA).
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames).
            JSON includes 'data_sets' with keys 'FranchiseHistory' and 'DefunctTeams'.
            DataFrames dict keys: 'FranchiseHistory', 'DefunctTeams'.
            CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_league_franchise_history for league {league_id}")
        return fetch_franchise_history_logic(
            league_id=league_id, return_dataframe=return_dataframe
        )

    def get_franchise_leaders(
        self,
        team_identifier: str, # Team ID is required for this endpoint.
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches all-time statistical leaders for a specific franchise.

        Args:
            team_identifier (str): Name, abbreviation, or ID of the team. The underlying API requires team_id.
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame).
            JSON includes 'data_sets' with key 'FranchiseLeaders'.
            DataFrame dict key: 'FranchiseLeaders'.
            CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_franchise_leaders for team {team_identifier}")
        try:
            team_id_val, _ = find_team_id_or_error(team_identifier)
        except Exception as e:
            logger.error(f"Error finding team ID for '{team_identifier}': {e}", exc_info=True)
            error_response = format_response(error=str(e))
            if return_dataframe:
                return error_response, {}
            return error_response

        return fetch_franchise_leaders_logic(
            team_id=str(team_id_val), return_dataframe=return_dataframe
        )

    def get_franchise_players(
        self,
        team_identifier: str, # Team ID is required for this endpoint.
        league_id: str = "00",
        per_mode_detailed: str = PerModeDetailed.totals,
        season_type_all_star: str = SeasonTypeAllStar.regular,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches all players who have ever played for a specific franchise, with their stats for that franchise.

        Args:
            team_identifier (str): Name, abbreviation, or ID of the team. The underlying API requires team_id.
            league_id (str, optional): League ID. Defaults to "00" (NBA).
            per_mode_detailed (str, optional): Statistical mode. Defaults to "Totals".
            season_type_all_star (str, optional): Season type. Defaults to "Regular Season".
            return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame).
            JSON includes 'data_sets' with key 'FranchisePlayers'.
            DataFrame dict key: 'FranchisePlayers'.
            CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"TeamToolkit: get_franchise_players for team {team_identifier}")
        try:
            team_id_val, _ = find_team_id_or_error(team_identifier)
        except Exception as e:
            logger.error(f"Error finding team ID for '{team_identifier}': {e}", exc_info=True)
            error_response = format_response(error=str(e))
            if return_dataframe:
                return error_response, {}
            return error_response

        return fetch_franchise_players_logic(
            team_id=str(team_id_val), league_id=league_id, per_mode_detailed=per_mode_detailed,
            season_type_all_star=season_type_all_star, return_dataframe=return_dataframe
        )